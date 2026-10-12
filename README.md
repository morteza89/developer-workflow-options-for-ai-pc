# AI PC Developer Workflows

**To reproduce the working local model on another laptop:** follow [the Windows 27B replication guide](dependency-migration/MODELS.md#replicate-on-another-windows-laptop), then the [benchmark setup guide](dependency-migration/README.md). The current comparison policy uses a 600-second (10-minute) work budget and a new `freeze-600s-v8.json` package; older four-minute results remain historical.

Start with [Dependency Migration](dependency-migration/README.md) for the current local-model pilot and its 600-second policy. Option 3, [Security Repair](security-repair/README.md), is now implemented as a separate 240-second PyJWT backport task and has passed offline verifier qualification. No model comparison or scored run has been performed for Security Repair; this work does not imply acceptance of the Dependency Migration workflow.

| Folder | Scope | State |
|---|---|---|
| [dependency-migration](dependency-migration/README.md) | Migrate a small expense service from Pydantic v1 to native v2 | Implemented; 600-second PTL pilots: 27B and OpenAI accepted, 8B rejected; repeated qualification runs pending |
| [security-repair](security-repair/README.md) | PyJWT security backport | Implemented; vulnerable/reference/negative controls qualified offline; model runs pending |
| [regression-tests](regression-tests/README.md) | Requests URL regression tests | Reserved; await security-repair acceptance |

The [handoff](AI_PC_WORKFLOW_HANDOFF.md) documents the proposal and earlier 600-second work budget. Security Repair follows its task-specific 240-second policy. Evaluation/setup/cleanup are outside each work budget, and historical attempt records and freezes retain their original values. Infrastructure/API/context errors and manual cancellation remain possible.

## VS Code Agent

Select **Workflow Author** in the agent picker to continue authoring or reviewing this benchmark. Its definition is [.github/agents/workflow-author.agent.md](.github/agents/workflow-author.agent.md); it is workspace-scoped and does not select or fall back to a particular model.

Example prompts:

- "Review the latest dependency-migration qualification evidence and investigate inconsistencies."
- "Help me qualify the PTL Qwen3-8B INT8 profile without changing the frozen task."
- "Compare these pilot attempts by verified completion, duration, repair rounds, usage and cost."

This customization is not the measured agent. Scored runs use the pinned Mini-SWE-Agent loop in the isolated runner, not a VS Code chat session that can read the answers. A useful later customization would be a read-only result-review agent; it is deliberately not another workflow implementation.