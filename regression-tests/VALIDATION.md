# Validation Evidence

The task package, shared isolated verifier, Windows controller registration, comparison reporting, and cross-laptop setup documentation are integrated. Historical stage evidence below is retained separately from the final Docker qualification.

## Executed

- Acquired Requests via the public GitHub `v2.31.0` tag and verified HEAD equals `147c8511ddbfa5e8f71bbf5c18ede0c4ceb3bba4`.
- Compared all 18 copied production files and LICENSE with the pinned checkout; recorded their SHA-256 hashes in `source-manifest.json`.
- Immediately after the initial manifest edit, checked each of the eight replacement targets occurs exactly once in pinned `requests/utils.py` and changes its text.
- Ran the clean visible/reference/protected suite: **39 passed** (5 visible, 25 reference, 9 protected including import provenance). The first run identified ambiguous bare-credential inputs; tests and documentation were corrected to use scheme-less `//user:password@host`, without production changes.
- Generated the universal Python 3.11 dependency lock using `uv pip compile --generate-hashes --universal`; primary and transitive dependencies are pinned.
- Compiled the qualification and wrapper modules successfully.
- Previously ran `qualify.py local`: reference passed clean and detected **8/8** faults through assertions; independent protected witnesses detected **8/8** assigned faults; **8/8** invalid controls were rejected. This predates the stricter fault-credit alignment below and was not rerun for this change. Evidence is stored in ignored `artifacts/qualification-local-*` with per-phase logs, named JUnit cases, and JSON.
- Confirmed the starter generated file is zero bytes and the reference tree contains tests only.

Local runs used the existing Python 3.11.15 host runner with the task dependency set supplied by `uv`. They are diagnostic trusted-code checks, not the Python 3.11.14 isolated acceptance gate. The earlier eight-control run executed 90 pytest subprocesses; the current eleven-control local matrix would execute 117.

## Docker Witness Isolation Update

`qualify.py check` now runs the protected witness suite on clean starter source and eight separately mutated starter copies in Docker, independently of the reference tests. Each copy retains the empty starter generated suite. All nine runs execute the same full protected suite; a mutant must fail its assigned witness and satisfy the shared engine's `fault_detected` rule against the clean witness test IDs.

Witness containers use the same resolved image ID as subsequent `engine.verify` calls, network disabled, a read-only root filesystem, read-only `/task` and `/grader` mounts, dropped capabilities, no new privileges, 128-process limit, policy CPU/memory limits, and a 128 MiB `/tmp` tmpfs. Each run has a unique container name. Container startup, pytest, and report retrieval have policy timeouts; cleanup is attempted in `finally`. Timeouts, missing or malformed reports, Docker errors, and cleanup failures block qualification. Per-run logs, JUnit, summaries, and any cleanup error are retained in the unique qualification artifact directory.

After independent witness checks, `engine.verify` evaluates the reference and all invalid submissions, each created by copying the starter baseline and writing only the generated test file. Reference acceptance requires every named engine check; any phase or cleanup error blocks qualification. Fault credit uses the shared engine rule: pytest exit 1, at least one failure, no errors or skips, only ordinary assertion failure messages, and test IDs identical to clean. The local diagnostic evaluator uses that same rule but remains explicitly labeled non-isolated.

Focused checks executed for this update:

- Python syntax check and in-memory compilation of `qualify.py` passed; editor diagnostics reported no errors.
- Six focused tests passed on the explicit Python 3.11.15 runner. Mocked Docker checks covered isolation flags, resource limits, unique names, image-ID reuse, timeout cleanup at startup/pytest/report retrieval, missing/malformed reports, and cleanup-error rejection. No Docker containers were launched by these tests.
- Witness orchestration checks confirmed nine independent starter snapshots, an empty generated suite, the full witness suite on each mutation, and failure of each assigned witness.
- Mocked isolated routing checked reference plus all eight controls through `engine.verify`, generated-suite copying, unchanged baseline production source, and no host pytest path.
- Synthetic JUnit checks rejected wrong exit codes, changed test IDs, errors, skips, `pytest.fail` messages, and mixed ordinary/non-ordinary failures. A real host pytest clean/fault pair confirmed `pytest.fail('not an assertion')` exits 1 but receives no fault credit. The actual `pytest-fail` control was also checked to differ from the reference and contain the intended replacement.

## Adversarial Controls Update

The previous ten-control set contains empty, trivial, wrong, import-error, skip, xfail, stub, pytest-fail, protected-witness-reuse, and artificial_raise. Success output derives both counts from the fault list and `len(controls(reference))`.

- `protected-witness-reuse` imports `/grader/test_witnesses.py` and calls every protected witness, including import provenance. It includes a nonconstant assertion so missing assertions cannot mask grader exposure. With grader access it passes clean and detects all eight mutants without authoring independent regression tests. The parent now mounts `/grader` only for its contract phase; generated and fault phases must reject this control without protected-file access. The independent trusted witness containers above intentionally retain their grader mount.
- `artificial_raise` replaces all three reference comparison assertions with explicit `raise AssertionError` on value mismatch, retaining harmless nonconstant assertions. It passes clean and detects all eight mutants, so JUnit failure-message checks alone are insufficient. The parent rejects any `ast.Raise` in fault workflows. Local source eligibility now mirrors that restriction and accepts nonconstant assertions anywhere in the module, including module helpers, matching the parent's helper handling. Local results record `source_eligible` separately from phase outcomes.

