# Security Repair Comparison

Generated: 2026-10-13 18:48 UTC
Frozen task created: 2026-10-13T18:38:07.232749+00:00
Task image: `sha256:0cd2054edd47f253aa6daf6537f82cb3fcb25e6b16cf4257371e54786a45b61a`
Matching model attempts: 1; other saved attempts excluded: 7; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 2 | ready |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | 1 | RERUN (1 other freeze) |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 1 | RERUN (1 other freeze) |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | pilot | `62473915a0b2` | 1 | 1 | 1/1 (100%) | 573.8s | 8/8 | 6/6 | $0.0000 |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | `attempt-fcd418ab07b1437caebb13119b6dc71b` | accepted | Submitted | 569.6s | 573.8s | 8/8 | 6/6 | $0.0000 | n/a / n/a |

Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
