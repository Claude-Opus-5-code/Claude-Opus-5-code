"""Honest static provider declaration; no runtime state or network discovery."""

from ._config import MODEL_AI_NAMES

DEFINITION: dict[str, object] = {
    "display_name": "Syntx",
    "definition_version": "1.0.0",
    "credential_mode": "platform",
    "capabilities": {"chat": True, "reasoning": True, "code": True, "vision_input": True},
    "operations": ["generate_text", "analyze_vision"],
    "models": [{"name": name} for name in MODEL_AI_NAMES],
    "health_supported": False,
}
