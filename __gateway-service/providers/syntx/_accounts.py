"""Private authorized account pool. All writers use one interprocess lock.

No registration, network or gateway imports. Constructor/import creates no files.
Pending-file producers must use stage_authorized, not write JSON independently.
"""

import asyncio
import json
import math
import os
import tempfile
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from ._config import ProviderConfig
from ._privacy import private_diagnostics

_MAX_BYTES = 4 * 1024 * 1024
_STATES = frozenset({"active", "cooldown", "expired", "invalid", "quota_exceeded"})


class PoolFailure(Exception):
    def __init__(self, kind: str, retry_after_ms: int | None = None):
        super().__init__("account storage unavailable")
        self.kind = kind
        self.retry_after_ms = retry_after_ms


@dataclass(frozen=True)
class Account:
    token: str = field(repr=False)


def _validate(value: Any) -> list[dict]:
    if not isinstance(value, list):
        raise PoolFailure("storage")
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            raise PoolFailure("storage")
        token, status = item.get("token"), item.get("status")
        until = item.get("cooldown_until", 0)
        if (
            not isinstance(token, str)
            or not token
            or len(token) > 16384
            or not all(33 <= ord(char) <= 126 for char in token)
            or not isinstance(status, str)
            or status not in _STATES
            or isinstance(until, bool)
            or not isinstance(until, int | float)
            or not 0 <= until <= 10**15
            or token in seen
        ):
            raise PoolFailure("storage")
        seen.add(token)
        result.append(dict(item))
    return result


def _read(path: Path) -> list[dict]:
    if path.is_symlink():
        raise PoolFailure("storage")
    try:
        with path.open("rb") as stream:
            raw = stream.read(_MAX_BYTES + 1)
    except FileNotFoundError:
        return []
    if len(raw) > _MAX_BYTES:
        raise PoolFailure("storage")
    try:
        return _validate(json.loads(raw))
    except (ValueError, UnicodeError, RecursionError):
        raise PoolFailure("storage") from None


def _write(path: Path, records: list[dict]) -> None:
    if path.is_symlink():
        raise PoolFailure("storage")
    try:
        payload = json.dumps(_validate(records), ensure_ascii=False, allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError):
        raise PoolFailure("storage") from None
    if len(payload) > _MAX_BYTES:
        raise PoolFailure("storage")
    fd, name = tempfile.mkstemp(prefix=".accounts_", suffix=".tmp", dir=path.parent)
    try:
        # mkstemp's 0600 permissions are preserved by replace.
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _merge(existing: list[dict], incoming: list[dict]) -> list[dict]:
    seen = {item["token"] for item in existing}
    # Duplicate imports cannot revive expired or cooling credentials.
    return existing + [item for item in incoming if item["token"] not in seen]


class AccountPool:
    def __init__(self, config: ProviderConfig, *, wall_clock: Callable[[], float] = time.time):
        self.config = config
        self.wall_clock = wall_clock
        self.lock_path = config.accounts_file.with_suffix(".json.lock")

    @asynccontextmanager
    async def transaction(self, deadline: float) -> AsyncIterator[None]:
        with private_diagnostics():
            # Each coroutine needs independent ownership; sharing a reentrant lock
            # instance across coroutines would not serialize their transactions.
            lock = FileLock(self.lock_path, thread_local=False, mode=0o600)
            try:
                if self.lock_path.is_symlink():
                    raise PoolFailure("storage")
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise PoolFailure("timeout")
                    try:
                        lock.acquire(timeout=0)
                        break
                    except Timeout:
                        await asyncio.sleep(min(0.01, remaining))
                try:
                    yield
                finally:
                    lock.release()
            except OSError:
                raise PoolFailure("storage") from None

    async def snapshot(self, deadline: float) -> list[dict]:
        async with self.transaction(deadline):
            return _read(self.config.accounts_file)

    async def add_authorized(self, records: list[dict], deadline: float) -> None:
        incoming = _validate(records)
        async with self.transaction(deadline):
            _write(self.config.accounts_file, _merge(_read(self.config.accounts_file), incoming))

    async def stage_authorized(self, records: list[dict], deadline: float) -> None:
        incoming = _validate(records)
        async with self.transaction(deadline):
            path = self.config.incoming_accounts_file
            _write(path, _merge(_read(path), incoming))

    async def merge_pending(self, deadline: float) -> int:
        async with self.transaction(deadline):
            current = _read(self.config.accounts_file)
            merged = _merge(current, _read(self.config.incoming_accounts_file))
            count = len(merged) - len(current)
            if count:
                _write(self.config.accounts_file, merged)
            # A crash after replace but before unlink is safe: merge is idempotent.
            self.config.incoming_accounts_file.unlink(missing_ok=True)
            return count

    async def select(self, deadline: float) -> Account:
        records = await self.snapshot(deadline)
        waiting = []
        for item in records:
            if item["status"] not in {"active", "cooldown"}:
                continue
            remaining = item.get("cooldown_until", 0) - self.wall_clock()
            if remaining <= 0:
                return Account(item["token"])
            waiting.append(math.ceil(remaining * 1000))
        if waiting:
            raise PoolFailure("rate_limited", min(waiting))
        if records and all(item["status"] == "quota_exceeded" for item in records):
            raise PoolFailure("quota_exceeded")
        raise PoolFailure("no_accounts")

    async def record_failure(
        self,
        token: str,
        kind: str,
        deadline: float,
        retry_after_ms: int | None = None,
    ) -> None:
        state = {
            "auth_expired": "expired",
            "invalid_credential": "invalid",
            "quota_exceeded": "quota_exceeded",
            "rate_limited": "cooldown",
        }.get(kind)
        if state is None:  # Plan denial/network/server failures do not invalidate credentials.
            return
        async with self.transaction(deadline):
            records = _read(self.config.accounts_file)
            for item in records:
                if item["token"] != token:
                    continue
                if state == "cooldown":
                    if item["status"] not in {"active", "cooldown"}:
                        return  # Late rate-limit responses must not revive invalid accounts.
                    delay = (
                        retry_after_ms / 1000
                        if retry_after_ms is not None
                        else self.config.cooldown_seconds
                    )
                    if not 0 <= delay <= 10**12:
                        raise PoolFailure("storage")
                    item["cooldown_until"] = max(
                        item.get("cooldown_until", 0), self.wall_clock() + delay
                    )
                item["status"] = state
                _write(self.config.accounts_file, records)
                return
