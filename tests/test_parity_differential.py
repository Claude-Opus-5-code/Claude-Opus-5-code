"""DIFFERENTIAL PARITY: original source vs migrated package (README §23).

This is the strongest offline evidence available for this provider. It loads the
IMMUTABLE original script from `workspace/inbox/` (never modified — README §9),
monkeypatches only `requests` inside that module, and drives BOTH the original
`send_chat_request` and the migrated `generate_text` through the SAME scripted
transport.

It then compares the resulting HTTP traffic semantically (README §23: not
byte-for-byte, because uuids/device ids/ips are random by design):

    method, url shape, headers, payload, timeout, stream flag, ordering

Equivalence is defined at the semantic level; the nondeterministic fields are
normalized before comparison and asserted separately for shape.

WHY THIS MATTERS: §44A forbids concluding "interfaces match, therefore behavior
matches". This test compares actual emitted requests, not interfaces.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    REPO_ROOT
    / "workspace"
    / "inbox"
    / "gemini--flash"
    / "01.02_overchat_gpt5_2_gemini3_5_bypass.py"
)
PROVIDER_PARENT = REPO_ROOT / "providers" / "finished"

if str(PROVIDER_PARENT) not in sys.path:
    sys.path.insert(0, str(PROVIDER_PARENT))

from overchat.config import OverchatConfig  # noqa: E402
from overchat.operations.text_generation import generate_text  # noqa: E402
from overchat.tests.conftest import (  # noqa: E402
    FakeResponse,
    RecordingTransport,
    delta_frame,
    error_frame,
    sse,
)

DONE = [b"data: [DONE]"]
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
PROMPT = "قارن بين النماذج"


# --------------------------------------------------------------------------
# Loading the ORIGINAL module without importing `requests` for real
# --------------------------------------------------------------------------


def _load_original(transport: RecordingTransport) -> ModuleType:
    """Load the immutable original script with `requests` replaced.

    The file is read but NEVER written (README §9). We inject a fake `requests`
    module into the module's namespace after execution, so the source's own
    `import requests` is neutralized for the duration of the test.

    SOURCE IMMUTABILITY HAZARD (README §9): the original persists its reply via
    `BASE_DIR / cfg.output_file` (source L309-311), where `BASE_DIR` is the
    SCRIPT'S OWN directory (source L98:
    `BASE_DIR = pathlib.Path(__file__).resolve().parent`). Executing the source
    unmodified therefore creates `chat_reply.txt` INSIDE
    `workspace/inbox/gemini--flash/`, which pollutes the immutable source set
    and breaks the §10 source tree hash. We repoint the module-level `BASE_DIR`
    at a per-load temporary directory so the side-effect file lands outside the
    repository.

    This is a test-harness redirection only (README §18 mechanical adaptation
    for testability): it changes no request, header, payload, or parsing
    behavior, and the write itself still executes so the code path stays
    covered. The source file on disk is never written.
    """
    assert SOURCE_PATH.exists(), f"original source missing: {SOURCE_PATH}"

    spec = importlib.util.spec_from_file_location("overchat_original_ref", SOURCE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    # Prevent the script's __main__ guard from running anything.
    module.__name__ = "overchat_original_ref"

    # Loading by file path makes CPython drop a `__pycache__/` next to the
    # source, i.e. inside the immutable inbox (README §9 + §48 cache hygiene).
    # Suppress bytecode writing for the duration of the load.
    _prev_dont_write = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = _prev_dont_write

    # Redirect the reply-file side effect away from the immutable inbox (§9).
    # `tempfile.mkdtemp` is not auto-removed, so the write target survives for
    # the whole test; it lives under the OS temp dir, never in the repo.
    module.BASE_DIR = Path(tempfile.mkdtemp(prefix="overchat_orig_ref_"))  # type: ignore[attr-defined]

    # Replace the real `requests` with the recording transport shim. The source
    # calls requests.get/patch/post with keyword args that our transport
    # already mirrors.
    module.requests = SimpleNamespace(  # type: ignore[attr-defined]
        get=transport.get,
        post=transport.post,
        patch=transport.patch,
    )
    # Silence the source's heavy stdout output; printing is not under test here.
    module.print = lambda *a, **k: None  # type: ignore[attr-defined]
    module.sys = SimpleNamespace(  # type: ignore[attr-defined]
        stdout=SimpleNamespace(write=lambda *_a: None, flush=lambda: None),
        platform="linux",
    )
    return module


def _script_transport(frames: list[dict[str, Any]] | None = None) -> RecordingTransport:
    """Transport scripted for the happy path of the 4-step flow."""
    frames = [delta_frame("مرحبا")] if frames is None else frames
    lines = sse(frames) + DONE

    def handler(method: str, url: str) -> FakeResponse:
        if url.endswith("/v1/auth/me"):
            return FakeResponse(200, payload={"id": "guest-1"})
        if url.endswith("/v2/chat/responses"):
            return FakeResponse(200, lines=list(lines))
        return FakeResponse(200, payload={})

    return RecordingTransport(handler=handler)


def _normalize(calls: list[Any]) -> list[dict[str, Any]]:
    """Reduce recorded calls to semantically comparable form.

    Normalizes the intentionally-random values (uuid4 chat/message ids, the
    16-char device uuid, the fake IP) to stable placeholders so that genuine
    differences stand out.
    """
    normalized: list[dict[str, Any]] = []

    for call in calls:
        url = UUID_RE.sub("<UUID>", call.url)

        headers = dict(call.headers)
        if "x-device-uuid" in headers:
            headers["x-device-uuid"] = "<DEVICE_UUID>"
        for name in ("X-Forwarded-For", "X-Real-IP", "Client-IP"):
            if name in headers:
                headers[name] = "<FAKE_IP>"

        body: Any = None
        if call.body is not None:
            body = json.loads(call.body)
            if isinstance(body, dict):
                if "chatUuid" in body:
                    body["chatUuid"] = "<UUID>"
                if "chatId" in body:
                    body["chatId"] = "<UUID>"
                for message in body.get("messages", []):
                    if "id" in message:
                        message["id"] = "<UUID>"

        normalized.append(
            {
                "method": call.method,
                "url": url,
                "headers": headers,
                "body": body,
                "timeout": call.timeout,
                "stream": call.stream,
            }
        )

    return normalized


@pytest.fixture()
def original_and_migrated() -> tuple[list[dict[str, Any]], list[dict[str, Any]], Any, Any]:
    """Run BOTH implementations against equivalent transports."""
    original_transport = _script_transport()
    module = _load_original(original_transport)
    original_cfg = module.Config()
    original_reply = module.send_chat_request(PROMPT, original_cfg, "parity")

    migrated_transport = _script_transport()
    migrated_result = generate_text(PROMPT, OverchatConfig(), migrated_transport)

    return (
        _normalize(original_transport.calls),
        _normalize(migrated_transport.calls),
        original_reply,
        migrated_result,
    )


# --------------------------------------------------------------------------
# The comparisons
# --------------------------------------------------------------------------


def test_original_source_is_loadable_and_unmodified() -> None:
    """Guard: the parity evidence is only meaningful if the file is pristine."""
    import hashlib

    digest = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    assert digest == "d513c0359c8aada2801a3d847466cf2d0e865e33fd05f0d180c902187cbbc470"


def test_same_number_of_requests(original_and_migrated) -> None:
    original, migrated, _, _ = original_and_migrated
    assert len(original) == len(migrated) == 4


def test_identical_method_and_url_sequence(original_and_migrated) -> None:
    """The contractual 4-step flow must match exactly, including order."""
    original, migrated, _, _ = original_and_migrated
    assert [(c["method"], c["url"]) for c in original] == [
        (c["method"], c["url"]) for c in migrated
    ]


def test_identical_timeouts_per_step(original_and_migrated) -> None:
    original, migrated, _, _ = original_and_migrated
    assert [c["timeout"] for c in original] == [c["timeout"] for c in migrated]
    assert [c["timeout"] for c in migrated] == [15, 15, 15, 120]


def test_identical_stream_flags(original_and_migrated) -> None:
    original, migrated, _, _ = original_and_migrated
    assert [c["stream"] for c in original] == [c["stream"] for c in migrated]


def test_identical_headers_on_every_call(original_and_migrated) -> None:
    """Header parity is where a rewrite most easily drifts (an omitted quirk
    header, a changed Accept, a 'cleaned up' authorization)."""
    original, migrated, _, _ = original_and_migrated
    for index, (a, b) in enumerate(zip(original, migrated)):
        assert a["headers"] == b["headers"], f"header mismatch on call {index}: {a['url']}"


def test_identical_payloads_on_every_call(original_and_migrated) -> None:
    original, migrated, _, _ = original_and_migrated
    for index, (a, b) in enumerate(zip(original, migrated)):
        assert a["body"] == b["body"], f"payload mismatch on call {index}: {a['url']}"


def test_full_normalized_traffic_is_equivalent(original_and_migrated) -> None:
    """The single strongest assertion: the entire normalized request sequence is
    identical between original and migrated implementations."""
    original, migrated, _, _ = original_and_migrated
    assert original == migrated


def test_identical_reply_text(original_and_migrated) -> None:
    """Behavioral outcome parity, not just request parity."""
    _, _, original_reply, migrated_result = original_and_migrated
    assert original_reply == "مرحبا"
    assert migrated_result.text == original_reply


def test_authorization_undefined_present_in_both(original_and_migrated) -> None:
    """Explicitly pin the quirk that a 'cleanup' rewrite would delete."""
    original, migrated, _, _ = original_and_migrated
    assert original[3]["headers"]["authorization"] == "undefined"
    assert migrated[3]["headers"]["authorization"] == "undefined"


def test_empty_system_message_present_in_both(original_and_migrated) -> None:
    original, migrated, _, _ = original_and_migrated
    for calls in (original, migrated):
        messages = calls[3]["body"]["messages"]
        assert messages[1]["role"] == "system"
        assert messages[1]["content"] == ""


def test_random_fields_are_actually_random_and_well_formed() -> None:
    """The normalization above must not be hiding a real regression: prove the
    masked fields are genuinely per-request and correctly shaped."""
    t1, t2 = _script_transport(), _script_transport()
    r1 = generate_text(PROMPT, OverchatConfig(), t1)
    r2 = generate_text(PROMPT, OverchatConfig(), t2)

    assert r1.device_uuid != r2.device_uuid
    assert len(r1.device_uuid) == 16 and r1.device_uuid.isalnum()
    assert r1.chat_uuid != r2.chat_uuid
    assert UUID_RE.fullmatch(r1.chat_uuid or "")
    octets = [int(o) for o in r1.spoofed_ip.split(".")]
    assert len(octets) == 4
    assert all(1 <= o <= 255 for o in octets)  # source range, 0 never occurs


# --------------------------------------------------------------------------
# Failure-path parity
# --------------------------------------------------------------------------


def test_auth_failure_parity_original_returns_none_migrated_reports_error() -> None:
    """Source returns None and stops after ONE call; migrated must abort at the
    same point and normalize the failure instead of returning None."""

    def handler(method: str, url: str) -> FakeResponse:
        return FakeResponse(500, text="server down")

    original_transport = RecordingTransport(handler=handler)
    module = _load_original(original_transport)
    original_reply = module.send_chat_request(PROMPT, module.Config(), "parity")

    migrated_transport = RecordingTransport(handler=handler)
    migrated = generate_text(PROMPT, OverchatConfig(), migrated_transport)

    assert original_reply is None
    assert not migrated.ok
    # identical abort point: exactly one call, the auth GET
    assert len(original_transport.calls) == len(migrated_transport.calls) == 1
    assert original_transport.calls[0].url.endswith("/v1/auth/me")
    assert migrated_transport.calls[0].url.endswith("/v1/auth/me")


def test_generation_failure_parity() -> None:
    """A non-2xx on the stream: original returns None, migrated normalizes, and
    BOTH have made the same four calls."""

    def handler(method: str, url: str) -> FakeResponse:
        if url.endswith("/v1/auth/me"):
            return FakeResponse(200, payload={"id": "guest-1"})
        if url.endswith("/v2/chat/responses"):
            return FakeResponse(502, text="Bad Gateway")
        return FakeResponse(200, payload={})

    original_transport = RecordingTransport(handler=handler)
    module = _load_original(original_transport)
    original_reply = module.send_chat_request(PROMPT, module.Config(), "parity")

    migrated_transport = RecordingTransport(handler=handler)
    migrated = generate_text(PROMPT, OverchatConfig(), migrated_transport)

    assert original_reply is None
    assert not migrated.ok
    assert migrated.error is not None
    assert migrated.error.category == "provider_unavailable"
    assert _normalize(original_transport.calls) == _normalize(migrated_transport.calls)


def test_in_stream_error_event_parity() -> None:
    """The source treats an `error` frame as NON-terminal and still returns the
    accumulated text. Migrated must produce the same reply."""
    frames = [delta_frame("قبل "), error_frame("upstream hiccup"), delta_frame("بعد")]

    original_transport = _script_transport(frames)
    module = _load_original(original_transport)
    original_reply = module.send_chat_request(PROMPT, module.Config(), "parity")

    migrated_transport = _script_transport(frames)
    migrated = generate_text(PROMPT, OverchatConfig(), migrated_transport)

    assert original_reply == "قبل بعد"
    assert migrated.text == original_reply
    assert migrated.ok  # non-terminal, so not a failure
    assert migrated.stream_errors == ["upstream hiccup"]


def test_malformed_frame_parity() -> None:
    """Both implementations must silently skip unparsable SSE frames."""
    lines = [
        b"data: {not json",
        b"data: " + json.dumps(delta_frame("ok")).encode(),
        b": comment",
        b"data: [DONE]",
    ]

    def handler(method: str, url: str) -> FakeResponse:
        if url.endswith("/v1/auth/me"):
            return FakeResponse(200, payload={"id": "guest-1"})
        if url.endswith("/v2/chat/responses"):
            return FakeResponse(200, lines=list(lines))
        return FakeResponse(200, payload={})

    original_transport = RecordingTransport(handler=handler)
    module = _load_original(original_transport)
    original_reply = module.send_chat_request(PROMPT, module.Config(), "parity")

    migrated_transport = RecordingTransport(handler=handler)
    migrated = generate_text(PROMPT, OverchatConfig(), migrated_transport)

    assert original_reply == "ok"
    assert migrated.text == original_reply


def test_model_override_parity() -> None:
    """Selecting `gpt-5-2` must produce identical payloads in both."""
    original_transport = _script_transport()
    module = _load_original(original_transport)
    cfg = module.Config()
    cfg.persona_id = "gpt-5-2"
    cfg.model = cfg.available_models["gpt-5-2"]["model"]
    module.send_chat_request(PROMPT, cfg, "parity")

    migrated_transport = _script_transport()
    generate_text(
        PROMPT,
        OverchatConfig().with_values(persona_id="gpt-5-2", model="gpt-5.2-2025-12-11"),
        migrated_transport,
    )

    assert _normalize(original_transport.calls) == _normalize(migrated_transport.calls)


def test_long_prompt_truncation_parity() -> None:
    """The title-only 300-char truncation must match exactly."""
    long_prompt = "ب" * 5000

    original_transport = _script_transport()
    module = _load_original(original_transport)
    module.send_chat_request(long_prompt, module.Config(), "parity")

    migrated_transport = _script_transport()
    generate_text(long_prompt, OverchatConfig(), migrated_transport)

    original = _normalize(original_transport.calls)
    migrated = _normalize(migrated_transport.calls)

    assert original[1]["body"]["userPrompt"] == migrated[1]["body"]["userPrompt"]
    assert len(migrated[1]["body"]["userPrompt"]) == 300
    assert migrated[3]["body"]["messages"][0]["content"] == long_prompt
    assert original == migrated


# --------------------------------------------------------------------------
# SOURCE IMMUTABILITY GUARD (README §9 / §10)
# --------------------------------------------------------------------------


def test_running_original_does_not_pollute_immutable_inbox() -> None:
    """Executing the ORIGINAL must not create/modify files in `workspace/inbox/`.

    Regression guard for a real defect in this harness: the source writes its
    reply to `BASE_DIR / cfg.output_file` with `BASE_DIR` = the script's own
    directory, so an unredirected load dropped `chat_reply.txt` into the
    immutable source set and invalidated the §10 source tree hash.

    This asserts the directory inventory and the source's own SHA-256 are both
    unchanged across a full generation run, and that the reply file really was
    written somewhere else (proving the code path executed rather than being
    skipped).
    """
    import hashlib

    inbox_dir = SOURCE_PATH.parent

    def inventory() -> set[str]:
        return {p.name for p in inbox_dir.iterdir()}

    def source_digest() -> str:
        return hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()

    # Start from a clean baseline so a cache dir left by an earlier test in the
    # same session cannot mask a genuine new pollution.
    for stale in inbox_dir.glob("__pycache__"):
        if stale.is_dir():
            for child in stale.iterdir():
                child.unlink()
            stale.rmdir()

    before_files = inventory()
    before_hash = source_digest()
    assert before_files == {SOURCE_PATH.name}, (
        f"inbox is not pristine before the run: {before_files}"
    )

    transport = _script_transport()
    module = _load_original(transport)
    reply = module.send_chat_request(PROMPT, module.Config(), "immutability")

    # The generation path really ran (otherwise this test would be vacuous).
    assert reply == "مرحبا"

    assert inventory() == before_files, (
        "executing the original created or removed files inside the immutable "
        f"inbox: {inventory() ^ before_files}"
    )
    assert source_digest() == before_hash, "the original source file was modified"

    # And the side-effect write landed in the redirected temp dir instead.
    written = module.BASE_DIR / module.Config().output_file
    assert written.exists(), "reply file was not written to the redirected BASE_DIR"
    assert written.read_text(encoding="utf-8") == "مرحبا"
    assert inbox_dir not in written.parents
