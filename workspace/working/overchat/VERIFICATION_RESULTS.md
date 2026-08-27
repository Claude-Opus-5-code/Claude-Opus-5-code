# VERIFICATION RESULTS — Overchat provider, revision r1

Every row below was produced by executing the stated command in this repository
during this cycle. Nothing here is carried over from a previous chat, a commit
message, or `WORK_STATE.json` (README §39: those are explicitly not gate
evidence).

* Provider key: `overchat`
* Revision: `r1`
* Source: `workspace/inbox/gemini--flash/01.02_overchat_gpt5_2_gemini3_5_bypass.py`
* Source SHA-256: `d513c0359c8aada2801a3d847466cf2d0e865e33fd05f0d180c902187cbbc470`
  (403 lines, 20308 bytes — re-verified unchanged at the end of this cycle)
* Source tree SHA-256: `5cb5f4f423f44a6ed28341002ff867aa315cb9cc24d3f06bcf5cf0645936daa9`
* Finished package: `providers/finished/overchat/`

---

## 1. Gate results

| Gate | Command | Result |
| --- | --- | --- |
| Repo-level tests | `python3 -m pytest -q` | **PASS** — 64 passed |
| Full suite incl. provider package | `python3 -m pytest tests providers/finished/overchat/tests -o addopts=""` | **PASS** — 291 passed |
| Repository verification | `bash engineering/verification/check_provider_repo.sh` | **PASS** (`RESULT: PASS`, 8/8 checks) |
| Secret scan | included in the script above | **PASS** — `secret scan clean` |
| Cache hygiene | `git ls-files \| grep -E 'pytest_cache\|__pycache__'` | **PASS** — no cache files tracked |
| Standalone certification | provider driven with `workspace/working/overchat` moved aside | **PASS** — see §3 |
| Live verification | real calls to `api.overchat.ai` | **PASS** — see §4 |
| mypy | not installed, no config in `pyproject.toml` | `NOT_CONFIGURED` (README §40) |
| ruff | `[tool.ruff] line-length = 100` present, binary absent | `NOT_CONFIGURED` (declared-but-unavailable; not run, not claimed) |
| import-linter | not installed, no config | `NOT_CONFIGURED` |

`pyproject.toml` sets `testpaths = ["tests"]`, so the bare `pytest -q` invocation
collects **only** the 64 repo-level tests. The provider package's own 227 tests
must be requested explicitly. Both numbers are reported above rather than
quoting the larger one from the smaller command.

### Test distribution (291 total)

| File | Tests |
| --- | --- |
| `providers/finished/overchat/tests/test_config.py` | 7 |
| `providers/finished/overchat/tests/test_errors.py` | 37 |
| `providers/finished/overchat/tests/test_headers.py` | 10 |
| `providers/finished/overchat/tests/test_health.py` | 13 |
| `providers/finished/overchat/tests/test_legacy.py` | 19 |
| `providers/finished/overchat/tests/test_models.py` | 15 |
| `providers/finished/overchat/tests/test_operations.py` | 35 |
| `providers/finished/overchat/tests/test_parser.py` | 20 |
| `providers/finished/overchat/tests/test_provider.py` | 36 |
| `providers/finished/overchat/tests/test_request.py` | 20 |
| `providers/finished/overchat/tests/test_session.py` | 15 |
| `tests/test_parity_differential.py` | 19 |
| `tests/contract/test_overchat_provider_contract.py` | 23 |
| other `tests/contract/*` (platform contracts) | 22 |

---

## 2. Defects found and fixed during this verification pass

Verification is only meaningful if it can fail. It did, twice.

### 2.1 The parity harness polluted the immutable source directory (README §9)

The original script computes
`BASE_DIR = pathlib.Path(__file__).resolve().parent` (source L98) and saves its
reply to `BASE_DIR / cfg.output_file` (source L309-311). Because
`tests/test_parity_differential.py` executes the real source file in place,
every parity run created
`workspace/inbox/gemini--flash/chat_reply.txt` — a **new file inside the
immutable source set**, which invalidates the §10 source tree hash. Loading by
file path also dropped a `__pycache__/` directory in the same place.

Fix, both inside `_load_original`:

* `module.BASE_DIR` is repointed at a per-load `tempfile.mkdtemp()` directory,
  so the write still executes (the code path stays covered) but lands outside
  the repository;
* `sys.dont_write_bytecode` is set for the duration of `exec_module`, so no
  `__pycache__` is created next to the source.

The pre-existing stray `chat_reply.txt` and `__pycache__` were removed. The
source file's own SHA-256 is unchanged and was never written.

