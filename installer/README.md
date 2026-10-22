# Windows One-Click Setup

## Start Here

1. Download and fully extract the repository ZIP, or clone the repository. Keep the complete folder in a writable, permanent location. Do not run setup from inside the ZIP or copy only the launcher. Git and a preinstalled Python are not required.
2. Double-click [Install.cmd](../Install.cmd) at the repository root. Internet access is needed for missing runtime downloads, Python packages, and container builds. First setup can take many minutes and requires space for runtimes, images, and later model downloads.
3. Approve Windows UAC requests for missing system prerequisites only if authorized. If Docker Desktop is missing, review and accept its license to install it. Finish any Docker Desktop first-run screens.
4. If setup reports **RESTART REQUIRED**, restart Windows yourself and sign back in as the same user. Setup resumes at sign-in; you can also double-click the launcher again. Setup never forces a restart.
5. Keep the separate workflow-preparation progress window open until its checks finish. Wait for **SETUP COMPLETE** in the setup window, then open one of the three shortcuts: **AI PC - Dependency Migration**, **AI PC - Security Repair**, or **AI PC - Regression Tests**. Copies are on your Desktop and in `.installer/Workflows` inside the repository.

The supported installer target is **Windows 11 23H2 or newer, x64**. ARM64 and Windows Server are not supported. Hardware virtualization must be enabled in BIOS/UEFI, and enterprise policy must permit WSL, virtualization, Docker Desktop, downloads, and the required elevation. Setup cannot enable firmware virtualization or bypass administrator or organizational restrictions.

Local GPU inference requires a supported Intel GPU, a suitable installed Intel graphics driver, and enough available system/GPU memory for the selected model. **The GPU driver is not installed automatically.** Not every Intel GPU or memory configuration is qualified. Cloud workflows can run without an Intel GPU, but still need the Docker task environment, network access, your own API credentials, and paid API usage.

## What Setup Does

The [installer](install.ps1) checks for Docker Desktop, WSL 2.1.5 or newer, and the x64 Visual C++ runtime, installing missing prerequisites through an elevated system stage. It enables required WSL/Virtual Machine Platform Windows features when needed and waits for Docker Desktop's local `desktop-linux` engine. Existing detected components are reused subject to the installer's checks.

It provisions pinned uv, Python 3.11.15, the hash-locked runner environment, and native Windows OVMS 2026.4.0. The runner lives at `dependency-migration/.venv-runner`; setup synchronizes its dependencies to the repository lock file. An existing incompatible or incomplete runner/runtime can block setup rather than being silently deleted.

The [workflow preparation helper](prepare_workflows.py) builds installation-local Docker images for all three workflows, runs offline qualification, creates new local freezes, and runs an accepted mock smoke for each workflow. Migration also prepares separate locked host qualification environments; model-generated submissions execute in Docker, not on the host. The active manifest is `dependency-migration/artifacts/installation-local/workflows.json`. It records the checkout root, runner fingerprint, immutable image IDs, freezes, private profiles, and qualification/smoke evidence.

These are offline workflow-framework checks, not model qualification or a full repository unit-test-suite run. Smoke evidence must be accepted, mock, unscored, and have zero model calls. Profiles remain unqualified and runs remain unscored. Setup does not certify model accuracy, inference speed, memory fit, actual GPU execution, or repeatability. No clean-VM verification or universal GPU compatibility is claimed here.

