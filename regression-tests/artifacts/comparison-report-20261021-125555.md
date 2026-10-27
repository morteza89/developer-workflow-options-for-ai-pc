# Regression Tests Comparison

Generated: 2026-10-21 19:55 UTC
Frozen task created: 2026-10-20T20:45:25.732925+00:00
Task image: `sha256:2297cd12645d7a77fad76bfc45fdcadf67a3fab99bfd4c098c56ce68acba6842`
Matching model attempts: 9; other saved attempts excluded: 4; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model                           | Provider / model ID               | Device / runtime                                                                                                             | Matching attempts | Other-freeze attempts | Status |
| ------------------------------------------ | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------: | --------------------: | ------ |
| b390-morteza89-27b-int4-20261009           | local / qwen3.8-27b-ov            | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a |                 2 |                     1 | ready  |
| b390-qwen3-8b-int8-20261010                | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a |                 1 |                     1 | ready  |
| ptl-openai-gpt-6.1-sol                     | openai / gpt-6.1-sol              | provider-managed; OpenAI Responses API                                                                                       |                 1 |                     0 | ready  |
| ptl-openai-gpt-6-astra                     | openai / gpt-6-astra              | provider-managed; OpenAI Responses API                                                                                       |                 2 |                     0 | ready  |
| b390-qwen3-coder-30b-a3b-int4-20261020     | local / qwen3-coder-30b-a3b-ov    | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a |                 2 |                     0 | ready  |
| ptl-qwen38-fable5-coding-27b-int4-20261021 | local / qwen38-fable5-int4        | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a |                 1 |                     0 | ready  |

## Summary

| Model                                      | Provider / model ID               | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees |
| ------------------------------------------ | --------------------------------- | -------- | ---------------- | -------: | -------: | ---------: | -------------------: | --------------: | -------------: | --------------: | -------: |
| b390-morteza89-27b-int4-20261009           | local / qwen3.8-27b-ov            | pilot    | `a841892ff8cc` |        2 |        2 | 2/2 (100%) |               671.1s |             7.0 |          18/18 |           54/54 |  $0.0000 |
| b390-qwen3-8b-int8-20261010                | local / OpenVINO/Qwen3-8B-int8-ov | pilot    | `a841892ff8cc` |        1 |        0 |   0/1 (0%) |                  n/a |            13.3 |            9/9 |             0/3 |  $0.0000 |
| b390-qwen3-coder-30b-a3b-int4-20261020     | local / qwen3-coder-30b-a3b-ov    | pilot    | `a841892ff8cc` |        2 |        2 | 2/2 (100%) |                63.8s |            38.1 |          18/18 |             6/6 |  $0.0000 |
| ptl-openai-gpt-6-astra                     | openai / gpt-6-astra              | pilot    | `a841892ff8cc` |        2 |        2 | 2/2 (100%) |                74.9s |            54.0 |          18/18 |           74/74 |  $0.4138 |
| ptl-openai-gpt-6.1-sol                     | openai / gpt-6.1-sol              | pilot    | `a841892ff8cc` |        1 |        1 | 1/1 (100%) |                56.0s |            37.8 |            9/9 |             6/6 |  $0.0224 |
| ptl-qwen38-fable5-coding-27b-int4-20261021 | local / qwen38-fable5-int4        | pilot    | `a841892ff8cc` |        1 |        1 | 1/1 (100%) |               602.6s |             6.9 |            9/9 |           30/30 |  $0.0000 |

## Attempt Details

