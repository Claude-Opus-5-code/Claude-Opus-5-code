"""Input/output statistics.

Migrated from source L178-189 (input) and L292-306 (output). The formulas are
preserved exactly, including the /3.5 token approximation and the divide-by-zero
guard.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Source L181: chars per approximate token.
CHARS_PER_TOKEN = 3.5


@dataclass(frozen=True)
class InputStats:
    chars: int
    lines: int
    words: int
    approx_tokens: int


@dataclass(frozen=True)
class OutputStats:
    chars: int
    lines: int
    words: int
    elapsed_seconds: float
    chars_per_second: float


def input_stats(prompt_text: str) -> InputStats:
    """Source L178-181, exact."""
    char_count = len(prompt_text)
    return InputStats(
        chars=char_count,
        lines=len(prompt_text.splitlines()),
        words=len(prompt_text.split()),
        approx_tokens=int(char_count / CHARS_PER_TOKEN),
    )


def output_stats(reply_text: str, elapsed_seconds: float) -> OutputStats:
    """Source L293-296, exact.

    Speed is `out_chars / elapsed if elapsed > 0 else 0` - the guard is the
    source's, preserved to avoid ZeroDivisionError on instant replies.
    """
    out_chars = len(reply_text)
    speed = out_chars / elapsed_seconds if elapsed_seconds > 0 else 0
    return OutputStats(
        chars=out_chars,
        lines=len(reply_text.splitlines()),
        words=len(reply_text.split()),
        elapsed_seconds=elapsed_seconds,
        chars_per_second=speed,
    )
