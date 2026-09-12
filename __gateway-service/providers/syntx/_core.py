"""Syntx AI Core Engine — Layer 1 (Autonomous 3-Function Capsule).

Compliance: Bolla Constitution v1.2 & UNIVERSAL_PROVIDER_SPEC_AND_BLUEPRINT.md
- Autonomous 3-function capsule: register(), refresh(), ask().
- FileLock concurrency protection (15s timeout) on accounts_syntx.json.
- Non-vision model guard: rejects vision requests on text-only models before network calls.
- Pure Python in-process execution — zero dangling subprocesses.
"""

from __future__ import annotations

import base64
import json
import os
import random
import re
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any

try:
    from filelock import FileLock, Timeout as LockTimeout
except ImportError:
    FileLock = None
    LockTimeout = TimeoutError

# Load metadata for raw model capabilities
_METADATA_PATH = Path(__file__).resolve().parent / "models_metadata.json"
try:
    with open(_METADATA_PATH, "r", encoding="utf-8") as _f:
        MODELS_METADATA: dict[str, dict] = json.load(_f)
except Exception:
    MODELS_METADATA = {}


class UpstreamFailure(Exception):
    """Canonical internal exception carrying normalized category and diagnostics."""

    def __init__(
        self,
        category: str,
        message: str,
        retry_after_ms: int | None = None,
        provider_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.retry_after_ms = retry_after_ms
        self.provider_code = provider_code


def is_vision_model(model: str) -> bool:
    """Check if the given model supports images/vision input according to metadata."""
    model_info = MODELS_METADATA.get(model)
    if not model_info:
        return False
    caps = model_info.get("capabilities", {})
    return bool(caps.get("images", False))


def get_model_ai_name(model: str) -> str:
    """Retrieve the upstream ai_name identifier for the given model."""
    info = MODELS_METADATA.get(model)
    if info and "ai_name" in info:
        return info["ai_name"]
    lower = model.lower()
    if "claude" in lower:
        return "claude"
    if "gpt" in lower or "chatgpt" in lower:
        return "chatgpt"
    if "grok" in lower:
        return "grok"
    if "gemini" in lower:
        return "gemini"
    if "deepseek" in lower:
        return "deepseek"
    if "qwen" in lower:
        return "qwen"
    return "auto"


def get_accounts_file_path() -> Path:
    """Resolve the accounts pool file path with environment override."""
    env_override = os.environ.get("GW_SYNTX_ACCOUNTS_FILE")
    if env_override:
        return Path(env_override)
    local = Path(__file__).resolve().parent / "accounts_syntx.json"
    if local.exists():
        return local
    vibe = Path("d:/SMS/.hRhRhRhRhRhR/.AAA_GGG_iii_VIBE_CODING/🟢_syntx_ai/accounts_syntx.json")
    if vibe.exists():
        return vibe
    return local


def _execute_locked(callback, timeout_s: float = 15.0):
    """Execute a read/write operation under the canonical shared FileLock."""
    path = get_accounts_file_path()
    lock_path = path.with_suffix(".json.lock")
    if FileLock:
        try:
            with FileLock(str(lock_path), timeout=timeout_s):
                return callback(path)
        except Exception as err:
            raise UpstreamFailure("provider_unavailable", f"Accounts lock timeout: {err}") from err
    return callback(path)


def load_accounts_pool() -> list[dict[str, Any]]:
    """Load accounts securely under lock."""
    def _read(path: Path) -> list[dict[str, Any]]:
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

    return _execute_locked(_read)


def save_accounts_pool(accounts: list[dict[str, Any]]) -> bool:
    """Save accounts atomically under lock."""
    def _write(path: Path) -> bool:
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(accounts, f, ensure_ascii=False, indent=2)
            tmp.replace(path)
            return True
        except Exception:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            return False

    return _execute_locked(_write)


def get_active_account() -> dict[str, Any] | None:
    """Retrieve first active account with valid token."""
    accounts = load_accounts_pool()
    for acc in accounts:
        token = acc.get("token")
        if (
            acc.get("status") == "active"
            and isinstance(token, str)
            and token
            and token.isascii()
        ):
            return acc
    return None


def evict_account(token: str) -> None:
    """Evict a depleted or expired account from the pool atomically."""
    def _evict(path: Path):
        if not path.exists():
            return
        try:
            accounts = json.loads(path.read_text(encoding="utf-8"))
            retained = [a for a in accounts if a.get("token") != token]
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(retained, f, ensure_ascii=False, indent=2)
            tmp.replace(path)
        except Exception:
            pass

    _execute_locked(_evict)


# --------------------------------------------------------------------------- #
# HTTP Client Wrapper (Supports both curl_cffi and httpx for tests)           #
# --------------------------------------------------------------------------- #

_TRANSPORT_OVERRIDE = None


def set_transport_override(transport) -> None:
    """Hook for unit tests to inject MockTransport without touching network."""
    global _TRANSPORT_OVERRIDE
    _TRANSPORT_OVERRIDE = transport


def http_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    timeout: float = 30.0,
):
    """Unified HTTP request dispatcher supporting curl_cffi, httpx, and mock transports."""
    if _TRANSPORT_OVERRIDE is not None:
        import httpx

        with httpx.Client(transport=_TRANSPORT_OVERRIDE, timeout=timeout) as client:
            return client.request(
                method, url, headers=headers, json=json_data, files=files, data=data
            )

    try:
        from curl_cffi import requests as cffi_req

        session = cffi_req.Session(impersonate="chrome124")
        try:
            return session.request(
                method,
                url,
                headers=headers,
                json=json_data,
                files=files,
                data=data,
                timeout=timeout,
            )
        finally:
            session.close()
    except ImportError:
        import httpx

        with httpx.Client(timeout=timeout) as client:
            return client.request(
                method, url, headers=headers, json=json_data, files=files, data=data
            )


