"""Layer 2 — Syntx AI FACADE. The only layer the gateway sees.

ProviderContext in, FacadeResult out — matches the canonical generate_text schema.
Zero raw exceptions cross this boundary.
"""

from __future__ import annotations

from typing import Any

from gateway.contracts import (
    ErrorCategory,
    FacadeResult,
    GatewayOperation,
    ProviderContext,
    Usage,
)
from gateway.errors import make_error
from providers.syntx._upstream import UpstreamReply, call_syntx_generation

_ALLOWED_PAYLOAD_KEYS = frozenset({"messages", "temperature", "max_tokens"})

_FINISH_REASON_MAP = {
    "stop": "stop",
    "length": "length",
    "content_filter": "filter",
}

_HTTP_STATUS_MAP: dict[int, ErrorCategory] = {
    401: ErrorCategory.INVALID_CREDENTIAL,
    403: ErrorCategory.INVALID_CREDENTIAL,
    404: ErrorCategory.MODEL_UNAVAILABLE,
    429: ErrorCategory.RATE_LIMITED,
    400: ErrorCategory.BAD_REQUEST,
    413: ErrorCategory.BAD_REQUEST,
    422: ErrorCategory.BAD_REQUEST,
    500: ErrorCategory.RETRYABLE_SERVER_ERROR,
    502: ErrorCategory.RETRYABLE_SERVER_ERROR,
    503: ErrorCategory.RETRYABLE_SERVER_ERROR,
    504: ErrorCategory.RETRYABLE_SERVER_ERROR,
}


def _validate_payload(payload: dict[str, Any]) -> FacadeResult | None:
    extras = set(payload) - _ALLOWED_PAYLOAD_KEYS
    if extras:
        return FacadeResult(
            succeeded=False,
            error=make_error(
                ErrorCategory.BAD_REQUEST,
                "payload carries keys outside the generate_text schema",
            ),
        )
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return FacadeResult(
            succeeded=False,
            error=make_error(ErrorCategory.BAD_REQUEST, "payload.messages is required"),
        )
    for item in messages:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("role"), str)
            or not isinstance(item.get("content"), str)
        ):
            return FacadeResult(
                succeeded=False,
                error=make_error(
                    ErrorCategory.BAD_REQUEST,
                    "payload.messages items must be {role: str, content: str}",
                ),
            )
    temperature = payload.get("temperature")
    if temperature is not None and not isinstance(temperature, int | float):
        return FacadeResult(
            succeeded=False,
            error=make_error(ErrorCategory.BAD_REQUEST, "payload.temperature must be a number"),
        )
    max_tokens = payload.get("max_tokens")
    if max_tokens is not None and not isinstance(max_tokens, int):
        return FacadeResult(
            succeeded=False,
            error=make_error(ErrorCategory.BAD_REQUEST, "payload.max_tokens must be an integer"),
        )
    return None


def _format_prompt(messages: list[dict[str, str]]) -> str:
    """Combines messages into a coherent prompt string."""
    if len(messages) == 1 and messages[0].get("role") == "user":
        return messages[0].get("content", "")
    lines = []
    for msg in messages:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _translate_failure(reply: UpstreamReply) -> FacadeResult:
    if reply.fail_kind in ("no_key", "pool_exhausted"):
        return FacadeResult(
            succeeded=False,
            error=make_error(
                ErrorCategory.PROVIDER_UNAVAILABLE,
                "syntx credential pool is exhausted or unavailable",
                provider_code="pool_exhausted",
                retryable=True,
            ),
        )
    if reply.fail_kind == "timeout":
        return FacadeResult(
            succeeded=False,
            error=make_error(ErrorCategory.TIMEOUT, "upstream call timed out"),
        )
    if reply.fail_kind == "network":
        return FacadeResult(
            succeeded=False,
            error=make_error(
                ErrorCategory.PROVIDER_UNAVAILABLE,
                "upstream is unreachable",
                retryable=True,
            ),
        )

    status = reply.http_status or 0
    category = _HTTP_STATUS_MAP.get(status, ErrorCategory.NON_RETRYABLE_ERROR)
    if (
        category is ErrorCategory.BAD_REQUEST
        and reply.error_code is not None
        and "content" in reply.error_code
    ):
        category = ErrorCategory.CONTENT_REJECTED

    return FacadeResult(
        succeeded=False,
        error=make_error(
            category,
            "upstream call failed",
            provider_code=reply.error_code or f"http_{status}",
            retry_after_ms=(
                reply.retry_after_ms if category is ErrorCategory.RATE_LIMITED else None
            ),
        ),
    )


async def generate_text(context: ProviderContext) -> FacadeResult:
    invalid = _validate_payload(context.payload)
    if invalid is not None:
        return invalid

    prompt = _format_prompt(context.payload["messages"])
    reply = await call_syntx_generation(
        model=context.model,
        prompt=prompt,
        timeout_ms=context.timeout_ms,
    )
    if not reply.ok:
        return _translate_failure(reply)

    finish = _FINISH_REASON_MAP.get(reply.finish_reason or "", "stop")
    return FacadeResult(
        succeeded=True,
        output={"text": reply.text, "finish_reason": finish},
        usage=Usage(
            input_tokens=reply.usage.get("prompt_tokens"),
            output_tokens=reply.usage.get("completion_tokens"),
            units=1,
        ),
    )


HANDLERS: dict[GatewayOperation, object] = {
    GatewayOperation.GENERATE_TEXT: generate_text,
}