| Model                                      | Attempt                                      | Outcome             | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens |
| ------------------------------------------ | -------------------------------------------- | ------------------- | ----------- | ---------: | ------------: | --------------: | -------------: | --------------: | ------: | --------------------: |
| b390-morteza89-27b-int4-20261009           | `attempt-883ec4aa218c4746843c6b447fb0bb89` | accepted            | Submitted   |     672.4s |        687.3s |             6.9 |            9/9 |           27/27 | $0.0000 |             n/a / n/a |
| b390-morteza89-27b-int4-20261009           | `attempt-becfea643ea04302a50ce062a7cc93e5` | accepted            | Submitted   |     640.3s |        655.0s |             7.2 |            9/9 |           27/27 | $0.0000 |             n/a / n/a |
| b390-qwen3-8b-int8-20261010                | `attempt-8f9f263af5114fb7b2048ddf10159df3` | verification_failed | Submitted   |      54.9s |         69.0s |            13.3 |            9/9 |             0/3 | $0.0000 |             n/a / n/a |
| ptl-openai-gpt-6.1-sol                     | `attempt-b5517fa392a34b0c8d981848c08a21c4` | accepted            | Submitted   |      37.9s |         56.0s |            37.8 |            9/9 |             6/6 | $0.0224 |           5153 / 1370 |
| ptl-openai-gpt-6-astra                     | `attempt-62807e7f1a394078b593f823d7e12cb5` | accepted            | Submitted   |      60.1s |         75.2s |            50.5 |            9/9 |           36/36 | $0.1948 |           5263 / 2985 |
| b390-qwen3-coder-30b-a3b-int4-20261020     | `attempt-4e269e77ca534578bab2a4ce78fac3c6` | accepted            | Submitted   |      47.6s |         62.2s |            39.4 |            9/9 |             3/3 | $0.0000 |             n/a / n/a |
| b390-qwen3-coder-30b-a3b-int4-20261020     | `attempt-4c01dbb637e7433fbee6492da75cf330` | accepted            | Submitted   |      50.8s |         65.4s |            36.9 |            9/9 |             3/3 | $0.0000 |             n/a / n/a |
| ptl-qwen38-fable5-coding-27b-int4-20261021 | `attempt-c2dba9abbf3043d8b81554f69dab5d00` | accepted            | Submitted   |     586.6s |        602.6s |             6.9 |            9/9 |           30/30 | $0.0000 |             n/a / n/a |
| ptl-openai-gpt-6-astra                     | `attempt-0a758b35d4504e27868b4bfe15c86e00` | accepted            | Submitted   |      59.6s |         74.6s |            57.6 |            9/9 |           38/38 | $0.2190 |           7855 / 3376 |

## Fault Detection

| Model                                      | Attempt                                      | Faults detected | Undetected faults                                                                                                                                                                       | Evaluation errors |
| ------------------------------------------ | -------------------------------------------- | --------------: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| ptl-openai-gpt-6-astra                     | `attempt-0a758b35d4504e27868b4bfe15c86e00` |             8/8 | none                                                                                                                                                                                    | none              |
| b390-qwen3-coder-30b-a3b-int4-20261020     | `attempt-4c01dbb637e7433fbee6492da75cf330` |             8/8 | none                                                                                                                                                                                    | none              |
| b390-qwen3-coder-30b-a3b-int4-20261020     | `attempt-4e269e77ca534578bab2a4ce78fac3c6` |             8/8 | none                                                                                                                                                                                    | none              |
| ptl-openai-gpt-6-astra                     | `attempt-62807e7f1a394078b593f823d7e12cb5` |             8/8 | none                                                                                                                                                                                    | none              |
| b390-morteza89-27b-int4-20261009           | `attempt-883ec4aa218c4746843c6b447fb0bb89` |             8/8 | none                                                                                                                                                                                    | none              |
| b390-qwen3-8b-int8-20261010                | `attempt-8f9f263af5114fb7b2048ddf10159df3` |             0/8 | overwrite_existing_scheme, lose_query, drop_port, lose_credentials_adding_scheme, fail_percent_decode_credentials, wrong_missing_credential_value, retain_fragment, retain_auth_cleanup | none              |
| ptl-openai-gpt-6.1-sol                     | `attempt-b5517fa392a34b0c8d981848c08a21c4` |             8/8 | none                                                                                                                                                                                    | none              |
| b390-morteza89-27b-int4-20261009           | `attempt-becfea643ea04302a50ce062a7cc93e5` |             8/8 | none                                                                                                                                                                                    | none              |
| ptl-qwen38-fable5-coding-27b-int4-20261021 | `attempt-c2dba9abbf3043d8b81554f69dab5d00` |             8/8 | none                                                                                                                                                                                    | none              |

Detection credit requires the same generated tests to pass on clean code and fail by ordinary assertions on each fault, without errors or skips. Raw failing-test counts alone are not detection credit.

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
