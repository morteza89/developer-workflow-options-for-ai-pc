# Security Repair Comparison

Generated: 2026-10-13 18:16 UTC
Frozen task created: 2026-10-13T18:10:29.578494+00:00
Task image: `sha256:0cd2054edd47f253aa6daf6537f82cb3fcb25e6b16cf4257371e54786a45b61a`
Matching model attempts: 1; other saved attempts excluded: 3; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Status |
| --- | --- | --- | ---: | --- |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | MISSING |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | MISSING |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 1 | ready |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | pilot | `109399dedd84` | 1 | 1 | 1/1 (100%) | 124.1s | 8/8 | 31/31 | $0.0876 |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ptl-openai-gpt-6.1-sol | `attempt-f65c444763ea4ad08980c78d7f7d9cba` | accepted | Submitted | 119.4s | 124.1s | 8/8 | 31/31 | $0.0876 | 54923 / 4641 |

Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
