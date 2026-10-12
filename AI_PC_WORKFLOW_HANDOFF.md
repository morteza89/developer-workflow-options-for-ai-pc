# AI PC developer workflow — implementation handoff

Prepared for Morteza Heidari and Ajith, 5 October 2026.

Timing policy revised 12 October 2026: one 600-second (10-minute) agent-work budget for every local/cloud configuration, followed by independent evaluation of saved files, including partial work. No shorter target range or secondary success cutoff applies. Implementation status and run commands are maintained in [dependency-migration/README.md](dependency-migration/README.md); the research/selection discussion below is background, not a current setup guide.

## Read this first

This is a consolidated development handoff from the discussion available in this conversation. The accompanying archive includes the original pasted manager/Claude discussion, the audit, and the later four-option proposal in Word and Markdown. It is not a word-for-word export of every ChatGPT message.

No benchmark implementation or hardware measurements have been completed in this handoff. No workflow selection by Ajith is recorded. The recommendation is Option 1 first, or Options 1 and 2 together; these remain recommendations. Existing reports contain historical source checks and candidate software/model versions, which the implementation agent must verify before use.

Priority when interpreting these files:

1. The user's current instructions and any new choice by Ajith.
2. The clarified manager objective below and the latest four-option proposal.
3. The earlier audit, as supporting technical research.
4. The original Claude suggestions, as historical background subject to the audit.

For the current PTL comparison, the user has selected an OpenAI API model (`gpt-6.1-sol`) for the cloud slot because OpenAI API credit is available. This is a deliberate provider substitution from the original Claude matrix; keep OpenAI and Claude results labeled separately and do not pool them.

The earlier audit's A/B/C/D options are not the same numbering as the latest proposal's Options 1–4. In particular, the latest proposal replaces BaxBench Recipes and the Flask issue with an expense feature and a Pydantic migration as the leading choices.

## Manager objective

Create a useful, everyday developer workflow in which AI performs a substantial coding activity within a common 600-second work budget. Run the same frozen task through local inference on Intel Lunar Lake (LNL), Intel Panther Lake (PTL), and a fixed Claude API model. Evaluate the saved files after early submission or the deadline; compare full acceptance, partial test results, elapsed time and cloud API fees. Extend the unchanged workflow to AMD in a later phase; add NPU configurations only after qualification.

The workflow must be repeatable, reusable, resettable, and shareable. The language and editor are implementation choices; meaningful task completion and the local/cloud comparison are the priorities. The original notes mention NVL as a future platform; the clarified first-phase platforms are LNL and PTL.

Historical motivation, summarized with the current timing policy:

Develop reusable, resettable coding workflows to compare local models on PTL/LNL with cloud inference, then extend to AMD. Give every model 600 seconds for meaningful developer work and evaluate the resulting application/tests afterward. The original request sought four actionable workflow options for selection; dependency migration is now implemented first.

## Requirements to preserve

- Define "same output" as meeting the same functional acceptance contract, not generating identical code or token sequences.
- Calibrate the task once on a named local reference configuration. Freeze the meaningful requirements, fixtures, source, acceptance checks, and agent policy before comparing platforms. Do not resize tasks separately for each model or device.
- Keep all real task time, including model requests, tool use, visible tests, and repairs. Do not create the duration with sleeps, repetitive generation, installation, or artificially expensive tests.
- Prepare models, dependencies, container images, and fixtures before the measured interval. Report cold model startup separately from warm task performance.
- Use the same coding agent, tool permissions, task prompt, acceptance tests, and deadline across the principal local/cloud comparison. Record settings that cannot be made identical across providers.
- Start each attempt from a clean source/data snapshot, empty agent conversation, and documented cache condition. Retain failures and timeouts.
- The benchmarked agent must not receive the reference solution, hidden grader, future Git history, or this research archive. The development agent building the benchmark may use these materials.
- Apply the allowed submission to a clean verifier environment. Do not trust only the tests or reported success inside the editable agent workspace.
- Qualify the grader: unfinished baseline fails; a reference solution passes; deliberately wrong solutions fail.
- Report local execution as "$0 cloud model API fees" when all inference is local. Hardware, electricity, and engineering work are separate costs. Disable and check for cloud fallback.
- Treat runtime support, local-model quality, NPU availability, memory fit and the ability to complete the task within 600 seconds as unverified until measured.

## Four workflow choices

