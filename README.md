# AI PC Developer Workflows

**To reproduce the working local model on another laptop:** follow [the Windows 27B replication guide](dependency-migration/MODELS.md#replicate-on-another-windows-laptop), then the [benchmark setup guide](dependency-migration/README.md). The current comparison policy uses a 600-second (10-minute) work budget and a new `freeze-600s-v8.json` package; older four-minute results remain historical.

Start with [Dependency Migration](dependency-migration/README.md). It is the only implemented workflow. The agent gets **10 minutes (600 seconds)** to edit and test, then the saved files are independently evaluated, including partial progress. Current PTL pilots accepted the 27B local and OpenAI API runs; the 8B run was rejected. These are initial pilots, not a qualified or statistical comparison. See [the run matrix](dependency-migration/README.md) for details.

| Folder | Scope | State |
|---|---|---|
| [dependency-migration](dependency-migration/README.md) | Migrate a small expense service from Pydantic v1 to native v2 | Implemented; 600-second PTL pilots: 27B and OpenAI accepted, 8B rejected; repeated qualification runs pending |
| [security-repair](security-repair/README.md) | PyJWT security backport | Reserved; await dependency-migration acceptance |
| [regression-tests](regression-tests/README.md) | Requests URL regression tests | Reserved; await security-repair acceptance |

The [handoff](AI_PC_WORKFLOW_HANDOFF.md) documents the current 600-second work budget, with no shorter success target. Evaluation/setup/cleanup are outside that budget. Historical attempt records and freezes retain their original values. Infrastructure/API/context errors and manual cancellation remain possible. The workflow order is unchanged.

## VS Code Agent

Select **Workflow Author** in the agent picker to continue authoring or reviewing this benchmark. Its definition is [.github/agents/workflow-author.agent.md](.github/agents/workflow-author.agent.md); it is workspace-scoped and does not select or fall back to a particular model.

Example prompts:

- "Review the latest dependency-migration qualification evidence and investigate inconsistencies."
- "Help me qualify the PTL Qwen3-8B INT8 profile without changing the frozen task."
- "Compare these pilot attempts by verified completion, duration, repair rounds, usage and cost."

This customization is not the measured agent. Scored runs use the pinned Mini-SWE-Agent loop in the isolated runner, not a VS Code chat session that can read the answers. A useful later customization would be a read-only result-review agent; it is deliberately not another workflow implementation.