"""Canonical facade tests: synthetic pool and mock transport, never real service.

Replaces obsolete shared-chat/environment-token fixtures, retaining original
success, schema, HTTP failure, missing pool, timeout and secret-safety coverage.
"""

import json
import time
from uuid import uuid4

import httpx
import pytest

from gateway.contracts import (
    CredentialMode,
    ErrorCategory,
    GatewayOperation,
    ProviderContext,
    ProviderDefinition,
)
from gateway.errors import RETRYABLE_DEFAULTS
from providers.syntx import DEFINITION, HANDLERS, _upstream
from providers.syntx._accounts import AccountPool
from providers.syntx._config import ProviderConfig
from providers.syntx._transport import UpstreamFailure
from providers.syntx.adapter import analyze_vision, generate_text

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aV1cAAAAASUVORK5CYII="
FAKE_KEY = "sentinel_credential_never_real"


def context(payload=None, operation=GatewayOperation.GENERATE_TEXT, **overrides):
    data = dict(
        operation=operation,
        model="grok-4.6",
        request_id="req",
        tenant_id="tenant",
        credential_mode=CredentialMode.PLATFORM,
        timeout_ms=500,
        payload={"messages": [{"role": "user", "content": "hi"}]} if payload is None else payload,
    )
    return ProviderContext(**(data | overrides))


@pytest.fixture
async def install(tmp_path, monkeypatch):
    cfg = ProviderConfig(state_dir=tmp_path, poll_interval=0.001, maintenance_enabled=False)
    pool = AccountPool(cfg)
    await pool.add_authorized([{"token": FAKE_KEY, "status": "active"}], time.monotonic() + 1)
    real_generate = _upstream.generate

    def use(responder):
        async def call(**kwargs):
            return await real_generate(
                **kwargs, config=cfg, pool=pool, transport=httpx.MockTransport(responder)
            )

        monkeypatch.setattr(_upstream, "generate", call)

    return use, pool


def test_definition_parity_and_honesty():
    parsed = ProviderDefinition.model_validate(DEFINITION)
    assert {op.value for op in HANDLERS} == set(DEFINITION["operations"])
    assert set(DEFINITION["operations"]) == {"generate_text", "analyze_vision"}
    assert parsed.credential_mode is CredentialMode.PLATFORM
    assert parsed.capabilities["vision_input"] is True
    assert parsed.health_supported is False
    assert {m.name for m in parsed.models} == {
        "gpt-5.6-terra",
        "claude-opus-4-8",
        "claude-sonnet-5",
        "grok-4.6",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"messages": []},
        {"messages": "bad"},
        {"messages": [None]},
        {"messages": [{"role": "user", "content": []}]},
        {"messages": [{"role": "user", "content": "x", "extra": True}]},
        {"messages": [{"role": "user", "content": "x"}], "files": []},
        {"messages": [{"role": "user", "content": "x"}], "temperature": True},
        {"messages": [{"role": "user", "content": "x"}], "temperature": float("nan")},
        {"messages": [{"role": "user", "content": "x"}], "max_tokens": "20"},
    ],
)
async def test_bad_schema_does_not_call_upstream(payload, monkeypatch):
    async def forbidden(**kwargs):
        pytest.fail("upstream must not run for invalid payload")

    monkeypatch.setattr(_upstream, "generate", forbidden)
    result = await generate_text(context(payload))
    assert result.error.category is ErrorCategory.BAD_REQUEST


async def test_success_preserves_history_once_and_ignores_unsupported_controls(install):
    use, _ = install
    prompt = []

    def respond(request):
        if request.url.path.endswith("/chats"):
            return httpx.Response(201, json={"uuid": str(uuid4())})
        if request.url.path.endswith("/generate"):
            data = json.loads(request.content)
            prompt.append(data["text"])
            assert "temperature" not in data and "max_tokens" not in data
            return httpx.Response(200, json={"job_id": "job"})
        return httpx.Response(
            200,
            json={
                "messages": [
                    {
                        "author_id": -1,
                        "usage": {"input_tokens": 5, "output_tokens": 8},
                        "message_object": [
                            {"object_type": "text", "object_text": "answer", "completed": True}
                        ],
                    }
                ]
            },
        )

    use(respond)
    result = await generate_text(
        context(
            {
                "messages": [
                    {"role": "system", "content": "instruction"},
                    {"role": "assistant", "content": "earlier"},
                    {"role": "user", "content": "latest"},
                ],
                "temperature": 0.5,
                "max_tokens": 50,
            }
        )
    )
    assert result.succeeded and result.output == {"text": "answer", "finish_reason": "stop"}
    assert result.usage.input_tokens == 5 and result.usage.output_tokens == 8
    assert result.usage.units == 1
    assert prompt == [
        "Previous conversation:\nsystem: instruction\n\nassistant: earlier\n\n"
        "Current request:\nuser: latest"
    ]


