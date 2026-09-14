#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏛️ Provider Contract & Standard Compliance Test
Verifies that all active providers in `providers/` conform strictly to Bolla Constitution v1.2
and PROVIDER_CONSTANTS_AND_TOOLKIT.md v2.1 (The Four Core Files + Trinity Functions + Gateway Facade).
"""
import sys
import json
import inspect
import importlib
from pathlib import Path
import pytest

PROVIDERS_DIR = Path(__file__).resolve().parents[1] / "providers"

REQUIRED_FILES = [
    "__init__.py",
    "_core.py",
    "adapter.py",
    "definition.py",
    "models_metadata.json",
]


def get_live_provider_slugs():
    """Discover production provider directories under providers/ (skipping templates and groq placeholder)."""
    slugs = []
    for item in PROVIDERS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith((".", "_")):
            if (item / "definition.py").exists() and (item / "_core.py").exists():
                slugs.append(item.name)
    return sorted(slugs)


@pytest.mark.parametrize("slug", get_live_provider_slugs())
def test_provider_file_structure(slug):
    """Ensure all 4 core files + __init__.py exist."""
    pdir = PROVIDERS_DIR / slug
    for fname in REQUIRED_FILES:
        target = pdir / fname
        assert target.exists(), f"Provider '{slug}' is missing required file: {fname}"


@pytest.mark.parametrize("slug", get_live_provider_slugs())
def test_models_metadata_json_schema(slug):
    """Ensure models_metadata.json is valid JSON and contains model definitions."""
    meta_path = PROVIDERS_DIR / slug / "models_metadata.json"
    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Supports either list of models or dict keyed by model_id
    if isinstance(data, dict):
        if "models" in data and isinstance(data["models"], list):
            models_list = data["models"]
            assert len(models_list) > 0, f"{slug}/models_metadata.json 'models' list is empty"
        else:
            # Keyed by model ID
            assert len(data) > 0, f"{slug}/models_metadata.json is empty"
            for m_id, m_info in data.items():
                if isinstance(m_info, dict):
                    assert (
                        "label" in m_info
                        or "context_window" in m_info
                        or "capabilities" in m_info
                    ), f"Model {m_id} in {slug} lacks basic metadata"
    elif isinstance(data, list):
        assert len(data) > 0, f"{slug}/models_metadata.json list is empty"
    else:
        pytest.fail(f"Invalid models_metadata.json shape in {slug}")


@pytest.mark.parametrize("slug", get_live_provider_slugs())
def test_definition_schema(slug):
    """Ensure definition.py exports a valid DEFINITION dictionary conforming to Gateway v1."""
    mod = importlib.import_module(f"providers.{slug}.definition")
    assert hasattr(mod, "DEFINITION"), f"{slug}/definition.py must export 'DEFINITION'"
    d = getattr(mod, "DEFINITION")
    assert isinstance(d, dict), f"{slug} DEFINITION must be a dictionary"
    assert "display_name" in d, f"{slug} DEFINITION missing display_name"
    assert "credential_mode" in d or "auth_pattern" in d, f"{slug} DEFINITION missing credential/auth mode"
    assert "capabilities" in d or "models" in d, f"{slug} DEFINITION missing capabilities or models"


@pytest.mark.parametrize("slug", get_live_provider_slugs())
def test_adapter_and_core_contract(slug):
    """Ensure adapter.py and _core.py provide execution and error handling interfaces."""
    core_mod = importlib.import_module(f"providers.{slug}._core")
    adapter_mod = importlib.import_module(f"providers.{slug}.adapter")

    # Core must have text generation / chat execution capability
    has_gen = (
        hasattr(core_mod, "generate_text")
        or hasattr(core_mod, "execute_chat")
        or hasattr(core_mod, "ask")
        or hasattr(core_mod, "chat")
    )
    assert has_gen, f"{slug}/_core.py must implement generate_text() or execute_chat() or ask()"

    # Core must define UpstreamFailure exception
    assert hasattr(core_mod, "UpstreamFailure"), f"{slug}/_core.py must define UpstreamFailure exception"

    # Adapter must implement at least generate_text or complete handler
    has_handler = hasattr(adapter_mod, "generate_text") or hasattr(adapter_mod, "complete")
    assert has_handler, f"{slug}/adapter.py must implement generate_text(context) or complete(context)"

    # Adapter must have error translation helper
    has_err_translator = hasattr(adapter_mod, "_translate_upstream_failure") or hasattr(adapter_mod, "translate_error")
    assert has_err_translator, f"{slug}/adapter.py must implement _translate_upstream_failure"


def test_no_rogue_or_uppercase_error_categories():
    """Ensure no UpstreamFailure uses an uppercase or invalid error category across providers."""
    from gateway.contracts import ErrorCategory
    valid_categories = {c.value for c in ErrorCategory}

    import re
    pat = re.compile(r'UpstreamFailure\(\s*["\']([A-Za-z0-9_]+)["\']')
    for py_file in PROVIDERS_DIR.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="replace")
        for match in pat.finditer(content):
            cat = match.group(1)
            assert cat in valid_categories, (
                f"[{py_file.name}] Rogue or uppercase error category '{cat}'. "
                f"Must be one of: {sorted(valid_categories)}"
            )
