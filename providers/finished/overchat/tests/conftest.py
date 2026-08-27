"""Shared test doubles.

The `RecordingTransport` below is the backbone of both the deterministic tests
and the differential parity test: it records every call the provider makes
(method, url, headers, body, timeout, stream flag) so tests can assert on the
EXACT requests instead of on internal implementation details.

It deliberately mimics only what `requests` exposes to the source, so the same
object can drive the ORIGINAL script and the MIGRATED package (README §23).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import pytest

# Make the provider package importable as `overchat` when tests are run from
# inside the finished package (standalone mode, README §37).
_PKG_DIR = Path(__file__).resolve().parent.parent
_PARENT = _PKG_DIR.parent
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))


@dataclass
class RecordedCall:
    """One HTTP call, captured verbatim."""

    method: str
    url: str
    headers: dict[str, str]
    body: str | None
    timeout: int | None
    stream: bool

    @property
    def json_body(self) -> Any:
        """Parse the recorded body, which the provider always sends as a string."""
        return None if self.body is None else json.loads(self.body)


class FakeResponse:
    """Minimal stand-in for `requests.Response`."""

    def __init__(
        self,
        status_code: int = 200,
        payload: Any = None,
        text: str = "",
        lines: Iterable[bytes | str] = (),
        raise_on_json: bool = False,
        raise_on_iter: BaseException | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self._lines = list(lines)
        self._raise_on_json = raise_on_json
        self._raise_on_iter = raise_on_iter

    def json(self) -> Any:
        if self._raise_on_json:
            raise ValueError("not json")
        return self._payload

    def iter_lines(self) -> Iterable[bytes | str]:
        if self._raise_on_iter is not None:
            raise self._raise_on_iter
        return iter(self._lines)


@dataclass
class RecordingTransport:
    """Records calls and returns queued/scripted responses.

    `handler` receives (method, url) and returns a FakeResponse, so a test can
    script per-endpoint behavior without caring about call order.
    """

    handler: Callable[[str, str], FakeResponse] | None = None
    calls: list[RecordedCall] = field(default_factory=list)
    raise_on: dict[str, BaseException] = field(default_factory=dict)

    # -- helpers ------------------------------------------------------------

    @property
    def urls(self) -> list[str]:
        return [c.url for c in self.calls]

    @property
    def methods(self) -> list[str]:
        return [c.method for c in self.calls]

    @property
    def flow(self) -> list[tuple[str, str]]:
        return [(c.method, c.url) for c in self.calls]

    def call_to(self, needle: str) -> RecordedCall:
        for call in self.calls:
            if needle in call.url:
                return call
        raise AssertionError(f"no recorded call matching {needle!r}; got {self.urls}")

    # -- transport surface --------------------------------------------------

    def _record(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: int | None = None,
        data: str | None = None,
        stream: bool = False,
    ) -> FakeResponse:
        self.calls.append(
            RecordedCall(
                method=method,
                url=url,
                # copy: the provider reuses/mutates header dicts between steps
                headers=dict(headers),
                body=data,
                timeout=timeout,
                stream=stream,
            )
        )
        for needle, exc in self.raise_on.items():
            if needle in url:
                raise exc
        if self.handler is None:
            return FakeResponse(status_code=200, payload={"id": "guest-1"})
        return self.handler(method, url)

    def get(self, url: str, *, headers: dict[str, str], timeout: int | None = None) -> FakeResponse:
        return self._record("GET", url, headers=headers, timeout=timeout)

    def post(
        self,
        url: str,
        *,
        data: str | None = None,
        headers: dict[str, str],
        timeout: int | None = None,
        stream: bool = False,
    ) -> FakeResponse:
        return self._record("POST", url, headers=headers, timeout=timeout, data=data, stream=stream)

    def patch(
        self,
        url: str,
        *,
        data: str | None = None,
        headers: dict[str, str],
        timeout: int | None = None,
    ) -> FakeResponse:
        return self._record("PATCH", url, headers=headers, timeout=timeout, data=data)


def sse(frames: Iterable[dict[str, Any]]) -> list[bytes]:
    """Encode dicts as `data: {...}` SSE byte lines, as upstream would."""
    return [f"data: {json.dumps(f)}".encode() for f in frames]


def delta_frame(text: str) -> dict[str, Any]:
    """A delta frame in the exact shape the source expects (L281-282)."""
    return {"event": "response.output_text.delta", "data": {"delta": text}}


def error_frame(message: str) -> dict[str, Any]:
    """An in-stream error frame (source L287-288)."""
    return {"event": "error", "data": {"message": message}}


def make_transport(
    *,
    auth_status: int = 200,
    auth_payload: Any = None,
    gen_status: int = 200,
    gen_lines: Iterable[bytes | str] = (),
    gen_text: str = "",
    auth_text: str = "",
) -> RecordingTransport:
    """Build a transport scripted for the normal 4-step flow."""
    payload = {"id": "guest-1"} if auth_payload is None else auth_payload

    def handler(method: str, url: str) -> FakeResponse:
        if url.endswith("/v1/auth/me"):
            return FakeResponse(status_code=auth_status, payload=payload, text=auth_text)
        if url.endswith("/v2/chat/responses"):
            return FakeResponse(status_code=gen_status, lines=gen_lines, text=gen_text)
        return FakeResponse(status_code=200, payload={})

    return RecordingTransport(handler=handler)


@pytest.fixture()
def transport() -> RecordingTransport:
    return make_transport(gen_lines=sse([delta_frame("hi")]) + [b"data: [DONE]"])