# --------------------------------------------------------------------------- #
# Function 1: register(timeout: int = 120) -> dict                            #
# --------------------------------------------------------------------------- #

class TempMailClubClient:
    """Direct client for Temp-Mail.club to obtain verified disposable email and poll OTP."""

    def __init__(self):
        self.fake_ip = f"{random.randint(11, 190)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "X-Forwarded-For": self.fake_ip,
            "X-Real-IP": self.fake_ip,
            "Client-IP": self.fake_ip,
        }
        self.csrf_token = ""
        self.app_fingerprint = None
        self.app_server_memo = None
        self.box_action_comp = None
        self.email = ""
        self._session = None

    def _get_session(self):
        if self._session is None:
            if _TRANSPORT_OVERRIDE is not None:
                import httpx
                self._session = httpx.Client(transport=_TRANSPORT_OVERRIDE, timeout=15.0)
            else:
                try:
                    from curl_cffi import requests as cffi_req
                    self._session = cffi_req.Session(impersonate="chrome124")
                except ImportError:
                    import httpx
                    self._session = httpx.Client(timeout=15.0)
        return self._session

    def close(self):
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    def create_email(self) -> str | None:
        import html
        session = self._get_session()
        try:
            r_home = session.get("https://temp-mail.club/", headers=self.headers, timeout=15)
            m_csrf = re.search(
                r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', r_home.text
            ) or re.search(r'content=["\']([^"\']+)["\']\s+name=["\']csrf-token["\']', r_home.text)
            self.csrf_token = m_csrf.group(1) if m_csrf else ""

            action_comp = None
            for m in re.findall(r'wire:initial-data=["\'](.*?)["\']\s', r_home.text):
                try:
                    j = json.loads(html.unescape(m))
                    if j.get("fingerprint", {}).get("name") == "frontend.actions":
                        action_comp = j
                        break
                except Exception:
                    pass

            if not action_comp:
                return None

            lw_headers = {
                "Content-Type": "application/json",
                "X-CSRF-TOKEN": self.csrf_token,
                "X-Livewire": "true",
                "Origin": "https://temp-mail.club",
                "Referer": "https://temp-mail.club/",
                "Accept": "text/html, application/xhtml+xml",
                "X-Forwarded-For": self.fake_ip,
            }
            payload = {
                "fingerprint": action_comp["fingerprint"],
                "serverMemo": action_comp["serverMemo"],
                "updates": [
                    {
                        "type": "callMethod",
                        "payload": {
                            "id": secrets.token_hex(3),
                            "method": "random",
                            "params": [],
                        },
                    }
                ],
            }
            session.post(
                "https://temp-mail.club/livewire/message/frontend.actions",
                json=payload,
                headers=lw_headers,
                timeout=10,
            )

            r_box = session.get(
                "https://temp-mail.club/mailbox", headers=self.headers, timeout=10
            )
            for mb in re.findall(r'wire:initial-data=["\'](.*?)["\']', r_box.text):
                try:
                    mb_j = json.loads(html.unescape(mb))
                    comp_name = mb_j.get("fingerprint", {}).get("name")
                    if comp_name == "frontend.app":
                        self.email = mb_j.get("serverMemo", {}).get("data", {}).get("email", "")
                        self.app_fingerprint = mb_j.get("fingerprint")
                        self.app_server_memo = mb_j.get("serverMemo")
                    elif comp_name == "frontend.actions":
                        self.box_action_comp = mb_j
                except Exception:
                    pass
            return self.email if self.email else None
        except Exception:
            return None

    def delete_email(self) -> bool:
        """Reset and clean mailbox on temp-mail.club to prevent daily accumulation."""
        session = self._get_session()
        try:
            if not self.box_action_comp:
                r_box = session.get("https://temp-mail.club/mailbox", headers=self.headers, timeout=10)
                for mb in re.findall(r'wire:initial-data=["\'](.*?)["\']', r_box.text):
                    try:
                        mb_j = json.loads(html.unescape(mb))
                        if mb_j.get("fingerprint", {}).get("name") == "frontend.actions":
                            self.box_action_comp = mb_j
                            break
                    except Exception:
                        pass

            if self.box_action_comp and self.csrf_token:
                lw_headers = {
                    "Content-Type": "application/json",
                    "X-CSRF-TOKEN": self.csrf_token,
                    "X-Livewire": "true",
                    "Origin": "https://temp-mail.club",
                    "Referer": "https://temp-mail.club/mailbox",
                    "Accept": "text/html, application/xhtml+xml",
                    "X-Forwarded-For": self.fake_ip,
                }
                payload_del = {
                    "fingerprint": self.box_action_comp["fingerprint"],
                    "serverMemo": self.box_action_comp["serverMemo"],
                    "updates": [
                        {"type": "callMethod", "payload": {"id": secrets.token_hex(3), "method": "deleteEmail", "params": []}}
                    ],
                }
                r = session.post(
                    "https://temp-mail.club/livewire/message/frontend.actions",
                    json=payload_del,
                    headers=lw_headers,
                    timeout=10,
                )
                return r.status_code == 200
        except Exception:
            pass
        return False

    def poll_otp(self, timeout: int = 45) -> str | None:
        if not self.app_fingerprint or not self.app_server_memo:
            return None
        session = self._get_session()
        lw_headers = {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": self.csrf_token,
            "X-Livewire": "true",
            "Origin": "https://temp-mail.club",
            "Referer": "https://temp-mail.club/mailbox",
            "Accept": "text/html, application/xhtml+xml",
            "X-Forwarded-For": self.fake_ip,
            "X-Real-IP": self.fake_ip,
            "Client-IP": self.fake_ip,
        }
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(3)
            payload = {
                "fingerprint": self.app_fingerprint,
                "serverMemo": self.app_server_memo,
                "updates": [
                    {
                        "type": "fireEvent",
                        "payload": {
                            "id": secrets.token_hex(3),
                            "event": "fetchMessages",
                            "params": [],
                        },
                    }
                ],
            }
            try:
                r_msg = session.post(
                    "https://temp-mail.club/livewire/message/frontend.app",
                    json=payload,
                    headers=lw_headers,
                    timeout=10,
                )
                if r_msg.status_code == 200:
                    res_j = r_msg.json()
                    if "serverMemo" in res_j:
                        self.app_server_memo.update(res_j["serverMemo"])
                    html_content = res_j.get("effects", {}).get("html", "") or ""
                    msgs = res_j.get("serverMemo", {}).get("data", {}).get("messages", [])
                    for m_item in msgs:
                        content = m_item.get("content", "") or m_item.get("subject", "")
                        m = re.search(r"\b(\d{6})\b", content)
                        if m:
                            return m.group(1)
                    if "verification code" in html_content.lower() or "otp" in html_content.lower():
                        m = re.search(r"\b(\d{6})\b", html_content)
                        if m:
                            return m.group(1)
            except Exception:
                pass
        return None


