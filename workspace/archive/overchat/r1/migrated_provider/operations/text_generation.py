"""Text generation operation - the migrated 4-step flow.

Migrated from source `send_chat_request` L176-324 (network + control flow only;
the printing/stats/file-saving parts of that function live in `legacy/`).

FLOW ORDER IS CONTRACTUAL (source L191-269):

    1. build_mobile_headers()          fresh device identity, per request
    2. GET   /v1/auth/me               -> user_id     ABORTS on failure
    3. PATCH .../generateChatTitle     fire-and-forget, failure ignored
    4. POST  /v1/chat/{user_id}        fire-and-forget, failure ignored
    5. POST  /v2/chat/responses        SSE stream -> accumulated reply

Only step 2 can abort the flow. Steps 3 and 4 are best-effort in the source and
must stay best-effort here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from ..config import OverchatConfig
from ..runtime import request as request_mod
from ..runtime.errors import (
    ProviderError,
    classify_http_status,
    classify_transport_exception,
    is_success_status,
)
from ..runtime.headers import build_mobile_headers
from ..runtime.parser import DeltaEvent, StreamErrorEvent, iter_events
from ..runtime.session import Transport, new_conversation_ids, resolve_user_id


@dataclass
class GenerationResult:
    """Outcome of a generation attempt.

    `text` is the accumulated reply (source `bot_full_reply`). On failure the
    source returned None; here `error` is populated and `text` stays "" so the
    legacy layer can reproduce the None return.
    """

    text: str = ""
    error: ProviderError | None = None
    stream_errors: list[Any] = field(default_factory=list)
    device_uuid: str = ""
    spoofed_ip: str = ""
    user_id: str | None = None
    chat_uuid: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def generate_text(
    prompt_text: str,
    config: OverchatConfig,
    transport: Transport,
    *,
    on_delta: Callable[[str], None] | None = None,
    on_stream_error: Callable[[Any], None] | None = None,
) -> GenerationResult:
    """Execute the full source flow for one prompt.

    `on_delta` reproduces the source's incremental stdout writing (L284-285);
    when omitted, deltas are only accumulated.
    """
    # --- step 1: fresh identity per request (source L191) -------------------
    base_headers, device_uuid, spoofed_ip = build_mobile_headers(
        include_ip_spoof_headers=config.include_ip_spoof_headers,
    )
    result = GenerationResult(device_uuid=device_uuid, spoofed_ip=spoofed_ip)

    # --- step 2: guest auth (source L194-203) - the only aborting step ------
    auth = resolve_user_id(transport, config.base_url, base_headers)
    if not auth.ok:
        result.error = auth.error
        return result
    user_id = auth.user_id
    assert user_id is not None
    result.user_id = user_id

    # --- uuids (source L205-207) -------------------------------------------
    ids = new_conversation_ids()
    result.chat_uuid = ids.chat_uuid

    headers_json = request_mod.json_headers(base_headers)  # source L209-210

    # --- step 3: title, fire-and-forget (source L212-223) ------------------
    request_mod.generate_chat_title(
        transport,
        config.base_url,
        user_id=user_id,
        chat_uuid=ids.chat_uuid,
        prompt_text=prompt_text,
        system_prompt=config.system_prompt,
        model=config.model,
        headers=headers_json,
    )

    # --- step 4: chat init, fire-and-forget (source L225-235) -------------
    request_mod.create_chat_session(
        transport,
        config.base_url,
        user_id=user_id,
        chat_uuid=ids.chat_uuid,
        persona_id=config.persona_id,
        headers=headers_json,
    )

    # --- step 5: SSE generation (source L237-324) -------------------------
    payload = request_mod.build_responses_payload(
        prompt_text,
        model=config.model,
        persona_id=config.persona_id,
        chat_uuid=ids.chat_uuid,
        msg_id_1=ids.msg_id_1,
        msg_id_2=ids.msg_id_2,
    )
    headers_stream = request_mod.build_stream_headers(base_headers)

    try:
        response = request_mod.open_response_stream(
            transport,
            config.base_url,
            payload=payload,
            headers=headers_stream,
            timeout_seconds=config.timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - source L322 catches bare Exception
        result.error = classify_transport_exception(exc, stage="generation")
        return result

    status = int(getattr(response, "status_code", 0))
    if not is_success_status(status):  # source L271 / L318-320
        body = ""
        try:
            body = response.text or ""
        except Exception:  # noqa: BLE001
            body = ""
        result.error = classify_http_status(status, body=body, stage="generation")
        return result

    try:
        chunks: list[str] = []
        for event in iter_events(response.iter_lines()):
            if isinstance(event, DeltaEvent):
                chunks.append(event.text)
                if on_delta is not None:
                    on_delta(event.text)
            elif isinstance(event, StreamErrorEvent):
                # Source L287-288: reported, NOT terminal - loop continues.
                result.stream_errors.append(event.message)
                if on_stream_error is not None:
                    on_stream_error(event.message)
        result.text = "".join(chunks)
    except Exception as exc:  # noqa: BLE001 - source's outer bare except (L322)
        result.error = classify_transport_exception(exc, stage="generation")
        return result

    return result


def stream_text(
    prompt_text: str,
    config: OverchatConfig,
    transport: Transport,
) -> Iterator[str]:
    """Streaming variant: yield each delta as it is parsed.

    This is genuine incremental streaming (deltas are yielded from inside the
    SSE loop, not collected first), matching the source, which writes each
    delta to stdout as it arrives (L284-285). The provider declares the
    `streaming` capability because the source always sends `stream: True`.

    Raises `OverchatError` with a normalized error if the flow fails before the
    stream opens.
    """
    from ..runtime.errors import OverchatError

    base_headers, _device_uuid, _spoofed_ip = build_mobile_headers(
        include_ip_spoof_headers=config.include_ip_spoof_headers,
    )

    auth = resolve_user_id(transport, config.base_url, base_headers)
    if not auth.ok:
        assert auth.error is not None
        raise OverchatError(auth.error)
    user_id = auth.user_id
    assert user_id is not None

    ids = new_conversation_ids()
    headers_json = request_mod.json_headers(base_headers)

    request_mod.generate_chat_title(
        transport,
        config.base_url,
        user_id=user_id,
        chat_uuid=ids.chat_uuid,
        prompt_text=prompt_text,
        system_prompt=config.system_prompt,
        model=config.model,
        headers=headers_json,
    )
    request_mod.create_chat_session(
        transport,
        config.base_url,
        user_id=user_id,
        chat_uuid=ids.chat_uuid,
        persona_id=config.persona_id,
        headers=headers_json,
    )

    payload = request_mod.build_responses_payload(
        prompt_text,
        model=config.model,
        persona_id=config.persona_id,
        chat_uuid=ids.chat_uuid,
        msg_id_1=ids.msg_id_1,
        msg_id_2=ids.msg_id_2,
    )

    try:
        response = request_mod.open_response_stream(
            transport,
            config.base_url,
            payload=payload,
            headers=request_mod.build_stream_headers(base_headers),
            timeout_seconds=config.timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        raise OverchatError(classify_transport_exception(exc, stage="generation")) from exc

    status = int(getattr(response, "status_code", 0))
    if not is_success_status(status):
        try:
            body = response.text or ""
        except Exception:  # noqa: BLE001
            body = ""
        raise OverchatError(classify_http_status(status, body=body, stage="generation"))

    for event in iter_events(response.iter_lines()):
        if isinstance(event, DeltaEvent):
            yield event.text
        # StreamErrorEvent is non-terminal in the source; streaming continues.
