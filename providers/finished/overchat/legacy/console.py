"""Windows console encoding fix.

Migrated verbatim from source L31-36. Still platform-gated and still swallows
exceptions, exactly as the source does.
"""

from __future__ import annotations

import sys


def configure_console(platform: str | None = None, streams: object = None) -> bool:
    """Reconfigure stdout/stderr to UTF-8 on win32.

    Source L31-36::

        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    Returns True if reconfiguration was attempted and succeeded, False
    otherwise. Non-win32 platforms are a no-op, as in the source.
    """
    current = sys.platform if platform is None else platform
    if current != "win32":
        return False

    targets = streams if streams is not None else (sys.stdout, sys.stderr)
    try:
        for stream in targets:  # type: ignore[union-attr]
            stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001,S110 - source swallows silently
        return False
    return True
