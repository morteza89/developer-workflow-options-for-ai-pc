# AI PC Developer Workflows

**To reproduce the working local model on another laptop:** follow [the Windows 27B replication guide](dependency-migration/MODELS.md#replicate-on-another-windows-laptop), then the relevant workflow's setup guide. Dependency Migration and Security Repair use 600 seconds (10 minutes); Regression Tests uses 720 seconds (12 minutes). Keep each workflow's selected freeze and historical results separate.

Start with [Dependency Migration](dependency-migration/README.md) for the current local-model pilot and its 600-second policy. Option 3, [Security Repair](security-repair/README.md), is a separate PyJWT backport task, offline-qualified and now using a shared 600-second budget. Earlier 240-second pilots show OpenAI accepted, 27B timed out near completion, and 8B submitted incomplete; these need same-freeze 600-second reruns and are not scored results.

| Folder | Scope | State |
|---|---|---|
| [dependency-migration](dependency-migration/README.md) | Migrate a small expense service from Pydantic v1 to native v2 | Implemented; 600-second PTL pilots: 27B and OpenAI accepted, 8B rejected; repeated qualification runs pending |
| [security-repair](security-repair/README.md) | PyJWT security backport | Offline-qualified; 600-second policy; comparable local-model reruns pending |
| [regression-tests](regression-tests/README.md) | Requests URL regression tests | Retained 720-second policy; two accepted 27B pilots; 8B pilot rejected; 600-second results historical |

The [handoff](AI_PC_WORKFLOW_HANDOFF.md) documents the proposal. Dependency Migration and Security Repair use 600 seconds. The user retained 720 seconds for Regression Tests on 20 October 2026 after successful 27B pilots. Its original 600-second results remain historical and are not pooled with the longer-budget experiment. Evaluation/setup/cleanup are outside each work budget. Infrastructure/API/context errors and manual cancellation remain possible.

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