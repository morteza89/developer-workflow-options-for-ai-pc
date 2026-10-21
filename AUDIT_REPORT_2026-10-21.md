# Developer Workflow Audit

Date: 21 October 2026. Reviewed commit: `be70d8f3f105c723c15e84f34431d3a56cb3c36e`, branch `ptl64-full`.

## Plain-Language Summary

**Dependency Migration:** The design is valid and closely matches the requested workflow: start with a service broken by a dependency upgrade, let the model repair it, then independently check that its behavior is preserved. The weakness is in judging the repair: some incorrect solutions pass, and one valid alternative is rejected. It is useful as a demonstration, but its acceptance checks need correction before model comparisons are dependable.

**Security Repair:** The task and reference repair are valid, but the current grader is not strong enough to certify a secure result. The clearest problem is that a repair disabling signature verification still passed every protected/reference test. Some required key formats are also insufficiently checked. This workflow demonstrates a realistic security-maintenance task, but "accepted" should not yet be interpreted as "secure."

**Regression Tests:** The overall design is sound: keep production code unchanged, generate tests, and check whether they catch deliberately introduced faults. However, one fault can be detected without testing the behavior it is supposed to measure, so an 8/8 score overstates coverage. The test-policy checks also incorrectly accept or reject some suites. It is useful for demonstration, but needs grading refinements before its scores reliably represent test quality.

## Findings First

**Verdict:** All three selected developer activities are implemented, their normal paths work, and their current frozen source/image identities agree. They are useful unscored demonstrations. However, the graders and lifecycle controls are not yet reliable enough for scored comparisons: this audit reproduced false acceptance, false rejection, and evidence-retention failures.

| Priority | Finding | Evidence |
| --- | --- | --- |
| P1 | Security grading accepts disabled signature verification | Wrong-secret token accepted while 8 protected and 2 reference checks passed in the pinned image; S1 |
| P1 | Security coverage permits incomplete key-format repairs | Additional defective variants independently passed all 10 checks; S2 |
| P1 | Native-v2 enforcement misses deprecated APIs | Warning filter ignored in pinned image; chained deprecated serialization passed 41 checks; M1 |
| P1 | All eight regression faults can be detected without decoding tests | Both encoded-credential cases removed; clean success and eight detections retained; R1 |
| P1 | Deadline and interrupted-run paths do not guarantee a faithful snapshot | Late dispatch and missing exports under fault injection; X1-X2 |
| P1 | Isolation is per workflow, not per PC | Separate locks allow overlap; failed cleanup does not block admission; X3 |
| P1 | Cloud destination checks are incomplete | SDK environment override and unchecked warmup destination; X4 |
| P1 | Closing the GUI ignores active work | Confirmed using actual handlers under Windows PowerShell 5.1; G1 |

P1 means fix before relying on scored/unattended comparisons. P2 means a concrete correctness or robustness problem. P3 means lower-impact defensive validation. These are priorities for this experiment, not general vulnerability ratings.

**No existing code, configuration, profiles, freezes, results, model files, or Word document were changed.** This report is the only added deliverable. No commit, push, installation, refreeze, model inference, or paid API call was performed. Trusted counterexamples ran in memory or disposable test environments; model-generated submissions were not executed on the host.

## Scope And Interpretation

Five independent reviewers covered migration, security, regression, shared execution/isolation, and GUI/reporting. A sixth focused review confirmed GUI behavior under the production PowerShell version. The coordinating review independently ran the full runner suite, freeze checks, and selected pinned-container counterexamples.

Requirements came from [the Word proposal](Developer_Workflow_Options_for_AI_PC.docx), [the handoff](AI_PC_WORKFLOW_HANDOFF.md), [the current decision record](README.md), and the frozen task contracts. The complete Word text was recovered in memory after diagnosing malformed XML; see O3.

Intentional differences from the original proposal are not defects:

