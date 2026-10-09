# Validation Record

Authoring date: 2026-10-05. No synthetic model speed or cost results are presented as measurements.

## Current Audited Package: 2026-10-09

The unified policy remains **240 seconds of agent work followed by evaluation of the captured files**. The audit changes strengthen the route/native grader, partial evaluation, truncation feedback, stop-reason reporting, context qualification and operator guidance. Prior freezes and attempts remain immutable and are not pooled with this revision.

- Current freeze: `artifacts/freeze-240s-v3.json`; task hash `9fec2664e9aa06cabb96a5d7c2f5db65cf5a5c2a06bb3bc88bc7e9b1c3b3aafc`. V3 adds backward-compatible reporting for records without an explicit exit status; v2 and the earlier `freeze-240s.json` are retained unchanged. The original TASK hash mismatch was only an added final CRLF, but exact-byte freeze enforcement correctly rejected it.
- Runner tests: **52 passed**. Fixture qualification passed for v1 baseline, expected broken v2 baseline, v2 reference, codemod baseline, and **14 negative controls**, including hardcoded GET output, bypassed POST model boundary, and `pydantic.v1` import.
- Current v3 offline smoke `attempt-b70080c01d8a42539b569a6ea2bb0b92`: **39 contract/native and 2 generated checks passed**, accepted within budget, task paused after **1.158 seconds**, verification complete at **4.396 seconds**, no cleanup errors; zero model calls or fees. This validates the harness, not model capability.
- Prior v2 deadline probe `attempt-7aee1271516f4eee860ddfe1fe89f937`: actual deadline at **240.000 seconds**, confirmed pause at **240.082 seconds**, verification complete at **243.193 seconds**. All **39 contract/native checks passed**; generated tests were absent/empty, so `missing_regression_assertions` and `accepted: false` are the intended results. Container and volume cleanup were clean; zero model calls or fees. The v3 runner change only affects reporting of historical records and the cutoff probe has not been repeated on v3.
- Partial allowed files are now verified even if other allowed files are missing or extra files violate submission policy. Policy violations remain non-accepting but no longer hide protected results. Missing generated-test files receive an explicit generated-phase error while contract checks still run.
- The route grader checks FastAPI request-model boundaries and dynamically changes an attribute record during GET serialization; a hardcoded response is rejected. Native checks catch `from pydantic import v1` and any `model_construct` call. Generated-test screening accepts pytest/unittest assertion styles and rejects trivial constant assertions, but the generated suite is **not mutation-tested** and its defect-detection quality remains unmeasured.
- Captured content can be accepted after a worker/API error if all protected checks pass; `exit_status` and nonstandard stops remain separately reported. Early-submit median/range is separate from deadline successes. The policy preserves actual output-length finish reasons and sends shorter-command guidance to the agent.
- Profile templates no longer assert an unmeasured context limit; scored profiles require a positive recorded limit. The README and model guide align on five unscored pilot attempts per configuration, then five scored attempts if qualified, and identify the working article 27B export.
- No real-model or cloud attempt was run. The mock cutoff proves parent/worker/Docker pause and snapshot timing, not cancellation/drain of an actual OVMS request. The generic runner still cannot observe OVMS request drain or prefix-cache hits; operators must record these and avoid comparing mismatched cache histories. The current platform scope remains the PTL host, not the proposal's NVL/LNL matrix.
- Diagnostics are clear for changed code, tests, policy, profiles and docs. The existing editor-only unresolved test imports remain; the locked runner and v2 environments execute them successfully.

## Historical Four-Minute Package: 2026-10-07

## Historical Four-Minute Package: 2026-10-07

The earlier v06 package replaced the unbounded experiment with 240 seconds of model work followed by evaluation. An early submission ended work sooner. The task was paused before worker termination/export, with no protected feedback returned for further edits. Its evidence is preserved below, but current runs must use the unified freeze above.

- Freeze: `artifacts/freeze-v06.json`; task hash `f9ecd6ae1cc3af012a39cf4795bcc9988fe1f7593ca49a5631ea1d47b064a2f3`. Earlier freezes/attempts remain unchanged.
- Actual four-minute offline probe `attempt-77540614372149a2a23367c4e5926d57`: author-controlled application repairs, no generated tests, then a blocked mock model. Deadline reported at **240.000 seconds**, confirmed task pause at **240.144 seconds**, final verification at **242.947 seconds**. Contract/native checks **38 passed**, generated tests **0**, `missing_regression_assertions`, `accepted: false`, stop reason `deadline`. No cleanup errors. This expected unsuccessful task demonstrates cutoff plus partial evaluation, not model capability.
- Early-submission smoke `attempt-54c0b79955444a2d8589aec37d7f3d04`: **38 contract/native and 2 generated tests passed**, accepted, task paused after **1.115 seconds**, no cleanup errors. Zero model calls/fees in both mocks.
- Runner tests cover deadline enforcement with buffered messages, pause-before-termination ordering, evaluation without a submit marker, named partial results, and contract evaluation despite absent or syntactically invalid regression tests. A deadline snapshot that passes all requirements is fully accepted even without a submit marker; deadline and output correctness are separate fields.
- Reports retain named passed/failed/error/skipped cases and phase totals for unsuccessful attempts. Collection errors mean those tests could not execute. Policy violations prevent execution and remain explicit failures. No acceptance criterion or protected check was relaxed.
- Editor diagnostics remain clear in runner/worker/policy/guides. Test imports remain unresolved in the editor, but execute in the locked runner environment.
- Actual HTTP request cancellation/server drain at the deadline and real-model v06 performance are still unverified. The blocked-model probe exercises the real parent/worker/Docker cutoff without making API calls. Docker/OS failure can delay stopping; measured stop overhead is retained, not hidden.