def register(timeout: int = 120) -> dict[str, Any]:
    """Register a fresh Syntx account and persist to accounts pool."""
    start_time = time.time()
    base_api = "https://api.syntx.ai/api/v1"
    headers_syntx = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    client = TempMailClubClient()
    try:
        email = client.create_email()
        if not email:
            raise UpstreamFailure("provider_unavailable", "Could not generate temporary email")

        # Send OTP
        send_payload = {"email": email, "ref_uuid": None, "utm": ""}
        r_send = http_request(
            "POST", f"{base_api}/auth/email/send-otp", json_data=send_payload, headers=headers_syntx, timeout=15
        )
        if r_send.status_code != 200:
            raise UpstreamFailure(
                "provider_unavailable",
                f"Syntx send-otp failed ({r_send.status_code})",
                provider_code=str(r_send.status_code),
            )

        remaining_time = max(10, int(timeout - (time.time() - start_time)))
        otp_code = client.poll_otp(timeout=min(remaining_time, 60))
        if not otp_code:
            raise UpstreamFailure("provider_unavailable", "Syntx registration OTP timed out")

        # Verify OTP
        verify_payload = {"email": email, "otp_code": otp_code, "ref_uuid": None, "utm": ""}
        r_verify = http_request(
            "POST", f"{base_api}/auth/email/verify-otp", json_data=verify_payload, headers=headers_syntx, timeout=15
        )
        if r_verify.status_code != 200 or not r_verify.json().get("success"):
            raise UpstreamFailure("invalid_credential", "Syntx OTP verification rejected by upstream")

        token = r_verify.json().get("token")
        if not token:
            raise UpstreamFailure("provider_unavailable", "Syntx did not return bearer token")

        # Create initial chat session
        chat_headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
        }
        chat_uuid = ""
        try:
            r_chat = http_request(
                "POST",
                f"{base_api}/chats",
                json_data={"title": "Syntx Master Session", "scope": "text"},
                headers=chat_headers,
                timeout=15,
            )
            if r_chat.status_code in [200, 201]:
                chat_uuid = r_chat.json().get("uuid", "")
        except Exception:
            pass

        new_account = {
            "email": email,
            "token": token,
            "chat_uuid": chat_uuid,
            "provider": "tempmailclub",
            "status": "active",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expires_in_days": 365,
        }

        accounts = load_accounts_pool()
        accounts.append(new_account)
        save_accounts_pool(accounts)
        return new_account
    finally:
        client.delete_email()
        client.close()


