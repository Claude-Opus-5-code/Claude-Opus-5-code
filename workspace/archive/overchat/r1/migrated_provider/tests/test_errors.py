"""Error normalization (SANITIZED, adapter-added).

The source performs NO normalization — it prints and returns None. V3 §14
requires normalized categories, so this layer exists at the boundary. These
tests prove the mapping is honest: statuses the source actually distinguishes
keep their meaning, the body truncations are preserved as evidence, and nothing
leaks a raw provider detail into `safe_message`.
"""

from __future__ import annotations

import pytest

from overchat.runtime.errors import (
    AUTH_BODY_TRUNCATION,
    GENERATION_BODY_TRUNCATION,
    SUCCESS_STATUSES,
    OverchatError,
    ProviderError,
    classify_http_status,
    classify_transport_exception,
    is_success_status,
    unsupported_capability,
)


def test_success_statuses_are_exactly_200_and_201() -> None:
    """Source L197 and L271 both use `[200, 201]`."""
    assert SUCCESS_STATUSES == (200, 201)
    assert is_success_status(200)
    assert is_success_status(201)


@pytest.mark.parametrize("status", [199, 202, 204, 301, 400, 401, 403, 429, 500, 502])
def test_other_statuses_are_not_success(status: int) -> None:
    """Notably 202 and 204 are NOT accepted, matching the source's literal list."""
    assert not is_success_status(status)


@pytest.mark.parametrize(
    ("status", "category", "retryable"),
    [
        (401, "auth_expired", False),
        (403, "invalid_credential", False),
        (429, "rate_limited", True),
        (402, "quota_exceeded", False),
        (404, "model_unavailable", False),
        (400, "bad_request", False),
        (408, "timeout", True),
        (502, "provider_unavailable", True),
        (503, "provider_unavailable", True),
        (504, "provider_unavailable", True),
        (500, "retryable_server_error", True),
        (418, "non_retryable_error", False),
    ],
)
def test_status_maps_to_v3_category_with_correct_retryability(
    status: int, category: str, retryable: bool
) -> None:
    """Categories come from V3 §14's fixed vocabulary; retryability must be
    consistent with the category or the Core's retry policy would misfire."""
    error = classify_http_status(status)
    assert error.category == category
    assert error.retryable is retryable
    assert error.provider_code == str(status)


def test_502_maps_to_provider_unavailable_matching_observed_live_behavior() -> None:
    """502 is the status actually observed live against api.overchat.ai, so this
    row is backed by real evidence rather than assumption."""
    error = classify_http_status(502, body="Bad Gateway", stage="generation")
    assert error.category == "provider_unavailable"
    assert error.retryable is True


def test_auth_stage_truncates_body_at_150() -> None:
    """Source L198: `res_auth.text[:150]`."""
    assert AUTH_BODY_TRUNCATION == 150
    error = classify_http_status(500, body="x" * 400, stage="auth")
    assert len(error.metadata["raw_body_truncated"]) == 150


def test_generation_stage_truncates_body_at_250() -> None:
    """Source L319: `res_msg.text[:250]` — a DIFFERENT limit from auth.

    The asymmetry is the source's; preserving it keeps error evidence identical
    to what the original would have shown.
    """
    assert GENERATION_BODY_TRUNCATION == 250
    error = classify_http_status(500, body="x" * 400, stage="generation")
    assert len(error.metadata["raw_body_truncated"]) == 250


def test_short_bodies_are_not_padded_and_stage_is_recorded() -> None:
    error = classify_http_status(400, body="nope", stage="generation")
    assert error.metadata["raw_body_truncated"] == "nope"
    assert error.metadata["stage"] == "generation"


def test_empty_body_is_handled() -> None:
    assert classify_http_status(500).metadata["raw_body_truncated"] == ""


def test_safe_message_contains_no_raw_body_content() -> None:
    """Security: the upstream body may echo request data, so it belongs only in
    metadata, never in the message the Core may surface or log."""
    error = classify_http_status(400, body="secret-token-abc123", stage="generation")
    assert "secret-token-abc123" not in error.safe_message


def test_timeout_exception_maps_to_timeout_category() -> None:
    class ReadTimeout(Exception):
        pass

    error = classify_transport_exception(ReadTimeout("slow"))
    assert error.category == "timeout"
    assert error.retryable is True
    assert error.provider_code == "ReadTimeout"


def test_generic_exception_maps_to_provider_unavailable() -> None:
    """Source's bare excepts (L201, L322) mean 'could not reach provider'."""
    error = classify_transport_exception(ConnectionError("refused"))
    assert error.category == "provider_unavailable"
    assert error.retryable is True


def test_transport_exception_message_is_never_copied() -> None:
    error = classify_transport_exception(ConnectionError("https://host/p?token=xyz"))
    assert "token=xyz" not in error.safe_message
    assert "https://" not in error.safe_message


def test_unsupported_capability_error_shape() -> None:
    """V3 §5: undeclared operations must be rejected explicitly."""
    error = unsupported_capability("image_generation")
    assert error.category == "unsupported_capability"
    assert error.retryable is False
    assert error.metadata["capability"] == "image_generation"
    assert "image_generation" in error.safe_message


def test_to_dict_exposes_v3_fields_only() -> None:
    """The serialized form must not carry provider-internal metadata to the Core."""
    payload = classify_http_status(429, body="slow down", stage="generation").to_dict()
    assert set(payload) == {
        "category",
        "retryable",
        "retry_after_ms",
        "provider_code",
        "safe_message",
    }
    assert "slow down" not in str(payload)
    assert "metadata" not in payload


def test_retry_after_ms_is_none_unless_supplied() -> None:
    """README §16: the source never reads a Retry-After header, so this stays
    None rather than being invented."""
    assert classify_http_status(429).retry_after_ms is None
    assert classify_http_status(429, retry_after_ms=1500).retry_after_ms == 1500


def test_provider_error_is_frozen() -> None:
    import dataclasses

    error = classify_http_status(500)
    with pytest.raises(dataclasses.FrozenInstanceError):
        error.category = "other"  # type: ignore[misc]


def test_overchat_error_wraps_normalized_error_and_uses_safe_message() -> None:
    """The only exception type crossing the adapter boundary must carry the
    normalized error and reveal nothing else."""
    normalized = ProviderError(
        category="rate_limited", retryable=True, safe_message="slow down please"
    )
    exc = OverchatError(normalized)

    assert exc.error is normalized
    assert str(exc) == "slow down please"
    assert isinstance(exc, Exception)