Historical freezes and results are not overwritten. Locally rebuilt images, local freezes, and a local runner fingerprint do **not** establish comparability with historical attempts or another laptop. For coordinated comparisons, follow [Reproduce Across Laptops](../README.md#reproduce-across-laptops) and preserve the coordinator's exact package and evidence.

## Launch And Models

Installed shortcuts launch the [shared controller](../dependency-migration/demo-controller.ps1) directly with `-Workflow` and `-InstallationManifest`. They do not invoke the historical [Migration launcher](../dependency-migration/Run-Demo.cmd), [Security launcher](../security-repair/Run-Demo.cmd), or [Regression launcher](../regression-tests/Run-Demo.cmd), whose presets remain for advanced/historical use. The installed GUI title includes **INSTALLATION-LOCAL (unscored)** and uses the manifest's freeze and ordered private profiles.

Installed controllers select the local `desktop-linux` Docker context in their own process, without changing your global Docker settings. Before a pilot, they verify the installation manifest and evidence again. After a refresh, close and reopen existing controllers so they use the new generation; stale windows block dispatch rather than mixing packages.

Equivalent manual launch from a PowerShell terminal at the repository root:

```powershell
$root = (Get-Location).Path
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "$root\dependency-migration\demo-controller.ps1" -Workflow dependency-migration -InstallationManifest "$root\dependency-migration\artifacts\installation-local\workflows.json"
```

Use `security-repair` or `regression-tests` for the other workflows. The manifest argument must be an absolute path; do not combine it with `-FreezePath`. Keep Docker Desktop's Linux engine running when using a workflow.

**No model weights are downloaded during installation.** For any local model, select it in the GUI and click **Start selected local model**. Missing assets download on demand from pinned revisions; existing complete assets are reused. Downloads can be many GB. Cancellation retains downloaded data, and retry resumes transfers where possible. Wait for **AVAILABLE**, then **Test connection**, before **Run unscored pilot**. Stop the current local server before switching models. Download, compilation, and startup time are outside the work budget. See [Automatic Local Model Downloads](../README.md#automatic-local-model-downloads) for model revisions and details.

For a cloud model, select it, use **Set OpenAI API key**, and test the connection before a pilot. Cloud warmups and pilots require billable-run confirmation; API access and charges are your responsibility. Selecting a cloud model does not download local weights, and setup makes no cloud model calls.

## Rerun And Refresh

Run these commands from a PowerShell terminal at the repository root:

```powershell
.\Install.cmd
.\Install.cmd -CheckOnly
.\Install.cmd -RefreshWorkflows
.\Install.cmd -NoShortcuts
```

| Option | Behavior |
| --- | --- |
| No options | Retry setup or verify an existing local generation without rebuilding it. Missing prerequisites may still be installed and runner dependencies synchronized. Models, caches, profiles, and historical results are retained. |
| `-CheckOnly` | Report prerequisite readiness and presence of runner, OVMS, and manifest after platform/package checks. Does not install, build, create shortcuts, or prove Docker engine, model, or full manifest readiness. |
| `-RefreshWorkflows` | Build and validate a new retained local generation. Replace only the active manifest after all workflows pass; do not overwrite earlier generations or historical freezes. |
| `-NoShortcuts` | Skip creating Desktop shortcuts; still create `.installer/Workflows` shortcuts. Does not remove existing Desktop shortcuts or disable restart resume. |
| `-AcceptDockerLicense` | Record your acceptance of the Docker agreement instead of showing the installer's consent dialog. This is contractual acceptance, not a license exemption or a bypass of UAC, paid subscription requirements, enterprise policy, or Docker first-run screens. |

Options can be combined, for example `.\Install.cmd -RefreshWorkflows -NoShortcuts`. Only use `-AcceptDockerLicense` when authorized to accept the [Docker Subscription Service Agreement](https://www.docker.com/legal/docker-subscription-service-agreement/); some organizations, including government entities, require paid subscriptions. If Docker is already installed, setup does not display its installation-consent dialog; existing licensing obligations still apply.

Drift in source, runner, images, or evidence blocks reuse. Review the cause, then use `-RefreshWorkflows` to create new local evidence rather than editing hashes or historical freezes. Private installation profiles are created once and retained, including across refresh; invalid or qualified profiles can block validation and are not silently reset. A failed refresh leaves the prior active manifest in place and retains failure logs, but prior evidence may still be stale relative to changed source.

Keep the checkout at the same path. The manifest records its absolute root, shortcuts contain absolute paths, and runner identity is checked. Moving or copying an installed checkout is not a portable installation: rerun setup with `-RefreshWorkflows` at the new location to regenerate local evidence and shortcuts. A moved Python environment may need repair first; follow the reported error and preserve the old environment before recreating it. Do not edit the manifest root/fingerprint to bypass verification. Review preserved private profiles for any host-specific paths and remove obsolete shortcuts manually.

## Restart And Troubleshooting

When prerequisite installation reports a pending restart, setup writes `.installer/resume.pending` and a per-user Startup shortcut named `AI PC Setup Resume-<identity>.lnk`. It preserves applicable license, refresh, and Desktop-shortcut options for resume. Restart manually and sign back in; successful setup removes its pending marker and matching Startup shortcut. A failed or interrupted setup can be retried with the root launcher. Do not start concurrent setup/refresh processes or delete lock files to defeat an active lock.

Check `.installer/setup-*.log` for setup transcripts. Errors before transcript startup appear in the launcher window. Detailed build, preparation, qualification, freeze, and smoke logs are retained under `dependency-migration/artifacts/installation-local/generation-*`. Qualification and smoke receipts also refer to original evidence in each workflow's `artifacts` directory; retain that evidence, not just the active manifest.

If the Docker engine times out, open Docker Desktop and resolve its WSL, virtualization, permissions, or first-run error before rerunning setup. If UAC or license consent is declined, resolve that requirement with your administrator; do not bypass it. If a download fails integrity validation, remove only the identified cached download and retry after checking its source. Setup deliberately stops on incomplete environments or runtime directories; move the identified incomplete directory aside as instructed rather than deleting unrelated data.

## Download Integrity

[downloads.json](downloads.json) is the authoritative catalog of exact HTTPS URLs, filenames, SHA-256 pins, and expected publishers. Current entries are uv 0.12.7 and OVMS 2026.4.0 from their versioned GitHub releases, Docker Desktop 4.96.2 from Docker's build-specific URL, WSL 3.0.3 from Microsoft's versioned release, and Visual C++ runtime 14.51.36247 from Microsoft's fixed download URL. Python is provisioned through pinned uv, and runner packages use a hash-locked requirements file. These catalog hashes should not be mistaken for independent hashes of every model asset.

Before extraction or execution, the installer checks catalog payload SHA-256, including cached downloads. Docker, WSL, and Visual C++ installers additionally require a valid Authenticode signature with the catalog publisher (`Docker Inc` or `Microsoft Corporation`). uv and OVMS ZIPs use catalog hashes, not Authenticode. System-stage downloads use restricted temporary staging and are removed afterward; uv/OVMS archives are cached under `.installer/downloads`.

To independently inspect a downloaded catalog payload without executing it, run from the repository root and replace the example path with the actual downloaded file:

```powershell
$catalog = Get-Content .\installer\downloads.json -Raw | ConvertFrom-Json
$payload = 'C:\Downloads\Docker-Desktop-4.96.2.exe'
$spec = $catalog.Docker
$spec.url
(Get-FileHash -LiteralPath $payload -Algorithm SHA256).Hash -ieq $spec.sha256
Get-AuthenticodeSignature -LiteralPath $payload | Format-List Status, SignerCertificate
$spec.publisher
```

Require a matching hash, `Valid` signature status, and the expected signer organization for signed installers. Review the catalog against trusted upstream release information when updating pins; do not disable checks, substitute an unreviewed URL, or use an external mutable "latest" installation script. A matching repository pin alone does not establish trust in an untrusted repository copy.

## Verification

Verified on the existing Windows 11 x64 development host on 22 October 2026:

- 325 controller, provisioning, and Windows PowerShell 5.1 bootstrap tests passed, including unchanged historical package checks.
- A full installer refresh built the images, qualified all three workflows, recorded three accepted offline smoke results with zero model calls, verified the manifest, and reached **SETUP COMPLETE**. Rerunning setup also reused and verified the installation successfully.
- An isolated fresh runner downloaded managed Python 3.11.15, installed all 87 locked packages, passed dependency checks, and imported the required agent/downloader/test modules without altering the existing runner.
- Three real Desktop shortcuts were created. Independent agents reviewed prerequisite sources, provisioning, GUI integration, and failure handling; the resulting fixes have regression coverage.

Docker, WSL, and Visual C++ were already installed on this host. Their actual first-time installation, standard-user elevation, and reboot/sign-in continuation have **not** been verified end to end on a clean Windows VM. Tests cover those control paths without changing the operating system. GPU driver installation and inference on other hardware remain outside these verification claims.

## Removal

There is no automatic uninstaller. Close workflow controllers and stop their owned local model servers. Remove only this checkout's three Desktop shortcuts if no longer wanted. To cancel pending automatic setup resume, open the current user's Startup folder (`shell:startup`) and remove the matching `AI PC Setup Resume-<identity>.lnk`, then remove this checkout's `.installer/resume.pending`. Do not remove other checkouts' resume entries.

Reruns retain user/private profiles, caches, downloaded models, and results. Before manually removing a checkout, back up anything you want to retain, including its installation-local profiles/evidence and model directories; deleting the whole checkout would delete those local files. Optional removal of setup caches/runtime directories should happen only after abandoning that installation or planning to reprovision it.

Do not automatically delete Docker images, containers, volumes, WSL distributions, or shared runtimes. Review ownership and dependencies before any manual cleanup. Uninstall Docker Desktop, WSL, or Visual C++ through supported Windows/vendor procedures only if no other applications need them; setup does not remove these shared resources for you.