"""Hermetic checks of completed layers while the facade is being implemented."""

import asyncio
import json
import os
import stat
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError

import pytest
from filelock import FileLock

from providers.syntx import _accounts
from providers.syntx._accounts import AccountPool, PoolFailure
from providers.syntx._config import MODEL_AI_NAMES, PROVIDER_DIR, ProviderConfig


def test_config_has_exact_model_mapping():
    assert dict(MODEL_AI_NAMES) == {
        "gpt-5.6-terra": "chatgpt",
        "claude-opus-4-8": "claude",
        "claude-sonnet-5": "claude",
        "grok-4.6": "grok",
    }
    with pytest.raises(KeyError):
        _ = MODEL_AI_NAMES["unknown"]
    with pytest.raises(TypeError):
        MODEL_AI_NAMES["unknown"] = "chatgpt"


def test_config_is_immutable_and_settings_are_not_shared():
    cfg = ProviderConfig()
    with pytest.raises(FrozenInstanceError):
        cfg.thinking = False
    settings = cfg.generation_settings()
    assert settings["thinking"] is settings["plan"] is settings["deep_research"] is True
    settings["tools"].clear()
    assert cfg.generation_settings()["tools"] == ["search", "code", "shell", "files", "charts"]
    assert ProviderConfig(enable_tools=False).generation_settings()["tools"] == []


def test_config_paths_do_not_depend_on_cwd_or_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GW_SYNTX_ACCOUNTS_FILE", "/untrusted/path.json")
    cfg = ProviderConfig()
    assert cfg.accounts_file == PROVIDER_DIR / "accounts_syntx.json"
    assert cfg.incoming_accounts_file.parent == cfg.maintenance_lock_file.parent == PROVIDER_DIR
    isolated = ProviderConfig(state_dir=tmp_path / "not-created")
    assert isolated.accounts_file.parent == tmp_path / "not-created"
    assert not isolated.state_dir.exists()


def budget():
    return time.monotonic() + 5


def record(token="synthetic_token", status="active", **extra):
    return {"token": token, "status": status, **extra}


@pytest.fixture
def pool(tmp_path):
    return AccountPool(ProviderConfig(state_dir=tmp_path), wall_clock=lambda: 1000)


async def test_empty_pool_does_not_register_or_create_accounts(pool):
    with pytest.raises(PoolFailure) as exc:
        await pool.select(budget())
    assert exc.value.kind == "no_accounts"
    assert not pool.config.accounts_file.exists()


async def test_private_write_metadata_and_safe_repr(pool):
    await pool.add_authorized([record(email="test@example.invalid")], budget())
    assert (await pool.snapshot(budget()))[0]["email"] == "test@example.invalid"
    assert "synthetic_token" not in repr(await pool.select(budget()))
    assert stat.S_IMODE(pool.config.accounts_file.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{broken",
        b"{}",
        b"[null]",
        b'[{"token":"x"}]',
        b'[{"token":"bad\\nheader","status":"active"}]',
        b'[{"token":"x","status":[]}]',
        b'[{"token":"x","status":"active","cooldown_until":NaN}]',
    ],
)
async def test_invalid_pool_preserved(pool, raw):
    pool.config.accounts_file.write_bytes(raw)
    with pytest.raises(PoolFailure):
        await pool.add_authorized([record()], budget())
    assert pool.config.accounts_file.read_bytes() == raw


async def test_replace_failure_preserves_pool_pending_and_cleans_temporary(pool, monkeypatch):
    await pool.add_authorized([record("first")], budget())
    await pool.stage_authorized([record("second")], budget())
    before = pool.config.accounts_file.read_bytes()

    def fail(*args):
        raise OSError("sensitive path token")

    monkeypatch.setattr(_accounts.os, "replace", fail)
    with pytest.raises(PoolFailure) as exc:
        await pool.merge_pending(budget())
    assert "sensitive" not in str(exc.value)
    assert pool.config.accounts_file.read_bytes() == before
    assert pool.config.incoming_accounts_file.exists()
    assert not list(pool.config.state_dir.glob(".accounts_*.tmp"))