- The implemented tasks correspond to **Options 2, 3, and 4**. Option 1 is a separate expense-feature task, not a missing piece of these workflows.
- Approved budgets are **600 seconds for migration/security and 720 seconds for regression**, superseding the original 240 seconds. Models within a task receive the same budget.
- OpenAI deliberately replaces the Claude slot, with six selectable model identities kept distinct.
- Historical freezes/results remain separate. Freeze-bound historical documentation is not the current timing authority.
- A custom Docker harness replaces the proposed Harbor runner. Mini-SWE-Agent remains pinned and shared. This is an architectural substitution, not evidence of Harbor-format compatibility.

## Requirement Traceability

| Proposal Requirement | Assessment |
| --- | --- |
| Migration: working v1, unchanged broken v2, native reference, codemod baseline | Implemented and qualified against existing controls; M1-M3 expose missing/overconstrained checks |
| Migration: preserve aliases, validation, notes presence, record loading, JSON types | Substantial coverage, but not complete enforcement |
| Security: exact vulnerable source and source-only upstream repair | Source provenance and reference agree with pins |
| Security: reject key confusion while preserving genuine verification | Reference works; acceptance misses counterexamples S1-S2 |
| Security: generated behavioral regression | Pass/fail baseline gate exists; incidental import failure can earn credit, S3 |
| Regression: fixed Requests source, tests-only edits, clean pass, eight faults | Implemented; decoding specificity and source-rule gaps R1-R3 |
| Clean task and protected independent evaluation | Implemented on normal paths; snapshot/recovery limits X2/X5 |
| Common pinned agent and no fallback | Implemented; destination validation needs X4 |
| Stop at submit/deadline; retain interrupted/partial work | Normal deadline evidence exists; boundary and exceptional paths deficient, X1-X2 |
| One active task per PC; cleanup before next task | Not fully enforced across workflows or cleanup failures, X3 |
| Named outcomes, timings, native usage, fees, configuration | Rich raw evidence exists; reporting/validation defects D1-D4 |
| Five pilots per configuration and interleaved cross-host comparison | Not established by inspected evidence; individual pilots do not complete this protocol |
| Device/memory/context/startup qualification | Appropriately not claimed for unqualified profiles; gate itself weak, X6 |
| AMD/NPU extensions | Deferred qualification, not verified current capabilities |

## Dependency Migration

### M1 - P1: Native-v2 Warning Enforcement Is Ineffective

