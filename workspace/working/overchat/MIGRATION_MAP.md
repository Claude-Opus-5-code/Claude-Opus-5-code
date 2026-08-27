# MIGRATION MAP — `overchat`

Exact source→target mapping. Every meaningful responsibility in the 403-line source
appears exactly once below. Nothing is dropped silently.

Source file for all rows:
`01.02_overchat_gpt5_2_gemini3_5_bypass.py` (sha256 `d513c035…bcc470`)

## File-level map

```text
source (single 403-line script)  →  providers/finished/overchat/
├── L1-17    module docstring          → README.md (provenance section)
├── L18-28   imports                   → distributed per module
├── L31-36   win32 encoding fix        → legacy/console.py
├── L39-45   colorama + fallback       → legacy/colors.py
├── L51-92   Config                    → config.py
├── L58-71   available_models          → discovery/models.py
├── L98      BASE_DIR                  → legacy/file_io.py
├── L100-102 generate_fake_ip          → runtime/headers.py
├── L104-125 build_mobile_headers      → runtime/headers.py
├── L127-150 print_banner              → legacy/banner.py
├── L152-174 read_input_content        → legacy/file_io.py
├── L176-324 send_chat_request         → SPLIT (see below)
├── L326-340 interactive_chat_mode     → legacy/cli_app.py
└── L342-400 main                      → legacy/cli_app.py
```

`send_chat_request` (L176-324) is the only function that is split, because it mixes
five V3 concerns in one body:

```text
L178-189  input stats + print          → legacy/stats.py     (compute) + legacy/banner.py (print)
L191      identity minting             → runtime/headers.py
L195-203  auth / user id               → runtime/session.py:resolve_user_id
L205-207  uuid minting                 → runtime/session.py:new_conversation_ids
L213-223  title call                   → runtime/request.py:generate_chat_title
L227-235  init call                    → runtime/request.py:create_chat_session
L241-263  payload + stream headers     → runtime/request.py:build_responses_request
L269      stream POST                  → runtime/request.py:open_response_stream
L272-290  SSE parse loop               → runtime/parser.py:iter_text_deltas
L292-306  output stats + print         → legacy/stats.py + legacy/banner.py
L309-314  save reply                   → legacy/file_io.py:write_output
L318-324  failure paths                → runtime/errors.py
orchestration of the above            → operations/text_generation.py:generate_text
V3 normalized boundary                → provider.py:OverchatProvider
```

## Symbol-level map

