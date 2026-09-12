"""Layer 2: strict canonical payloads and safe canonical results only."""

import math

from gateway.contracts import (
    CredentialMode,
    ErrorCategory,
    FacadeResult,
    GatewayOperation,
    ProviderContext,
    Usage,
)
from gateway.errors import make_error

from . import _upstream
from ._config import ProviderConfig
from ._images import decode_image
from ._transport import Deadline, UpstreamFailure


def _text_prompt(payload: dict) -> str:
    if set(payload) - {"messages", "temperature", "max_tokens"}:
        raise UpstreamFailure("bad_request")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise UpstreamFailure("bad_request")
    for message in messages:
        if (
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or not isinstance(message["role"], str)
            or not isinstance(message["content"], str)
        ):
            raise UpstreamFailure("bad_request")
    temperature = payload.get("temperature")
    if temperature is not None:
        if type(temperature) not in (int, float):
            raise UpstreamFailure("bad_request")
        try:
            finite = math.isfinite(temperature)
        except OverflowError:
            finite = False
        if not finite:
            raise UpstreamFailure("bad_request")
    if payload.get("max_tokens") is not None and type(payload["max_tokens"]) is not int:
        raise UpstreamFailure("bad_request")
    # Original API accepts one text string, not structured history. Render each
    # role/content exactly once, with the final message in the current section.
    history = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages[:-1])
    last = messages[-1]
    current = f"{last['role']}: {last['content']}"
    return (
        f"Previous conversation:\n{history}\n\nCurrent request:\n{current}" if history else current
    )


def _failure(exc: UpstreamFailure) -> FacadeResult:
    try:
        category = ErrorCategory(exc.kind)
    except ValueError:
        category = ErrorCategory.NON_RETRYABLE_ERROR
    return FacadeResult(
        succeeded=False,
        error=make_error(
            category,
            "provider request failed",
            provider_code=str(exc.status) if exc.status is not None else None,
            retry_after_ms=exc.retry_after_ms if category is ErrorCategory.RATE_LIMITED else None,
        ),
    )


async def _execute(context: ProviderContext, operation: GatewayOperation) -> FacadeResult:
    deadline = Deadline.after_ms(context.timeout_ms)
    try:
        if context.operation is not operation:
            raise UpstreamFailure("unsupported_capability")
        if (
            context.credential_mode is not CredentialMode.PLATFORM
            or context.credential_value is not None
        ):
            raise UpstreamFailure("invalid_credential")
        image = None
        if operation is GatewayOperation.GENERATE_TEXT:
            prompt = _text_prompt(context.payload)
        else:
            if set(context.payload) != {"image_b64", "image_format", "instruction"}:
                raise UpstreamFailure("bad_request")
            prompt = context.payload["instruction"]
            if not isinstance(prompt, str):
                raise UpstreamFailure("bad_request")
            image = decode_image(
                context.payload["image_b64"], context.payload["image_format"], ProviderConfig()
            )
        deadline.remaining()
        reply = await _upstream.generate(
            model=context.model,
            text=prompt,
            timeout_ms=context.timeout_ms,
            deadline=deadline,
            image=image,
        )
        output = {"text": reply.text}
        if operation is GatewayOperation.GENERATE_TEXT:
            output["finish_reason"] = reply.finish_reason
        return FacadeResult(
            succeeded=True,
            output=output,
            usage=Usage(
                input_tokens=reply.input_tokens, output_tokens=reply.output_tokens, units=1
            ),
        )
    except UpstreamFailure as exc:
        return _failure(exc)
    except Exception:
        # Unexpected bugs never expose exception repr, credentials or paths.
        # CancelledError is a BaseException and deliberately propagates.
        return _failure(UpstreamFailure("non_retryable_error"))


async def generate_text(context: ProviderContext) -> FacadeResult:
    return await _execute(context, GatewayOperation.GENERATE_TEXT)


async def analyze_vision(context: ProviderContext) -> FacadeResult:
    return await _execute(context, GatewayOperation.ANALYZE_VISION)


HANDLERS = {
    GatewayOperation.GENERATE_TEXT: generate_text,
    GatewayOperation.ANALYZE_VISION: analyze_vision,
}
