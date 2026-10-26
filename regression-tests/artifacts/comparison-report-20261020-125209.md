# Regression Tests Comparison

Generated: 2026-10-20 19:52 UTC
Frozen task created: 2026-10-20T18:43:55.249024+00:00
Task image: `sha256:2297cd12645d7a77fad76bfc45fdcadf67a3fab99bfd4c098c56ce68acba6842`
Matching model attempts: 2; other saved attempts excluded: 0; matching mock attempts excluded: 2

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 0 | ready |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 0 | ready |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 0 | MISSING |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | pilot | `a5ca1271e6c0` | 1 | 0 | 0/1 (0%) | n/a | 7.1 | 9/9 | 0/0 | $0.0000 |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | pilot | `a5ca1271e6c0` | 1 | 0 | 0/1 (0%) | n/a | 13.1 | 9/9 | 0/3 | $0.0000 |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | `attempt-2a59973e4e744210a4e01000707a2361` | deadline | deadline | 600.1s | 611.9s | 7.1 | 9/9 | 0/0 | $0.0000 | n/a / n/a |
| b390-qwen3-8b-int8-20261010 | `attempt-2c9ccdbf0a08472eb7a30789474cfe3c` | verification_failed | Submitted | 56.5s | 70.8s | 13.1 | 9/9 | 0/3 | $0.0000 | n/a / n/a |

## Fault Detection

| Model | Attempt | Faults detected | Undetected faults | Evaluation errors |
| --- | --- | ---: | --- | --- |
| b390-morteza89-27b-int4-20261009 | `attempt-2a59973e4e744210a4e01000707a2361` | 0/8 | overwrite_existing_scheme, lose_query, drop_port, lose_credentials_adding_scheme, fail_percent_decode_credentials, wrong_missing_credential_value, retain_fragment, retain_auth_cleanup | none |
| b390-qwen3-8b-int8-20261010 | `attempt-2c9ccdbf0a08472eb7a30789474cfe3c` | 0/8 | overwrite_existing_scheme, lose_query, drop_port, lose_credentials_adding_scheme, fail_percent_decode_credentials, wrong_missing_credential_value, retain_fragment, retain_auth_cleanup | none |

Detection credit requires the same generated tests to pass on clean code and fail by ordinary assertions on each fault, without errors or skips. Raw failing-test counts alone are not detection credit.

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
