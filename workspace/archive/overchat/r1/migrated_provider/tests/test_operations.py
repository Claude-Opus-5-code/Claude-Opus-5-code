"""Text-generation flow parity (source L176-324).

The flow ORDER is contractual: headers -> auth -> title -> init -> responses,
where ONLY auth aborts. These tests assert the recorded call sequence and the
per-step timeout/header asymmetries, not internal implementation details.
"""

from __future__ import annotations

from overchat.config import OverchatConfig
from overchat.operations.text_generation import generate_text, stream_text
from overchat.runtime.errors import OverchatError

from .conftest import (
    FakeResponse,
    RecordingTransport,
    delta_frame,
    error_frame,
    make_transport,
    sse,
)

CONFIG = OverchatConfig()
DONE = [b"data: [DONE]"]


def _ok_transport(frames=None) -> RecordingTransport:
    frames = [delta_frame("Hello")] if frames is None else frames
    return make_transport(gen_lines=sse(frames) + DONE)


def _flow_handler(gen: FakeResponse) -> RecordingTransport:
    """Auth succeeds, generation scripted, side calls return bare 200."""

    def handler(method: str, url: str) -> FakeResponse:
        if url.endswith("/v1/auth/me"):
            return FakeResponse(200, payload={"id": "guest-1"})
        if url.endswith("/v2/chat/responses"):
            return gen
        return FakeResponse(200, payload={})

    return RecordingTransport(handler=handler)


# --------------------------------------------------------------------------
# Order and composition of the 4-step flow
# --------------------------------------------------------------------------


def test_exact_request_sequence() -> None:
    """Source L191-269: four HTTP calls, these methods, this order."""
    transport = _ok_transport()
    result = generate_text("hi", CONFIG, transport)

    assert result.ok
    assert transport.flow == [
        ("GET", "https://api.overchat.ai/v1/auth/me"),
        (
            "PATCH",
            f"https://api.overchat.ai/v1/chat/guest-1/{result.chat_uuid}/generateChatTitle",
        ),
        ("POST", "https://api.overchat.ai/v1/chat/guest-1"),
        ("POST", "https://api.overchat.ai/v2/chat/responses"),
    ]


def test_reply_is_accumulated_from_deltas() -> None:
    transport = _ok_transport([delta_frame("Hel"), delta_frame("lo!")])
    result = generate_text("hi", CONFIG, transport)
    assert result.ok
    assert result.text == "Hello!"


def test_user_id_from_auth_is_used_in_both_chat_urls() -> None:
    """The auth `id` must propagate into the title and init URLs (L214/L227)."""
    transport = make_transport(auth_payload={"id": "abc-999"}, gen_lines=DONE)
    generate_text("hi", CONFIG, transport)

    assert "/v1/chat/abc-999/" in transport.call_to("generateChatTitle").url
    # exact match: the init URL has no trailing segment, unlike the title URL
    init_urls = [c.url for c in transport.calls if c.url.endswith("/v1/chat/abc-999")]
    assert init_urls == ["https://api.overchat.ai/v1/chat/abc-999"]


def test_same_chat_uuid_is_used_across_title_init_and_payload() -> None:
    """One conversation: the uuid minted at L205 must appear in the title URL,
    the init body, and the generation payload's chatId."""
    transport = _ok_transport()
    result = generate_text("hi", CONFIG, transport)
    chat_uuid = result.chat_uuid

    assert chat_uuid
    assert chat_uuid in transport.call_to("generateChatTitle").url
    # the init call is the 3rd in the contractual sequence; select it by index
    # because its URL is a prefix of the title URL
    assert transport.calls[2].json_body["chatUuid"] == chat_uuid
    assert transport.call_to("/v2/chat/responses").json_body["chatId"] == chat_uuid


def test_message_ids_are_distinct_in_payload() -> None:
    """Source L206-207 mints two separate message ids."""
    transport = _ok_transport()
    generate_text("hi", CONFIG, transport)

    messages = transport.call_to("/v2/chat/responses").json_body["messages"]
    assert messages[0]["id"] != messages[1]["id"]


