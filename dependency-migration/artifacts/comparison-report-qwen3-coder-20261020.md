# dependency-migration Comparison with Qwen3-Coder

Generated: 2026-10-20 22:58 UTC
Frozen task created: 2026-10-20T22:31:19.497731+00:00
Task image: `sha256:74283564a52c5969dec0355e2d0fa1f297110fd8be55f0b6d497650a627315a5`
Matching model attempts: 1; other saved attempts excluded: 24; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | 6 | RERUN (6 other freeze) |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | 5 | RERUN (5 other freeze) |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 6 | RERUN (6 other freeze) |
| ptl-openai-gpt-6-astra | openai / gpt-6-astra | provider-managed; OpenAI Responses API | 0 | 0 | MISSING |
| b390-qwen3-coder-30b-a3b-int4-20261020 | local / qwen3-coder-30b-a3b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 0 | ready |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-qwen3-coder-30b-a3b-int4-20261020 | local / qwen3-coder-30b-a3b-ov | pilot | `9a80903bd1f2` | 1 | 0 | 0/1 (0%) | n/a | 26.9 | 25/39 | 8/8 | $0.0000 |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-qwen3-coder-30b-a3b-int4-20261020 | `attempt-1cb8f6af894f46cea82c3f100b6a4ed4` | submission_policy_violation | deadline | 600.1s | 603.8s | 26.9 | 25/39 | 8/8 | $0.0000 | n/a / n/a |

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
