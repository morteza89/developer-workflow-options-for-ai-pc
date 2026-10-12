# Dependency Migration: Pydantic v1 to v2

**Another laptop:** start with [Replicate on Another Windows Laptop](MODELS.md#replicate-on-another-windows-laptop) for the exact working 27B runtime/model/launcher. Return here for benchmark setup. Do not use the old restart handoff as a fresh-install guide.


**Current policy:** [policy.json](policy.json), [starter/TASK.md](starter/TASK.md), tests and the proposal use one **600-second (10-minute)** work budget. Create and use `artifacts/freeze-600s-v8.json` for the current OpenAI adapter revision. Existing freezes and attempts retain their original inputs and must not be overwritten.

## What You Can Test Now

This is an implemented, resettable benchmark package, **not a hardware-qualified benchmark yet**. The original v1 service and native v2 reference pass 35 identical behavior cases. The v2 reference also passes four native-API and route-boundary checks. Fourteen deliberately incorrect repairs are rejected. The official codemod runs but does not finish this task. Runner unit tests pass. See [VALIDATION.md](VALIDATION.md) for evidence and limitations.

The model gets **600 seconds (10 minutes) of work**, including inference, editing, visible tests and repairs. At the deadline, earlier submission or worker exit, the parent pauses the task, stops the worker and evaluates the saved files. Evaluation runs outside the work budget and includes partial progress. Protected feedback is not returned for another repair round. There is no separate shorter success cutoff or target range; all three models receive the same budget.

The 8B INT8 and the article's distinct Morteza89 27B INT4 endpoints both serve requests; the 27B also passed native tool-call parsing. Under the 600-second policy, the PTL 27B pilot was accepted; the 8B pilot submitted unchanged starter code and was rejected. The first OpenAI GPT-6.1 Sol attempt exposed two adapter issues, now fixed. Its v8 pilot was accepted in 42.66 seconds with 39/39 contract/native checks, 27/27 generated tests, and an estimated $0.03283 API fee. One response had four command blocks; only the first was run, as required by the agent protocol. These are initial pilots, not qualification or a statistical comparison. Check the provider usage dashboard for actual billing. See [MODELS.md](MODELS.md) for setup.

### Current Host Checkpoint

The 10-minute policy uses `artifacts/freeze-600s-v8.json`, also the CLI default. Earlier attempts and freezes, including the unbounded run, remain untouched and cannot be overwritten. The application contract, strengthened native-v2 checks and four-file allowlist are unchanged. Missing or malformed generated tests do not prevent separate application evaluation, but still prevent full acceptance.

The next optional local test is unscored, from this folder in clean PowerShell, with OVMS still running:

```powershell
.\.venv-runner\Scripts\python.exe bench.py run --profile profiles\ptl-morteza89-27b.private.json --freeze artifacts\freeze-600s-v8.json
```

Keep `qualified: false` until pilot review and required host/profile measurements are complete. Do not run scored loops yet. Normally let the deadline finish the run so the snapshot gets evaluated. Ctrl+C is emergency cancellation with available artifacts/usage retained and cleanup attempted; it does not guarantee a final snapshot. Shell actions retain a 30-second timeout and verifier execution phases a 60-second timeout. Preparation, snapshot overhead, evaluation and cleanup mean the complete command can take longer than 10 minutes.

## Workflow

```mermaid
flowchart LR
    .\.venv-runner\Scripts\python.exe bench.py freeze --output artifacts\freeze-600s-v8.json
    .\.venv-runner\Scripts\python.exe bench.py smoke --freeze artifacts\freeze-600s-v8.json
    C --> D[Same Mini-SWE-Agent loop]
    L[Local OVMS] --> D
    R[Fixed OpenAI API for this comparison] --> D
    D --> E[Read - edit - test - repair]
    E --> D
    D --> F[Submit early or reach 600 seconds]
    F --> G[Pause task - stop agent - snapshot files]
    G --> H[Check allowed files]
    H --> I[Fresh protected contract verifier]
    H --> J[Separate generated-test verifier]
    I --> K[Named pass - fail - error - skipped results]
    J --> K
    K --> N[Full acceptance or partial progress - timings - usage - fees]

```

The developer task is in [starter/TASK.md](starter/TASK.md). It repairs three models, settings, and routes after an already-installed Pydantic upgrade. Requirements include aliases, strict integer cents, numeric merchant-code coercion, receipt rules, omitted versus null notes, per-request settings, and record-object loading. This is an API-contract migration, not a dependency downgrade or compatibility shim.

Editable submission: `app/schemas.py`, `app/settings.py`, `app/routes.py`, and `tests/test_generated.py`. Everything else is preserved or rejected. Generated tests must execute, contain assertions, and pass; they are not a full test-quality benchmark. The protected contract is the correctness authority.

## 1. Test the Fixture Without Any Model

Use PowerShell from this folder. Python 3.11 and `uv` are required. Commands install only workflow-local virtual environments; downloads happen before measurement.

```powershell
Set-Location C:\projects\Developer_Workflow_Options_for_AI_PC\dependency-migration
python qualify.py prepare
python qualify.py check
```

Expected: every line says `PASS`. A broken baseline or deliberately incorrect repair normally has a nonzero inner exit code: that is an expected rejection, not a qualification failure. The qualification command itself must exit 0. Evidence goes to a new `artifacts/qualification-...` directory, including logs, structured test results, codemod output, source hashes, and actual environment versions. `prepare` syncs exact hash-locked dependencies; `check` rejects version drift.

The trusted authoring checks run on the host. **Never use qualify.py to execute a model's submission.** Its inputs are our controlled references and mutants only.

`prepare` is safe to repeat: it creates missing environments, reuses valid Python 3.11 environments, and resyncs their locked dependencies. It does not delete existing environments. If an existing environment is incomplete or uses a different Python version, it stops and asks you to move that folder aside before retrying.

## 2. Prepare the Runner and Container

```powershell
if (-not (Test-Path .venv-runner)) { uv venv --python 3.11 .venv-runner }
uv pip sync --python .venv-runner\Scripts\python.exe --require-hashes requirements-runner.lock
.\.venv-runner\Scripts\python.exe -m pytest tests -q -o pythonpath=.
docker version
docker info --format '{{.OSType}}'
docker build --tag migration-task:0.1 .
```

Docker Desktop must already be installed, running, and configured for **Linux containers** using its qualified WSL2 backend. Install it using your organization's approved procedure if missing. The runner will not silently run generated code on the Windows host. Docker setup requiring elevation is a user/administrator step.

The task image uses Python 3.11.14-slim-bookworm, installs hash-locked Pydantic v2 dependencies, and runs as a non-root user. Its concrete image ID is recorded in each freeze.


On another OS, use `.venv-runner/bin/python` instead of the Windows executable path. Keep the principal comparison on the same OS/runtime arrangement. Transfer the built image with `docker save`/`docker load` for the same image ID across hosts; rebuilding from a mutable base tag may produce a different image, and results will then be separated.

## 3. Freeze and Exercise the Complete Offline Harness

```powershell
.\.venv-runner\Scripts\python.exe bench.py freeze --image migration-task:0.1 --output artifacts\freeze-600s-v8.json
.\.venv-runner\Scripts\python.exe bench.py smoke --freeze artifacts\freeze-600s-v8.json
```

Skip freeze creation if that exact freeze already exists; never overwrite it. Expected smoke: `accepted: true`, `mock: true`, `scored: false`, early submission, 39 contract/native checks and two generated tests passing, zero model calls/fees. References are supplied only to this labeled mock, never to the real model. Smoke is not model-quality or speed evidence.

To test the actual 10-minute cutoff without any model, use `bench.py smoke --freeze artifacts\freeze-600s-v8.json --deadline-probe` with the same runner executable. This writes reference application repairs but no regression tests, then blocks the mock worker. Expected: deadline at 600 seconds, snapshot-stop overhead reported separately, 39 contract/native passes, zero generated tests, `accepted: false`, exit code 1 and clean cleanup. That rejection is the intended probe result, not a broken harness.

Freeze captures source, published contract, notes, reference, grader, locks, policy, runner code, and the concrete image ID. It does not overwrite an existing freeze. After a justified pre-comparison change to this 600-second package, create a fresh v9 freeze:

```powershell
.\.venv-runner\Scripts\python.exe bench.py freeze --output artifacts\freeze-600s-v8.json
.\.venv-runner\Scripts\python.exe bench.py smoke --freeze artifacts\freeze-600s-v8.json
```

Supply that same `--freeze` path to later runs. Freeze creation is not proof of calibration. Re-run qualification after changing the fixture or checks.

## 4. Qualify a Local Model

Follow [MODELS.md](MODELS.md) for model preparation, OVMS commands, memory checks, profile completion, and cloud setup. The working 27B endpoint on this host is the article export **Morteza89/qwen3.8-27b-int4-ov**, using `profiles/ptl-morteza89-27b.private.json`, based on the tracked `profiles/article-27b.json` template. Do not substitute the removed OpenVINO 27B export profile. Confirm that each OVMS export honors the non-thinking request setting.

Local profiles contain observed machine identity but deliberately retain `qualified: false` and missing measurement fields. Those are not promises that the model will fit or succeed. Duplicate profiles before editing so results retain a clear configuration identity.

```powershell
if (-not (Test-Path profiles\ptl-8b.private.json)) { Copy-Item profiles\local-8b.json profiles\ptl-8b.private.json }
.\.venv-runner\Scripts\python.exe bench.py run --profile profiles\ptl-8b.private.json
```

This is an unscored pilot; it still uses the frozen task and retains failures. Inspect the full trajectory, tests, model identity, native usage, and submitted source. Correct serving or routing problems before calibrating task scope. No model download/startup should occur inside this command. Keep the server resident and warmed, with the documented cache condition.

For the running article export use [profiles/ptl-morteza89-27b.private.json](profiles/ptl-morteza89-27b.private.json), copied from [profiles/article-27b.json](profiles/article-27b.json). Do not reduce the frozen task for either local model.

## 5. Compare Two Local Models and Cloud

For the current PTL comparison, use local Qwen3-8B INT8, local Morteza89 Qwen3.8-27B INT4, and one pinned OpenAI API model (`gpt-6.1-sol`). All receive the same frozen task, 600-second work budget, agent permissions and post-work checks. The OpenAI run uses the Responses API with medium reasoning effort; temperature is not sent. The adapter converts the agent transcript to Responses-compatible `role`/`content` messages, strips unsupported Chat Completions fields such as `tool_calls`, and if the model returns multiple action blocks it logs the raw response and sends only the first command to the agent. Record these provider-specific compatibility behaviors in comparisons. Run only one local server at a time. Claude remains a separately supported provider and its results must not be grouped with OpenAI.

### Initial PTL Results (v8)

| Configuration | Result | Handoff / through verification | Contract/native | Generated tests | Calls; tokens | Estimated API fee |
|---|---|---:|---:|---:|---|---:|
| Qwen3.8 27B INT4 | Accepted | 432.99 s / 436.13 s | 39/39 | 12/12 | 15; 69,949 input, 3,067 output | $0.00 |
| Qwen3 8B INT8 | Rejected; submitted unchanged starter | 8.76 s / 11.40 s | Collection error (2 errors; no contract checks ran) | 0 | 4; 4,792 input, 80 output | $0.00 |
| OpenAI GPT-6.1 Sol | Accepted | 42.66 s / 45.77 s | 39/39 | 27/27 | 4; 12,499 input, 2,211 output | $0.032829 estimated |

Attempt records: [27B](artifacts/attempt-8b0e51f33b8a4a3186be8f05810ee109/result.json), [8B](artifacts/attempt-20eb2a59ba3644b9b72e3037baa6d5ba/result.json), [OpenAI](artifacts/attempt-59734f17f8ec44399f369e8401fc0064/result.json). All three use task hash `58678ca6f07db6309a3d12f53a6c5743f82d4e5ae9df6e17d1eb41a3169f3762` and image `sha256:74283564a52c5969dec0355e2d0fa1f297110fd8be55f0b6d497650a627315a5`.

These are single unscored pilots, not qualification or statistical evidence. Output rates are not directly comparable across tokenizers. The OpenAI adapter discarded three extra action blocks from one response and ran only the first; disclose this provider-specific normalization. The saved 8B v8 attempt captured the profile before its host metadata was corrected; the current private profile is now corrected, but that immutable attempt record still has the old profile snapshot.

Compare full acceptance, named partial results, and early completion time. Do not resize the task for a model or discard partial/failed attempts. Following the proposal, run five supervised unscored pilot attempts per configuration and review their saved files/results and profile evidence. If the configurations qualify, run the same predeclared number of scored attempts for all three; the initial plan is five additional scored attempts each. Every attempt starts from a fresh task. Submission ends work early even if later protected evaluation fails; there is no protected repair loop under this policy.

After pilot review, complete the host/inference evidence and set `qualified` to true in each approved profile. This is an operator attestation, not an automatically inferred hardware fact. The runner checks completeness, current installed runner versions, image/task identity, and an accepted matching Docker smoke before permitting `--scored`.

Run each attempt individually from the saved interleaving schedule. Switch the local server only between attempts and wait until any previous request has drained. For example:

```powershell
.\.venv-runner\Scripts\python.exe bench.py run --profile profiles\ptl-8b.private.json --scored
.\.venv-runner\Scripts\python.exe bench.py report
```

Run one at a time: an exclusive attempt lock rejects overlap. The initial PTL plan is five attempts each for **local 8B, local 27B, and pinned OpenAI GPT-6.1 Sol**: 15 runs on this host. Randomize/interleave configuration order in a saved schedule while loading only one local model at a time. Other hosts, NPU and AMD are later, separate qualifications. Do not omit failed attempts.

OpenAI API invocation is an unscored pilot first, with an explicit cloud opt-in:

The parent enforces the same 10-minute work limit for cloud, but this is not a dollar spending cap. Review provider spending controls; in-flight work may remain billable after client termination. See [MODELS.md](MODELS.md).

```powershell
.\.venv-runner\Scripts\python.exe bench.py run --profile profiles\ptl-openai.private.json --freeze artifacts\freeze-600s-v8.json --allow-cloud
```

See [MODELS.md](MODELS.md#openai-api-through-the-same-agent) for Console/API key setup, profile preparation, model identity and rate-card details. VS Code Copilot Chat is not the API provider used in this measurement.

## Timing and Cost Definitions

| Field | Meaning |
|---|---|
| `submission_seconds` | Handoff to submission or the scheduled deadline (600 seconds) |
| `agent_seconds` | Handoff through confirmed task pause; excludes final evaluation |
| `cutoff_overrun_seconds` | Actual pause time beyond the deadline due to scheduling/Docker stop overhead |
| `accepted_within_budget` | Captured saved output passes evaluation within the work budget; stop reason is reported separately. Historical records without this metric remain unknown, not reclassified |
| Full acceptance | The captured snapshot respects file policy and passes both verifier phases, regardless of whether it stopped by submission, deadline or worker error |
| `completion_seconds` | Handoff through verified final output collection; null for unsuccessful attempts |
| `median_early_success_seconds` / `early_success_range_seconds` | Submission-to-handoff times for accepted attempts that ended with an explicit submit; deadline successes are excluded |
| `verifier_seconds` | Post-work verifier execution/setup time |
| `verification.test_results` | Per-phase totals and named passed/failed/error/skipped test cases |
| `submission_check_seconds` | Zero under this policy; retained for historical completion-loop results |
| `through_verification_seconds` | Elapsed through final verification/output collection, excluding cleanup |
| `request_seconds` / `tool_seconds` | Client-observed request spans / shell spans; submission-check waits excluded from shell time |
| `api_fee_usd` | Native usage multiplied by the saved rate card; null when billing cannot be established |

At submission, deadline or worker exit, the parent pauses the task before terminating the worker, then exports and verifies the captured snapshot in fresh containers. No further model edits are accepted. A file interrupted mid-write is evaluated as captured; source that appeared only in an incomplete model response is not a saved edit. `exit_status` retains the stop reason even if saved files pass. Missing assertions, missing test files, or invalid generated-test syntax are reported separately and do not hide contract results. Unpermitted changes prevent acceptance but no longer suppress protected checks on the allowed files. Collection errors mean tests could not execute, not that every behavior was tested and failed. Provider-side work may continue after client termination; unknown fees stay null. Cleanup and stop overhead are separately recorded.

Reports include acceptance rate, early-success median/range, nonstandard worker stops, per-attempt named test results in `evaluation_results`, contract/generated phase passes, timings, model/tool calls, failed tools, native usage, incomplete requests, cleanup failures and API fees. Generated tests are checked for execution, passing results and a nontrivial assertion pattern, but are not mutation-tested; acceptance does not establish their defect-detection quality. `completed_request_output_tokens_per_second` uses completed request wall time, not pure decode speed. Native usage is not normalized across tokenizers. TTFT/prefill/decode, energy and GPU-memory figures require separate instrumentation. SDK retries stay disabled; repair/format-error turns are counted. No fallback provider exists.

Reports group by package/image/actual-runner fingerprint and complete profile hash, and separate pilots, mocks, and scored runs. Per-group API cost per accepted task includes failures: total fees divided by accepted attempts. Zero successes, missing usage, or unresolved billed requests produce null/undefined, not zero. Local runs mean **$0 cloud model API fees**, not free hardware, power, or engineering. No cloud energy estimate is made.

## Reset and Inspect

Each `run` makes a unique directory and fresh container, Docker task volume, conversation, source, Python process, and test caches. No destructive Git reset is needed; rerun the same command. The model stays resident according to your cache policy. References and the source proposal are never mounted in the measured container. API credentials remain on the runner host, not in task containers or profile files. The task volume is removed after export; it is not a host-directory mount. Monitor available Docker disk space during pilots.

An attempt retains `profile.json`, `freeze.json`, `trajectory.json` when available, append-only events, native usage, exported workspace, four-file submission, verifier XML/logs and `result.json`. Older completion-loop attempts may also have `check-*` snapshots. Submission files are authoritative, not a self-reported diff. Early failures may lack trajectory/submission but retain a result once attempt creation starts. Preflight errors occur before an attempt starts.

If interrupted by a machine crash, preserve the attempt folder. Check `artifacts/active-run.json` and its PID; remove a stale lock only after confirming no attempt is running. List `migration-agent-*` and `migration-verifier-*` containers and their named `migration-agent-*-task` volumes; remove only abandoned resources from this workflow. Do not bulk-delete other Docker resources. Agent, volume, and verifier cleanup errors are retained; any cleanup error invalidates readiness for the next attempt until resolved.

## Limits and Design Decisions

- Mini-SWE-Agent 2.4.6 is reused, with its text-action parser and standard read/edit/test loop. Official OpenAI and Anthropic SDK adapters preserve native usage with retries disabled. No second custom coding-agent loop is invented.
- Harbor was a proposal, not a fixed requirement. This first Windows package uses a focused supervisor instead. Docker and endpoint integration must pass smoke/pilots before calling this choice qualified. It is not advertised as a Harbor task.
- The parent enforces 600 seconds even during an unresponsive model request. There is no additional step or conversation-character cap; backend context limits still apply, without silent compaction. The 2048-token response limit remains, and the shared prompt requests small complete commands. A stalled or repetitive model can consume its 10 minutes but cannot keep the coding loop running indefinitely. Docker/OS failures are infrastructure exceptions, not hard real-time guarantees.
- The fixed temperature 0 is an experimental choice, not the Qwen authors' quality-optimal sampling recommendation. Qualify it; change common settings only before freezing. No seed is sent because support is not assumed. Repeated runs are still necessary.
- This is cooperative coding evaluation. Read-only files and separate processes reduce accidental leakage and tampering; executing submitted Python with pytest is not an adversarial-proof grader. Review accepted diffs for hardcoded routes, grader-targeting, validation bypass, or process tampering before publishing acceptance. Do not expose this host/container setup to malicious code.
- Qualification contracts are public; only grader implementation and references are hidden from measured agents. Functionally equivalent native solutions are intended to pass. Security repair and regression-test workflows remain unimplemented pending your approval.
- The current package is a PTL-host pilot with two local candidates and Claude, not the proposal's multi-host NVL/LNL matrix. Harbor was deliberately replaced with the focused supervisor. The agent sees the reproducible failing visible test and migration notes, not a separate CI log.
- The generic runner cannot inspect OVMS request drain or per-attempt prefix-cache hits. Confirm previous local requests have ended, record server restarts/cache state/run order, and do not treat different warm-cache histories as equivalent.
- A deadline can snapshot a file during a write. The verifier evaluates the bytes captured; an incomplete file can cause a collection error.

**Current feedback checkpoint:** use the current pilot command above with the article 27B server ready and no previous request still running. Review partial/full test results after 10 minutes plus evaluation, then repeat the same policy for 8B/cloud. Do not move to security repair until this workflow is accepted. Fresh hosts first pass setup and smoke.