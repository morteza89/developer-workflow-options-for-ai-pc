# Dependency Migration Comparison

Generated: 2026-10-13 19:39 UTC
Frozen task created: 2026-10-12T22:42:21.223991+00:00
Task image: `sha256:74283564a52c5969dec0355e2d0fa1f297110fd8be55f0b6d497650a627315a5`
Matching model attempts: 0; other saved attempts excluded: 23; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | 6 | RERUN (6 other freeze) |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | 5 | RERUN (5 other freeze) |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 6 | RERUN (6 other freeze) |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
