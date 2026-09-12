"""Exercise the real orchestration against deterministic mock transport."""

import asyncio
import json
import time
from uuid import uuid4

import httpx
import pytest

from providers.syntx._accounts import AccountPool
from providers.syntx._config import MODEL_AI_NAMES, ProviderConfig
from providers.syntx._transport import UpstreamFailure
from providers.syntx._upstream import generate


@pytest.fixture
async def setup_chat(tmp_path):
    cfg = ProviderConfig(state_dir=tmp_path, poll_interval=0.001, maintenance_enabled=False)
    pool = AccountPool(cfg)
    await pool.add_authorized(
        [{"token": "test-token", "status": "active", "chat_uuid": str(uuid4())}],
        time.monotonic() + 2,
    )
    return cfg, pool


def completed(text="reply", **extra):
    return {
        "author_id": -1,
        "message_object": [{"object_type": "text", "object_text": text, "completed": True}],
        **extra,
    }


@pytest.mark.parametrize("model", list(MODEL_AI_NAMES))
async def test_models_payload_and_official_usage(setup_chat, model):
    cfg, pool = setup_chat
    session = str(uuid4())
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path.endswith("/chats"):
            return httpx.Response(201, json={"uuid": session})
        if request.url.path.endswith("/generate"):
            data = json.loads(request.content)
            assert data["model"] == model
            assert data["chat_uuid"] == session
            assert data["text"] == "hello"
            assert data["thinking"] and data["plan"] and data["deep_research"]
            assert request.url.params["ai_name"] == MODEL_AI_NAMES[model]
            return httpx.Response(200, json={"job_id": "job"})
        return httpx.Response(
            200, json={"messages": [completed(usage={"prompt_tokens": 7, "completion_tokens": 3})]}
        )

    reply = await generate(
        model=model,
        text="hello",
        timeout_ms=500,
        config=cfg,
        pool=pool,
        transport=httpx.MockTransport(respond),
    )
    assert (reply.text, reply.input_tokens, reply.output_tokens) == ("reply", 7, 3)
    assert len(calls) == 3


async def test_concurrent_requests_have_independent_chats_and_no_stale_answers(setup_chat):
    cfg, pool = setup_chat
    sessions = {}
    titles = set()

    async def respond(request):
        if request.url.path.endswith("/chats"):
            titles.add(json.loads(request.content)["title"])
            return httpx.Response(201, json={"uuid": str(uuid4())})
        if request.url.path.endswith("/generate"):
            data = json.loads(request.content)
            sessions[data["chat_uuid"]] = data["text"]
            return httpx.Response(200, json={"job_id": data["chat_uuid"]})
        session = request.url.path.split("/")[-2]
        await asyncio.sleep(0.01)
        return httpx.Response(
            200,
            json={
                "messages": [
                    completed(sessions[session], chat_uuid=session),
                    completed("WRONG", chat_uuid=str(uuid4())),
                    completed("WRONG JOB", job_id="other"),
                ]
            },
        )

    responses = await asyncio.gather(
        *(
            generate(
                model="grok-4.6",
                text=text,
                timeout_ms=500,
                config=cfg,
                pool=pool,
                transport=httpx.MockTransport(respond),
            )
            for text in ("first", "second")
        )
    )
    assert [item.text for item in responses] == ["first", "second"]
    assert len(sessions) == len(titles) == 2
    assert all(item.input_tokens is item.output_tokens is None for item in responses)


@pytest.mark.parametrize(
    "status,body,kind,state",
    [
        (403, {"detail": {"code": "modelNotAvailableForPlan"}}, "model_unavailable", "active"),
        (401, {}, "invalid_credential", "invalid"),
        (429, {}, "rate_limited", "cooldown"),
    ],
)
async def test_error_state_updates_without_resubmission(setup_chat, status, body, kind, state):
    cfg, pool = setup_chat
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path.endswith("/chats"):
            return httpx.Response(201, json={"uuid": str(uuid4())})
        return httpx.Response(status, json=body)

    with pytest.raises(UpstreamFailure) as exc:
        await generate(
            model="grok-4.6",
            text="hi",
            timeout_ms=500,
            config=cfg,
            pool=pool,
            transport=httpx.MockTransport(respond),
        )
    assert exc.value.kind == kind
    assert len(calls) == 2
    assert (await pool.snapshot(time.monotonic() + 1))[0]["status"] == state


async def test_unfinished_poll_times_out_without_resubmitting(setup_chat):
    cfg, pool = setup_chat
    generations = 0

    def respond(request):
        nonlocal generations
        if request.url.path.endswith("/chats"):
            return httpx.Response(201, json={"uuid": str(uuid4())})
        if request.url.path.endswith("/generate"):
            generations += 1
            return httpx.Response(200, json={"job_id": "j"})
        partial = completed("partial")
        partial["message_object"][0]["completed"] = False
        return httpx.Response(200, json={"messages": [partial]})

    with pytest.raises(UpstreamFailure) as exc:
        await generate(
            model="grok-4.6",
            text="hi",
            timeout_ms=30,
            config=cfg,
            pool=pool,
            transport=httpx.MockTransport(respond),
        )
    assert exc.value.kind == "timeout"
    assert generations == 1


async def test_caller_cancellation_propagates(setup_chat):
    cfg, pool = setup_chat
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def respond(request):
        entered.set()
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    task = asyncio.create_task(
        generate(
            model="grok-4.6",
            text="hi",
            timeout_ms=500,
            config=cfg,
            pool=pool,
            transport=httpx.MockTransport(respond),
        )
    )
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