Added `test_running_original_does_not_pollute_immutable_inbox`, which asserts
the inbox's file inventory and the source's SHA-256 are identical across a full
generation run, and that the reply file materialized in the redirected temp
directory instead. Mutation-checked: deleting the `BASE_DIR` redirection makes
this test fail with
`PosixPath('.../workspace/inbox/gemini--flash') not in PosixPath.parents`.

### 2.2 A preserved parsing quirk was asserted in a way that could not fail (README §33)

Source L283 (`if delta:`) skips falsy deltas entirely. The existing test was:

```python
assert accumulate_reply([d(""), d("real"), d("")]) == "real"
```

This cannot detect the guard's removal, because concatenating `""` is invisible
— flipping `if delta:` to `if True:` still yields `"real"`. The behavior is only
observable at event/chunk granularity, which is exactly what a streaming
consumer sees.

Added `test_falsy_delta_emits_no_event_at_all`, asserting
`list(iter_events(...)) == [DeltaEvent("a"), DeltaEvent("b")]` and that no
zero-length chunk is ever surfaced. Mutation-checked: the mutation that
previously survived is now caught.

---

## 3. Standalone certification (README §37, §44H)

Procedure: `workspace/working/overchat/` was moved out of the repository, then
the provider was exercised from a neutral working directory (`/tmp`) with only
`providers/finished/` on `sys.path` — no repo root, no `conftest.py`, no
migration workspace.

Observed:

```
workspace/working -> [.gitkeep ]
provider_id  : overchat
capabilities : ['streaming', 'text_generation']
models       : ['gpt-5.2-2025-12-11', 'google/gemini-3.5-flash', 'openai/gpt-4.1-nano']
generated    : 'hello' | model: google/gemini-3.5-flash
call flow    : ['GET /v1/auth/me',
                'PATCH /v1/chat/<uid>/<uuid>/generateChatTitle',
                'POST /v1/chat/<uid>',
                'POST /v2/chat/responses']
stream chunks: ['he', 'llo']
workspace modules leaked: []
STANDALONE_OK
```

* the 4-step request sequence is intact with the workspace absent;
* streaming yields per-delta chunks;
* no module resolved from `workspace`/`working`;
* `providers/finished/overchat/tests` → **226 passed** with the workspace gone.

Unsupported capabilities are rejected rather than silently ignored:
`run_operation('image_generation', ...)` raises `OverchatError`
("Overchat does not support capability 'image_generation'."), as do
`generate_image`, `create_embeddings`, and `run_provider_agent`.

Two probe attempts in this cycle used **guessed** APIs (`OverchatProvider()`
with no transport; a non-existent `execute()` method) and failed loudly. Both
were corrected by reading `provider.py` first. Recorded here because a guessed
signature that happens to pass is a hidden false positive (README §33).

---

## 4. Live / integration verification (README §36) — upgraded this cycle

The previous cycle recorded `LIVE_VERIFICATION = PARTIAL`: guest auth observed
200, but the generation path was blocked by an upstream 502. **That block has
cleared, and the generation path is now verified live.**

Full detail: `workspace/working/overchat/evidence/live_generation_parity.json`.

| Probe | Result |
| --- | --- |
| A: `GET /v1/auth/me` with no device headers | **401 Unauthorized** — guest admission is not unconditional; the header block is load-bearing |
| B: `GET /v1/auth/me` with `overchat.runtime.headers.build_mobile_headers()` | **200**, `isGuest: true`, `id` present — the *migrated* builder provisions a guest against the real upstream |
| C: live generation through the migrated V3 adapter | **SUCCESS** — model `google/gemini-3.5-flash`, reply `'OK'`, no stream errors |
| D: live generation through the **ORIGINAL** inbox script | **SUCCESS** — reply `'OK'` |
| E: IP-spoof header ablation (A/B on the same endpoint) | **200 with** and **200 without** the 3 headers → `ADMISSION_DIFFERS = False` |

**Live differential parity (C vs D): equivalent.** Both the original and the
migrated provider completed the same 4-step flow against the real API in the
same session and returned `'OK'`. Equivalence is semantic (README §23), with a
prompt chosen to be effectively deterministic so the comparison is meaningful.

Probe A is worth keeping: it proves the preserved device-header behavior is
functionally required, not cosmetic. No credential exists for this provider
(identity is a throwaway guest), and no `id`, `email`, `deviceId`, or IP value
was printed or persisted (README §38).

---

## 5. Red-team sweep (README §44)

