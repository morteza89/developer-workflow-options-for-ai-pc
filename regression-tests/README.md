# Regression Tests

Option 4 writes tests for correct, immutable Requests 2.31.0 at commit `147c8511ddbfa5e8f71bbf5c18ede0c4ceb3bba4`. The only editable file is [starter/tests/test_generated.py](starter/tests/test_generated.py), initially zero bytes. The targets are `requests.utils.prepend_scheme_if_needed`, `get_auth_from_url`, and `urldefragauth`. No network requests are required.

The generated suite must pass on clean production and detect eight frozen, reachable behavior-changing faults with ordinary assertion failures. Errors, skips, xfail, `pytest.fail`, and stubbed implementations do not count. [starter/TASK.md](starter/TASK.md) gives the behavior and import contract. A scheme-less URL with credentials needs a leading `//`; bare `user:password@host` is not the same case.

## Status

Implemented task package with pinned source, hashed dependency lock, visible examples, 25 human reference cases, eight independent protected fault witnesses, and eleven invalid-submission controls. Docker qualification `qualification-check-f21daa4a67f2` passed the reference, all eight faults, independent Docker witnesses, and all eleven invalid controls. The shared runner suite passes 84 tests. See [VALIDATION.md](VALIDATION.md).

Shared-engine fault phases, production-replacement protection, and controller registration are integrated. The initial freeze name is `freeze-600s-requests-v1.json`; saved `artifacts/attempt-*/result.json` records are the authority for accepted smoke and 600-second deadline-probe outcomes. These offline attempts are not model/profile performance or hardware qualification.

## Setup

Prerequisites: Docker Desktop in Linux-container mode and the locked shared runner at `dependency-migration/.venv-runner`. Run commands below from the repository root in PowerShell. Docker-only qualification does not require a host task environment or host task dependencies.

```powershell
$Runner = '.\dependency-migration\.venv-runner\Scripts\python.exe'
docker build --tag requests-regression:0.1 .\regression-tests
& $Runner .\regression-tests\qualify.py check --image requests-regression:0.1
```

`check` validates production hashes and exact fault replacements, runs independent protected witnesses on clean source and all eight mutants in Docker, then uses `engine.verify` for the reference and all eleven controls. It requires named fault-phase checks and JUnit results, fails closed on missing phases or infrastructure errors, and requires `production_function_replacement` for the alias-preserving stub.

Both modes save JSON evidence and per-phase JUnit/log files under ignored `regression-tests/artifacts/qualification-*`. The eleven controls cover empty, trivial, incorrect expectations, import errors, skips, xfail, stubs, `pytest.fail`, protected-witness reuse, artificial raises, and alias-preserving production replacement. The last control retains the original directly imported functions and reference assertions, then replaces a production module attribute; clean/fault outcomes alone cannot establish eligibility. Local source eligibility uses the same `engine.regression_source_issue` guard and permits nonconstant assertions in module helpers. The reference is constructed by copying clean `starter/` and overlaying only `reference/tests/test_generated.py`.

The image uses exactly `python:3.11.14-slim-bookworm`, hashed installs, non-root UID 10001, disabled plugin autoload, and `PYTHONPATH=/task`, matching Security Repair. The shared verifier provides read-only mounts/rootfs, `--network none`, dropped capabilities, no-new-privileges, resource limits, and ephemeral report storage. Building the image requires network access; verification and the agent task do not.

## Optional Local Diagnostic

For trusted package/reference/control diagnostics only, install `uv` and create a separate environment using the pinned task lock:

```powershell
$TaskPython = '.\regression-tests\.venv-task\Scripts\python.exe'
uv venv --python $Runner .\regression-tests\.venv-task
uv pip sync --require-hashes --python $TaskPython .\regression-tests\requirements-task.lock
& $TaskPython .\regression-tests\qualify.py local
```

`local` executes trusted suites and protected witnesses on the host. It records `isolated_qualification: false` and is not a substitute for Docker qualification. Never use host execution to evaluate untrusted model submissions.

## Freeze and Smoke

For a newly authored package, after successful isolated qualification, create a new freeze and run both smoke gates. To join an existing comparison, transfer its exact image, source bytes, runner build, and freeze instead of creating a laptop-specific replacement; see the repository's cross-laptop guide. Skip freeze creation when that selected file already exists:

