#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏗️ Scaffold Generator — يولّد هيكل مزود جديد مطابق لـ TOOLKIT v2.1 ودستور بولا v1.2
الاستخدام:  python tools/scaffold_provider.py <slug> [--display "Name"] [--lab]
"""
import sys
import json
import time
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ROOT / "providers"
LAB = ROOT.parent / ".AAA_GGG_iii_VIBE_CODING"

CORE = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""{disp} — _core.py | ثلاثية الدوال الموحدة (TOOLKIT v2.1)"""
import json
import time
from typing import Generator
from curl_cffi import requests as cffi

IMPERSONATE_TARGET = "chrome120"
TIMEOUT_SECONDS = 60
BASE_URL = "https://CHANGE_ME.example"


class UpstreamFailure(Exception):
    def __init__(self, category: str, message: str, retry_after_ms: int | None = None, provider_code: str | None = None):
        super().__init__(message)
        self.category = category
        self.message = message
        self.retry_after_ms = retry_after_ms
        self.provider_code = provider_code


def _translate_upstream_failure(status: int, body: str = "") -> UpstreamFailure:
    try:
        from gateway.errors import classify_http_status
        category = classify_http_status(status, body).value
    except Exception:
        category = "retryable_server_error" if status in (500, 502, 503) else "non_retryable_error"
    return UpstreamFailure(category, f"{disp} upstream {{status}}", provider_code=str(status))


# ─── الثلاثية الموحدة (The Universal Lab Trinity) ────────────────────────────
def register_account(session: cffi.Session | None = None) -> dict:
    sess = session or cffi.Session(impersonate=IMPERSONATE_TARGET)
    raise NotImplementedError("TODO: منطق التسجيل أو جلب الجلسة المبدئية")


def refresh_session(account_info: dict) -> dict:
    account_info["last_refreshed"] = time.time()
    return account_info


def execute_chat(prompt: str, session_data: dict, model: str = "default",
                 stream: bool = True) -> str:
    return "".join(stream_text(prompt, session_data, model))


# ─── واجهات الجيتواي (Gateway Interfaces) ────────────────────────────────────
def generate_text(prompt: str, session_data: dict, model: str = "default") -> str:
    return execute_chat(prompt, session_data, model, stream=False)


def stream_text(prompt: str, session_data: dict,
                model: str = "default") -> Generator[str, None, None]:
    raise NotImplementedError("TODO: منطق البث SSE الآمن")
'''

ADAPTER = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""{disp} — adapter.py | تحويل نواتج _core إلى FacadeResult مع عزل تام للمعلومات السرية"""
from __future__ import annotations

import asyncio
from typing import Any

from gateway.contracts import (
    CredentialMode,
    ErrorCategory,
    FacadeResult,
    GatewayOperation,
    ProviderContext,
    Usage,
)
from gateway.errors import make_error
from providers.{slug} import _core


_SAFE_MESSAGES: dict[ErrorCategory, str] = {{
    ErrorCategory.AUTH_EXPIRED: "upstream authentication expired",
    ErrorCategory.INVALID_CREDENTIAL: "upstream credential invalid",
    ErrorCategory.RATE_LIMITED: "upstream rate limit reached",
    ErrorCategory.QUOTA_EXCEEDED: "upstream quota exceeded",
    ErrorCategory.MODEL_UNAVAILABLE: "upstream model unavailable",
    ErrorCategory.PROVIDER_UNAVAILABLE: "upstream provider unavailable",
    ErrorCategory.UNSUPPORTED_CAPABILITY: "unsupported capability",
    ErrorCategory.BAD_REQUEST: "bad request payload",
    ErrorCategory.CONTENT_REJECTED: "content rejected by upstream policy",
    ErrorCategory.TIMEOUT: "upstream call timed out",
    ErrorCategory.RETRYABLE_SERVER_ERROR: "upstream server error",
    ErrorCategory.NON_RETRYABLE_ERROR: "upstream call failed",
}}


def _translate_upstream_failure(exc: _core.UpstreamFailure) -> FacadeResult:
    """Translate Layer 1 failure shape into canonical wire error."""
    try:
        category = ErrorCategory(exc.category)
    except ValueError:
        category = ErrorCategory.NON_RETRYABLE_ERROR

    safe_msg = _SAFE_MESSAGES.get(category, "upstream call failed")
    return FacadeResult(
        succeeded=False,
        error=make_error(
            category,
            safe_msg,
            retry_after_ms=exc.retry_after_ms if category is ErrorCategory.RATE_LIMITED else None,
            provider_code=exc.provider_code,
        ),
    )


async def generate_text(context: ProviderContext) -> FacadeResult:
    """generate_text facade handler for {disp}."""
    if context.operation != GatewayOperation.GENERATE_TEXT:
        return FacadeResult(
            succeeded=False,
            error=make_error(
                ErrorCategory.UNSUPPORTED_CAPABILITY,
                f"Handler generate_text cannot serve operation {{context.operation!r}}",
            ),
        )

    model = context.model or "default"
    messages = context.payload.get("messages", [])
    prompt = messages[-1].get("content", "") if messages else context.payload.get("prompt", "")

    try:
        text = await asyncio.to_thread(_core.generate_text, prompt, {{}}, model)
        return FacadeResult(
            succeeded=True,
            output={{"text": text}},
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )
    except _core.UpstreamFailure as exc:
        return _translate_upstream_failure(exc)
    except Exception as exc:
        return FacadeResult(
            succeeded=False,
            error=make_error(ErrorCategory.RETRYABLE_SERVER_ERROR, "upstream communication failure"),
        )
'''

