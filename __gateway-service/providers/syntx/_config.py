"""Private immutable settings. Importing this module creates no runtime state."""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

PROVIDER_DIR = Path(__file__).resolve().parent
BASE_API_URL = "https://api.syntx.ai/api/v1/"
MODEL_AI_NAMES = MappingProxyType(
    {
        "gpt-5.6-terra": "chatgpt",
        "claude-opus-4-8": "claude",
        "claude-sonnet-5": "claude",
        "grok-4.6": "grok",
    }
)
TOOLS = ("search", "code", "shell", "files", "charts")


@dataclass(frozen=True)
class ProviderConfig:
    """Defaults are self-contained; state_dir is explicitly injectable for tests.

    No paths or credentials are read from caller payloads or environment variables.
    Limits are local resource budgets, not claims about upstream service limits.
    """

    state_dir: Path = PROVIDER_DIR
    thinking: bool = True
    plan: bool = True
    deep_research: bool = True
    enable_tools: bool = True
    poll_interval: float = 1.2
    cooldown_seconds: float = 60.0
    max_image_bytes: int = 10 * 1024 * 1024
    maintenance_enabled: bool = True
    maintenance_threshold: int = 5
    maintenance_max_accounts: int = 5
    maintenance_interval: float = 60.0
    maintenance_timeout_ms: int = 30_000

    @property
    def accounts_file(self) -> Path:
        return self.state_dir / "accounts_syntx.json"

    @property
    def incoming_accounts_file(self) -> Path:
        return self.state_dir / "accounts_new.json"

    @property
    def maintenance_lock_file(self) -> Path:
        return self.state_dir / "maintenance.lock"

    def generation_settings(self) -> dict[str, object]:
        return {
            "thinking": self.thinking,
            "plan": self.plan,
            "deep_research": self.deep_research,
            "tools": list(TOOLS) if self.enable_tools else [],
        }
