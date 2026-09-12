"""Security regressions: diagnostic privacy, import isolation and shared budgets."""

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from providers.syntx._accounts import AccountPool
from providers.syntx._config import ProviderConfig
from providers.syntx._transport import Deadline, Transport, UpstreamFailure
from providers.syntx._upstream import generate


async def test_library_diagnostics_private_but_other_tasks_keep_logs(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    entered, release = asyncio.Event(), asyncio.Event()

    async def respond(request):
        logging.getLogger("httpcore.http11").debug("private upstream details")
        entered.set()
        await release.wait()
        return httpx.Response(200, json={})

    async def private_request():
        async with Transport(
            "sentinel", Deadline.after_ms(1000), transport=httpx.MockTransport(respond)
        ) as wire:
            await wire.request("POST", "chats")

    task = asyncio.create_task(private_request())
    await entered.wait()
    logging.getLogger("httpx").info("unrelated concurrent request is visible")
    release.set()
    await task
    cfg = ProviderConfig(state_dir=tmp_path, maintenance_enabled=False)
    await AccountPool(cfg).add_authorized(
        [{"token": "sentinel", "status": "active"}], time.monotonic() + 1
    )
    assert "unrelated concurrent request is visible" in caplog.text
    for secret in ("api.syntx.ai", "private upstream details", "accounts_syntx.json", "sentinel"):
        assert secret not in caplog.text


def test_import_has_no_network_tasks_or_file_creation(tmp_path):
    package = Path(__file__).resolve().parents[2] / "providers" / "syntx"
    before = sorted(p.name for p in package.iterdir())
    code = """
import asyncio, socket, subprocess
from pathlib import Path
from unittest.mock import patch

def forbidden(*args, **kwargs):
    raise AssertionError('import side effect')

with patch.object(socket.socket, 'connect', forbidden), \\
     patch.object(socket, 'getaddrinfo', forbidden), \\
     patch.object(subprocess, 'Popen', forbidden), \\
     patch.object(Path, 'write_text', forbidden), \\
     patch.object(Path, 'write_bytes', forbidden), \\
     patch.object(asyncio, 'create_task', forbidden):
    from providers.syntx import DEFINITION, HANDLERS
    assert len(HANDLERS) == 2
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in package.iterdir()) == before


async def test_multiple_stages_share_one_deadline(tmp_path):
    cfg = ProviderConfig(state_dir=tmp_path, maintenance_enabled=False)
    pool = AccountPool(cfg)
    await pool.add_authorized([{"token": "test", "status": "active"}], time.monotonic() + 1)
    stages = []

    async def respond(request):
        stages.append(request.url.path)
        await asyncio.sleep(0.04)
        if request.url.path.endswith("/chats"):
            return httpx.Response(201, json={"uuid": str(uuid4())})
        return httpx.Response(200, json={"job_id": "j"})

    start = time.monotonic()
    with pytest.raises(UpstreamFailure) as exc:
        await generate(
            model="grok-4.6",
            text="hello",
            timeout_ms=65,
            config=cfg,
            pool=pool,
            transport=httpx.MockTransport(respond),
        )
    assert exc.value.kind == "timeout"
    assert len(stages) == 2
    assert time.monotonic() - start < 0.5


async def test_cancellation_restores_library_logging(caplog):
    caplog.set_level(logging.DEBUG)
    entered = asyncio.Event()

    async def respond(request):
        entered.set()
        await asyncio.sleep(10)

    async def run():
        try:
            async with Transport(
                "test", Deadline.after_ms(1000), transport=httpx.MockTransport(respond)
            ) as wire:
                await wire.request("POST", "chats")
        except asyncio.CancelledError:
            logging.getLogger("httpx").info("logging restored after cancellation")
            raise

    task = asyncio.create_task(run())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert "logging restored after cancellation" in caplog.text
