"""Injectable, bounded asynchronous HTTP transport; no retries or redirects."""

import asyncio
import json
import math
import re
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from ._config import BASE_API_URL
from ._privacy import private_async

_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_PATH = re.compile(
    r"(?:chats(?:/upload-files|/[0-9a-f-]{36}/messages)?|llm/(?:generate|limits)|user/balance)\Z"
)
_CODE_KINDS = {
    "modelNotAvailableForPlan": "model_unavailable",
    "token_expired": "auth_expired",
    "session_expired": "auth_expired",
    "quota_exceeded": "quota_exceeded",
    "insufficient_quota": "quota_exceeded",
    "content_rejected": "content_rejected",
    "content_policy_violation": "content_rejected",
}


class UpstreamFailure(Exception):
    def __init__(self, kind: str, *, status: int | None = None, retry_after_ms: int | None = None):
        super().__init__("provider request failed")
        self.kind = kind
        self.status = status
        self.retry_after_ms = retry_after_ms


@dataclass(frozen=True)
class Deadline:
    end: float

    @classmethod
    def after_ms(cls, timeout_ms: int) -> "Deadline":
        return cls(time.monotonic() + timeout_ms / 1000)

    def remaining(self) -> float:
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise UpstreamFailure("timeout")
        return remaining

    async def sleep(self, interval: float) -> None:
        await asyncio.sleep(min(max(interval, 0.001), self.remaining()))
        self.remaining()


def retry_delay(headers: httpx.Headers, detail: dict, default_seconds: float) -> int:
    candidates = [default_seconds]
    raw = headers.get("retry-after")
    if raw is not None:
        try:
            candidates.append(float(raw))
        except ValueError:
            try:
                candidates.append(parsedate_to_datetime(raw).timestamp() - time.time())
            except (ValueError, TypeError, OverflowError):
                pass
    value = detail.get("retry_after_seconds")
    if isinstance(value, int | float) and not isinstance(value, bool):
        candidates.append(value)
    valid = [value for value in candidates if 0 <= value <= 10**12]
    # Do not shorten upstream cooldowns. A conservative configured floor is safe.
    return math.ceil(max(valid, default=60.0) * 1000)


def http_failure(
    status: int, body: Any, headers: httpx.Headers, cooldown: float
) -> UpstreamFailure:
    detail = body.get("detail", body) if isinstance(body, dict) else {}
    detail = detail if isinstance(detail, dict) else {}
    code = detail.get("code", detail.get("error"))
    code = code.rsplit(".", 1)[-1] if isinstance(code, str) else ""
    kind = "non_retryable_error"
    if 500 <= status <= 599:
        kind = "retryable_server_error"
    elif 400 <= status <= 499:
        kind = _CODE_KINDS.get(code) or {
            400: "bad_request",
            401: "invalid_credential",
            403: "invalid_credential",
            404: "model_unavailable",
            413: "bad_request",
            422: "bad_request",
            429: "rate_limited",
        }.get(status, kind)
    return UpstreamFailure(
        kind,
        status=status,
        retry_after_ms=(retry_delay(headers, detail, cooldown) if kind == "rate_limited" else None),
    )


class Transport:
    def __init__(
        self,
        token: str,
        deadline: Deadline,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        cooldown: float = 60,
    ):
        self.deadline = deadline
        self.cooldown = cooldown
        self.client = httpx.AsyncClient(
            base_url=BASE_API_URL,
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )

    @private_async
    async def __aenter__(self) -> "Transport":
        await self.client.__aenter__()
        return self

    @private_async
    async def __aexit__(self, *args: Any) -> None:
        await self.client.__aexit__(*args)

    @private_async
    async def request(self, method: str, path: str, **kwargs: Any) -> dict:
        if not _PATH.fullmatch(path):
            raise UpstreamFailure("bad_request")
        try:
            async with asyncio.timeout(self.deadline.remaining()):
                async with self.client.stream(
                    method, path, timeout=self.deadline.remaining(), **kwargs
                ) as response:
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > _MAX_RESPONSE_BYTES:
                            raise UpstreamFailure("non_retryable_error")
                    try:
                        body = json.loads(content)
                    except (ValueError, UnicodeError, RecursionError):
                        body = None
                    if not 200 <= response.status_code <= 299:
                        raise http_failure(
                            response.status_code, body, response.headers, self.cooldown
                        )
                    if not isinstance(body, dict):
                        raise UpstreamFailure("non_retryable_error")
                    self.deadline.remaining()
                    return body
        except (TimeoutError, httpx.TimeoutException):
            raise UpstreamFailure("timeout") from None
        except httpx.RequestError:
            raise UpstreamFailure("provider_unavailable") from None
