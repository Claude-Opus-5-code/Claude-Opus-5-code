"""Adapter boundary tests (V3 §8.1 / README §19-§20).

The adapter must expose ONLY the normalized contract: declared capabilities that
match source evidence, normalized errors, and explicit rejection of everything
the source does not implement. Nothing provider-specific (HTTP status codes, SSE
frames, raw exceptions) may cross this line.
"""

from __future__ import annotations

import pytest

from overchat.config import OverchatConfig
from overchat.provider import (
    DECLARED_CAPABILITIES,
    DECLARED_OPERATIONS,
    UNSUPPORTED_CAPABILITIES,
    GenerateRequest,
    OverchatProvider,
)
from overchat.runtime.errors import OverchatError, ProviderError

from .conftest import delta_frame, error_frame, make_transport, sse

DONE = [b"data: [DONE]"]


def _provider(transport=None, config=None) -> OverchatProvider:
    transport = transport or make_transport(gen_lines=sse([delta_frame("hi")]) + DONE)
    return OverchatProvider(transport, config)


# --------------------------------------------------------------------------
# Declaration honesty
# --------------------------------------------------------------------------


def test_declared_capabilities_are_exactly_the_two_the_source_proves() -> None:
    """text_generation (L241-316) and streaming (L253/L259/L272-290). Declaring
    more would violate README §16."""
    assert DECLARED_CAPABILITIES == frozenset({"text_generation", "streaming"})


def test_declared_capabilities_are_valid_v3_capability_ids() -> None:
    """Capability strings must exist in the Core's CapabilityId enum, else the
    registry could not consume them.

    Skipped when Core is not importable (true standalone mode, README §37): the
    PROVIDER must not depend on Core at runtime, so this is a supplemental
    cross-check that only runs inside the repository.
    """
    providers_contract = pytest.importorskip(
        "core.contracts.providers",
        reason="Core not on sys.path (standalone package mode)",
    )
    CapabilityId = providers_contract.CapabilityId

    valid = {c.value for c in CapabilityId}
    assert DECLARED_CAPABILITIES <= valid
    assert UNSUPPORTED_CAPABILITIES <= valid


def test_supports_is_true_only_for_declared_capabilities() -> None:
    provider = _provider()
    assert provider.supports("text_generation")
    assert provider.supports("streaming")
    for capability in UNSUPPORTED_CAPABILITIES:
        assert not provider.supports(capability)


def test_declared_and_unsupported_sets_are_disjoint() -> None:
    assert not (DECLARED_CAPABILITIES & UNSUPPORTED_CAPABILITIES)


def test_reasoning_and_coding_are_not_declared() -> None:
    """The source's banner text calls one model 'Deep Reasoning', but marketing
    strings in the source are DATA, not evidence (README §5/§16)."""
    assert not _provider().supports("reasoning")
    assert not _provider().supports("coding")


def test_manifest_summary_reports_no_account_pool_and_guest_auth() -> None:
    summary = _provider().get_manifest_summary()
    assert summary["account_pool_supported"] is False
    assert summary["auth_types"] == ["none_guest_device"]
    assert summary["models_discovery"] == "static"
    assert summary["streaming"] is True


def test_manifest_summary_static_models_match_source_table() -> None:
    summary = _provider().get_manifest_summary()
    assert summary["static_models"] == [
        "gpt-5.2-2025-12-11",
        "google/gemini-3.5-flash",
        "openai/gpt-4.1-nano",
    ]


# --------------------------------------------------------------------------
# Operations
# --------------------------------------------------------------------------


def test_generate_returns_normalized_response() -> None:
    transport = make_transport(gen_lines=sse([delta_frame("Hello "), delta_frame("world")]) + DONE)
    response = _provider(transport).generate(GenerateRequest(prompt="hi"))

    assert response.text == "Hello world"
    assert response.provider_id == "overchat"
    assert response.model == "google/gemini-3.5-flash"


def test_generate_raises_normalized_error_never_a_raw_status() -> None:
    """README §19: the Core must not see provider HTTP details as exceptions."""
    transport = make_transport(gen_status=500, gen_text="boom")
    with pytest.raises(OverchatError) as excinfo:
        _provider(transport).generate(GenerateRequest(prompt="hi"))

    error = excinfo.value.error
    assert isinstance(error, ProviderError)
    assert error.category == "retryable_server_error"
    assert "boom" not in error.safe_message


def test_generate_surfaces_non_terminal_stream_errors_without_failing() -> None:
    transport = make_transport(
        gen_lines=sse([delta_frame("a"), error_frame("hiccup"), delta_frame("b")]) + DONE
    )
    response = _provider(transport).generate(GenerateRequest(prompt="hi"))

    assert response.text == "ab"
    assert response.stream_errors == ("hiccup",)


def test_per_request_model_override_uses_source_resolution() -> None:
    transport = make_transport(gen_lines=DONE)
    response = _provider(transport).generate(GenerateRequest(prompt="hi", model="gpt-5-2"))

    assert response.model == "gpt-5.2-2025-12-11"
    body = transport.call_to("/v2/chat/responses").json_body
    assert body["personaId"] == "gpt-5-2"


def test_unknown_model_is_passed_through_not_rejected() -> None:
    """Source L368-370 sends an unknown key upstream unchanged. The adapter must
    not invent validation the source does not have."""
    transport = make_transport(gen_lines=DONE)
    response = _provider(transport).generate(GenerateRequest(prompt="hi", model="brand/new-1"))

    assert response.model == "brand/new-1"
    body = transport.call_to("/v2/chat/responses").json_body
    assert body["personaId"] == "brand/new-1"
    assert body["model"] == "brand/new-1"