def test_device_identity_is_shared_across_all_four_calls() -> None:
    """Source mints headers ONCE per request (L191) and reuses them, so all four
    calls must present the SAME device uuid; a fresh uuid per call would look
    like four different devices upstream."""
    transport = _ok_transport()
    result = generate_text("hi", CONFIG, transport)

    uuids = {c.headers["x-device-uuid"] for c in transport.calls}
    assert len(uuids) == 1
    assert uuids == {result.device_uuid}


def test_spoofed_ip_is_shared_across_all_four_calls() -> None:
    """Source L106 generates ONE fake ip per request, used in all three headers."""
    transport = _ok_transport()
    result = generate_text("hi", CONFIG, transport)

    ips = {c.headers["X-Forwarded-For"] for c in transport.calls}
    assert ips == {result.spoofed_ip}


def test_identity_differs_between_separate_requests() -> None:
    """Source L191 re-mints per request."""
    r1 = generate_text("a", CONFIG, _ok_transport())
    r2 = generate_text("b", CONFIG, _ok_transport())
    assert r1.device_uuid != r2.device_uuid


def test_timeouts_per_step_match_source() -> None:
    """15s hardcoded on auth/title/init (L196, L221, L233); cfg.timeout_seconds
    only on the stream (L269)."""
    transport = _ok_transport()
    generate_text("hi", CONFIG, transport)

    assert [c.timeout for c in transport.calls] == [15, 15, 15, 120]


def test_configured_timeout_only_affects_the_stream_call() -> None:
    transport = _ok_transport()
    generate_text("hi", CONFIG.with_values(timeout_seconds=7), transport)
    assert [c.timeout for c in transport.calls] == [15, 15, 15, 7]


def test_stream_flag_set_only_on_generation_call() -> None:
    """Source passes stream=True only at L269."""
    transport = _ok_transport()
    generate_text("hi", CONFIG, transport)

    assert [c.stream for c in transport.calls] == [False, False, False, True]


def test_authorization_undefined_only_on_generation_call() -> None:
    """Source adds it at L263, after the earlier calls were already made."""
    transport = _ok_transport()
    generate_text("hi", CONFIG, transport)

    assert transport.call_to("/v2/chat/responses").headers["authorization"] == "undefined"
    assert "authorization" not in transport.call_to("/v1/auth/me").headers
    assert "authorization" not in transport.call_to("generateChatTitle").headers


def test_generation_call_uses_event_stream_accept_header() -> None:
    transport = _ok_transport()
    generate_text("hi", CONFIG, transport)

    assert transport.call_to("/v2/chat/responses").headers["Accept"] == "text/event-stream"
    # earlier calls keep the JSON Accept from the base headers (L111)
    assert (
        transport.call_to("/v1/auth/me").headers["Accept"] == "application/json, text/plain, */*"
    )


def test_content_type_absent_on_auth_but_present_on_later_calls() -> None:
    """Source adds Content-Type only from L210 onward; the GET has none."""
    transport = _ok_transport()
    generate_text("hi", CONFIG, transport)

    assert "Content-Type" not in transport.call_to("/v1/auth/me").headers
    assert transport.call_to("generateChatTitle").headers["Content-Type"] == "application/json"
    assert transport.call_to("/v2/chat/responses").headers["Content-Type"] == "application/json"


def test_model_and_persona_from_config_reach_the_payload() -> None:
    transport = _ok_transport()
    config = CONFIG.with_values(persona_id="gpt-5-2", model="gpt-5.2-2025-12-11")
    generate_text("hi", config, transport)

    body = transport.call_to("/v2/chat/responses").json_body
    assert body["model"] == "gpt-5.2-2025-12-11"
    assert body["personaId"] == "gpt-5-2"
    # the title call carries the model too (source L219)
    assert transport.call_to("generateChatTitle").json_body["personaModel"] == "gpt-5.2-2025-12-11"


def test_system_prompt_is_sent_on_title_call_only() -> None:
    """Source L217 sends systemPrompt to the TITLE endpoint, while the
    generation payload's system message is EMPTY (L245) - an odd but real split
    that README §17 forbids tidying."""
    transport = _ok_transport()
    generate_text("hi", CONFIG, transport)

    assert transport.call_to("generateChatTitle").json_body["systemPrompt"] == CONFIG.system_prompt
    messages = transport.call_to("/v2/chat/responses").json_body["messages"]
    assert messages[1]["role"] == "system"
    assert messages[1]["content"] == ""


