"""Overchat provider (migrated, V3-compliant).

```text
Provider key : overchat
Upstream     : https://api.overchat.ai
Source file  : 01.02_overchat_gpt5_2_gemini3_5_bypass.py  (403 lines)
Source sha256: d513c0359c8aada2801a3d847466cf2d0e865e33fd05f0d180c902187cbbc470
```

Declared capabilities: `text_generation`, `streaming`.
Activation: `disabled` / `integration_pending` (see `manifest.yaml`).

The Core-facing surface is `OverchatProvider`. Everything else exported here is
for provider-owned tests and the preserved CLI shell.

Provider identity note: the inbox folder was named `gemini--flash`, but that is
a MODEL hint. The upstream gateway is Overchat, serving three vendor models, so
the provider key is `overchat` per V3 §3 (Model != Provider != Account !=
Credential).
"""

from .config import DEFAULT_SYSTEM_PROMPT, OverchatConfig
from .health import DEGRADED, HEALTHY, UNAVAILABLE, HealthReport, check_health
from .provider import (
    DECLARED_CAPABILITIES,
    DECLARED_MODALITIES,
    DECLARED_OPERATIONS,
    PROVIDER_DISPLAY_NAME,
    PROVIDER_ID,
    UNSUPPORTED_CAPABILITIES,
    GenerateRequest,
    GenerateResponse,
    OverchatProvider,
)
from .runtime.errors import OverchatError, ProviderError

__all__ = [
    "DECLARED_CAPABILITIES",
    "DECLARED_MODALITIES",
    "DECLARED_OPERATIONS",
    "DEFAULT_SYSTEM_PROMPT",
    "DEGRADED",
    "GenerateRequest",
    "GenerateResponse",
    "HEALTHY",
    "HealthReport",
    "OverchatConfig",
    "OverchatError",
    "OverchatProvider",
    "PROVIDER_DISPLAY_NAME",
    "PROVIDER_ID",
    "ProviderError",
    "UNAVAILABLE",
    "UNSUPPORTED_CAPABILITIES",
    "check_health",
]
