# MIGRATION REPORT — Overchat provider, revision r1

Companion documents in this directory:

* `CAPABILITY_INVENTORY.md` — 37 numbered capabilities with classifications
* `MIGRATION_MAP.md` — exhaustive source-line → target-symbol mapping
* `MIGRATION_PLAN.md` — target structure and the M1-M8 adaptation table
* `VERIFICATION_RESULTS.md` — executed gates, red-team sweep, acceptance matrix
* `evidence/` — sanitized live-capture artifacts

---

## 1. What was migrated

| | |
| --- | --- |
| Provider key | `overchat` |
| Revision | `r1` |
| Input set | `workspace/inbox/gemini--flash/` (1 file — single logical provider, README §6) |
| Source file | `01.02_overchat_gpt5_2_gemini3_5_bypass.py` |
| Size / lines | 20308 bytes / 403 lines |
| Source SHA-256 | `d513c0359c8aada2801a3d847466cf2d0e865e33fd05f0d180c902187cbbc470` |
| Source tree SHA-256 | `5cb5f4f423f44a6ed28341002ff867aa315cb9cc24d3f06bcf5cf0645936daa9` |
| Sanitized snapshot | not required — the source contains no credential values (guest/no-auth provider) |
| Finished package | `providers/finished/overchat/` |
| Files reorganized | 1 script → 23 runtime/support modules + 13 test modules + manifest |
| Activation | `disabled` / `integration_pending` |

The upstream is a single host: `https://api.overchat.ai`.

### Provider naming

The inbox folder is named `gemini--flash`, but that is a **model** hint, not the
provider identity. The upstream gateway is Overchat, serving three vendor
models; naming the provider `gemini-flash` would collapse Model into Provider
and violate the V3 architecture. The provider key is therefore `overchat`, with
the folder name recorded in `WORK_STATE.json` for traceability.

---

## 2. Target structure

```
providers/finished/overchat/
├── manifest.yaml            # declared capabilities/models, all evidence-backed
├── provider.py              # V3 adapter boundary (the only Core-facing module)
├── config.py                # frozen Config dataclass (source Config)
├── health.py                # V3-required health contract (adapter-added)
├── discovery/models.py      # static 3-model table + unknown-model passthrough
├── operations/
│   └── text_generation.py   # the 4-step flow orchestration
├── runtime/
│   ├── session.py           # transport protocol + guest auth
│   ├── headers.py           # device fingerprint + quarantined IP-spoof headers
│   ├── request.py           # payload/URL construction, title truncation
│   ├── parser.py            # SSE parsing (delta / error / [DONE])
│   └── errors.py            # normalized error categories
├── legacy/                  # CLI-only behavior, preserved not dropped (§17)
│   ├── cli_app.py  banner.py  colors.py  console.py  file_io.py  stats.py
└── tests/                   # 227 tests co-located with the package
```

The four-step upstream flow, preserved in order:

```
GET   /v1/auth/me                                   → guest identity
PATCH /v1/chat/<uid>/<chat_uuid>/generateChatTitle  → title (prompt[:300])
POST  /v1/chat/<uid>                                → chat create
POST  /v2/chat/responses                            → SSE generation
```

---

## 3. Capability classification (37 inventoried)

| Classification | Count | Notes |
| --- | --- | --- |
| SUPPORTED | 24 | migrated with source evidence + deterministic tests |
| SANITIZED | 3 | #17 error normalization, #29 health check, #35 rate-limit mapping — all **additive at the boundary only**, required by V3, absent from the source |
| QUARANTINED | 3 | #4 fake-IP generation, #5 the three IP-spoof headers, #37 their server-side effect |
| UNSUPPORTED | 5 | genuinely absent from the source (see below) |
| UNKNOWN | 1 | #36 non-delta/non-error SSE event types |
| UNVERIFIED | 0 | — |

Declared capabilities: `text_generation`, `streaming`. Nothing else.

**UNSUPPORTED because the source does not contain them** (README §16 forbids
inventing them): retries/backoff, polling/async jobs, account pools/rotation,
file upload/download, provider-native agents. Also absent: dynamic model
discovery, and any OAuth/api-key authentication. Each is declared `false` in
the manifest and raises `unsupported_capability` if called, rather than failing
silently.

---

## 4. Behavior preserved deliberately (README §17)

These look like defects or noise. They are source behavior and were kept:

