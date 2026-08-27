# CAPABILITY INVENTORY — `overchat`

```text
Source set:        workspace/inbox/gemini--flash/
Source file:       01.02_overchat_gpt5_2_gemini3_5_bypass.py  (403 lines, 20308 bytes)
Source sha256:     d513c0359c8aada2801a3d847466cf2d0e865e33fd05f0d180c902187cbbc470
Source tree hash:  5cb5f4f423f44a6ed28341002ff867aa315cb9cc24d3f06bcf5cf0645936daa9
Files inspected:   1 / 1  (100%)
Reconnaissance:    COMPLETE — whole file read line-by-line; execution graph traced
                   from main() through every helper to termination.
```

## Provider identity decision

The inbox folder is named `gemini--flash`, but that is a **model** hint, not a provider
identity. The source's real upstream is `https://api.overchat.ai`, serving three
different vendor models through one gateway (Google Gemini, OpenAI GPT). Under V3
(`30_PROVIDER_ARCHITECTURE_AND_PLUGIN_SPEC.md` §3 "Model != Provider != Account !=
Credential"), provider key = **`overchat`**, with `google/gemini-3.5-flash` recorded as
one of its model bindings and the source default. Naming the provider `gemini_flash`
would have collapsed Model into Provider and violated §3.

## Execution graph (traced, not inferred)

```text
main()  L342
├── argparse (8 flags)                                    L344-353
├── Config()                                              L355
├── --list-models  → print + return                       L357-362
├── --model resolution (mapped key OR passthrough)        L364-370
├── --file/--output/--max-lines/--max-chars overrides     L372-379
├── build_mobile_headers() [discarded; banner only]       L381
├── print_banner()                                        L382
├── positional prompt → send_chat_request(...,"CLI Argument")  L384-387
├── --cli          → interactive_chat_mode()              L389-391
└── default        → read_input_content()                 L394
                     ├── content → send_chat_request(...,label)   L396-397
                     └── empty   → interactive_chat_mode()        L399-400

send_chat_request()  L176
├── input stats + banner print                            L178-189
├── build_mobile_headers()  [FRESH per request]           L191
├── GET  /v1/auth/me                    timeout 15        L195-203   → user_id
├── uuid4 x3 (chat_uuid, msg_id_1, msg_id_2)              L205-207
├── PATCH /v1/chat/{user_id}/{chat_uuid}/generateChatTitle timeout 15  L213-223
├── POST  /v1/chat/{user_id}             timeout 15       L227-235
├── POST  /v2/chat/responses  stream=True timeout cfg     L269
│   └── SSE loop: iter_lines → "data:" → [DONE] | delta | error   L272-290
├── output stats (elapsed, chars, lines, words, speed)    L292-306
├── write output_file                                     L309-314
└── return bot_full_reply | None
```

## Inventory

| # | Capability | Source symbol (lines) | Actual observed behavior | Target location | Class | Verification | Evidence |
|---|---|---|---|---|---|---|---|
| 1 | Unified config object | `Config` (L51-92) | Frozen-ish dataclass; defaults: `persona_id=gemini-3-5-flash`, `model=google/gemini-3.5-flash`, `base_url=https://api.overchat.ai`, `timeout_seconds=120`, `input_file=chat_send.txt`, `output_file=chat_reply.txt`, `max_lines=None`, `max_chars=None`, fixed `system_prompt` | `config.py:OverchatConfig` | SUPPORTED | deterministic test | `test_config_defaults_match_source` |
| 2 | Static model map (3 models) | `Config.available_models` (L58-71) | `gpt-5-2→gpt-5.2-2025-12-11`, `gemini-3-5-flash→google/gemini-3.5-flash`, `free-chat-gpt-landing→openai/gpt-4.1-nano`. Discovery is **static**; no discovery endpoint exists in source | `discovery/models.py` | SUPPORTED | deterministic test | `test_static_model_map_exact` |
| 3 | Model selection incl. unknown-model passthrough | `main` (L364-370) | Known key → persona_id=key, model=mapped value. Unknown key → **persona_id=model=raw arg** (passthrough, no validation, no error) | `discovery/models.py:resolve_model` | SUPPORTED | deterministic test | `test_unknown_model_passthrough` |
| 4 | Fake IP generation | `generate_fake_ip` (L100-102) | 4 octets, each `random.randint(1,255)` — note: **1..255 inclusive**, never 0 | `runtime/headers.py` | QUARANTINED | deterministic test | `test_fake_ip_octet_range` |
| 5 | Android device fingerprint + spoof headers | `build_mobile_headers` (L104-125) | 16-char uuid from `ascii_lowercase+digits`; exactly 14 headers; same fake IP reused in `X-Forwarded-For`/`X-Real-IP`/`Client-IP`; returns `(headers, uuid, ip)` | `runtime/headers.py` | SUPPORTED (device headers) / QUARANTINED (3 IP headers) | deterministic test + live differential | `test_mobile_headers_exact_set`, `evidence/live_auth_me_shape.json` |
| 6 | Fresh identity per request | `send_chat_request` (L191) | `build_mobile_headers()` called **per request**, so every request is a new device/guest. `main` L381 calls it a second time purely for the banner and discards the headers | `runtime/headers.py` + `operations/text_generation.py` | SUPPORTED | deterministic test | `test_identity_is_fresh_per_request` |
| 7 | Guest auth / user id resolution | L195-203 | `GET /v1/auth/me`, timeout **15** (not cfg timeout). Accepts **200 or 201**. `user_id = json()["id"]`. Non-2xx → prints status + `text[:150]`, returns None. Exception → returns None. **No credential is ever sent**; identity is auto-provisioned from `x-device-*` headers | `runtime/session.py` | SUPPORTED | deterministic test + LIVE | `test_auth_accepts_200_and_201`, live HTTP 200 captured |
| 8 | Chat title generation (fire-and-forget) | L213-223 | `PATCH /v1/chat/{user_id}/{chat_uuid}/generateChatTitle`; body `userPrompt=prompt[:300]`, `systemPrompt`, `personaType="text"`, `personaModel=model`; timeout 15; **status ignored, all exceptions swallowed** (`except Exception: pass`) | `runtime/request.py` | SUPPORTED | deterministic test | `test_title_is_fire_and_forget` |
| 9 | Chat session init (fire-and-forget) | L227-235 | `POST /v1/chat/{user_id}`; body `personaId`, `firstBotMessageHidden=True`, `chatUuid`; timeout 15; **status ignored, exceptions swallowed** | `runtime/request.py` | SUPPORTED | deterministic test | `test_chat_init_is_fire_and_forget` |
| 10 | Request ordering (4-step flow) | L191-269 | Strict order: headers → auth → title → init → responses. Title/init failures do **not** abort; only auth failure aborts | `operations/text_generation.py` | SUPPORTED | deterministic test | `test_request_order_exact` |
| 11 | Generation payload | L242-256 | Two messages: user(content, id) then **system with empty content**; `max_tokens=4000`, `temperature=0.5`, `top_p=0.95`, `frequency_penalty=0`, `presence_penalty=0`, `stream=True`; `chatId=chat_uuid` | `runtime/request.py` | SUPPORTED | deterministic test | `test_generation_payload_exact` |
| 12 | Streaming headers incl. `authorization: undefined` | L258-263 | Adds `Accept: text/event-stream`, `Content-Type`, `cache-control: no-cache`, `x-requested-with: XMLHttpRequest`, and the literal string **`authorization: "undefined"`** (a JS `undefined` leaking into the header — preserved verbatim) | `runtime/request.py` | SUPPORTED | deterministic test | `test_stream_headers_exact` |
| 13 | SSE parsing | L272-290 | `iter_lines`; skip falsy lines; `decode('utf-8', errors='replace')`; only lines starting `data:`; strips first `"data: "` occurrence only; `[DONE]` → break; per-line JSON errors **silently ignored** | `runtime/parser.py` | SUPPORTED | deterministic test | `test_sse_parser_*` (7 tests) |
| 14 | Delta event accumulation | L281-286 | Only `event == "response.output_text.delta"`; delta at `data["data"]["delta"]`; falsy delta skipped; accumulates in order | `runtime/parser.py` | SUPPORTED | deterministic test | `test_sse_accumulates_deltas_in_order` |
| 15 | In-stream error event | L287-288 | `event == "error"` → prints `data["data"]["message"]`, **does not break, does not fail** — stream continues | `runtime/parser.py` | SUPPORTED | deterministic test | `test_error_event_does_not_terminate_stream` |
| 16 | Non-2xx generation failure | L318-320 | Accepts 200/201 only; else prints status + `text[:250]`, returns None | `runtime/errors.py` | SUPPORTED | deterministic test | `test_generation_non_2xx_returns_none` |
| 17 | Error normalization | L198, L288, L319, L322 | Source has **no** normalization — raw prints + `None`. V3 §14 requires normalized categories; mapping added at the boundary only | `runtime/errors.py` | SANITIZED (adapter-added, additive) | deterministic test | `test_error_normalization_categories` |
| 18 | Input file reading + limits | `read_input_content` (L152-174) | `BASE_DIR/input_file`; `read_text(utf-8).strip()`; `max_lines` truncates by lines, `max_chars` truncates after; **falsy-check semantics** mean `max_lines=0` is treated as "no limit"; labels are Arabic and exact; read exception → warn + `("","")` | `legacy/file_io.py` | SUPPORTED | deterministic test | `test_read_input_*` (6 tests) |
| 19 | Output file writing | L309-314 | Writes full reply to `BASE_DIR/output_file` utf-8; failure warns but **still returns the reply** | `legacy/file_io.py` | SUPPORTED | deterministic test | `test_output_write_failure_still_returns_reply` |
| 20 | Input statistics | L178-189 | `approx_tokens = int(char_count/3.5)`; words via `split()`, lines via `splitlines()` | `legacy/stats.py` | SUPPORTED | deterministic test | `test_input_stats_exact` |
| 21 | Output statistics + speed | L292-306 | `speed = out_chars/elapsed`, guarded `elapsed>0 else 0` | `legacy/stats.py` | SUPPORTED | deterministic test | `test_output_stats_and_speed_guard` |
| 22 | Interactive chat mode | `interactive_chat_mode` (L326-340) | Loop; blank input skipped (`continue`); exit words `exit/quit/خروج/q` case-insensitively; `KeyboardInterrupt`/`EOFError` → break | `legacy/cli_app.py` | SUPPORTED | deterministic test | `test_interactive_exit_words`, `test_interactive_skips_blank` |
| 23 | CLI argument surface | L344-353 | 8 flags with exact short forms `-m -f -o -l -c` + `--list-models`, `--cli`, positional `nargs="*"` | `legacy/cli_app.py` | SUPPORTED | deterministic test | `test_cli_flag_surface_exact` |
| 24 | Mode dispatch precedence | L384-400 | prompt > `--cli` > input-file > interactive fallback | `legacy/cli_app.py` | SUPPORTED | deterministic test | `test_mode_dispatch_precedence` |
| 25 | Banner rendering | `print_banner` (L127-150) | Neon banner, marks active model, lists all models | `legacy/banner.py` | SUPPORTED | smoke test | `test_banner_renders_active_marker` |
| 26 | Windows console encoding fix | L31-36 | `sys.platform=="win32"` → `reconfigure(utf-8, errors=replace)`, exception swallowed | `legacy/console.py` | SUPPORTED (platform-gated) | deterministic test | `test_win32_reconfigure_guarded` |
| 27 | Optional colorama with fallback | L39-45 | On ImportError, `_F.__getattr__` returns `""` for **any** attribute so all colour refs degrade to empty strings | `legacy/colors.py` | SUPPORTED | deterministic test | `test_color_fallback_returns_empty_for_any_attr` |
| 28 | `BASE_DIR` anchoring | L98 | All file IO is relative to the **script's** directory, not CWD | `legacy/file_io.py` | SUPPORTED | deterministic test | `test_base_dir_anchoring` |
| 29 | Health check | — | **Absent in source.** V3 §4.1 requires a health contract; implemented as a read-only `auth/me` probe reusing capability #7 only | `health.py` | SANITIZED (adapter-added) | deterministic test + LIVE | `test_health_maps_status` |
| 30 | Account pool / rotation | — | **Absent.** Each request mints a throwaway guest identity; there is no pool, lease, cooldown, or rotation | not implemented | UNSUPPORTED | n/a — declared `false` in manifest | source absence |
| 31 | File upload / download | — | **Absent.** (`lastUploadUrl` appears in the live `auth/me` body, but the source implements no upload path) | not implemented | UNSUPPORTED | n/a | source absence |
| 32 | Provider-native agent | — | **Absent.** No thread/run/tool APIs | not implemented | UNSUPPORTED | n/a | source absence |
| 33 | Retries / backoff | — | **Absent.** Zero retry logic anywhere; a failed auth simply returns None | not implemented | UNSUPPORTED | n/a | source absence |
| 34 | Async jobs / polling | — | **Absent.** Response is synchronous SSE only | not implemented | UNSUPPORTED | n/a | source absence |
| 35 | Rate-limit handling | — | **Absent.** No 429 branch, no `Retry-After` read | `runtime/errors.py` maps 429→`rate_limited` at boundary only | SANITIZED (additive) | deterministic test | `test_error_normalization_categories` |
| 36 | Non-delta SSE event types | L281-288 | Only `response.output_text.delta` and `error` are handled. Whether upstream emits other event types is **not established by the source** | `runtime/parser.py` (ignored, as in source) | UNKNOWN | cannot be closed offline | see MIGRATION_REPORT limitations |
| 37 | Server-side effect of the 3 IP headers | L114-116 | Source intent is IP masking. Live differential shows a `200` **without** them and `502` **with and without** them → no evidence they affect admission | `runtime/headers.py` (preserved, default on) | QUARANTINED | live differential | `evidence/live_auth_me_shape.json`, §"IP header finding" |

## Classification totals

```text
SUPPORTED:    24   (#1,2,3,5*,6,7,8,9,10,11,12,13,14,15,16,18,19,20,21,22,23,24,25,26,27,28)  → 26 rows, #5 split
SANITIZED:     3   (#17 error normalization, #29 health, #35 rate-limit mapping)
QUARANTINED:   3   (#4 fake IP, #5-IP-headers, #37 IP header effect)
UNSUPPORTED:   5   (#30 accounts, #31 assets, #32 provider agent, #33 retries, #34 polling)
UNKNOWN:       1   (#36 unobserved SSE event types)
UNVERIFIED:    0
```

## IP header finding (live differential evidence)

```text
Probe A  device headers only, uuid=probe0000probe00, NO IP headers   → HTTP 200 + guest id
Probe B  device headers + X-Forwarded-For                            → HTTP 502
Probe C  device headers + X-Real-IP                                  → HTTP 502
Probe D  device headers + Client-IP                                  → HTTP 502
Probe E  device headers + all three IP headers                       → HTTP 502
Probe F  replay of Probe A byte-identical, minutes later             → HTTP 502
Probe G  no device headers at all                                    → HTTP 502
```

Probe F is decisive: the request that succeeded in Probe A later returned 502 unchanged.
Therefore the 502s are **global upstream degradation**, not caused by the spoof headers,
and the spoof headers are **not** required for guest admission (Probe A succeeded without
them). This is recorded as evidence, not as authorization to remove them — they remain
enabled by default to preserve original behavior, and the removal question is escalated
to the operator (MIGRATION_REPORT §Operator decision).
