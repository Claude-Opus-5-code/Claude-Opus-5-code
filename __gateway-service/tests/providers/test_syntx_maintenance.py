"""Maintenance isolation, lifetime ownership and synthetic health evidence."""

import asyncio
import time
from dataclasses import replace

import httpx
import pytest
from filelock import FileLock

from providers.syntx import _maintenance
from providers.syntx._accounts import AccountPool
from providers.syntx._config import ProviderConfig


@pytest.fixture
async def setup_pool(tmp_path):
    cfg = ProviderConfig(state_dir=tmp_path, maintenance_interval=0)
    pool = AccountPool(cfg)
    await pool.add_authorized([{"token": "synthetic", "status": "active"}], time.monotonic() + 2)
    return cfg, pool


async def test_disabled_or_external_lock_never_starts_worker(setup_pool):
    cfg, pool = setup_pool
    assert (
        _maintenance.trigger_maintenance(replace(cfg, maintenance_enabled=False), pool=pool) is None
    )
    with FileLock(cfg.maintenance_lock_file):
        assert _maintenance.trigger_maintenance(cfg, pool=pool) is None


async def test_single_worker_does_not_hold_account_lock_while_network_waits(setup_pool):
    cfg, pool = setup_pool
    entered, release = asyncio.Event(), asyncio.Event()

    async def respond(request):
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"balance": 10})

    mock = httpx.MockTransport(respond)
    task = _maintenance.trigger_maintenance(cfg, pool=pool, transport=mock)
    await entered.wait()
    assert _maintenance.trigger_maintenance(cfg, pool=pool, transport=mock) is None
    # Account transaction remains available while worker waits for the service.
    await pool.add_authorized([{"token": "new", "status": "active"}], time.monotonic() + 0.2)
    assert len(await pool.snapshot(time.monotonic() + 0.2)) == 2
    release.set()
    assert await task
    with FileLock(cfg.maintenance_lock_file, timeout=0):
        pass


async def test_cancel_before_coroutine_starts_releases_ownership(setup_pool):
    cfg, pool = setup_pool
    task = _maintenance.trigger_maintenance(
        cfg,
        pool=pool,
        transport=httpx.MockTransport(
            lambda request: pytest.fail("cancelled worker must not call network")
        ),
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    assert cfg.maintenance_lock_file.resolve() not in _maintenance._active
    with FileLock(cfg.maintenance_lock_file, timeout=0):
        pass


@pytest.mark.parametrize(
    "status,body,state",
    [
        (401, {}, "invalid"),
        (403, {"detail": {"code": "modelNotAvailableForPlan"}}, "active"),
        (429, {"detail": {"retry_after_seconds": 200}}, "cooldown"),
        (500, {}, "active"),
        (200, {"balance": 0}, "quota_exceeded"),
        (200, {"balance": "0"}, "active"),
    ],
)
async def test_health_evidence_changes_only_justified_states(setup_pool, status, body, state):
    cfg, pool = setup_pool
    task = _maintenance.trigger_maintenance(
        cfg,
        pool=pool,
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body)),
    )
    assert await task
    assert (await pool.snapshot(time.monotonic() + 1))[0]["status"] == state


async def test_pending_import_and_threshold_skip_network(setup_pool):
    cfg, pool = setup_pool
    await pool.stage_authorized(
        [{"token": f"new_{i}", "status": "active"} for i in range(4)], time.monotonic() + 1
    )
    task = _maintenance.trigger_maintenance(
        cfg,
        pool=pool,
        transport=httpx.MockTransport(
            lambda request: pytest.fail("healthy pool does not need probing")
        ),
    )
    assert await task
    assert len(await pool.snapshot(time.monotonic() + 1)) == 5
    assert not cfg.incoming_accounts_file.exists()


async def test_worker_fault_is_safe_and_ownership_released(setup_pool, monkeypatch):
    cfg, pool = setup_pool

    async def fail(deadline):
        raise ValueError("private token path")

    monkeypatch.setattr(pool, "merge_pending", fail)
    task = _maintenance.trigger_maintenance(cfg, pool=pool)
    assert await task is False
    with FileLock(cfg.maintenance_lock_file, timeout=0):
        pass


async def test_worker_deadline_cancels_hanging_network(setup_pool):
    cfg, pool = setup_pool
    stopped = asyncio.Event()

    async def respond(request):
        try:
            await asyncio.sleep(10)
        finally:
            stopped.set()

    task = _maintenance.trigger_maintenance(
        replace(cfg, maintenance_timeout_ms=20), pool=pool, transport=httpx.MockTransport(respond)
    )
    assert await task is False
    assert stopped.is_set()
    with FileLock(cfg.maintenance_lock_file, timeout=0):
        pass
