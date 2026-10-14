# AI PC Developer Workflows

**To reproduce the working local model on another laptop:** follow [the Windows 27B replication guide](dependency-migration/MODELS.md#replicate-on-another-windows-laptop), then the [benchmark setup guide](dependency-migration/README.md). The current comparison policy uses a 600-second (10-minute) work budget with `freeze-600s-v9.json` for Option 2 and `freeze-600s-pyjwt-v9.json` for Option 3; older freezes and results remain historical.

Start with [Dependency Migration](dependency-migration/README.md) for the current local-model pilot and its 600-second policy. Option 3, [Security Repair](security-repair/README.md), is a separate PyJWT backport task, offline-qualified and now using a shared 600-second budget. The only saved model pilots in this repository are Security Repair's 240-second runs on `freeze-240s-pyjwt-v4.json`: OpenAI accepted (8/8 protected, 27/27 generated), the 27B reached the deadline at 6/8, and the 8B submitted incomplete at 4/8. They need same-freeze 600-second reruns and are not scored results.

| Folder | Scope | State |
|---|---|---|
| [dependency-migration](dependency-migration/README.md) | Migrate a small expense service from Pydantic v1 to native v2 | Implemented and offline-qualified; 600-second freeze `freeze-600s-v9.json` created and smoke-tested; no model pilot run under this policy yet |
| [security-repair](security-repair/README.md) | PyJWT security backport | Offline-qualified; 600-second freeze `freeze-600s-pyjwt-v9.json`; comparable local-model reruns pending |
| [regression-tests](regression-tests/README.md) | Requests URL regression tests | Reserved; await security-repair acceptance |

The [handoff](AI_PC_WORKFLOW_HANDOFF.md) documents the proposal and earlier 600-second work budget. Both current workflows use 600 seconds; evaluation/setup/cleanup are outside each work budget, and historical attempt records and freezes retain their original values. Infrastructure/API/context errors and manual cancellation remain possible.

## Set Up Another Machine for a Comparable Run

Results from two machines only belong in the same comparison when they share a `task_hash`, which covers the package file hashes, the concrete Docker image ID and the installed runner versions. **Do not `docker build` on a comparison host** — every build produces a different image ID, which silently splits the comparison into two fingerprints. Transfer the images instead.

Prerequisites on the new machine: Windows x64, Python 3.11, `uv`, and Docker Desktop with Linux containers and the **containerd image store** enabled (Settings → General → *Use containerd for pulling and storing images*). On a classic-store daemon, `docker load` derives image IDs from the config blobs instead of the index digest, and the frozen IDs below will not match.

### 1. Take the repository and make the runner match the lock

```powershell
git clone https://github.com/morteza89/developer-workflow-options-for-ai-pc.git
cd developer-workflow-options-for-ai-pc
git checkout PLT-32gb
git status --porcelain
```

`git status` must be clean. In particular `dependency-migration/requirements-runner.lock` must not appear as modified: a locally edited lock is hashed into the freeze and makes every frozen package look changed. Then create and synchronize the runner environment:

```powershell
cd dependency-migration
if (-not (Test-Path .venv-runner)) { uv venv --python 3.11 .venv-runner }
uv pip sync --python .venv-runner\Scripts\python.exe --require-hashes requirements-runner.lock
.\.venv-runner\Scripts\python.exe -m pytest tests -q -o pythonpath=.
cd ..
```

### 2. Load the shared task images

Copy `workflow-images.tar` from the machine that built it (it is deliberately not stored in Git), verify its hash, then load it:

```powershell
(Get-FileHash workflow-images.tar -Algorithm SHA256).Hash.ToLower()
docker load -i workflow-images.tar
docker image inspect --format "{{.Id}}" migration-task:0.1
docker image inspect --format "{{.Id}}" pyjwt-security:0.1
```

The two IDs must equal the `image` field of the freezes in this branch:

| Image | Required ID | Used by |
|---|---|---|
| `migration-task:0.1` | `sha256:183e551061789725ec9bcace0cf1bffcce501f1ea1f7ac0071afb845223947fc` | `dependency-migration/artifacts/freeze-600s-v9.json` |
| `pyjwt-security:0.1` | `sha256:72caa5f6b24729b3c11cff25143a8ebb362e1da14b04cfff00cfe64e73250813` | `security-repair/artifacts/freeze-600s-pyjwt-v9.json` |

If an ID differs, stop. Do not create a new freeze to work around it, or this host's results will not be comparable with the others.

To regenerate the archive on the machine that owns the images:

```powershell
docker save migration-task:0.1 pyjwt-security:0.1 -o workflow-images.tar
```

### 3. Prove the package offline before spending model time

```powershell
cd dependency-migration
.\.venv-runner\Scripts\python.exe bench.py smoke --freeze artifacts\freeze-600s-v9.json
cd ..
.\dependency-migration\.venv-runner\Scripts\python.exe security-repair\bench.py smoke
```

Both must report `"accepted": true` with zero model calls and no cleanup errors. A failure here identifies which input drifted — image identity, package hashes, or runner versions — before any model or API time is spent. Optionally confirm the cutoff itself with `bench.py smoke --freeze artifacts\freeze-600s-v9.json --deadline-probe`; the expected result is 39/39 contract checks, no generated tests, `accepted: false` and exit code 1 after about ten minutes.

Also run the host-side fixture checks once per machine; they need no model and no freeze:

```powershell
cd dependency-migration
python qualify.py prepare
python qualify.py check
cd ..
.\dependency-migration\.venv-runner\Scripts\python.exe security-repair\qualify.py check --image pyjwt-security:0.1
```

### 4. Create this host's own profile, then run pilots

Private profiles are Git-ignored because they record machine identity. Copy the tracked template, fill every `REQUIRED` field with this machine's measured values, and keep `qualified: false` until the profile is reviewed:

```powershell
cd dependency-migration
if (-not (Test-Path profiles\ptl-morteza89-27b.private.json)) { Copy-Item profiles\article-27b.json profiles\ptl-morteza89-27b.private.json }
if (-not (Test-Path profiles\ptl-8b.private.json))            { Copy-Item profiles\local-8b.json    profiles\ptl-8b.private.json }
if (-not (Test-Path profiles\ptl-openai.private.json))        { Copy-Item profiles\openai.json      profiles\ptl-openai.private.json }
```

See [MODELS.md](dependency-migration/MODELS.md#replicate-on-another-windows-laptop) for the exact OVMS runtime, model export and warmup, then run one unscored pilot at a time with the same `--freeze` path. Record server restarts, warm/cold state and run order; the runner cannot observe OVMS request drain or per-attempt prefix-cache reuse.

### What must stay identical across machines, and what may differ

| Must be identical | May differ per host |
|---|---|
| Package files (frozen hashes), Docker image ID, runner package versions, 600-second policy, agent settings | SKU, RAM, GPU/driver/BIOS, power mode, private profile contents, local model cache state |

Attempt directories are Git-ignored, so results stay on the machine that produced them. To compare across hosts, copy each attempt's `result.json` (not the whole directory) to one machine and run `comparison_report.py`; it includes only attempts whose saved freeze matches the selected one and flags the rest as needing a rerun.

## VS Code Agent

Select **Workflow Author** in the agent picker to continue authoring or reviewing this benchmark. Its definition is [.github/agents/workflow-author.agent.md](.github/agents/workflow-author.agent.md); it is workspace-scoped and does not select or fall back to a particular model.

Example prompts:

- "Review the latest dependency-migration qualification evidence and investigate inconsistencies."
- "Help me qualify the PTL Qwen3-8B INT8 profile without changing the frozen task."
- "Compare these pilot attempts by verified completion, duration, repair rounds, usage and cost."

This customization is not the measured agent. Scored runs use the pinned Mini-SWE-Agent loop in the isolated runner, not a VS Code chat session that can read the answers. A useful later customization would be a read-only result-review agent; it is deliberately not another workflow implementation.