# Security Repair Comparison

Generated: 2026-10-13 19:39 UTC
Frozen task created: 2026-10-13T18:38:07.232749+00:00
Task image: `sha256:0cd2054edd47f253aa6daf6537f82cb3fcb25e6b16cf4257371e54786a45b61a`
Matching model attempts: 4; other saved attempts excluded: 7; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 2 | 2 | ready |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 1 | ready |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 1 | 1 | ready |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | pilot | `62473915a0b2` | 2 | 2 | 2/2 (100%) | 564.5s | 6.4 | 16/16 | 11/11 | $0.0000 |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | pilot | `62473915a0b2` | 1 | 0 | 0/1 (0%) | n/a | 11.9 | 4/8 | 0/0 | $0.0000 |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | pilot | `62473915a0b2` | 1 | 1 | 1/1 (100%) | 78.1s | 34.0 | 8/8 | 10/10 | $0.0571 |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | `attempt-fcd418ab07b1437caebb13119b6dc71b` | accepted | Submitted | 569.6s | 573.8s | 6.4 | 8/8 | 6/6 | $0.0000 | n/a / n/a |
| b390-morteza89-27b-int4-20261009 | `attempt-9c1d5902396a4a12b78ccc0bc6bde872` | accepted | Submitted | 551.2s | 555.2s | 6.5 | 8/8 | 5/5 | $0.0000 | n/a / n/a |
| b390-qwen3-8b-int8-20261010 | `attempt-987a40a091284fdb9a2c635704cd45d3` | missing_regression_assertions | Submitted | 38.6s | 42.3s | 11.9 | 4/8 | 0/0 | $0.0000 | n/a / n/a |
| ptl-openai-gpt-6.1-sol | `attempt-925c4a67a6ce49148086308538251759` | accepted | Submitted | 73.7s | 78.1s | 34.0 | 8/8 | 10/10 | $0.0571 | 40604 / 2442 |

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
