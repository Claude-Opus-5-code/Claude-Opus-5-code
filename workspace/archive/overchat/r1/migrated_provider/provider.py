"""V3 provider adapter - the normalized boundary.

This is the ONLY module the Core is expected to touch. Per V3
`30_PROVIDER_ARCHITECTURE_AND_PLUGIN_SPEC.md` §20 (and README §20), the adapter
is a BOUNDARY, not a rewrite: it wraps the migrated provider behavior and
exposes the normalized contract. All provider-specific mechanics (headers,
cookies-less guest auth, SSE parsing, URL shapes, the `authorization:
undefined` quirk) stay behind this line.

Declared capabilities are exactly what the source implements: text generation
and streaming. Everything else is rejected with `unsupported_capability`
(V3 §5), never silently ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

from .config import OverchatConfig
from .discovery.models import (
    AVAILABLE_MODELS,
    DISCOVERY_MODE,
    list_models,
    resolve_model,
)
from .health import HealthReport, check_health
from .operations.text_generation import GenerationResult, generate_text, stream_text
from .runtime.errors import OverchatError, ProviderError, unsupported_capability
from .runtime.session import Transport

PROVIDER_ID = "overchat"
PROVIDER_DISPLAY_NAME = "Overchat"

#: Capabilities the source actually implements (V3 CapabilityId values).
DECLARED_CAPABILITIES: frozenset[str] = frozenset({"text_generation", "streaming"})

#: Modalities: text in, text out. Nothing else exists in the source.
DECLARED_MODALITIES: frozenset[str] = frozenset({"text"})

#: Operations implemented, per V3 §5.
DECLARED_OPERATIONS: frozenset[str] = frozenset({"generate_text"})

#: Capabilities explicitly NOT supported (source evidence: absent).
UNSUPPORTED_CAPABILITIES: frozenset[str] = frozenset(
    {
        "vision_input",
        "image_generation",
        "audio_stt",
        "audio_tts",
        "embeddings",
        "rerank",
        "moderation",
        "file_upload",
        "provider_agent",
    }
)


@dataclass(frozen=True)
class GenerateRequest:
    """Normalized generation request."""

    prompt: str
    model: str | None = None
    stream: bool = False


@dataclass(frozen=True)
class GenerateResponse:
    """Normalized generation response."""

    text: str
    model: str
    provider_id: str = PROVIDER_ID
    stream_errors: tuple[Any, ...] = ()


class OverchatProvider:
    """Normalized provider adapter (V3 §8.1 required interface)."""

    provider_id = PROVIDER_ID
    display_name = PROVIDER_DISPLAY_NAME

    def __init__(
        self,
        transport: Transport,
        config: OverchatConfig | None = None,
    ) -> None:
        self._transport = transport
        self._config = OverchatConfig() if config is None else config

    # ---- identity / declaration ----------------------------------------

    def get_capabilities(self) -> frozenset[str]:
        """V3 §8.1 `getCapabilities`."""
        return DECLARED_CAPABILITIES

    def supports(self, capability: str) -> bool:
        return capability in DECLARED_CAPABILITIES

    def get_manifest_summary(self) -> dict[str, Any]:
        """Runtime view of the manifest's behavioral claims."""
        return {
            "id": PROVIDER_ID,
            "name": PROVIDER_DISPLAY_NAME,
            "capabilities": sorted(DECLARED_CAPABILITIES),
            "modalities": sorted(DECLARED_MODALITIES),
            "operations": sorted(DECLARED_OPERATIONS),
            "models_discovery": DISCOVERY_MODE,
            "static_models": [m["model"] for m in list_models()],
            "auth_types": ["none_guest_device"],
            "account_pool_supported": False,
            "streaming": True,
        }

    # ---- credentials ----------------------------------------------------

    def validate_credential(self, credential_ref: str | None = None) -> HealthReport:
        """V3 §8.1 `validateCredential`.

        This provider takes NO credential: identity is a throwaway guest minted
        from device headers (source L191-203). A credential_ref is therefore
        neither required nor used; validation degenerates to a reachability
        probe. This is reported honestly rather than pretending to validate a
        secret that does not exist.
        """
        return check_health(self._transport, self._config, provider_id=PROVIDER_ID)

    # ---- discovery ------------------------------------------------------

    def discover_models(self) -> list[dict[str, str]]:
        """V3 §8.1 `discoverModels`.

        Discovery is STATIC: the source has no model-list endpoint, so this
        returns the source's own 3-entry table and never contacts the network.
        """
        return list_models()

    def model_bindings(self) -> list[dict[str, Any]]:
        """Provider→model bindings for the registry (V3 §3)."""
        return [
            {
                "provider_id": PROVIDER_ID,
                "model_id": persona_id,
                "provider_model_name": meta["model"],
                "capabilities": sorted(DECLARED_CAPABILITIES),
            }
            for persona_id, meta in AVAILABLE_MODELS.items()
        ]

    # ---- health ---------------------------------------------------------

    def health_check(self) -> HealthReport:
        """V3 §8.1 `healthCheck`."""
        return check_health(self._transport, self._config, provider_id=PROVIDER_ID)

    # ---- errors ---------------------------------------------------------

    def normalize_error(self, error: object) -> ProviderError:
        """V3 §8.1 `normalizeError`."""
        if isinstance(error, OverchatError):
            return error.error
        if isinstance(error, ProviderError):
            return error
        from .runtime.errors import classify_transport_exception

        if isinstance(error, BaseException):
            return classify_transport_exception(error)
        return ProviderError(
            category="non_retryable_error",
            retryable=False,
            safe_message="Unrecognized provider error.",
        )

    # ---- operations -----------------------------------------------------

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        """V3 §8.1 `generate` - normalized entry point.

        Dispatches to the only declared operation (`generate_text`). Raises
        `OverchatError` carrying a normalized error on failure; the Core never
        sees a raw provider exception or HTTP status.
        """
        config = self._config_for(request)
        result: GenerationResult = generate_text(request.prompt, config, self._transport)
        if not result.ok:
            assert result.error is not None
            raise OverchatError(result.error)
        return GenerateResponse(
            text=result.text,
            model=config.model,
            stream_errors=tuple(result.stream_errors),
        )

    def generate_stream(self, request: GenerateRequest) -> Iterator[str]:
        """Streaming generation (declared `streaming` capability)."""
        config = self._config_for(request)
        return stream_text(request.prompt, config, self._transport)

    def run_operation(self, operation: str, request: GenerateRequest) -> GenerateResponse:
        """Explicit operation dispatch with V3 §5 rejection of undeclared ops."""
        if operation not in DECLARED_OPERATIONS:
            raise OverchatError(unsupported_capability(operation))
        return self.generate(request)

    # ---- unsupported capability guards ---------------------------------

    def generate_image(self, *_args: Any, **_kwargs: Any) -> None:
        raise OverchatError(unsupported_capability("image_generation"))

    def analyze_vision(self, *_args: Any, **_kwargs: Any) -> None:
        raise OverchatError(unsupported_capability("vision_input"))

    def create_embeddings(self, *_args: Any, **_kwargs: Any) -> None:
        raise OverchatError(unsupported_capability("embeddings"))

    def transcribe_audio(self, *_args: Any, **_kwargs: Any) -> None:
        raise OverchatError(unsupported_capability("audio_stt"))

    def synthesize_speech(self, *_args: Any, **_kwargs: Any) -> None:
        raise OverchatError(unsupported_capability("audio_tts"))

    def rerank_documents(self, *_args: Any, **_kwargs: Any) -> None:
        raise OverchatError(unsupported_capability("rerank"))

    def moderate_content(self, *_args: Any, **_kwargs: Any) -> None:
        raise OverchatError(unsupported_capability("moderation"))

    def upload_asset(self, *_args: Any, **_kwargs: Any) -> None:
        raise OverchatError(unsupported_capability("file_upload"))

    def run_provider_agent(self, *_args: Any, **_kwargs: Any) -> None:
        raise OverchatError(unsupported_capability("provider_agent"))

    # ---- internals ------------------------------------------------------

    def _config_for(self, request: GenerateRequest) -> OverchatConfig:
        """Apply a per-request model override using source resolution rules."""
        if not request.model:
            return self._config
        persona_id, model = resolve_model(request.model)
        return self._config.with_values(persona_id=persona_id, model=model)
