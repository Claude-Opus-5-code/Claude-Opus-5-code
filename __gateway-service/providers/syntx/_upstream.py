"""Layer 1 — Syntx AI upstream client and Enterprise Credential Pool.

Internal territory; nothing here crosses to the platform.
Real HTTP calls to Syntx AI via httpx with FileLock concurrency and Cooldown management.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

try:
    from filelock import FileLock
except ImportError:
    # Fallback for environments where filelock is not installed
    class FileLock:  # type: ignore[no-redef]
        def __init__(self, lock_file: str, timeout: float = 10.0) -> None:
            pass
        def __enter__(self) -> FileLock:
            return self
        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass


SYNTX_BASE_URL = "https://api.syntx.ai/api/v1"
API_KEY_ENV = "GW_SYNTX_API_KEY"
ACCOUNTS_FILE_ENV = "GW_SYNTX_ACCOUNTS_FILE"
DEFAULT_ACCOUNTS_FILE = "accounts_syntx.json"

_MODEL_AI_NAME_MAP: dict[str, str] = {
    "claude-opus-4-8": "claude",
    "gpt-5.6-terra": "chatgpt",
    "claude-sonnet-5": "claude",
    "grok-4.6": "grok",
}

_default_transport: httpx.AsyncBaseTransport | None = None
_DEFAULT_COOLDOWN_SECONDS = 21526  # 6 hours as proven in live HAR


@dataclass(frozen=True)
class UpstreamReply:
    """Internal reply shape (Layer 1) — the facade translates it."""

    ok: bool
    text: str = ""
    finish_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    fail_kind: str | None = None  # "no_key" | "timeout" | "network" | "http" | "pool_exhausted"
    http_status: int | None = None
    error_code: str | None = None
    retry_after_ms: int | None = None


def get_accounts_file_path() -> pathlib.Path:
    configured = os.environ.get(ACCOUNTS_FILE_ENV)
    if configured:
        return pathlib.Path(configured)
    return pathlib.Path(DEFAULT_ACCOUNTS_FILE)


def _load_accounts(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return []
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_accounts(accounts: list[dict[str, Any]], path: pathlib.Path) -> None:
    tmp_path = path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        tmp_path.replace(path)
    except Exception:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(accounts, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def acquire_account() -> dict[str, Any] | None:
    """Acquires a valid active account. Respects cooldown and single static key."""
    static_key = os.environ.get(API_KEY_ENV)
    if static_key:
        return {
            "id": "static_platform_key",
            "token": static_key,
            "chat_uuid": os.environ.get("GW_SYNTX_CHAT_UUID", "07d713b3-d876-465e-8d8c-970ec1ef3cdb"),
            "status": "active",
        }

    path = get_accounts_file_path()
    lock_file = str(path) + ".lock"
    with FileLock(lock_file, timeout=10.0):
        accounts = _load_accounts(path)
        if not accounts:
            return None

        now_iso = datetime.now(timezone.utc).isoformat()
        now_ts = time.time()
        updated = False

        for acc in accounts:
            if acc.get("status") == "cooldown":
                cooldown_until = acc.get("cooldown_until")
                if cooldown_until:
                    try:
                        dt = datetime.fromisoformat(cooldown_until)
                        if dt.timestamp() <= now_ts:
                            acc["status"] = "active"
                            acc["cooldown_until"] = None
                            updated = True
                    except Exception:
                        acc["status"] = "active"
                        acc["cooldown_until"] = None
                        updated = True

        chosen: dict[str, Any] | None = None
        for acc in accounts:
            if acc.get("status") == "active" and acc.get("token"):
                chosen = acc
                acc["last_used_at"] = now_iso
                updated = True
                break

        if updated:
            _save_accounts(accounts, path)

        return chosen


def update_account_status(token: str, status: str, cooldown_seconds: int | None = None) -> None:
    """Updates account status to cooldown or expired."""
    static_key = os.environ.get(API_KEY_ENV)
    if static_key and token == static_key:
        return

    path = get_accounts_file_path()
    lock_file = str(path) + ".lock"
    with FileLock(lock_file, timeout=10.0):
        accounts = _load_accounts(path)
        updated = False
        now_ts = time.time()
        for acc in accounts:
            if acc.get("token") == token:
                acc["status"] = status
                if status == "cooldown":
                    duration = cooldown_seconds or _DEFAULT_COOLDOWN_SECONDS
                    expiry_dt = datetime.fromtimestamp(now_ts + duration, timezone.utc)
                    acc["cooldown_until"] = expiry_dt.isoformat()
                elif status == "expired":
                    acc["cooldown_until"] = None
                updated = True
                break
        if updated:
            _save_accounts(accounts, path)


def _safe_error_code(response: httpx.Response) -> str | None:
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            detail = parsed.get("detail")
            if isinstance(detail, dict):
                code = detail.get("code") or detail.get("error")
                if isinstance(code, str) and code:
                    return code
            err = parsed.get("error")
            if isinstance(err, str) and err:
                return err
    except Exception:
        pass
    return None


def _retry_after_ms(response: httpx.Response) -> int | None:
    raw = response.headers.get("retry-after")
    if raw:
        try:
            return max(0, int(float(raw) * 1000))
        except ValueError:
            pass
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            detail = parsed.get("detail", {})
            if isinstance(detail, dict):
                sec = detail.get("retry_after_seconds") or detail.get("params", {}).get("retryAfterSeconds")
                if sec is not None:
                    return int(sec) * 1000
    except Exception:
        pass
    return None


async def _poll_messages(
    client: httpx.AsyncClient,
    chat_uuid: str,
    headers: dict[str, str],
    timeout_seconds: float,
    poll_interval: float = 1.2,
) -> str | None:
    start = time.time()
    while time.time() - start < timeout_seconds:
        await asyncio.sleep(poll_interval)
        try:
            r = await client.get(f"/chats/{chat_uuid}/messages?page_size=20", headers=headers)
            if r.status_code == 200:
                data = r.json()
                messages = data.get("messages", []) if isinstance(data, dict) else []
                for msg in messages:
                    if msg.get("author_id") == -1:
                        m_objs = msg.get("message_object", [])
                        for obj in m_objs:
                            if obj.get("object_type") == "text" and obj.get("completed"):
                                return str(obj.get("object_text", ""))
        except Exception:
            continue
    return None


async def call_syntx_generation(
    *,
    model: str,
    prompt: str,
    timeout_ms: int,
    base_url: str = SYNTX_BASE_URL,
    transport: httpx.AsyncBaseTransport | None = None,
    allow_failover: bool = True,
) -> UpstreamReply:
    account = acquire_account()
    if not account or not account.get("token"):
        return UpstreamReply(ok=False, fail_kind="pool_exhausted")

    token = account["token"]
    chat_uuid = account.get("chat_uuid") or "07d713b3-d876-465e-8d8c-970ec1ef3cdb"
    ai_name = _MODEL_AI_NAME_MAP.get(model, "chatgpt")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    }

    body: dict[str, Any] = {
        "chat_uuid": chat_uuid,
        "text": prompt,
        "model": model,
        "thinking": True,
        "plan": True,
        "deep_research": True,
        "tools": ["search", "code", "shell", "files", "charts"],
    }

    timeout_seconds = max(1.0, timeout_ms / 1000.0)
    effective_transport = transport if transport is not None else _default_transport

    try:
        async with httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            transport=effective_transport,
            timeout=timeout_seconds,
        ) as client:
            resp = await client.post(f"/llm/generate?ai_name={ai_name}", json=body, headers=headers)

            if resp.status_code == 400 and model == "grok-4.6":
                body["model"] = "grok-4.5"
                resp = await client.post(f"/llm/generate?ai_name={ai_name}", json=body, headers=headers)

            if resp.status_code == 429:
                retry_ms = _retry_after_ms(resp)
                cooldown_sec = (retry_ms // 1000) if retry_ms else _DEFAULT_COOLDOWN_SECONDS
                update_account_status(token, "cooldown", cooldown_sec)
                if allow_failover:
                    return await call_syntx_generation(
                        model=model,
                        prompt=prompt,
                        timeout_ms=timeout_ms,
                        base_url=base_url,
                        transport=transport,
                        allow_failover=False,
                    )
                return UpstreamReply(
                    ok=False,
                    fail_kind="http",
                    http_status=429,
                    error_code="rate_limit_exceeded",
                    retry_after_ms=retry_ms or (_DEFAULT_COOLDOWN_SECONDS * 1000),
                )

            if resp.status_code in (401, 403):
                update_account_status(token, "expired")
                if allow_failover:
                    return await call_syntx_generation(
                        model=model,
                        prompt=prompt,
                        timeout_ms=timeout_ms,
                        base_url=base_url,
                        transport=transport,
                        allow_failover=False,
                    )
                return UpstreamReply(
                    ok=False,
                    fail_kind="http",
                    http_status=resp.status_code,
                    error_code=_safe_error_code(resp) or "unauthorized",
                )

            if resp.status_code != 200:
                return UpstreamReply(
                    ok=False,
                    fail_kind="http",
                    http_status=resp.status_code,
                    error_code=_safe_error_code(resp),
                    retry_after_ms=_retry_after_ms(resp),
                )

            # Poll for final completed message
            reply_text = await _poll_messages(
                client=client,
                chat_uuid=chat_uuid,
                headers=headers,
                timeout_seconds=min(90.0, timeout_seconds),
            )

            if reply_text is not None:
                approx_in = max(1, int(len(prompt) / 3.5))
                approx_out = max(1, int(len(reply_text) / 3.5))
                return UpstreamReply(
                    ok=True,
                    text=reply_text,
                    finish_reason="stop",
                    usage={"prompt_tokens": approx_in, "completion_tokens": approx_out},
                )

            return UpstreamReply(ok=False, fail_kind="timeout")

    except httpx.TimeoutException:
        return UpstreamReply(ok=False, fail_kind="timeout")
    except httpx.HTTPError:
        return UpstreamReply(ok=False, fail_kind="network")
