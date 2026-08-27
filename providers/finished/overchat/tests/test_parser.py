"""SSE parsing parity (source L272-290).

Every test here pins one of the source's parsing rules, including the awkward
ones. README §24 requires the event matrix to be covered, and §17 forbids
"cleaning up" the odd cases — so the odd cases are asserted, not fixed.
"""

from __future__ import annotations

import json

from overchat.runtime.parser import (
    DELTA_EVENT,
    DONE_SENTINEL,
    ERROR_EVENT,
    DeltaEvent,
    StreamErrorEvent,
    accumulate_reply,
    iter_events,
    iter_text_deltas,
)


def d(text: str) -> bytes:
    return f'data: {{"event": "{DELTA_EVENT}", "data": {{"delta": {json.dumps(text)}}}}}'.encode()


def test_event_names_match_source_literals() -> None:
    assert DELTA_EVENT == "response.output_text.delta"  # L281
    assert ERROR_EVENT == "error"  # L287
    assert DONE_SENTINEL == "[DONE]"  # L277


def test_accumulates_deltas_in_order() -> None:
    """Source L286: `bot_full_reply += delta` — order is the reply."""
    assert accumulate_reply([d("Hel"), d("lo "), d("world")]) == "Hello world"


def test_done_sentinel_terminates_and_discards_later_frames() -> None:
    """Source L277-278 breaks out of the loop, so anything after [DONE] is never
    read — even a valid delta."""
    lines = [d("kept"), b"data: [DONE]", d("MUST NOT APPEAR")]
    assert accumulate_reply(lines) == "kept"


def test_falsy_lines_are_skipped() -> None:
    """Source L273: `if line:` — keepalive blank lines must not break parsing."""
    assert accumulate_reply([b"", d("a"), b"", None, d("b")]) == "ab"  # type: ignore[list-item]


def test_non_data_lines_are_ignored() -> None:
    """Source L275: only `data:`-prefixed lines are considered."""
    lines = [b"event: ping", b": comment", b"id: 42", d("x"), b"retry: 100"]
    assert accumulate_reply(lines) == "x"


def test_only_first_data_prefix_occurrence_is_stripped() -> None:
    """Source L276 uses `.replace("data: ", "", 1)` — count=1.

    A delta whose TEXT contains the literal "data: " must keep it. This is the
    kind of detail a rewrite would silently break.
    """
    payload = {"event": DELTA_EVENT, "data": {"delta": "see data: here"}}
    line = f"data: {json.dumps(payload)}".encode()
    assert accumulate_reply([line]) == "see data: here"


def test_falsy_delta_is_skipped() -> None:
    """Source L283: `if delta:` — empty deltas contribute nothing."""
    assert accumulate_reply([d(""), d("real"), d("")]) == "real"


def test_falsy_delta_emits_no_event_at_all() -> None:
    """Source L283 skips the frame ENTIRELY, it does not yield an empty delta.

    `accumulate_reply` alone cannot prove this: concatenating "" is invisible,
    so removing the `if delta:` guard still produces the same joined string.
    The difference is only observable at event/chunk granularity, which is what
    a streaming consumer actually sees. Verified by mutation: flipping
    `if delta:` to `if True:` survives the accumulate-only assertion but fails
    this one (README §33 - a test must prove the intended condition).
    """
    lines = [d("a"), d(""), d("b")]

    assert list(iter_events(lines)) == [DeltaEvent(text="a"), DeltaEvent(text="b")]
    # No zero-length chunk is ever surfaced to a streaming caller.
    assert list(iter_text_deltas(lines)) == ["a", "b"]
    assert "" not in list(iter_text_deltas(lines))


def test_missing_delta_key_defaults_to_empty_and_is_skipped() -> None:
    """Source L282 uses .get("delta", "")."""
    line = b'data: {"event": "response.output_text.delta", "data": {}}'
    assert accumulate_reply([line, d("ok")]) == "ok"