Locations: [bench.py](dependency-migration/bench.py#L335), [qualify.py](dependency-migration/qualify.py#L54), [test_native.py](dependency-migration/grader/test_native.py#L51).

The interpreter-level `-W error::pydantic.PydanticDeprecatedSince20` filter is ignored: the pinned image prints `Invalid -W option ignored: invalid module name: 'pydantic'`. A valid minimal Pydantic subclass then executes deprecated `.dict()` successfully. The static fallback examines selected simple receivers and misses chained calls.

A trusted in-memory route using `ExpenseRead.model_validate(record).dict(by_alias=True)` passed **39 protected plus 2 generated checks**, violating the explicit native-v2 contract. The coordinating review independently confirmed the warning behavior in the pinned image.

**Recommendation:** configure warnings after import initialization, improve native-API checks without prescribing one coding style, and qualify a chained-deprecated-call negative control.

### M2 - P2: Strict Types And Normalization Have False-Pass Cases

Locations: [invalid inputs](dependency-migration/grader/test_contract.py#L43), [normalization](dependency-migration/grader/test_contract.py#L55), [GET checks](dependency-migration/grader/test_contract.py#L85). Requirement: [task contract](dependency-migration/starter/TASK.md#L10).

Separate trusted in-memory variants passed all **41 checks** despite these violations:

- A partially strict validator accepted `amountCents: 5.0` with HTTP 201. Fractional floats are covered; integral floats are not.
- GET emitted floating-point `expenseId` and `amountCents`. Python dictionary equality does not distinguish `7` from `7.0`.
- Normalization worked only for `work`; `" PERSONAL "` returned 422 instead of 201.

**Recommendation:** add integral-float rejection, explicit GET numeric-type assertions, and normalization cases for both categories, with corresponding negative controls.

### M3 - P2: A Valid Native-v2 Alternative Is Rejected

Location: [runtime-record test](dependency-migration/grader/test_native.py#L38).

The test changes a record through a monkeypatch of `ExpenseRead.model_validate`, then requires that change in the response. A route using `TypeAdapter(ExpenseRead).validate_python(record, from_attributes=True).model_dump(by_alias=True)` preserves native validation and correct output, but fails this implementation-specific check: **40 passed, 1 failed**.

**Recommendation:** vary the supplied record independently of the selected validation method; add compliant alternatives as positive qualification controls.

### Migration Evidence That Holds

The reference passed **41/41** in a fresh offline reviewer run. [Saved qualification](dependency-migration/artifacts/qualification-f790a66efc46/qualification.json) records 35 passing v1 checks, the expected unchanged-v2 failure, successful-but-incomplete codemod execution, reference success, and 14 detected negative controls. All 16 recorded qualification hashes matched; applicable v1/v2 dependency pins agreed with the installed environments.

Aliases, omitted/null notes, receipts, integer merchant coercion, settings reload, unknown fields, and basic attribute loading have meaningful tests. No reference behavior defect was identified. The assertion-screening helper also accepts `assert 1 == 1`, so it does not establish focused generated-test value; no new end-to-end trivial-submission run was performed.

## Security Repair

### S1 - P1: Disabled Signature Verification Passes

Locations: [HMAC compatibility](security-repair/grader/test_security.py#L98), [asymmetric compatibility](security-repair/grader/test_compatibility.py#L29). Explicit prohibition: [task](security-repair/starter/TASK.md#L24).

Tests exercise key rejection and successful sign/decode round trips, but not invalid signatures. In the pinned image with reference source mounted read-only, the audit replaced algorithm `verify()` methods **in memory** with unconditional success. A token signed with one secret decoded using another while **all 8 protected and 2 reference tests passed**. The security reviewer and coordinating review independently reproduced this.

This is a false-pass grader, not a defect in the untouched reference or proof that any saved model patch uses this shortcut. Reference generated tests still fail on the untouched vulnerable baseline, so that separate gate does not fix the omission.

**Recommendation:** independently constructed tokens, wrong HMAC/asymmetric keys, tampered signatures, algorithm restrictions, and a verification-disabled negative control.

### S2 - P1: Key Formats And Compatibility Are Incompletely Covered

Locations: [PEM cases](security-repair/grader/test_security.py#L62), [compatibility](security-repair/grader/test_compatibility.py#L29), [invalid EdDSA keys](security-repair/grader/test_compatibility.py#L48).

Three additional trusted defective variants independently passed **10/10** in container probes:

- A narrowed PEM recognizer accepted a real traditional EC private PEM key as an HMAC secret.
- A compatibility defect broke legitimate ECDSA/OpenSSH handling.
- EdDSA preparation accepted a parsed RSA public key instead of rejecting the wrong key family.

Together with S1, four independent defective controls remain green. The current format matrix and `None`/arbitrary-byte cases do not cover these promised behaviors.

**Recommendation:** cover the published PEM/OpenSSH formats, retain upstream ECDSA/OpenSSH compatibility, and test wrong-family serialized keys and objects. Preserve these as negative controls.

### S3 - P2: An Import Failure Earns Regression Credit

Location: [baseline failure classification](dependency-migration/bench.py#L348).

A test importing the newly added `is_pem_format` inside its body and asserting `callable(...)` passes the repair but fails the baseline with `ImportError`. Pytest classifies that body exception as a failure, satisfying the gate without testing security behavior.

**Recommendation:** distinguish incidental import/runtime failures from behavioral regression evidence. Retain legitimate `pytest.raises` tests; requiring only plain-assert failure text would be too restrictive here.

### Security Evidence That Holds

All ten packaged library files agree with the pinned base after newline normalization; both repaired files agree with the pinned upstream fix. Version/license/source boundaries are preserved. [Saved qualification](security-repair/artifacts/qualification-005e56289276/qualification.json) records baseline rejection, reference acceptance, and four rejected existing controls, but not S1-S2's escapes.

Pinned probes used Python 3.11.14, cryptography 42.0.8, and pytest 8.4.2. Reference tests passed; its two generated tests failed on the vulnerable baseline. The loopback demo showed vulnerable acceptance and reference `InvalidKeyError`. By default, that viewer demonstrates the **human reference**, not automatically the latest model submission.

## Regression Tests

### R1 - P1: The Decoding Fault Also Breaks Missing Credentials

Location: [mutation definition](regression-tests/workflow.json#L40).

Replacing `unquote(parsed.username/password)` with `str(...)` also converts absent credentials into `"None"`, bypassing the original fallback behavior. Missing-credential assertions therefore detect the nominal decoding fault without exercising decoding.

Removing both encoded-credential reference cases left **23 clean tests and all 8 detections** in the reviewer's pytest/JUnit probe. The coordinating review independently called the same reference assertions in the pinned image:

| Source | Assertion Failures |
| --- | ---: |
| Clean source | 0 |
| Overwrite scheme | 4 |
| Lose query | 3 |
| Drop port | 3 |
| Lose credentials adding scheme | 2 |
| Fail percent decoding | 2 |
| Wrong missing credentials | 2 |
| Retain fragment | 4 |
| Retain authentication | 4 |

The mutant is reachable/non-equivalent but insufficiently specific to establish decoding coverage. **Recommendation:** preserve missing-credential behavior in that mutant and qualify a decoding-omission suite. Changing the fault set requires new qualification/freeze; historical 8/8 is not proof of the revised coverage.

### R2 - P2: The Source Guard Rejects Harmless Reads And Misses Stubbing

Locations: [assignment walk](dependency-migration/bench.py#L246), [call inspection](dependency-migration/bench.py#L251).

The harmless assignment `expected[utils.get_auth_from_url] = ("", "")` is treated as production replacement because the guard walks all descendants of the target. A reference extension passed **26 clean cases and 8 detections**, yet failed the guard. Storing the real callable on an unrelated instance similarly triggers it.

Conversely, `patch.object(...)` is missed because the final call name is `object`. Appending a stub test to the otherwise valid reference retained **26 clean passes, 8 detections, and no source issue**. The real reference's direct imports were unaffected: this proves a rule bypass, not that the stub earned all detection credit.

**Recommendation:** identify actual writes/receivers and recognize ordinary mocking APIs. Static checks must not be presented as a proof against arbitrary hostile Python.

### R3 - P2: Non-strict XPASS Evades The No-xfail Rule

Locations: [JUnit pass](dependency-migration/bench.py#L217), [JUnit summary](dependency-migration/bench.py#L223).

Appending an always-passing `@pytest.mark.xfail` test retained **26 clean passes and 8 detections** because the JUnit path loses XPASS identity. Separate probes confirmed real skips, expected failures, fixture errors, and mixed assertion/error outcomes do not earn credit.

**Recommendation:** reject xfail markers at collection or retain structured `wasxfail` evidence. A strict default alone does not cover explicit `strict=False`.

### Regression Evidence That Holds

All 19 production/license hashes match; the starter test file is empty. All eight mutations have unique valid replacement targets and independent witness evidence. The reviewer reconciled **388 saved XML summaries** and **16 reference/witness mutant copies** without inconsistencies; all 11 existing invalid controls are rejected.

Reviewer pytest/JUnit counterexamples used host urllib3 2.8.0, not the image's 2.5.0, and are not new Docker qualification. R1 was independently repeated semantically in the pinned image. Other new guard cases remain runtime/helper evidence. The worker renders the policy duration to 720; the older raw template literal is not an effective 600-second runtime limit.

## Shared Execution And Measurement

### X1 - P1: Deadline Boundary Does Not Gate Dispatch

Locations: [message polling](dependency-migration/bench.py#L496), [pause/termination](dependency-migration/bench.py#L603), [request dispatch](dependency-migration/worker.py#L115), [tool dispatch](dependency-migration/worker.py#L180).

The parent completes Docker pause before terminating the worker, but the worker has no absolute-deadline dispatch check. A synthetic-clock probe of the actual worker/library loop started a tool at **601 seconds under a 600-second policy**. A polling-boundary probe returned `Submitted` timestamped **600.2 seconds**. Submission is reported after the agent returns, not at an independently captured submit-marker instant.

These are reproduced control-flow gaps, not proof that historical pilots include late edits. The saved normal-path 600-second probe records only about **0.08246 seconds** stop overhead; this does not qualify delayed/failed pause or HTTP cancellation. `accepted_within_budget` is distinct from `accepted`, and summaries must preserve that distinction.

**Recommendation:** share an absolute monotonic deadline, gate tool/request starts, validate completion timestamps, capture submission before trajectory serialization, and classify uncertain snapshots explicitly. Qualify real stop/cancel/drain separately.

### X2 - P1: Exceptional Exits Can Lose Edits And Diagnostics

Locations: [exception path](dependency-migration/bench.py#L640), [cleanup](dependency-migration/bench.py#L651), [verifier exception](dependency-migration/bench.py#L353).

Injected `KeyboardInterrupt`, worker EOF, and pause timeout caused cleanup with **no export or verification** before removal of the task volume. A failure category may survive while the actual partial submission is lost. Injected verifier timeout also discarded available stdout/stderr and did not recover a report.

**Recommendation:** bounded best-effort capture on every exit; retain recoverable volumes if capture fails; distinguish uncertain timing; preserve partial verifier output. Live forced-cancellation recovery remains untested.

### X3 - P1: Admission And Cleanup Are Not Host-wide Or Fail-Closed

Locations: [package lock](dependency-migration/bench.py#L515), [release](dependency-migration/bench.py#L524), [cleanup result](dependency-migration/bench.py#L651), [exit status](dependency-migration/bench.py#L671).

Each package has its own active-run lock. Holding one did not prevent another workflow's admission in the mock probe. Separate GUIs can compete for one endpoint/accelerator despite the one-task-per-PC requirement.

Mocked removal failures retained `accepted=true`, returned **0**, and released the lock. Correctness may legitimately remain true, but operational validity and permission for the next run must not follow from it. Existing tests permit this behavior.

**Recommendation:** host-wide admission; separate correctness, measurement validity, and cleanup status; block new measured work while owned residual resources remain unresolved.

### X4 - P1: Cloud Destination Validation Is Incomplete

Locations: [OpenAI construction](dependency-migration/worker.py#L100), [profile guard](dependency-migration/bench.py#L158), [GUI warmup](dependency-migration/demo-controller.ps1#L491).

The worker omits the validated `base_url` when constructing OpenAI's SDK client. With `OPENAI_BASE_URL` set to synthetic loopback, the client targeted it despite a valid official-endpoint profile. No network request was sent.

GUI warmup sends Authorization to the unchecked profile URL and hardcodes `OPENAI_API_KEY` instead of honoring `api_key_env`. A synthetic invalid profile reached a mocked credential-bearing request. Current public URLs are valid; **no actual credential disclosure occurred**.

**Recommendation:** pass the validated destination explicitly, reject conflicting routing, and share profile/key validation across worker and warmup before sending credentials.

### X5 - P2: Deleted Editable Files Are Restored Silently

Locations: [baseline overlay](dependency-migration/bench.py#L188), [deletion checks](dependency-migration/bench.py#L212).

Security/regression collection copies the entire starter, then overlays exported files. Missing allowed files are exempt from deletion violations. A temporary-tree probe produced the starter version of an absent editable file with no violation.

**Recommendation:** preserve only immutable files or explicitly reject/represent allowed-file deletion. Evaluate the saved submission, not a silently reconstructed alternative.

### X6 - P2: Scored Qualification Gates Are Weakly Bound

Locations: [profile gate](dependency-migration/bench.py#L166), [smoke prerequisite](dependency-migration/bench.py#L536), [security evidence](security-repair/qualify.py#L84).

A synthetic profile with `qualified=true`, context limit 1, and zero memory/startup measurements passed without host/export/offload evidence. Scored admission requires matching smoke success, not matching semantic qualification. Security qualification records commits/image but not source/grader/policy/runner hashes.

Current public profiles correctly remain unqualified and current freeze bytes match. This is inadequate enforcement against incomplete/stale administrative evidence, not fabricated hardware data. **Recommendation:** validate a complete evidence schema and bind semantic qualification and model/host/runtime identity to the exact experiment.

## GUI And Reporting

### G1 - P1: Form Close Ignores Active Pilots

Location: [FormClosing](dependency-migration/demo-controller.ps1#L603).

Actual AST handlers were tested under **Windows PowerShell 5.1.26100.9711** with mocked effects. With an active task and no owned server, closure proceeded without a prompt, stopped the timer, and retained the task. With active task/server, choosing Yes invoked server-tree termination while retaining the task.

Cloud work can continue billing after closure; local work can lose its endpoint. **Recommendation:** explicit active-task wait/cancel/leave-running handling before server shutdown, using X2's evidence-preserving cancellation. No real paid process or server was started.

### G2 - P2: Warmup Readiness Can Belong To Another Selection

Locations: [DoEvents](dependency-migration/demo-controller.ps1#L489), [readiness assignment](dependency-migration/demo-controller.ps1#L505), [external endpoint gate](dependency-migration/demo-controller.ps1#L390), [server exit](dependency-migration/demo-controller.ps1#L577).

Warmup pumps events before blocking HTTP with 90/120-second timeouts. A PowerShell 5.1 probe switched A to B during `DoEvents`: only A was requested, but its completion set readiness and enabled Run for B. The button also became enabled during the operation. Endpoint disappearance/reappearance and owned-server exit can retain warmup readiness.

The worker's returned-model check provides a later safeguard; this is not proof of silently accepted wrong-model output. **Recommendation:** explicit busy state, asynchronous selection-bound completion, lifecycle invalidation, and external identity revalidation. Real WinForms scheduling was not load-tested.

### G3 - P2: Report Process Failure Leaves Stale State

Locations: [launch](dependency-migration/demo-controller.ps1#L561), [completion](dependency-migration/demo-controller.ps1#L592).

Injected spawn failure left the pending report path set; a synthetic exit code 2 still opened an existing report path. **Recommendation:** clear state on start failure and require successful completion plus expected output before opening the report.

### D1 - P2: Configuration Attribution Is Ambiguous

Locations: [coverage](dependency-migration/comparison_report.py#L103), [summary](dependency-migration/comparison_report.py#L140), [throughput selection](dependency-migration/demo-controller.ps1#L279).

Coverage/latest throughput match provider/model, not exact profile fingerprint. A changed-device profile was labeled ready using another configuration's attempts. Summary groups separate hashes internally but omit them from display, allowing indistinguishable rows.

This is attribution failure, **not numerical pooling**. **Recommendation:** display exact configuration fingerprints and distinguish model history from exact-configuration coverage.

### D2 - P2: Usage Display And Validation Confuse Missing With Zero

Locations: [token display](dependency-migration/comparison_report.py#L170), [metrics](dependency-migration/bench.py#L475), [finalization](dependency-migration/bench.py#L655).

The token column supports `input_tokens/output_tokens`, not local `prompt_tokens/completion_tokens`: **19 of 24 inspected current-freeze non-mock attempts** had known native counts hidden as `n/a`. Synthetic empty/input-only usage was marked complete with zero throughput; explicit null output raised `TypeError`.

Aggregation precedes final result saving, so malformed telemetry can also prevent durable evidence. That malformed-provider scenario was injected, not observed in saved records. **Recommendation:** recognize both schemas, validate counters, preserve unavailable versus zero, and make telemetry failure nonfatal to saving the attempt.

### D3 - P2: One Malformed Artifact Aborts Reports

Locations: [comparison loading](dependency-migration/comparison_report.py#L69), [grouped report](dependency-migration/bench.py#L677).

Injected truncated JSON raised in both reports. Comparison parsing occurs before freeze filtering, so an unrelated old damaged attempt blocks a current report. None of the **68 inspected results** was malformed.

**Recommendation:** report unreadable records explicitly while continuing with valid evidence; disclose denominator uncertainty and use atomic writes. Do not silently discard failed records.

### D4 - P3: Billing Counters Need Defensive Validation

Location: [fee calculation](dependency-migration/bench.py#L419).

Synthetic negative output produced a negative fee; nonnumeric cache counters can throw. Missing categories default to zero, defensible only if guaranteed by the provider schema. Valid saved-rate arithmetic, cache categories, context thresholds, failed-attempt inclusion, local zero fees, and incomplete-request unknown fees passed.

**Recommendation:** validate finite nonnegative counters and provider schemas; report unknown on malformed evidence. Live current prices/account terms were not recertified. GUI warmup charges are outside the inspected attempt-fee accounting.

## Operational Issues

### O1 - P2: Migration's CLI Default Is Stale

Locations: [CLI default](dependency-migration/bench.py#L706), [GUI selection](dependency-migration/demo-controller.ps1#L20).

GUI v10 matches; CLI-default v9 has a different runner hash, so default run/smoke is blocked by drift. The README documents an explicit v10 workaround.

**Recommendation:** align defaults in the next authorized revision. The default resides in the **hash-bound shared engine**: editing it invalidates selected package hashes. Coordinate it with new qualification/freezes; do not bypass checks or overwrite historical freezes. An explicit v10 argument is the current no-change workaround.

### O2 - P2: Security Demo Timeout Lacks Container Cleanup

Locations: [container launch](security-repair/demo_server.py#L37), [timeout handling](security-repair/demo_server.py#L51).

The demo launches unnamed containers without CPU/memory/PID bounds. A mocked timeout returned an error without cleanup. `--rm` does not prove that timing out the Docker client terminates a still-running container. Threaded HTTP requests can multiply work.

**Recommendation:** named tracked containers, unconditional bounded cleanup, resource limits, and bounded concurrency. Actual orphan creation and HTTP load behavior were not tested.

### O3 - P2: The Word Proposal Contains Invalid XML

Location: [proposal](Developer_Workflow_Options_for_AI_PC.docx), internal `word/document.xml`.

Strict parsing failed with `prefix must not be bound to one of the reserved namespace names: line 2, column 58599`. Aliases `d5p1` and `d8p1` are bound to the reserved XML namespace instead of using `xml`. Both .NET and ElementTree extraction encountered the defect.

Only the in-memory text was normalized to parse all proposal paragraphs/tables. The archive was not changed. This is a standards/interoperability defect; Word opening/recovery was not tested. **Recommendation:** repair a backed-up copy with conforming OOXML tooling and verify text, links, tables, and layout before replacement.

## Verification Record

| Check | Result | Evidence Level |
| --- | --- | --- |
| Full runner/controller suite | **105 passed in 7.37 s** | Fresh executable check |
| Migration v10 | **21 hashes match; frozen image matches** | Fresh read-only check |
| Security v9 | **45 hashes match; frozen image matches** | Fresh read-only check |
| Regression 720-second v2 | **41 hashes match; frozen image matches** | Fresh read-only check |
| Locked runner | Python **3.11.15**, applicable installed pins validate | Fresh environment check |
| Disabled verification | Wrong secret accepted; 10 tests pass | Independently repeated pinned-container probe |
| Pydantic warning filter | Ignored; deprecated call succeeds | Pinned-container probe |
| Decoding omission | 23 clean assertions pass; all 8 faults fail | Pinned-container semantics plus reviewer pytest/JUnit probe |
| GUI close/warmup | Defects reproduced | Actual AST handlers; mocked effects; PowerShell 5.1 |
| Deadline/cancel/cleanup | Gaps reproduced | Actual logic with synthetic clock/process/Docker effects |
| Selected reviewer runner tests | 33 passed | Subset, not additional unique coverage |

Full-suite command:

```powershell
.\dependency-migration\.venv-runner\Scripts\python.exe -B -m pytest dependency-migration/tests/test_runner.py -o pythonpath=dependency-migration -p no:cacheprovider -q
```

Container probes used existing pinned images, no network, read-only source/root filesystem, non-root image defaults, dropped capabilities, no-new-privileges, PID/CPU/memory bounds, and `--rm`. Mutations were in memory. The coordinating regression probe called reference assertions directly; it was not a fresh complete verifier qualification. No probe container remained running.

An initial Pydantic probe incorrectly instantiated `BaseModel` directly and was discarded; the corrected subclass probe is reported. Interrupted/contaminated exploratory output was not counted as success. All local report links were checked. Existing source files remained unchanged.

## Verified Strengths

- Six selectors/templates align; missing private profiles are handled without model substitution. Unknown local models do not fall back to 8B. Owned-model mismatch checks work.
- Starter-only preparation, fresh no-network verifiers, non-root execution, read-only verification mounts, allowlisted collection, and protected-grader separation are implemented.
- Regression generated/fault phases do not mount the protected grader; each fault gets a clean source copy.
- Normal failure paths retain named outcomes and detailed usage/timing evidence. Matching-freeze reports exclude mocks and keep task/profile groups distinct internally.
- No automatic model/cloud fallback was found. Returned identity is checked. Local zero cloud fees correctly exclude hardware and energy.
- Reference/source provenance and existing negative controls are substantive. New defects concern missing cases and lifecycle paths, not an absence of useful implementation.

## Remaining Risks And Unverified Claims

- No fresh real 720-second cutoff, live HTTP drain, forced process-tree cancellation, or pause-failure recovery was performed. A historical 600-second no-model probe does not establish those properties.
- Hostile pytest hooks/report forgery and sandbox escape were not tested. Submitted code shares the verifier interpreter and writable report area; read-only mounts are not a complete anti-gaming proof.
- Export occurs before allowed-file size filtering; total export and tool-output bounds need review. Input files read after initial hashing can also change mid-run; immutable staging would strengthen reproducibility.
- Prefix caching differs across launchers, and AVAILABLE can enable Run without warmup. Cache/startup conditions need an explicit recorded comparison protocol.
- The 8B wrapper and article-27B launcher do not clear inherited `API_KEY`; Coder/Fable do. Live authentication effects were not retested, so this remains a consistency risk rather than a demonstrated outage.
- Local hash/image agreement and checkout tests do not prove a fresh second-laptop reconstruction. Tagged base images and exact host Python builds constrain reproducibility; transfer the frozen image as documented.
- No new model pilots, weight rehash, hardware/offload/memory measurement, randomized cross-host study, AMD/NPU qualification, or ranking was performed. Prior successful pilots remain pilots.
- Pylance selects a separate Python 3.12 executable and reports unresolved `packaging.requirements`; the explicit locked 3.11 runner imports it and passes dependency validation. This is an editor-environment mismatch, not a proven runtime defect. No editor configuration was changed.
- The previously oversized validation document is already restored; this audit did not identify a renewed corruption or perform another restoration.

## Recommended Adjustment Order

1. Fix acceptance validity: S1-S3, M1-M3, R1-R3. Keep the counterexamples as permanent negative controls and valid alternatives as positive controls.
2. Harden deadline/snapshot retention, host-wide admission, cleanup validity, and faithful collection. Qualify bounded real-container recovery before scored work.
3. Fix explicit endpoint routing and GUI lifecycle/readiness. Complete mocked gates before paid tests.
4. Correct attribution, native usage, malformed evidence, and CLI defaults; bind qualification records to exact inputs.
5. Standardize warmup/cache conditions and address demo/document robustness. Create new coordinator-owned freezes for changed frozen inputs; retain old cohorts intact.
6. Execute the repeated interleaved same-freeze comparison on qualified hosts, retaining failures and reporting uncertainty.

**No remedies were applied.** Historical acceptance means that a submission passed its historical frozen grader. This audit does not retroactively fail those submissions or claim they contain these defects; it establishes why acceptance alone is insufficient proof of every promised property.