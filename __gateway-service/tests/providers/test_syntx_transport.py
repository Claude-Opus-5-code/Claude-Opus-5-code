"""Transport uses mock HTTP only; no credentials, DNS, service or subprocesses."""

import asyncio
import time

import httpx
import pytest

from providers.syntx._transport import Deadline, Transport, UpstreamFailure


@pytest.mark.parametrize(
    "status,body,kind",
    [
        (401, {}, "invalid_credential"),
        (403, {}, "invalid_credential"),
        (403, {"detail": {"code": "chat.modelNotAvailableForPlan"}}, "model_unavailable"),
        (401, {"detail": {"code": "token_expired"}}, "auth_expired"),
        (429, {}, "rate_limited"),
        (429, {"detail": {"code": "quota_exceeded"}}, "quota_exceeded"),
        (400, {"detail": {"code": "content_policy_violation"}}, "content_rejected"),
        (400, {}, "bad_request"),
        (413, {}, "bad_request"),
        (422, {}, "bad_request"),
        (404, {}, "model_unavailable"),
        (418, {}, "non_retryable_error"),
        (500, {}, "retryable_server_error"),
        (501, {}, "retryable_server_error"),
        (599, {}, "retryable_server_error"),
        (302, {}, "non_retryable_error"),
    ],
)
async def test_http_failure_mapping(status, body, kind):
    def respond(request):
        return httpx.Response(
            status, json=body, headers={"Location": "https://other.invalid/secret"}
        )

    async with Transport(
        "synthetic-token", Deadline.after_ms(500), transport=httpx.MockTransport(respond)
    ) as wire:
        with pytest.raises(UpstreamFailure) as exc:
            await wire.request("POST", "chats")
    assert exc.value.kind == kind
    assert exc.value.status == status
    assert "synthetic-token" not in str(exc.value)
    assert "other.invalid" not in str(exc.value)


async def test_cooldown_uses_longest_evidence():
    def respond(request):
        return httpx.Response(
            429, headers={"Retry-After": "90"}, json={"detail": {"retry_after_seconds": 21526}}
        )

    async with Transport(
        "test", Deadline.after_ms(500), transport=httpx.MockTransport(respond)
    ) as wire:
        with pytest.raises(UpstreamFailure) as exc:
            await wire.request("GET", "llm/limits")
        assert exc.value.retry_after_ms == 21526000


@pytest.mark.parametrize("response", [b"not-json", b"[]", b"null"])
async def test_invalid_success_body_is_not_success(response):
    async with Transport(
        "test",
        Deadline.after_ms(500),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=response)),
    ) as wire:
        with pytest.raises(UpstreamFailure) as exc:
            await wire.request("POST", "chats")
        assert exc.value.kind == "non_retryable_error"


@pytest.mark.parametrize("path", ["https://other.invalid", "../secrets", "/chats", "chats/../user"])
async def test_internal_path_guard_never_sends_arbitrary_url(path):
    def forbidden(request):
        pytest.fail("unexpected request")

    async with Transport(
        "test", Deadline.after_ms(500), transport=httpx.MockTransport(forbidden)
    ) as wire:
        with pytest.raises(UpstreamFailure):
            await wire.request("GET", path)


async def test_total_budget_cancels_mock_that_ignores_http_timeout():
    cancelled = asyncio.Event()

    async def respond(request):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    start = time.monotonic()
    async with Transport(
        "test", Deadline.after_ms(30), transport=httpx.MockTransport(respond)
    ) as wire:
        with pytest.raises(UpstreamFailure) as exc:
            await wire.request("POST", "chats")
        assert exc.value.kind == "timeout"
    assert cancelled.is_set()
    assert time.monotonic() - start < 0.5


@pytest.mark.parametrize(
    "error,kind",
    [
        (httpx.ReadTimeout("sensitive token url"), "timeout"),
        (httpx.ConnectError("sensitive token url"), "provider_unavailable"),
    ],
)
async def test_safe_network_failures(error, kind):
    def respond(request):
        raise error

    async with Transport(
        "test", Deadline.after_ms(500), transport=httpx.MockTransport(respond)
    ) as wire:
        with pytest.raises(UpstreamFailure) as exc:
            await wire.request("POST", "chats")
        assert exc.value.kind == kind
        assert "sensitive" not in str(exc.value)
