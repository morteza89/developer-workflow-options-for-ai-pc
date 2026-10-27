# Dependency Migration Comparison | INSTALLATION-LOCAL (unscored)

Generated: 2026-10-27 03:08 UTC
Freeze file: dependency-migration-INSTALLATION-LOCAL.json
Frozen task created: 2026-10-26T20:37:56.172970+00:00
Task image: `sha256:d9bcaceecbf469cec0d1a2c26e83db6257ad13ddb921dc471f4ef05b718b0850`
Matching model attempts: 3; other saved attempts excluded: 42; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| INSTALLATION-LOCAL article-27b | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 8 | ready |
| INSTALLATION-LOCAL local-8b | local / OpenVINO/Qwen3-8B-int8-ov | GPU; REQUIRED | 1 | 6 | ready |
| INSTALLATION-LOCAL openai | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 6 | RERUN (6 other freeze) |
| INSTALLATION-LOCAL openai-astra | openai / gpt-6-astra | provider-managed; OpenAI Responses API | 1 | 2 | ready |
| INSTALLATION-LOCAL qwen3-coder-30b | local / qwen3-coder-30b-a3b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0; OpenVINO GenAI 2026.4.0 | 0 | 2 | RERUN (2 other freeze) |
| INSTALLATION-LOCAL qwen38-fable5-coding-27b | local / qwen38-fable5-int4 | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | 2 | RERUN (2 other freeze) |

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
| INSTALLATION-LOCAL article-27b | local / qwen3.8-27b-ov | pilot | `c2b0b2ec086b` | 1 | 1 | 1/1 (100%) | 514.7s | 6.6 | 47/47 | 9/9 | $0.0000 | `430d9b16bd8d` (current) |
| INSTALLATION-LOCAL local-8b | local / OpenVINO/Qwen3-8B-int8-ov | pilot | `c2b0b2ec086b` | 1 | 0 | 0/1 (0%) | n/a | 8.7 | 0/2 | 0/0 | $0.0000 | `b253ed601f04` (current) |
| INSTALLATION-LOCAL openai-astra | openai / gpt-6-astra | pilot | `c2b0b2ec086b` | 1 | 0 | 0/1 (0%) | n/a | n/a | 0/2 | 0/0 | ≥ $0.0000 (incomplete) | `6d4bfb782184` (current) |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens | Within budget | Fmt norm. |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| INSTALLATION-LOCAL article-27b | `attempt-035c2ecba3f74921aa948c3a9c9e303d` | accepted | Submitted | 510.6s | 514.7s | 6.6 | 47/47 | 9/9 | $0.0000 | 71383 / 3330 | yes | 0 |
| INSTALLATION-LOCAL local-8b | `attempt-e8c2f54665ef43838ffae870b15c8c6e` | verification_failed | Submitted | 9.8s | 13.2s | 8.7 | 0/2 | 0/0 | $0.0000 | 4792 / 80 | no | 0 |
| INSTALLATION-LOCAL openai-astra | `attempt-a487212a111e46959528d876e4a85c60` | error | error | 1.0s | 4.1s | n/a | 0/2 | 0/0 | ≥ $0.0000 (incomplete) | n/a / n/a | no | 0 |

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. For providers whose output cap includes reasoning tokens, output tokens/s counts reasoning tokens; reasoning tokens are listed separately in the token column when reported. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; ≥ (incomplete) marks a lower bound where some requests lacked usage, and unknown means no fee could be computed. Fmt norm. counts responses whose extra action blocks were discarded. Local API fees exclude hardware and energy costs.