def test_long_prompt_is_truncated_only_for_the_title_call() -> None:
    """End-to-end proof of the L216 vs L244 asymmetry."""
    prompt = "x" * 1000
    transport = _ok_transport()
    generate_text(prompt, CONFIG, transport)

    assert len(transport.call_to("generateChatTitle").json_body["userPrompt"]) == 300
    body = transport.call_to("/v2/chat/responses").json_body
    assert body["messages"][0]["content"] == prompt


# --------------------------------------------------------------------------
# Abort semantics
# --------------------------------------------------------------------------


def test_auth_failure_aborts_before_any_further_call() -> None:
    """Source L197-199 returns immediately: no title, no init, no generation."""
    transport = make_transport(auth_status=500, auth_text="down")
    result = generate_text("hi", CONFIG, transport)

    assert not result.ok
    assert result.error is not None
    assert result.error.metadata["stage"] == "auth"
    assert len(transport.calls) == 1
    assert transport.calls[0].url.endswith("/v1/auth/me")


def test_auth_failure_leaves_text_empty_and_reports_no_reply() -> None:
    """The source returned None here; the migrated result reports ok=False with
    an empty reply so legacy can reproduce that None."""
    result = generate_text("hi", CONFIG, make_transport(auth_status=403))
    assert result.text == ""
    assert not result.ok


def test_title_failure_does_not_abort_generation() -> None:
    """Source L222-223 swallows: generation must still happen and succeed."""
    transport = _flow_handler(FakeResponse(200, lines=sse([delta_frame("still works")]) + DONE))
    transport.raise_on = {"generateChatTitle": RuntimeError("title down")}

    result = generate_text("hi", CONFIG, transport)

    assert result.ok
    assert result.text == "still works"
    assert len(transport.calls) == 4  # all four attempted


def test_chat_init_failure_does_not_abort_generation() -> None:
    """Source L234-235 swallows likewise."""
    transport = _flow_handler(FakeResponse(200, lines=sse([delta_frame("ok")]) + DONE))
    transport.raise_on = {"/v1/chat/guest-1": RuntimeError("init down")}

    result = generate_text("hi", CONFIG, transport)

    assert result.ok
    assert result.text == "ok"


def test_generation_non_2xx_is_normalized_with_250_char_body() -> None:
    """Source L318-320."""
    transport = make_transport(gen_status=500, gen_text="E" * 400)
    result = generate_text("hi", CONFIG, transport)

    assert not result.ok
    assert result.error is not None
    assert result.error.provider_code == "500"
    assert result.error.metadata["stage"] == "generation"
    assert len(result.error.metadata["raw_body_truncated"]) == 250


def test_generation_201_is_accepted() -> None:
    """Source L271 accepts 200 OR 201 for the stream too."""
    transport = make_transport(gen_status=201, gen_lines=sse([delta_frame("created")]) + DONE)
    result = generate_text("hi", CONFIG, transport)

    assert result.ok
    assert result.text == "created"


def test_stream_transport_exception_is_normalized() -> None:
    transport = RecordingTransport(
        handler=lambda m, u: FakeResponse(200, payload={"id": "guest-1"}),
        raise_on={"/v2/chat/responses": ConnectionError("reset")},
    )
    result = generate_text("hi", CONFIG, transport)

    assert not result.ok
    assert result.error is not None
    assert result.error.provider_code == "ConnectionError"


def test_mid_stream_exception_is_normalized_not_raised() -> None:
    """Source's outer bare except (L322) also covers failures during iteration."""
    transport = _flow_handler(FakeResponse(200, raise_on_iter=ConnectionError("dropped")))
    result = generate_text("hi", CONFIG, transport)

    assert not result.ok
    assert result.error is not None
    assert result.error.category == "provider_unavailable"


# --------------------------------------------------------------------------
# In-stream error event (non-terminal)
# --------------------------------------------------------------------------