| Behavior | Source | Why it would have been "cleaned up" |
| --- | --- | --- |
| `authorization: undefined` header sent as a literal string | request builder | Looks like a JS `undefined` leak; a rewrite would drop it. Sent on live requests. |
| `data: ` prefix stripped **only once**, with `count=1` | L276 | A delta whose text contains `data: ` keeps it; a naive `.replace()` would corrupt payloads. |
| Falsy deltas skipped entirely | L283 | Emitting an empty chunk looks harmless but changes what a streaming consumer observes. |
| In-stream `error` events are **non-terminal** | L287-288 | The source prints and keeps reading; "fixing" this to abort would change termination semantics. |
| Per-frame exceptions silently swallowed | L289-290 | Bare `except: pass` looks like a bug; it defines the source's tolerance for malformed frames. |
| Fake IP octets are `1..255`, never `0` | L100-102 | An off-by-one "correction" would change the generated distribution. |
| Title prompt truncated to exactly 300 chars | title call | Arbitrary-looking constant. |
| Exactly 14 device headers, fake IP reused across all three IP headers | L104-125 | Deduplication would alter the request fingerprint. |
| Zero limits mean "no limit" via falsy checks | stats/limits | A `is None` "correction" would change behavior for `0`. |
| CLI banner/colors/stats/reply-file | L1-57, L138-190, L300-311, L371-403 | Not provider logic, but not deleted — relocated to `legacy/`. |

Every item above is pinned by a test. Seven were additionally mutation-tested.

---

## 5. Mechanical adaptations (README §18 — allowed, documented)

M1-M8 are tabulated in `MIGRATION_PLAN.md` §4: script→package split, `print()`→
injected stream/returned events, module-level `requests`→injected transport,
`Config`→frozen dataclass, `available_models`→`MappingProxyType`, `BASE_DIR`→
package dir, raw error prints→normalized error objects, and the added
`include_ip_spoof_headers` flag (default `True` = source behavior).

None changes an endpoint, method, header value, payload field, model name,
parsing rule, or termination condition. The offline differential test compares
emitted traffic from both implementations and would fail if any did.

### Harness-only adaptation

`tests/test_parity_differential.py::_load_original` redirects the original
module's `BASE_DIR` to a temp directory and suppresses bytecode writing during
`exec_module`. This is a **harness** change, not a provider change: it exists
because executing the real source in place was writing `chat_reply.txt` and
`__pycache__/` into `workspace/inbox/`, violating source immutability (§9). No
request behavior is affected and the file-write code path still executes — a
test asserts the reply file lands in the redirected directory.

---

## 6. Verification summary

Full detail in `VERIFICATION_RESULTS.md`. All results below were executed in
this cycle.

* **291 tests pass** (64 repo-level + 227 provider package).
  `testpaths = ["tests"]` means bare `pytest -q` collects only 64; the
  provider's own tests must be requested explicitly.
* **Repository gate PASS** — `check_provider_repo.sh` → `RESULT: PASS` (8/8),
  including `secret scan clean`.
* **Offline differential parity** — original vs migrated driven through one
  shared recording transport; emitted method/URL/headers/payload/ordering
  compared after normalizing intentionally-random values (uuids, device id,
  fake IP).
* **Live verification** — guest auth returns 200 through the *migrated* header
  builder; live generation succeeded through **both** the migrated adapter and
  the original script, both returning `'OK'`. Live differential parity:
  equivalent.
* **Standalone certification** — provider copied to `/tmp/sc_test` with
  `workspace/working/overchat` moved out of the repository: **225 passed,
  2 skipped**; the 2 skips self-declare "Core not on sys.path (standalone
  mode)". Import check confirms 14 `overchat.*` modules all resolved from
  `/tmp/sc_test` and **zero** workspace-derived modules loaded.
* **Red-team sweep §44 A-J** — all applicable exploits blocked; 7 mutations of
  preserved quirks applied, all detected.

### Defects this verification effort found in its own artifacts

1. **Source-immutability violation in the parity harness** — running the
   original created `chat_reply.txt` (and a `__pycache__/`) inside
   `workspace/inbox/`. Fixed; guarded by a test that mutation-testing confirms
   can fail.
2. **A non-failing assertion** — the falsy-delta skip (source L283) was
   asserted only through `accumulate_reply`, where concatenating `""` is
   invisible, so removing the guard still passed. Fixed with an
   event-granularity test; the previously-surviving mutation is now caught.
