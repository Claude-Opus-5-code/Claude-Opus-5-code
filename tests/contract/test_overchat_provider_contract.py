"""Overchat <-> Core contract conformance (README §19, V3 §3/§7/§8.1).

These tests live at REPO level, not inside the provider package, because they
assert the provider is consumable by the Core's generic contracts and that it
does NOT weaken or extend them.

They deliberately do not re-test provider internals (that is the provider's own
suite); they test the boundary.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from core.contracts import (
    CapabilityId,
    Modality,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderModelBinding,
    ProviderRef,
    ProviderStatus,
)

# The finished provider is a standalone package; add its parent to sys.path the
# same way a Core plugin loader would.
_PROVIDER_PARENT = Path(__file__).resolve().parents[2] / "providers" / "finished"
if str(_PROVIDER_PARENT) not in sys.path:
    sys.path.insert(0, str(_PROVIDER_PARENT))

from overchat.provider import (  # noqa: E402
    DECLARED_CAPABILITIES,
    DECLARED_MODALITIES,
    PROVIDER_ID,
    UNSUPPORTED_CAPABILITIES,
    GenerateRequest,
    OverchatProvider,
)
from overchat.runtime.errors import OverchatError  # noqa: E402
from overchat.tests.conftest import (  # noqa: E402
    FakeResponse,
    RecordingTransport,
    delta_frame,
    make_transport,
    sse,
)

MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "providers" / "finished" / "overchat" / "manifest.yaml"
)
DONE = [b"data: [DONE]"]


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Capability / modality vocabulary
# --------------------------------------------------------------------------


def test_declared_capabilities_are_core_capability_ids() -> None:
    """A capability string the Core cannot parse would make the provider
    unroutable."""
    valid = {c.value for c in CapabilityId}
    assert DECLARED_CAPABILITIES <= valid
    assert UNSUPPORTED_CAPABILITIES <= valid


def test_declared_modalities_are_core_modalities() -> None:
    assert DECLARED_MODALITIES <= {m.value for m in Modality}


def test_provider_ref_can_be_constructed_from_the_adapter() -> None:
    """The provider must fit the generic ProviderRef WITHOUT extra fields
    (`extra="forbid"`), proving no provider-specific field leaked into the
    generic contract (README §19)."""
    provider = OverchatProvider(make_transport(gen_lines=DONE))
    ref = ProviderRef(
        provider_id=provider.provider_id,
        display_name=provider.display_name,
        status=ProviderStatus.DISABLED,
        capabilities={CapabilityId(c) for c in provider.get_capabilities()},
        modalities={Modality.TEXT},
    )

    assert ref.provider_id == "overchat"
    assert CapabilityId.TEXT_GENERATION in ref.capabilities
    assert CapabilityId.STREAMING in ref.capabilities


def test_model_bindings_satisfy_the_generic_binding_contract() -> None:
    """V3 §3: Model != Provider. Bindings must carry the provider-specific model
    name separately from the logical model id."""
    provider = OverchatProvider(make_transport(gen_lines=DONE))
    bindings = [ProviderModelBinding(**b) for b in provider.model_bindings()]

    assert len(bindings) == 3
    for binding in bindings:
        assert binding.provider_id == PROVIDER_ID
        assert binding.model_id  # persona id
        assert binding.provider_model_name  # upstream model string
    # gemini persona maps to a DIFFERENT upstream name: the distinction is real
    gemini = next(b for b in bindings if b.model_id == "gemini-3-5-flash")
    assert gemini.provider_model_name == "google/gemini-3.5-flash"


def test_health_report_maps_onto_generic_provider_health() -> None:
    provider = OverchatProvider(make_transport(gen_lines=DONE))
    report = provider.health_check()

    health = ProviderHealth(
        provider_id=report.provider_id,
        status=ProviderHealthStatus(report.status),
        message=report.message,
    )
    assert health.status is ProviderHealthStatus.HEALTHY
    assert health.provider_id == "overchat"


def test_unavailable_health_also_maps_cleanly() -> None:
    transport = RecordingTransport(handler=lambda m, u: FakeResponse(502, text="Bad Gateway"))
    report = OverchatProvider(transport).health_check()

    health = ProviderHealth(
        provider_id=report.provider_id,
        status=ProviderHealthStatus(report.status),
        message=report.message,
    )
    assert health.status is ProviderHealthStatus.UNAVAILABLE


# --------------------------------------------------------------------------
# Manifest <-> code agreement
# --------------------------------------------------------------------------


def test_manifest_capabilities_match_the_adapter_exactly(manifest: dict) -> None:
    """A manifest that over-claims relative to code is a governance failure."""
    assert set(manifest["declared_capabilities"]) == DECLARED_CAPABILITIES


def test_manifest_unsupported_capabilities_match_the_adapter(manifest: dict) -> None:
    assert set(manifest["unsupported_capabilities"]) == UNSUPPORTED_CAPABILITIES


def test_manifest_modalities_match_the_adapter(manifest: dict) -> None:
    assert set(manifest["declared_modalities"]) == DECLARED_MODALITIES


def test_manifest_provider_id_matches_code(manifest: dict) -> None:
    assert manifest["id"] == PROVIDER_ID


def test_manifest_is_not_auto_activated(manifest: dict) -> None:
    """README §21: production routing must NOT be enabled automatically."""
    assert manifest["status"] == "disabled"
    assert manifest["activation"] == "integration_pending"
    assert ProviderStatus(manifest["status"]) is ProviderStatus.DISABLED


def test_manifest_declares_no_account_pool(manifest: dict) -> None:
    """README §29: pool behavior must not be invented; the source has none."""
    assert manifest["account_pool"]["supported"] is False
    assert manifest["retries"]["supported"] is False
    assert manifest["polling"]["supported"] is False


def test_manifest_declares_credential_free_auth(manifest: dict) -> None:
    assert manifest["auth"]["credential_required"] is False
    assert manifest["auth"]["types"] == ["none_guest_device"]


def test_manifest_static_models_match_code(manifest: dict) -> None:
    provider = OverchatProvider(make_transport(gen_lines=DONE))
    code_models = {(m["persona_id"], m["model"]) for m in provider.discover_models()}
    manifest_models = {
        (m["persona_id"], m["model"]) for m in manifest["models"]["static_models"]
    }
    assert code_models == manifest_models


def test_manifest_records_source_provenance_hash(manifest: dict) -> None:
    """README §10/§21: declared behavior must be traceable to hashed source."""
    provenance = manifest["provenance"]
    assert provenance["source_sha256"] == (
        "d513c0359c8aada2801a3d847466cf2d0e865e33fd05f0d180c902187cbbc470"
    )
    assert provenance["source_lines"] == 403


def test_manifest_streaming_semantics_match_parser_behavior(manifest: dict) -> None:
    """The manifest claims the `error` event is NON-terminal; prove the code
    agrees, so documentation cannot drift from behavior."""
    assert manifest["streaming"]["error_event_terminal"] is False

    from overchat.tests.conftest import error_frame

    transport = make_transport(
        gen_lines=sse([delta_frame("a"), error_frame("x"), delta_frame("b")]) + DONE
    )
    response = OverchatProvider(transport).generate(GenerateRequest(prompt="p"))
    assert response.text == "ab"  # stream continued past the error


def test_manifest_success_statuses_match_code(manifest: dict) -> None:
    from overchat.runtime.errors import SUCCESS_STATUSES

    assert tuple(manifest["errors"]["success_statuses"]) == SUCCESS_STATUSES


def test_manifest_body_truncation_limits_match_code(manifest: dict) -> None:
    from overchat.runtime.errors import AUTH_BODY_TRUNCATION, GENERATION_BODY_TRUNCATION

    assert manifest["errors"]["body_truncation"]["auth"] == AUTH_BODY_TRUNCATION
    assert manifest["errors"]["body_truncation"]["generation"] == GENERATION_BODY_TRUNCATION


# --------------------------------------------------------------------------
# Boundary hygiene
# --------------------------------------------------------------------------


def test_core_contracts_do_not_import_the_provider() -> None:
    """Core must remain ignorant of provider specifics (README §19)."""
    core_dir = Path(__file__).resolve().parents[2] / "core"
    for path in core_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "overchat" not in text.lower(), f"{path} references the provider"


def test_provider_errors_never_reach_core_as_raw_exceptions() -> None:
    """Any failure must surface as OverchatError carrying a normalized error."""
    transport = make_transport(gen_status=500, gen_text="internal detail")
    provider = OverchatProvider(transport)

    with pytest.raises(OverchatError) as excinfo:
        provider.generate(GenerateRequest(prompt="hi"))

    error = excinfo.value.error
    assert error.category in {c for c in _NORMALIZED_CATEGORIES}
    assert "internal detail" not in error.safe_message
    # the serialized form carries no provider internals
    assert "metadata" not in error.to_dict()


_NORMALIZED_CATEGORIES = {
    "auth_expired",
    "invalid_credential",
    "rate_limited",
    "quota_exceeded",
    "model_unavailable",
    "provider_unavailable",
    "unsupported_capability",
    "bad_request",
    "content_rejected",
    "timeout",
    "retryable_server_error",
    "non_retryable_error",
}


def test_every_normalized_category_is_from_the_fixed_vocabulary() -> None:
    """V3 §14 defines a fixed category set; the provider must not invent one."""
    from overchat.runtime import errors as err_mod

    declared = {
        value
        for name, value in vars(err_mod).items()
        if name.startswith("CATEGORY_") and isinstance(value, str)
    }
    assert declared == _NORMALIZED_CATEGORIES


def test_provider_package_has_no_import_dependency_on_the_workspace() -> None:
    """README §37: no RUNTIME dependency on the migration workspace.

    Checked via AST over import statements rather than raw text, because
    docstrings legitimately CITE workspace evidence paths (README §22 requires
    traceability); a substring scan would conflate a citation with a dependency.
    """
    import ast

    pkg = Path(__file__).resolve().parents[2] / "providers" / "finished" / "overchat"
    offenders: list[str] = []

    for path in pkg.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if "workspace" in name or "source_snapshot" in name:
                    offenders.append(f"{path.name}: {name}")

    assert offenders == []


def test_provider_package_does_not_read_workspace_paths_at_runtime() -> None:
    """Complements the import check: no executable code may open a workspace
    path. Docstrings are excluded via tokenize so evidence citations are kept."""
    import io
    import tokenize

    pkg = Path(__file__).resolve().parents[2] / "providers" / "finished" / "overchat"
    offenders: list[str] = []

    for path in pkg.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            # Only NAME/OP/NUMBER carry executable references; STRING tokens
            # here would be docstrings or evidence citations.
            if token.type == tokenize.NAME and token.string in {"workspace", "source_snapshot"}:
                offenders.append(f"{path.name}:{token.start[0]}")

    assert offenders == []