| # | Exploit | How it was attacked | Outcome |
| --- | --- | --- | --- |
| A | Fake parity ("interfaces match") | Parity tests compare *emitted HTTP traffic* (method, URL, headers, payload, ordering) from original vs migrated through one shared recording transport, not interfaces | **BLOCKED** |
| B | Mock-only completion | Real network calls executed against `api.overchat.ai`; both original and migrated generated live text (§4) | **BLOCKED** |
| C | Silent logic deletion | 7 mutations applied to preserved quirks; see table below | **BLOCKED** (after fixing one real gap) |
| D | Invented capability | Every manifest `persona_id`/`model` checked to appear verbatim in the source; only endpoint in source is `https://api.overchat.ai`; capability map is all-`false` except `chat` | **BLOCKED** — `NO_INVENTED_MODELS = True` |
| E | Limitation shortcut | The one previously-claimed limitation (live generation) was retried and closed, not accepted | **BLOCKED** |
| F | Tooling policy invention | mypy/ruff/import-linter absent → reported `NOT_CONFIGURED`; no tool installed to manufacture a gate | **BLOCKED** |
| G | Stale state trust | `WORK_STATE.json` claimed `ARCHIVE: DONE` and cited two reports; filesystem showed the archive directory and both reports **did not exist** | **BLOCKED** — see §6 |
| H | Workspace dependency | Provider exercised with `workspace/working/overchat` physically moved away | **BLOCKED** |
| I | Credential contamination | Secret scan clean; every "secret"-matching string in the package is a test *asserting redaction* | **BLOCKED** |
| J | Green-status optimization | The two defects in §2 were fixed by strengthening tests/harness, never by relaxing an assertion; one new test was added specifically because a mutation survived | **BLOCKED** |

### Mutation results (§44C detail)

Each mutation was applied to the finished package, the full 291-test suite was
run, then the file was restored byte-for-byte.

| Mutation | Detected? |
| --- | --- |
| Remove `headers["authorization"] = "undefined"` | CAUGHT |
| `data: ` stripped everywhere instead of first occurrence only | CAUGHT |
| `TITLE_PROMPT_LIMIT` 300 → 200 | CAUGHT |
| `DONE_SENTINEL` `[DONE]` → `[done]` | CAUGHT |
| Remove quarantined `X-Forwarded-For` header | CAUGHT |
| Shrink `IP_SPOOF_HEADER_NAMES` tuple | CAUGHT |
| `if delta:` → `if True:` (falsy-delta skip, L283) | **NOT CAUGHT** → gap closed (§2.2), now CAUGHT |

Working tree confirmed restored after every mutation run.

---

## 6. State reconciliation (README §8, §44G)

`WORK_STATE.json` overstated three stages. Filesystem evidence at the start of
this cycle:

| WORK_STATE claim | Filesystem reality |
| --- | --- |
| `ARCHIVE: DONE` → `workspace/archive/overchat/r1/` | **Did not exist** — `workspace/archive/` contained only `.gitkeep` |
| `STANDALONE_CERTIFICATION: DONE` — "see VERIFICATION_RESULTS.md" | `VERIFICATION_RESULTS.md` **did not exist** |
| Cycle referenced a migration report | `MIGRATION_REPORT.md` **did not exist** |

Confirmed accurate: source identity (hash re-matched exactly), the finished
package's 36 files, the working documents, and `cycle_status: IN_PROGRESS`.

The archive and both reports were produced in this cycle. `WORK_STATE.json` was
then rewritten to match verified evidence.

---

## 7. Acceptance matrix (README §53)

Source line references are to the immutable inbox script.

