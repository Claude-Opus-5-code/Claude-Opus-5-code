"""Static model discovery.

Model discovery for this provider is STATIC. The source contains no model-list
endpoint and no dynamic discovery of any kind: the three entries below are the
complete, literal contents of `Config.available_models` (source L58-71).

Zero-invention rule (README §16/§27): no model, alias, or id is added here that
is not present in the source. `google/gemini-3.5-flash` is the source default
(L54-55).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

#: Discovery mode for this provider, derived from source evidence (no endpoint).
DISCOVERY_MODE = "static"

#: Source L58-71, verbatim: persona_id -> {model, desc}.
AVAILABLE_MODELS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "gpt-5-2": MappingProxyType(
            {
                "model": "gpt-5.2-2025-12-11",
                "desc": "🧠 الوحش ChatGPT 5.2 (Deep Reasoning & Smart Logic)",
            }
        ),
        "gemini-3-5-flash": MappingProxyType(
            {
                "model": "google/gemini-3.5-flash",
                "desc": "⚡ جوجل فلاش 3.5 (Ultra Fast Speed & Instant Response)",
            }
        ),
        "free-chat-gpt-landing": MappingProxyType(
            {
                "model": "openai/gpt-4.1-nano",
                "desc": "🚀 شات جي بي تي نانو (Lightweight & Free Landing Model)",
            }
        ),
    }
)

#: Source default persona/model pair (L54-55).
DEFAULT_PERSONA_ID = "gemini-3-5-flash"
DEFAULT_MODEL = "google/gemini-3.5-flash"


def resolve_model(requested: str) -> tuple[str, str]:
    """Resolve a requested model key to ``(persona_id, model)``.

    Extracted verbatim from source `main()` L364-370::

        if args.model in cfg.available_models:
            cfg.persona_id = args.model
            cfg.model = cfg.available_models[args.model]["model"]
        else:
            cfg.persona_id = args.model
            cfg.model = args.model

    The `else` branch is an intentional PASSTHROUGH: an unknown key is sent
    upstream unchanged, as both persona_id and model, with no validation and no
    error. This is preserved exactly (README §17/§18) - it is how the source
    supports models that are not in its own table.
    """
    entry = AVAILABLE_MODELS.get(requested)
    if entry is not None:
        return requested, entry["model"]
    return requested, requested


def list_models() -> list[dict[str, str]]:
    """Static model listing, in source declaration order."""
    return [
        {"persona_id": pid, "model": meta["model"], "desc": meta["desc"]}
        for pid, meta in AVAILABLE_MODELS.items()
    ]