# --------------------------------------------------------------------------- #
# Background Replenishment Engine (Voice 88/90 Proactive Pool Fortification)  #
# --------------------------------------------------------------------------- #

_REFILL_LOCK = threading.Lock()


def _background_refill_worker(count: int = 5) -> None:
    """Provision fresh accounts in background to maintain pool depth under traffic."""
    if not _REFILL_LOCK.acquire(blocking=False):
        # A refill worker is already actively provisioning; skip to prevent duplicate spam
        return
    try:
        for _ in range(count):
            try:
                register(timeout=90)
                # Small humanized pause between registrations to avoid rate-limiting
                time.sleep(random.uniform(1.5, 3.5))
            except Exception:
                pass
    finally:
        _REFILL_LOCK.release()


def trigger_background_refill(count: int = 5) -> None:
    """Non-blocking dispatcher to spawn background accounts replenishment worker."""
    if _TRANSPORT_OVERRIDE is not None or os.environ.get("GW_SYNTX_DISABLE_BG_REFILL") == "1":
        return
    worker_thread = threading.Thread(
        target=_background_refill_worker, args=(count,), daemon=True, name="syntx-bg-refill"
    )
    worker_thread.start()


# --------------------------------------------------------------------------- #
# Function 2: refresh(account: dict) -> bool                                  #
# --------------------------------------------------------------------------- #

