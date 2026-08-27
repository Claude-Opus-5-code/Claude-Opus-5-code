"""Config parity with source `Config` (L51-92).

These assertions are pinned to literal values read from the source, so a change
to any default in the migrated package fails the test. That is the point: the
config IS observable behavior (it decides URLs, timeouts, and the model).
"""

from __future__ import annotations

import dataclasses

import pytest

from overchat.config import DEFAULT_SYSTEM_PROMPT, OverchatConfig


def test_defaults_match_source_exactly() -> None:
    """Source L54-92: every default, verbatim."""
    config = OverchatConfig()

    assert config.persona_id == "gemini-3-5-flash"  # L54
    assert config.model == "google/gemini-3.5-flash"  # L55
    assert config.input_file == "chat_send.txt"  # L74
    assert config.output_file == "chat_reply.txt"  # L75
    assert config.max_lines is None  # L78
    assert config.max_chars is None  # L79
    assert config.base_url == "https://api.overchat.ai"  # L82
    assert config.timeout_seconds == 120  # L85


def test_system_prompt_is_source_text_verbatim() -> None:
    """Source L88-92. Sent upstream on every title call, so it is behavior."""
    assert config_prompt() == (
        "You are an expert AI assistant. "
        "Provide accurate, structured, and well-reasoned responses. "
        "Reply in Egyptian Arabic when requested or appropriate."
    )


def config_prompt() -> str:
    return OverchatConfig().system_prompt


def test_default_system_prompt_constant_is_the_default() -> None:
    assert OverchatConfig().system_prompt == DEFAULT_SYSTEM_PROMPT


def test_ip_spoof_flag_defaults_to_source_behavior() -> None:
    """Adaptation M8: the flag is migration-added but MUST default to the
    source's behavior, which always sends the three IP headers."""
    assert OverchatConfig().include_ip_spoof_headers is True


def test_config_is_frozen() -> None:
    """Adaptation M4. The source mutated cfg in place; here mutation must fail
    so provider state cannot be changed mid-flight."""
    config = OverchatConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.persona_id = "other"  # type: ignore[misc]


def test_with_values_returns_new_object_and_leaves_original_untouched() -> None:
    """`with_values` replaces the source's in-place reassignment (L366-379)."""
    original = OverchatConfig()
    updated = original.with_values(persona_id="gpt-5-2", model="gpt-5.2-2025-12-11")

    assert updated is not original
    assert (updated.persona_id, updated.model) == ("gpt-5-2", "gpt-5.2-2025-12-11")
    # original untouched
    assert (original.persona_id, original.model) == (
        "gemini-3-5-flash",
        "google/gemini-3.5-flash",
    )
    # unrelated fields carried over
    assert updated.base_url == original.base_url
    assert updated.timeout_seconds == original.timeout_seconds


def test_available_models_exposes_source_map_and_is_read_only() -> None:
    """Source `Config.available_models` (L58-71) is reachable from config, and
    adaptation M5 makes it immutable."""
    models = OverchatConfig().available_models
    assert set(models) == {"gpt-5-2", "gemini-3-5-flash", "free-chat-gpt-landing"}
    with pytest.raises(TypeError):
        models["new"] = {}  # type: ignore[index]
