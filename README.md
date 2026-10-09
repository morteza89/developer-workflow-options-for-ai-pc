# AI PC Developer Workflows

**To reproduce the working local model on another laptop:** follow [the Windows 27B replication guide](dependency-migration/MODELS.md#replicate-on-another-windows-laptop), then the [benchmark setup guide](dependency-migration/README.md). All current instructions use the same 240-second work budget and `freeze-240s-v3.json` package.

Start with [Dependency Migration](dependency-migration/README.md). It is the only implemented workflow. The agent gets **four minutes (240 seconds)** to edit and test, then the saved files are independently evaluated, including partial progress. Compare named test results, acceptance, time, usage and cost for two local models and one pinned cloud model under the same frozen policy. No accepted real-model result under this package is claimed yet.

| Folder | Scope | State |
|---|---|---|
| [dependency-migration](dependency-migration/README.md) | Migrate a small expense service from Pydantic v1 to native v2 | Implemented; Docker cutoff and partial evaluation verified, real-model runs pending |
| [security-repair](security-repair/README.md) | PyJWT security backport | Reserved; await dependency-migration acceptance |
| [regression-tests](regression-tests/README.md) | Requests URL regression tests | Reserved; await security-repair acceptance |

The [Word proposal](Developer_Workflow_Options_for_AI_PC.docx) and [handoff](AI_PC_WORKFLOW_HANDOFF.md) have also been revised to one 240-second work budget, with no shorter success target. Evaluation/setup/cleanup are outside that budget. Historical attempt records and freezes retain their original values. Infrastructure/API/context errors and manual cancellation remain possible. The workflow order is unchanged.

## VS Code Agent

Select **Workflow Author** in the agent picker to continue authoring or reviewing this benchmark. Its definition is [.github/agents/workflow-author.agent.md](.github/agents/workflow-author.agent.md); it is workspace-scoped and does not select or fall back to a particular model.

Example prompts:

- "Review the latest dependency-migration qualification evidence and investigate inconsistencies."
- "Help me qualify the PTL Qwen3-8B INT8 profile without changing the frozen task."
- "Compare these pilot attempts by verified completion, duration, repair rounds, usage and cost."

This customization is not the measured agent. Scored runs use the pinned Mini-SWE-Agent loop in the isolated runner, not a VS Code chat session that can read the answers. A useful later customization would be a read-only result-review agent; it is deliberately not another workflow implementation.