# Requests Regression Tests Comparison (720 seconds)

Generated: 2026-10-20 20:58 UTC
Frozen task created: 2026-10-20T20:45:25.732925+00:00
Task image: `sha256:2297cd12645d7a77fad76bfc45fdcadf67a3fab99bfd4c098c56ce68acba6842`
Matching model attempts: 1; other saved attempts excluded: 4; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 1 | ready |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | 1 | RERUN (1 other freeze) |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 0 | MISSING |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | pilot | `a841892ff8cc` | 1 | 1 | 1/1 (100%) | 687.3s | 6.9 | 9/9 | 27/27 | $0.0000 |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | `attempt-883ec4aa218c4746843c6b447fb0bb89` | accepted | Submitted | 672.4s | 687.3s | 6.9 | 9/9 | 27/27 | $0.0000 | n/a / n/a |

## Fault Detection

| Model | Attempt | Faults detected | Undetected faults | Evaluation errors |
| --- | --- | ---: | --- | --- |
| b390-morteza89-27b-int4-20261009 | `attempt-883ec4aa218c4746843c6b447fb0bb89` | 8/8 | none | none |

Detection credit requires the same generated tests to pass on clean code and fail by ordinary assertions on each fault, without errors or skips. Raw failing-test counts alone are not detection credit.

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
