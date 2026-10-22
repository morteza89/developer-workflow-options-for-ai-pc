# AI PC Developer Workflows

**Start here on Windows: extract the full repository ZIP (or clone it), then double-click [Install.cmd](Install.cmd) in the repository root.** Git and a preinstalled Python are not required. Setup prepares the prerequisites and three installation-local, unscored workflows, with Desktop shortcuts for Dependency Migration, Security Repair, and Regression Tests. Read the [Windows setup guide](installer/README.md) for requirements, prompts, restart/resume, logs, refresh, and removal.

Use Windows 11 23H2 or newer, x64, with hardware virtualization enabled and permission to install system prerequisites. Missing Docker Desktop, WSL, or Visual C++ runtime components require Windows administrator/UAC approval; installing Docker also requires acceptance of its license, with paid subscriptions required in some cases. Setup cannot bypass organizational restrictions. Local GPU inference needs a supported Intel GPU and driver; the driver is not installed automatically. Cloud workflows do not require an Intel GPU, but need your API key and incur API charges.

Setup downloads no model weights and runs no model pilots. Open an installed workflow shortcut, select a local model, and click **Start selected local model** to download its weights on demand. The shortcuts use an installation-local manifest, not the historical Run-Demo presets. Offline qualification and smoke checks validate the workflow framework, not model performance, GPU compatibility, or cross-laptop comparability. End-to-end provisioning verification is still in progress; clean-VM installation and universal GPU compatibility are not claimed.

