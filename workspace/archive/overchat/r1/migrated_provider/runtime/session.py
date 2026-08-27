"""Guest identity / session resolution.

Migrated from source L195-207.

AUTH MODEL (established by source + live evidence, not assumed):
this provider sends NO credential at all. `GET /v1/auth/me` returns a freshly
auto-provisioned guest identity derived from the `x-device-*` headers, and its
`id` becomes the user id used to build the chat URLs. There is no login, token,
cookie, refresh, or API key anywhere in the source.

Live evidence: `GET /v1/auth/me` with only the device headers returned HTTP 200
with an `id` field and `firstName: "Demo"`/`lastName: "Account"`, confirming
guest auto-provisioning (redacted capture in
workspace/working/overchat/evidence/live_auth_me_shape.json).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from .errors import (
    ProviderError,
    classify_http_status,
    classify_transport_exception,
    is_success_status,
)

#: Fixed timeout used by the source for the auth call (L196) - deliberately
#: NOT cfg.timeout_seconds, which the source only applies to the stream call.
AUTH_TIMEOUT_SECONDS = 15

#: Source L195.
AUTH_PATH = "/v1/auth/me"


class Transport(Protocol):
    """Minimal transport surface (adaptation M3).

    Mirrors the `requests` functions the source calls, so the default
    implementation can pass arguments through unchanged.
    """

    def get(self, url: str, *, headers: dict[str, str], timeout: int) -> Any: ...

    def post(
        self,
        url: str,
        *,
        data: str,
        headers: dict[str, str],
        timeout: int,
        stream: bool = False,
    ) -> Any: ...

    def patch(self, url: str, *, data: str, headers: dict[str, str], timeout: int) -> Any: ...


@dataclass(frozen=True)
class ConversationIds:
    """The three uuid4 values minted per request (source L205-207)."""

    chat_uuid: str
    msg_id_1: str
    msg_id_2: str


def new_conversation_ids() -> ConversationIds:
    """Source L205-207: three independent `str(uuid.uuid4())` values."""
    return ConversationIds(
        chat_uuid=str(uuid.uuid4()),
        msg_id_1=str(uuid.uuid4()),
        msg_id_2=str(uuid.uuid4()),
    )


@dataclass(frozen=True)
class AuthResult:
    """Outcome of the auth step: exactly one of `user_id` / `error` is set."""

    user_id: str | None = None
    error: ProviderError | None = None

    @property
    def ok(self) -> bool:
        return self.user_id is not None


def resolve_user_id(
    transport: Transport,
    base_url: str,
    headers: dict[str, str],
) -> AuthResult:
    """Resolve the guest user id.

    Source L194-203, preserved exactly:
      * `GET {base_url}/v1/auth/me`
      * timeout 15 (hardcoded, not the config timeout)
      * success = status in [200, 201]
      * user id = `res.json().get("id")`  (may be None if absent)
      * non-success  -> source printed status + body[:150] and returned None
      * any exception -> source printed and returned None

    The only change is that the failure paths return a normalized ProviderError
    instead of printing (adaptation M7); the legacy layer converts that back to
    the source's `None` return so CLI behavior is unchanged.
    """
    url = f"{base_url}{AUTH_PATH}"
    try:
        response = transport.get(url, headers=headers, timeout=AUTH_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 - source catches bare Exception (L201)
        return AuthResult(error=classify_transport_exception(exc, stage="auth"))

    status = int(getattr(response, "status_code", 0))
    if not is_success_status(status):
        body = _safe_text(response)
        return AuthResult(error=classify_http_status(status, body=body, stage="auth"))

    try:
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - source's bare except covers this too
        return AuthResult(error=classify_transport_exception(exc, stage="auth"))

    # Source uses .get("id"), so a missing id yields None rather than raising.
    user_id = payload.get("id") if isinstance(payload, dict) else None
    if user_id is None:
        return AuthResult(
            error=classify_http_status(status, body="", stage="auth").__class__(
                category="bad_request",
                retryable=False,
                safe_message="Overchat auth response contained no user id.",
                provider_code=str(status),
                metadata={"stage": "auth"},
            )
        )
    return AuthResult(user_id=str(user_id))


def _safe_text(response: Any) -> str:
    """Read `response.text` defensively (the source reads it directly)."""
    try:
        return response.text or ""
    except Exception:  # noqa: BLE001
        return ""
