"""Syntx AI DEFINITION — official provider declaration (deny-by-default).

The registry trusts ONLY this declaration — never code introspection.
Platform-managed credentials with multi-model capability.
"""

from __future__ import annotations

DEFINITION: dict[str, object] = {
    "display_name": "Syntx AI",
    "definition_version": "1.0.0",
    "credential_mode": "platform",
    "capabilities": {"chat": True, "reasoning": True, "code": True},
    "operations": ["generate_text"],
    "models": [
        {"name": "claude-opus-4-8", "context_window": 200000},
        {"name": "gpt-5.6-terra",   "context_window": 128000},
        {"name": "claude-sonnet-5", "context_window": 200000},
        {"name": "grok-4.6",        "context_window": 131072},
    ],
    "health_supported": False,
}