def test_model_override_does_not_mutate_provider_config() -> None:
    provider = _provider(make_transport(gen_lines=DONE))
    provider.generate(GenerateRequest(prompt="hi", model="gpt-5-2"))
    # the next request must fall back to the configured default
    assert provider._config.model == "google/gemini-3.5-flash"


def test_generate_stream_yields_deltas() -> None:
    transport = make_transport(gen_lines=sse([delta_frame("x"), delta_frame("y")]) + DONE)
    stream = _provider(transport).generate_stream(GenerateRequest(prompt="hi", stream=True))
    assert list(stream) == ["x", "y"]


def test_run_operation_accepts_the_declared_operation() -> None:
    assert DECLARED_OPERATIONS == frozenset({"generate_text"})
    response = _provider().run_operation("generate_text", GenerateRequest(prompt="hi"))
    assert response.text == "hi"


def test_run_operation_rejects_undeclared_operation() -> None:
    """V3 §5: undeclared operations are rejected explicitly."""
    with pytest.raises(OverchatError) as excinfo:
        _provider().run_operation("generate_image", GenerateRequest(prompt="hi"))

    assert excinfo.value.error.category == "unsupported_capability"


# --------------------------------------------------------------------------
# Unsupported capability guards
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "capability"),
    [
        ("generate_image", "image_generation"),
        ("analyze_vision", "vision_input"),
        ("create_embeddings", "embeddings"),
        ("transcribe_audio", "audio_stt"),
        ("synthesize_speech", "audio_tts"),
        ("rerank_documents", "rerank"),
        ("moderate_content", "moderation"),
        ("upload_asset", "file_upload"),
        ("run_provider_agent", "provider_agent"),
    ],
)
def test_unsupported_methods_raise_unsupported_capability(method: str, capability: str) -> None:
    """Each guard must name its own capability; a copy-paste slip would be
    invisible without this parametrization."""
    provider = _provider()
    with pytest.raises(OverchatError) as excinfo:
        getattr(provider, method)()

    error = excinfo.value.error
    assert error.category == "unsupported_capability"
    assert error.retryable is False
    assert error.metadata["capability"] == capability


def test_unsupported_guards_make_no_network_call() -> None:
    """Rejection must be local: no upstream request may be attempted."""
    transport = make_transport(gen_lines=DONE)
    provider = _provider(transport)
    with pytest.raises(OverchatError):
        provider.generate_image()
    assert transport.calls == []


# --------------------------------------------------------------------------
# normalize_error
# --------------------------------------------------------------------------


def test_normalize_error_passes_through_provider_error() -> None:
    error = ProviderError(category="rate_limited", retryable=True, safe_message="slow")
    assert _provider().normalize_error(error) is error


def test_normalize_error_unwraps_overchat_error() -> None:
    inner = ProviderError(category="timeout", retryable=True, safe_message="slow")
    assert _provider().normalize_error(OverchatError(inner)) is inner


def test_normalize_error_classifies_raw_exception() -> None:
    result = _provider().normalize_error(ConnectionError("refused"))
    assert result.category == "provider_unavailable"
    assert result.retryable is True


def test_normalize_error_never_leaks_exception_text() -> None:
    result = _provider().normalize_error(ConnectionError("https://h/p?token=abc"))
    assert "token=abc" not in result.safe_message


def test_normalize_error_handles_non_exception_object() -> None:
    result = _provider().normalize_error({"weird": "object"})
    assert result.category == "non_retryable_error"
    assert result.retryable is False


# --------------------------------------------------------------------------
# Discovery / credentials
# --------------------------------------------------------------------------


def test_discover_models_makes_no_network_call() -> None:
    """Discovery is STATIC (no endpoint in the source), so it must not touch the
    network — a dynamic call would be invented behavior."""
    transport = make_transport(gen_lines=DONE)
    models = _provider(transport).discover_models()

    assert len(models) == 3
    assert transport.calls == []


def test_model_bindings_expose_persona_to_model_mapping() -> None:
    bindings = {b["model_id"]: b["provider_model_name"] for b in _provider().model_bindings()}
    assert bindings == {
        "gpt-5-2": "gpt-5.2-2025-12-11",
        "gemini-3-5-flash": "google/gemini-3.5-flash",
        "free-chat-gpt-landing": "openai/gpt-4.1-nano",
    }
    assert all(b["provider_id"] == "overchat" for b in _provider().model_bindings())


def test_validate_credential_ignores_credential_ref_because_none_exists() -> None:
    """The provider is credential-free; validation degenerates to reachability.
    Passing a ref must neither be required nor change the outcome."""
    transport = make_transport(gen_lines=DONE)
    provider = _provider(transport)

    with_ref = provider.validate_credential("irrelevant-ref")
    without_ref = provider.validate_credential()

    assert with_ref.status == without_ref.status == "healthy"


def test_validate_credential_sends_no_credential_header() -> None:
    transport = make_transport(gen_lines=DONE)
    _provider(transport).validate_credential("some-ref")

    headers = transport.calls[0].headers
    assert "authorization" not in {k.lower() for k in headers}
    assert not any("some-ref" in v for v in headers.values())


def test_config_defaults_are_used_when_none_supplied() -> None:
    provider = OverchatProvider(make_transport(gen_lines=DONE))
    assert provider._config == OverchatConfig()