def test_stream_error_event_is_collected_but_generation_still_succeeds() -> None:
    """Source L287-288: reported, NOT terminal, NOT a failure."""
    transport = _ok_transport(
        [delta_frame("before "), error_frame("upstream hiccup"), delta_frame("after")]
    )
    result = generate_text("hi", CONFIG, transport)

    assert result.ok
    assert result.error is None
    assert result.text == "before after"
    assert result.stream_errors == ["upstream hiccup"]


def test_callbacks_receive_deltas_and_stream_errors_in_order() -> None:
    """`on_delta` reproduces the source's incremental stdout write (L284-285)."""
    seen: list[tuple[str, object]] = []
    transport = _ok_transport([delta_frame("a"), error_frame("e"), delta_frame("b")])

    generate_text(
        "hi",
        CONFIG,
        transport,
        on_delta=lambda t: seen.append(("delta", t)),
        on_stream_error=lambda m: seen.append(("error", m)),
    )

    assert seen == [("delta", "a"), ("error", "e"), ("delta", "b")]


def test_empty_stream_yields_empty_reply_without_error() -> None:
    """A [DONE]-only stream is a successful empty reply, as in the source."""
    result = generate_text("hi", CONFIG, make_transport(gen_lines=DONE))
    assert result.ok
    assert result.text == ""


def test_ip_spoof_headers_present_by_default_and_removable_via_config() -> None:
    """Quarantined behavior, observed end-to-end on every call. Default ON
    matches the source; the switch is the migration-added boundary."""
    transport = _ok_transport()
    generate_text("hi", CONFIG, transport)
    assert all("X-Forwarded-For" in c.headers for c in transport.calls)

    off = CONFIG.with_values(include_ip_spoof_headers=False)
    transport2 = _ok_transport()
    result = generate_text("hi", off, transport2)

    assert result.ok  # everything still works without them
    for call in transport2.calls:
        assert "X-Forwarded-For" not in call.headers
        assert "X-Real-IP" not in call.headers
        assert "Client-IP" not in call.headers


# --------------------------------------------------------------------------
# stream_text
# --------------------------------------------------------------------------


def test_stream_text_yields_deltas_in_order() -> None:
    transport = _ok_transport([delta_frame("x"), delta_frame("y"), delta_frame("z")])
    assert list(stream_text("hi", CONFIG, transport)) == ["x", "y", "z"]


def test_stream_text_is_incremental_not_buffered() -> None:
    """Genuine streaming: the first delta must be observable before the rest of
    the stream has been consumed."""
    pulled: list[str] = []

    def line_source():
        for text in ["1", "2", "3"]:
            pulled.append(text)
            yield (
                'data: {"event": "response.output_text.delta", '
                f'"data": {{"delta": "{text}"}}}}'
            ).encode()

    transport = _flow_handler(FakeResponse(200, lines=line_source()))
    stream = stream_text("hi", CONFIG, transport)
    first = next(stream)

    assert first == "1"
    assert pulled == ["1"]  # remaining frames not yet pulled


def test_stream_text_skips_non_terminal_error_events() -> None:
    transport = _ok_transport([delta_frame("a"), error_frame("bad"), delta_frame("b")])
    assert list(stream_text("hi", CONFIG, transport)) == ["a", "b"]


def test_stream_text_raises_normalized_error_on_auth_failure() -> None:
    transport = make_transport(auth_status=403, auth_text="denied")
    try:
        list(stream_text("hi", CONFIG, transport))
    except OverchatError as exc:
        assert exc.error.category == "invalid_credential"
        assert exc.error.metadata["stage"] == "auth"
    else:  # pragma: no cover
        raise AssertionError("expected OverchatError")


def test_stream_text_raises_normalized_error_on_bad_generation_status() -> None:
    transport = make_transport(gen_status=502, gen_text="Bad Gateway")
    try:
        list(stream_text("hi", CONFIG, transport))
    except OverchatError as exc:
        assert exc.error.category == "provider_unavailable"
        assert exc.error.retryable is True
    else:  # pragma: no cover
        raise AssertionError("expected OverchatError")


def test_stream_text_performs_the_same_four_step_flow() -> None:
    transport = _ok_transport()
    list(stream_text("hi", CONFIG, transport))
    assert [c.method for c in transport.calls] == ["GET", "PATCH", "POST", "POST"]
