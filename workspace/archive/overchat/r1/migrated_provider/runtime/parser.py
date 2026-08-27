"""SSE stream parsing.

Migrated from source L272-290. The parsing rules are reproduced exactly; the
only change is structural (adaptation M2): the source wrote deltas straight to
stdout inside the loop, whereas this yields normalized events so the operation
layer can both print them (legacy behavior) and accumulate them.

PRESERVED SEMANTICS - each of these is a real behavior of the source, not an
accident to be cleaned up:
  * falsy lines are skipped                                (L273)
  * decoding uses errors="replace", never raising          (L274)
  * only lines starting with "data:" are considered        (L275)
  * ONLY THE FIRST "data: " occurrence is stripped, then
    the remainder is .strip()ed                            (L276)
  * exactly "[DONE]" terminates the stream                 (L277-278)
  * only event == "response.output_text.delta" produces text (L281)
  * the delta is read from data["data"]["delta"]           (L282)
  * a falsy delta is skipped                               (L283)
  * event == "error" is REPORTED BUT NON-TERMINAL: the
    source prints the message and keeps reading            (L287-288)
  * any per-frame exception (bad JSON, missing "data" key)
    is silently ignored and the loop continues             (L289-290)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Iterator

#: Source L281.
DELTA_EVENT = "response.output_text.delta"

#: Source L287.
ERROR_EVENT = "error"

#: Source L277.
DONE_SENTINEL = "[DONE]"

#: Source L275.
DATA_PREFIX = "data:"

#: Source L276 - note the trailing space and count=1.
DATA_STRIP_PREFIX = "data: "


@dataclass(frozen=True)
class DeltaEvent:
    """A text delta (source L282-286)."""

    text: str


@dataclass(frozen=True)
class StreamErrorEvent:
    """An in-stream error frame (source L287-288).

    Non-terminal by design: the source prints it and continues reading.
    """

    message: Any


def iter_events(lines: Iterable[bytes | str]) -> Iterator[DeltaEvent | StreamErrorEvent]:
    """Parse raw SSE lines into events, exactly as the source does.

    Accepts bytes (as `requests.iter_lines()` yields) or str.
    """
    for line in lines:
        if not line:  # source L273
            continue

        if isinstance(line, bytes):
            decoded_line = line.decode("utf-8", errors="replace")  # source L274
        else:
            decoded_line = line

        if not decoded_line.startswith(DATA_PREFIX):  # source L275
            continue

        json_str = decoded_line.replace(DATA_STRIP_PREFIX, "", 1).strip()  # source L276

        if json_str == DONE_SENTINEL:  # source L277-278
            break

        try:
            data = json.loads(json_str)  # source L280
            event = data.get("event")
            if event == DELTA_EVENT:  # source L281
                delta = data["data"].get("delta", "")  # source L282
                if delta:  # source L283
                    yield DeltaEvent(text=delta)
            elif event == ERROR_EVENT:  # source L287
                yield StreamErrorEvent(message=data["data"].get("message"))  # source L288
        except Exception:  # noqa: BLE001,S112 - source L289-290 ignores silently
            continue


def iter_text_deltas(lines: Iterable[bytes | str]) -> Iterator[str]:
    """Yield only the text deltas, in order."""
    for event in iter_events(lines):
        if isinstance(event, DeltaEvent):
            yield event.text


def accumulate_reply(lines: Iterable[bytes | str]) -> str:
    """Concatenate all deltas into the full reply (source `bot_full_reply`)."""
    return "".join(iter_text_deltas(lines))
