"""Syntx AI provider — Enterprise Platform Credential Pool.

Three-layer model, applied:

    Layer 1 (free)      -> _upstream.py            real httpx calls to Syntx AI
                                                   with multi-process pool & cooldown
    Layer 2 (mandatory) -> adapter.py              the facade: canonical in/out
    Layer 3 (fixed)     -> gateway.contracts       imported, never modified

Credential mode: ``platform`` — managed via the local accounts pool or environment.
"""

from __future__ import annotations
