
# Model Setup and Qualification

These instructions are preparation, not timed agent work. Do not download both large models simultaneously or assume both can remain resident on 32 GB RAM.

## Replicate on Another Windows Laptop

**Start here to reproduce the working 27B setup.** The later configure/JSON examples are for the separate 8B setup. Do not combine those recipes. The setup below was demonstrated on the named Intel PTL host, not on every Windows laptop. Another Intel GPU/driver needs its own qualification; an AMD GPU, NPU or CPU backend is a different configuration, not a drop-in replication.

### 1. Prepare the Laptop and Workspace

- Use Windows x64 and an Intel GPU supported by this OVMS/OpenVINO release. Install the appropriate driver through your normal approved process. The reference host had 32 GB RAM; this does not guarantee sufficient GPU memory on another laptop.
- Install Python 3.11 and `uv`. Docker Desktop with WSL2 Linux containers is needed for the migration benchmark, but not for the standalone model warmup. Complete any administrator/reboot steps yourself.
- Copy/clone the project source, including [the launcher](../models/start-27b-article.cmd), workflow files, profiles and dependency locks. Do not copy virtual environments, active-run locks or a live task container. Private profiles, downloaded models, runtime binaries and artifacts may be Git-ignored and therefore absent from a clone.
- Use AC power and record Windows power mode, driver, BIOS, GPU, RAM and OS build. Best performance was selected on the reference host; do not infer another laptop's settings from its profile template.

The examples use this workspace root; substitute your chosen root when needed. The launcher resolves paths relative to itself, so the following internal layout matters:

```text
Developer_Workflow_Options_for_AI_PC/
    models/
        start-27b-article.cmd
        morteza89-qwen3.8-27b-int4-ov/
    ovms_downloaded/
        windows-2026.4.0-python-on/
            ovms/
                ovms.exe
                setupvars.bat
                ...remaining distribution files...
    dependency-migration/
```

### 2. Install the Same OVMS Distribution

