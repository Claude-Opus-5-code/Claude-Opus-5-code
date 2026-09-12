"""Authorized account maintenance, scheduled internally without blocking chat.

No account creation or trial replenishment. Known read-only health endpoints
are reused from the original health checker. Unknown evidence never deletes a
credential. There is no invented refresh API. Lock ownership spans the complete
worker lifetime, including cancellation before the coroutine first runs.
"""

import asyncio
import time
from pathlib import Path

import httpx
from filelock import FileLock, Timeout

from ._accounts import AccountPool
from ._config import ProviderConfig
from ._privacy import private_diagnostics
from ._transport import Deadline, Transport, UpstreamFailure

_active: dict[Path, asyncio.Task] = {}
_last_start: dict[Path, float] = {}


async def _run(
    config: ProviderConfig, pool: AccountPool, transport: httpx.AsyncBaseTransport | None
) -> bool:
    deadline = Deadline.after_ms(config.maintenance_timeout_ms)
    try:
        async with asyncio.timeout(deadline.remaining()):
            await pool.merge_pending(deadline.end)
            snapshot = await pool.snapshot(deadline.end)
            ready = [
                item
                for item in snapshot
                if item["status"] in {"active", "cooldown"}
                and item.get("cooldown_until", 0) <= pool.wall_clock()
            ]
            if len(ready) >= config.maintenance_threshold:
                return True
            for item in ready[: config.maintenance_max_accounts]:
                # Network work is OUTSIDE the account pool transaction lock.
                try:
                    async with Transport(
                        item["token"],
                        deadline,
                        transport=transport,
                        cooldown=config.cooldown_seconds,
                    ) as wire:
                        balance = await wire.request("GET", "user/balance")
                        value = balance.get("balance")
                        if type(value) in (int, float) and value == 0:
                            await pool.record_failure(item["token"], "quota_exceeded", deadline.end)
                            continue
                        limits = await wire.request("GET", "llm/limits")
                        for window in ("window_6h", "window_7d"):
                            data = limits.get(window)
                            value = data.get("percent_left") if isinstance(data, dict) else None
                            if type(value) in (int, float) and value == 0:
                                await pool.record_failure(
                                    item["token"], "rate_limited", deadline.end
                                )
                                break
                except UpstreamFailure as exc:
                    await pool.record_failure(
                        item["token"], exc.kind, deadline.end, exc.retry_after_ms
                    )
            return True
    except Exception:
        # Deliberately no raw exception logs or task exception leaks.
        # Cancellation still propagates; the done callback releases ownership.
        return False


def _trigger_maintenance(
    config: ProviderConfig,
    *,
    pool: AccountPool | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> asyncio.Task | None:
    """Try once, never wait for ownership. Caller must not await the returned task.

    Maintenance is request-triggered and bounded; it is not a permanent daemon.
    Tests disable it in their configs or inject a mock transport/worker explicitly.
    """
    if not config.maintenance_enabled:
        return None
    path = config.maintenance_lock_file.resolve()
    now = time.monotonic()
    if path in _active or now - _last_start.get(path, float("-inf")) < config.maintenance_interval:
        return None
    try:
        loop = asyncio.get_running_loop()
        if config.maintenance_lock_file.is_symlink():
            return None
        lock = FileLock(config.maintenance_lock_file, thread_local=False, mode=0o600)
        lock.acquire(timeout=0)
    except (OSError, Timeout, RuntimeError):
        return None
    coroutine = _run(config, pool or AccountPool(config), transport)
    try:
        task = loop.create_task(coroutine)
    except BaseException:
        coroutine.close()
        lock.release()
        raise
    _active[path] = task
    _last_start[path] = now

    def finished(done: asyncio.Task) -> None:
        lock.release()
        if _active.get(path) is done:
            _active.pop(path, None)
        if not done.cancelled():
            done.exception()  # Retrieve unexpected worker exceptions without logging secrets.

    task.add_done_callback(finished)
    return task


def trigger_maintenance(
    config: ProviderConfig,
    *,
    pool: AccountPool | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> asyncio.Task | None:
    with private_diagnostics():
        try:
            return _trigger_maintenance(config, pool=pool, transport=transport)
        except (OSError, RuntimeError):
            return None  # Optional maintenance never breaks chat on path/loop failures.
