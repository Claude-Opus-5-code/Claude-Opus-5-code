# MIGRATION PLAN — `overchat`

## 1. Target package structure

Follows `30_PROVIDER_ARCHITECTURE_AND_PLUGIN_SPEC.md` §6.2 (mature layout), trimmed to
modules this provider actually needs (§6.2 explicitly allows fewer files; §4.3 forbids
forcing modules a provider does not have).

```text
providers/finished/overchat/
├── manifest.yaml                  V3 §7
├── README.md                      provenance + usage
├── __init__.py                    public surface
├── provider.py                    V3 §8.1 normalized adapter
├── config.py                      source Config
├── health.py                      V3 §4.1 health contract (SANITIZED)
├── runtime/
│   ├── headers.py                 device fingerprint + IP spoof (QUARANTINED)
│   ├── session.py                 guest auth / user id / uuids
│   ├── request.py                 title, init, payload, stream open
│   ├── parser.py                  SSE parsing + delta accumulation
│   └── errors.py                  V3 §14 normalization (SANITIZED)
├── discovery/
│   └── models.py                  static 3-model map + resolution
├── operations/
│   └── text_generation.py         4-step orchestration
├── legacy/                        preserved script-shell behavior (README §17)
│   ├── console.py  colors.py  banner.py
│   ├── file_io.py  stats.py    cli_app.py
└── tests/                         provider-owned tests
```

`legacy/` is used exactly as README §17 prescribes: behavior that has no natural V3
home (terminal UI, Arabic labels, file IO anchored to script dir, CLI) is isolated
there rather than deleted.

## 2. Source-to-target mapping

See `MIGRATION_MAP.md` (authoritative, per-symbol).

## 3. Unchanged behavior (no intentional change)

```text
all 4 endpoints, methods, and their order
all payload keys/values incl. empty system message
all 14 device headers + 5 stream headers incl. authorization: "undefined"
timeouts: 15/15/15 fixed + 120 configurable
status acceptance: [200, 201] for auth and generation
SSE rules: data: prefix, single-replace, [DONE], silent JSON skip
delta event name + data.data.delta path
error event non-terminal
3 model ids + unknown-model passthrough
file IO limits incl. falsy-limit semantics, Arabic labels
stats formulas (/3.5 tokens, speed guard)
CLI flags, exit words, dispatch precedence
```

## 4. Mechanical adaptations (README §18 — allowed, documented)

| # | Adaptation | Reason | Behavior impact |
|---|---|---|---|
| M1 | one script → package modules | V3 §6 boundaries | none |
| M2 | `print()` → injected stream / returned events | testability + V3 (Core must not receive prints) | UI text identical when stream is stdout |
| M3 | module-level `requests` calls → injected transport | testability, portability | none; default transport is `requests` with same args |
| M4 | `Config` → frozen dataclass | immutability | same fields/defaults |
| M5 | `available_models` dict → `MappingProxyType` | prevent mutation | same content |
| M6 | `BASE_DIR` → package dir | standalone portability (§37) | file IO anchor moves with the package, as in source |
| M7 | raw prints on error → normalized error objects | V3 §14 | source's `None` return preserved at legacy layer |
| M8 | `include_ip_spoof_headers` flag added | allows operator control | default `True` = source behavior |

## 5. Unsupported (declared `false`, not implemented)

`account_pool`, `file_upload/download`, `provider_agent`, `retries/backoff`,
`async_jobs/polling`, `vision`, `image_generation`, `embeddings`, `rerank`,
`moderation`, `audio_*`, dynamic model discovery, OAuth/api-key auth.

## 6. Unknown

Non-delta/non-error SSE event types (#36) — source establishes only two.

## 7. Quarantined

`generate_fake_ip`, the 3 IP spoof headers, and their unproven server effect.
Preserved and default-on; isolated in `runtime/headers.py` behind one flag.

## 8. Sanitization requirements

Source contains **no credentials** (guest/no-auth provider), so no secret
sanitization of the source is needed; `sanitized_source_snapshot/` is therefore
**not created** (README §9 makes it conditional). Live evidence is redacted before
being written to `evidence/` (guest id, device id, registration IP, overchat id).

## 9. Tests

```text
providers/finished/overchat/tests/
├── test_manifest.py            manifest ↔ contracts ↔ declared caps
├── test_config.py              defaults, immutability
├── test_models.py              3-model map, resolution, passthrough
├── test_headers.py             14 headers, uuid alphabet/length, IP range, freshness
├── test_session.py             auth 200/201, id extraction, failure paths
├── test_request.py             payload/headers/urls/order exactness
├── test_parser.py              SSE rules, deltas, [DONE], error event, junk frames
├── test_errors.py              normalization categories + retryability
├── test_operations.py          4-step order, abort-only-on-auth
├── test_provider.py            V3 adapter, unsupported rejection, no secret leak
├── test_legacy_behavior.py     file IO, stats, CLI, colors, console
└── test_parity_differential.py migrated vs original, recorded-fixture based
```

Plus repo-level:
```text
tests/contract/test_overchat_provider_contract.py   provider ↔ core contracts
```

## 10. Characterization fixtures

`workspace/working/overchat/evidence/` — live `auth/me` shape (redacted), IP-header
differential probe matrix, SSE frame fixtures derived from source-declared shapes.

## 11. Differential verification

Original and migrated code driven through a **shared fake transport** that records
method/url/headers/body per step; outputs compared for: endpoint set, ordering,
payload equality, header equality, delta accumulation, terminal behavior, return value.
Live end-to-end differential is blocked by upstream 502 (see limitations).

## 12. Live verification

Performed for guest auth (`HTTP 200`, `id` present) before upstream degraded.
Generation-path live verification is currently **blocked by upstream 502** on all
`api.overchat.ai` requests, including a byte-identical replay of the request that
had just succeeded — i.e. environment/provider-side, not migration-caused.

## 13. Standalone validation

Run provider tests from `providers/finished/overchat/` with
`workspace/working/overchat` made unavailable (temporarily moved aside) and
`sys.path` not containing it; assert import + tests + no workspace references.

## 14. Archive plan

`workspace/archive/overchat/r1/` with source snapshot, migrated package copy,
all working docs, `VERIFICATION_RESULTS.md`, `ARCHIVE_MANIFEST.json`, and
`source_original_hash.txt` / `target_hash.txt`.

## 15. Activation

`status: disabled`, `activation: integration_pending`, `is_functional: true`.
README §21 forbids auto-enabling production routing; no governance file in this
repo authorizes activation.
