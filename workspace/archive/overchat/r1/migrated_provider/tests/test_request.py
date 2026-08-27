"""Request construction parity (source L209-269).

URLs, payload keys/values, header sets and timeouts are asserted against literal
values transcribed from the source. README §18 forbids changing any of them.
"""

from __future__ import annotations

import json

from overchat.runtime.request import (
    SIDE_CALL_TIMEOUT_SECONDS,
    TITLE_PROMPT_LIMIT,
    build_chat_create_payload,
    build_responses_payload,
    build_stream_headers,
    build_title_payload,
    chat_create_url,
    create_chat_session,
    generate_chat_title,
    json_headers,
    responses_url,
    title_url,
)

from .conftest import RecordingTransport

BASE = "https://api.overchat.ai"


# --------------------------------------------------------------------------
# URLs (source L214, L227, L241)
# --------------------------------------------------------------------------


def test_title_url_shape() -> None:
    assert (
        title_url(BASE, "uid-1", "chat-1")
        == "https://api.overchat.ai/v1/chat/uid-1/chat-1/generateChatTitle"
    )


def test_chat_create_url_shape() -> None:
    assert chat_create_url(BASE, "uid-1") == "https://api.overchat.ai/v1/chat/uid-1"


def test_responses_url_is_v2() -> None:
    """The generation endpoint is v2 while the others are v1 — a real asymmetry."""
    assert responses_url(BASE) == "https://api.overchat.ai/v2/chat/responses"


# --------------------------------------------------------------------------
# Payloads
# --------------------------------------------------------------------------


def test_title_payload_exact_keys_and_values() -> None:
    """Source L215-220."""
    payload = build_title_payload("prompt text", "sys prompt", "google/gemini-3.5-flash")
    assert payload == {
        "userPrompt": "prompt text",
        "systemPrompt": "sys prompt",
        "personaType": "text",
        "personaModel": "google/gemini-3.5-flash",
    }


def test_title_payload_truncates_prompt_to_300_chars() -> None:
    """Source L216: `prompt_text[:300]` — only the title call truncates."""
    assert TITLE_PROMPT_LIMIT == 300
    payload = build_title_payload("x" * 1000, "s", "m")
    assert len(payload["userPrompt"]) == 300


def test_title_payload_does_not_truncate_short_prompts() -> None:
    assert build_title_payload("short", "s", "m")["userPrompt"] == "short"


def test_chat_create_payload_exact() -> None:
    """Source L228-232, including firstBotMessageHidden=True."""
    assert build_chat_create_payload("gemini-3-5-flash", "chat-1") == {
        "personaId": "gemini-3-5-flash",
        "firstBotMessageHidden": True,
        "chatUuid": "chat-1",
    }


def test_responses_payload_exact() -> None:
    """Source L242-256, every key and value."""
    payload = build_responses_payload(
        "hello",
        model="google/gemini-3.5-flash",
        persona_id="gemini-3-5-flash",
        chat_uuid="chat-1",
        msg_id_1="m1",
        msg_id_2="m2",
    )
    assert payload == {
        "messages": [
            {"role": "user", "content": "hello", "id": "m1"},
            {"id": "m2", "role": "system", "content": ""},
        ],
        "model": "google/gemini-3.5-flash",
        "personaId": "gemini-3-5-flash",
        "chatId": "chat-1",
        "frequency_penalty": 0,
        "max_tokens": 4000,
        "presence_penalty": 0,
        "stream": True,
        "temperature": 0.5,
        "top_p": 0.95,
    }