### Historical Unbounded Run

On October 7, inspection of v05 attempt `attempt-106572dfe0e1463495d12322f0294117` found 51 completed responses, 18 shell actions, 33 output-length finishes and no protected submission. Useful actions stopped about 560 seconds after handoff. The application files were edited and one visible test passed, but oversized test-writing responses never became executable commands; later output degenerated into repeated punctuation. The unlimited format-error loop kept requesting responses. The old processes and active-run lock were gone before v06 validation. Preserve that failed experiment; it is not a four-minute result.

## Historical Completion Policy: 2026-10-06

This superseded experiment continued after rejected submissions until the permitted output passed protected contract/native checks and generated-test verification. It had no task deadline, model-request timeout, step cap, artificial character cap or consecutive-format-error cap. Individual shell/verifier operations remained bounded; infrastructure/API/context errors or manual cancellation could terminate an unsuccessful attempt. This was not a guarantee of convergence or a cloud spending cap and is not the current policy.

- Final freeze: `artifacts/freeze-v05.json`; task hash `24b51a24acd2aa80323bb4712db518cfc538b7a2c24d0a5d64529d92ab9e54d5`. This includes the corrected model-facing task text. All older freezes and attempts remain separate.
- Runner tests: **35 passed** using `.\.venv-runner\Scripts\python.exe -m pytest tests/test_runner.py -q -o pythonpath=.`. Coverage includes no time/step/request/character cutoff, more than 24 agent actions, rejection feedback, accepted snapshots remaining paused, slow accepted results, native usage completeness, and separate local8/local27/cloud report groups.
- Final Docker smoke `attempt-64a1252cc886418abf94d433784ba706`: first submission rejected for missing regression assertions; the same agent loop repaired and resubmitted. Two submission checks, one rejection, both final verifier phases passed, no file-policy violations, no container/volume cleanup errors. Completion was 49.52 seconds; this is a **mock harness check**, not model-performance evidence. Zero model calls and zero model API fees.
- Interim v04 smoke `attempt-ab358ea863f24031b0e769dd22033e8f` also passed rejection/repair/acceptance. v05 additionally removed stale deadline wording from the task and updated the CLI default at that time; neither is the current pilot package.
- Editor diagnostics: no errors in runner, worker, policy or updated guides. Test-file import diagnostics remain for dependencies the editor cannot resolve; those imports and tests work in the explicitly selected locked runner executable above.
- No real-model completion-based attempt had been run at freeze time. The subsequent failed unbounded attempt is recorded above. Two-local-versus-cloud comparison remained pending; no cloud API calls were made.

## Executed Successfully

- Original Pydantic 1.10.24 service: 35 behavior cases pass in an isolated Python 3.11 environment.
- Native Pydantic 2.12.3 reference: the same 35 cases plus three native checks pass.
- Unchanged source in v2: expected startup collection failure on legacy root_validator.
- Official bump-pydantic 0.8.0: execution succeeds; transformed source still fails the expected startup check. Its transformed files are retained. Semantic work is required beyond the codemod.
- Twelve negative controls fail the expected named tests without unrelated collection failures: lost null presence, required notes, lost aliases, lost merchant coercion, receipt boundary error, disabled receipt rule, wrong settings prefix, lost attribute loading, legacy call, v1 compatibility import, stripped whitespace receipt, discarded receipt value.
- Two reference-generated regression tests pass.
- Runner component tests cover permitted-file extraction, protected-file rejection, endpoint restrictions, cloud opt-in, profile completeness, fee/cache categories, interrupted request spans, empty/skipped test rejection, real pinned Mini-SWE-Agent text parsing/submission, dependency inventory, and supervisor timeout/cleanup preservation.
- Agent frontmatter and Python syntax checked. Full task and runner dependency graphs resolved and hash-locked.

The repeatable source of truth is `python qualify.py check` and the resulting artifacts, not this prose. Each qualification directory contains `inputs.json` with file hashes and actual environments, `qualification.json`, individual logs/XML, and the codemod application. Existing generated artifacts stay outside the measured agent's workspace.

## Independent Reviews

