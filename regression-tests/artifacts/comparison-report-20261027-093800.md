# Regression Tests Comparison | INSTALLATION-LOCAL (unscored)

Generated: 2026-10-27 16:38 UTC
Freeze file: regression-tests-INSTALLATION-LOCAL.json
Frozen task created: 2026-10-26T20:44:15.915840+00:00
Task image: `sha256:17717be24a9d15e75b4db4f1b919aa28ba9e5651cb15f2a2cdf44f70889ace88`
Matching model attempts: 3; other saved attempts excluded: 18; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| INSTALLATION-LOCAL article-27b | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 3 | ready |
| INSTALLATION-LOCAL local-8b | local / OpenVINO/Qwen3-8B-int8-ov | GPU; REQUIRED | 1 | 2 | ready |
| INSTALLATION-LOCAL openai | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 1 | RERUN (1 other freeze) |
| INSTALLATION-LOCAL openai-astra | openai / gpt-6-astra | provider-managed; OpenAI Responses API | 1 | 2 | ready |
| INSTALLATION-LOCAL qwen3-coder-30b | local / qwen3-coder-30b-a3b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0; OpenVINO GenAI 2026.4.0 | 0 | 2 | RERUN (2 other freeze) |
| INSTALLATION-LOCAL qwen38-fable5-coding-27b | local / qwen38-fable5-int4 | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | 1 | RERUN (1 other freeze) |

## Request Settings

| Configured model | Sampling | Temperature | Reasoning | Max output tokens | Cap includes reasoning tokens | API |
| --- | --- | ---: | --- | ---: | --- | --- |
| INSTALLATION-LOCAL article-27b | greedy | 0 | disabled | 2048 | no | chat.completions |
| INSTALLATION-LOCAL local-8b | greedy | 0 | disabled | 2048 | no | chat.completions |
| INSTALLATION-LOCAL openai-astra | provider_default | n/a | effort=medium | 2048 | yes | responses |

Settings are taken from the first matching attempt of each configured model. Local and cloud attempts are not identical in sampling/reasoning configuration; this must be considered when comparing results, times, and token rates.

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees | Profile |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| INSTALLATION-LOCAL article-27b | local / qwen3.8-27b-ov | pilot | `3ffecd415d78` | 1 | 1 | 1/1 (100%) | 651.7s | 7.2 | 9/9 | 27/27 | $0.0000 | `430d9b16bd8d` (current) |
| INSTALLATION-LOCAL local-8b | local / OpenVINO/Qwen3-8B-int8-ov | pilot | `3ffecd415d78` | 1 | 0 | 0/1 (0%) | n/a | 13.3 | 9/9 | 0/3 | $0.0000 | `b253ed601f04` (current) |
| INSTALLATION-LOCAL openai-astra | openai / gpt-6-astra | pilot | `3ffecd415d78` | 1 | 1 | 1/1 (100%) | 63.7s | 65.7 | 9/9 | 37/37 | $0.2021 | `6d4bfb782184` (current) |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens | Within budget | Fmt norm. |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| INSTALLATION-LOCAL article-27b | `attempt-1a1e2a26352140ae8d0ac51680824a28` | accepted | Submitted | 636.5s | 651.7s | 7.2 | 9/9 | 27/27 | $0.0000 | 73888 / 4587 | yes | 0 |
| INSTALLATION-LOCAL local-8b | `attempt-cde1db507c6441508d9940dab56125a0` | verification_failed | Submitted | 55.1s | 70.0s | 13.3 | 9/9 | 0/3 | $0.0000 | 2386 / 727 | no | 0 |
| INSTALLATION-LOCAL openai-astra | `attempt-7dde6158245b4699ac853fe526137a56` | accepted | Submitted | 48.5s | 63.7s | 65.7 | 9/9 | 37/37 | $0.2021 | 5283 / 3126 (reasoning 412) | yes | 1 |

## Fault Detection

| Model | Attempt | Faults detected | Undetected faults | Evaluation errors |
| --- | --- | ---: | --- | --- |
| INSTALLATION-LOCAL article-27b | `attempt-1a1e2a26352140ae8d0ac51680824a28` | 8/8 | none | none |
| INSTALLATION-LOCAL openai-astra | `attempt-7dde6158245b4699ac853fe526137a56` | 8/8 | none | none |
| INSTALLATION-LOCAL local-8b | `attempt-cde1db507c6441508d9940dab56125a0` | 0/8 | overwrite_existing_scheme, lose_query, drop_port, lose_credentials_adding_scheme, fail_percent_decode_credentials, wrong_missing_credential_value, retain_fragment, retain_auth_cleanup | none |

Detection credit requires the same generated tests to pass on clean code and fail by ordinary assertions on each fault, without errors or skips. Raw failing-test counts alone are not detection credit.

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. For providers whose output cap includes reasoning tokens, output tokens/s counts reasoning tokens; reasoning tokens are listed separately in the token column when reported. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; ≥ (incomplete) marks a lower bound where some requests lacked usage, and unknown means no fee could be computed. Fmt norm. counts responses whose extra action blocks were discarded. Local API fees exclude hardware and energy costs.
