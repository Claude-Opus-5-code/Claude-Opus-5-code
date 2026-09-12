"""Single-request chat workflow. Fresh sessions; never resubmit accepted jobs."""

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx

from ._accounts import AccountPool, PoolFailure
from ._config import MODEL_AI_NAMES, ProviderConfig
from ._images import Image, upload_image
from ._maintenance import trigger_maintenance
from ._transport import Deadline, Transport, UpstreamFailure


@dataclass(frozen=True)
class Reply:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str = "stop"


def _token_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _completed(body: dict, chat_uuid: str, job_id: str | None) -> Reply | None:
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise UpstreamFailure("non_retryable_error")
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("author_id") != -1:
            continue
        if message.get("chat_uuid", chat_uuid) != chat_uuid:
            continue
        if job_id is not None and message.get("job_id", job_id) != job_id:
            continue
        objects = message.get("message_object")
        if not isinstance(objects, list):
            continue
        parts = [
            item for item in objects if isinstance(item, dict) and item.get("object_type") == "text"
        ]
        if not parts or any(item.get("completed") is not True for item in parts):
            continue
        if any(not isinstance(item.get("object_text"), str) for item in parts):
            raise UpstreamFailure("non_retryable_error")
        usage = message.get("usage", body.get("usage", {}))
        usage = usage if isinstance(usage, dict) else {}
        finish = message.get("finish_reason")
        return Reply(
            text="\n".join(item["object_text"] for item in parts),
            input_tokens=_token_count(usage.get("input_tokens", usage.get("prompt_tokens"))),
            output_tokens=_token_count(usage.get("output_tokens", usage.get("completion_tokens"))),
            finish_reason=finish if finish in ("stop", "length", "filter") else "stop",
        )
    return None


async def generate(
    *,
    model: str,
    text: str,
    timeout_ms: int,
    config: ProviderConfig | None = None,
    pool: AccountPool | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    deadline: Deadline | None = None,
    image: Image | None = None,
) -> Reply:
    config = config or ProviderConfig()
    pool = pool or AccountPool(config)
    deadline = deadline or Deadline.after_ms(timeout_ms)
    if model not in MODEL_AI_NAMES:
        raise UpstreamFailure("model_unavailable")
    trigger_maintenance(config, pool=pool, transport=transport)
    try:
        async with asyncio.timeout(deadline.remaining()):
            account = await pool.select(deadline.end)
            try:
                async with Transport(
                    account.token, deadline, transport=transport, cooldown=config.cooldown_seconds
                ) as wire:
                    created = await wire.request(
                        "POST",
                        "chats",
                        json={
                            "title": f"Request {uuid4()}",
                            "scope": "text",
                        },
                    )
                    try:
                        chat_uuid = str(UUID(created["uuid"]))
                    except (KeyError, ValueError, TypeError, AttributeError):
                        raise UpstreamFailure("non_retryable_error") from None
                    payload = {
                        "chat_uuid": chat_uuid,
                        "text": text,
                        "model": model,
                        **config.generation_settings(),
                    }
                    if image is not None:
                        payload["files"] = await upload_image(wire, image)
                    accepted = await wire.request(
                        "POST",
                        "llm/generate",
                        params={"ai_name": MODEL_AI_NAMES[model]},
                        json=payload,
                    )
                    job_id = accepted.get("job_id")
                    job_id = job_id if isinstance(job_id, str) else None
                    while True:
                        body = await wire.request(
                            "GET", f"chats/{chat_uuid}/messages", params={"page_size": 20}
                        )
                        reply = _completed(body, chat_uuid, job_id)
                        if reply is not None:
                            deadline.remaining()
                            return reply
                        await deadline.sleep(config.poll_interval)
            except UpstreamFailure as exc:
                await pool.record_failure(account.token, exc.kind, deadline.end, exc.retry_after_ms)
                raise
    except TimeoutError:
        raise UpstreamFailure("timeout") from None
    except PoolFailure as exc:
        kind = {"no_accounts": "provider_unavailable", "storage": "provider_unavailable"}.get(
            exc.kind, exc.kind
        )
        raise UpstreamFailure(kind, retry_after_ms=exc.retry_after_ms) from None