Separate read-only agents reviewed (1) contract/reference/grader fidelity and (2) timing, cleanup, isolation and accounting. Findings led to stronger receipt assertions and negative controls, an explicit per-request settings contract, less restrictive attribute-loading checks, dependency/image fingerprints, prompt worker termination, durable cleanup reporting, conservative snapshot-based cutoff scoring, and retained interrupted spans. Follow-up unit tests exercise these corrections.

The initial model-research agent incorrectly reported the requested 27B INT4 artifact absent. Direct review of the exact official card corrected that finding before model profiles were finalized. This is why model availability and API interfaces are checked directly rather than inferred from search summaries.

## Not Yet Verified

- Real container cleanup during cancellation of an in-flight model request under the new policy; normal smoke cleanup and unit tests do not fully cover this case.
- Independent GPU activity, network isolation evidence, full template/system-message fidelity, longest-context behavior, peak memory and paging under the task.
- Qwen3-8B INT4 loading; acceptance of any real local profile on this PTL. The distinct Morteza89 27B export has loaded and served requests, as recorded below.
- Claude API trajectories and billing reconciliation.
- Repeated runs of the two local models and fixed cloud model under the unified 240-second budget, plus later cross-platform scored results. There is no shorter duration qualification gate.

No cloud API calls have been made. Scored runs are intentionally gated on a matching successful container smoke and a completed, operator-qualified profile.

## Local Integration and Pilot Evidence

- Docker Desktop 4.93.0 / Engine 29.8.1 reports Linux containers. The task image is `sha256:183e551061789725ec9bcace0cf1bffcce501f1ea1f7ac0071afb845223947fc`.
- OVMS `2026.4.0.869b2186` loaded the 8B INT8 model. A non-thinking `/v1/chat/completions` warmup returned `READY`, the expected model ID, and usage of 18 input / 2 output tokens. The generated graph specifies GPU; independent activity and memory measurements are still needed.
- Original pilot `attempt-9d1bdbb68ae540d78739da3a1869221b`: rejected as `submission_policy_violation` after 12.81 agent seconds and three model calls. The codemod created its default empty `log.txt`; pytest then exited 2 on the remaining legacy `root_validator`. The model submitted anyway and left the regression-test placeholder unchanged. Removing the log would not make this a correct migration.
- Corrected the shared task/notes to use `bump-pydantic --log-file /tmp/bump-pydantic.log app`. A disposable offline Linux container confirmed that this succeeds without creating `/task/log.txt`. No grader or allowlist relaxation was made.
- New freeze `artifacts/freeze-v03.json`, task hash `a3eb9ee28f463ff0cc422c07bb219b9e5cef2dc774f03db6c76d699e073127e2`: smoke `attempt-b1ef00a224f54c93b586098e489b9dfa` accepted, both contract/generated verifier phases passed, no cleanup errors. Earlier smoke results remain associated with the earlier task hash.
- Unscored v03 pilot `attempt-77dee30326ec4e4493a741bcd0c2bdfb`: one model call emitted only the submit command; rejected as `missing_regression_assertions`, with no submission-policy violations, after 2.73 agent seconds. No code repair or tests were performed. This is a model-performance failure, not a measured success.
- Both local pilots incurred zero cloud model API fees. Neither is an acceptance or calibration result; the private profile remains unqualified. Preserve both trajectories and do not pool their different task hashes.

### Article 27B Enablement and Historical Timed Pilot

- Following the user's tested notebook, the distinct `Morteza89/qwen3.8-27b-int4-ov` export (revision `0b379da0a1b2aa7987693b253724f19ad82928f1`) loaded via [the direct launcher](../models/start-27b-article.cmd). Chat and a native tool call succeeded at `/v3/chat/completions` with returned model `qwen3.8-27b-ov`. This does not establish migration correctness or independent GPU activity.
- Historical v03 attempt `attempt-5f4cc32c38694e03aeaec96c2a3268bc`: stopped at the old 300.19-second deadline, with clean cleanup. Six completed responses produced 976 completion tokens and application-file edits; the seventh request was interrupted before generated tests were written. The snapshot lacked regression assertions and was not accepted. Preserve this failure under v03, not in the v05 comparison.
- Short 128-output-token non-thinking probes took about 17 seconds each. This is request wall time, not pure decode throughput. Low free RAM and paging bursts were observed, but their contribution to inference latency was not established. AC and Windows Best performance were reported by the user. Hardware/profile evidence remains incomplete.

## Acceptance Review Boundary

The grader isolates known references and protected files from the measured agent and re-evaluates only allowed submissions. It is not resistant to arbitrary hostile Python that forges pytest reports or attacks the interpreter. Review production changes and generated tests before publishing benchmark results. A hardcoded service, grader-targeting patch, validation bypass, or unreported background activity invalidates an attempt even if automated checks pass.

Next checkpoint: run a local migration pilot with `artifacts/freeze-240s-v3.json`, inspect partial/full test results after four minutes plus evaluation, and complete host/profile evidence before scoring the three configurations. Security repair and regression-test generation remain reserved, not implemented.