DEFINITION = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""{disp} — definition.py | البطاقة الرسمية للمزود في بوابة الجيتواي"""
from __future__ import annotations

import json
from pathlib import Path

_METADATA_PATH = Path(__file__).resolve().parent / "models_metadata.json"

try:
    with open(_METADATA_PATH, "r", encoding="utf-8") as _f:
        _MODELS_DATA: dict[str, dict] = json.load(_f)
except Exception:
    _MODELS_DATA = {{}}

_DECLARED_MODELS: list[dict[str, object]] = [
    {{"name": m_id}} for m_id in _MODELS_DATA
]

DEFINITION: dict[str, object] = {{
    "display_name": "{disp}",
    "definition_version": "1.0.0",
    "credential_mode": "platform",
    "capabilities": {{
        "chat": True,
        "vision_input": False,
        "audio_input": False,
        "file_upload": False,
        "reasoning": True,
        "code": True,
    }},
    "operations": [
        "generate_text",
    ],
    "models": _DECLARED_MODELS,
    "health_supported": True,
}}
'''

META = {
    "default": {
        "label": "Default Model",
        "context_window": 8192,
        "max_output_tokens": 4096,
        "capabilities": {
            "thinking": False,
            "planning": False,
            "deep_research": False,
            "streaming": True,
        },
    }
}

LAB = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 {disp} — Universal Lab Test Script (TOOLKIT v2.1)"""
import sys
import time
from curl_cffi import requests as cffi

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

IMPERSONATE_TARGET = "chrome120"
TIMEOUT_SECONDS = 60


def register_account(session=None) -> dict:
    sess = session or cffi.Session(impersonate=IMPERSONATE_TARGET)
    return {{"status": "active", "session": sess}}


def refresh_session(account_info: dict) -> dict:
    account_info["last_refreshed"] = time.time()
    return account_info


def execute_chat(prompt: str, session_data: dict, model: str = "default", stream: bool = True) -> str:
    return ""


if __name__ == "__main__":
    print("🚀 [1/3] تسجيل الحساب...");  acc = register_account()
    print("🚀 [2/3] فحص الجلسة...");    acc = refresh_session(acc)
    print("🚀 [3/3] اختبار الشات...")
    print("\\n💬 الرد:", execute_chat("مرحبا! من أنت؟", acc))
'''


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        print(f"  ⏭️  موجود مسبقاً: {p.name}")
        return
    p.write_text(content, encoding="utf-8")
    print(f"  ✅ {p.relative_to(ROOT.parent)}")


def main():
    ap = argparse.ArgumentParser(description="Scaffold a new provider following Bolla Constitution and Toolkit v2.1")
    ap.add_argument("slug", help="Slug identifier for the provider (e.g., blackbox, perplexity)")
    ap.add_argument("--display", default=None, help="Display name for the provider (e.g., 'BlackBox AI')")
    ap.add_argument("--lab", action="store_true", help="Also generate the standalone lab script in .AAA_GGG_iii_VIBE_CODING")
    a = ap.parse_args()

    slug = a.slug.strip().lower().replace(" ", "-")
    disp = a.display or slug.replace("-", " ").title()
    d = PROVIDERS / slug

    print(f"\n🏗️  توليد هيكل المزود: {slug}  ({disp})\n")
    write(d / "__init__.py", 'from .definition import DEFINITION  # noqa\n')
    write(d / "_core.py", CORE.format(slug=slug, disp=disp))
    write(d / "adapter.py", ADAPTER.format(slug=slug, disp=disp))
    write(d / "definition.py", DEFINITION.format(slug=slug, disp=disp))
    write(d / "models_metadata.json",
          json.dumps(META, ensure_ascii=False, indent=2) + "\n")

    if a.lab:
        lab_file = LAB / slug / f"{slug}_lab.py"
        write(lab_file, LAB.format(disp=disp))

    print(f"\n✅ تم بنجاح. الخطوة التالية: املأ BASE_URL و register_account في _core.py\n")


if __name__ == "__main__":
    main()
