"""Guest auth / session parity (source L194-207).

AUTH MODEL: no credential is ever sent. Upstream auto-provisions a guest from
the device headers and returns its `id`. Tests below pin that model, including
the fact that 201 is accepted alongside 200.
"""

from __future__ import annotations

from overchat.runtime.session import (
    AUTH_PATH,
    AUTH_TIMEOUT_SECONDS,
    new_conversation_ids,
    resolve_user_id,
)

from .conftest import FakeResponse, RecordingTransport

BASE = "https://api.overchat.ai"


def _transport(response: FakeResponse) -> RecordingTransport:
    return RecordingTransport(handler=lambda method, url: response)


def test_auth_endpoint_and_timeout_match_source() -> None:
    """Source L195-196: `/v1/auth/me` with a HARDCODED timeout of 15.

    The 15 is deliberate and asserted: the source does NOT use cfg.timeout_seconds
    here (that applies only to the stream call).
    """
    assert AUTH_PATH == "/v1/auth/me"
    assert AUTH_TIMEOUT_SECONDS == 15

    transport = _transport(FakeResponse(200, payload={"id": "guest-1"}))
    resolve_user_id(transport, BASE, {"x-device-uuid": "abc"})

    call = transport.calls[0]
    assert call.method == "GET"
    assert call.url == f"{BASE}/v1/auth/me"
    assert call.timeout == 15


def test_device_headers_are_forwarded_unchanged() -> None:
    """The guest identity is derived from these headers, so they must arrive."""
    headers = {"x-device-uuid": "abc123", "User-Agent": "okhttp/4.12.0"}
    transport = _transport(FakeResponse(200, payload={"id": "g"}))

    resolve_user_id(transport, BASE, headers)

    assert transport.calls[0].headers == headers


def test_no_credential_header_is_sent() -> None:
    """Source sends no Authorization/api-key/cookie on the auth call.

    (The literal `authorization: "undefined"` appears only on the STREAM call,
    L263 — never here.)
    """
    transport = _transport(FakeResponse(200, payload={"id": "g"}))
    resolve_user_id(transport, BASE, {"x-device-uuid": "abc"})

    sent = {k.lower() for k in transport.calls[0].headers}
    assert "authorization" not in sent
    assert "cookie" not in sent
    assert not any("api" in k and "key" in k for k in sent)


def test_status_200_is_success() -> None:
    result = resolve_user_id(_transport(FakeResponse(200, payload={"id": "u200"})), BASE, {})
    assert result.ok
    assert result.user_id == "u200"
    assert result.error is None


def test_status_201_is_also_success() -> None:
    """Source L197: `if res_auth.status_code not in [200, 201]`.

    201 acceptance is easy to lose in a rewrite; a brand-new guest may well be
    reported as Created.
    """
    result = resolve_user_id(_transport(FakeResponse(201, payload={"id": "u201"})), BASE, {})
    assert result.ok
    assert result.user_id == "u201"


def test_status_204_is_failure_even_though_2xx() -> None:
    """The source accepts ONLY 200/201, not all 2xx."""
    result = resolve_user_id(_transport(FakeResponse(204, payload={"id": "x"})), BASE, {})
    assert not result.ok
    assert result.error is not None
    assert result.error.provider_code == "204"


def test_failure_carries_truncated_body_at_source_limit_150() -> None:
    """Source L198 prints `res_auth.text[:150]`; the truncation is preserved as
    error evidence."""
    body = "E" * 500
    result = resolve_user_id(_transport(FakeResponse(500, text=body)), BASE, {})

    assert not result.ok
    assert result.error is not None
    assert len(result.error.metadata["raw_body_truncated"]) == 150
    assert result.error.metadata["stage"] == "auth"


def test_transport_exception_is_normalized_not_raised() -> None:
    """Source L201-203 catches bare Exception and returns None. The migrated
    layer must not leak the raw exception to the caller (README §19)."""
    transport = RecordingTransport(raise_on={"/v1/auth/me": ConnectionError("dns fail")})

    result = resolve_user_id(transport, BASE, {})

    assert not result.ok
    assert result.error is not None
    assert result.error.provider_code == "ConnectionError"
    assert result.error.retryable is True


def test_exception_message_is_not_leaked_into_safe_message() -> None:
    """Security: exception text can contain hosts/URLs, so it must stay out of
    the message the Core may surface."""
    secret = "https://internal.host/secret-path?token=abc"
    transport = RecordingTransport(raise_on={"/v1/auth/me": ConnectionError(secret)})

    result = resolve_user_id(transport, BASE, {})

    assert result.error is not None
    assert secret not in result.error.safe_message
    assert "token" not in result.error.safe_message


def test_unparsable_json_body_is_a_normalized_failure() -> None:
    """Source L200 calls .json() inside the try; a non-JSON 200 returns None."""
    result = resolve_user_id(
        _transport(FakeResponse(200, raise_on_json=True, text="<html/>")), BASE, {}
    )
    assert not result.ok
    assert result.error is not None


def test_missing_id_field_is_a_failure_not_a_none_user_id() -> None:
    """Source uses .get("id"), so a body without `id` yields user_id=None and
    the subsequent URLs would contain the string 'None'. The migrated layer
    turns that into an explicit normalized error instead of building a
    malformed URL — an additive safety improvement that cannot change any
    previously-working request."""
    result = resolve_user_id(_transport(FakeResponse(200, payload={"isGuest": True})), BASE, {})

    assert not result.ok
    assert result.error is not None
    assert result.error.category == "bad_request"
    assert "user id" in result.error.safe_message.lower()


def test_non_dict_payload_is_a_failure() -> None:
    result = resolve_user_id(_transport(FakeResponse(200, payload=["not", "a", "dict"])), BASE, {})
    assert not result.ok


def test_user_id_is_coerced_to_string() -> None:
    """Upstream could return a numeric id; it lands in a URL path, so it must be
    a string."""
    result = resolve_user_id(_transport(FakeResponse(200, payload={"id": 12345})), BASE, {})
    assert result.ok
    assert result.user_id == "12345"


def test_conversation_ids_are_three_distinct_uuid4_strings() -> None:
    """Source L205-207: three INDEPENDENT uuid4 values."""
    import uuid

    ids = new_conversation_ids()
    values = [ids.chat_uuid, ids.msg_id_1, ids.msg_id_2]

    assert len(set(values)) == 3
    for value in values:
        assert uuid.UUID(value).version == 4


def test_conversation_ids_are_fresh_per_call() -> None:
    first, second = new_conversation_ids(), new_conversation_ids()
    assert first.chat_uuid != second.chat_uuid