3. **Tracked cache files** — `.pytest_cache/` was tracked in git despite being
   listed in `.gitignore`, contradicting §48. Untracked in this cycle. Note the
   repo gate cannot catch this: it deletes caches from disk *before* checking,
   so it only ever sees a clean tree. Detection requires `git ls-files`.
4. **Overstated standalone count** — a previous revision of
   `VERIFICATION_RESULTS.md` recorded "226 passed" for the standalone run; the
   real result is 225 passed + 2 skipped. Corrected.

---

## 7. State reconciliation (README §8, §44G)

`WORK_STATE.json` was a recovery pointer, not proof — and it overstated stages.
Re-checked against the filesystem on this resume:

| Claim | Reality when re-checked |
| --- | --- |
| `ARCHIVE: DONE` → `workspace/archive/overchat/r1/` | `workspace/archive/` contained only `.gitkeep`; **no revision directory existed** |
| migration report referenced by §46 | `MIGRATION_REPORT.md` **did not exist** |
| `STANDALONE_CERTIFICATION: DONE` | `VERIFICATION_RESULTS.md` existed and documented it, but the count was wrong; re-executed from scratch |
| `LIVE_VERIFICATION: PARTIAL` (blocked by 502) | Stale — the upstream 502 has cleared; live generation now verified on both implementations |

Accurate claims: source identity (hash re-matched byte-for-byte), the finished
package inventory, the working documents, and `cycle_status: IN_PROGRESS`.

The archive and this report were produced in this cycle, and `WORK_STATE.json`
was rewritten to match verified evidence.

### Toolchain interruption during this cycle

The shell became unresponsive (failing even on `echo`) while
`workspace/working/overchat` was moved aside for standalone certification. Per
§42 a sandbox reset was performed; the reset cleared `/tmp`, which held the
moved directory. The directory was recovered intact from git (the tree was
committed and clean beforehand) and verified byte-for-byte by size and content
checks before continuing. No artifact was reconstructed from memory.

---

## 8. Known limitations

### Provider-intrinsic (irreducible)

**Non-delta / non-error SSE event types — `UNKNOWN`.** The source establishes
handling for exactly two event types (`response.output_text.delta`, `error`);
live traffic emitted only those. No available evidence enumerates the upstream's
full event vocabulary, and implementing speculative handling would violate
README §16. Classified `UNKNOWN`, not `UNVERIFIED`: this is not untested
engineering work but an unknowable fact about the upstream.

### Environmental / tooling

**mypy, ruff, import-linter are `NOT_CONFIGURED`.** None is installed;
`pyproject.toml` carries only `[tool.ruff] line-length = 100` with no rule
selection. Per §40, no tool was installed to have its defaults misreported as
repository policy, and no such gate is claimed as PASS.

### Not a limitation, but a bounded observation

Live coverage exercised the happy path plus a 401. The in-stream `error` event
and the unknown-model passthrough are covered by deterministic and differential
tests but were not provoked live, since doing so would mean deliberately
malforming production traffic.

---

## 9. Open operator decision (README §43)

**The three quarantined IP-spoof headers.** A controlled ablation this cycle
shows guest admission succeeds identically with and without `X-Forwarded-For` /
`X-Real-IP` / `Client-IP` (both HTTP 200), while the wider device-header set
*is* required (401 without it). The spoof subset is thus confirmed
non-functional for admission.

They remain preserved and default-ON, because:

* §17/§18 forbid removing source behavior merely because it looks unnecessary;
* a status code cannot prove the server ignores the values entirely;
* the source's intent was IP masking, so removal could change how the provider
  is treated over time.

An `include_ip_spoof_headers` flag (adaptation M8) makes disabling them a
one-line operator choice. Flipping the default is a deliberate behavior
divergence and was **not** taken unilaterally.

---

## 10. Final status

**`VERIFIED_WITH_LIMITATIONS`**

Every `SUPPORTED` behavior has source evidence, a target mapping, and a
deterministic test; the request flow has offline differential parity against the
original; the auth and generation paths are verified live on both original and
migrated code; and the finished package passes standalone certification with the
migration workspace removed from the repository.

`COMPLETE` is not claimed — it would require enumerating upstream SSE event
types that no available evidence can enumerate (§49: never claim more
verification than the evidence supports).