def test_responses_payload_keeps_empty_system_message_after_user_message() -> None:
    """Source L244-245: an odd but REAL shape — user first, then a system
    message with empty content. README §17 forbids 'tidying' it away."""
    payload = build_responses_payload(
        "hi", model="m", persona_id="p", chat_uuid="c", msg_id_1="1", msg_id_2="2"
    )
    messages = payload["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "system"
    assert messages[1]["content"] == ""


def test_responses_payload_never_truncates_the_prompt() -> None:
    """The source's headline feature is 'unlimited' input (L12): the generation
    payload must carry the full prompt, unlike the title call."""
    long_prompt = "ب" * 50_000
    payload = build_responses_payload(
        long_prompt, model="m", persona_id="p", chat_uuid="c", msg_id_1="1", msg_id_2="2"
    )
    assert payload["messages"][0]["content"] == long_prompt


def test_responses_payload_always_requests_streaming() -> None:
    """Source L253 hardcodes stream=True — this underpins the `streaming` claim."""
    payload = build_responses_payload(
        "x", model="m", persona_id="p", chat_uuid="c", msg_id_1="1", msg_id_2="2"
    )
    assert payload["stream"] is True


# --------------------------------------------------------------------------
# Headers
# --------------------------------------------------------------------------


def test_json_headers_adds_content_type_without_mutating_base() -> None:
    """Source L209-210 uses `.copy()`; mutating the base would leak the JSON
    content-type into the SSE request."""
    base = {"User-Agent": "okhttp/4.12.0"}
    result = json_headers(base)
    assert result["Content-Type"] == "application/json"
    assert "Content-Type" not in base


def test_stream_headers_exact_additions() -> None:
    """Source L258-263."""
    base = {"Accept": "application/json, text/plain, */*", "User-Agent": "okhttp/4.12.0"}
    headers = build_stream_headers(base)

    assert headers["Accept"] == "text/event-stream"  # overwritten, L259
    assert headers["Content-Type"] == "application/json"  # L260
    assert headers["cache-control"] == "no-cache"  # L261
    assert headers["x-requested-with"] == "XMLHttpRequest"  # L262
    assert headers["authorization"] == "undefined"  # L263
    assert headers["User-Agent"] == "okhttp/4.12.0"  # base preserved


def test_authorization_header_is_the_literal_string_undefined() -> None:
    """Source L263. This is a JavaScript `undefined` that leaked into the client
    as a STRING. It is part of the request the working provider sends, so it is
    preserved verbatim (README §16/§18) — not omitted, not None, not empty.
    """
    headers = build_stream_headers({})
    assert headers["authorization"] == "undefined"
    assert isinstance(headers["authorization"], str)


def test_stream_headers_do_not_mutate_base() -> None:
    base = {"Accept": "application/json, text/plain, */*"}
    build_stream_headers(base)
    assert base["Accept"] == "application/json, text/plain, */*"
    assert "authorization" not in base


# --------------------------------------------------------------------------
# Fire-and-forget calls (source L212-235)
# --------------------------------------------------------------------------


def test_title_call_method_url_body_and_timeout() -> None:
    transport = RecordingTransport()
    generate_chat_title(
        transport,
        BASE,
        user_id="uid",
        chat_uuid="cid",
        prompt_text="p",
        system_prompt="s",
        model="m",
        headers={"Content-Type": "application/json"},
    )

    call = transport.calls[0]
    assert call.method == "PATCH"  # L221 uses requests.patch
    assert call.url == f"{BASE}/v1/chat/uid/cid/generateChatTitle"
    assert call.timeout == SIDE_CALL_TIMEOUT_SECONDS == 15
    assert call.json_body["personaModel"] == "m"
    # body is a JSON STRING (source uses data=json.dumps(...), not json=...)
    assert isinstance(call.body, str)
    assert json.loads(call.body)["personaType"] == "text"


def test_chat_create_call_method_url_body_and_timeout() -> None:
    transport = RecordingTransport()
    create_chat_session(
        transport,
        BASE,
        user_id="uid",
        chat_uuid="cid",
        persona_id="gemini-3-5-flash",
        headers={},
    )

    call = transport.calls[0]
    assert call.method == "POST"
    assert call.url == f"{BASE}/v1/chat/uid"
    assert call.timeout == 15
    assert call.json_body == {
        "personaId": "gemini-3-5-flash",
        "firstBotMessageHidden": True,
        "chatUuid": "cid",
    }


def test_title_failure_is_swallowed() -> None:
    """Source L222-223: `except Exception: pass`. A failing title call must NOT
    propagate, because generation continues regardless."""
    transport = RecordingTransport(raise_on={"generateChatTitle": RuntimeError("network down")})

    generate_chat_title(
        transport,
        BASE,
        user_id="uid",
        chat_uuid="cid",
        prompt_text="p",
        system_prompt="s",
        model="m",
        headers={},
    )  # must not raise

    assert len(transport.calls) == 1  # it was attempted


def test_chat_create_failure_is_swallowed() -> None:
    """Source L234-235: same swallow."""
    transport = RecordingTransport(raise_on={"/v1/chat/uid": RuntimeError("boom")})

    create_chat_session(
        transport, BASE, user_id="uid", chat_uuid="cid", persona_id="p", headers={}
    )  # must not raise

    assert len(transport.calls) == 1


def test_side_calls_ignore_response_status() -> None:
    """Source never inspects these responses: a 500 must be a no-op, not an error."""
    from .conftest import FakeResponse

    transport = RecordingTransport(handler=lambda m, u: FakeResponse(status_code=500, text="err"))

    generate_chat_title(
        transport,
        BASE,
        user_id="u",
        chat_uuid="c",
        prompt_text="p",
        system_prompt="s",
        model="m",
        headers={},
    )
    create_chat_session(transport, BASE, user_id="u", chat_uuid="c", persona_id="p", headers={})

    assert len(transport.calls) == 2  # both completed without raising
