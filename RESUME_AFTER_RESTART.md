# Resume After Windows Restart

Historical restart checkpoint only. It records the former 240-second policy and freeze; do not use it to start new attempts. Current setup/run instructions are in [the model guide](dependency-migration/MODELS.md) and [the migration README](dependency-migration/README.md). New attempts use the 600-second policy and a fresh `freeze-600s-v9.json` after its offline smoke passes. Historical status claims below are not current readiness evidence.

Checkpoint: 2026-10-05. Restarting Windows after WSL installation. Installation completion and post-reboot WSL status have not yet been verified.

## Completed

- Dependency-migration fixture preparation and qualification passed.
- Fixed preparation so existing Python environments are reused safely.
- Created dependency-migration/.venv-runner and installed its locked dependencies.
- Runner tests passed: 25 tests.
- Docker command was unavailable; Docker Desktop was not found in standard installation locations.
- Before installation, Windows reported WSL was not installed.

Do not recreate the Python environments or reinstall their packages. Do not proceed to security repair or regression-test generation yet.

## Next Steps

1. After restarting, open PowerShell and check WSL:

```powershell
wsl --status
wsl --version
```

If WSL reports an installation error, resolve it before proceeding. No separate Ubuntu distribution is required for Docker Desktop's own WSL2 backend.

2. Install Docker Desktop for Windows **x86_64**, following the [official instructions](https://docs.docker.com/desktop/setup/install/windows-install/). Use your organization's approved installation and licensing process. Select the **WSL 2 backend** and use **Linux containers**. Launch Docker Desktop and wait until the engine is running. Any administrator prompts must be handled by you or IT.

3. Restart VS Code after Docker installation and open a new PowerShell terminal so PATH is refreshed. Verify:

```powershell
docker version
docker info --format '{{.OSType}}'
```

Expected: both Client and Server details, then `linux`. Stop and investigate if either command fails.

4. Build the prepared task image:

```powershell
Set-Location C:\projects\Developer_Workflow_Options_for_AI_PC\dependency-migration
docker build --tag migration-task:0.1 .
```

5. Only after the build succeeds, freeze the package and run the offline smoke test:

```powershell
.\.venv-runner\Scripts\python.exe bench.py freeze --image migration-task:0.1
.\.venv-runner\Scripts\python.exe bench.py smoke
```

Expected smoke result: `accepted: true`, `mock: true`, `scored: false`. This uses no model endpoint or cloud API. The previous freeze attempt stopped because Docker was missing; no successful freeze or Docker smoke has been recorded. If a freeze file already exists, preserve it and follow the new-freeze instructions in the workflow README rather than deleting it.

6. Share the smoke outcome before proceeding to local-model setup. The subsequent step is one warm Qwen3-8B pilot, following [the model guide](dependency-migration/MODELS.md). The requested Qwen3.8-27B INT4 profile is also prepared, but neither model's memory fit, GPU execution, task acceptance, nor timing has been measured.

## Main Guides

- [Dependency-migration README](dependency-migration/README.md)
- [Local and cloud model setup](dependency-migration/MODELS.md)
- [Validation and outstanding checks](dependency-migration/VALIDATION.md)

## Prompt to Resume This Conversation

> Read RESUME_AFTER_RESTART.md. I have restarted Windows after installing WSL. Help me verify WSL, finish Docker Desktop setup, build the dependency-migration image, and run the offline smoke test. Keep the existing Python environments and do not start the other workflows.