async def test_vision_canonical_output(install):
    use, _ = install

    def respond(request):
        if request.url.path.endswith("/chats"):
            return httpx.Response(201, json={"uuid": str(uuid4())})
        if request.url.path.endswith("/upload-files"):
            return httpx.Response(
                200, json={"files": [{"url": "https://assets.example.invalid/i.png"}]}
            )
        if request.url.path.endswith("/generate"):
            assert json.loads(request.content)["files"][0]["object_type"] == "image"
            return httpx.Response(200, json={"job_id": "job"})
        return httpx.Response(
            200,
            json={
                "messages": [
                    {
                        "author_id": -1,
                        "message_object": [
                            {"object_type": "text", "completed": True, "object_text": "a pixel"}
                        ],
                    }
                ]
            },
        )

    use(respond)
    result = await analyze_vision(
        context(
            {"image_b64": PNG, "image_format": "png", "instruction": "describe"},
            operation=GatewayOperation.ANALYZE_VISION,
        )
    )
    assert result.output == {"text": "a pixel"}
    assert result.usage.input_tokens is result.usage.output_tokens is None


@pytest.mark.parametrize(
    "status,kind",
    [
        (401, ErrorCategory.INVALID_CREDENTIAL),
        (403, ErrorCategory.INVALID_CREDENTIAL),
        (404, ErrorCategory.MODEL_UNAVAILABLE),
        (429, ErrorCategory.RATE_LIMITED),
        (400, ErrorCategory.BAD_REQUEST),
        (422, ErrorCategory.BAD_REQUEST),
        (500, ErrorCategory.RETRYABLE_SERVER_ERROR),
        (599, ErrorCategory.RETRYABLE_SERVER_ERROR),
    ],
)
async def test_http_failures_and_secret_safety(install, status, kind):
    use, _ = install
    use(
        lambda request: httpx.Response(
            status,
            json={
                "detail": {
                    "message": f"secret={FAKE_KEY} /private/path https://private.invalid",
                    "retry_after_seconds": 21526,
                }
            },
        )
    )
    result = await generate_text(context())
    assert not result.succeeded and result.error.category is kind
    assert result.output is result.usage is None
    assert FAKE_KEY not in result.model_dump_json()
    assert "/private" not in result.model_dump_json()
    if status == 429:
        assert result.error.retry_after_ms == 21526000


@pytest.mark.parametrize("category", list(ErrorCategory))
async def test_all_twelve_categories_cross_facade_with_contract_retryability(monkeypatch, category):
    async def fail(**kwargs):
        raise UpstreamFailure(category.value, retry_after_ms=1000)

    monkeypatch.setattr(_upstream, "generate", fail)
    result = await generate_text(context())
    assert result.error.category is category
    assert result.error.retryable is RETRYABLE_DEFAULTS[category]
    assert result.error.retry_after_ms == (1000 if category is ErrorCategory.RATE_LIMITED else None)


async def test_empty_pool_is_unavailable(install):
    use, pool = install
    pool.config.accounts_file.unlink()
    use(lambda request: pytest.fail("empty pool must not call upstream"))
    assert (await generate_text(context())).error.category is ErrorCategory.PROVIDER_UNAVAILABLE


async def test_timeout(install):
    use, _ = install

    def respond(request):
        raise httpx.ReadTimeout("secret private url")

    use(respond)
    assert (await generate_text(context())).error.category is ErrorCategory.TIMEOUT


async def test_unexpected_exception_is_safe(monkeypatch):
    async def fail(**kwargs):
        raise RuntimeError(FAKE_KEY)

    monkeypatch.setattr(_upstream, "generate", fail)
    result = await generate_text(context())
    assert result.error.category is ErrorCategory.NON_RETRYABLE_ERROR
    assert FAKE_KEY not in result.model_dump_json()


async def test_wrong_operation_is_unsupported():
    result = await generate_text(context(operation=GatewayOperation.GENERATE_IMAGE))
    assert result.error.category is ErrorCategory.UNSUPPORTED_CAPABILITY


async def test_caller_credentials_are_not_used():
    result = await generate_text(
        context(credential_mode=CredentialMode.USER_KEY, credential_value=FAKE_KEY)
    )
    assert result.error.category is ErrorCategory.INVALID_CREDENTIAL