**Advanced replication and comparisons:** follow [the Windows 27B replication guide](dependency-migration/MODELS.md#replicate-on-another-windows-laptop), then the relevant workflow's setup guide. Dependency Migration and Security Repair use 600 seconds (10 minutes); Regression Tests uses 720 seconds (12 minutes). Keep each workflow's selected freeze and historical results separate. The historical presets and comparison evidence below are distinct from the installer's newly generated local packages.

## Automatic Local Model Downloads

All three workflow GUIs now prepare missing local model files automatically. Use [one-click Windows setup](installer/README.md) to prepare the locked runner, native Windows OVMS runtime, and other prerequisites, or follow the advanced manual setup guides. Then open an installed workflow shortcut, select a local model, and click **Start selected local model**. There is no need to run a Hugging Face download command yourself. Opening the GUI or choosing a cloud model does not download weights.

The controller checks the selected model in the background. Complete existing assets are reused offline; missing or incomplete assets are downloaded from the pinned public Hugging Face revision. The log shows a wait message, source, destination, file progress, and byte progress during transfer. Downloads can be many GB and take considerable time. A free-space check runs before transfer. Downloading and model startup are outside the benchmark's work budget.

| Local choice | Pinned Hugging Face repository | Revision |
| --- | --- | --- |
| Qwen3.8 27B INT4 | `Morteza89/qwen3.8-27b-int4-ov` | `0b379da0a1b2aa7987693b253724f19ad82928f1` |
| Qwen3 8B INT8 | `OpenVINO/Qwen3-8B-int8-ov` | `f82c978d714abc9c398efa361827a76d3cae5473` |
| Qwen3-Coder 30B-A3B INT4 | `OpenVINO/Qwen3-Coder-30B-A3B-Instruct-int4-ov` | `21140c68a63012da511fe50656319e00be2f6542` |
| Qwen3.8 Fable 5 Coding INT4 | `Morteza89/qwen3.8-27b-fable-5-coding-distilled-int4-ov` | `6a84fb7b49812848f4541b84ae45307ad4c1fb8d` |

During preparation, model selection and pilot controls are disabled. **Cancel download** stops preparation without deleting downloaded data. Clicking Start again retries and resumes Hugging Face transfers where possible. Closing the window during preparation offers cancellation; the downloader is not deliberately left running. Different controllers cannot prepare the same model folder simultaneously.

Only successful preparation starts OVMS. Wait for **AVAILABLE**, then **Test connection** before running a pilot. A failed download leaves the server and pilot stopped; the log gives the failure and retry guidance. The 8B launch now uses the model directory relative to this checkout rather than a configuration file containing another laptop's absolute path.

The shared [model setup helper](dependency-migration/model_setup.py) checks required weight sizes and runtime assets, and records completed download manifests for subsequent offline checks. These are download-completeness checks, not model/host qualification or a substitute for independent artifact hashes. Models and download metadata remain local and ignored by Git. The model downloader itself does not install OVMS, Docker, drivers, or the runner; the separate Windows installer now prepares those prerequisites except the GPU driver. Model downloading does not change task contracts, deadlines, or selected freezes.

Start with [Dependency Migration](dependency-migration/README.md) for the current local-model pilot and its 600-second policy. Option 3, [Security Repair](security-repair/README.md), is a separate PyJWT backport task, offline-qualified and now using a shared 600-second budget. Earlier 240-second pilots show OpenAI accepted, 27B timed out near completion, and 8B submitted incomplete; these need same-freeze 600-second reruns and are not scored results.

| Folder | Scope | State |
|---|---|---|
| [dependency-migration](dependency-migration/README.md) | Migrate a small expense service from Pydantic v1 to native v2 | Implemented; 600-second PTL pilots: 27B and OpenAI accepted, 8B rejected; repeated qualification runs pending |
| [security-repair](security-repair/README.md) | PyJWT security backport | Offline-qualified; 600-second policy; comparable local-model reruns pending |
| [regression-tests](regression-tests/README.md) | Requests URL regression tests | Retained 720-second policy; two accepted 27B pilots; 8B pilot rejected; 600-second results historical |

The [handoff](AI_PC_WORKFLOW_HANDOFF.md) documents the proposal. Dependency Migration and Security Repair use 600 seconds. The user retained 720 seconds for Regression Tests on 20 October 2026 after successful 27B pilots. Its original 600-second results remain historical and are not pooled with the longer-budget experiment. Evaluation/setup/cleanup are outside each work budget. Infrastructure/API/context errors and manual cancellation remain possible.

## Qwen3-Coder Local Model

All three controllers include **Qwen3-Coder 30B-A3B INT4 (local)** as a fifth choice. The source is [OpenVINO/Qwen3-Coder-30B-A3B-Instruct-int4-ov](https://huggingface.co/OpenVINO/Qwen3-Coder-30B-A3B-Instruct-int4-ov), pinned to revision `21140c68a63012da511fe50656319e00be2f6542`. This is a distinct model from the existing 27B and 8B options. Its approximately 16.3 GB main weights file was checked against the pinned repository SHA-256: `03936cfcf2b9edd8d5a492e67eeb90862b7aeaef724b748154ebc2b55fe90d31`. The 3B active-parameter designation does not mean only 3B parameters must fit in memory.

Download assets before timing, from the repository root:

```powershell
.\dependency-migration\.venv-runner\Scripts\hf.exe download OpenVINO/Qwen3-Coder-30B-A3B-Instruct-int4-ov --revision 21140c68a63012da511fe50656319e00be2f6542 --local-dir .\models\qwen3-coder-30b-a3b-int4-ov
```

The [dedicated launcher](models/start-qwen3-coder-30b.cmd) uses the existing OVMS 2026.4 runtime, explicit GPU device, loopback port 8000, `qwen3coder` parser, 2 GB KV cache, prefix caching, and a separate disk compilation cache. It clears inherited `API_KEY` for this local keyless endpoint. Models, caches, and private profiles remain local and are not committed. The [profile template](dependency-migration/profiles/qwen3-coder-30b.json) creates a separate private profile when selected. It remains unqualified: independent device, peak-memory, context, and repeated-run qualification are still required.

Close and reopen an existing controller, select Coder, click **Start selected local model**, wait for **AVAILABLE**, and click **Test connection** before **Run unscored pilot**. Stop the current local server before switching models. The controller prevents a previously started model's readiness from authorizing a different model. Model setup, compilation, and warmup are outside the work budget. All models use the same agent and acceptance contract within each frozen task; the Coder response limit remains 2048 tokens and no cloud fallback is configured.

Current GUI freezes are [Migration v10](dependency-migration/artifacts/freeze-600s-v10.json), [Security v9](security-repair/artifacts/freeze-600s-pyjwt-v9.json), and [Regression v2](regression-tests/artifacts/freeze-720s-requests-v2.json). Migration and Security were requalified and smoke-tested for the existing shared-engine changes; their previous freezes remain historical. For migration CLI runs, explicitly pass `--freeze .\dependency-migration\artifacts\freeze-600s-v10.json` from the repository root, since its older CLI default is retained. Do not compare the refreshed Migration/Security results directly with attempts from older task hashes; rerun other models on these same freezes first.

### Initial Coder Pilots

One unscored attempt per workload on Intel Arc B390 / 63.4 GB RAM, with the pinned GPU launcher and a warm resident model:

| Workload | Submission / budget | Protected checks | Generated tests | Faults detected | Accepted |
| --- | ---: | ---: | ---: | ---: | --- |
| Dependency Migration | 600.00 / 600 s | 25/39 | 8/8 | N/A | No |
| Security Repair | 410.69 / 600 s | 4/8 | 0 collected | N/A | No |
| Regression Tests | 47.51 / 720 s | 9/9 | 3/3 | 8/8 | Yes |

Attempt IDs: Migration `attempt-1cb8f6af894f46cea82c3f100b6a4ed4`; Security `attempt-01ea5864462a4aaea922536721817529`; Regression `attempt-4e269e77ca534578bab2a4ce78fac3c6`. All three recorded $0 cloud API fees and clean cleanup. Completed-request output rates were approximately 26.87, 23.56, and 39.44 tokens/s respectively; these are client-observed rates, not isolated GPU decode measurements.

Migration timed out with incomplete behavior and an unpermitted `=2.12.0` file caused by the model's unquoted `pip install pydantic>=2.12.0` command. Security submitted without the repair or a collected designated suite and wrote unpermitted `test_fix.py`. Those files were not accepted into the verified submission. Regression's three test functions contain real assertions that independently detect all eight faults; test-function count alone is not the quality criterion. A separate reviewer checked the saved evidence. These single pilots do not establish reliability or a hardware ranking.

Attempts were sequential with prefix caching enabled. After Migration's cutoff left an in-flight request, the owned server was restarted and warmed before Security; Regression followed Security without a restart. The test server was stopped after the pilots. Preserve those cache/startup conditions when interpreting results, and keep complete attempt directories for review.

## Qwen3.8 Fable 5 Coding Model

All three controllers include **Qwen3.8 27B Fable 5 Coding INT4 (local)** as a separate sixth model choice. It is an unofficial INT4 OpenVINO conversion of the Fable 5 coding-distilled Qwen3.8 VLM; this is not the existing base Qwen3.8 27B checkpoint. The published OVMS model name is `qwen38-fable5-int4`; repository revision is `6a84fb7b49812848f4541b84ae45307ad4c1fb8d`. The model card reports successful native Windows OVMS 2026.4 use with Arc B390 GPU. It describes the export as VLM and reports unresolved upstream training provenance details; this integration does not independently validate its training data or claims. NPU use is not claimed.

Check disk space before downloading: the language weights are about 13.9 GB, with vision, embeddings, tokenizer, and runtime files adding several more GB. Run from the repository root, outside measured model work:

```powershell
.\dependency-migration\.venv-runner\Scripts\hf.exe download Morteza89/qwen3.8-27b-fable-5-coding-distilled-int4-ov --revision 6a84fb7b49812848f4541b84ae45307ad4c1fb8d --local-dir .\models\qwen3.8-27b-fable-5-coding-distilled-int4-ov
```

The [dedicated launcher](models/start-qwen38-fable5-coding-27b.cmd) serves the OpenVINO folder directly on loopback through OVMS 2026.4, explicitly targets GPU, enables prefix caching, and uses a separate compilation cache. It clears inherited `API_KEY`. No test images or remote image URLs are required for these text-only software tasks. The [profile template](dependency-migration/profiles/qwen38-fable5-coding-27b.json) disables Qwen thinking to match the benchmark text-action protocol. It is unqualified until export/template hashes, context, peak GPU/system memory, actual device execution, and repeatable inference are measured.

Close and reopen each controller to load the sixth option. Start the selected Fable model, wait for **AVAILABLE**, and run **Test connection** before an unscored pilot. Stop the current local model before switching; the GUI blocks a pilot when its owned server model does not match the selected profile. Use the same workflow freezes and deadlines as the other models. Task setup and model compilation stay outside the measured interval. Keep the existing agent loop, prompt, 2048-token response limit, graders, and task acceptance unchanged.

## OpenAI Models in Every GUI

All three workflow controllers offer **GPT-6.1 Sol** (`gpt-6.1-sol`) and **GPT-6 Astra** (`gpt-6-astra`) as separate choices, alongside the local models. Close and reopen an existing controller to load the new option. Select **GPT-6 Astra (OpenAI API)**, use **Set OpenAI API key**, then **Test connection** and **Run unscored pilot**. Warmups and pilots require billable-run confirmation; access depends on your OpenAI API project. No model fallback is used.

Astra uses the same Responses API shell-action loop, medium reasoning effort, and 2048-token response limit as Sol. Both receive the selected workflow's unchanged budget: 600 seconds for Dependency Migration/Security Repair, 720 seconds for Regression Tests. Reports keep their model identities, profile fingerprints, usage, and costs separate.

The [Astra profile template](dependency-migration/profiles/openai-astra.json) is copied to an ignored private profile when first selected; it does not replace or edit the Sol profile. It remains unqualified until host/profile evidence is completed. Standard pricing saved on 20 October 2026 is $10 input, $1 cached input, $12.50 cache write, and $50 output per million tokens for requests up to 272,000 input tokens; above that threshold, the corresponding rates are $20, $2, $25, and $75. These are usage-based estimates, not a spending cap; verify actual billing and any account-specific terms. Sources: [Astra API model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra) and [OpenAI pricing](https://developers.openai.com/api/docs/pricing). No Astra model calls or qualification results are claimed by this integration.

## Regression Tests: Retained Budget

Use **720 seconds for every model** in the current Regression Tests comparison, including local 27B, local 8B, and cloud profiles. The selected package remains [freeze-720s-requests-v2.json](regression-tests/artifacts/freeze-720s-requests-v2.json). The task, eight fault checks, 2048-token response limit, model profiles, and Docker image are unchanged from the duration-only follow-up. Early submission ends work; independent verification follows outside the work budget. The other two workflows remain at 600 seconds.

Verified unscored results for this freeze:

| Configuration | Attempt ID | Agent submission time | Generated tests | Faults detected | Accepted |
| --- | --- | ---: | ---: | ---: | --- |
| Qwen3.8 27B INT4 | `attempt-883ec4aa218c4746843c6b447fb0bb89` | 672.29 s | 27/27 | 8/8 | Yes |
| Qwen3.8 27B INT4 | `attempt-becfea643ea04302a50ce062a7cc93e5` | 640.21 s | 27/27 | 8/8 | Yes |
| Qwen3 8B INT8 | `attempt-8f9f263af5114fb7b2048ddf10159df3` | 54.86 s | 0/3 | 0/8 | No |

These are pilots, not hardware qualification or a statistical reliability claim. Keep failures as well as successes. Attempt logs are machine-local runtime evidence; transfer complete attempt directories for independent review. Reopen the [Regression Tests controller](regression-tests/Run-Demo.cmd) after policy changes and confirm it shows a 12-minute budget.

The package's own README and validation notes are freeze-bound and retain their wording from creation of v2, including its earlier "follow-up" description and historical test counts. This top-level decision record adopts that unchanged 720-second package for continued use; it does not alter or overwrite a freeze or imply that earlier 600-second attempts passed.

## Reproduce Across Laptops

Keep the same task source bytes, runner interpreter build, locked dependencies, model artifact, settings, and Docker image across a comparison. Do not change the task or silently substitute a smaller model on a 32 GB host; record memory fit as a qualification result. Each laptop needs Docker Desktop running Linux containers. Generated model submissions are evaluated only in isolated Docker containers, never on the host.

Separate **authoring a new package** from **joining an existing comparison**. After a shared-engine change, historical freezes for both older workflows become stale: requalify, choose a new freeze filename, and distribute that one coordinator-owned package. Never overwrite or replace historical freezes with host-specific image IDs merely to make a run start.

The tracked attributes preserve the regression package's exact mixed newline bytes and explicitly reconstruct the shared runner's CRLF bytes, independently of laptop `core.autocrlf` settings. For other historical task packages, Git newline conversion may already have changed frozen bytes. Use a checksummed archive of the coordinator's exact frozen source when a checkout cannot reproduce those hashes. Package hash mismatches must stop the run, not be bypassed. The runner fingerprint includes the exact Python build and locked installed versions; a generic Python 3.11 requirement alone does not establish identical comparison fingerprints.

Transfer the coordinator's built image with `docker save --output workflow-images.tar <image-tag>` and `docker load --input workflow-images.tar`, plus the selected freeze and exact source revision. Record `Get-FileHash .\workflow-images.tar -Algorithm SHA256` before transfer and check it against that trusted value after transfer. Verify `docker image inspect <image-tag> --format '{{.Id}}'` equals the selected freeze's `image`. Rebuilding independently is useful for setup, but does not guarantee the same image ID.

Run an accepted offline smoke for the exact freeze on each laptop and compare saved `task_hash` values before model trials. A missing private model profile is reported as `PROFILE MISSING`, not replaced with another model. When collecting results, preserve entire attempt directories, especially both `result.json` and `freeze.json`, along with the original saved profile, trajectory, submitted files, usage, and verifier evidence. The comparison report excludes attempts whose saved freeze differs or is missing.

## VS Code Agent

Select **Workflow Author** in the agent picker to continue authoring or reviewing this benchmark. Its definition is [.github/agents/workflow-author.agent.md](.github/agents/workflow-author.agent.md); it is workspace-scoped and does not select or fall back to a particular model.

Example prompts:

- "Review the latest dependency-migration qualification evidence and investigate inconsistencies."
- "Help me qualify the PTL Qwen3-8B INT8 profile without changing the frozen task."
- "Compare these pilot attempts by verified completion, duration, repair rounds, usage and cost."

This customization is not the measured agent. Scored runs use the pinned Mini-SWE-Agent loop in the isolated runner, not a VS Code chat session that can read the answers. A useful later customization would be a read-only result-review agent; it is deliberately not another workflow implementation.