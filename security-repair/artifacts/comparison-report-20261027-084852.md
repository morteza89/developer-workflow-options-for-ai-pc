# Security Repair Comparison | INSTALLATION-LOCAL (unscored)

Generated: 2026-10-27 15:48 UTC
Freeze file: security-repair-INSTALLATION-LOCAL.json
Frozen task created: 2026-10-26T20:39:04.525863+00:00
Task image: `sha256:eeea5742be8e7abec574d8173720eaed9b0e1392743f263f04d698e74156136c`
Matching model attempts: 2; other saved attempts excluded: 29; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| INSTALLATION-LOCAL article-27b | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 8 | ready |
| INSTALLATION-LOCAL local-8b | local / OpenVINO/Qwen3-8B-int8-ov | GPU; REQUIRED | 0 | 4 | RERUN (4 other freeze) |
| INSTALLATION-LOCAL openai | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 2 | RERUN (2 other freeze) |
| INSTALLATION-LOCAL openai-astra | openai / gpt-6-astra | provider-managed; OpenAI Responses API | 1 | 1 | ready |
| INSTALLATION-LOCAL qwen3-coder-30b | local / qwen3-coder-30b-a3b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0; OpenVINO GenAI 2026.4.0 | 0 | 3 | RERUN (3 other freeze) |
| INSTALLATION-LOCAL qwen38-fable5-coding-27b | local / qwen38-fable5-int4 | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 0 | 1 | RERUN (1 other freeze) |

## Request Settings

| Configured model | Sampling | Temperature | Reasoning | Max output tokens | Cap includes reasoning tokens | API |
| --- | --- | ---: | --- | ---: | --- | --- |
| INSTALLATION-LOCAL article-27b | greedy | 0 | disabled | 2048 | no | chat.completions |
| INSTALLATION-LOCAL openai-astra | provider_default | n/a | effort=medium | 2048 | yes | responses |

Settings are taken from the first matching attempt of each configured model. Local and cloud attempts are not identical in sampling/reasoning configuration; this must be considered when comparing results, times, and token rates.

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees | Profile |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| INSTALLATION-LOCAL article-27b | local / qwen3.8-27b-ov | pilot | `a14c3a99af07` | 1 | 0 | 0/1 (0%) | n/a | 6.4 | 16/19 | 7/7 | $0.0000 | `430d9b16bd8d` (current) |
| INSTALLATION-LOCAL openai-astra | openai / gpt-6-astra | pilot | `a14c3a99af07` | 1 | 0 | 0/1 (0%) | n/a | n/a | 11/19 | 0/0 | ≥ $0.0000 (incomplete) | `6d4bfb782184` (current) |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens | Within budget | Fmt norm. |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| INSTALLATION-LOCAL article-27b | `attempt-a14ad5522b4a4c3e98875a0e70fb8fef` | verification_failed | Submitted | 579.0s | 583.6s | 6.4 | 16/19 | 7/7 | $0.0000 | 187157 / 3692 | no | 0 |
| INSTALLATION-LOCAL openai-astra | `attempt-a182c814f86c458296b7a19fe1ff1def` | error | error | 1.9s | 6.3s | n/a | 11/19 | 0/0 | ≥ $0.0000 (incomplete) | n/a / n/a | no | 0 |

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. For providers whose output cap includes reasoning tokens, output tokens/s counts reasoning tokens; reasoning tokens are listed separately in the token column when reported. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; ≥ (incomplete) marks a lower bound where some requests lacked usage, and unknown means no fee could be computed. Fmt norm. counts responses whose extra action blocks were discarded. Local API fees exclude hardware and energy costs.
