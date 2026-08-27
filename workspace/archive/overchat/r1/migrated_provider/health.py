"""Provider health check.

CLASSIFICATION: SANITIZED (adapter-added).

The source has NO health check. V3 `30_PROVIDER_ARCHITECTURE_AND_PLUGIN_SPEC.md`
§4.1 and §11 require every provider to expose a health contract, so this module
is added at the boundary.

It invents no new upstream behavior: it reuses ONLY the existing guest-auth
call (`GET /v1/auth/me`, capability #7), which is read-only and is already the
first step of every generation request. No new endpoint is contacted.

Provider health is deliberately kept separate from account health (V3 §11):
this provider has no accounts, so only provider-level status is reported.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import OverchatConfig
from .runtime.errors import (
    CATEGORY_PROVIDER_UNAVAILABLE,
    CATEGORY_RATE_LIMITED,
    ProviderError,
)
from .runtime.headers import build_mobile_headers
from .runtime.session import Transport, resolve_user_id

#: V3 §11 provider-wide states.
HEALTHY = "healthy"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class HealthReport:
    """Normalized provider health result."""

    provider_id: str
    status: str
    message: str | None = None
    error: ProviderError | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "status": self.status,
            "message": self.message,
        }


def check_health(
    transport: Transport,
    config: OverchatConfig | None = None,
    *,
    provider_id: str = "overchat",
) -> HealthReport:
    """Probe provider availability using the read-only guest-auth endpoint.

    Mapping rationale (V3 §11 / §13.2):
      * auth succeeds and yields an id     -> HEALTHY
      * rate limited                       -> DEGRADED (provider is up, throttling)
      * provider unavailable / 5xx / net   -> UNAVAILABLE
      * anything else                      -> DEGRADED (reachable, not usable)
    """
    cfg = OverchatConfig() if config is None else config
    headers, _uuid, _ip = build_mobile_headers(
        include_ip_spoof_headers=cfg.include_ip_spoof_headers,
    )
    result = resolve_user_id(transport, cfg.base_url, headers)

    if result.ok:
        return HealthReport(
            provider_id=provider_id,
            status=HEALTHY,
            message="Guest identity resolved.",
        )

    error = result.error
    assert error is not None

    if error.category == CATEGORY_RATE_LIMITED:
        status = DEGRADED
    elif error.category == CATEGORY_PROVIDER_UNAVAILABLE:
        status = UNAVAILABLE
    else:
        status = DEGRADED

    return HealthReport(
        provider_id=provider_id,
        status=status,
        message=error.safe_message,
        error=error,
    )