async def test_idempotent_merge_never_revives_expired_record(pool):
    await pool.add_authorized([record("old", "expired")], budget())
    await pool.stage_authorized([record("old"), record("new")], budget())
    assert await pool.merge_pending(budget()) == 1
    assert await pool.merge_pending(budget()) == 0
    assert (await pool.snapshot(budget()))[0]["status"] == "expired"
    assert (await pool.select(budget())).token == "new"
    assert not pool.config.incoming_accounts_file.exists()


async def test_cooldown_preserves_account_and_never_shortens_wait(pool):
    await pool.add_authorized([record()], budget())
    await pool.record_failure("synthetic_token", "rate_limited", budget(), 2000)
    await pool.record_failure("synthetic_token", "rate_limited", budget(), 100)
    with pytest.raises(PoolFailure) as exc:
        await pool.select(budget())
    assert (exc.value.kind, exc.value.retry_after_ms) == ("rate_limited", 2000)
    pool.wall_clock = lambda: 1003
    assert (await pool.select(budget())).token == "synthetic_token"


@pytest.mark.parametrize("kind", ["model_unavailable", "timeout", "network", "server"])
async def test_noncredential_failure_does_not_touch_pool(pool, kind):
    await pool.add_authorized([record()], budget())
    before = pool.config.accounts_file.read_bytes()
    await pool.record_failure("synthetic_token", kind, budget())
    assert pool.config.accounts_file.read_bytes() == before


@pytest.mark.parametrize(
    "kind,status",
    [
        ("auth_expired", "expired"),
        ("invalid_credential", "invalid"),
        ("quota_exceeded", "quota_exceeded"),
    ],
)
async def test_invalid_states_cannot_be_revived_by_late_cooldown(pool, kind, status):
    await pool.add_authorized([record()], budget())
    await pool.record_failure("synthetic_token", kind, budget())
    await pool.record_failure("synthetic_token", "rate_limited", budget(), 1)
    assert (await pool.snapshot(budget()))[0]["status"] == status
    with pytest.raises(PoolFailure):
        await pool.select(budget())


async def test_lock_deadline_nonblocking_and_cancellation_safe(pool):
    with FileLock(pool.lock_path):
        heartbeat = asyncio.create_task(asyncio.sleep(0.01, result="alive"))
        with pytest.raises(PoolFailure) as exc:
            await pool.snapshot(time.monotonic() + 0.04)
        assert exc.value.kind == "timeout"
        assert await heartbeat == "alive"
        task = asyncio.create_task(pool.snapshot(budget()))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    await pool.add_authorized([record()], budget())
    assert len(await pool.snapshot(budget())) == 1


async def test_symlink_rejected(pool):
    target = pool.config.state_dir / "target.json"
    target.write_text("[]")
    pool.config.accounts_file.symlink_to(target)
    with pytest.raises(PoolFailure):
        await pool.add_authorized([record()], budget())
    assert target.read_text() == "[]"


def test_eight_process_writers_preserve_all_updates(tmp_path):
    code = (
        "import asyncio,sys,time; from pathlib import Path; "
        "from providers.syntx._accounts import AccountPool; "
        "from providers.syntx._config import ProviderConfig; "
        "p=AccountPool(ProviderConfig(state_dir=Path(sys.argv[1]))); "
        "asyncio.run(p.add_authorized([{'token':sys.argv[2],'status':'active'}],time.monotonic()+5))"
    )
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(tmp_path), f"test_{i}"],
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for i in range(8)
    ]
    try:
        for worker in workers:
            _, stderr = worker.communicate(timeout=15)
            assert worker.returncode == 0, stderr.decode()
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()
                worker.wait()
    records = json.loads((tmp_path / "accounts_syntx.json").read_text())
    assert {item["token"] for item in records} == {f"test_{i}" for i in range(8)}