def refresh(account: dict[str, Any]) -> bool:
    """Verify account token health against Syntx quotas and balances."""
    token = account.get("token")
    if not token or not isinstance(token, str):
        return False

    base_api = "https://api.syntx.ai/api/v1"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }

    try:
        r = http_request("GET", f"{base_api}/user/balance", headers=headers, timeout=10)
        if r.status_code in [401, 403, 429]:
            evict_account(token)
            return False
        if r.status_code == 200:
            body = r.json()
            balance = body.get("balance")
            if balance == 0:
                evict_account(token)
                return False
            return True
    except Exception:
        pass
    return True


# --------------------------------------------------------------------------- #
# Function 3: ask(...) -> dict                                                #
# --------------------------------------------------------------------------- #

def upload_image_bytes(token: str, image_bytes: bytes, filename: str = "image.png") -> str:
    """Upload image multipart to Syntx R2 bucket and return public URL."""
    base_api = "https://api.syntx.ai/api/v1"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    files = {"files": (filename, image_bytes, "image/png")}
    data = {"destination": "uploaded", "check_duplicates": "true", "model_type": ""}
    if _TRANSPORT_OVERRIDE is not None:
        r = http_request(
            "POST", f"{base_api}/chats/upload-files", headers=headers, files=files, data=data, timeout=30
        )
    else:
        import requests
        r = requests.post(
            f"{base_api}/chats/upload-files", headers=headers, files=files, data=data, timeout=30
        )
    if r.status_code in [200, 201]:
        res_json = r.json()
        files_list = res_json.get("files", [])
        if files_list and "url" in files_list[0]:
            return files_list[0]["url"]
    raise UpstreamFailure(
        "bad_request",
        f"Failed to upload image to Syntx R2 ({r.status_code})",
        provider_code=str(r.status_code),
    )


