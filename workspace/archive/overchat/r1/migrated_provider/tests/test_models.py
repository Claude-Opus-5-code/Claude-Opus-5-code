"""Static model discovery parity (source L58-71, L364-370)."""

from __future__ import annotations

import pytest

from overchat.discovery.models import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    DEFAULT_PERSONA_ID,
    DISCOVERY_MODE,
    list_models,
    resolve_model,
)

#: The complete source table, transcribed from L58-71.
SOURCE_TABLE = {
    "gpt-5-2": "gpt-5.2-2025-12-11",
    "gemini-3-5-flash": "google/gemini-3.5-flash",
    "free-chat-gpt-landing": "openai/gpt-4.1-nano",
}


def test_discovery_is_static() -> None:
    """README §27: the source has no model-list endpoint."""
    assert DISCOVERY_MODE == "static"


def test_model_table_is_exactly_the_source_table() -> None:
    """No model added (README §16), none dropped (§17), same mapping."""
    assert {pid: meta["model"] for pid, meta in AVAILABLE_MODELS.items()} == SOURCE_TABLE


def test_model_table_preserves_source_declaration_order() -> None:
    """Order is observable: `--list-models` and the banner iterate this dict."""
    assert list(AVAILABLE_MODELS) == [
        "gpt-5-2",
        "gemini-3-5-flash",
        "free-chat-gpt-landing",
    ]


def test_descriptions_are_preserved() -> None:
    """Arabic descriptions are printed by --list-models, so they are behavior."""
    assert "ChatGPT 5.2" in AVAILABLE_MODELS["gpt-5-2"]["desc"]
    assert AVAILABLE_MODELS["gemini-3-5-flash"]["desc"].startswith("⚡")
    assert AVAILABLE_MODELS["free-chat-gpt-landing"]["desc"].startswith("🚀")


def test_defaults_match_source() -> None:
    """Source L54-55."""
    assert (DEFAULT_PERSONA_ID, DEFAULT_MODEL) == (
        "gemini-3-5-flash",
        "google/gemini-3.5-flash",
    )


@pytest.mark.parametrize(("key", "expected_model"), sorted(SOURCE_TABLE.items()))
def test_known_key_resolves_to_mapped_model(key: str, expected_model: str) -> None:
    """Source L365-367: persona_id = key, model = table lookup."""
    assert resolve_model(key) == (key, expected_model)


@pytest.mark.parametrize(
    "unknown",
    ["claude-4", "gpt-5.2-2025-12-11", "", "google/gemini-3.5-flash"],
)
def test_unknown_key_passes_through_as_both_fields(unknown: str) -> None:
    """Source L368-370 — the intentional passthrough branch.

    An unknown key becomes BOTH persona_id and model with no validation and no
    error. Note the deliberately included cases: a raw MODEL NAME (not a persona
    key) also passes through unchanged, because the source only ever checks
    membership in the persona table. Preserving this is what lets the source
    reach models absent from its own table (README §17/§18).
    """
    assert resolve_model(unknown) == (unknown, unknown)


def test_unknown_key_is_not_silently_replaced_by_the_default() -> None:
    """Guard against a 'helpful' fallback that the source does not have."""
    persona, model = resolve_model("totally-unknown")
    assert persona != DEFAULT_PERSONA_ID
    assert model != DEFAULT_MODEL


def test_list_models_shape_and_order() -> None:
    listed = list_models()
    assert [m["persona_id"] for m in listed] == list(AVAILABLE_MODELS)
    assert [m["model"] for m in listed] == list(SOURCE_TABLE.values())
    assert all({"persona_id", "model", "desc"} == set(m) for m in listed)


def test_model_table_is_immutable() -> None:
    """Adaptation M5: prevent runtime mutation of the declared table."""
    with pytest.raises(TypeError):
        AVAILABLE_MODELS["x"] = {"model": "x", "desc": "x"}  # type: ignore[index]
    with pytest.raises(TypeError):
        AVAILABLE_MODELS["gpt-5-2"]["model"] = "hacked"  # type: ignore[index]