| Option | Developer request | Deliverable | Acceptance |
|---|---|---|---|
| 1. Feature implementation | Add CSV expense import and monthly summaries | Working FastAPI/SQLite application feature and regression tests | Exact values, duplicates, atomic rollback, month boundaries, input validation, existing behavior |
| 2. Dependency migration | Repair a service after upgrading to Pydantic v2 | Native v2 application preserving its API contract | Startup, validation, aliases, omitted/null behavior, serialization, no downgrade or v1 compatibility shortcut |
| 3. Security backport | Repair PyJWT CVE-2022-29217 | Focused library patch and regression tests | Vulnerability blocked and legitimate signing/verification preserved |
| 4. Regression test generation | Protect Requests URL utilities before a refactor | A generated pytest suite | Pass on correct code and detect all selected, independently validated faults |

### Option 1 — expense import feature

Prepare a small existing FastAPI/SQLite expense application with manual-entry behavior already working, database helpers, a sample CSV, installed dependencies, and a fixed viewer. Leave the import and monthly-summary business logic unimplemented. Keep the editable area small.

Implement `POST /expenses/import` and `GET /expenses/summary?month=YYYY-MM`.

The proposed contract includes UTF-8 CSV columns `external_id`, `date`, `category`, and `amount`; ISO dates; nonempty IDs/categories; positive finite USD amounts with at most two decimal places; integer-cent storage; and duplicate external-ID handling. Invalid rows cause HTTP 400 and no new rows inserted. Valid imports return HTTP 200 with inserted and skipped counts. Summaries return the month, integer `total_cents`, and category totals sorted by category. Empty months return zero and an empty list; invalid month syntax returns HTTP 400.

Before coding the task, make the contract fully explicit: request body format and content type, exact response schema, CSV headers and whitespace rules, validation precedence for duplicate rows, and what happens when duplicates contain conflicting data. These details were not all frozen in the discussion. Publish every requirement used by the grader.

The agent reads, implements, adds tests, runs tests, and repairs. Verify exact totals, correct persistence, intra-file and existing duplicates, rollback, boundary dates, and existing manual entry. Reset the source and seeded database for every attempt. Calibrate by supplying the parser for a smaller scope or adding a coherent CSV-export feature for a larger scope, then freeze one version.

### Option 2 — dependency migration

Prepare a separate small service with around three models, settings, routes, and behavior tests. First establish a working Pydantic v1 reference and capture its intended external behavior. Then put the unchanged application source in a preinstalled, locked Pydantic v2 environment and capture reproducible failures.

Migrate settings, validators, configuration, object loading, call sites, aliases, and optional/default handling as needed. Preserve declared API behavior. Use native v2 APIs; do not downgrade dependencies or use `pydantic.v1`. Provide the same local migration notes and permitted utilities to every model.

Run the official migration codemod as a preparation baseline. If it completes the entire task, select a genuine semantic migration case that still needs reasoning. Do not artificially withhold an effective permitted utility.

Verify startup, accepted and rejected inputs, aliases, omitted versus explicit-null fields, object serialization, and semantic response values/types. Reset old source into the same v2 environment without reinstalling during timing. Keep this task independently resettable from Option 1.

### Option 3 — PyJWT security repair

Historical source pins recorded in the earlier research:

- Repository: `jpadilla/pyjwt`.
- Vulnerable start: `24b29adfebcb4f057a3cef5aaf35653bc0c1c8cc`.
- Reference repair: `9c528670c455b8d948aff95ed50e22940d1ad3fc`.
- Focus: `jwt/algorithms.py` and `jwt/utils.py`.
- Issue: CVE-2022-29217 / GHSA-ffqj-6fqr-9h24.

Give the measured agent the sanitized vulnerable snapshot, issue description, local reproducer, and visible checks. Keep future history and the reference patch outside its environment. Qualify compatible Python/cryptography dependencies before measurement.

Verify inappropriate asymmetric key material is rejected as an HMAC secret while legitimate HMAC and asymmetric operations still succeed. Account for the upstream intended exception change in maintainer-controlled tests. Reject solutions that disable verification or reject all tokens.

This is a known security repair/backporting task, not a claim of novel discovery. Historical public patches may have appeared in training. Keep the security acceptance requirements intact during calibration; classify the task as too slow or unsuccessful if a configuration cannot meet them.

### Option 4 — regression tests for URL utilities

Historical source pin: Requests v2.31.0, commit `147c8511ddbfa5e8f71bbf5c18ede0c4ceb3bba4`.

Target `prepend_scheme_if_needed`, `get_auth_from_url`, and `urldefragauth` in `requests/utils.py`. Give the measured agent the correct immutable implementation, a behavior contract, and an empty designated test file. Allow edits only to generated tests.