Focused checks executed immediately after the code edit on Python 3.11.15:

- In-memory compilation of the qualifier and all ten generated controls passed; the artificial-raise control contains three raises and three nonconstant assertions.
- Eighteen real host pytest phases confirmed clean acceptance and 8/8 fault detections for each new control. For witness reuse only, the protected path was explicitly redirected to the host witness file to simulate the former exposure. This is exploit evidence, not evidence of Docker isolation.
- A mocked local evaluation confirmed the reference remains accepted and artificial raises are source-ineligible even when every fault is reported detected. All ten invalid controls were rejected in that mocked evaluation; this is not a full local qualification rerun.

## Completed Docker Qualification

Existing `artifacts/qualification-check-814f016c411a/qualification.json` records successful isolated qualification on image `sha256:2297cd12645d7a77fad76bfc45fdcadf67a3fab99bfd4c098c56ce68acba6842`: reference accepted with **8/8** faults detected, **10/10** invalid controls rejected, and independent Docker witnesses passing clean and detecting all eight assigned mutations. This is real Docker evidence for the previous ten-control package, not qualification of the newly added eleventh control or a later freeze.

## Eleven-Control Update

The parent engine now provides `regression_source_issue(tree)`, rejecting explicit raises, assignments/deletions targeting the three production function attributes, and calls named `setattr`, `delattr`, `patch`, or `reload`. The source manifest and pinned production record are unchanged.

`alias-preserving-stub` appends `import requests.utils as utils` and a lambda assignment to `utils.prepend_scheme_if_needed` after the unchanged reference suite. Its original direct imports and assertions remain intact, so clean success and eight-fault detection alone would not expose the production replacement. Isolated qualification now requires this control's rejection reason to be `production_function_replacement`.

Local eligibility requires a nonconstant assertion anywhere in the module and `engine.regression_source_issue(tree) is None`, matching engine helper-assertion support and the production-replacement guard.

Focused checks on Python 3.11.15 passed immediately after the qualifier edit:

- In-memory compilation of `qualify.py` and all eleven generated controls; unchanged reference prefix and assertion count in the alias-preserving control.
- Actual shared guard returns no issue for the reference or module-helper assertions, `artificial_test_exception` for artificial raises, and `production_function_replacement` for the alias-preserving stub.
- Mocked local routing accepts the reference and helper assertions, rejects all eleven invalid controls, and records artificial raises and alias-preserving replacement as source-ineligible even when their simulated fault outcomes detect every fault.
- Mocked isolated routing covers the reference and eleven controls; the alias-preserving control must report the exact replacement reason, and a missing reason blocks qualification.

These are focused compile/control checks, not a full local or Docker requalification. No Docker containers were launched for this update.

## Final Integrated Qualification

On 20 October 2026, `qualify.py check --image requests-regression:0.1` passed in Docker. Evidence: `artifacts/qualification-check-f21daa4a67f2/qualification.json`. The reference passed 25 clean generated cases and nine protected cases, detected **8/8** faults, and all **11/11** invalid submissions were rejected. Independent protected witnesses also ran clean and against each of the eight mutations in network-disabled Docker containers. No phase or cleanup errors were recorded. The earlier ten-control Docker qualification was independently reconciled against all 119 saved XML reports by a separate review agent.

The shared runner suite passes **84 tests**, including fault-copy reconstruction, contract-only grader mounts, helper assertions, partial fault-credit reporting, invalid submissions, verifier timeouts, malformed reports, and missing private profiles. PowerShell controller syntax parsing passes. The controller registers `regression-tests`, uses the workflow manifest's default freeze, and retains explicit cloud confirmation. No cloud calls were made during implementation.

The first freeze is named `freeze-600s-requests-v1.json`. Offline attempt results and their sibling saved freezes under `artifacts/attempt-*` record smoke acceptance, the real 600-second deadline stop, partial verification, stop overhead, zero mock model usage, and cleanup. These generated records are the authority for runtime outcomes; updating this document after freezing would itself change the package hash. Inspect `bench.py report` rather than treating successful fixture qualification as model completion.

The `PLT-32gb` branch was fetched locally without switching away from `main`. Its missing-profile report handling, partial-repair mock deadline probe, and clean subprocess-error handling were adopted. Hardware-specific freezes and historical result rewrites were not imported. The user's pre-existing dependency-migration validation edits were preserved. Because the shared engine changed, both older workflows need new coordinator-owned freezes and matching smokes before further comparisons; their old evidence remains historical.

Remaining qualification is model- and host-specific: actual 8B/27B memory fit, device execution, cold startup, model-loop pilots, repeated attempts, cross-laptop matching fingerprints, and any scored results. No such performance, hardware, reliability, or scored-run claims are made. Follow the setup and gated execution order in [README.md](README.md).