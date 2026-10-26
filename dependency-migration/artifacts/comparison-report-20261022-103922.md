# Dependency Migration Comparison | INSTALLATION-LOCAL (unscored)

Generated: 2026-10-22 17:39 UTC
Frozen task created: 2026-10-22T17:03:08.252756+00:00
Task image: `sha256:2fab805deda305f6af1425d89cc496b73ce9aac2fc0c055e08698e2fc809f41a`
Matching model attempts: 3; other saved attempts excluded: 33; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| INSTALLATION-LOCAL article-27b | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 7 | ready |
| INSTALLATION-LOCAL local-8b | local / OpenVINO/Qwen3-8B-int8-ov | GPU; REQUIRED | 0 | 6 | RERUN (6 other freeze) |
| INSTALLATION-LOCAL openai | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 6 | RERUN (6 other freeze) |
| INSTALLATION-LOCAL openai-astra | openai / gpt-6-astra | provider-managed; OpenAI Responses API | 1 | 1 | ready |
| INSTALLATION-LOCAL qwen3-coder-30b | local / qwen3-coder-30b-a3b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0; OpenVINO GenAI 2026.4.0 | 0 | 2 | RERUN (2 other freeze) |
| INSTALLATION-LOCAL qwen38-fable5-coding-27b | local / qwen38-fable5-int4 | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 1 | ready |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| INSTALLATION-LOCAL article-27b | local / qwen3.8-27b-ov | pilot | `b43cd10c6464` | 1 | 1 | 1/1 (100%) | 512.8s | 6.8 | 39/39 | 16/16 | $0.0000 |
| INSTALLATION-LOCAL openai-astra | openai / gpt-6-astra | pilot | `b43cd10c6464` | 1 | 1 | 1/1 (100%) | 35.1s | 71.7 | 39/39 | 35/35 | $0.1798 |
| INSTALLATION-LOCAL qwen38-fable5-coding-27b | local / qwen38-fable5-int4 | pilot | `b43cd10c6464` | 1 | 1 | 1/1 (100%) | 326.8s | 6.9 | 39/39 | 9/9 | $0.0000 |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| INSTALLATION-LOCAL article-27b | `attempt-dac12ddb2aa14669b932b609bf3982c5` | accepted | Submitted | 508.4s | 512.8s | 6.8 | 39/39 | 16/16 | $0.0000 | n/a / n/a |
| INSTALLATION-LOCAL qwen38-fable5-coding-27b | `attempt-15c2ceed93264d318bd8a1f1c8292976` | accepted | Submitted | 323.4s | 326.8s | 6.9 | 39/39 | 9/9 | $0.0000 | n/a / n/a |
| INSTALLATION-LOCAL openai-astra | `attempt-d21ad99fbd5c4408bf7c7f9b1619444e` | accepted | Submitted | 31.7s | 35.1s | 71.7 | 39/39 | 35/35 | $0.1798 | 12631 / 2169 |

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