The suite must pass on correct code and meaningfully fail against a small frozen fault set. Candidate faults include lost queries/ports, overwritten schemes, wrong credential decoding, retained fragments, and retained authentication. Validate each fault as reachable and behavior-changing, and prove a reference suite detects it. Broken imports, collection failures, skipped tests, and unrelated existing tests do not earn detection credit. Coverage is diagnostic, not the success criterion by itself.

Reset generated tests, caches, conversation, and each verifier copy. This is the simplest environment and a later candidate for compact-model/NPU qualification.

## Proposed shared implementation

The following choices were recommended but have not been integrated or tested:

| Layer | Starting proposal | What to verify |
|---|---|---|
| Experiment runner | Harbor, local sequential runs | Current task format, reset/isolation, resource limits, artifact collection |
| Coding agent | A pinned Mini-SWE-Agent configuration | Same read/edit/test loop through local and Claude endpoints |
| Intel local inference | OVMS on the host, GPU first | Exact model/export, runtime, device, chat protocol, context, actual offload |
| Cloud inference | Fixed Claude API model ID | Availability, returned identity, usage fields, rate card, reasoning and cache settings |
| AMD later | Qualified Lemonade backend | Exact hardware/backend, model artifact, actual offload |
| Verification | Separate clean environment | Protected tests, permitted-file submission, reliable failure classification |
| Demonstration | Measured trajectory, diff, test results, fixed viewer | Demo corresponds to the measured configuration |

Start with one qualified 8B-class local GPU model. The proposal mentions Qwen3-8B INT4 and Qwen3.5-9B as candidates; do not treat either as a guaranteed current compatible configuration. Recheck official documentation and pin exact artifacts. Defer larger/Gemma models and NPU variants until the first path works. Avoid hardcoding historical model IDs or prices from the earlier audit.

For Windows, the proposed arrangement is native OVMS with CPU task containers under WSL2/Docker, after validating host/container networking and device/runtime support. The model accelerator stays with the serving process. Match OS, container images, dependency locks, and relevant resource settings across compared hosts.

Keep endpoint routing in configuration. A local model server's OpenAI-compatible interface does not imply that the Claude API uses the same schema; use supported adapters behind a common agent policy. Avoid hidden retries, fallback models, or unreported routing.

The earlier audit rejected several shortcuts: treating an unfinished vulnerable-app reference as an oracle; making Claude Code the universal non-Claude agent; assuming a proxy exposes true cloud prefill timing; giving every model 64K context without need; equating parser support with device readiness; and using coverage alone as proof of test quality.

Harbor and Mini-SWE-Agent are proposed foundations. Confirm their current interfaces and local compatibility before writing wrappers. Keep custom orchestration small. Using Cline or another agent for a separate demo changes the agent and requires separately labeled timing.

## Timing, quality, and cost

Record a monotonic agent interval from task handoff in a ready workspace to final submission or 600 seconds, whichever comes first. It includes model calls, file edits, visible tests and repairs. Pause the task and evaluate its saved files afterward, including incomplete work. Record stop overhead, independent final-verification time and cleanup separately; total command duration can exceed 10 minutes. No further model repairs occur after the cutoff.

Log at least:

- Task/version/hash, attempt ID, seed if supported, and configuration.
- Acceptance, deadline outcome, failure category, and named passed/failed/error/skipped test results for partial work.
- Agent time, verifier time, client-observed model-request spans, tool spans, and calls/turns.
- Native input/output/reasoning/cache usage where provided; retain raw usage records with secrets excluded.
- Actual returned model identity, export/quantization/template hashes, agent and runtime versions.
- Host SKU, RAM, OS, driver, BIOS, power mode, context and cache conditions.
- Actual API fees from the saved provider rate card, including failed attempts and applicable cache categories.

A proxy can collect request spans but cannot expose internal cloud prefill/decode metrics that a provider does not return. Native token counts are not normalized across different tokenizers. Local energy measurements do not establish cloud server energy use.

Cost per accepted task = total API charges for the attempt set / number of accepted attempts. If there are no accepted attempts, report it as undefined rather than zero. Record hardware/electricity separately from API fees.

## Calibration and first experiment