| Behavior Area | Source Evidence | Target | Deterministic Test | Differential Test | Live Evidence | Classification | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Models (static discovery) | L58-70 `available_models` | `discovery/models.py` | `test_models.py` (15) | traffic `model` field compared | Probe C used `google/gemini-3.5-flash` | SUPPORTED | none |
| Unknown-model passthrough | L364-370 | `discovery/models.py:resolve_model` | `test_models.py` | `test_model_override_parity` | — | SUPPORTED | not exercised live (would need an invalid model against prod) |
| Authentication (guest, no credential) | L191-203 | `runtime/session.py` | `test_session.py` (15) | auth call compared | Probe B: **200**, `isGuest: true` | SUPPORTED | none |
| Device/mobile headers | L104-137 | `runtime/headers.py` | `test_headers.py` (10) | headers compared per call | Probe A (401 without) vs B (200 with) | SUPPORTED | none |
| IP-spoof headers | L100-102, header block | `runtime/headers.py` | `test_headers.py`; 2 mutations CAUGHT | included in header comparison | sent in all live probes | QUARANTINED | default-ON to match source; disabling is an operator decision |
| `authorization: undefined` quirk | request builder | `runtime/request.py` | `test_request.py`; mutation CAUGHT | `test_authorization_undefined_present_in_both` | sent live | SUPPORTED | none |
| Transport / 4-step ordering | L191-271 | `runtime/session.py`, `operations/` | `test_operations.py` (35) | `test_full_normalized_traffic_is_equivalent` | Probes C+D same sequence | SUPPORTED | none |
| Request construction | L205-271 | `runtime/request.py` | `test_request.py` (20) | payload semantics compared | live 200s | SUPPORTED | none |
| Title truncation (300 chars) | title call | `runtime/request.py:TITLE_PROMPT_LIMIT` | mutation CAUGHT | `test_long_prompt_truncation_parity` | — | SUPPORTED | none |
| Streaming (SSE deltas) | L272-286 | `runtime/parser.py`, `operations/` | `test_parser.py` (20) | delta accumulation compared | Probes C+D streamed to `'OK'` | SUPPORTED | none |
| Falsy-delta skip | L283 | `runtime/parser.py` | `test_falsy_delta_emits_no_event_at_all` (**added**) | — | — | SUPPORTED | none |
| `[DONE]` termination | L277-278 | `runtime/parser.py` | mutation CAUGHT | — | live streams terminated on `[DONE]` | SUPPORTED | none |
| In-stream `error` event (non-terminal) | L287-288 | `runtime/parser.py` | `test_parser.py` | `test_generation_failure_parity` | not observed live | SUPPORTED | upstream did not emit one during probes |
| Per-frame exception swallowing | L289-290 | `runtime/parser.py` | `test_parser.py` | — | — | SUPPORTED | none |
| Other SSE event types | only 2 types exist in source | — | `test_unknown_event_types_are_ignored` | — | only delta observed | **UNKNOWN** | intrinsic: source establishes no other types; inventing handling would violate §16 |
| Error normalization | L291+ status handling | `runtime/errors.py` | `test_errors.py` (37) | `test_generation_failure_parity` | 401 from Probe A classifies correctly | SUPPORTED | none |
| Secret redaction in errors | — (V3 requirement) | `runtime/errors.py` | `test_errors.py`, `test_session.py` | — | — | SUPPORTED | none |
| Health check | — (V3 boundary) | `health.py` | `test_health.py` (13) | — | reachability confirmed | SUPPORTED | degenerate by design: no credential to validate |
| Retries / backoff / polling | **absent** in source | not implemented | — | — | — | UNSUPPORTED | correctly absent (§16) |
| Accounts / pools | **absent** in source | not implemented | `test_provider.py` asserts `account_pool_supported: false` | — | — | UNSUPPORTED | correctly absent |
| Uploads / downloads / assets | **absent** in source | rejected stubs | `test_provider.py` | — | — | UNSUPPORTED | correctly absent |
| Provider-native agent | **absent** in source | rejected stub | `test_provider.py` | — | — | UNSUPPORTED | correctly absent |
| Reply-file persistence | L309-311 | `legacy/file_io.py` | `test_legacy.py` (19) | — | — | SANITIZED | relocated out of provider runtime; path is caller-supplied |
| CLI / banner / colors / stats | L1-57, L138-190, L300-308, L371-403 | `legacy/` (6 modules) | `test_legacy.py` | — | — | SANITIZED | preserved, not silently dropped (§17) |

---

## 8. Honest status

**`VERIFIED_WITH_LIMITATIONS`**

Justification: every `SUPPORTED` behavior has source evidence, a target
mapping, and a deterministic test; the whole request flow has offline
differential parity against the original; and the auth *and* generation paths
are now verified live on both the original and migrated code. The finished
package passes standalone certification with the migration workspace removed.

The single remaining limitation is genuinely intrinsic (README §50): the
upstream's full SSE event vocabulary is unknowable from a source that
establishes exactly two event types, and inventing handling for hypothetical
types is forbidden by §16. It is classified `UNKNOWN`, not `UNVERIFIED`.

`COMPLETE` is not claimed: it would require enumerating upstream event types
that no available evidence can enumerate.

### Open operator decision (carried forward)

The quarantined IP-spoof headers (`X-Forwarded-For`, `X-Real-IP`, `Client-IP`)
are preserved and default-ON to match source behavior. This cycle sharpened the
evidence with a controlled ablation (Probe E): the same endpoint returns
**200 with and 200 without** the three headers, so they do **not** affect guest
admission — whereas the wider device-header set clearly does (Probe A returns
401 without it). The spoof subset is therefore confirmed non-functional for
admission, yet still preserved: README §17/§18 forbid dropping source behavior
merely because it looks unnecessary, and the server may use these values for
purposes not observable from a status code. Removing them would be a deliberate
behavior divergence requiring an operator decision (README §43); it was not
taken unilaterally.

### Activation

`disabled` / `integration_pending`. README §21 forbids auto-enabling
production routing, and no governance file in this repository authorizes
activation — live success does not change that.