def test_unknown_event_types_are_ignored() -> None:
    """Source handles ONLY delta and error (classification UNKNOWN for others);
    other frames fall through both branches and are ignored."""
    lines = [
        b'data: {"event": "response.created", "data": {}}',
        b'data: {"event": "response.completed", "data": {}}',
        d("only this"),
    ]
    assert accumulate_reply(lines) == "only this"


def test_malformed_json_frames_are_silently_skipped() -> None:
    """Source L289-290: bare `except Exception: pass` around the whole frame."""
    lines = [b"data: {not json", d("a"), b"data: ]]]", d("b")]
    assert accumulate_reply(lines) == "ab"


def test_frame_missing_data_object_is_skipped_not_fatal() -> None:
    """`data["data"]` raises KeyError in the source; the bare except swallows it."""
    lines = [b'data: {"event": "response.output_text.delta"}', d("survived")]
    assert accumulate_reply(lines) == "survived"


def test_utf8_decoding_uses_replace_and_never_raises() -> None:
    """Source L274: decode(errors="replace") — invalid bytes must not crash."""
    bad = b'data: {"event": "response.output_text.delta", "data": {"delta": "\xff\xfe"}}'
    # Must not raise; the frame itself may or may not survive JSON parsing.
    assert isinstance(accumulate_reply([bad, d("after")]), str)
    assert "after" in accumulate_reply([bad, d("after")])


def test_arabic_and_emoji_deltas_survive_roundtrip() -> None:
    """The provider's default system prompt asks for Arabic, so multi-byte
    deltas are the normal case, not an edge case."""
    assert accumulate_reply([d("مرحبا "), d("بالعالم 🚀")]) == "مرحبا بالعالم 🚀"


def test_error_event_is_yielded_but_does_not_terminate_stream() -> None:
    """Source L287-288: the error is PRINTED and the loop CONTINUES.

    This asymmetry (error != terminal) is real provider behavior; README §24
    forbids normalizing it away.
    """
    lines = [
        d("before "),
        b'data: {"event": "error", "data": {"message": "boom"}}',
        d("after"),
    ]
    events = list(iter_events(lines))

    assert [type(e).__name__ for e in events] == [
        "DeltaEvent",
        "StreamErrorEvent",
        "DeltaEvent",
    ]
    assert isinstance(events[1], StreamErrorEvent)
    assert events[1].message == "boom"
    # Text after the error is still accumulated:
    assert accumulate_reply(lines) == "before after"


def test_error_event_with_missing_message_yields_none() -> None:
    """Source L288 uses .get("message"), so a missing key gives None."""
    events = list(iter_events([b'data: {"event": "error", "data": {}}']))
    assert len(events) == 1
    assert isinstance(events[0], StreamErrorEvent)
    assert events[0].message is None


def test_accepts_str_lines_as_well_as_bytes() -> None:
    """`requests.iter_lines()` yields bytes; tests and other transports may
    yield str. Both must parse identically."""
    as_bytes = accumulate_reply([d("a"), d("b")])
    as_str = accumulate_reply([d("a").decode(), d("b").decode()])
    assert as_bytes == as_str == "ab"


def test_iter_text_deltas_filters_out_error_events() -> None:
    lines = [d("a"), b'data: {"event": "error", "data": {"message": "m"}}', d("b")]
    assert list(iter_text_deltas(lines)) == ["a", "b"]


def test_parsing_is_lazy_so_deltas_stream_incrementally() -> None:
    """Streaming must be genuine: a delta has to be yielded BEFORE the rest of
    the stream is consumed, otherwise `streaming` would be a false claim."""
    consumed: list[str] = []

    def source_lines():
        for text in ["a", "b", "c"]:
            consumed.append(text)
            yield d(text)

    stream = iter_text_deltas(source_lines())
    first = next(stream)

    assert first == "a"
    # Only the first frame has been pulled from the generator so far.
    assert consumed == ["a"]


def test_delta_event_is_immutable_value_object() -> None:
    event = DeltaEvent(text="x")
    assert event.text == "x"
    try:
        event.text = "y"  # type: ignore[misc]
    except Exception as exc:
        assert type(exc).__name__ == "FrozenInstanceError"
    else:  # pragma: no cover
        raise AssertionError("DeltaEvent must be frozen")
