# Syntx Step 3 Refresh — approved T2 specification and recovery checkpoint

## Approval and scope

User GO approved on 2026-09-11 under EXTERNAL_AGENT_MANDATE.md v1.2, section 2. Baseline: `35af8b9`. This specification restores the previously approved work after a sandbox reset; it does not reopen or expand the design.

Deliver through `feature/syntx-step-3-refresh` and a PR, never push main. Local implementation uses the sandbox's `genspark_ai_developer` branch; the delivery branch points to the same final commit. GitHub assigns the PR number. Push each completed chunk, keep the PR draft until validation finishes, then squash the feature's commits for final review. On reset, recover from the remote branch rather than assuming local checkpoints survived.

Add only `03_syntx_refresh.py`, `test_syntx_refresh.py` and this specification. Do not modify chat, registration, gateway, HARs, or the real pool. Preserve the existing list-of-account-objects contract and every field of retained records. No signup, imports that execute other scripts, refill worker, daemon, endpoint discovery or token refresh endpoint.

## Pre-edit anchor: exact-byte SHA-256

The new script has no pre-existing version. The Git baseline and these fingerprints are the rollback anchor:

| File relative to Syntx directory | SHA-256 |
| --- | --- |
| 01_syntx_chat.py | 2717327c57ea928df14f496710313ac324b15f6b1342442c1a19f15d7f0bf76b |
| 02_syntx_register.py | 751bbfce78e6e79fc3b594e71447e4597aec63d90b1bd184f79b124129c6644c |
| accounts_syntx.json | 3f85fbf728d95e4cb4bf802a2cbe0a130a2a986d4a3656e5e8592fe6e3531a81 |
| har/syntx.ai....har | f8b81137a6e64c5120fd3f91eef8b804b01efdf4bac0bc5127e53f6d8e290e81 |
| har/syntx.ai...har | 19a3e94063a347ee11c38ac37f457664696aafb46bea8eadb9caf78448c4228d |

## Evidence and explicit GO policy

- Main HAR: `GET /api/v1/user/balance`, URL line 53843, response line 54006: root `balance` number.
- Main HAR: `GET /api/v1/llm/limits`, URL line 4382, response line 4533: `window_6h.percent_left`, `window_7d.percent_left`; timestamp fields can be null.
- Main HAR line 23167: both percentages are zero. Line 39295: generate (not a health GET) returns rate-limit detail with retry duration. Do not invent expiration timestamps.
- Supplemental HAR: balance response line 5981; limits responses 10769 and 21656.
- Authorization and deletion semantics were explicitly approved in the user's GO, not falsely attributed to missing HAR headers/error examples. Use `Authorization: Bearer <token>` and the existing chat User-Agent/Content-Type from `01_syntx_chat.py:555-559`.
- Removal candidates: either health request returns HTTP 401/403/429; a valid numeric balance is exactly zero; or valid numeric 6h percentage is exactly zero. This is pool management policy, not proof of permanent credential expiry.
- Network errors, other HTTP statuses, malformed JSON, missing fields, nonnumeric/negative/nonfinite values and absent tokens alone are NOT removal evidence. Retain them as unknown.
- A 7d zero alone is reported separately and retained, not counted as fully healthy. It is not an approved removal criterion.
- Definitive approved removal evidence wins over an inconclusive result from the other endpoint. Healthy means positive balance and both valid percentages positive. Preserve unknown and limited rows.

## CLI and storage contract

- One sequential report-only pass by default. `--clean` / `--purge` explicitly delete candidates. `--file` chooses a pool; default is sibling `accounts_syntx.json`, independent of working directory.
- `--timeout`: per request, default 15 seconds, valid range 1..120. No retries or redirects; at most 2N calls for N accounts. Keep the already-used curl_cffi/requests transport pattern; no new required libraries.
- Terminal report: row indices, numeric balance/limits, fixed reason strings and counts. Never tokens, email addresses, raw bodies or exception text. Colorama optional; honor NO_COLOR and redirected output.
- Warn below five verified healthy accounts. Distinguish candidate count from actual deletion count. No automated refill or invented signal file.
- Corrupt/missing/non-list pool or non-object rows abort without overwrite. Empty list is valid. Tokenless rows remain untouched.
- Purge requires ALL pool writers stopped. No concurrent-writer safety claim. Exact snapshot comparison is a best-effort guard, NOT a lock or a replacement for the maintenance window.
- If and only if candidates exist: create a unique sibling `.tmp` with restrictive initial permissions, serialize, flush/fsync, preserve original mode, recheck source snapshot, then `os.replace`. No non-atomic fallback; remove the temporary file on failure. Do not create automatic secret-containing backups.
- Exit codes: 0 completed report/clean (a low-pool warning may still exist); 1 unknown/incomplete health results; 2 input/dependency/persistence failure; 130 interrupted. Atomic replace is the commit point; interruption after it cannot undo the purge.

## Nine micro-tasks

| # | Task | Classification |
| --- | --- | --- |
| 1 | Freeze approved request/response and decision specification | T0 |
| 2 | Record baseline hashes and pre-edit anchor | T0 verification |
| 3 | Read and validate existing pool contract without losing fields | T2 |
| 4 | Implement bounded health GETs and approved classification | T2 |
| 5 | Produce redacted colored report and counts | T2 |
| 6 | Implement explicit atomic purge under stopped-writer assumption | T2 |
| 7 | Alert below five; no registration/daemon | T2 |
| 8 | Network-blocked mocks, filesystem failure cases, syntax/py_compile | T2 verification |
| 9 | Push checkpoints, final review report and Antigravity handoff | T0 / Git workflow |

No T1 or unrelated existing-file changes are planned.

## Validation and handoff

Tests must forbid network access and use synthetic temporary pools inside this repository, not real account credentials. Cover approved removals, uncertain failures retained, 7d-only exhaustion, no credential output, report-mode byte preservation, empty/corrupt pools, atomic write/replace failures and changed-snapshot aborts. Compare protected hashes and run py_compile. Live E2E belongs exclusively to Antigravity.

From repository root:

```bash
python -B -m unittest discover -s "🟢_syntx_ai" -p "test_syntx_refresh.py" -v
python "🟢_syntx_ai/03_syntx_refresh.py" --help
# The following commands contact Syntx: run only in the local team's environment.
python "🟢_syntx_ai/03_syntx_refresh.py"
# Stop all pool writers and make an operator-controlled backup first:
python "🟢_syntx_ai/03_syntx_refresh.py" --clean
```

Code rollback removes only the feature additions; it does not restore accounts removed by a live purge. Local data restoration is the operator's responsibility.
