# Dependency Migration Comparison

Generated: 2026-10-12 21:24 UTC
Frozen task created: 2026-10-12T18:17:47.705784+00:00
Task image: `sha256:74283564a52c5969dec0355e2d0fa1f297110fd8be55f0b6d497650a627315a5`
Matching model attempts: 9; other saved attempts excluded: 12; matching mock attempts excluded: 2

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Status |
| --- | --- | --- | ---: | --- |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 3 | ready |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 3 | ready |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 3 | ready |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | pilot | `58678ca6f07d` | 3 | 3 | 3/3 (100%) | 464.1s | 117/117 | 38/38 | $0.0000 |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | pilot | `58678ca6f07d` | 2 | 0 | 0/2 (0%) | n/a | 0/4 | 0/0 | $0.0000 |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | pilot | `58678ca6f07d` | 1 | 0 | 0/1 (0%) | n/a | 0/2 | 0/0 | $0.0000 |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | pilot | `58678ca6f07d` | 3 | 3 | 3/3 (100%) | 44.4s | 117/117 | 92/92 | $0.0985 |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ptl-openai-gpt-6.1-sol | `attempt-59734f17f8ec44399f369e8401fc0064` | accepted | Submitted | 42.7s | 45.8s | 39/39 | 27/27 | $0.0328 | 12499 / 2211 |
| b390-morteza89-27b-int4-20261009 | `attempt-8b0e51f33b8a4a3186be8f05810ee109` | accepted | Submitted | 433.1s | 436.1s | 39/39 | 12/12 | $0.0000 | n/a / n/a |
| b390-qwen3-8b-int8-20261010 | `attempt-20eb2a59ba3644b9b72e3037baa6d5ba` | missing_regression_assertions | Submitted | 8.8s | 11.4s | 0/2 | 0/0 | $0.0000 | n/a / n/a |
| b390-morteza89-27b-int4-20261009 | `attempt-7001833a192f4a37ac1abe192eb94474` | accepted | Submitted | 479.6s | 482.9s | 39/39 | 17/17 | $0.0000 | n/a / n/a |
| b390-qwen3-8b-int8-20261010 | `attempt-53111bcd52454de8a4658d78858f0b14` | missing_regression_assertions | Submitted | 8.7s | 11.3s | 0/2 | 0/0 | $0.0000 | n/a / n/a |
| ptl-openai-gpt-6.1-sol | `attempt-a0975953aa2b4695aa360c53e3a850fd` | accepted | Submitted | 40.5s | 43.7s | 39/39 | 30/30 | $0.0333 | 12412 / 2026 |
| b390-morteza89-27b-int4-20261009 | `attempt-22a933f889e643d6961c940a8f24a775` | accepted | Submitted | 460.9s | 464.1s | 39/39 | 9/9 | $0.0000 | n/a / n/a |
| b390-qwen3-8b-int8-20261010 | `attempt-786e190467224218ab01c19a87291b4d` | missing_regression_assertions | Submitted | 8.6s | 11.2s | 0/2 | 0/0 | $0.0000 | n/a / n/a |
| ptl-openai-gpt-6.1-sol | `attempt-ca0de3de805145d8b55f30ea989cd87e` | accepted | Submitted | 41.1s | 44.4s | 39/39 | 35/35 | $0.0324 | 12545 / 2166 |

Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
