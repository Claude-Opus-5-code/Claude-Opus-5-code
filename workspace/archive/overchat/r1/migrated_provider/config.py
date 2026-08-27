"""Provider configuration.

Migrated verbatim from source `Config` dataclass (source L51-92). Every field
name, default value, and type is preserved. Only mutability changed: the source
dataclass is mutable and reassigned in `main()`; here it is frozen and updated
through `replace()`, which produces identical values (adaptation M4).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .discovery.models import AVAILABLE_MODELS

#: Source L88-92, verbatim.
DEFAULT_SYSTEM_PROMPT = (
    "You are an expert AI assistant. "
    "Provide accurate, structured, and well-reasoned responses. "
    "Reply in Egyptian Arabic when requested or appropriate."
)


@dataclass(frozen=True)
class OverchatConfig:
    """Unified provider settings.

    Source mapping (all defaults identical to source L54-92):

    ==========================  ============  ==========================
    field                       source line   source default
    ==========================  ============  ==========================
    persona_id                  L54           "gemini-3-5-flash"
    model                       L55           "google/gemini-3.5-flash"
    input_file                  L74           "chat_send.txt"
    output_file                 L75           "chat_reply.txt"
    max_lines                   L78           None
    max_chars                   L79           None
    base_url                    L82           "https://api.overchat.ai"
    timeout_seconds             L85           120
    system_prompt               L88-92        DEFAULT_SYSTEM_PROMPT
    ==========================  ============  ==========================
    """

    persona_id: str = "gemini-3-5-flash"
    model: str = "google/gemini-3.5-flash"

    input_file: str = "chat_send.txt"
    output_file: str = "chat_reply.txt"

    # None = no limit at all (source L77-79). NOTE: the source uses a falsy
    # check (`if cfg.max_lines and ...`), so 0 also means "no limit". That
    # semantic is preserved in legacy.file_io.
    max_lines: int | None = None
    max_chars: int | None = None

    base_url: str = "https://api.overchat.ai"
    timeout_seconds: int = 120
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    # Migration-added switch (adaptation M8). Default True == source behavior:
    # the source always sends the three IP-spoof headers.
    include_ip_spoof_headers: bool = True

    @property
    def available_models(self) -> Any:
        """Source `Config.available_models` (L58-71), read-only."""
        return AVAILABLE_MODELS

    def with_values(self, **changes: Any) -> "OverchatConfig":
        """Return a copy with overrides (replaces source's in-place mutation)."""
        return replace(self, **changes)
