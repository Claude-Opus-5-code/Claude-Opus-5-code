# Provider — `overchat`

Migrated, V3-compliant package for the Overchat gateway (`https://api.overchat.ai`).

```text
Provider key   : overchat
Revision       : r1
Status         : disabled / integration_pending   (production routing NOT enabled)
Capabilities   : text_generation, streaming
Auth           : none — auto-provisioned guest identity from device headers
Discovery      : static (3 models)
```

## 1. Provenance

| Item | Value |
|---|---|
| Source file | `01.02_overchat_gpt5_2_gemini3_5_bypass.py` (403 lines, 20 308 bytes) |
| Source sha256 | `d513c0359c8aada2801a3d847466cf2d0e865e33fd05f0d180c902187cbbc470` |
| Source tree sha256 | `5cb5f4f423f44a6ed28341002ff867aa315cb9cc24d3f06bcf5cf0645936daa9` |
| Inbox path | `workspace/inbox/gemini--flash/` |
| Working docs | `workspace/working/overchat/` |
| Archive | `workspace/archive/overchat/r1/` |

The original module docstring (source L1-17) described the script as an
"Overchat Dual-Models Master Bypass Hub" reading `chat_send.txt` and writing
`chat_reply.txt`. That behavior is preserved in `legacy/`.

**Provider identity:** the inbox folder is named `gemini--flash`, but that is a
*model* hint. The upstream is the Overchat gateway serving three different vendor
models, so the provider key is `overchat` — naming it after one model would
collapse Model into Provider, which V3 §3 forbids.

## 2. Layout

```text
overchat/
├── manifest.yaml               V3 §7 — every claim carries source evidence
├── provider.py                 V3 §8.1 normalized adapter (the ONLY Core-facing module)
├── config.py                   source Config (L51-92)
├── health.py                   V3 §4.1 health contract — SANITIZED (source had none)
├── runtime/                    provider-internal mechanics (Core must not import)
│   ├── headers.py              device fingerprint; IP spoof headers QUARANTINED
│   ├── session.py              guest auth, user id, uuid minting
│   ├── request.py              URLs, payloads, stream headers, fire-and-forget calls
│   ├── parser.py               SSE parsing + delta accumulation
│   └── errors.py               V3 §14 normalization — SANITIZED (source had none)
├── discovery/models.py         static 3-model table + unknown-model passthrough
├── operations/text_generation.py   the 4-step flow orchestration
├── legacy/                     preserved script shell (README §17); not on the contract path
│   ├── banner.py  colors.py  console.py
│   ├── file_io.py  stats.py   cli_app.py
└── tests/                      provider-owned tests
```

## 3. Usage

### As a V3 provider (the contract surface)

```python
import requests
from providers.finished.overchat import GenerateRequest, OverchatProvider

provider = OverchatProvider(transport=requests)

provider.get_capabilities()      # {'text_generation', 'streaming'}
provider.discover_models()       # static 3-model list, no network call
provider.health_check()          # read-only auth/me probe

response = provider.generate(GenerateRequest(prompt="مرحبا"))
print(response.text)

for delta in provider.generate_stream(GenerateRequest(prompt="hi", stream=True)):
    print(delta, end="")
```

Undeclared capabilities are rejected, never silently ignored:

```python
provider.generate_image()   # raises OverchatError(category='unsupported_capability')
```

### As the original CLI (preserved behavior)

```bash
python -m providers.finished.overchat.legacy.cli_app --list-models
python -m providers.finished.overchat.legacy.cli_app "your prompt"
python -m providers.finished.overchat.legacy.cli_app --cli
python -m providers.finished.overchat.legacy.cli_app -m gpt-5-2 -f in.txt -o out.txt
```

Flags, exit words, dispatch precedence, Arabic labels and statistics are
identical to the source.

## 4. Behavior preserved deliberately

These are real behaviors of the working original, kept verbatim (README §17/§18)
rather than "cleaned up":

| Behavior | Source | Why kept |
|---|---|---|
| `authorization: "undefined"` header | L263 | A JS `undefined` leaked into the client as a literal string; it is part of the request that actually works |
| Empty system message after the user message | L245 | Real payload shape |
| Fire-and-forget title/init with `except Exception: pass` | L222, L234 | Failures must not abort generation |
| Silent skip of malformed SSE frames | L289-290 | Source tolerates junk frames |
| `error` SSE event is non-terminal | L287-288 | Stream continues after an error frame |
| `max_lines`/`max_chars` falsy checks | L160, L167 | `0` means "no limit" in the source |
| Hardcoded 15 s timeouts on 3 calls | L196, L221, L233 | Only the stream call uses the configurable timeout |
| Duplicate header mint in `main()` | L381 | Value is discarded; used only for the banner |
| `random.randint(1, 255)` octets | L100-102 | Never 0, can be 255 — not "corrected" |

## 5. Quarantined

`generate_fake_ip` and the three IP headers (`X-Forwarded-For`, `X-Real-IP`,
`Client-IP`) are isolated in `runtime/headers.py` behind
`OverchatConfig.include_ip_spoof_headers`, which **defaults to `True` to match
the source exactly**.

Live differential evidence showed guest admission succeeding *without* them, and
later 502s occurring both with and without them, so no server-side effect is
established. That evidence does not authorize removal — the decision is
escalated to the operator.

## 6. Not supported (declared `false`, absent from source)

Account pools/rotation, file upload/download, provider-native agents,
retries/backoff, async jobs/polling, vision, image generation, embeddings,
rerank, moderation, audio STT/TTS, dynamic model discovery, and any
API-key/OAuth auth flow.

## 7. Adapter-added (SANITIZED)

Three things do not exist in the source and were added at the boundary because
V3 requires them. All are strictly additive — they never change which requests
succeed or fail:

* `runtime/errors.py` — V3 §14 error normalization (source only printed and returned `None`);
* `health.py` — V3 §4.1 health contract, reusing only the existing read-only `auth/me` call;
* 429 → `rate_limited` mapping (the source has no 429 branch).

## 8. Known limitations

* **Live generation verification blocked**: `api.overchat.ai` returned 502 for
  every generation attempt, including a byte-identical replay of a request that
  had just succeeded. Provider-side/environmental, not migration-caused.
* **Unobserved SSE event types are UNKNOWN**: the source establishes only
  `response.output_text.delta` and `error`. Other frames are ignored, exactly as
  in the source. This cannot be closed offline.

## 9. Dependencies

Runtime: `requests` (as in the source) — injected as a transport, so the package
imports and tests without it. Optional: `colorama` (source has a built-in
fallback to empty strings). No dependency was added by the migration.