def ask(
    model: str,
    prompt: str,
    image_b64: str | None = None,
    image_format: str | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Execute text or vision inference with automatic account replenishment and retry."""
    # 1. Non-Vision Guard (Zero Network touch)
    if image_b64:
        if not is_vision_model(model):
            raise UpstreamFailure(
                "unsupported_capability",
                f"Model {model!r} does not support vision/image inputs",
            )

    # 2. Trigger Proactive Background Replenishment (Eng. Zizo Voice 88/90 Mandate)
    # Spawns detached daemon worker to provision 5 fresh accounts in background without blocking response
    trigger_background_refill(count=5)

    max_attempts = 3
    for attempt in range(max_attempts):
        # 2. Acquire active account
        account = get_active_account()
        if not account:
            try:
                account = register(timeout=min(timeout, 90))
            except Exception as reg_err:
                raise UpstreamFailure("provider_unavailable", f"No active account available: {reg_err}") from reg_err

        token = account["token"]
        chat_uuid = account.get("chat_uuid")
        base_api = "https://api.syntx.ai/api/v1"

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
        }

        if not chat_uuid:
            r_chat = http_request(
                "POST",
                f"{base_api}/chats",
                json_data={"title": "Gateway Session", "scope": "text"},
                headers=headers,
                timeout=15,
            )
            if r_chat.status_code in [200, 201]:
                chat_uuid = r_chat.json().get("uuid")

        # 3. Handle image upload if vision
        img_url = None
        if image_b64:
            try:
                raw_bytes = base64.b64decode(image_b64)
                img_ext = (image_format or "png").lower().lstrip(".")
                img_url = upload_image_bytes(token, raw_bytes, filename=f"image.{img_ext}")
            except UpstreamFailure:
                raise
            except Exception as e:
                raise UpstreamFailure("bad_request", f"Invalid image base64 data: {e}") from e

        # 4. Dispatch Generation Request
        ai_name = get_model_ai_name(model)
        payload: dict[str, Any] = {
            "chat_uuid": chat_uuid,
            "text": prompt,
            "model": model,
            "thinking": True,
            "plan": True,
            "deep_research": True,
            "tools": ["search", "code", "shell", "files", "charts"],
        }
        if img_url:
            payload["files"] = [{"object_type": "image", "object_url": img_url}]

        # Fetch pre-existing message IDs to ignore them during polling
        pre_msg_ids = set()
        try:
            r_pre = http_request(
                "GET", f"{base_api}/chats/{chat_uuid}/messages?page_size=20", headers=headers, timeout=10
            )
            if r_pre.status_code == 200:
                pre_msg_ids = set(m.get("id") for m in r_pre.json().get("messages", []))
        except Exception:
            pass

        r_gen = http_request(
            "POST",
            f"{base_api}/llm/generate?ai_name={ai_name}",
            json_data=payload,
            headers=headers,
            timeout=timeout,
        )

        # Handle status mapping
        if r_gen.status_code in [401, 403]:
            evict_account(token)
            next_acc = get_active_account()
            if next_acc and attempt < max_attempts - 1:
                continue
            raise UpstreamFailure("invalid_credential", "Syntx authentication expired or invalid")
        if r_gen.status_code == 404:
            raise UpstreamFailure("model_unavailable", f"Model {model!r} not available upstream")
        if r_gen.status_code == 429:
            evict_account(token)
            next_acc = get_active_account()
            if next_acc and attempt < max_attempts - 1:
                continue
            retry_ms = 2000
            try:
                retry_sec = r_gen.json().get("detail", {}).get("retry_after_seconds")
                if retry_sec:
                    retry_ms = int(retry_sec * 1000)
            except Exception:
                pass
            raise UpstreamFailure(
                "rate_limited", "Syntx rate limit reached", retry_after_ms=retry_ms, provider_code="429"
            )
        if r_gen.status_code in [400, 422]:
            raise UpstreamFailure(
                "bad_request", f"Syntx rejected payload ({r_gen.status_code})", provider_code=str(r_gen.status_code)
            )
        if r_gen.status_code >= 500:
            raise UpstreamFailure(
                "retryable_server_error",
                f"Syntx server glitch ({r_gen.status_code})",
                provider_code=str(r_gen.status_code),
            )

        # 5. Poll for message completion
        bot_reply = None
        input_tokens = None
        output_tokens = None

        poll_start = time.time()
        poll_sleep = 0.01 if _TRANSPORT_OVERRIDE is not None else 1.0
        while time.time() - poll_start < timeout:
            time.sleep(poll_sleep)
            r_poll = http_request(
                "GET", f"{base_api}/chats/{chat_uuid}/messages?page_size=20", headers=headers, timeout=15
            )
            if r_poll.status_code == 200:
                messages = r_poll.json().get("messages", [])
                for msg in reversed(messages):
                    if msg.get("id") not in pre_msg_ids and msg.get("author_id") == -1:
                        usage = msg.get("usage")
                        if isinstance(usage, dict):
                            input_tokens = usage.get("input_tokens")
                            output_tokens = usage.get("output_tokens")
                        for obj in msg.get("message_object", []):
                            if obj.get("object_type") == "text" and obj.get("completed"):
                                bot_reply = obj.get("object_text", "")
                                break
                    if bot_reply:
                        break
            if bot_reply:
                break

        if not bot_reply:
            raise UpstreamFailure("timeout", "Syntx generation timed out waiting for completed response")

        return {
            "text": bot_reply,
            "finish_reason": "stop",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }

    raise UpstreamFailure("provider_unavailable", "Exhausted all retry attempts")
