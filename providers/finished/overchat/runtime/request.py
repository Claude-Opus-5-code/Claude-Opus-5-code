"""Upstream request construction and execution.

Migrated from source L209-269. Every URL, method, header, payload key and
timeout below is byte-for-byte what the source sends (README §18).
"""

from __future__ import annotations

import json
from typing import Any

from .session import Transport

#: Fixed timeouts used by the source for the two fire-and-forget calls
#: (L221, L233) - same value as the auth call, and again NOT cfg.timeout.
SIDE_CALL_TIMEOUT_SECONDS = 15

#: Prompt slice sent as the title seed, source L216.
TITLE_PROMPT_LIMIT = 300


def json_headers(base_headers: dict[str, str]) -> dict[str, str]:
    """Source L209-210: copy base headers and add JSON content type."""
    headers = base_headers.copy()
    headers["Content-Type"] = "application/json"
    return headers


def build_stream_headers(base_headers: dict[str, str]) -> dict[str, str]:
    """Source L258-263, exactly.

    Includes the literal ``authorization: "undefined"`` header. That is a
    JavaScript `undefined` that leaked into the original client as a string. It
    is preserved verbatim: it is part of the request the working provider
    actually sends, and README §16/§18 forbid "fixing" it.
    """
    headers = base_headers.copy()
    headers["Accept"] = "text/event-stream"
    headers["Content-Type"] = "application/json"
    headers["cache-control"] = "no-cache"
    headers["x-requested-with"] = "XMLHttpRequest"
    headers["authorization"] = "undefined"
    return headers


def title_url(base_url: str, user_id: str, chat_uuid: str) -> str:
    """Source L214."""
    return f"{base_url}/v1/chat/{user_id}/{chat_uuid}/generateChatTitle"


def chat_create_url(base_url: str, user_id: str) -> str:
    """Source L227."""
    return f"{base_url}/v1/chat/{user_id}"


def responses_url(base_url: str) -> str:
    """Source L241."""
    return f"{base_url}/v2/chat/responses"


def build_title_payload(prompt_text: str, system_prompt: str, model: str) -> dict[str, Any]:
    """Source L215-220, exact keys and order."""
    return {
        "userPrompt": prompt_text[:TITLE_PROMPT_LIMIT],
        "systemPrompt": system_prompt,
        "personaType": "text",
        "personaModel": model,
    }


def build_chat_create_payload(persona_id: str, chat_uuid: str) -> dict[str, Any]:
    """Source L228-232, exact keys."""
    return {
        "personaId": persona_id,
        "firstBotMessageHidden": True,
        "chatUuid": chat_uuid,
    }


def build_responses_payload(
    prompt_text: str,
    *,
    model: str,
    persona_id: str,
    chat_uuid: str,
    msg_id_1: str,
    msg_id_2: str,
) -> dict[str, Any]:
    """Source L242-256, exact.

    Preserved oddities:
      * two messages, the second being a SYSTEM message with empty content,
        placed AFTER the user message, with its `id` key first (source L245);
      * fixed sampling values; `stream` always True.
    """
    return {
        "messages": [
            {"role": "user", "content": prompt_text, "id": msg_id_1},
            {"id": msg_id_2, "role": "system", "content": ""},
        ],
        "model": model,
        "personaId": persona_id,
        "chatId": chat_uuid,
        "frequency_penalty": 0,
        "max_tokens": 4000,
        "presence_penalty": 0,
        "stream": True,
        "temperature": 0.5,
        "top_p": 0.95,
    }


def generate_chat_title(
    transport: Transport,
    base_url: str,
    *,
    user_id: str,
    chat_uuid: str,
    prompt_text: str,
    system_prompt: str,
    model: str,
    headers: dict[str, str],
) -> None:
    """Fire-and-forget title generation.

    Source L212-223: a PATCH whose response status is never inspected and whose
    exceptions are swallowed by `except Exception: pass`. Both properties are
    preserved deliberately - the call is best-effort and must never abort the
    request flow.
    """
    try:
        transport.patch(
            title_url(base_url, user_id, chat_uuid),
            data=json.dumps(build_title_payload(prompt_text, system_prompt, model)),
            headers=headers,
            timeout=SIDE_CALL_TIMEOUT_SECONDS,
        )
    except Exception:  # noqa: BLE001,S110 - source L222-223 swallows silently
        pass


def create_chat_session(
    transport: Transport,
    base_url: str,
    *,
    user_id: str,
    chat_uuid: str,
    persona_id: str,
    headers: dict[str, str],
) -> None:
    """Fire-and-forget chat session init.

    Source L225-235: POST, status ignored, exceptions swallowed. Preserved.
    """
    try:
        transport.post(
            chat_create_url(base_url, user_id),
            data=json.dumps(build_chat_create_payload(persona_id, chat_uuid)),
            headers=headers,
            timeout=SIDE_CALL_TIMEOUT_SECONDS,
        )
    except Exception:  # noqa: BLE001,S110 - source L234-235 swallows silently
        pass


def open_response_stream(
    transport: Transport,
    base_url: str,
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int,
) -> Any:
    """Open the SSE stream.

    Source L269, exact: POST to /v2/chat/responses with
    `data=json.dumps(payload)`, `stream=True`, and the CONFIGURABLE timeout
    (the only call that uses cfg.timeout_seconds).
    """
    return transport.post(
        responses_url(base_url),
        data=json.dumps(payload),
        headers=headers,
        timeout=timeout_seconds,
        stream=True,
    )
