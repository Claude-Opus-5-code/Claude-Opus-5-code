"""Hermetic Syntx provider tests — facade + Layer 1 with MockTransport only.

ZERO network. The upstream is an ``httpx.MockTransport`` installed through
the Layer-1 test seam; credentials come from a test fixture or env sentinel.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from gateway.contracts import (
    CredentialMode,
    ErrorCategory,
    GatewayOperation,
    ProviderContext,
)
from providers.syntx import _upstream
from providers.syntx._upstream import API_KEY_ENV
from providers.syntx.adapter import HANDLERS, generate_text
from providers.syntx.definition import DEFINITION

FAKE_KEY = "syntx_test_token_sentinel_never_real"
FAKE_CHAT_UUID = "07d713b3-d876-465e-8d8c-970ec1ef3cdb"


@pytest.fixture(autouse=True)
def _fake_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, FAKE_KEY)
    monkeypatch.setenv("GW_SYNTX_CHAT_UUID", FAKE_CHAT_UUID)


@pytest.fixture
def recorder() -> list[httpx.Request]:
    return []


def _install(
    monkeypatch: pytest.MonkeyPatch,
    responder: Any,
    log: list[httpx.Request],
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        log.append(request)
        return responder(request)

    monkeypatch.setattr(_upstream, "_default_transport", httpx.MockTransport(_handler))


def _context(
    payload: dict[str, Any] | None = None,
    model: str = "claude-opus-4-8",
) -> ProviderContext:
    return ProviderContext(
        operation=GatewayOperation.GENERATE_TEXT,
        model=model,
        request_id="req_syntx_1",
        tenant_id="ten_syntx_1",
        credential_mode=CredentialMode.PLATFORM,
        credential_value=None,
        payload=(
            {"messages": [{"role": "user", "content": "Hello Syntx!"}]}
            if payload is None
            else payload
        ),
        timeout_ms=5000,
    )


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


def test_definition_parity_with_handlers() -> None:
    ops = set(DEFINITION["operations"])  # type: ignore[arg-type]
    handler_ops = {op.value for op in HANDLERS}
    assert ops == handler_ops


def test_definition_honesty() -> None:
    assert DEFINITION["health_supported"] is False
    assert DEFINITION["credential_mode"] == "platform"
    models = DEFINITION["models"]
    assert isinstance(models, list)
    model_names = {m["name"] for m in models}
    assert "claude-opus-4-8" in model_names
    assert "gpt-5.6-terra" in model_names
    assert "claude-sonnet-5" in model_names
    assert "grok-4.6" in model_names


@pytest.mark.asyncio
async def test_schema_rejects_extra_keys() -> None:
    ctx = _context(
        payload={
            "messages": [{"role": "user", "content": "hi"}],
            "unexpected_extra_key": "bad",
        }
    )
    result = await generate_text(ctx)
    assert not result.succeeded
    assert result.error is not None
    assert result.error.category == ErrorCategory.BAD_REQUEST


@pytest.mark.asyncio
async def test_schema_rejects_empty_messages() -> None:
    ctx = _context(payload={"messages": []})
    result = await generate_text(ctx)
    assert not result.succeeded
    assert result.error is not None
    assert result.error.category == ErrorCategory.BAD_REQUEST


@pytest.mark.asyncio
async def test_canonical_success_shape(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[httpx.Request],
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "/llm/generate" in url_str:
            return httpx.Response(
                200,
                json={
                    "job_id": "eda974de-2543-4279-9732-6e13d9488273",
                    "stream_url": "https://sse.syntx.ai/stream/test",
                },
            )
        if "/messages" in url_str:
            return httpx.Response(
                200,
                json={
                    "messages": [
                        {
                            "author_id": -1,
                            "role": "assistant",
                            "message_object": [
                                {
                                    "object_type": "text",
                                    "object_text": "Hello, I am Claude Opus 4.8 on Syntx!",
                                    "completed": True,
                                }
                            ],
                        }
                    ]
                },
            )
        return httpx.Response(404)

    # Use fast poll for hermetic tests
    monkeypatch.setattr(_upstream, "_poll_messages", lambda client, chat_uuid, headers, timeout_seconds: _mock_fast_poll())
    async def _mock_fast_poll() -> str:
        return "Hello, I am Claude Opus 4.8 on Syntx!"

    _install(monkeypatch, responder, recorder)

    result = await generate_text(_context())
    assert result.succeeded is True
    assert result.output is not None
    assert result.output["text"] == "Hello, I am Claude Opus 4.8 on Syntx!"
    assert result.output["finish_reason"] == "stop"
    assert result.usage is not None
    assert result.usage.units == 1
    assert result.error is None


@pytest.mark.asyncio
async def test_upstream_429_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[httpx.Request],
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "detail": {
                    "code": "chat.text.rateLimitExceeded",
                    "retry_after_seconds": 21526,
                    "error": "rate_limit_exceeded",
                }
            },
        )

    _install(monkeypatch, responder, recorder)

    result = await generate_text(_context())
    assert result.succeeded is False
    assert result.error is not None
    assert result.error.category == ErrorCategory.RATE_LIMITED
    assert result.error.retryable is True
    assert result.error.retry_after_ms == 21526000


@pytest.mark.asyncio
async def test_upstream_401_invalid_credential(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[httpx.Request],
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Unauthorized token"})

    _install(monkeypatch, responder, recorder)

    result = await generate_text(_context())
    assert result.succeeded is False
    assert result.error is not None
    assert result.error.category == ErrorCategory.INVALID_CREDENTIAL


@pytest.mark.asyncio
async def test_upstream_404_model_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[httpx.Request],
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Model not found"})

    _install(monkeypatch, responder, recorder)

    result = await generate_text(_context())
    assert result.succeeded is False
    assert result.error is not None
    assert result.error.category == ErrorCategory.MODEL_UNAVAILABLE


@pytest.mark.asyncio
async def test_upstream_500_retryable_server_error(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[httpx.Request],
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    _install(monkeypatch, responder, recorder)

    result = await generate_text(_context())
    assert result.succeeded is False
    assert result.error is not None
    assert result.error.category == ErrorCategory.RETRYABLE_SERVER_ERROR


@pytest.mark.asyncio
async def test_pool_exhausted_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    monkeypatch.setenv("GW_SYNTX_ACCOUNTS_FILE", "non_existent_empty_pool.json")

    result = await generate_text(_context())
    assert result.succeeded is False
    assert result.error is not None
    assert result.error.category == ErrorCategory.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
async def test_timeout_translated(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[httpx.Request],
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Mocked read timeout")

    _install(monkeypatch, responder, recorder)

    result = await generate_text(_context())
    assert result.succeeded is False
    assert result.error is not None
    assert result.error.category == ErrorCategory.TIMEOUT


@pytest.mark.asyncio
async def test_no_secret_leak(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[httpx.Request],
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": f"Token {FAKE_KEY} was revoked"})

    _install(monkeypatch, responder, recorder)

    result = await generate_text(_context())
    assert result.error is not None
    assert FAKE_KEY not in (result.error.message or "")
    assert FAKE_KEY not in (result.error.provider_code or "")