| Source symbol (lines) | Target symbol | Adaptation |
|---|---|---|
| `Config` (L51-92) | `config.OverchatConfig` | dataclass → frozen dataclass; field names/defaults/types **unchanged** |
| `Config.available_models` (L58-71) | `discovery.models.AVAILABLE_MODELS` | dict → module-level `MappingProxyType`; **same 3 keys, same model strings, same descriptions** |
| model resolution (L364-370) | `discovery.models.resolve_model` | extracted from `main` verbatim, incl. unknown-key passthrough |
| `generate_fake_ip` (L100-102) | `runtime.headers.generate_fake_ip` | identical; `random.randint(1,255)` preserved exactly |
| `build_mobile_headers` (L104-125) | `runtime.headers.build_mobile_headers` | identical 14 headers, same order, same 3-tuple return; `include_ip_spoof_headers` flag added **defaulting to True** (no behavior change) |
| `print_banner` (L127-150) | `legacy.banner.print_banner` | identical output; takes injected stream for testability |
| `read_input_content` (L152-174) | `legacy.file_io.read_input_content` | identical incl. Arabic labels and falsy-limit semantics |
| `BASE_DIR` (L98) | `legacy.file_io.BASE_DIR` | anchored to finished package dir (portability adaptation; documented) |
| auth block (L195-203) | `runtime.session.resolve_user_id` | identical URL/timeout(15)/`[200,201]`/`["id"]`; raw-print replaced by returning a normalized error |
| uuid block (L205-207) | `runtime.session.new_conversation_ids` | identical `uuid4()` x3 |
| title block (L213-223) | `runtime.request.generate_chat_title` | identical URL/payload/timeout; `except Exception: pass` **preserved** |
| init block (L227-235) | `runtime.request.create_chat_session` | identical URL/payload/timeout; swallow **preserved** |
| payload (L242-256) | `runtime.request.build_responses_payload` | identical keys, identical values, identical message order incl. empty system message |
| stream headers (L258-263) | `runtime.request.build_stream_headers` | identical, incl. literal `authorization: "undefined"` |
| stream POST (L269) | `runtime.request.open_response_stream` | identical method/url/`stream=True`/`data=json.dumps(...)`/cfg timeout |
| SSE loop (L272-290) | `runtime.parser.iter_text_deltas` | print side-effect → generator of events; parsing rules byte-identical |
| delta extraction (L281-286) | `runtime.parser.iter_text_deltas` | same event name, same `data.data.delta` path, same falsy skip |
| error event (L287-288) | `runtime.parser.iter_text_deltas` | yields non-terminal error event; **does not break** (as source) |
| non-2xx (L318-320) | `runtime.errors.classify_http_status` | status kept; `text[:250]` truncation preserved |
| stats (L178-189, L292-306) | `legacy.stats.input_stats` / `output_stats` | identical formulas incl. `/3.5` and `elapsed>0` guard |
| save reply (L309-314) | `legacy.file_io.write_output` | identical; failure non-fatal |
| `interactive_chat_mode` (L326-340) | `legacy.cli_app.interactive_chat_mode` | identical exit words/blank-skip/interrupt handling |
| `main` (L342-400) | `legacy.cli_app.main` | identical flags and dispatch precedence |
| win32 fix (L31-36) | `legacy.console.configure_console` | identical, still platform-gated |
| colorama fallback (L39-45) | `legacy.colors` | identical `_F` fallback semantics |

## Request-flow map

| Source flow | Target operation |
|---|---|
| `GET /v1/auth/me` | `runtime.session.resolve_user_id` |
| `PATCH /v1/chat/{uid}/{cuid}/generateChatTitle` | `runtime.request.generate_chat_title` |
| `POST /v1/chat/{uid}` | `runtime.request.create_chat_session` |
| `POST /v2/chat/responses` (SSE) | `runtime.request.open_response_stream` + `runtime.parser.iter_text_deltas` |
| whole 4-step sequence | `operations.text_generation.generate_text` |
| V3 normalized entry | `provider.OverchatProvider.generate` |

## Boundary map (V3 additions — additive only, never replacing source logic)

| V3 requirement | Target | Justification |
|---|---|---|
| manifest (§7) | `manifest.yaml` | required for every provider |
| capability declaration (§4.1) | `manifest.yaml` + `provider.get_capabilities` | required |
| error normalization (§14) | `runtime/errors.py` | required; source had none → SANITIZED |
| health contract (§4.1, §11) | `health.py` | required; source had none → SANITIZED |
| normalized adapter (§8.1) | `provider.py` | boundary wrapper, not a rewrite |
| unsupported ops rejected (§5) | `provider.generate` → `unsupported_capability` | required |

## Nothing-dropped ledger

Every source line range L1-403 is accounted for above. Explicitly retained
despite being "awkward" under V3 (README §17 zero-dropped-logic):

```text
authorization: "undefined"     literal JS-undefined header      → preserved verbatim
fake IP + 3 spoof headers      no proven server effect          → preserved, default ON
empty system message           odd but real payload shape       → preserved
fire-and-forget title/init     bare `except Exception: pass`    → preserved
silent SSE JSON error skip     hides malformed frames           → preserved
max_lines falsy semantics      0 behaves as "unlimited"         → preserved
timeout 15 on 3 calls          inconsistent with cfg timeout    → preserved
non-terminal error event       stream continues after error     → preserved
duplicate header mint in main  discarded value, banner only     → preserved
Arabic UI strings/labels       part of observable behavior      → preserved
```
