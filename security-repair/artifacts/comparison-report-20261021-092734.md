# Security Repair Comparison

Generated: 2026-10-21 16:27 UTC
Frozen task created: 2026-10-20T22:31:22.783998+00:00
Task image: `sha256:0cd2054edd47f253aa6daf6537f82cb3fcb25e6b16cf4257371e54786a45b61a`
Matching model attempts: 5; other saved attempts excluded: 13; matching mock attempts excluded: 1

Only attempts with a saved freeze identical to the selected GUI freeze are included. Different task and profile fingerprints remain separate.

## Model Coverage

| Configured model | Provider / model ID | Device / runtime | Matching attempts | Other-freeze attempts | Status |
| --- | --- | --- | ---: | ---: | --- |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 1 | 5 | ready |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 2 | 2 | ready |
| ptl-openai-gpt-6.1-sol | openai / gpt-6.1-sol | provider-managed; OpenAI Responses API | 0 | 2 | RERUN (2 other freeze) |
| ptl-openai-gpt-6-astra | openai / gpt-6-astra | provider-managed; OpenAI Responses API | 0 | 0 | MISSING |
| b390-qwen3-coder-30b-a3b-int4-20261020 | local / qwen3-coder-30b-a3b-ov | GPU; OVMS 2026.4.0.869b2186; OpenVINO 2026.4.0-22959-99c81491cc3-releases/2026/4; OpenVINO GenAI 2026.4.0.0-3407-7ea2546852a | 2 | 0 | ready |

## Summary

| Model | Provider / model ID | Run type | Task fingerprint | Attempts | Accepted | Acceptance | Median accepted time | Output tokens/s | Contract tests | Generated tests | API fees |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-morteza89-27b-int4-20261009 | local / qwen3.8-27b-ov | pilot | `ad5d499e89ca` | 1 | 1 | 1/1 (100%) | 595.4s | 6.8 | 8/8 | 8/8 | $0.0000 |
| b390-qwen3-8b-int8-20261010 | local / OpenVINO/Qwen3-8B-int8-ov | pilot | `ad5d499e89ca` | 2 | 0 | 0/2 (0%) | n/a | 12.2 | 8/16 | 0/0 | $0.0000 |
| b390-qwen3-coder-30b-a3b-int4-20261020 | local / qwen3-coder-30b-a3b-ov | pilot | `ad5d499e89ca` | 2 | 0 | 0/2 (0%) | n/a | 24.8 | 9/16 | 0/0 | $0.0000 |

## Attempt Details

| Model | Attempt | Outcome | Stop reason | Agent time | Verified time | Output tokens/s | Contract tests | Generated tests | API fee | Input / output tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| b390-qwen3-coder-30b-a3b-int4-20261020 | `attempt-01ea5864462a4aaea922536721817529` | submission_policy_violation | Submitted | 410.8s | 414.6s | 23.6 | 4/8 | 0/0 | $0.0000 | n/a / n/a |
| b390-qwen3-coder-30b-a3b-int4-20261020 | `attempt-990421230bb6400cb2980f99ff33b495` | submission_policy_violation | Submitted | 291.6s | 295.2s | 25.9 | 5/8 | 0/0 | $0.0000 | n/a / n/a |
| b390-morteza89-27b-int4-20261009 | `attempt-d629e6e5267e4b3d8d63d77fe77d41bf` | accepted | Submitted | 591.3s | 595.4s | 6.8 | 8/8 | 8/8 | $0.0000 | n/a / n/a |
| b390-qwen3-8b-int8-20261010 | `attempt-afd1a78cea0d4084ab78785adf0a7bdf` | missing_regression_assertions | Submitted | 37.7s | 41.4s | 12.2 | 4/8 | 0/0 | $0.0000 | n/a / n/a |
| b390-qwen3-8b-int8-20261010 | `attempt-0b461cc32cfc4ef6bf80f657d231e781` | missing_regression_assertions | Submitted | 37.9s | 41.5s | 12.1 | 4/8 | 0/0 | $0.0000 | n/a / n/a |

Output tokens/s is total provider-reported output tokens divided by summed completed model-request wall time (excluding tools and verification); n/a means usage was unavailable. Rates are approximate and may not be directly comparable across tokenizers/providers. Times are runner wall-clock seconds. API fees are estimates from recorded usage; unknown means usage was incomplete. Local API fees exclude hardware and energy costs.
