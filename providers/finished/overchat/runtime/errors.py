"""Provider error normalization.

CLASSIFICATION: SANITIZED (adapter-added, additive).

The source performs NO error normalization. It prints a raw message and returns
`None` (source L198-199, L288, L319-320, L322-324). V3
`30_PROVIDER_ARCHITECTURE_AND_PLUGIN_SPEC.md` §14 requires every provider to
normalize errors into common categories, so this module is added at the
boundary only.

It is strictly additive:
  * it never changes which requests succeed or fail;
  * the source's "return None" outcome is still what the legacy CLI layer sees;
  * the raw provider status/body truncations (150/250 chars) are preserved.

No error category here is invented beyond what the source or V3 §14 defines:
categories come from V3 §14's fixed list, and only statuses the source can
actually encounter are mapped. Statuses the source never distinguishes map to
the generic retryable/non-retryable buckets rather than to guessed semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# V3 §14 normalized categories (fixed vocabulary; not invented here).
CATEGORY_AUTH_EXPIRED = "auth_expired"
CATEGORY_INVALID_CREDENTIAL = "invalid_credential"
CATEGORY_RATE_LIMITED = "rate_limited"
CATEGORY_QUOTA_EXCEEDED = "quota_exceeded"
CATEGORY_MODEL_UNAVAILABLE = "model_unavailable"
CATEGORY_PROVIDER_UNAVAILABLE = "provider_unavailable"
CATEGORY_UNSUPPORTED_CAPABILITY = "unsupported_capability"
CATEGORY_BAD_REQUEST = "bad_request"
CATEGORY_CONTENT_REJECTED = "content_rejected"
CATEGORY_TIMEOUT = "timeout"
CATEGORY_RETRYABLE_SERVER_ERROR = "retryable_server_error"
CATEGORY_NON_RETRYABLE_ERROR = "non_retryable_error"

#: Truncation limits preserved from source: auth L198 uses 150, generation
#: L319 uses 250.
AUTH_BODY_TRUNCATION = 150
GENERATION_BODY_TRUNCATION = 250

#: Statuses the source treats as success (L197, L271).
SUCCESS_STATUSES = (200, 201)


@dataclass(frozen=True)
class ProviderError:
    """Normalized provider error (V3 §14 required shape)."""

    category: str
    retryable: bool
    safe_message: str
    provider_code: str | None = None
    retry_after_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "retryable": self.retryable,
            "retry_after_ms": self.retry_after_ms,
            "provider_code": self.provider_code,
            "safe_message": self.safe_message,
        }


class OverchatError(Exception):
    """Raised only at the V3 adapter boundary; carries a normalized error."""

    def __init__(self, error: ProviderError) -> None:
        super().__init__(error.safe_message)
        self.error = error


def is_success_status(status_code: int) -> bool:
    """Source acceptance rule: exactly 200 or 201 (L197, L271)."""
    return status_code in SUCCESS_STATUSES


def classify_http_status(
    status_code: int,
    *,
    body: str = "",
    stage: str = "generation",
    retry_after_ms: int | None = None,
) -> ProviderError:
    """Map an upstream HTTP status onto a V3 §14 category.

    `stage` selects the source's body-truncation length so the raw evidence
    matches what the original script would have shown.
    """
    limit = AUTH_BODY_TRUNCATION if stage == "auth" else GENERATION_BODY_TRUNCATION
    truncated = (body or "")[:limit]

    if status_code == 401:
        category, retryable = CATEGORY_AUTH_EXPIRED, False
    elif status_code == 403:
        category, retryable = CATEGORY_INVALID_CREDENTIAL, False
    elif status_code == 429:
        category, retryable = CATEGORY_RATE_LIMITED, True
    elif status_code == 402:
        category, retryable = CATEGORY_QUOTA_EXCEEDED, False
    elif status_code == 404:
        category, retryable = CATEGORY_MODEL_UNAVAILABLE, False
    elif status_code == 400:
        category, retryable = CATEGORY_BAD_REQUEST, False
    elif status_code == 408:
        category, retryable = CATEGORY_TIMEOUT, True
    elif status_code in (502, 503, 504):
        category, retryable = CATEGORY_PROVIDER_UNAVAILABLE, True
    elif 500 <= status_code < 600:
        category, retryable = CATEGORY_RETRYABLE_SERVER_ERROR, True
    else:
        category, retryable = CATEGORY_NON_RETRYABLE_ERROR, False

    return ProviderError(
        category=category,
        retryable=retryable,
        safe_message=f"Overchat {stage} request failed with status {status_code}.",
        provider_code=str(status_code),
        retry_after_ms=retry_after_ms,
        metadata={"stage": stage, "raw_body_truncated": truncated},
    )


def classify_transport_exception(exc: BaseException, *, stage: str = "generation") -> ProviderError:
    """Map a transport-level exception.

    The source catches bare `Exception` at L201 and L322 and returns None. The
    category chosen here mirrors that "could not reach provider" meaning; the
    exception type name is kept as provider_code, and the exception message is
    NOT copied into safe_message (it can contain URLs/hosts).
    """
    name = type(exc).__name__
    lowered = name.lower()
    if "timeout" in lowered:
        category, retryable = CATEGORY_TIMEOUT, True
    else:
        category, retryable = CATEGORY_PROVIDER_UNAVAILABLE, True
    return ProviderError(
        category=category,
        retryable=retryable,
        safe_message=f"Overchat {stage} transport failure.",
        provider_code=name,
        metadata={"stage": stage},
    )


def unsupported_capability(capability: str) -> ProviderError:
    """V3 §5: a provider must reject operations it does not declare."""
    return ProviderError(
        category=CATEGORY_UNSUPPORTED_CAPABILITY,
        retryable=False,
        safe_message=f"Overchat does not support capability '{capability}'.",
        provider_code=None,
        metadata={"capability": capability},
    )
