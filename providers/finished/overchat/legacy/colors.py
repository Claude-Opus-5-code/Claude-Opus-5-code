"""Optional colorama support with the source's exact fallback.

Migrated verbatim from source L39-45::

    try:
        from colorama import init, Fore, Style
        init(autoreset=True)
    except ImportError:
        class _F:
            def __getattr__(self, _): return ""
        Fore = Style = _F()

The fallback returns "" for ANY attribute access, which is why every colour
reference in the source degrades safely when colorama is absent.
"""

from __future__ import annotations


class _NullColors:
    """Source `_F` (L43-44): any attribute resolves to an empty string."""

    def __getattr__(self, _name: str) -> str:
        return ""


try:  # pragma: no cover - depends on environment
    from colorama import Fore as _Fore
    from colorama import Style as _Style
    from colorama import init as _init

    _init(autoreset=True)
    Fore: object = _Fore
    Style: object = _Style
    COLORAMA_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    Fore = Style = _NullColors()
    COLORAMA_AVAILABLE = False