```powershell
$Freeze = '.\regression-tests\artifacts\freeze-600s-requests-v1.json'
& $Runner .\regression-tests\bench.py freeze --image requests-regression:0.1 --output $Freeze
& $Runner .\regression-tests\bench.py smoke --freeze $Freeze
& $Runner .\regression-tests\bench.py smoke --freeze $Freeze --deadline-probe
& $Runner .\regression-tests\bench.py report --directory .\regression-tests\artifacts
```

The default freeze is `regression-tests/artifacts/freeze-600s-requests-v1.json`. It binds the task, source, reference, grader, policy, workflow/fault definitions, task dependencies, shared engine, and image. A freeze is not model qualification. Do not overwrite an existing freeze; use a new explicit `--output` and pass the corresponding `--freeze` to subsequent commands after package changes. Smoke must seed only the allowed generated file from the reference, never replace immutable production. Require an accepted smoke for the exact freeze before model runs. A deadline probe (`bench.py smoke --deadline-probe`) uses the same 600-second budget and is not an accepted-task smoke.

## Model Runs and Controller

After the gates above, double-click [Run-Demo.cmd](Run-Demo.cmd). It invokes the registered shared controller with `-Workflow regression-tests`. Reuse existing local 27B, local 8B, and OpenAI profiles without changing their identities or qualification claims. The shared shell-action loop, 2048-token action limit, time accounting, and 600-second deadline apply equally to all models. Submission can end early; a timeout preserves partial work for independent evaluation.

In the controller, select the model, start a local server if needed, test the connection, and run an unscored pilot. Enter cloud keys only in the controller's masked prompt, never in a profile, task file, command line, or chat. Cloud runs need explicit billable-run confirmation. Use the controller's latest-attempt and report controls to inspect the saved evidence. GUI runs must not silently build images or replace missing/stale freezes.

CLI equivalents (replace the example profile path with an existing configured profile):

```powershell
& $Runner .\regression-tests\bench.py run --freeze $Freeze --profile .\dependency-migration\profiles\YOUR-LOCAL-PROFILE.private.json
& $Runner .\regression-tests\bench.py run --freeze $Freeze --profile .\dependency-migration\profiles\YOUR-OPENAI-PROFILE.private.json --allow-cloud
& $Runner .\regression-tests\bench.py report --directory .\regression-tests\artifacts
& $Runner .\dependency-migration\comparison_report.py --directory .\regression-tests\artifacts --freeze $Freeze --output .\regression-tests\artifacts\comparison-report-requests-v1.md --title 'Requests Regression Tests Comparison'
```

The shared controller also provides **Generate comparison report**; the CLI `report` summarizes this task's attempt categories, checks, named test results, timing, and usage. The comparison command selects task artifacts with `--directory` and binds them to `--freeze`. Do not mix different freezes or call unqualified pilots scored runs. Scored runs require a separately qualified model/profile and the engine's `--scored` gates.

## Engine Contract

[workflow.json](workflow.json) uses `fault_variants`, a list of exactly eight objects with keys `{name, path, before, after}`. Each `path` is `requests/utils.py`; `before` must occur exactly once in clean starter source, and `after` is its single replacement. Names are `overwrite_existing_scheme`, `lose_query`, `drop_port`, `lose_credentials_adding_scheme`, `fail_percent_decode_credentials`, `wrong_missing_credential_value`, `retain_fragment`, and `retain_auth_cleanup`.

For each fault, the engine reconstructs clean `starter/`, overlays only the submitted allowed generated file, injects exactly one replacement, and runs pytest only on that generated file. Submitted production, visible tests, grader, and reference files are never overlaid into fault runs. Results include boolean `checks["fault_<name>"]` and named `test_results["fault_<name>"]` alongside clean `generated` and protected `contract` phases. A fault counts only with pytest exit 1, ordinary assertion failures, no errors/skips/xfail/pytest.fail, and unchanged clean test IDs. Clean generated and protected phases must pass. `package_hashes()` binds `workflow.json` into the freeze. Baseline files are preserved on collection; smoke seeds only allowed files.

The source guard rejects explicit raises, assignments/deletions targeting production function attributes, and calls named `setattr`, `delattr`, `patch`, or `reload`. Generated and fault phases cannot access `/grader`; only the protected contract phase mounts it. Trusted independent witness runs intentionally mount it as well.

The protected grader is independent of the generated suite and uses different concrete examples to witness every fault. It is mounted only for protected evaluation, not visible to the agent. The complete reference, fault definitions, qualification artifacts, and source manifest remain outside the task mount. Provenance and licensing are in [SOURCE_NOTICES.md](SOURCE_NOTICES.md).