1. Choose a named local reference PC/model. LNL was proposed if both platforms are available; this is an experimental choice, not an observed ranking.
2. Qualify model loading, memory fit, actual device use, and a short read/edit/test loop.
3. Build a reference solution, incomplete starting state, and validated acceptance checks for each selected workflow.
4. Pilot the meaningful scope using a warm resident model and the common 600-second work budget. Do not resize the task for each model or to fill the interval.
5. Freeze task, contract, dependencies, agent policy, context limits, and timeout. Rerun the same package everywhere.
6. Run five pilot attempts per configuration under the same 600-second work budget. Report full acceptance and partial results without a shorter success target; this plan is not a statistical reliability claim.
7. Use 600 seconds as the single scored work deadline. Evaluate the early-submission or deadline snapshot afterward, even without a submit marker. Keep incomplete work, failures and timeouts; do not infer an earlier completion time from later evaluation.
8. Inspect the request/tool breakdown. A proposed selection criterion is at least 60% of agent elapsed time in client-observed model requests; this is not pure accelerator compute.

The latest proposed first matrix is two selected workflows × four configurations × five attempts = 40 measured attempts:

| Host | Inference |
|---|---|
| LNL | Qualified local model through OVMS GPU |
| PTL | Same compatible local artifact and server configuration |
| LNL | Fixed Claude API model, developer tools on LNL |
| PTL | Same Claude API model, developer tools on PTL |

For one workflow, the corresponding matrix has 20 attempts. Randomize or interleave order, run one attempt per PC at a time, and document warmup/cache policy. Preserve all attempts. Add distinct tasks before making broad quality claims.

AMD is a later phase. Identical tasks and acceptance criteria allow a useful complete-platform comparison; different runtimes/quantization formats do not isolate hardware alone. A controlled hardware comparison needs tighter artifact/software/power controls. A fixed model-request replay can be a secondary inference diagnostic, not a replacement for live task acceptance.

## Development sequence for the receiving agent

1. Read this file and the latest Markdown proposal. Inspect the actual repository and any existing instructions before editing.
2. State which requirements are fixed and which choices remain unconfirmed. Do not restart the four-option research or silently select two options as if Ajith approved them.
3. Inspect available OS, Python/runtime, container tooling, and model endpoint information. Record missing access rather than inventing it.
4. Propose a small repository layout. Begin reusable runner/configuration/result-schema/reset scaffolding and an offline mock-endpoint smoke path if a task choice is still pending.
5. Before workflow-specific implementation, obtain the selected option(s), or use an explicit selection supplied in the new prompt.
6. Implement the reference solution and independent verifier first, then derive the unfinished task snapshot. Test useful negative controls.
7. Connect the same agent loop to the local and cloud adapters. Keep credentials out of files and logs. Pin verified versions in dependency locks and configuration.
8. Calibrate, freeze, execute, and report actual results. Document exact setup/run/reset/report commands as they are implemented.

Suggested project components, not claims that these files already exist: `tasks/` for task packages, `profiles/` for endpoint/host configuration, `runner/` for thin orchestration, `tests/` for runner/verifier checks, `results/` for attempt artifacts, and `docs/` for setup and decisions. Follow Harbor's actual task format if adopted.

Each attempted run should preserve its submitted patch/test file, trajectory, test output, verifier result, timing, usage, and configuration. Reset must reconstruct source, databases, generated tests, processes, and conversation state while preserving the saved run record.

Important separation: these handoff materials may include reference repair details. Do not mount the handoff directory or benchmark-authoring repository wholesale into the measured coding agent's environment.

## Open decisions

- Which one or two workflows did Ajith select?
- Exact LNL/PTL SKUs, RAM, OS, power modes, and available serving environments.
- Exact local model/export and fixed Claude model, credentials, and API test budget.
- Whether the proposed Harbor/Mini-SWE-Agent stack works in the actual environment.
- Final endpoint/body/schema details for a selected purpose-built task.
- Final context, sampling/reasoning, cache, timeout, and task scope after calibration.
- Whether the demonstration uses a replay/viewer or a separately measured IDE agent.

## Included background

- `docs/Original_Manager_Notes_and_Claude_Discussion.txt`: original pasted source preserved as bytes.
- `docs/Developer_Workflow_Options_for_AI_PC.md`: text/tables extracted from the complete latest named Word proposal, including link targets.
- `docs/Developer_Workflow_Options_for_AI_PC.docx`: original Word proposal.
- `docs/AI_PC_Developer_Workload_Audit.md`: complete earlier audit, historical source pins, and references.
- `docs/Discussion_Continuity.md`: sequence of requests, revisions, and the current handoff request; a continuity record, not a verbatim transcript.

Read the handoff and latest proposal first. Consult the long original discussion or audit when a source pin, rationale, or rejected suggestion matters. Their inclusion preserves context; it does not make every historical claim current or verified anew.