Copy the original verified runtime ZIP or obtain the Windows **python_on** ZIP from the [OVMS 2026.4.0 release](https://github.com/openvinotoolkit/model_server/releases/tag/v2026.4.0). Extract the entire distribution into the layout above, not only the executable. Do not use `python_off`, a moving latest build, or an extra nested `ovms/ovms` directory.

Reference archive SHA-256: `5a022e44e794e6a9cb0f1c6c40822167dac53a36daf9af123c9411974cef1914`. Check your ZIP using `Get-FileHash -Algorithm SHA256`. A different archive is not the same pinned runtime; investigate rather than silently treating it as equivalent.

From clean PowerShell at the workspace root, validate initialization without starting a server:

```powershell
Set-Location C:\projects\Developer_Workflow_Options_for_AI_PC
.\models\start-27b-article.cmd --version
```

Expected OVMS: `2026.4.0.869b2186`; OpenVINO `2026.4.0-22959-99c81491cc3-releases/2026/4`; GenAI `2026.4.0.0-3407-7ea2546852a`. A missing DLL or missing runtime folder must be fixed before model serving. The launcher initializes its own CMD child; do not initialize the PowerShell used for Python/uv with `setupvars.bat`.

### 3. Obtain the Exact Working Export

Either transfer the complete existing model directory and compare file hashes, or download this exact revision from clean PowerShell at the workspace root:

```powershell
$Model = 'Morteza89/qwen3.8-27b-int4-ov'
$Revision = '0b379da0a1b2aa7987693b253724f19ad82928f1'
$ModelDir = Join-Path $PWD 'models\morteza89-qwen3.8-27b-int4-ov'
uvx --from huggingface-hub==0.35.3 hf download $Model --revision $Revision --local-dir $ModelDir
```

Wait for successful download completion. This is **not** `OpenVINO/Qwen3.8-27B-int4-ov`; that earlier export/configuration did not load successfully on this host. Do not rerun downloads to fix environment, port or cache errors. Retain a served-file hash manifest as described below. Let the new laptop build its own disk compilation cache; do not treat a transferred cache as evidence of equivalent startup behavior.

### 4. Start Only One Model Server

In the server PowerShell terminal, from the workspace root:

```powershell
.\models\start-27b-article.cmd
```

Leave this terminal open and wait for `AVAILABLE`. The launcher binds `127.0.0.1:8000`, selects `GPU`, uses alias `qwen3.8-27b-ov`, enables prefix caching and uses a separate disk compilation cache. It relies on the observed dynamic KV-cache default (`cache_size=0`) and automatic parser detection. Do not add `--configure`, fixed 1/2 GB KV-cache overrides, `--cache_size 0.5`, draft/MTP options, or the old serving JSON to this recipe. The fractional cache flag was rejected by the installed CLI; fixed-cache attempts did not establish a working 27B setup.

If another server already owns port 8000, identify and stop your previous server before starting this one. Do not launch duplicate OVMS instances or silently switch to CPU/AUTO. A memory-budget assertion is a failed load, not a completed setup; retain its logs and inspect actual memory allocation rather than repeatedly changing cache values.

### 5. Warm Up from a Separate Clean PowerShell

The server terminal stays occupied. In a second, clean PowerShell terminal:

```powershell
$Body = @{
        model = 'qwen3.8-27b-ov'
        messages = @(@{role='user'; content='Return the single word READY.'})
        max_tokens = 32
        temperature = 0
        chat_template_kwargs = @{enable_thinking=$false}
} | ConvertTo-Json -Depth 8
$Response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/v3/chat/completions' -Method Post -ContentType 'application/json' -Body $Body -TimeoutSec 120
$Response | ConvertTo-Json -Depth 12
```

Confirm returned model `qwen3.8-27b-ov`, meaningful content and native usage. Retain server/client output. The 120-second warmup timeout is a diagnostic client timeout, not the benchmark work budget. A chat response establishes basic inference only; independently observe GPU activity and memory under a real task. Native tool parsing succeeded on the reference host, but the benchmark uses text shell actions, not the native tool API.

### 6. Prepare a New Laptop Profile, Then the Benchmark

Do not assume a private profile exists in a clone. For the tested article export, copy [profiles/article-27b.json](profiles/article-27b.json) to `profiles/ptl-morteza89-27b.private.json` without overwriting an existing file. This is the working 27B export; the unsupported OpenVINO 27B candidate profile was removed. Replace every `REQUIRED` host/evidence value with measurements from the current machine and keep `qualified: false` until the qualification gates pass.

| Field                                               | Working article configuration                                                                                                                                                                                                                   |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `label`                                           | A unique label for the new laptop and export                                                                                                                                                                                                    |
| `base_url`                                        | `http://127.0.0.1:8000/v3`                                                                                                                                                                                                                    |
| `model`, `expected_returned_model`              | `qwen3.8-27b-ov`                                                                                                                                                                                                                              |
| `extra_body.chat_template_kwargs.enable_thinking` | `false`                                                                                                                                                                                                                                       |
| `qualified`                                       | `false` until independently qualified                                                                                                                                                                                                         |
| `host`                                            | Fill all `REQUIRED` values with this laptop's measured identity/settings                                                                                                                                                                        |
| `inference.model_revision`                        | `0b379da0a1b2aa7987693b253724f19ad82928f1`                                                                                                                                                                                                    |
| `inference.runtime`                               | Exact observed versions from step 2                                                                                                                                                                                                             |
| `inference.context_limit`                         | `null` until actual capacity is established, not the template's assumed 8192                                                                                                                                                                  |
| `inference.cache_policy`                          | Record dynamic KV default, prefix caching on, max sequences default 256, disk compilation cache and warm/cold condition. This profile captures configuration, not per-attempt prefix-cache hits; repeated prompts may benefit from cache reuse. |

Fill artifact/template/runtime hashes, startup time, memory and GPU/offline evidence using this laptop's measurements. Use [Complete a Local Profile](#complete-a-local-profile) for the remaining fields. Do not copy the original host's qualification claims.

Then follow [README.md](README.md) for locked environments, fixture checks, Linux task image, freeze, offline smoke and a local pilot. For a same-task cross-laptop comparison, transfer the exact matching source/freeze and Docker image via `docker save`/`docker load`; record each host separately and run its own smoke. A rebuild may have a different image ID. Do not copy Windows virtual environments.

**Current benchmark policy (October 12):** every local and cloud attempt receives 600 seconds (10 minutes) of agent work, followed by separate evaluation of saved files. Policy, task instructions and tests use this limit. Create `artifacts/freeze-600s-v8.json` for the revised source and image, then run its smoke on each laptop. Earlier 240-second freezes and attempts are historical; do not reuse them with this policy or overwrite them.

## Current Host: Working Article 27B

The user's [tested notebook](https://github.com/morteza89/vscode-copilot-local-model-ovms) uses **Morteza89/qwen3.8-27b-int4-ov**, revision `0b379da0a1b2aa7987693b253724f19ad82928f1`. This is the tested article export. It exists in this workspace, but `models/` is Git-ignored; on a fresh clone, follow step 3 to download the exact revision. Do not substitute another export.

If its server is already running, leave it running. Otherwise, with no other OVMS server using port 8000, start the saved launcher from a clean PowerShell terminal:

```powershell
Set-Location C:\projects\Developer_Workflow_Options_for_AI_PC
.\models\start-27b-article.cmd
```

[The launcher](../models/start-27b-article.cmd) initializes OVMS only in its child CMD process and serves directly with `--target_device GPU`, prefix caching enabled and a separate disk compilation cache. It does not use `--configure`, a serving JSON, fixed KV-cache overrides, or parser overrides. The observed runtime defaults are dynamic KV cache (`cache_size=0`) and `max_num_seqs=256`; disk compilation cache is not KV cache. Do not apply the 8B fixed-cache recipe below to this working setup.

OVMS `2026.4.0.869b2186` with OpenVINO/GenAI 2026.4 loaded this export and reached `AVAILABLE` in about 38 seconds. `/v3/chat/completions` returned chat content and a valid native tool call under model ID `qwen3.8-27b-ov`. The benchmark uses the same text-action agent loop as the other models, not that native tool API, and requests non-thinking output. The v8 PTL pilot was accepted (39/39 contract/native checks and 12/12 generated tests) in 432.99 seconds; this is one unscored result, not qualification. [The private profile](profiles/ptl-morteza89-27b.private.json) records this machine and configuration but still requires qualification evidence.

Use a separate clean PowerShell for the benchmark and the current 600-second freeze. The v8 27B pilot was accepted once; repeated attempts and independent GPU/memory qualification remain pending. Earlier 240-second runs are historical. Before a new attempt, confirm the previous OVMS request has ended; restart the server manually if it remains busy after cancelling the client. Prefix caching differs between 27B and 8B and must be disclosed.

## Candidates

| Profile                                                 | Exact artifact                | Choice and memory caveat                                                                                                                                       |
| ------------------------------------------------------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [local-8b.json](profiles/local-8b.json)                  | OpenVINO/Qwen3-8B-int8-ov     | Preferred first 8B candidate. About 8 GB of weights at an idealized one byte/parameter, plus runtime, cache, OS and Docker overhead; not a measured allocation |
| Separate 8B INT4 profile                                | OpenVINO/Qwen3-8B-int4-ov     | About 4 GB idealized weights; use as a distinct configuration if INT8 lacks headroom                                                                           |
| [article-27b.json](profiles/article-27b.json)            | Morteza89/qwen3.8-27b-int4-ov | Tested article export and reusable profile template; accepted in one 600-second PTL pilot, still unqualified |

System RAM is shared with Windows, WDDM, the desktop, Docker and the model server; model weights alone do not predict whether a configuration fits. Follow the artifact's verified serving recipe. Measure peak system commit, resident memory, GPU allocation and paging under the real task, not just loading. Record failures to fit and how much of the migration passes within the same 10-minute work budget. A different export or quantization is a separately recorded configuration.

The original reference host was Core Ultra X7 358H / Arc B390 with 31.4 GiB RAM and BIOS UX5406AA.110. The current comparison workstation is ASUS NUC16GDKX76 / Arc B390 with 63.4 GiB RAM, Windows 11 Pro build 26200, driver 32.0.101.8860 and BIOS GDPTL579.0039.2026.0420.2004. Record power mode, thermals and available memory for every run set; model loading alone does not establish GPU activity or qualification.

## OVMS Preparation

Use the official [Windows binary deployment guide](https://docs.openvino.ai/ovms_baremetal). The requested 27B card specifies OpenVINO >=2026.4.0 and OpenVINO GenAI >=2026.4.0.0; select an OVMS build that includes those versions. Record the exact build and ZIP/executable SHA-256. A moving `latest` or `weekly` URL is not an experiment pin. Review any driver update under your normal administrator process; this repository does not install drivers.

Use a terminal initialized by the distribution's `setupvars.bat`. A `.bat` launched as a child from PowerShell does not update the parent PowerShell environment; use the initialized Command Prompt for `ovms.exe` or the distribution's documented PowerShell initialization. Do not paste credentials into chat.

### Keep Two Terminals Separate

- **PowerShell terminal:** its prompt starts with `PS`. Use it for `$Model` variables, JSON generation, downloads, endpoint checks, and the benchmark. Do not run `setupvars.bat` here or launch this PowerShell from an initialized OVMS shell.
- **OVMS terminal:** an initialized Command Prompt whose prompt does not start with `PS`. Use it only for `ovms.exe` commands. `setupvars.bat` changes `PATH` and `PYTHONHOME` to use bundled Python; running `uv`, `uvx`, or benchmark Python here can select that embedded runtime and fail with `No module named 'encodings'`.

For the Windows package already extracted on this host, open a separate PowerShell terminal and run these two lines to turn it into the OVMS terminal:

```powershell
Set-Location 'C:\projects\Developer_Workflow_Options_for_AI_PC\ovms_downloaded\windows-2026.4.0-python-on\ovms'
cmd.exe /k "call setupvars.bat"
```

After the initialization message, run only the Command Prompt/OVMS commands in that terminal. `exit` returns to the original PowerShell; otherwise leave it open for the server. Use a separate clean PowerShell terminal for the PowerShell blocks below.

**8B setup in this workspace:** the weights, generated `graph.pbtxt`, and `models/migration-ovms.json` are local Git-ignored assets. A fresh clone will not contain them. Check each path before setup: skip the pinned download only if weights exist; run the configure command below if `graph.pbtxt` is missing; generate `migration-ovms.json` if it is missing, and verify its model ID and base path if it already exists. Stop the 27B server before starting 8B. Keep the profile unqualified until task and hardware qualification pass.

### Install OVMS on a New Host

Downloading a Hugging Face model does **not** install OVMS. If `ovms.exe` is not recognized, download and extract the Windows **python_on** binary ZIP from [the official OVMS 2026.4.0 release assets](https://github.com/openvinotoolkit/model_server/releases/tag/v2026.4.0) first. Do not use `python_off`: the deployment guide documents limited chat-template support and omitted system messages in that build, which would invalidate the shared agent policy. Keep its exact version and archive hash. Locate both `ovms.exe` and `setupvars.bat` in the extracted package. Open **Command Prompt**, not PowerShell, and run the following, substituting your actual extraction directory:

```bat
cd /d C:\tools\ovms
call setupvars.bat
ovms.exe --version
ovms.exe --help
```

`C:\tools\ovms` is an example, not a directory created by this workflow. If the ZIP has a nested `ovms` folder, use that folder. Do not proceed to configuration until `--version` succeeds and `--help` lists the required options. In PowerShell, a local executable needs `.\ovms.exe` or its full path, but that alone does not initialize the runtime DLL paths. A missing DLL or unsupported option is a runtime setup issue, not a reason to redownload model weights.

### Alternative 8B: Download an Explicit Revision

In a clean PowerShell terminal with `uv` available (not the initialized OVMS terminal), choose one model. Skip this section if the model is already downloaded:

```powershell
$Model = 'OpenVINO/Qwen3-8B-int8-ov'
$ModelDir = 'C:\projects\Developer_Workflow_Options_for_AI_PC\models\qwen3-8b-int8'
$Revision = (Invoke-RestMethod "https://huggingface.co/api/models/$Model").sha
$Revision
uvx --from huggingface-hub==0.35.3 hf download $Model --revision $Revision --local-dir $ModelDir
```

Record that revision in the profile and retain the downloaded artifact for all hosts. For the working 27B use the separate pinned Morteza89 steps above, not this 8B recipe or the earlier OpenVINO 27B export. The HF tool download is preparation, not part of the timed task or task container.

The reported completed 8B download used revision `f82c978d714abc9c398efa361827a76d3cae5473` at the path above. Do not rerun the download just to fix a server or configuration-path error. The optional `hf_xet` warning is not a failure when all files finish downloading over HTTP.

### Alternative 8B: Configure and Serve Locally

The following commands use the OVMS 2026 configure and graph-serving interfaces. The corrected configure command was executed successfully on this host with OVMS `2026.4.0.869b2186`; the generated graph specifies GPU, one sequence, a 2 GB cache, and disabled prefix caching. Server startup and a non-thinking warmup succeeded: response model `OpenVINO/Qwen3-8B-int8-ov`, content `READY`, finish reason `stop`, 18 prompt tokens and 2 completion tokens. This is basic inference evidence, not independent GPU activity or migration-task qualification. Confirm options with the exact build's `ovms.exe --help`; do not silently substitute CPU or AUTO if GPU fails.

In the initialized OVMS terminal, substitute the downloaded path. Do not pass `--model_name` with `--configure`; the serving name is set in the JSON configuration:

```text
ovms.exe --configure --model_path "C:\projects\Developer_Workflow_Options_for_AI_PC\models\qwen3-8b-int8" --task text_generation --target_device GPU --max_num_seqs 1 --cache_size 2 --enable_prefix_caching false --tool_parser none --reasoning_parser qwen3
```

This prepares the local graph without starting the server. Stop if this command fails; a serving JSON file cannot replace the missing graph. [The serving configuration](../models/migration-ovms.json) is already saved for the model path above. **Skip the next block when using that saved configuration.** To regenerate it for a different model/path, run the entire block in the separate PowerShell terminal, including the `$ConfigPath` assignment. Variables from another terminal are not shared:

```powershell
$Model = 'OpenVINO/Qwen3-8B-int8-ov'
$ModelDir = 'C:\projects\Developer_Workflow_Options_for_AI_PC\models\qwen3-8b-int8'
$ConfigDir = 'C:\projects\Developer_Workflow_Options_for_AI_PC\models'
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$ConfigPath = Join-Path $ConfigDir 'migration-ovms.json'
@{model_config_list=@(); mediapipe_config_list=@(@{name=$Model; base_path=$ModelDir})} |
    ConvertTo-Json -Depth 5 |
    Set-Content -Encoding ascii -LiteralPath $ConfigPath
Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
```

Use a full path beginning with `C:\`, not `:\`. The latter is not a valid absolute Windows drive path and can be interpreted as an alternate data stream.

Then, in the initialized OVMS terminal:

```text
ovms.exe --config_path "C:\projects\Developer_Workflow_Options_for_AI_PC\models\migration-ovms.json" --rest_bind_address 127.0.0.1 --rest_port 8000 --idle_unload_timeout_seconds 0
```

This configure recipe was verified for 8B, not for the working article 27B. Use the direct launcher above for that export. The benchmark sends text only, without external media or a draft/MTP model. Local profiles request `chat_template_kwargs.enable_thinking=false`; confirm the actual exported template honors it.

The runner is on the Windows host and reaches OVMS through loopback. Task containers are offline and do not call the endpoint themselves; no `host.docker.internal` route or exposed model key is needed.

### Alternative 8B: Verify the Endpoint Before a Pilot

This small warmup is unscored, local-only. Run it in the separate PowerShell terminal while the OVMS terminal remains occupied by the server. Keep its response for model identity and usage inspection:

```powershell
$Model = 'OpenVINO/Qwen3-8B-int8-ov'
$Body = @{
    model=$Model
    messages=@(@{role='user'; content='Return the single word READY.'})
    max_tokens=32
    temperature=0
    chat_template_kwargs=@{enable_thinking=$false}
} | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/chat/completions -Method Post -ContentType 'application/json' -Body $Body
```

The 8B INT4 card currently shows a `/v3` client example while the 27B card shows `/v1`. Do not assume aliases: if the qualified build exposes `/v3/chat/completions`, test that documented endpoint and set the profile base URL to `http://127.0.0.1:8000/v3`. The runner supports either path without changing the task. `expected_returned_model` must match the actual response after checking the server's loaded artifact; an API label alone is not proof of weights or GPU execution.

Capture server logs proving the selected GPU and inspect GPU activity during generation. Repeat with outbound networking unavailable under your organization's approved controls after all assets are downloaded, or retain equivalent routing/configuration evidence showing no cloud/proxy fallback. Do not disable general machine security controls. Both SDK clients ignore proxy environment variables; they cannot inspect what a separate server does internally.

### Record Artifact and Template Hashes

After configuration, retain a manifest of all actual served files (excluding only the HF download metadata directory). Run once outside timing; large binaries take time to hash:

```powershell
Get-ChildItem $ModelDir -Recurse -File |
    Where-Object { $_.FullName -notmatch '\\.cache\\' } |
    Sort-Object FullName |
    ForEach-Object { [pscustomobject]@{Path=$_.FullName.Substring($ModelDir.Length); SHA256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash} } |
    ConvertTo-Json -Depth 4 |
    Set-Content -Encoding ascii artifacts\model-manifest.json
Get-FileHash artifacts\model-manifest.json -Algorithm SHA256
```

Set `export_sha256` to that manifest's hash and retain it with the study. Set `template_sha256` to the actual template file hash; if embedded, hash the containing tokenizer configuration and identify it in your evidence. Hash the runtime ZIP/executable separately. Use the same relative directory layout when comparing manifests. Record server graph configuration and cache parameters too.

## Complete a Local Profile

Fill every `REQUIRED` value with measured data. Update copied hardware values on another host. Record the actual context capacity, exact runtime version and hash, model revision, export/template hashes, cache policy, cold startup time, peak whole-system memory, and paths or descriptions of GPU/offline evidence. Measure cold startup separately from the warm run. Keep the model resident; prefix caching is disabled in the example to avoid cross-attempt prefix reuse.

There is no runner character guard or automatic context compaction. Profile templates leave context capacity unknown; record a provider/model-specific supported limit and exercise the longest pilot conversation with room for 2048 generated tokens before scoring. A backend context error remains a recorded failure, not a task timeout. Changing available context, caching, sampling, quantization, or reasoning settings creates a distinct recorded configuration. The runner cannot observe OVMS prefix-cache hits; keep the server/cache state and attempt order in the run log, or treat results with different warm-cache histories as non-comparable.

Only after the Docker smoke and an actual read/edit/test pilot succeed should you set `qualified: true`. A model that can answer READY but cannot repair the service is not task-qualified. Preserve memory failures and rejected pilots; keep `qualified` false until the gate is satisfied.

## OpenAI API Through the Same Agent

This is a direct OpenAI API run through the benchmark's OpenAI Responses API adapter. It is **not** a VS Code Copilot Chat run: Copilot model access and ChatGPT subscriptions do not provide API credentials or cover API usage. The current comparison uses this OpenAI configuration instead of Claude in the cloud slot; keep those results labeled separately.

The pinned candidate is **GPT-6.1 Sol**, model ID `gpt-6.1-sol`, with standard service tier and medium reasoning effort. It supports the Responses API. The saved profile template is [profiles/openai.json](profiles/openai.json). The rate card records the current short-context rates ($2/M input, $0.10/M cached input, $2.50/M cache write, $10/M output) and long-context rates for requests over 272,000 input tokens. Check [OpenAI&#39;s model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol) and [pricing page](https://developers.openai.com/api/docs/pricing) again immediately before a study; account availability and rates can change.

1. In the [OpenAI API platform](https://platform.openai.com/), confirm API access, available credit, and the organization/project spend limits. API credit is separate from ChatGPT and Copilot plans. Set a spend limit you are comfortable with; the runner's 600-second work deadline is not a dollar cap.
2. Create a private copy of the template without overwriting an existing profile:

   ```powershell
   if (-not (Test-Path profiles\ptl-openai.private.json)) { Copy-Item profiles\openai.json profiles\ptl-openai.private.json }
   ```
3. Review the copied profile. Keep model ID and expected returned model as `gpt-6.1-sol`, and `qualified: false`. Replace host placeholders with this machine's facts. Do not put the API key in the profile.
4. Create a project API key in the [API keys page](https://platform.openai.com/api-keys). In the same PowerShell process that will run the benchmark, set it as a temporary environment variable using hidden input:

   ```powershell
   $secureKey = Read-Host 'OpenAI API key (input hidden)' -AsSecureString
   $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
   try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer) }
   finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer); $secureKey.Dispose() }
   ```

   The key is not written to the profile or shell command history. It is available to child processes of this PowerShell window; close that window after the run to remove the process-scoped variable. Never paste the key into chat.
5. First make a small, unscored API warmup and verify the returned ID and usage:

   ```powershell
   .\.venv-runner\Scripts\python.exe -c "from openai import OpenAI; r=OpenAI(max_retries=0).responses.create(model='gpt-6.1-sol', input='Reply READY only.', max_output_tokens=64, reasoning={'effort':'medium'}); print({'model':r.model,'text':r.output_text,'usage':r.usage.model_dump() if r.usage else None})"
   ```
6. Run one unscored pilot from `dependency-migration`, against the same frozen task as the local attempts:

   ```powershell
   .\.venv-runner\Scripts\python.exe bench.py run --profile profiles\ptl-openai.private.json --freeze artifacts\freeze-600s-v8.json --allow-cloud
   ```

The runner records native input/output, cached input and cache-write tokens and estimates cost using the saved standard rate card. A usage mismatch or missing rate data produces an unknown fee rather than zero. Local evaluation runs after model work stops. Provider-side requests already in flight may remain billable after client termination. Keep this pilot unscored and the profile unqualified until the result, host metadata, and measurements have been reviewed.

## Claude Through the Same Agent

Copy [profiles/claude.json](profiles/claude.json) to your private study profile. Choose one exact, currently accessible Claude API model ID, not a `latest` alias. A documented example is `claude-sonnet-4-5-20250929`, but its availability and price on your account must be checked before use. Fill both model identity fields, local host metadata, the saved rate-card timestamp/source, service tier, and all five USD-per-million token rates.

Use the standard non-streaming Messages API, no explicit prompt-cache markers, no extended-thinking parameter, and the common output limit/temperature. If your chosen model does not support these settings, qualify a supported fixed model or change the common policy before freezing. The raw response usage still records cache fields when returned. The runner charges input, output, cache reads, five-minute writes and one-hour writes separately; incomplete usage is reported as unknown. Reconcile any unresolved charges against the provider's billing records.

Set `ANTHROPIC_API_KEY` directly in your terminal or approved secret manager, never in a JSON file or chat. Cloud calls require `--allow-cloud`, including pilots. No cloud call was made during package authoring. The same 600-second work budget applies; **it is not a dollar spending cap**. Review pricing and provider-side spending controls. Client termination does not guarantee server-side work stops immediately, and incomplete usage/fees remain unknown until reconciled. Provider errors are recorded separately from the work deadline. Evaluation happens locally after model work stops.

## Source Checks

Directly consulted on 2026-10-05; online cards can change, so pin artifacts rather than relying on this date:

- [Requested 27B OpenVINO artifact and runtime requirements](https://huggingface.co/OpenVINO/Qwen3.8-27B-int4-ov)
- [Qwen3.8 model, non-thinking option and reasoning controls](https://huggingface.co/Qwen/Qwen3.8-27B)
- [8B INT8 artifact](https://huggingface.co/OpenVINO/Qwen3-8B-int8-ov)
- [8B INT4 artifact and OVMS GPU example](https://huggingface.co/OpenVINO/Qwen3-8B-int4-ov)
- [OVMS parameters, configure mode, target GPU and cache settings](https://docs.openvino.ai/2026/model-server/ovms_docs_parameters.html)
- [Mini-SWE-Agent documentation](https://mini-swe-agent.com/latest/); the installed 2.4.6 package, not an assumed import path, grounds this implementation.
- [Pydantic migration guide](https://docs.pydantic.dev/latest/migration/)
- [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
