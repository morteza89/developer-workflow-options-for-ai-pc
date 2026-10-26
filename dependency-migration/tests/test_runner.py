import ast
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

import bench
import comparison_report
import qualify


def test_model_setup_completeness_and_interrupted_download(tmp_path):
    import model_setup

    model = dict(model_setup.MODELS["qwen3-coder-30b-a3b-ov"], weights={"openvino_model.bin": 5})
    assert not model_setup.complete(tmp_path, model)
    names = list(model_setup.required_files(model))
    for name in names:
        (tmp_path / name).write_text("asset", encoding="utf-8")
    assert model_setup.complete(tmp_path, model)
    (tmp_path / model_setup.PENDING).touch()
    assert not model_setup.complete(tmp_path, model)
    (tmp_path / model_setup.PENDING).unlink()
    (tmp_path / model_setup.RECEIPT).write_text(json.dumps({**model, "files": {name: 5 for name in names}}), encoding="utf-8")
    assert model_setup.complete(tmp_path, model)
    (tmp_path / names[0]).write_text("truncated", encoding="utf-8")
    assert not model_setup.complete(tmp_path, model)


def test_model_setup_download_retry_progress_and_offline_reuse(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    import huggingface_hub
    import model_setup

    model = dict(model_setup.MODELS["qwen3-coder-30b-a3b-ov"], weights={"openvino_model.bin": 5})
    monkeypatch.setitem(model_setup.MODELS, "test-local", model)
    names = list(model_setup.required_files(model))
    info = SimpleNamespace(sha=model["revision"], siblings=[SimpleNamespace(rfilename=name, size=5) for name in names])
    monkeypatch.setattr(huggingface_hub.HfApi, "model_info", lambda *args, **kwargs: info)
    monkeypatch.setattr(model_setup.shutil, "disk_usage", lambda path: SimpleNamespace(free=10 ** 10))
    calls = []

    def download_file(**kwargs):
        assert kwargs["revision"] == model["revision"]
        assert kwargs["token"] is False and kwargs["endpoint"] == "https://huggingface.co"
        calls.append(kwargs)
        if len(calls) == 2:
            raise OSError("simulated connection interruption")
        with kwargs["tqdm_class"](total=5, desc=kwargs["filename"], unit="B", disable=False) as progress:
            progress.update(5)
        (kwargs["local_dir"] / kwargs["filename"]).write_text("asset", encoding="utf-8")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download_file)
    with pytest.raises(OSError, match="connection interruption"):
        model_setup.prepare("test-local", tmp_path)
    directory = tmp_path / model["directory"]
    assert (directory / model_setup.PENDING).exists()
    assert not model_setup.complete(directory, model)
    model_setup.prepare("test-local", tmp_path)
    assert model_setup.complete(directory, model)
    assert not (directory / model_setup.PENDING).exists()
    assert "100%" in capsys.readouterr().out
    before = len(calls)
    monkeypatch.setattr(huggingface_hub.HfApi, "model_info", lambda *args, **kwargs: pytest.fail("Existing model should work offline"))
    model_setup.prepare("test-local", tmp_path)
    assert len(calls) == before


@pytest.mark.parametrize("failure", ["disk", "revision", "manifest", "unsafe"])
def test_model_setup_rejects_invalid_download_before_transfer(tmp_path, monkeypatch, failure):
    from types import SimpleNamespace
    import huggingface_hub
    import model_setup

    model = dict(model_setup.MODELS["qwen3-coder-30b-a3b-ov"], weights={"openvino_model.bin": 5})
    files = {name: 5 for name in model_setup.required_files(model)}
    if failure == "manifest":
        files.pop("openvino_model.bin")
    if failure == "unsafe":
        files["../outside.bin"] = 5
    info = SimpleNamespace(sha="wrong" if failure == "revision" else model["revision"],
                           siblings=[SimpleNamespace(rfilename=name, size=size) for name, size in files.items()])
    monkeypatch.setattr(huggingface_hub.HfApi, "model_info", lambda *args, **kwargs: info)
    monkeypatch.setattr(model_setup.shutil, "disk_usage", lambda path: SimpleNamespace(free=0 if failure == "disk" else 10 ** 10))
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", lambda **kwargs: pytest.fail("Invalid preparation must not download"))
    with pytest.raises((RuntimeError, ValueError)):
        model_setup.download(model, tmp_path)
    assert not (tmp_path / model_setup.RECEIPT).exists()


def test_model_setup_blocks_concurrent_preparation(tmp_path, monkeypatch):
    from filelock import FileLock
    import model_setup

    model = model_setup.MODELS["qwen3-coder-30b-a3b-ov"]
    directory = tmp_path / model["directory"]
    directory.mkdir()
    monkeypatch.setattr(model_setup, "download", lambda *args: pytest.fail("Concurrent setup must not download"))
    with FileLock(str(directory / ".workflow-model-setup.lock")):
        with pytest.raises(RuntimeError, match="Another controller"):
            model_setup.prepare("qwen3-coder-30b-a3b-ov", tmp_path)


def run_controller_powershell(tmp_path, body):
    if os.name != "nt":
        pytest.skip("Controller execution requires Windows")
    windows_powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    executable = str(windows_powershell) if windows_powershell.is_file() else shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    assert executable, "PowerShell is required on Windows"
    script = tmp_path / "controller-test.ps1"
    script.write_text(r'''
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$tokens = $null
$parseErrors = $null
$controller = [System.Management.Automation.Language.Parser]::ParseFile($env:CONTROLLER_TEST_SOURCE, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
function Assert-That($condition, [string]$message) {
    if (-not $condition) { throw $message }
}
function Import-ControllerFunction([string]$name) {
    $matches = @($controller.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true))
    Assert-That ($matches.Count -eq 1) "Expected one function: $name"
    $matches[0].Extent.Text
}
function Get-ControllerHandler([string]$owner, [string]$event) {
    $matches = @($controller.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.InvokeMemberExpressionAst] -and
        $node.Expression.Extent.Text -eq ('$' + $owner) -and $node.Member.Value -eq $event
    }, $true))
    Assert-That ($matches.Count -eq 1) "Expected one handler: $owner.$event"
    $handler = $matches[0].Arguments[0].ScriptBlock
    $text = $handler.Extent.Text
    $types = @($handler.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.TypeExpressionAst] -and
        $node.TypeName.FullName -eq 'System.Windows.Forms.MessageBox'
    }, $true) | Sort-Object { $_.Extent.StartOffset } -Descending)
    foreach ($type in $types) {
        $offset = $type.Extent.StartOffset - $handler.Extent.StartOffset
        $text = $text.Remove($offset, $type.Extent.Text.Length).Insert($offset, '[ControllerTest.MessageBox]')
    }
    [scriptblock]::Create($text.Substring(1, $text.Length - 2))
}
foreach ($name in @('profilePaths', 'templatePaths', 'modelNames')) {
    $assignments = @($controller.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and
        $node.Left.Extent.Text -eq ('$script:' + $name)
    }, $true))
    Assert-That ($assignments.Count -eq 1) "Expected one array: $name"
    . ([scriptblock]::Create($assignments[0].Extent.Text))
}
$script:profileRoot = Join-Path $env:CONTROLLER_TEST_TEMP 'profiles'
New-Item -ItemType Directory -Path $script:profileRoot | Out-Null
$script:setupProcess = $null
$script:setupSelection = $null
$modelPicker = [pscustomobject]@{ Enabled = $true }
$reportButton = [pscustomobject]@{ Enabled = $true }
$comparisonButton = [pscustomobject]@{ Enabled = $true }
function Write-Log { param($message) }
''' + body + "\nWrite-Output 'CONTROLLER_TEST_PASSED'\n", encoding="utf-8")
    environment = dict(os.environ, CONTROLLER_TEST_SOURCE=str(bench.ENGINE_ROOT / "demo-controller.ps1"),
                       CONTROLLER_TEST_TEMP=str(tmp_path))
    environment.pop("PSModulePath", None)
    result = subprocess.run(
        [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONTROLLER_TEST_PASSED" in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize("exit_code", [0, 7])
def test_controller_real_preparation_process_preserves_exit_code(tmp_path, exit_code):
    run_controller_powershell(tmp_path, r'''
$script:logRoot = $env:CONTROLLER_TEST_TEMP
$script:launches = 0
$script:messages = @()
function Add-WatchedFile($path) { }
function Read-WatchedFiles { }
function Write-Log($message) { $script:messages += $message }
function Get-SelectedModel { [pscustomobject]@{ Profile = [pscustomobject]@{ model = 'qwen3.8-27b-ov' } } }
function Start-LocalServer($selected) { $script:launches++ }
foreach ($name in @('Start-TrackedProcess', 'Update-ModelPreparation')) {
    . ([scriptblock]::Create((Import-ControllerFunction $name)))
}
$script:setupSelection = Get-SelectedModel
$script:setupProcess = Start-TrackedProcess $env:ComSpec '/d /c exit __EXIT_CODE__' $env:CONTROLLER_TEST_TEMP 'real-process'
try {
    Assert-That ($script:setupProcess.WaitForExit(15000)) 'Test child did not exit'
    Assert-That ($script:setupProcess.HasExited) 'Exited child was not detected'
    $script:setupProcess.Refresh()
    $actualExit = $script:setupProcess.ExitCode
    Assert-That ($null -ne $actualExit -and $actualExit -eq __EXIT_CODE__) "Lost real process exit status: [$actualExit]"
    Update-ModelPreparation
    Assert-That ($null -eq $script:setupProcess) 'Finished preparation was not cleared'
    Assert-That ($script:launches -eq __EXPECTED_LAUNCHES__) 'Wrong server handoff for real exit code'
    Assert-That (-not (($script:messages -join ' ').Contains('(exit )'))) 'Blank exit status logged'
}
finally {
    if ($script:setupProcess -and -not $script:setupProcess.HasExited) { $script:setupProcess.Kill() }
}
'''.replace('__EXIT_CODE__', str(exit_code)).replace('__EXPECTED_LAUNCHES__', str(int(exit_code == 0))))


@pytest.mark.parametrize("model_id", ["qwen3.8-27b-ov", "OpenVINO/Qwen3-8B-int8-ov", "qwen3-coder-30b-a3b-ov", "qwen38-fable5-int4"])
def test_controller_model_download_lifecycle(tmp_path, model_id):
    run_controller_powershell(tmp_path, r'''
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
namespace ControllerTest {
    public static class MessageBox {
        public static string Choice = "Yes";
        public static string LastMessage;
        public static string Show(string text, string title, string buttons, string icon) {
            LastMessage = text;
            return Choice;
        }
    }
}
'@
$script:workspaceRoot = Join-Path $env:CONTROLLER_TEST_TEMP 'shared laptop workspace'
$script:engineRoot = Join-Path $script:workspaceRoot 'dependency-migration'
$script:modelRoot = Join-Path $script:workspaceRoot 'models'
$script:ovmsRoot = Join-Path $script:workspaceRoot 'ovms'
$script:runnerPython = Join-Path $script:engineRoot 'runner python.exe'
foreach ($directory in @($script:engineRoot, $script:modelRoot, $script:ovmsRoot)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}
foreach ($path in @($script:runnerPython, (Join-Path $script:engineRoot 'model_setup.py'), (Join-Path $script:ovmsRoot 'setupvars.bat'), (Join-Path $script:ovmsRoot 'ovms.exe'))) {
    [System.IO.File]::WriteAllText($path, 'test sentinel; never execute')
}
$script:selectedModel = '__MODEL_ID__'
$script:selectedProvider = 'local'
$script:taskProcess = $null
$script:serverProcess = $null
$script:serverReady = $false
$script:warmupReady = $false
$script:downloads = 0
$script:launches = 0
$script:kills = 0
$script:logs = @()
function Write-Log($message) { $script:logs += $message }
function Get-SelectedModel { [pscustomobject]@{ Name = 'selected local model'; Profile = [pscustomobject]@{ provider = $script:selectedProvider; model = $script:selectedModel } } }
function Test-Port8000 { $false }
function Read-WatchedFiles { }
function Start-TrackedProcess($FileName, $Arguments, $WorkingDirectory, $Tag) {
    Assert-That ($FileName -eq $script:runnerPython -and $Tag -eq 'model-download') 'Wrong setup executable or tag'
    Assert-That ($Arguments.Contains(('"' + (Join-Path $script:engineRoot 'model_setup.py') + '"')) -and $Arguments.Contains(('"' + $script:modelRoot + '"')) -and $Arguments.Contains($script:selectedModel)) 'Missing quoted setup arguments'
    Assert-That ($WorkingDirectory -eq $script:workspaceRoot) 'Wrong setup working directory'
    $script:downloads++
    $process = [pscustomobject]@{ Id = 22222; HasExited = $false; ExitCode = 0 }
    $process | Add-Member ScriptMethod Refresh { }
    $process
}
function Start-LocalServer($selected) {
    Assert-That ($selected.Profile.model -eq $script:selectedModel) 'Started a different selection'
    $script:launches++
}
function Start-Process { param($FilePath, $ArgumentList, $WindowStyle, [switch]$Wait, [switch]$PassThru)
    Assert-That ($FilePath -eq 'taskkill.exe' -and $ArgumentList -eq '/PID 22222 /T /F' -and $Wait -and $PassThru) 'Wrong cancellation target'
    $script:kills++
    [pscustomobject]@{ ExitCode = 0 }
}
foreach ($name in @('apiKeyButton', 'startButton', 'stopButton', 'warmupButton', 'runButton')) {
    Set-Variable -Name $name -Value ([pscustomobject]@{ Enabled = $true; Text = '' })
}
$apiStatus = [pscustomobject]@{ Text = ''; ForeColor = $null }
$serverStatus = [pscustomobject]@{ Text = ''; ForeColor = $null }
$timer = [pscustomobject]@{ Stopped = $false }
$timer | Add-Member ScriptMethod Stop { $this.Stopped = $true }
foreach ($name in @('Update-Status', 'Update-ModelPreparation', 'Stop-ModelPreparation')) {
    . ([scriptblock]::Create((Import-ControllerFunction $name)))
}
$start = Get-ControllerHandler 'startButton' 'Add_Click'
$stop = Get-ControllerHandler 'stopButton' 'Add_Click'
$closing = Get-ControllerHandler 'form' 'Add_FormClosing'
& $start
Assert-That ($script:downloads -eq 1 -and $script:launches -eq 0) 'Start launched server before setup'
Assert-That (-not $modelPicker.Enabled -and -not $runButton.Enabled -and -not $warmupButton.Enabled -and -not $startButton.Enabled -and -not $reportButton.Enabled -and -not $comparisonButton.Enabled) 'Setup allowed overlapping operations'
Assert-That ($stopButton.Enabled -and $stopButton.Text -eq 'Cancel download') 'Download cannot be canceled'
Assert-That (($script:logs -join ' ').Contains('Please wait')) 'Missing wait/download log message'
& $start
Assert-That ($script:downloads -eq 1) 'Duplicate setup started'
Update-ModelPreparation
Assert-That ($script:launches -eq 0) 'Running setup launched server'
$script:setupProcess.HasExited = $true
Update-ModelPreparation
Update-ModelPreparation
Assert-That ($script:launches -eq 1 -and $null -eq $script:setupProcess -and $null -eq $script:setupSelection) 'Successful setup did not launch exactly once'
Update-Status
Assert-That ($modelPicker.Enabled) 'Picker stayed locked after setup'
& $start
$script:setupProcess.HasExited = $true
$script:setupProcess.ExitCode = 1
Update-ModelPreparation
Assert-That ($script:launches -eq 1 -and $null -eq $script:setupProcess) 'Failed setup launched a server'
& $start
& $stop
Update-ModelPreparation
Assert-That ($script:kills -eq 1 -and $null -eq $script:setupProcess -and $script:launches -eq 1) 'Canceled setup launched or leaked state'
& $start
$script:selectedModel = 'changed-selection'
$script:setupProcess.HasExited = $true
Update-ModelPreparation
Assert-That ($script:launches -eq 1) 'Completion reused stale selection'
$script:selectedModel = '__MODEL_ID__'
& $start
[ControllerTest.MessageBox]::Choice = 'No'
$closingEvent = [pscustomobject]@{ Cancel = $false }
$closingEvent | ForEach-Object $closing
Assert-That ($closingEvent.Cancel -and $null -ne $script:setupProcess -and -not $timer.Stopped) 'Close ignored pending download'
[ControllerTest.MessageBox]::Choice = 'Yes'
$closingEvent | ForEach-Object $closing
Assert-That ($null -eq $script:setupProcess -and $script:kills -eq 2 -and $timer.Stopped) 'Close did not cancel preparation'
$before = $script:downloads
$script:selectedProvider = 'openai'
& $start
Assert-That ($script:downloads -eq $before -and $script:launches -eq 1) 'Cloud choice started a model download'
'''.replace('__MODEL_ID__', model_id))


def test_controller_local_choices_copy_coder_and_fable_templates(tmp_path):
    run_controller_powershell(tmp_path, r'''
Assert-That (($script:profilePaths -join '|') -ceq 'ptl-morteza89-27b.private.json|ptl-8b.private.json|ptl-openai.private.json|ptl-openai-astra.private.json|ptl-qwen3-coder-30b.private.json|ptl-qwen38-fable5-coding-27b.private.json') 'Private profile choices are not aligned'
Assert-That (($script:templatePaths -join '|') -ceq 'article-27b.json|local-8b.json|openai.json|openai-astra.json|qwen3-coder-30b.json|qwen38-fable5-coding-27b.json') 'Template choices are not aligned'
Assert-That (($script:modelNames -join '|') -ceq 'Qwen3.8 27B INT4 (local)|Qwen3 8B INT8 (local)|GPT-6.1 Sol (OpenAI API)|GPT-6 Astra (OpenAI API)|Qwen3-Coder 30B-A3B INT4 (local)|Qwen3.8 27B Fable 5 Coding INT4 (local)') 'Display choices are not aligned'
$template = Join-Path $script:profileRoot $script:templatePaths[4]
$source = Join-Path (Split-Path $env:CONTROLLER_TEST_SOURCE) ('profiles\' + $script:templatePaths[4])
Copy-Item -LiteralPath $source -Destination $template
$modelPicker = [pscustomobject]@{ SelectedIndex = 4 }
. ([scriptblock]::Create((Import-ControllerFunction 'Get-SelectedModel')))
$selected = Get-SelectedModel
Assert-That ($selected.Index -eq 4 -and $selected.Name -ceq $script:modelNames[4]) 'Wrong fifth selection'
Assert-That ($selected.Path -eq (Join-Path $script:profileRoot $script:profilePaths[4])) 'Profile escaped temporary root'
Assert-That ($selected.Profile.provider -eq 'local' -and $selected.Profile.model -ceq 'qwen3-coder-30b-a3b-ov') 'Wrong copied model'
Assert-That ($selected.Profile.inference.model_revision -ceq '21140c68a63012da511fe50656319e00be2f6542') 'Wrong copied revision'
Assert-That ([Convert]::ToBase64String([System.IO.File]::ReadAllBytes($template)) -ceq [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($selected.Path))) 'Private copy differs from template'
[System.IO.File]::WriteAllText($selected.Path, '{"provider":"local","model":"private-sentinel"}')
$again = Get-SelectedModel
Assert-That ($again.Profile.model -ceq 'private-sentinel') 'Existing private profile was overwritten'
$fableTemplate = Join-Path $script:profileRoot $script:templatePaths[5]
$fableSource = Join-Path (Split-Path $env:CONTROLLER_TEST_SOURCE) ('profiles\' + $script:templatePaths[5])
Copy-Item -LiteralPath $fableSource -Destination $fableTemplate
$modelPicker = [pscustomobject]@{ SelectedIndex = 5 }
$fable = Get-SelectedModel
Assert-That ($fable.Index -eq 5 -and $fable.Name -ceq $script:modelNames[5]) 'Wrong sixth selection'
Assert-That ($fable.Profile.provider -eq 'local' -and $fable.Profile.model -ceq 'qwen38-fable5-int4') 'Wrong Fable profile'
Assert-That ($fable.Profile.inference.model_revision -ceq '6a84fb7b49812848f4541b84ae45307ad4c1fb8d') 'Wrong Fable revision'
Assert-That (@(Get-ChildItem $script:profileRoot -File).Count -eq 4) 'Unexpected profile files created'
''')


def test_controller_owned_model_mismatch_blocks_stale_readiness(tmp_path):
    run_controller_powershell(tmp_path, r'''
Add-Type -AssemblyName System.Drawing
. ([scriptblock]::Create((Import-ControllerFunction 'Update-Status')))
function Get-SelectedModel { [pscustomobject]@{ Profile = [pscustomobject]@{ provider = 'local'; model = $script:selectedModel } } }
function Read-WatchedFiles { }
function Test-Port8000 { throw 'Owned-server readiness must not probe the port' }
foreach ($name in @('apiKeyButton', 'startButton', 'stopButton', 'warmupButton', 'runButton')) {
    Set-Variable -Name $name -Value ([pscustomobject]@{ Enabled = $true; Text = '' })
}
$apiStatus = [pscustomobject]@{ Text = ''; ForeColor = $null }
$serverStatus = [pscustomobject]@{ Text = ''; ForeColor = $null }
$script:serverProcess = [pscustomobject]@{ HasExited = $false }
$models = @('qwen3.8-27b-ov', 'qwen3-coder-30b-a3b-ov', 'qwen38-fable5-int4')
foreach ($ownedModel in $models) {
    $script:serverModel = $ownedModel
    $script:selectedModel = @($models | Where-Object { $_ -ne $ownedModel })[0]
    foreach ($ready in @($false, $true)) {
        foreach ($busy in @($false, $true)) {
            $script:serverReady = $ready
            $script:warmupReady = $true
            $script:taskProcess = if ($busy) { [pscustomobject]@{ HasExited = $false } } else { $null }
            Update-Status
            Assert-That (-not $warmupButton.Enabled -and -not $runButton.Enabled -and -not $startButton.Enabled) 'Mismatched owned model allowed work using stale readiness'
            Assert-That ($stopButton.Enabled -eq (-not $busy)) 'Mismatched owned model has wrong stop state'
            Assert-That ($serverStatus.Text.Contains($ownedModel) -and $serverStatus.Text.Contains('stop')) 'Mismatch status does not identify owned model'
            Assert-That ($script:serverReady -eq $ready) 'Mismatch inferred or changed global readiness'
        }
    }
    $script:taskProcess = $null
    $script:selectedModel = $ownedModel
    foreach ($ready in @($false, $true)) {
        $script:serverReady = $ready
        Update-Status
        Assert-That ($warmupButton.Enabled -and $stopButton.Enabled -and -not $startButton.Enabled) 'Matching owned model controls are wrong'
        Assert-That ($runButton.Enabled -eq $ready) 'Matching owned model ignored actual server readiness'
    }
}
''')


def test_controller_local_launcher_dispatch_and_owned_model_cleanup(tmp_path):
    run_controller_powershell(tmp_path, r'''
Add-Type -TypeDefinition @'
namespace ControllerTest {
    public static class MessageBox {
        public static string LastMessage;
        public static string Show(string text, string title, string buttons, string icon) {
            LastMessage = text;
            return "Yes";
        }
    }
}
'@
function Get-SelectedModel { [pscustomobject]@{ Name = 'test local'; Profile = [pscustomobject]@{ provider = 'local'; model = $script:selectedModel } } }
function Test-Port8000 { $false }
function Update-Status { }
function Read-WatchedFiles { }
function Update-ThroughputStatus { }
function Update-ModelPreparation { }
function Start-TrackedProcess($FileName, $Arguments, $WorkingDirectory, $Tag) {
    $script:started += [pscustomobject]@{ FileName = $FileName; Arguments = $Arguments; WorkingDirectory = $WorkingDirectory; Tag = $Tag }
    [pscustomobject]@{ Id = 12345; HasExited = $false; ExitCode = 0 }
}
function Start-Process { param($FilePath, $ArgumentList, $WindowStyle, [switch]$Wait)
    Assert-That ($FilePath -eq 'taskkill.exe' -and $ArgumentList -eq '/PID 12345 /T /F' -and $Wait) 'Unexpected stop process'
    $script:stopCalls++
}
$script:workspaceRoot = $env:CONTROLLER_TEST_TEMP
$script:modelRoot = Join-Path $script:workspaceRoot 'models'
$script:ovmsRoot = Join-Path $script:workspaceRoot 'ovms'
$script:logRoot = Join-Path $script:workspaceRoot 'logs'
foreach ($directory in @($script:modelRoot, $script:ovmsRoot, $script:logRoot)) {
    New-Item -ItemType Directory -Path $directory | Out-Null
}
foreach ($relative in @('start-27b-article.cmd', 'start-qwen3-coder-30b.cmd', 'start-qwen38-fable5-coding-27b.cmd', 'morteza89-qwen3.8-27b-int4-ov\openvino_language_model.xml', 'qwen3-coder-30b-a3b-int4-ov\openvino_model.xml', 'qwen3.8-27b-fable-5-coding-distilled-int4-ov\openvino_language_model.xml', 'qwen3-8b-int8\openvino_model.xml')) {
    $path = Join-Path $script:modelRoot $relative
    New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
    [System.IO.File]::WriteAllText($path, 'test-only sentinel; never execute')
}
foreach ($relative in @('setupvars.bat', 'ovms.exe')) {
    [System.IO.File]::WriteAllText((Join-Path $script:ovmsRoot $relative), 'test-only sentinel; never execute')
}
. ([scriptblock]::Create((Import-ControllerFunction 'Start-LocalServer')))
$start = { Start-LocalServer (Get-SelectedModel) }
$stop = Get-ControllerHandler 'stopButton' 'Add_Click'
$tick = Get-ControllerHandler 'timer' 'Add_Tick'
$script:taskProcess = $null
$script:stopCalls = 0
$wrapper = Join-Path $script:logRoot 'start-local-model.cmd'
foreach ($case in @(
    @('qwen3.8-27b-ov', 'start-27b-article.cmd', $script:workspaceRoot),
    @('qwen3-coder-30b-a3b-ov', 'start-qwen3-coder-30b.cmd', $script:workspaceRoot),
    @('qwen38-fable5-int4', 'start-qwen38-fable5-coding-27b.cmd', $script:workspaceRoot),
    @('OpenVINO/Qwen3-8B-int8-ov', 'ovms.exe', $script:ovmsRoot)
)) {
    $script:selectedModel = $case[0]
    $script:serverProcess = $null
    $script:serverModel = $null
    $script:serverReady = $true
    $script:warmupReady = $true
    $script:started = @()
    [ControllerTest.MessageBox]::LastMessage = $null
    & $start
    Assert-That ($script:started.Count -eq 1) "Did not start exactly once for $($case[0])"
    $call = $script:started[0]
    Assert-That ($call.Tag -eq 'server' -and $call.FileName -eq $env:ComSpec -and $call.Arguments.Contains($wrapper) -and $call.WorkingDirectory -eq $case[2]) 'Wrong tracked process dispatch'
    Assert-That ((Get-Content $wrapper -Raw).Contains($case[1])) 'Wrong launcher wrapper'
    Assert-That ([string]::IsNullOrEmpty([ControllerTest.MessageBox]::LastMessage)) "Start handler caught an unexpected error: $([ControllerTest.MessageBox]::LastMessage)"
    Assert-That ($script:serverModel -eq $case[0] -and $null -ne $script:serverProcess) 'Started server ownership not recorded'
    Assert-That (-not $script:serverReady -and -not $script:warmupReady) 'Start retained stale readiness'
    & $stop
    Assert-That ($null -eq $script:serverModel -and $null -eq $script:serverProcess -and -not $script:serverReady -and -not $script:warmupReady) 'Stop retained owned server state'
    $script:serverProcess = [pscustomobject]@{ HasExited = $true; ExitCode = 0 }
    $script:serverModel = $case[0]
    $script:serverReady = $true
    & $tick
    Assert-That ($null -eq $script:serverProcess -and $null -eq $script:serverModel -and -not $script:serverReady) 'Exited server ownership not cleared'
}
Assert-That ($script:stopCalls -eq 4) 'Stop did not use mocked process termination'
Remove-Item -LiteralPath $wrapper
$script:selectedModel = 'unknown-local-model'
$script:started = @()
$unknownError = $null
try { & $start } catch { $unknownError = $_.Exception.Message }
Assert-That ($script:started.Count -eq 0 -and -not (Test-Path $wrapper)) 'Unknown model fell back to a launcher'
Assert-That ($unknownError -eq 'No local launcher is registered for unknown-local-model.') 'Unknown model did not report explicit rejection'
Assert-That ($null -eq $script:serverProcess -and $null -eq $script:serverModel) 'Unknown model acquired server ownership'
''')


CONTROLLER_MESSAGEBOX_STUB = r'''
Add-Type -TypeDefinition @'
namespace ControllerTest {
    public static class MessageBox {
        public static string Choice = "Yes";
        public static string LastMessage;
        public static System.Collections.Generic.List<string> Titles = new System.Collections.Generic.List<string>();
        public static string Show(string text, string title, string buttons, string icon) {
            LastMessage = text;
            Titles.Add(title);
            return Choice;
        }
    }
}
'@
'''


@pytest.mark.parametrize("case", ["yes", "no", "stop-fails"])
def test_controller_closing_with_active_pilot(tmp_path, case):
    run_controller_powershell(tmp_path, CONTROLLER_MESSAGEBOX_STUB + r'''
$case = '__CASE__'
$script:logs = @()
function Write-Log($message) { $script:logs += $message }
$script:kills = @()
function Start-Process { param($FilePath, $ArgumentList, $WindowStyle, [switch]$Wait, [switch]$PassThru)
    Assert-That ($FilePath -eq 'taskkill.exe' -and $Wait) 'Unexpected process launch while closing'
    $script:kills += $ArgumentList
    if ($ArgumentList -eq '/PID 4242 /T /F') {
        Assert-That $PassThru 'Pilot stop ignored the taskkill exit status'
        if ($case -eq 'stop-fails') { return [pscustomobject]@{ ExitCode = 128 } }
        $script:taskProcess.HasExited = $true
    }
    [pscustomobject]@{ ExitCode = 0 }
}
. ([scriptblock]::Create((Import-ControllerFunction 'Stop-ActivePilot')))
$closing = Get-ControllerHandler 'form' 'Add_FormClosing'
$timer = [pscustomobject]@{ Stopped = $false }
$timer | Add-Member ScriptMethod Stop { $this.Stopped = $true }
$pilot = [pscustomobject]@{ Id = 4242; HasExited = $false; ExitCode = $null }
$script:taskProcess = $pilot
$script:serverProcess = [pscustomobject]@{ Id = 5151; HasExited = $false }
$script:openReportPath = 'pending-report.md'
[ControllerTest.MessageBox]::Choice = if ($case -eq 'no') { 'No' } else { 'Yes' }
$closingEvent = [pscustomobject]@{ Cancel = $false }
$closingEvent | ForEach-Object $closing
$titles = [ControllerTest.MessageBox]::Titles
Assert-That ($titles.Count -ge 1 -and $titles[0] -eq 'Pilot running') 'Pilot question was not asked first'
Assert-That ([ControllerTest.MessageBox]::LastMessage -like 'A pilot is running (possibly billable)*' -or $titles.Count -gt 1) 'Pilot prompt text changed'
switch ($case) {
    'yes' {
        Assert-That (-not $closingEvent.Cancel -and $timer.Stopped) 'Yes did not close the window'
        Assert-That ($script:kills.Count -eq 2 -and $script:kills[0] -eq '/PID 4242 /T /F' -and $script:kills[1] -eq '/PID 5151 /T /F') 'Pilot was not stopped before the server'
        Assert-That ($null -eq $script:taskProcess -and $null -eq $script:openReportPath) 'Stopped pilot state leaked'
        Assert-That ($titles.Count -eq 2 -and $titles[1] -eq 'Local server running') 'Server question did not follow the pilot question'
        Assert-That (($script:logs -join ' ').Contains('artifacts are retained')) 'Artifact retention was not logged'
    }
    'no' {
        Assert-That ($closingEvent.Cancel -and -not $timer.Stopped) 'No did not cancel closing'
        Assert-That ($script:kills.Count -eq 0) 'No stopped a process'
        Assert-That ([object]::ReferenceEquals($script:taskProcess, $pilot) -and -not $pilot.HasExited) 'No altered the pilot'
        Assert-That ($titles.Count -eq 1) 'No proceeded to later questions'
    }
    'stop-fails' {
        Assert-That ($closingEvent.Cancel -and -not $timer.Stopped) 'Failed stop closed the window'
        Assert-That ($script:kills.Count -eq 1 -and $script:kills[0] -eq '/PID 4242 /T /F') 'Failed pilot stop killed the server'
        Assert-That ([object]::ReferenceEquals($script:taskProcess, $pilot)) 'Failed stop cleared the pilot'
        Assert-That (($script:logs -join ' ').Contains('Could not stop the running pilot')) 'Stop failure was not logged'
        Assert-That ($titles.Count -eq 1) 'Failed stop proceeded to later questions'
    }
}
$script:taskProcess = $null
$script:serverProcess = $null
[ControllerTest.MessageBox]::Titles.Clear()
$closingEvent = [pscustomobject]@{ Cancel = $false }
$closingEvent | ForEach-Object $closing
Assert-That (-not $closingEvent.Cancel -and [ControllerTest.MessageBox]::Titles.Count -eq 0) 'Idle close asked a pilot question'
'''.replace('__CASE__', case))


PILOT_GUI_SETUP = CONTROLLER_MESSAGEBOX_STUB + r'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$script:selectedModel = 'qwen3.8-27b-ov'
$script:changeDuringWarmup = $false
$script:logs = @()
$script:launches = @()
$script:pickerDuringRequest = @()
$script:pickerAtStatusUpdate = @()
function Write-Log($message) { $script:logs += $message }
function Get-SelectedModel {
    [pscustomobject]@{ Name = "display $script:selectedModel"; Path = 'profile sentinel.json'; Profile = [pscustomobject]@{
        provider = 'local'; model = $script:selectedModel; expected_returned_model = $script:selectedModel
        base_url = 'http://127.0.0.1:8000/v3'; extra_body = [pscustomobject]@{ chat_template_kwargs = $null } } }
}
function Invoke-RestMethod { param($Uri, $Method, $Headers, $ContentType, $Body, $TimeoutSec)
    Assert-That ($Uri -eq 'http://127.0.0.1:8000/v3/chat/completions') 'Warmup used an unexpected endpoint'
    $script:pickerDuringRequest += $modelPicker.Enabled
    $requested = ($Body | ConvertFrom-Json).model
    if ($script:changeDuringWarmup) { $script:selectedModel = 'qwen38-fable5-int4' }
    [pscustomobject]@{ model = $requested; choices = @([pscustomobject]@{ message = [pscustomobject]@{ content = 'READY' } }); usage = [pscustomobject]@{ total_tokens = 3 } }
}
function Update-Status { $script:pickerAtStatusUpdate += $modelPicker.Enabled; $modelPicker.Enabled = -not ($script:setupProcess -or $script:taskProcess) }
function Start-TrackedProcess($FileName, $Arguments, $WorkingDirectory, $Tag) {
    $script:launches += [pscustomobject]@{ Arguments = $Arguments; Tag = $Tag }
    [pscustomobject]@{ Id = 777; HasExited = $false; ExitCode = $null }
}
$form = [pscustomobject]@{ Cursor = $null }
$warmupButton = [pscustomobject]@{ Enabled = $true }
$runButton = [pscustomobject]@{ Enabled = $true }
$throughputStatus = [pscustomobject]@{ Text = '' }
$script:installationSettings = $null
$script:benchScript = 'bench.py'
$script:freezePath = Join-Path $env:CONTROLLER_TEST_TEMP 'freeze test.json'
$script:runnerPython = 'python.exe'
$script:workflowRoot = $env:CONTROLLER_TEST_TEMP
$script:taskProcess = $null
$script:serverReady = $false
$script:warmupReady = $false
$script:warmupModel = $null
$warmup = Get-ControllerHandler 'warmupButton' 'Add_Click'
$run = Get-ControllerHandler 'runButton' 'Add_Click'
'''


def test_controller_warmup_binds_readiness_to_selection(tmp_path):
    run_controller_powershell(tmp_path, PILOT_GUI_SETUP + r'''
& $warmup
Assert-That ($script:pickerDuringRequest.Count -eq 1 -and -not $script:pickerDuringRequest[0]) 'Model picker stayed enabled during the warmup'
Assert-That ($script:pickerAtStatusUpdate.Count -eq 1 -and -not $script:pickerAtStatusUpdate[0] -and $modelPicker.Enabled) 'Picker was not re-enabled through Update-Status'
Assert-That ($script:warmupReady -and $script:warmupModel -ceq 'qwen3.8-27b-ov') 'Stable warmup did not bind readiness to the model'
Assert-That ([string]::IsNullOrEmpty([ControllerTest.MessageBox]::LastMessage)) "Warmup raised an error: $([ControllerTest.MessageBox]::LastMessage)"
$script:changeDuringWarmup = $true
& $warmup
Assert-That (-not $script:warmupReady -and $null -eq $script:warmupModel) 'Selection change during warmup recorded readiness'
Assert-That (($script:logs -join ' ').Contains('Selection changed during the warmup')) 'Selection change was not logged'
Assert-That ([string]::IsNullOrEmpty([ControllerTest.MessageBox]::LastMessage)) 'Selection change was reported as a warmup error'
Assert-That ($modelPicker.Enabled) 'Picker stayed locked after the changed-selection warmup'
& $run
Assert-That ($script:launches.Count -eq 0) 'Pilot started without readiness after the selection changed'
$script:changeDuringWarmup = $false
$script:selectedModel = 'qwen3.8-27b-ov'
& $warmup
Assert-That ($script:warmupReady -and $script:warmupModel -ceq 'qwen3.8-27b-ov') 'Repeat warmup did not restore readiness'
$script:selectedModel = 'qwen38-fable5-int4'
$script:serverReady = $true
& $run
Assert-That ($script:launches.Count -eq 0) 'Pilot started with readiness recorded for a different model'
Assert-That (($script:logs -join ' ').Contains('Test connection passed for qwen3.8-27b-ov')) 'Model mismatch was not explained'
Assert-That ($script:warmupReady -and $script:warmupModel -ceq 'qwen3.8-27b-ov') 'Refused run changed readiness'
$script:selectedModel = 'qwen3.8-27b-ov'
$script:serverReady = $false
& $run
Assert-That ($script:launches.Count -eq 1 -and $script:launches[0].Tag -eq 'pilot') 'Matching selection could not run'
Assert-That ($script:launches[0].Arguments.Contains('--profile "profile sentinel.json"') -and $script:launches[0].Arguments.Contains('--freeze "' + $script:freezePath + '"')) 'Pilot arguments lost quoting'
''')


def test_controller_run_refuses_while_task_is_active(tmp_path):
    run_controller_powershell(tmp_path, PILOT_GUI_SETUP + r'''
& $warmup
Assert-That ($script:warmupReady) 'Warmup did not pass'
$active = [pscustomobject]@{ Id = 4242; HasExited = $false; ExitCode = $null }
$script:taskProcess = $active
$script:serverReady = $true
$runButton.Enabled = $true
$script:logs = @()
& $run
Assert-That ($script:launches.Count -eq 0) 'Second pilot started while a task was active'
Assert-That (($script:logs -join ' ').Contains('A pilot is already running')) 'Active pilot refusal was not logged'
Assert-That ([ControllerTest.MessageBox]::LastMessage -like 'A pilot is already running*') 'Active pilot refusal was not shown'
Assert-That ([object]::ReferenceEquals($script:taskProcess, $active)) 'Refusal replaced the active task'
$active.HasExited = $true
& $run
Assert-That ($script:launches.Count -eq 1 -and -not [object]::ReferenceEquals($script:taskProcess, $active)) 'Finished task still blocked the next pilot'
''')


@pytest.mark.parametrize("case", ["exit-0", "exit-3", "exit-0-missing-file", "exit-null", "start-failed"])
def test_controller_comparison_report_opens_only_on_success(tmp_path, case):
    run_controller_powershell(tmp_path, r'''
$case = '__CASE__'
$script:logs = @()
$script:opened = @()
$script:started = @()
function Write-Log($message) { $script:logs += $message }
function Update-Status { }
function Update-ThroughputStatus { }
function Update-ModelPreparation { }
function Read-WatchedFiles { }
function Start-Process { param($FilePath) $script:opened += $FilePath }
function Start-TrackedProcess($FileName, $Arguments, $WorkingDirectory, $Tag) {
    if ($case -eq 'start-failed') { throw 'Runner is missing' }
    $script:started += [pscustomobject]@{ Arguments = $Arguments; Tag = $Tag }
    $process = [pscustomobject]@{ Id = 909; HasExited = $false; ExitCode = $null }
    $process | Add-Member ScriptMethod Refresh { }
    $process
}
$script:workflowRoot = $env:CONTROLLER_TEST_TEMP
$script:artifactRoot = Join-Path $script:workflowRoot 'artifacts'
New-Item -ItemType Directory -Path $script:artifactRoot | Out-Null
$script:reportScript = 'comparison_report.py'
$script:freezePath = 'freeze.json'
$script:reportTitle = 'Test Comparison'
$script:runnerPython = 'python.exe'
$script:serverProcess = $null
$script:taskProcess = $null
$script:openReportPath = $null
$comparison = Get-ControllerHandler 'comparisonButton' 'Add_Click'
$tick = Get-ControllerHandler 'timer' 'Add_Tick'
$startError = $null
try { & $comparison } catch { $startError = $_.Exception.Message }
if ($case -eq 'start-failed') {
    Assert-That ($startError -eq 'Runner is missing') 'Start failure was swallowed'
    Assert-That ($null -eq $script:openReportPath -and $null -eq $script:taskProcess) 'Report path recorded before the process started'
    & $tick
    Assert-That ($script:opened.Count -eq 0) 'Failed start opened a report'
}
else {
    Assert-That ($null -eq $startError -and $script:started.Count -eq 1 -and $script:started[0].Tag -eq 'comparison-report') 'Comparison process was not started'
    Assert-That ($script:openReportPath -like (Join-Path $script:artifactRoot 'comparison-report-*.md')) 'Report path was not recorded after start'
    $reportPath = $script:openReportPath
    & $tick
    Assert-That ($script:opened.Count -eq 0 -and $script:openReportPath -eq $reportPath -and $null -ne $script:taskProcess) 'Running report was opened or cleared early'
    $exitCode = switch ($case) { 'exit-3' { 3 } 'exit-null' { $null } default { 0 } }
    $script:taskProcess.HasExited = $true
    $script:taskProcess.ExitCode = $exitCode
    if ($case -ne 'exit-0-missing-file') { [System.IO.File]::WriteAllText($reportPath, '# report') }
    & $tick
    Assert-That ($null -eq $script:taskProcess -and $null -eq $script:openReportPath) 'Finished report task was not cleared'
    if ($case -eq 'exit-0') {
        Assert-That ($script:opened.Count -eq 1 -and $script:opened[0] -eq $reportPath) 'Successful report was not opened'
        Assert-That (-not (($script:logs -join ' ').Contains('generation failed'))) 'Success logged as failure'
    }
    else {
        Assert-That ($script:opened.Count -eq 0) 'Failed report generation opened a report'
        $expected = switch ($case) { 'exit-3' { '*generation failed (exit 3)*' } 'exit-null' { '*generation failed (exit )*' } default { '*generation failed (exit 0)*' } }
        Assert-That (($script:logs -join ' ') -like $expected) 'Failure exit code was not logged'
    }
    & $tick
    Assert-That ($script:opened.Count -eq [int]($case -eq 'exit-0')) 'Report opened again on a later tick'
}
'''.replace('__CASE__', case))


@pytest.mark.parametrize("model_id", ["qwen3.8-27b-ov", "OpenVINO/Qwen3-8B-int8-ov", "qwen3-coder-30b-a3b-ov", "qwen38-fable5-int4"])
def test_controller_local_launcher_wrappers_clear_api_key(tmp_path, model_id):
    run_controller_powershell(tmp_path, r'''
function Test-Port8000 { $false }
function Start-TrackedProcess($FileName, $Arguments, $WorkingDirectory, $Tag) { [pscustomobject]@{ Id = 1; HasExited = $false } }
$script:workspaceRoot = $env:CONTROLLER_TEST_TEMP
$script:modelRoot = Join-Path $script:workspaceRoot 'models'
$script:ovmsRoot = Join-Path $script:workspaceRoot 'ovms'
$script:logRoot = Join-Path $script:workspaceRoot 'logs'
foreach ($directory in @($script:modelRoot, $script:ovmsRoot, $script:logRoot)) {
    New-Item -ItemType Directory -Path $directory | Out-Null
}
foreach ($relative in @('start-27b-article.cmd', 'start-qwen3-coder-30b.cmd', 'start-qwen38-fable5-coding-27b.cmd', 'morteza89-qwen3.8-27b-int4-ov\openvino_language_model.xml', 'qwen3-coder-30b-a3b-int4-ov\openvino_model.xml', 'qwen3.8-27b-fable-5-coding-distilled-int4-ov\openvino_language_model.xml', 'qwen3-8b-int8\openvino_model.xml')) {
    $path = Join-Path $script:modelRoot $relative
    New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
    [System.IO.File]::WriteAllText($path, 'test-only sentinel; never execute')
}
foreach ($relative in @('setupvars.bat', 'ovms.exe')) {
    [System.IO.File]::WriteAllText((Join-Path $script:ovmsRoot $relative), 'test-only sentinel; never execute')
}
. ([scriptblock]::Create((Import-ControllerFunction 'Start-LocalServer')))
$script:serverProcess = $null
$script:serverReady = $false
$script:warmupReady = $false
Start-LocalServer ([pscustomobject]@{ Name = 'test local'; Profile = [pscustomobject]@{ provider = 'local'; model = '__MODEL_ID__' } })
$lines = @([System.IO.File]::ReadAllLines((Join-Path $script:logRoot 'start-local-model.cmd')))
Assert-That ($lines[0] -ceq '@echo off') 'Wrapper does not start with @echo off'
$clears = @($lines | Where-Object { $_ -ceq 'set "API_KEY="' })
Assert-That ($clears.Count -eq 1) 'Wrapper does not clear API_KEY exactly once'
$launch = @($lines | Where-Object { $_ -match '^(call |")' })
Assert-That ($launch.Count -ge 1 -and $lines.IndexOf($clears[0]) -lt $lines.IndexOf($launch[0])) 'API_KEY is not cleared before the launcher runs'
'''.replace('__MODEL_ID__', model_id))


@pytest.mark.parametrize("workflow", ["dependency-migration", "security-repair", "regression-tests"])
def test_qwen3_coder_profile_uses_local_route_and_existing_budget(workflow):
    from worker import request_options

    profile = bench.load(bench.ENGINE_ROOT / "profiles/qwen3-coder-30b.json")
    policy = bench.load(bench.ENGINE_ROOT.parent / workflow / "policy.json")
    bench.validate_profile(profile, False, False)
    options = request_options(profile, policy)
    assert options["model"] == profile["expected_returned_model"] == "qwen3-coder-30b-a3b-ov"
    assert options["max_tokens"] == 2048
    assert options["timeout"] == policy["request_timeout_seconds"]
    assert profile["inference"]["model_revision"] == "21140c68a63012da511fe50656319e00be2f6542"
    assert profile["qualified"] is False
    assert bench.api_fee(profile, []) == 0


@pytest.mark.parametrize("workflow", ["dependency-migration", "security-repair", "regression-tests"])
def test_qwen38_fable5_profile_uses_local_route_and_existing_budget(workflow):
    from worker import request_options

    profile = bench.load(bench.ENGINE_ROOT / "profiles/qwen38-fable5-coding-27b.json")
    policy = bench.load(bench.ENGINE_ROOT.parent / workflow / "policy.json")
    bench.validate_profile(profile, False, False)
    options = request_options(profile, policy)
    assert options["model"] == profile["expected_returned_model"] == "qwen38-fable5-int4"
    assert options["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert options["max_tokens"] == 2048
    assert options["timeout"] == policy["request_timeout_seconds"]
    assert profile["inference"]["model_revision"] == "6a84fb7b49812848f4541b84ae45307ad4c1fb8d"
    assert profile["qualified"] is False
    assert bench.api_fee(profile, []) == 0


@pytest.mark.parametrize("workflow", ["dependency-migration", "security-repair", "regression-tests"])
def test_astra_uses_existing_responses_adapter_and_workflow_budget(monkeypatch, workflow):
    from worker import openai_response_options

    profile = bench.load(bench.ENGINE_ROOT / "profiles/openai-astra.json")
    policy = bench.load(bench.ENGINE_ROOT.parent / workflow / "policy.json")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-credential")
    bench.validate_profile(profile, False, True)
    options = openai_response_options(profile, policy, [{"role": "system", "content": "task"}, {"role": "user", "content": "work"}])
    assert options["model"] == profile["expected_returned_model"] == "gpt-6-astra"
    assert options["reasoning"] == {"effort": "medium"}
    assert options["timeout"] == policy["request_timeout_seconds"]
    assert options["max_output_tokens"] == policy["max_output_tokens"] == 2048
    assert profile["qualified"] is False
    assert "profiles/ptl-openai-astra.private.json" in comparison_report.DEFAULT_PROFILES


@pytest.mark.parametrize("input_tokens,input_rate,cache_rate,write_rate,output_rate", [
    (272000, 10, 1, 12.5, 50),
    (272001, 20, 2, 25, 75),
])
def test_astra_fee_uses_its_own_rates(input_tokens, input_rate, cache_rate, write_rate, output_rate):
    profile = bench.load(bench.ENGINE_ROOT / "profiles/openai-astra.json")
    events = [
        {"kind": "request_start"},
        {"kind": "request_end", "usage": {"input_tokens": input_tokens, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 100, "cache_write_tokens": 400}}},
    ]
    expected = ((input_tokens - 500) * input_rate + 100 * cache_rate + 400 * write_rate + 20 * output_rate) / 1_000_000
    assert bench.api_fee(profile, events) == pytest.approx(expected)
    sol = bench.load(bench.ENGINE_ROOT / "profiles/openai.json")
    assert bench.api_fee(profile, events) != bench.api_fee(sol, events)


def test_comparison_keeps_astra_and_sol_separate(tmp_path):
    frozen = {"created_at": "same-freeze"}
    profiles = [bench.load(bench.ENGINE_ROOT / "profiles" / name) for name in ("openai.json", "openai-astra.json")]
    for profile in profiles:
        attempt = tmp_path / ("attempt-" + profile["model"])
        attempt.mkdir()
        bench.save(attempt / "freeze.json", frozen)
        bench.save(attempt / "result.json", {
            "attempt_id": attempt.name, "label": profile["label"], "provider": "openai",
            "model": profile["model"], "task_hash": "same-task", "profile_hash": profile["model"],
            "accepted": True, "mock": False, "category": "accepted",
        })
    report = comparison_report.render_report(tmp_path, frozen, [])
    for profile in profiles:
        assert f"| {profile['label']} | openai / {profile['model']} | pilot | `same-task` | 1 | 1 | 1/1 (100%)" in report


@pytest.mark.parametrize("autocrlf", ["true", "false"])
def test_regression_frozen_bytes_survive_clean_git_checkout(tmp_path, monkeypatch, autocrlf):
    git = shutil.which("git")
    assert git is not None, "Git is required to verify frozen checkout bytes"
    workspace = bench.ENGINE_ROOT.parent
    regression = workspace / "regression-tests"
    monkeypatch.setattr(bench, "ROOT", regression)
    original = bench.package_hashes()
    assert len(original) == 41
    assert {name for name in original if name.startswith("engine/")} == {
        "engine/bench.py", "engine/worker.py", "engine/requirements-runner.lock",
    }
    freeze = regression / "artifacts" / bench.load(regression / "workflow.json")["default_freeze"]
    # Engine edits stale the shared-engine entries until a new freeze is created; package bytes stay frozen.
    package_only = lambda hashes: {name: value for name, value in hashes.items() if not name.startswith("engine/")}
    if freeze.is_file():
        assert package_only(original) == package_only(bench.load(freeze)["hashes"])

    repository = tmp_path / "repository"
    repository.mkdir()
    shutil.copyfile(workspace / ".gitattributes", repository / ".gitattributes")
    paths = {
        name: Path("dependency-migration") / name.removeprefix("engine/")
        if name.startswith("engine/") else Path("regression-tests") / name
        for name in original
    }
    for relative in paths.values():
        destination = repository / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workspace / relative, destination)
    environment = {name: value for name, value in os.environ.items() if not name.upper().startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM="1")

    def run_git(*arguments):
        return subprocess.run(
            [git, "-c", f"core.autocrlf={autocrlf}", "-c", "core.safecrlf=false",
             "-c", f"core.attributesFile={os.devnull}", *arguments],
            cwd=repository, env=environment, check=True, capture_output=True,
            text=True, encoding="utf-8", timeout=30,
        )

    run_git("init", "--template=")
    run_git("add", "--", ".gitattributes", "dependency-migration", "regression-tests")
    indexed = run_git("ls-files", "-z").stdout.split("\0")
    assert set(indexed) - {""} == {".gitattributes", *(path.as_posix() for path in paths.values())}
    checkout = tmp_path / "checkout"
    assert not checkout.exists()
    run_git("checkout-index", "--all", f"--prefix={checkout.as_posix()}/")
    assert (checkout / ".gitattributes").read_bytes() == (workspace / ".gitattributes").read_bytes()
    reconstructed = {name: bench.digest(checkout / relative) for name, relative in paths.items()}
    assert reconstructed == original
    monkeypatch.setattr(bench, "ROOT", checkout / "regression-tests")
    monkeypatch.setattr(bench, "ENGINE_ROOT", checkout / "dependency-migration")
    assert bench.package_hashes() == original
    if freeze.is_file():
        assert package_only(reconstructed) == package_only(bench.load(freeze)["hashes"])


@pytest.mark.parametrize("function_name", ["prepend_scheme_if_needed", "get_auth_from_url", "urldefragauth"])
def test_regression_source_issue_rejects_alias_preserved_stub(function_name):
    source = f"""import requests.utils as utils
original = utils.{function_name}

def stub(*args, **kwargs):
    return original(*args, **kwargs)

utils.{function_name} = stub

def test_value():
    assert original('https://example.com') is not None
"""
    assert bench.regression_source_issue(ast.parse(source)) == "production_function_replacement"


def test_regression_source_issue_accepts_assertion_helpers():
    source = """from requests.utils import urldefragauth as clean_url

def check_url(value, expected):
    assert clean_url(value) == expected

def test_url():
    check_url('https://example.com/#fragment', 'https://example.com/')
"""
    tree = ast.parse(source)
    assert bench.regression_source_issue(tree) is None


def test_comparison_report_handles_missing_laptop_profile(tmp_path):
    report = comparison_report.render_report(tmp_path, {}, [tmp_path / "other-laptop.private.json"])
    assert "other-laptop.private" in report
    assert "PROFILE MISSING" in report


def test_comparison_report_preserves_partial_fault_credit(tmp_path):
    attempt = tmp_path / "attempt-partial"
    attempt.mkdir()
    frozen = {"created_at": "test"}
    bench.save(attempt / "freeze.json", frozen)
    bench.save(attempt / "result.json", {
        "attempt_id": attempt.name, "label": "local", "mock": False,
        "verification": {"faults_detected": 1, "faults_total": 2,
                         "checks": {"fault_query": True, "fault_auth": False},
                         "phase_errors": {"fault_auth": "TimeoutExpired"}},
    })
    report = comparison_report.render_report(tmp_path, frozen, [])
    assert "## Fault Detection" in report
    assert "| local | `attempt-partial` | 1/2 | auth | fault_auth |" in report


@pytest.mark.parametrize("outcome,exit_code,expected", [
    ('<failure message="assert actual == expected"/>', 1, True),
    ('<failure message="AssertionError: wrong value"/>', 1, True),
    ('<failure message="Failed: explicit pytest.fail"/>', 1, False),
    ('<error message="ImportError"/>', 1, False),
    ('<skipped/>', 1, False),
    ('', 0, False),
    ('<failure message="assert actual == expected"/>', 2, False),
])
def test_fault_detection_requires_assertion_failure(tmp_path, outcome, exit_code, expected):
    report = tmp_path / "report.xml"
    report.write_text(f'<testsuites><testsuite><testcase name="test_url[a-b]" classname="tests.test_generated">{outcome}</testcase></testsuite></testsuites>', encoding="utf-8")
    baseline = {"cases": [{"name": "test_url[a-b]", "classname": "tests.test_generated"}]}
    assert bench.fault_detected(report, exit_code, baseline, {"test_url"}) is expected
    assert not bench.fault_detected(report, exit_code, baseline, {"test_other"})
    assert not bench.fault_detected(report, exit_code, baseline, set())
    baseline["cases"][0]["name"] = "test_other"
    assert not bench.fault_detected(report, exit_code, baseline, {"test_url"})


def test_fault_credit_requires_behavioral_failing_test(tmp_path):
    report = tmp_path / "report.xml"
    report.write_text(
        '<testsuites><testsuite>'
        '<testcase name="test_hash[x]" classname="tests.test_generated"><failure message="assert digest == expected"/></testcase>'
        '<testcase name="test_cleanup[y]" classname="tests.test_generated"/>'
        '</testsuite></testsuites>', encoding="utf-8")
    baseline = {"cases": [{"name": "test_hash[x]", "classname": "tests.test_generated"}, {"name": "test_cleanup[y]", "classname": "tests.test_generated"}]}
    assert not bench.fault_detected(report, 1, baseline, {"test_cleanup"})
    assert bench.fault_detected(report, 1, baseline, {"test_hash"})


@pytest.mark.parametrize("source,expected", [
    ("def test_cleanup():\n    assert urldefragauth('u') == 'v'\n", {"test_cleanup"}),
    ("def test_cleanup():\n    assert 'v' == utils.urldefragauth('u')\n", {"test_cleanup"}),
    ("class TestUrl(unittest.TestCase):\n    def test_auth(self):\n        self.assertEqual(get_auth_from_url('u'), ('a', 'b'))\n", {"test_auth"}),
    ("def test_hash():\n    assert hashlib.sha256(source).hexdigest() == 'abc'\n", set()),
    ("def test_identity():\n    assert urldefragauth is not None\n", set()),
    ("def test_ordering():\n    assert urldefragauth('u') != 'v'\n", set()),
    ("def check():\n    assert urldefragauth('u') == 'v'\n\ndef test_cleanup():\n    check()\n", set()),
])
def test_behavioral_test_names(source, expected):
    assert bench.behavioral_test_names(ast.parse(source)) == expected


@pytest.mark.parametrize("existing", [False, True])
def test_prepare_creates_only_missing_environments_and_always_syncs(tmp_path, monkeypatch, existing):
    monkeypatch.setattr(qualify, "ROOT", tmp_path)
    commands = []
    for version in ("v1", "v2"):
        if existing:
            executable = qualify.interpreter(version)
            executable.parent.mkdir(parents=True)
            executable.touch()
            (tmp_path / f".venv-{version}" / "pyvenv.cfg").touch()

    def execute(command):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(qualify, "execute", execute)
    qualify.prepare()
    assert sum(command[:2] == ["uv", "venv"] for command in commands) == (0 if existing else 2)
    syncs = [command for command in commands if command[:3] == ["uv", "pip", "sync"]]
    assert len(syncs) == 2
    assert all("--require-hashes" in command for command in syncs)
    assert sum("-c" in command for command in commands) == (2 if existing else 0)


@pytest.mark.parametrize("complete", [False, True])
def test_prepare_preserves_invalid_existing_environment(tmp_path, monkeypatch, complete):
    monkeypatch.setattr(qualify, "ROOT", tmp_path)
    directory = tmp_path / ".venv-v1"
    directory.mkdir()
    sentinel = directory / "keep.txt"
    sentinel.write_text("preserve me", encoding="utf-8")
    if complete:
        executable = qualify.interpreter("v1")
        executable.parent.mkdir(parents=True)
        executable.touch()
        (directory / "pyvenv.cfg").touch()

    def execute(command):
        assert "-c" in command
        return subprocess.CompletedProcess(command, 1, "", "invalid interpreter")

    monkeypatch.setattr(qualify, "execute", execute)
    with pytest.raises(RuntimeError, match="Move it aside"):
        qualify.prepare()
    assert sentinel.read_text(encoding="utf-8") == "preserve me"


def test_local_route_cannot_silently_become_cloud():
    profile = bench.load(bench.ROOT / "profiles/local-8b.json")
    bench.validate_profile(profile, False, False)
    for url in ("https://example.com/v1", "http://localhost:8000/v1", "http://secret@127.0.0.1:8000/v1"):
        profile["base_url"] = url
        with pytest.raises(ValueError):
            bench.validate_profile(profile, False, False)


def test_unqualified_profile_cannot_be_scored():
    with pytest.raises(ValueError, match="qualify"):
        bench.validate_profile(bench.load(bench.ROOT / "profiles/local-8b.json"), True, False)


def test_scored_profile_requires_measured_context_limit():
    profile = bench.load(bench.ROOT / "profiles/local-8b.json")
    profile["qualified"] = True
    profile["host"].update(sku="test host", os="test OS", driver="test driver", bios="test BIOS", power_mode="Best performance")
    profile["inference"].update(runtime="OVMS", runtime_sha256="sha", model_revision="rev", export_sha256="sha", template_sha256="sha", cache_policy="warm", cold_start_seconds=1, peak_memory_gb=10, offload_evidence="measured", no_cloud_fallback_evidence="loopback")
    with pytest.raises(ValueError, match="context limit"):
        bench.validate_profile(profile, True, False)


def test_cloud_requires_opt_in_and_environment_secret(monkeypatch):
    profile = bench.load(bench.ROOT / "profiles/claude.json")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="allow-cloud"):
        bench.validate_profile(profile, False, False)
    with pytest.raises(ValueError, match="environment"):
        bench.validate_profile(profile, False, True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-not-a-credential")
    bench.validate_profile(profile, False, True)


def test_openai_requires_opt_in_and_environment_secret(monkeypatch):
    profile = bench.load(bench.ROOT / "profiles/openai.json")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="allow-cloud"):
        bench.validate_profile(profile, False, False)
    with pytest.raises(ValueError, match="environment"):
        bench.validate_profile(profile, False, True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-credential")
    bench.validate_profile(profile, False, True)


def test_openai_responses_request_uses_fixed_model_and_shared_budget():
    from types import SimpleNamespace
    from worker import openai_finish_reason, openai_response_input, openai_response_options

    profile = bench.load(bench.ROOT / "profiles/openai.json")
    policy = bench.load(bench.ROOT / "policy.json")
    messages = [
        {"role": "system", "content": "instructions"},
        {"role": "user", "content": "task"},
        {"role": "assistant", "content": "answer", "tool_calls": None, "function_call": None},
    ]
    options = openai_response_options(profile, policy, messages)
    assert options["model"] == "gpt-6.1-sol"
    assert options["instructions"] == "instructions"
    assert options["input"] == [{"role": "user", "content": "task"}, {"role": "assistant", "content": "answer"}]
    assert openai_response_input(messages) == options["input"]
    assert options["max_output_tokens"] == 2048
    assert options["reasoning"] == {"effort": "medium"}
    assert options["timeout"] == 600
    assert openai_finish_reason(SimpleNamespace(status="completed")) == "stop"
    assert openai_finish_reason(SimpleNamespace(status="incomplete", incomplete_details=SimpleNamespace(reason="max_output_tokens"))) == "length"


def test_multiple_action_blocks_execute_only_first():
    from worker import normalize_action

    response = """```mswea_bash_command
printf 'first'
```
```mswea_bash_command
printf 'second'
```"""
    normalized, count = normalize_action(response)
    assert count == 2
    assert normalized == "```mswea_bash_command\nprintf 'first'\n```"
    assert "second" not in normalized


def test_action_normalization_leaves_single_and_nonaction_text_unchanged():
    from worker import normalize_action

    single = "```mswea_bash_command\nprintf 'one'\n```"
    assert normalize_action(single) == (single, 1)
    assert normalize_action("no action") == ("no action", 0)


def test_request_settings_disclose_provider_parameters():
    from worker import request_settings

    policy = bench.load(bench.ROOT / "policy.json")
    local = request_settings(bench.load(bench.ROOT / "profiles/qwen38-fable5-coding-27b.json"), policy)
    assert local == {"provider": "local", "model": "qwen38-fable5-int4", "max_output_tokens": 2048, "temperature": 0, "sampling": "greedy", "reasoning": "disabled", "output_cap_includes_reasoning_tokens": False, "retries": 0, "api": "chat.completions"}
    thinking = request_settings({"provider": "local", "model": "m", "extra_body": {}}, dict(policy, temperature=0.7))
    assert thinking["reasoning"] == "model_default"
    assert thinking["sampling"] == "temperature"
    openai = request_settings(bench.load(bench.ROOT / "profiles/openai.json"), policy)
    assert openai == {"provider": "openai", "model": "gpt-6.1-sol", "max_output_tokens": 2048, "temperature": None, "sampling": "provider_default", "reasoning": "effort=medium", "output_cap_includes_reasoning_tokens": True, "retries": 0, "api": "responses"}
    anthropic = request_settings(bench.load(bench.ROOT / "profiles/claude.json"), policy)
    assert (anthropic["reasoning"], anthropic["api"], anthropic["temperature"], anthropic["output_cap_includes_reasoning_tokens"]) == ("model_default", "messages", 0, False)
    json.dumps([local, openai, anthropic, request_settings({"provider": "mock", "model": "offline-mock"}, policy)])


@pytest.mark.parametrize("provider", ["local", "openai"])
def test_worker_normalizes_multi_block_actions_for_every_provider(tmp_path, monkeypatch, provider):
    from types import SimpleNamespace
    import openai
    from worker import run_worker

    policy = bench.load(bench.ROOT / "policy.json")
    profile = bench.load(bench.ROOT / "profiles" / ("openai.json" if provider == "openai" else "local-8b.json"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-credential")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://169.254.0.1/hijacked")
    for key in ("MSWEA_GLOBAL_CONFIG_DIR", "MSWEA_SILENT_STARTUP", "MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT"):
        monkeypatch.setenv(key, "")
    replies = iter(["```mswea_bash_command\nprintf 'first'\n```\n```mswea_bash_command\nprintf 'second'\n```", "```mswea_bash_command\nprintf 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\\n'\n```"])
    clients = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            clients.append(kwargs)
            model = profile["expected_returned_model"]
            chat_response = lambda **options: SimpleNamespace(model=model, usage=None, id="chat", choices=[SimpleNamespace(message=SimpleNamespace(content=next(replies)), finish_reason="stop")])
            responses_response = lambda **options: SimpleNamespace(model=model, usage=None, id="resp", status="completed", output_text=next(replies))
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=chat_response))
            self.responses = SimpleNamespace(create=responses_response)

        def close(self):
            pass

    def fake_run(command, **kwargs):
        stdout = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n" if "COMPLETE_TASK" in command[-1] else "done\n"
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(subprocess, "run", fake_run)
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    (prepared / "TASK.md").write_text("task", encoding="utf-8")
    (tmp_path / "output").mkdir()
    sent = []
    connection = SimpleNamespace(send=sent.append, recv=lambda: "start", close=lambda: None)
    run_worker(connection, profile, policy, "sha256:test", "migration-agent-test", str(prepared), str(tmp_path / "output"))
    assert sent[-1]["kind"] == "finished" and sent[-1]["result"]["exit_status"] == "Submitted"
    assert clients[0]["base_url"] == profile["base_url"]
    events = [json.loads(line) for line in (tmp_path / "output/events.jsonl").read_text(encoding="utf-8").splitlines()]
    responses = [event for event in events if event["kind"] == "request_end"]
    assert responses[0]["content"].count("mswea_bash_command") == 2
    assert responses[0]["normalized_action_blocks"] == 2
    assert responses[0]["agent_content"] == "```mswea_bash_command\nprintf 'first'\n```"
    assert "normalized_action_blocks" not in responses[1]
    assert [event["command"] for event in events if event["kind"] == "tool_start"][0] == "printf 'first'"


def test_provider_error_diagnostics_keep_status_and_redact_key():
    from types import SimpleNamespace
    from worker import request_error_details

    error = SimpleNamespace(status_code=400, code="bad_request", param="input", request_id="req_test", message="invalid key sk-proj-123456789012345678901234")
    details = request_error_details(error)
    assert details["status_code"] == 400
    assert details["code"] == "bad_request"
    assert details["param"] == "input"
    assert "sk-proj-123456789012345678901234" not in details["message"]


def test_openai_fee_accounts_for_cached_reads_writes_and_long_context():
    profile = bench.load(bench.ROOT / "profiles/openai.json")
    card = profile["rate_card"]
    events = [
        {"kind": "request_start"},
        {"kind": "request_end", "usage": {"input_tokens": 1000, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 100, "cache_write_tokens": 400}}},
    ]
    assert bench.api_fee(profile, events) == pytest.approx(0.00221)
    long_events = [
        {"kind": "request_start"},
        {"kind": "request_end", "usage": {"input_tokens": card["long_context_threshold_tokens"] + 1, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}}},
    ]
    expected = (card["long_context_threshold_tokens"] + 1) * 4 / 1_000_000 + 20 * 15 / 1_000_000
    assert bench.api_fee(profile, long_events) == pytest.approx(expected)


def test_submission_filter_keeps_only_permitted_files(tmp_path):
    exported = tmp_path / "exported"
    shutil.copytree(bench.ROOT / "starter", exported, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    for relative in bench.ALLOWED:
        shutil.copyfile(bench.ROOT / "reference" / relative, exported / relative)
    destination = tmp_path / "submission"
    assert bench.collect_submission(exported, destination) == []
    assert sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()) == sorted(bench.ALLOWED)


def test_submission_filter_preserves_partial_allowed_files_and_reports_extra_files(tmp_path):
    exported = tmp_path / "exported"
    shutil.copytree(bench.ROOT / "starter", exported)
    for relative in bench.ALLOWED:
        (exported / relative).unlink(missing_ok=True)
    (exported / "app").mkdir(exist_ok=True)
    (exported / "app/schemas.py").write_text("partial", encoding="utf-8")
    (exported / "log.txt").write_text("unexpected", encoding="utf-8")
    destination = tmp_path / "submission"
    violations = bench.collect_submission(exported, destination)
    assert (destination / "app/schemas.py").read_text(encoding="utf-8") == "partial"
    assert sorted(violations) == ["unpermitted change: log.txt"]


@pytest.mark.parametrize("filename", ["TASK.md", "tests/test_visible.py", "conftest.py", "requirements.txt"])
def test_submission_rejects_unpermitted_edits(tmp_path, filename):
    exported = tmp_path / "exported"
    shutil.copytree(bench.ROOT / "starter", exported)
    (exported / filename).write_text("tampered", encoding="utf-8")
    assert any("unpermitted" in problem for problem in bench.collect_submission(exported, tmp_path / "submission"))


@pytest.mark.parametrize("xml,accepted", [("<testsuites/>", False), ('<testsuites><testsuite><testcase name="ok"/></testsuite></testsuites>', True), ('<testsuites><testsuite><testcase name="skip"><skipped/></testcase></testsuite></testsuites>', False), ('<testsuites><testsuite><testcase name="fail"><failure/></testcase></testsuite></testsuites>', False)])
def test_junit_requires_executed_passing_tests(tmp_path, xml, accepted):
    path = tmp_path / "report.xml"
    path.write_text(xml, encoding="utf-8")
    assert bench.junit_passed(path) is accepted


def test_junit_summary_retains_named_partial_results(tmp_path):
    path = tmp_path / "report.xml"
    path.write_text('<testsuites><testsuite><testcase name="ok"/><testcase name="bad"><failure/></testcase><testcase name="collection"><error/></testcase><testcase name="skip"><skipped/></testcase></testsuite></testsuites>', encoding="utf-8")
    summary = bench.junit_summary(path)
    assert {key: value for key, value in summary.items() if key != "cases"} == {"total": 4, "passed": 1, "failed": 1, "errors": 1, "skipped": 1}
    assert summary["cases"][0] == {"name": "ok", "classname": "", "status": "passed"}


@pytest.mark.parametrize("source,expected", [
    ("def test_contract():\n    assert response.status_code == 201", True),
    ("def test_rejects_invalid():\n    with pytest.raises(ValueError):\n        parse('bad')", True),
    ("class TestContract:\n    def test_response(self):\n        self.assertEqual(actual, expected)", True),
    ("def helper():\n    assert response.status_code == 201", False),
    ("def test_placeholder():\n    assert True", False),
    ("def test_placeholder():\n    assert 1 == 1", False),
    ("def test_placeholder():\n    assert 'a' != 'b' and 2 > 1", True),
    ("def test_value():\n    assert total == 1", True),
    ("def test_placeholder():\n    pass", False),
])
def test_generated_test_assertion_detection(source, expected):
    assert bench.has_test_assertion(bench.ast.parse(source)) is expected


def test_truncated_model_response_is_explained_to_agent():
    from minisweagent.exceptions import FormatError
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel
    import litellm

    policy = bench.load(bench.ROOT / "policy.json")
    model = LitellmTextbasedModel(model_name="offline", format_error_template=policy["format_error_template"])
    response = litellm.ModelResponse(model="offline", choices=[{"message": {"role": "assistant", "content": "partial"}, "finish_reason": "length"}])
    with pytest.raises(FormatError) as error:
        model._parse_actions(response)
    assert "truncated at the output limit" in error.value.messages[0]["content"]


@pytest.mark.parametrize("contract_passes", [True, False])
@pytest.mark.parametrize("source,issue", [("", "missing_regression_assertions"), ("def broken(", "invalid_test_source"), (None, "missing_test_file")])
def test_verification_evaluates_contract_despite_missing_or_broken_tests(tmp_path, monkeypatch, source, issue, contract_passes):
    submission = tmp_path / "submission"
    (submission / "tests").mkdir(parents=True)
    if source is not None:
        (submission / "tests/test_generated.py").write_text(source, encoding="utf-8")
    phases = []
    containers = {}

    def fake_docker(*arguments, **kwargs):
        if arguments[0] == "run":
            containers[arguments[arguments.index("--name") + 1]] = "contract" if any("dst=/grader," in str(argument) for argument in arguments) else "generated"
            return subprocess.CompletedProcess(arguments, 0, "", "")
        phase = containers.get(arguments[1])
        if "pytest" in arguments:
            phases.append(phase)
            assert arguments[2:5] == ("python", "-m", "pytest") and arguments[5:7] == ("-W", "error::pydantic.PydanticDeprecatedSince20")
        failed = '<testcase name="receipt"><failure/></testcase>' if phase == "generated" or not contract_passes else '<testcase name="receipt"/>'
        text = f'<testsuites><testsuite><testcase name="health"/>{failed}</testsuite></testsuites>'
        return subprocess.CompletedProcess(arguments, 0, text, "")

    monkeypatch.setattr(bench, "docker", fake_docker)
    result = bench.verify(submission, tmp_path, "image", {"container_cpus": 2, "container_memory": "2g", "verifier_timeout_seconds": 60})
    assert phases == (["contract"] if source is None else ["contract", "generated"])
    assert not result["accepted"]
    assert result["regression_issue"] == issue
    # A failing contract phase outranks the generated-test issue in the reported category.
    assert result["category"] == (issue if contract_passes else "verification_failed")
    assert result["checks"]["contract"] is contract_passes
    assert result["test_results"]["contract"]["passed"] == (2 if contract_passes else 1)
    if source is None:
        assert result["phase_errors"]["generated"] == "MissingGeneratedTestFile"


@pytest.mark.parametrize("message,expected", [
    ("assert decode(token) is None", True),
    ("AssertionError: vulnerable baseline accepted the token", True),
    ("Failed: DID NOT RAISE InvalidKeyError", True),
    ("TypeError: Expected an Ed25519 key", True),
    ("ImportError: cannot import name 'helper'", False),
    ("ModuleNotFoundError: No module named 'jwt.helpers'", False),
    ("AttributeError: module has no attribute", False),
    ("NameError: name 'is_pem_format' is not defined", False),
])
def test_negative_control_requires_behavioral_failure(tmp_path, monkeypatch, message, expected):
    root = tmp_path / "workflow"
    starter = root / "starter"
    (starter / "tests").mkdir(parents=True)
    (root / "grader").mkdir()
    (starter / "tests/test_generated.py").write_text("", encoding="utf-8")
    (starter / "jwt.py").write_text("def decode(token):\n    return token\n", encoding="utf-8")
    workflow = {"allowed_files": ["jwt.py", "tests/test_generated.py"], "preserve_baseline_files": True, "generated_test_path": "tests/test_generated.py", "contract_tests": ["test_security.py"], "require_generated_test_to_fail_on_baseline": True, "pydantic_warnings_as_errors": False}
    monkeypatch.setattr(bench, "ROOT", root)
    monkeypatch.setattr(bench, "WORKFLOW", workflow)
    monkeypatch.setattr(bench, "ALLOWED", workflow["allowed_files"])
    submission = tmp_path / "submission"
    shutil.copytree(starter, submission)
    (submission / "tests/test_generated.py").write_text("from jwt import decode\n\ndef test_fix():\n    assert decode('t') is None\n", encoding="utf-8")
    containers = {}

    def fake_docker(*arguments, **kwargs):
        if arguments[0] == "run":
            mounts = [arguments[index + 1] for index, argument in enumerate(arguments) if argument == "--mount"]
            phase = "negative_control" if any("negative-control" in mount for mount in mounts) else "contract" if any("dst=/grader," in mount for mount in mounts) else "generated"
            containers[arguments[arguments.index("--name") + 1]] = phase
            return subprocess.CompletedProcess(arguments, 0, "", "")
        if arguments[0] != "exec":
            return subprocess.CompletedProcess(arguments, 0, "", "")
        phase = containers[arguments[1]]
        if "pytest" in arguments:
            return subprocess.CompletedProcess(arguments, 1 if phase == "negative_control" else 0, "", "")
        outcome = f'<failure message="{message}"/>' if phase == "negative_control" else ""
        return subprocess.CompletedProcess(arguments, 0, f'<testsuites><testsuite><testcase name="test_fix">{outcome}</testcase></testsuite></testsuites>', "")

    monkeypatch.setattr(bench, "docker", fake_docker)
    result = bench.verify(submission, tmp_path / "output", "image", {"container_cpus": 2, "container_memory": "2g", "verifier_timeout_seconds": 60})
    assert sorted(containers.values()) == ["contract", "generated", "negative_control"]
    assert result["checks"]["negative_control"] is expected
    assert result["accepted"] is expected


@pytest.fixture
def configured_regression_verifier(tmp_path, monkeypatch):
    root = tmp_path / "workflow"
    starter = root / "starter"
    (starter / "tests").mkdir(parents=True)
    (root / "grader").mkdir()
    production = "def urldefragauth(url):\n    return 2 + 3\n"
    generated_path = "tests/test_generated.py"
    (starter / "production.py").write_text(production, encoding="utf-8")
    (starter / generated_path).write_text("", encoding="utf-8")
    (root / "grader/test_witnesses.py").write_text("def test_contract():\n    assert True\n", encoding="utf-8")
    workflow = {
        "allowed_files": [generated_path],
        "preserve_baseline_files": True,
        "generated_test_path": generated_path,
        "contract_tests": ["test_witnesses.py"],
        "pydantic_warnings_as_errors": False,
        "fault_variants": [
            {"name": "first", "path": "production.py", "before": "2 + 3", "after": "0 + 3"},
            {"name": "second", "path": "production.py", "before": "2 + 3", "after": "2 + 0"},
        ],
    }
    monkeypatch.setattr(bench, "ROOT", root)
    monkeypatch.setattr(bench, "WORKFLOW", workflow)
    monkeypatch.setattr(bench, "ALLOWED", workflow["allowed_files"])
    submission = tmp_path / "submission"
    shutil.copytree(starter, submission)
    # Fault credit (R1) needs the equality assertion inside the test function itself; helpers may still raise.
    source = "from production import urldefragauth\n\ndef fail_helper(message):\n    raise AssertionError(message)\n\ndef test_value():\n    if urldefragauth('u') is None:\n        fail_helper('missing')\n    assert urldefragauth('u') == 5\n"
    (submission / generated_path).write_text(source, encoding="utf-8")
    (submission / "production.py").write_text("def urldefragauth(url):\n    return 999\n", encoding="utf-8")
    (submission / "submission_only.py").write_text("tampered = True\n", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    containers = {}
    executed = []
    cleaned = []
    outcomes = {}
    case_name = "test_value[u]"
    snapshot = {path.relative_to(starter): path.read_bytes() for path in starter.rglob("*") if path.is_file()}

    def fake_docker(*arguments, **kwargs):
        if arguments[0] == "run":
            name = arguments[arguments.index("--name") + 1]
            mounts = [arguments[index + 1] for index, argument in enumerate(arguments) if argument == "--mount"]
            task_mount = next(mount for mount in mounts if "dst=/task," in mount)
            task = Path(task_mount.split("src=", 1)[1].split(",dst=", 1)[0])
            phase = task.name if task.parent == output else "contract" if any("dst=/grader," in mount for mount in mounts) else "generated"
            assert phase in {"contract", "generated", "fault_first", "fault_second"}
            assert len(mounts) == (2 if phase == "contract" else 1)
            assert any("dst=/grader," in mount for mount in mounts) is (phase == "contract")
            if phase == "contract":
                assert f"type=bind,src={root / 'grader'},dst=/grader,readonly" in mounts
            if phase.startswith("fault_"):
                fault = next(fault for fault in workflow["fault_variants"] if phase == "fault_" + fault["name"])
                assert (task / "production.py").read_text(encoding="utf-8") == production.replace(fault["before"], fault["after"])
                expected = (submission / generated_path).read_bytes() if (submission / generated_path).exists() else b""
                assert (task / generated_path).read_bytes() == expected
                assert {path.relative_to(task) for path in task.rglob("*") if path.is_file()} == set(snapshot)
            else:
                assert task == submission
            containers[name] = phase
        elif arguments[0] == "exec":
            phase = containers[arguments[1]]
            outcome = outcomes.get(phase, "failure" if phase.startswith("fault_") else "pass")
            if "pytest" in arguments:
                executed.append(phase)
                assert arguments[2:5] == ("python", "-m", "pytest")
                warning_index = arguments.index("-W") if "-W" in arguments else None
                assert (warning_index is not None) is bool(workflow["pydantic_warnings_as_errors"])
                if warning_index is not None:
                    assert warning_index > arguments.index("pytest") and arguments[warning_index + 1] == "error::pydantic.PydanticDeprecatedSince20"
                tests = arguments[(warning_index + 2) if warning_index is not None else arguments.index("pytest") + 1:arguments.index("-q")]
                assert tests == (("/grader/test_witnesses.py",) if phase == "contract" else ("/task/" + generated_path,))
                assert kwargs == {"timeout": 17, "check": False}
                if outcome == "timeout":
                    raise subprocess.TimeoutExpired("mock-docker", 17)
                return subprocess.CompletedProcess(arguments, 0 if outcome == "pass" else 1, "synthetic pytest output", "")
            assert arguments[2:] == ("cat", "/tmp/report.xml")
            tags = {
                "pass": "",
                "failure": '<failure message="assert urldefragauth(&apos;u&apos;) == 5"/>',
                "skip": "<skipped/>",
                "explicit_failure": '<failure message="Failed: explicit pytest.fail"/>',
                "error": '<error message="ImportError"/>',
            }
            xml = "<malformed" if outcome == "malformed" else f'<testsuites><testsuite><testcase classname="tests.test_generated" name="{case_name}">{tags[outcome]}</testcase></testsuite></testsuites>'
            return subprocess.CompletedProcess(arguments, 0, xml, "")
        else:
            assert arguments[0] == "rm"
            cleaned.append(containers[arguments[-1]])
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(bench, "docker", fake_docker)

    def verify():
        result = bench.verify(submission, output, "mock-image", {"container_cpus": 2, "container_memory": "2g", "verifier_timeout_seconds": 17})
        assert {path.relative_to(starter): path.read_bytes() for path in starter.rglob("*") if path.is_file()} == snapshot
        assert cleaned == executed
        return result

    return submission / generated_path, outcomes, executed, verify


def test_configured_regression_verify_isolates_faults_and_allows_helper_raise(configured_regression_verifier):
    generated, outcomes, executed, verify = configured_regression_verifier
    result = verify()
    assert executed == ["contract", "generated", "fault_first", "fault_second"]
    assert result["accepted"]
    assert result["category"] == "accepted"
    assert result["faults_total"] == result["faults_detected"] == 2
    assert result["checks"] == {phase: True for phase in executed}
    assert result["test_results"]["contract"]["passed"] == 1
    assert result["test_results"]["generated"]["passed"] == 1
    for phase in ("fault_first", "fault_second"):
        assert result["test_results"][phase]["failed"] == 1
    assert result["phase_errors"] == {}
    assert result["cleanup_errors"] == []


def test_configured_regression_verify_accepts_unittest_assert_methods(configured_regression_verifier):
    generated, outcomes, executed, verify = configured_regression_verifier
    generated.write_text("import unittest\nfrom production import urldefragauth\n\nclass TestValue(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(urldefragauth('u'), 5)\n", encoding="utf-8")
    result = verify()
    assert result["accepted"]
    assert result["regression_issue"] is None
    assert result["faults_detected"] == 2


def test_configured_regression_verify_denies_fault_credit_without_behavioral_failure(configured_regression_verifier):
    generated, outcomes, executed, verify = configured_regression_verifier
    generated.write_text("from production import urldefragauth\n\ndef test_value():\n    assert isinstance(urldefragauth('u'), int)\n", encoding="utf-8")
    result = verify()
    assert executed == ["contract", "generated", "fault_first", "fault_second"]
    assert not result["accepted"]
    assert result["regression_issue"] is None
    assert result["category"] == "verification_failed"
    assert result["checks"]["generated"]
    assert result["faults_detected"] == 0


def test_verifier_passes_pydantic_warning_filter_to_pytest(configured_regression_verifier):
    generated, outcomes, executed, verify = configured_regression_verifier
    bench.WORKFLOW["pydantic_warnings_as_errors"] = True
    result = verify()
    assert executed == ["contract", "generated", "fault_first", "fault_second"]
    assert result["accepted"]


@pytest.mark.parametrize("source,issue", [
    (None, "missing_test_file"),
    ("def broken(", "invalid_test_source"),
    ("def test_empty():\n    pass\n", "missing_regression_assertions"),
    ("def test_trivial():\n    assert 1 == 1\n", "missing_regression_assertions"),
    ("def check_value():\n    assert urldefragauth('u') == 5\n\ndef test_value():\n    check_value()\n", "missing_regression_assertions"),
    ("def test_value():\n    assert urldefragauth('u') == 5\n    raise AssertionError('artificial')\n", "artificial_test_exception"),
    ("import pytest\n\n@pytest.mark.xfail\ndef test_value():\n    assert urldefragauth('u') == 5\n", "xfail_marker_not_permitted"),
    ("from pytest import xfail\n\n@xfail\ndef test_value():\n    assert urldefragauth('u') == 5\n", "xfail_marker_not_permitted"),
    ("import inspect\n\ndef test_value():\n    assert 'rsplit' in inspect.getsource(urldefragauth)\n", "source_introspection"),
    ("def test_value():\n    assert open('production.py').read() != ''\n", "source_introspection"),
    ("import sys\n\ndef test_value():\n    assert sys.modules['production'].urldefragauth('u') == 5\n", "source_introspection"),
    ("def test_value():\n    assert urldefragauth.__code__.co_consts\n", "source_introspection"),
    ("from pathlib import Path\n\ndef test_value():\n    assert Path('production.py').read_text() != ''\n", "source_introspection"),
    ("import hashlib\n\ndef test_value():\n    assert hashlib.sha256(b'x').hexdigest() == 'y'\n", "source_introspection"),
    ("def test_value():\n    assert eval('urldefragauth(\"u\")') == 5\n", "source_introspection"),
    ("import importlib\n\ndef test_value():\n    assert importlib.import_module('production').urldefragauth('u') == 5\n", "source_introspection"),
])
def test_configured_regression_verify_rejects_invalid_generated_source(configured_regression_verifier, source, issue):
    generated, outcomes, executed, verify = configured_regression_verifier
    if source is None:
        generated.unlink()
    else:
        generated.write_text(source, encoding="utf-8")
    result = verify()
    assert not result["accepted"]
    assert result["category"] == result["regression_issue"] == issue
    assert result["checks"]["contract"]
    assert not result["checks"]["generated"]
    assert result["faults_total"] == 2
    if source is None:
        assert executed == ["contract"]
        assert result["faults_detected"] == 0
        assert result["phase_errors"] == {phase: "MissingGeneratedTestFile" for phase in ("generated", "fault_first", "fault_second")}


@pytest.mark.parametrize("phase,outcome,error", [
    ("fault_first", "pass", None),
    ("fault_first", "skip", None),
    ("fault_first", "explicit_failure", None),
    ("fault_first", "error", None),
    ("fault_first", "timeout", "TimeoutExpired"),
    ("fault_first", "malformed", "ParseError"),
    ("generated", "skip", None),
    ("generated", "timeout", "TimeoutExpired"),
    ("generated", "malformed", "ParseError"),
    ("contract", "failure", None),
])
def test_configured_regression_verify_requires_real_detection(configured_regression_verifier, phase, outcome, error):
    generated, outcomes, executed, verify = configured_regression_verifier
    outcomes[phase] = outcome
    result = verify()
    assert executed == ["contract", "generated", "fault_first", "fault_second"]
    assert not result["accepted"]
    assert result["category"] == "verification_failed"
    assert not result["checks"][phase]
    assert result["faults_total"] == 2
    assert result["faults_detected"] == (0 if phase == "generated" else 2 if phase == "contract" else 1)
    assert result["phase_errors"] == ({phase: error} if error else {})


def test_submission_policy_violation_retains_protected_results(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "docker", lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "", ""))
    monkeypatch.setattr(bench, "collect_submission", lambda *args: ["unpermitted change: log.txt"])
    monkeypatch.setattr(bench, "verify", lambda *args: {"accepted": True, "category": "accepted", "test_results": {"contract": {"passed": 38}}})
    result = bench.check_submission("task", tmp_path / "checkpoint", "image", {})
    assert not result["accepted"]
    assert result["category"] == "submission_policy_violation"
    assert result["violations"] == ["unpermitted change: log.txt"]
    assert result["test_results"]["contract"]["passed"] == 38


def test_cloud_fee_counts_cache_categories_and_incomplete_calls():
    profile = {"provider": "anthropic", "rate_card": {"input_per_million": 3, "output_per_million": 15, "cache_read_per_million": 0.3, "cache_write_5m_per_million": 3.75, "cache_write_1h_per_million": 6}}
    usage = {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 50, "cache_creation_input_tokens": 30, "cache_creation": {"ephemeral_5m_input_tokens": 20, "ephemeral_1h_input_tokens": 10}}
    events = [{"kind": "request_start"}, {"kind": "request_end", "usage": usage}]
    assert bench.api_fee(profile, events) == pytest.approx(0.00075)
    # A request still in flight at cutoff has no usage, so completed fees are still summed.
    assert bench.api_fee(profile, events + [{"kind": "request_start"}]) == pytest.approx(0.00075)
    assert bench.api_fee(profile, events + [{"kind": "request_start"}, {"kind": "request_end", "usage": None}]) is None
    usage["cache_creation_input_tokens"] = 40
    assert bench.api_fee(profile, events) is None
    assert bench.api_fee({"provider": "local"}, []) == 0


def test_openai_fee_sums_completed_requests_when_one_is_in_flight():
    profile = bench.load(bench.ROOT / "profiles/openai.json")
    completed = {"kind": "request_end", "usage": {"input_tokens": 1000, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 100, "cache_write_tokens": 400}}}
    events = [{"kind": "request_start"}, completed, {"kind": "request_start"}]
    assert bench.api_fee(profile, events) == pytest.approx(0.00221)
    assert bench.api_fee(profile, events + [{"kind": "request_end", "usage": {"input_tokens": 5}}]) is None


def test_cleanup_errors_are_recordable(monkeypatch):
    def failing_docker(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", 60)

    monkeypatch.setattr(bench, "docker", failing_docker)
    assert bench.cleanup_container("test") == "TimeoutExpired"


def test_no_success_has_undefined_cost_per_acceptance(tmp_path):
    output = tmp_path / "attempt-one"
    output.mkdir()
    settings = {"provider": "local", "model": "m", "max_output_tokens": 2048, "temperature": 0, "sampling": "greedy", "reasoning": "disabled", "output_cap_includes_reasoning_tokens": False, "retries": 0, "api": "chat.completions"}
    bench.save(output / "result.json", {"task_hash": "task", "profile_hash": "profile", "label": "test", "scored": True, "mock": False, "accepted": False, "api_fee_usd": 0, "category": "deadline", "request_settings": settings})
    row = bench.report(tmp_path)[0]
    assert row["attempts"] == 1
    assert row["api_fee_per_accepted_usd"] is None
    assert row["accepted_within_budget"] is None
    assert row["request_settings"] == settings


def test_saved_profiles_and_agent_frontmatter():
    import yaml

    for path in (bench.ROOT / "profiles").glob("*.json"):
        profile = bench.load(path)
        assert "api_key" not in profile
    content = (bench.ROOT.parent / ".github/agents/workflow-author.agent.md").read_text(encoding="utf-8")
    header = yaml.safe_load(content.split("---", 2)[1])
    assert header["description"]
    assert "model" not in header


@pytest.mark.parametrize("preliminary_steps", [0, 25])
def test_pinned_mini_agent_text_loop(tmp_path, monkeypatch, preliminary_steps):
    monkeypatch.setenv("MSWEA_GLOBAL_CONFIG_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT", "1")
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.docker import DockerEnvironment
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel
    import litellm

    class OfflineModel(LitellmTextbasedModel):
        calls = 0

        def _query(self, messages, **kwargs):
            self.calls += 1
            if self.calls <= preliminary_steps:
                return litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": "```mswea_bash_command\nprintf 'progress\\n'\n```"}, "finish_reason": "stop"}])
            return litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": "```mswea_bash_command\nprintf 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\\nchecked\\n'\n```"}, "finish_reason": "stop"}])

        def _calculate_cost(self, response):
            return {"cost": 0.0}

    class OfflineEnvironment(DockerEnvironment):
        def _start_container(self):
            self.container_id = None

        def execute(self, action, **kwargs):
            assert action["command"].startswith("printf")
            if "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" not in action["command"]:
                return {"output": "progress", "returncode": 0, "exception_info": ""}
            self._check_finished({"output": "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\nchecked\n", "returncode": 0})

    policy = bench.load(bench.ROOT / "policy.json")
    agent = DefaultAgent(OfflineModel(model_name="offline", cost_tracking="ignore_errors"), OfflineEnvironment(image="unused"), system_template=policy["system_template"], instance_template=policy["instance_template"], step_limit=policy["step_limit"], cost_limit=0)
    assert agent.run("check the loop")["exit_status"] == "Submitted"
    assert agent.n_calls == preliminary_steps + 1


def test_actual_runner_matches_lock():
    assert bench.runner_fingerprint()["packages"]["mini-swe-agent"] == "2.4.6"


def test_interrupted_request_span_is_counted_once():
    events = [{"kind": "request_start", "at": 10}, {"kind": "request_end", "at": 20}, {"kind": "request_error", "at": 21}, {"kind": "request_start", "at": 30}]
    assert bench.observed_span_seconds(events, "request", 35) == 15


@pytest.mark.parametrize("deadline,unlimited,worker_error", [(False, False, False), (False, False, True), (True, False, False), (False, True, False)])
def test_supervisor_stops_worker_before_verification_and_retains_cleanup_error(tmp_path, monkeypatch, deadline, unlimited, worker_error):
    real_root = bench.ROOT
    shutil.copytree(real_root / "starter", tmp_path / "starter")
    policy = bench.load(real_root / "policy.json")
    policy["deadline_seconds"] = None if unlimited else 600
    bench.save(tmp_path / "policy.json", policy)
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setattr(bench, "ENGINE_ROOT", tmp_path)
    monkeypatch.setattr(bench, "image_id", lambda image: "sha256:test")
    monkeypatch.setattr(bench, "runner_fingerprint", lambda: {"python": "test"})
    monkeypatch.setattr(bench, "package_hashes", lambda: {})
    monkeypatch.setattr(bench.time, "perf_counter", lambda: 805 if unlimited else (705 if deadline else 150))
    actions = []

    class Pipe:
        messages = iter([{"kind": "ready"}, {"kind": "started", "at": 100}, {"kind": "error", "at": 140, "error_type": "RuntimeError"} if worker_error else {"kind": "finished", "at": 800 if unlimited else 140, "result": {"exit_status": "Submitted"}}])
        polls = 0

        def poll(self, timeout):
            self.polls += 1
            return not (deadline and self.polls == 3)

        def recv(self):
            return next(self.messages)

        def send(self, message):
            pass

        def close(self):
            pass

    class Process:
        pid = 1
        alive = True

        def start(self):
            pass

        def is_alive(self):
            return self.alive

        def terminate(self):
            actions.append("terminate")
            self.alive = False

        def join(self, timeout):
            pass

    class Context:
        def Pipe(self):
            return Pipe(), Pipe()

        def Process(self, **kwargs):
            return Process()

    def fake_docker(*arguments, **kwargs):
        if arguments[0] == "pause":
            actions.append("pause")
        elif arguments[0] == "cp":
            exported = Path(arguments[2])
            shutil.copytree(real_root / "starter", exported, dirs_exist_ok=True)
            for relative in bench.ALLOWED:
                shutil.copyfile(real_root / "reference" / relative, exported / relative)
        elif arguments[0] == "rm":
            raise subprocess.TimeoutExpired("docker", 60)
        elif arguments[0] == "volume":
            return subprocess.CompletedProcess(arguments, 0)

    def fake_verify(*args):
        actions.append("verify")
        return {"accepted": True, "category": "accepted"}

    monkeypatch.setattr(bench.multiprocessing, "get_context", lambda mode: Context())
    monkeypatch.setattr(bench, "docker", fake_docker)
    monkeypatch.setattr(bench, "verify", fake_verify)
    result_code = bench.run_attempt({"label": "unit", "provider": "local"}, {"image": "test", "hashes": {}}, False)
    result = bench.load(next((tmp_path / "artifacts").glob("attempt-*/result.json")))
    assert actions[:3] == ["pause", "terminate", "verify"]
    assert result["cleanup_error"] == "TimeoutExpired"
    assert result["accepted"]
    # Budget credit needs a real submission; deadline and error stops are evaluated but not "within budget".
    assert result["accepted_within_budget"] is (not deadline and not worker_error)
    assert result["request_settings"]["provider"] == "local"
    assert result["request_settings"]["api"] == "chat.completions"
    assert result["api_fee_incomplete"] is False
    assert "snapshot" not in result
    assert not (tmp_path / "artifacts" / "active-run.json").exists()
    assert result_code == 0
    if deadline:
        assert result["exit_status"] == "deadline"
        assert result["verification"]["accepted"]
    if worker_error:
        assert result["exit_status"] == "error"
        assert result["accepted"]


def test_active_run_lock_is_shared_per_pc(tmp_path, monkeypatch):
    engine = tmp_path / "engine"
    package = tmp_path / "package"
    engine.mkdir()
    package.mkdir()
    monkeypatch.setattr(bench, "ENGINE_ROOT", engine)
    monkeypatch.setattr(bench, "ROOT", package)
    lock = engine / "artifacts" / "active-run.json"
    seen = []
    monkeypatch.setattr(bench, "_run_attempt", lambda *args: seen.append(json.loads(lock.read_text(encoding="utf-8"))) or 0)
    assert bench.run_attempt({}, {}, False) == 0
    assert seen[0]["pid"] == os.getpid()
    assert not (package / "artifacts").exists()
    assert not lock.exists()
    lock.write_text(json.dumps({"pid": 1}), encoding="utf-8")
    monkeypatch.setattr(bench, "ROOT", tmp_path / "other-package")
    with pytest.raises(RuntimeError, match="per PC"):
        bench.run_attempt({}, {}, False)
    assert len(seen) == 1


@pytest.mark.parametrize("mode", ["exported", "failed", "missing"])
def test_interrupted_attempt_snapshots_partial_work_without_verification(tmp_path, monkeypatch, mode):
    real_root = bench.ROOT
    shutil.copytree(real_root / "starter", tmp_path / "starter")
    shutil.copyfile(real_root / "policy.json", tmp_path / "policy.json")
    monkeypatch.setattr(bench, "ROOT", tmp_path)
    monkeypatch.setattr(bench, "ENGINE_ROOT", tmp_path)
    monkeypatch.setattr(bench, "image_id", lambda image: "sha256:test")
    monkeypatch.setattr(bench, "runner_fingerprint", lambda: {"python": "test"})
    monkeypatch.setattr(bench, "package_hashes", lambda: {})
    monkeypatch.setattr(bench, "verify", lambda *args: pytest.fail("Interrupted attempts must not be verified"))
    commands = []

    class Pipe:
        def poll(self, timeout):
            return False

        def send(self, message):
            pass

        def close(self):
            pass

    class Process:
        pid = 1

        def start(self):
            pass

        def is_alive(self):
            return False

        def join(self, timeout):
            pass

    class Context:
        def Pipe(self):
            return Pipe(), Pipe()

        def Process(self, **kwargs):
            return Process()

    def fake_docker(*arguments, **kwargs):
        commands.append(arguments[:2])
        if arguments[:2] == ("container", "inspect"):
            return subprocess.CompletedProcess(arguments, 1 if mode == "missing" else 0, "", "")
        if arguments[0] == "cp":
            if mode == "failed":
                raise subprocess.TimeoutExpired("docker", 60)
            shutil.copytree(real_root / "starter", Path(arguments[2]), dirs_exist_ok=True)
            (Path(arguments[2]) / "app/schemas.py").write_text("partial = True\n", encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 0, "", "")

    monkeypatch.setattr(bench.multiprocessing, "get_context", lambda mode: Context())
    monkeypatch.setattr(bench, "docker", fake_docker)
    assert bench.run_attempt({"label": "unit", "provider": "local"}, {"image": "test", "hashes": {}}, False) == 1
    output = next((tmp_path / "artifacts").glob("attempt-*"))
    result = bench.load(output / "result.json")
    assert result["category"] == "RuntimeError"
    assert not result["accepted"] and not result["accepted_within_budget"]
    assert result["snapshot"] == {"exported": "exported", "failed": "failed:TimeoutExpired", "missing": None}[mode]
    assert any(command[0] == "pause" for command in commands) is (mode != "missing")
    assert (output / "submission/app/schemas.py").is_file() is (mode == "exported")
    if mode == "exported":
        assert (output / "submission/app/schemas.py").read_text(encoding="utf-8") == "partial = True\n"
    assert commands[-2:] == [("rm", "-f"), ("volume", "rm")]


def test_ten_minute_policy_and_after_work_evaluation():
    from worker import render_system_template, request_options

    policy = bench.load(bench.ROOT / "policy.json")
    assert policy["deadline_seconds"] == 600
    assert policy["step_limit"] == 0
    assert policy["max_conversation_characters"] is None
    assert "reference_range_seconds" not in policy
    assert "success_cutoff_seconds" not in policy
    assert "600 seconds total" in render_system_template(policy)
    assert "stops at 600 seconds" in render_system_template(policy)
    assert "truncated at the output limit" in policy["format_error_template"]
    task = (bench.ROOT / "starter/TASK.md").read_text(encoding="utf-8")
    assert "600 seconds" in task
    assert "Their results are not returned for further repairs" in task
    for filename in ("local-8b.json", "article-27b.json", "claude.json", "openai.json"):
        assert request_options(bench.load(bench.ROOT / "profiles" / filename), policy)["timeout"] == 600


def test_deadline_does_not_accept_buffered_messages_after_cutoff(monkeypatch):
    monkeypatch.setattr(bench.time, "perf_counter", lambda: 701)

    class Connection:
        def poll(self, timeout):
            pytest.fail("Do not receive another action after the deadline")

    assert bench.wait_for_worker(Connection(), 100, 600, lambda: pytest.fail("No in-loop verification")) == {"kind": "deadline", "at": 700}


def test_unlimited_supervisor_returns_rejection_then_acceptance_feedback():
    class Connection:
        messages = iter([{"kind": "submission_check"}, {"kind": "submission_check"}, {"kind": "finished", "at": 10000}])
        replies = []

        def poll(self, timeout):
            pytest.fail("Unlimited task must not poll a deadline")

        def recv(self):
            return next(self.messages)

        def send(self, message):
            self.replies.append(message)

    reviews = iter([{"accepted": False, "category": "missing_regression_assertions"}, {"accepted": True, "category": "accepted"}])
    connection = Connection()
    assert bench.wait_for_worker(connection, 100, None, lambda: next(reviews))["at"] == 10000
    assert [reply["accepted"] for reply in connection.replies] == [False, True]


@pytest.mark.parametrize("accepted", [False, True])
def test_worker_only_finishes_verified_submission(accepted):
    from worker import review_submission

    class Connection:
        def send(self, message):
            assert message["kind"] == "submission_check"

        def recv(self):
            return {"accepted": accepted, "feedback": "missing_regression_assertions"}

    output = {"returncode": 0, "output": "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\ndone\n"}
    review_submission(output, Connection())
    assert output["returncode"] == (0 if accepted else 1)
    assert output["output"].startswith("COMPLETE_TASK") is accepted


@pytest.mark.parametrize("accepted", [False, True])
def test_submission_snapshot_stays_paused_only_when_accepted(tmp_path, monkeypatch, accepted):
    actions = []

    def fake_docker(*arguments, **kwargs):
        actions.append(arguments[0])

    monkeypatch.setattr(bench, "docker", fake_docker)
    monkeypatch.setattr(bench, "collect_submission", lambda *args: [])
    monkeypatch.setattr(bench, "verify", lambda *args: {"accepted": accepted, "category": "accepted" if accepted else "verification_failed"})
    review = bench.check_submission("test", tmp_path / "check", "image", {})
    assert review["accepted"] is accepted
    assert actions == (["pause", "cp"] if accepted else ["pause", "cp", "unpause"])


def test_native_usage_totals_keep_provider_fields_and_unknown_calls():
    events = [{"kind": "request_start"}, {"kind": "request_end", "seconds": 10, "usage": {"input_tokens": 100, "output_tokens": 20, "cache_creation": {"ephemeral_5m_input_tokens": 4}}}]
    metrics = bench.usage_metrics(events)
    assert metrics["native_usage_totals"]["cache_creation.ephemeral_5m_input_tokens"] == 4
    assert metrics["completed_request_output_tokens_per_second"] == 2
    assert metrics["usage_complete"]
    assert not bench.usage_metrics(events + [{"kind": "request_start"}])["usage_complete"]


def test_usage_report_counts_normalized_openai_action_blocks():
    events = [
        {"kind": "request_start"},
        {"kind": "request_end", "seconds": 1, "usage": {"input_tokens": 100, "output_tokens": 10}, "normalized_action_blocks": 3},
    ]
    metrics = bench.usage_metrics(events)
    assert metrics["normalized_action_response_count"] == 1
    assert metrics["discarded_action_block_count"] == 2


def test_completion_report_keeps_slow_success_and_profiles_separate(tmp_path):
    for index, profile in enumerate(("local8", "local27", "cloud")):
        output = tmp_path / f"attempt-{index}"
        output.mkdir()
        exit_status = ("Submitted", "deadline", "error")[index]
        record = {"attempt_id": output.name, "task_hash": "completion-task", "profile_hash": profile, "label": profile, "scored": False, "mock": False, "accepted": True, "agent_seconds": 900, "completion_seconds": 902, "api_fee_usd": 0 if index < 2 else 0.5, "category": "accepted", "exit_status": exit_status, "submission_seconds": (12, 600, 200)[index], "native_usage_totals": {"output_tokens": 200}, "usage_complete": True, "verification": {"checks": {"contract": True, "generated": True}}}
        if index == 2:
            record["worker_outcome"] = {"error_type": "RuntimeError"}
        bench.save(output / "result.json", record)
    rows = bench.report(tmp_path)
    assert len(rows) == 3
    assert all(row["acceptance_rate"] == 1 for row in rows)
    assert all(row["median_completion_seconds"] == 902 for row in rows)
    assert all(row["contract_passes"] == row["generated_test_passes"] == 1 for row in rows)
    assert [row["median_early_success_seconds"] for row in rows] == [12, None, None]
    assert rows[2]["nonstandard_stops"][0]["error_type"] == "RuntimeError"


def test_report_retains_partial_deadline_evaluation(tmp_path):
    output = tmp_path / "attempt-partial"
    output.mkdir()
    summary = {"contract": {"total": 2, "passed": 1, "failed": 1, "errors": 0, "skipped": 0, "cases": [{"name": "health", "status": "passed"}, {"name": "receipt", "status": "failed"}]}}
    bench.save(output / "result.json", {"attempt_id": output.name, "task_hash": "ten-minute", "profile_hash": "local27", "label": "local27", "scored": False, "mock": False, "accepted": False, "accepted_within_budget": False, "deadline_seconds": 600, "api_fee_usd": 0, "category": "deadline", "exit_status": "deadline", "verification": {"test_results": summary, "regression_issue": "missing_regression_assertions"}})
    row = bench.report(tmp_path)[0]
    assert row["accepted"] == 0
    assert row["evaluation_results"][0]["stop_reason"] == "deadline"
    assert row["evaluation_results"][0]["test_results"] == summary
    assert row["evaluation_results"][0]["regression_issue"] == "missing_regression_assertions"
    assert row["deadline_seconds"] == 600
    assert row["accepted_within_budget"] == 0


def test_comparison_report_filters_freeze_and_summarizes_models(tmp_path):
    frozen = {"created_at": "current", "image": "sha256:current", "hashes": {"task": "current"}}
    records = [
        ("27b", "local", "qwen3.8-27b-ov", True, 0, 39, 39, 6.5),
        ("8b", "local", "OpenVINO/Qwen3-8B-int8-ov", False, 0, 39, 0, None),
        ("openai", "openai", "gpt-6.1-sol", True, 0.25, 39, 27, 34.0),
    ]
    for name, provider, model, accepted, api_fee, contract_passed, generated_passed, output_rate in records:
        attempt = tmp_path / f"attempt-{name}"
        attempt.mkdir()
        bench.save(attempt / "freeze.json", frozen)
        device = "provider-managed" if provider == "openai" else "GPU"
        profile = {"label": name, "provider": provider, "model": model, "inference": {"device": device, "runtime": "test-runtime"}}
        bench.save(attempt / "result.json", {
            "attempt_id": attempt.name,
            "label": name,
            "provider": provider,
            "model": model,
            "task_hash": "current-task",
            "profile_hash": comparison_report.profile_hash(profile),
            "scored": False,
            "mock": False,
            "accepted": accepted,
            "category": "accepted" if accepted else "test_failure",
            "exit_status": "Submitted" if accepted else "deadline",
            "agent_seconds": 30,
            "through_verification_seconds": 32,
            "api_fee_usd": api_fee,
            "completed_request_output_tokens_per_second": output_rate,
            "native_usage_totals": {"input_tokens": 1000, "output_tokens": 200},
            "verification": {"test_results": {
                "contract": {"passed": contract_passed, "total": 39},
                "generated": {"passed": generated_passed, "total": 27},
            }},
        })

    old = tmp_path / "attempt-old"
    old.mkdir()
    bench.save(old / "freeze.json", {"created_at": "old"})
    bench.save(old / "result.json", {
        "attempt_id": old.name,
        "label": "old",
        "provider": "local",
        "model": "older-model",
        "mock": False,
    })
    profile_paths = []
    for index, (name, provider, model, *_rest) in enumerate(records):
        path = tmp_path / f"profile-{index}.json"
        device = "provider-managed" if provider == "openai" else "GPU"
        bench.save(path, {
            "label": name,
            "provider": provider,
            "model": model,
            "inference": {"device": device, "runtime": "test-runtime"},
        })
        profile_paths.append(path)
    old_profile = tmp_path / "profile-old.json"
    bench.save(old_profile, {
        "label": "old model",
        "provider": "local",
        "model": "older-model",
    })
    profile_paths.append(old_profile)

    report = comparison_report.render_report(tmp_path, frozen, profile_paths)
    assert "Matching model attempts: 3; other saved attempts excluded: 1; matching mock attempts excluded: 0" in report
    assert "| 8b | local / OpenVINO/Qwen3-8B-int8-ov | GPU; test-runtime | 1 | 0 | ready |" in report
    assert "| openai | openai / gpt-6.1-sol | provider-managed; test-runtime | 1 | 0 | ready |" in report
    assert "| old model | local / older-model | unknown; unknown | 0 | 1 | RERUN (1 other freeze) |" in report
    assert "| openai | openai / gpt-6.1-sol | pilot | `current-task` | 1 | 1 | 1/1 (100%)" in report
    assert "| openai | openai / gpt-6.1-sol | pilot | `current-task` | 1 | 1 | 1/1 (100%) | 32.0s | 34.0 |" in report
    assert "| openai | `attempt-openai` | accepted | Submitted | 30.0s | 32.0s | 34.0 |" in report
    assert "| 8b | local / OpenVINO/Qwen3-8B-int8-ov | pilot | `current-task` | 1 | 0 | 0/1 (0%) | n/a | n/a |" in report
    assert "39/39" in report
    assert "0/27" in report
    assert "$0.2500" in report
    assert "`attempt-old`" not in report
    security_report = comparison_report.render_report(tmp_path, frozen, profile_paths, title="Security Repair Comparison")
    assert security_report.startswith("# Security Repair Comparison\n")


@pytest.fixture
def installation_gui_manifest(tmp_path):
    root = tmp_path / "repository with spaces"
    local = root / "dependency-migration/artifacts/installation-local"
    (local / "profiles").mkdir(parents=True)
    (local / "generation-test").mkdir()
    (root / "dependency-migration/profiles").mkdir()
    templates = ["article-27b.json", "local-8b.json", "openai.json", "openai-astra.json",
                 "qwen3-coder-30b.json", "qwen38-fable5-coding-27b.json"]
    profiles = []
    for template in templates:
        profile = json.loads((bench.ENGINE_ROOT / "profiles" / template).read_text(encoding="utf-8"))
        bench.save(root / "dependency-migration/profiles" / template, profile)
        profile["label"] = "INSTALLATION-LOCAL " + Path(template).stem
        path = local / "profiles" / (Path(template).stem + ".private.json")
        bench.save(path, profile)
        profiles.append(path.relative_to(root).as_posix())
    manifest = {"schema_version": 1, "scope": "INSTALLATION-LOCAL", "qualified": False,
                "repository_root": str(root), "workflows": {}}
    for workflow in ("dependency-migration", "security-repair", "regression-tests"):
        freeze = local / "generation-test" / f"{workflow}-INSTALLATION-LOCAL.freeze.json"
        bench.save(freeze, {"image": "sha256:test"})
        manifest["workflows"][workflow] = {"freeze": freeze.relative_to(root).as_posix(), "profiles": profiles.copy()}
        for name in ("policy.json", "workflow.json"):
            source = bench.ENGINE_ROOT.parent / workflow / name
            if source.exists():
                (root / workflow).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, root / workflow / name)
    path = local / "workflows.json"
    bench.save(path, manifest)
    return root, path, manifest


INSTALLATION_GUI_SETUP = r'''
Assert-That ($PSVersionTable.PSVersion.Major -eq 5) 'Installer tests require Windows PowerShell 5.1'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility') -ErrorAction Stop
foreach ($name in @('Resolve-InstallationFile', 'Get-InstallationSettings', 'Get-SelectedModel')) {
    . ([scriptblock]::Create((Import-ControllerFunction $name)))
}
$testRoot = Join-Path $env:CONTROLLER_TEST_TEMP 'repository with spaces'
$script:profileRoot = Join-Path $testRoot 'dependency-migration\profiles'
$InstallationManifest = Join-Path $testRoot 'dependency-migration\artifacts\installation-local\workflows.json'
$Workflow = 'dependency-migration'
$FreezePath = ''
$script:dockerInitializations = 0
function Initialize-InstallationDocker { $script:dockerInitializations++ }
function Initialize-InstallationController {
    $script:engineRoot = Join-Path $testRoot 'dependency-migration'
    foreach ($statement in $controller.EndBlock.Statements) {
        if ($statement.Extent.Text -like 'New-Item*') { break }
        if ($statement -is [System.Management.Automation.Language.AssignmentStatementAst]) {
            if ($statement.Left.Extent.Text -ne '$script:engineRoot') {
                . ([scriptblock]::Create($statement.Extent.Text))
            }
        }
        elseif ($statement -is [System.Management.Automation.Language.IfStatementAst]) {
            . ([scriptblock]::Create($statement.Extent.Text))
        }
    }
}
'''


@pytest.mark.parametrize("workflow", ["dependency-migration", "security-repair", "regression-tests"])
def test_installer_gui_manifest_routes_profiles_freeze_and_reports(tmp_path, installation_gui_manifest, workflow):
    run_controller_powershell(tmp_path, INSTALLATION_GUI_SETUP + r'''
$Workflow = '__WORKFLOW__'
Initialize-InstallationController
Assert-That ($script:dockerInitializations -eq 1) 'Installed controller did not initialize Docker once'
Assert-That ($script:profilePaths.Count -eq 6) 'Missing installed profiles'
Assert-That ($script:freezePath -like "*generation-test\$Workflow-INSTALLATION-LOCAL.freeze.json") 'Wrong workflow freeze'
Assert-That ($script:workflowTitle -like '*INSTALLATION-LOCAL (unscored)') 'Missing installation title'
Assert-That ($script:reportTitle -like '*INSTALLATION-LOCAL (unscored)') 'Missing installation report title'
$modelPicker = [pscustomobject]@{ SelectedIndex = 0 }
for ($index = 0; $index -lt 6; $index++) {
    $modelPicker.SelectedIndex = $index
    $selected = Get-SelectedModel
    Assert-That ($selected.Path -eq $script:profilePaths[$index]) 'Selected historical profile'
    Assert-That ($selected.Profile.label -like 'INSTALLATION-LOCAL *') 'Wrong profile content'
    Assert-That ([IO.Path]::IsPathRooted($selected.Path)) 'Profile path is not absolute'
}
$script:launches = @()
function Start-TrackedProcess($executable, $arguments, $directory, $kind) {
    $script:launches += [pscustomobject]@{ Arguments = $arguments; Kind = $kind }
    return [pscustomobject]@{ HasExited = $true }
}
function Update-Status { }
$script:comparisonHandler = Get-ControllerHandler 'comparisonButton' 'Add_Click'
$comparisonButton | Add-Member -MemberType ScriptMethod -Name PerformClick -Value { . $script:comparisonHandler }
foreach ($owner in @('comparisonButton', 'reportButton')) {
    . (Get-ControllerHandler $owner 'Add_Click')
    $launch = $script:launches[-1]
    Assert-That ($launch.Kind -eq 'comparison-report') 'Installed report used unfiltered historical report'
    Assert-That ($launch.Arguments.Contains('--freeze "' + $script:freezePath + '"')) 'Report lost installed freeze'
    foreach ($path in $script:profilePaths) {
        Assert-That ($launch.Arguments.Contains('--profile "' + $path + '"')) 'Report lost installed profile'
    }
    Assert-That (-not $launch.Arguments.Contains('ptl-')) 'Report includes historical profile'
}
$modelPicker.SelectedIndex = 0
$script:serverReady = $true
$script:warmupReady = $false
$throughputStatus = [pscustomobject]@{ Text = '' }
$script:verifications = 0
function Assert-InstallationCurrent { $script:verifications++ }
. (Get-ControllerHandler 'runButton' 'Add_Click')
Assert-That ($script:verifications -eq 1) 'Installed pilot skipped verification'
$launch = $script:launches[-1]
Assert-That ($launch.Kind -eq 'pilot') 'Pilot was not dispatched'
Assert-That ($launch.Arguments.Contains('--freeze "' + $script:freezePath + '"')) 'Pilot lost installed freeze'
Assert-That ($launch.Arguments.Contains('--profile "' + $script:profilePaths[0] + '"')) 'Pilot lost installed profile'
Assert-That (-not $launch.Arguments.Contains('--scored')) 'Installation run became scored'
Remove-Item -LiteralPath $script:profilePaths[0]
$rejected = $false
try { Get-SelectedModel | Out-Null } catch { $rejected = $true }
Assert-That $rejected 'Missing installed profile fell back to historical template'
Assert-That (-not (Test-Path -LiteralPath $script:profilePaths[0])) 'Missing installed profile was recreated'
'''.replace('__WORKFLOW__', workflow))


@pytest.mark.parametrize("failure", ["none", "changed-before", "changed-during", "missing-manifest",
                                     "missing-digest", "empty-digest", "nonzero", "null-exit", "timeout",
                                     "start-failed", "historical", "absent-settings"])
def test_installer_gui_verifies_before_pilot(tmp_path, installation_gui_manifest, failure):
    run_controller_powershell(tmp_path, INSTALLATION_GUI_SETUP + r'''
Add-Type -TypeDefinition @'
namespace ControllerTest {
    public static class MessageBox {
        public static int Confirmations;
        public static string LastMessage;
        public static string Show(string text, string title, string buttons, string icon) {
            LastMessage = text;
            if (buttons == "YesNo") { Confirmations++; }
            return "Yes";
        }
    }
}
'@
Initialize-InstallationController
. ([scriptblock]::Create((Import-ControllerFunction 'Assert-InstallationCurrent')))
$failure = '__FAILURE__'
$originalFreeze = $script:freezePath
$originalProfiles = $script:profilePaths -join '|'
$script:messages = @()
$script:launches = @()
$script:statusUpdates = 0
$script:logReads = 0
$script:selections = 0
$script:verification = [pscustomobject]@{
    ExitCode = 0; HasExited = $true; Killed = $false; Disposed = $false; WaitMilliseconds = 0
}
$script:verification | Add-Member ScriptMethod WaitForExit {
    param($milliseconds)
    $this.WaitMilliseconds = $milliseconds
    if ($failure -eq 'changed-during') { Add-Content -LiteralPath $InstallationManifest -Value ' ' }
    return $failure -ne 'timeout'
}
$script:verification | Add-Member ScriptMethod Refresh { }
$script:verification | Add-Member ScriptMethod Kill { $this.Killed = $true }
$script:verification | Add-Member ScriptMethod Dispose { $this.Disposed = $true }
function Write-Log($message) { $script:messages += $message }
function Read-WatchedFiles { $script:logReads++ }
function Update-Status { $script:statusUpdates++ }
function Get-SelectedModel {
    $script:selections++
    [pscustomobject]@{ Name = 'test cloud'; Path = $script:profilePaths[2]; Profile = [pscustomobject]@{ provider = 'openai' } }
}
function Start-TrackedProcess($executable, $arguments, $directory, $kind) {
    $script:launches += [pscustomobject]@{ Executable = $executable; Arguments = $arguments; Directory = $directory; Kind = $kind }
    if ($kind -eq 'installationverify') {
        if ($failure -eq 'start-failed') { throw 'Verifier could not start' }
        return $script:verification
    }
    Assert-That ($kind -eq 'pilot') 'Unexpected child launch'
    return [pscustomobject]@{ HasExited = $false }
}
$benchmark = [pscustomobject]@{ HasExited = $true; Killed = $false }
$benchmark | Add-Member ScriptMethod Kill { $this.Killed = $true; throw 'Must not kill benchmark' }
$script:taskProcess = $benchmark
$throughputStatus = [pscustomobject]@{ Text = '' }
$env:OPENAI_API_KEY = 'test-placeholder-never-sent'
switch ($failure) {
    'changed-before' { Add-Content -LiteralPath $InstallationManifest -Value ' ' }
    'missing-manifest' { Remove-Item -LiteralPath $InstallationManifest }
    'missing-digest' { Remove-Variable installationManifestDigest -Scope Script }
    'empty-digest' { $script:installationManifestDigest = '' }
    'nonzero' { $script:verification.ExitCode = 7 }
    'null-exit' { $script:verification.ExitCode = $null }
    'timeout' { $script:verification.HasExited = $false }
    'historical' { $script:installationSettings = $null }
    'absent-settings' { Remove-Variable installationSettings -Scope Script }
}
. (Get-ControllerHandler 'runButton' 'Add_Click')
$success = $failure -in @('none', 'historical', 'absent-settings')
$verifierExpected = $failure -notin @('changed-before', 'missing-manifest', 'missing-digest', 'empty-digest', 'historical', 'absent-settings')
$verifiers = @($script:launches | Where-Object Kind -eq 'installationverify')
$pilots = @($script:launches | Where-Object Kind -eq 'pilot')
Assert-That ($verifiers.Count -eq [int]$verifierExpected) 'Wrong verifier launch count'
Assert-That ($pilots.Count -eq [int]$success) 'Verification failure allowed a pilot'
Assert-That ($script:selections -eq [int]$success) 'Selected model before verification passed'
Assert-That ([ControllerTest.MessageBox]::Confirmations -eq [int]$success) 'Billable prompt preceded verification'
Assert-That ($script:statusUpdates -eq 1) 'Controls were not refreshed'
Assert-That (-not $benchmark.Killed) 'Killed benchmark instead of owned verifier'
Assert-That ($script:freezePath -eq $originalFreeze -and ($script:profilePaths -join '|') -eq $originalProfiles) 'Changed cached selection'
if ($verifierExpected) {
    $launch = $verifiers[0]
    $helper = Join-Path $script:workspaceRoot 'installer\prepare_workflows.py'
    Assert-That ($launch.Executable -eq $script:runnerPython) 'Verifier did not use locked runner'
    Assert-That ($launch.Arguments -ceq ('-B "{0}" --root "{1}" --verify-only' -f $helper, $script:workspaceRoot)) 'Wrong verification arguments or quoting'
    Assert-That ($launch.Directory -eq $script:workspaceRoot) 'Wrong verifier working directory'
    if ($failure -ne 'start-failed') {
        Assert-That ($script:verification.WaitMilliseconds -eq 30000) 'Verification wait was not bounded to 30 seconds'
        Assert-That ($script:verification.Killed -eq ($failure -eq 'timeout')) 'Incorrect verifier termination'
        Assert-That ($script:verification.Disposed -and $script:logReads -eq 1) 'Verifier resources or logs were not handled'
    }
}
if ($success) {
    if ($failure -eq 'none') {
        Assert-That ($script:launches[0].Kind -eq 'installationverify') 'Pilot preceded verification'
        Assert-That (($script:messages -join ' ') -like '*Installation verification passed*') 'Missing success log'
    }
}
else {
    Assert-That ([object]::ReferenceEquals($script:taskProcess, $benchmark)) 'Verification replaced benchmark process'
    Assert-That (($script:messages -join ' ') -like '*Could not start pilot:*') 'Failure missing from GUI log'
    Assert-That (($script:messages -join ' ') -notlike '*Installation verification passed*') 'Failure logged as success'
    $expected = switch ($failure) {
        'nonzero' { '*verification failed (exit 7)*' }
        'null-exit' { '*verification failed*' }
        'timeout' { '*timed out after 30 seconds*' }
        'start-failed' { '*Verifier could not start*' }
        default { '*Installation changed; close and reopen*' }
    }
    Assert-That ([ControllerTest.MessageBox]::LastMessage -like $expected) 'Wrong failure explanation'
}
'''.replace('__FAILURE__', failure))


@pytest.mark.parametrize("location", ["path", "program-files", "local-app-data", "both", "missing", "unset-roots"])
@pytest.mark.parametrize("inherited_overrides", [False, True])
def test_installer_gui_docker_environment(tmp_path, installation_gui_manifest, location, inherited_overrides):
    run_controller_powershell(tmp_path, INSTALLATION_GUI_SETUP + r'''
$definition = Import-ControllerFunction 'Initialize-InstallationDocker'
$functionAst = [System.Management.Automation.Language.Parser]::ParseInput($definition, [ref]$tokens, [ref]$parseErrors)
Assert-That ($parseErrors.Count -eq 0) 'Docker initialization did not parse in Windows PowerShell 5.1'
$commands = @($functionAst.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst]
}, $true))
foreach ($command in $commands) {
    Assert-That ($command.GetCommandName() -in @('Get-Command', 'Select-Object', 'Join-Path', 'Test-Path', 'Remove-Item')) 'Unexpected command could start Docker or change global state'
}
$invocations = @($functionAst.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.InvokeMemberExpressionAst]
}, $true))
Assert-That ($invocations.Count -eq 0) 'Docker initialization must not call persistent environment or process APIs'
$removals = @($commands | Where-Object { $_.GetCommandName() -eq 'Remove-Item' })
Assert-That ($removals.Count -eq 1 -and $removals[0].Extent.Text -eq 'Remove-Item Env:DOCKER_HOST, Env:DOCKER_TLS_VERIFY, Env:DOCKER_CERT_PATH -ErrorAction SilentlyContinue') 'Only process Docker overrides may be removed'
. ([scriptblock]::Create($definition))
$saved = @{}
foreach ($name in @('PATH', 'ProgramFiles', 'LOCALAPPDATA', 'DOCKER_CONTEXT', 'DOCKER_HOST', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')) {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    $env:ProgramFiles = Join-Path $env:CONTROLLER_TEST_TEMP 'Program Files'
    $env:LOCALAPPDATA = Join-Path $env:CONTROLLER_TEST_TEMP 'Local App Data'
    $pathDirectory = Join-Path $env:CONTROLLER_TEST_TEMP 'cli on path'
    $systemDirectory = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'
    $userDirectory = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'
    foreach ($directory in @($pathDirectory, $systemDirectory, $userDirectory)) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }
    $env:PATH = $pathDirectory
    $env:DOCKER_CONTEXT = 'remote-context'
    foreach ($name in @('DOCKER_HOST', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')) {
        $value = if (__OVERRIDES__) { 'remote-override' } else { $null }
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
    $location = '__LOCATION__'
    $expectedDirectory = switch ($location) {
        'path' { $pathDirectory }
        'program-files' { $systemDirectory }
        'local-app-data' { $userDirectory }
        'both' { $systemDirectory }
        default { $null }
    }
    if ($expectedDirectory) { [IO.File]::WriteAllText((Join-Path $expectedDirectory 'docker.exe'), 'inert test file; never execute') }
    if ($location -in @('path', 'both')) {
        [IO.File]::WriteAllText((Join-Path $systemDirectory 'docker.exe'), 'inert test file; never execute')
        [IO.File]::WriteAllText((Join-Path $userDirectory 'docker.exe'), 'inert test file; never execute')
    }
    if ($location -eq 'unset-roots') {
        Remove-Item Env:ProgramFiles, Env:LOCALAPPDATA
    }
    $failure = $null
    try { Initialize-InstallationController } catch { $failure = $_ }
    if (-not $expectedDirectory) {
        Assert-That ($null -ne $failure) 'Missing Docker CLI was accepted'
        Assert-That ($failure.Exception.Message -like '*Docker CLI (docker.exe)*Repair*Docker Desktop*PATH*reopen*') 'CLI failure is not actionable'
        Assert-That ($env:PATH -eq $pathDirectory -and $env:DOCKER_CONTEXT -eq 'remote-context') 'Failed discovery changed the environment'
    }
    else {
        if ($failure) { throw $failure }
        Assert-That ($env:DOCKER_CONTEXT -eq 'desktop-linux') 'Installation did not select the local Linux context'
        foreach ($name in @('DOCKER_HOST', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')) {
            Assert-That ($null -eq [Environment]::GetEnvironmentVariable($name, 'Process')) "Inherited override survived: $name"
        }
        $expectedPath = if ($location -eq 'path') { $pathDirectory } else { $expectedDirectory + ';' + $pathDirectory }
        Assert-That ($env:PATH -eq $expectedPath) 'CLI search order or PATH preservation changed'
        Assert-That ((Get-Command docker.exe -CommandType Application).Source -eq (Join-Path $expectedDirectory 'docker.exe')) 'Docker CLI is not discoverable'
        Initialize-InstallationDocker
        Assert-That ($env:PATH -eq $expectedPath) 'Repeated setup duplicated PATH'
        $childJson = & (Join-Path $PSHOME 'powershell.exe') -NoLogo -NoProfile -NonInteractive -Command '[pscustomobject]@{ Context = $env:DOCKER_CONTEXT; HostOverride = $env:DOCKER_HOST; Tls = $env:DOCKER_TLS_VERIFY; Cert = $env:DOCKER_CERT_PATH; Path = $env:PATH } | ConvertTo-Json -Compress'
        Assert-That ($LASTEXITCODE -eq 0) 'Environment probe child failed'
        $child = $childJson | ConvertFrom-Json
        Assert-That ($child.Context -eq 'desktop-linux' -and $child.Path -eq $expectedPath) 'Child process lost Docker context or PATH'
        Assert-That (-not $child.HostOverride -and -not $child.Tls -and -not $child.Cert) 'Child inherited remote Docker overrides'
    }
}
finally {
    foreach ($name in $saved.Keys) { [Environment]::SetEnvironmentVariable($name, $saved[$name], 'Process') }
}
'''.replace('__LOCATION__', location).replace('__OVERRIDES__', '$true' if inherited_overrides else '$false'))


@pytest.mark.parametrize("failure", [
    "schema", "schema-string", "scope", "qualified", "qualified-string", "missing-qualified",
    "repository", "relative-repository", "missing-workflow", "missing-freeze", "missing-profile",
    "profile-count", "profile-extra", "profile-scalar", "profile-order", "profile-duplicate",
    "profile-qualified", "profile-missing-qualified", "profile-provider", "profile-model",
    "profile-label", "profile-url", "profile-invalid-json", "manifest-invalid-json",
    "freeze-absolute", "freeze-traversal", "freeze-outside", "freeze-prefix-sibling", "freeze-ads",
    "freeze-wildcard", "freeze-drive-relative", "freeze-root-relative", "freeze-directory",
    "profile-escape", "profile-absolute", "freeze-override", "relative-manifest", "missing-manifest",
])
def test_installer_gui_rejects_invalid_manifest(tmp_path, installation_gui_manifest, failure):
    root, path, manifest = installation_gui_manifest
    record = manifest["workflows"]["dependency-migration"]
    profile_path = root / record["profiles"][0]
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if failure in {"schema", "schema-string", "scope", "qualified", "qualified-string", "repository", "relative-repository"}:
        field, value = {
            "schema": ("schema_version", 2), "schema-string": ("schema_version", "1"),
            "scope": ("scope", "historical"), "qualified": ("qualified", True),
            "qualified-string": ("qualified", "false"), "repository": ("repository_root", str(tmp_path)),
            "relative-repository": ("repository_root", "."),
        }[failure]
        manifest[field] = value
    elif failure == "missing-qualified":
        del manifest["qualified"]
    elif failure == "missing-workflow":
        del manifest["workflows"]["dependency-migration"]
    elif failure == "missing-freeze":
        (root / record["freeze"]).unlink()
    elif failure == "missing-profile":
        profile_path.unlink()
    elif failure == "profile-count":
        record["profiles"].pop()
    elif failure == "profile-extra":
        record["profiles"].append(record["profiles"][0])
    elif failure == "profile-scalar":
        record["profiles"] = record["profiles"][0]
    elif failure == "profile-order":
        record["profiles"][0], record["profiles"][1] = record["profiles"][1], record["profiles"][0]
    elif failure == "profile-duplicate":
        record["profiles"][1] = record["profiles"][0]
    elif failure in {"profile-qualified", "profile-missing-qualified", "profile-provider", "profile-model", "profile-label", "profile-url"}:
        if failure == "profile-missing-qualified":
            del profile["qualified"]
        else:
            field, value = {"profile-qualified": ("qualified", True), "profile-provider": ("provider", "openai"),
                            "profile-model": ("model", "wrong"), "profile-label": ("label", ""),
                            "profile-url": ("base_url", None)}[failure]
            profile[field] = value
        bench.save(profile_path, profile)
    elif failure == "profile-invalid-json":
        profile_path.write_text("{", encoding="utf-8")
    elif failure.startswith("freeze-") and failure != "freeze-override":
        local = "dependency-migration/artifacts/installation-local"
        record["freeze"] = {
            "freeze-absolute": str(root / record["freeze"]),
            "freeze-traversal": local + "/../outside.json", "freeze-outside": "outside.json",
            "freeze-prefix-sibling": local + "-other/freeze.json", "freeze-ads": record["freeze"] + ":stream",
            "freeze-wildcard": local + "/generation-test/*.json", "freeze-drive-relative": "C:freeze.json",
            "freeze-root-relative": r"\freeze.json", "freeze-directory": local + "/profiles",
        }[failure]
        if failure in {"freeze-traversal", "freeze-outside", "freeze-prefix-sibling"}:
            (root / record["freeze"]).parent.mkdir(parents=True, exist_ok=True)
            bench.save(root / record["freeze"], {})
    elif failure == "profile-escape":
        record["profiles"][0] = "dependency-migration/profiles/article-27b.json"
    elif failure == "profile-absolute":
        record["profiles"][0] = str(profile_path)
    bench.save(path, manifest)
    if failure == "manifest-invalid-json":
        path.write_text("{", encoding="utf-8")
    if failure == "missing-manifest":
        path.unlink()
    extra = {"freeze-override": "$FreezePath = 'override.json'\n",
             "relative-manifest": "$InstallationManifest = 'workflows.json'\n"}.get(failure, "")
    run_controller_powershell(tmp_path, INSTALLATION_GUI_SETUP + extra + r'''
$rejected = $false
try { Initialize-InstallationController } catch { $rejected = $true }
Assert-That $rejected 'Unsafe installation manifest was accepted'
Assert-That ($script:dockerInitializations -eq 0) 'Rejected manifest initialized Docker'
''')


@pytest.mark.parametrize("workflow", ["dependency-migration", "security-repair", "regression-tests"])
@pytest.mark.parametrize("override", [False, True])
def test_installer_gui_no_manifest_preserves_historical_defaults(tmp_path, installation_gui_manifest, workflow, override):
    run_controller_powershell(tmp_path, INSTALLATION_GUI_SETUP + r'''
$Workflow = '__WORKFLOW__'
$InstallationManifest = ''
$FreezePath = __OVERRIDE__
$dockerEnvironment = @{}
foreach ($name in @('PATH', 'DOCKER_CONTEXT', 'DOCKER_HOST', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')) {
    $dockerEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
Initialize-InstallationController
Assert-That ($script:dockerInitializations -eq 0) 'Historical mode initialized Docker'
foreach ($name in $dockerEnvironment.Keys) {
    Assert-That ([Environment]::GetEnvironmentVariable($name, 'Process') -ceq $dockerEnvironment[$name]) "Historical mode changed $name"
}
Assert-That ($null -eq $script:installationSettings) 'Historical mode loaded installed settings'
Assert-That ($script:profilePaths[0] -eq 'ptl-morteza89-27b.private.json') 'Historical profiles changed'
Assert-That ($script:workflowTitle -notlike '*INSTALLATION-LOCAL*') 'Historical title changed'
$expected = if ($FreezePath) { [IO.Path]::GetFullPath($FreezePath) } else { Join-Path $script:workflowRoot ('artifacts\' + $script:freezeName) }
Assert-That ($script:freezePath -eq $expected) 'Historical freeze or explicit override changed'
$modelPicker = [pscustomobject]@{ SelectedIndex = 0 }
$selected = Get-SelectedModel
Assert-That ($selected.Path -eq (Join-Path $script:profileRoot $script:profilePaths[0])) 'Historical template fallback changed'
'''.replace('__WORKFLOW__', workflow).replace('__OVERRIDE__', "'pending-freeze.json'" if override else "''"))


@pytest.mark.parametrize("workflow", ["dependency-migration", "security-repair", "regression-tests"])
@pytest.mark.parametrize("installed", [False, True])
def test_installer_gui_direct_launch_quotes_paths_and_propagates_exit(tmp_path, workflow, installed):
    if os.name != "nt":
        pytest.skip("Windows PowerShell launch requires Windows")
    root = tmp_path / "repository with spaces & punctuation"
    engine = root / "dependency-migration"
    engine.mkdir(parents=True)
    controller = engine / "demo-controller.ps1"
    controller.write_text(r'''
param([string]$Workflow = 'dependency-migration', [string]$InstallationManifest)
$record = @{ workflow = $Workflow; manifest = $InstallationManifest; version = $PSVersionTable.PSVersion.Major }
[IO.File]::WriteAllText($env:LAUNCHER_TEST_RESULT, ($record | ConvertTo-Json))
exit 17
''', encoding="utf-8")
    manifest = engine / "artifacts/installation-local/workflows.json"
    if installed:
        manifest.parent.mkdir(parents=True)
        bench.save(manifest, {})
    output = tmp_path / "launcher-result.json"
    environment = dict(os.environ, LAUNCHER_TEST_RESULT=str(output))
    environment.pop("PSModulePath", None)
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    arguments = [str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(controller),
                 "-Workflow", workflow]
    if installed:
        arguments.extend(["-InstallationManifest", str(manifest)])
    result = subprocess.run(arguments,
                            cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=45)
    assert result.returncode == 17, result.stdout + result.stderr
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["workflow"] == workflow
    assert record["version"] == 5
    if installed:
        assert Path(record["manifest"]).is_absolute()
        assert Path(record["manifest"]).resolve() == manifest.resolve()
    else:
        assert not record["manifest"]


def save_comparison_attempt(directory, name, frozen, **fields):
    attempt = directory / f"attempt-{name}"
    attempt.mkdir()
    bench.save(attempt / "freeze.json", frozen)
    result = {"attempt_id": attempt.name, "label": name, "provider": "local", "model": "local-model",
              "task_hash": "task", "profile_hash": "profile", "scored": False, "mock": False,
              "accepted": True, "category": "accepted", "exit_status": "Submitted"}
    result.update(fields)
    bench.save(attempt / "result.json", result)
    return attempt


def test_comparison_report_header_names_freeze_file(tmp_path):
    frozen = {"created_at": "freeze-time"}
    report = comparison_report.render_report(tmp_path, frozen, [], freeze_name="freeze-600s-v10.json")
    assert "\nFreeze file: freeze-600s-v10.json\nFrozen task created: freeze-time\n" in report
    assert "Freeze file: unknown" in comparison_report.render_report(tmp_path, frozen, [])
    assert "Skipped malformed artifacts" not in report


def test_comparison_report_attributes_attempts_by_profile_hash(tmp_path):
    frozen = {"created_at": "current"}
    profile = {"label": "local27", "provider": "local", "model": "qwen-27b", "inference": {"device": "GPU", "runtime": "ovms"}}
    profile_path = tmp_path / "local27.json"
    bench.save(profile_path, profile)
    current = comparison_report.profile_hash(profile)
    save_comparison_attempt(tmp_path, "stale", frozen, label="local27", model="qwen-27b", profile_hash="stale-profile-hash")
    report = comparison_report.render_report(tmp_path, frozen, [profile_path])
    assert "| local27 | local / qwen-27b | GPU; ovms | 0 | 0 | RERUN (profile changed) |" in report
    assert "| `stale-profil` (changed) |" in report
    save_comparison_attempt(tmp_path, "fresh", frozen, label="local27", model="qwen-27b", profile_hash=current)
    report = comparison_report.render_report(tmp_path, frozen, [profile_path])
    assert "| local27 | local / qwen-27b | GPU; ovms | 1 | 0 | ready |" in report
    assert f"| `{current[:12]}` (current) |" in report
    assert "| `stale-profil` (changed) |" in report
    missing = comparison_report.render_report(tmp_path, frozen, [tmp_path / "absent.private.json"])
    assert "| absent.private | not configured | not configured | 0 | 0 | PROFILE MISSING |" in missing


def test_comparison_report_shows_local_and_reasoning_tokens(tmp_path):
    frozen = {"created_at": "tokens"}
    save_comparison_attempt(tmp_path, "local", frozen, created_at="1",
                            native_usage_totals={"prompt_tokens": 1200, "completion_tokens": 300,
                                                 "completion_tokens_details.reasoning_tokens": 120})
    save_comparison_attempt(tmp_path, "cloud", frozen, created_at="2", provider="openai", model="gpt-6.1-sol",
                            native_usage_totals={"input_tokens": 900, "output_tokens": 400,
                                                 "output_tokens_details.reasoning_tokens": 256})
    save_comparison_attempt(tmp_path, "plain", frozen, created_at="3", native_usage_totals={"prompt_tokens": 10, "completion_tokens": 5})
    save_comparison_attempt(tmp_path, "empty", frozen, created_at="4")
    report = comparison_report.render_report(tmp_path, frozen, [])
    assert "| `attempt-local` | accepted | Submitted | n/a | n/a | n/a | n/a | n/a | unknown | 1200 / 300 (reasoning 120) | n/a | n/a |" in report
    assert "| 900 / 400 (reasoning 256) | n/a | n/a |" in report
    assert "| 10 / 5 | n/a | n/a |" in report
    assert "| n/a / n/a | n/a | n/a |" in report
    assert "For providers whose output cap includes reasoning tokens, output tokens/s counts reasoning tokens" in report


def test_comparison_report_lists_request_settings_per_configured_model(tmp_path):
    frozen = {"created_at": "settings"}
    local_profile = {"label": "local27", "provider": "local", "model": "qwen-27b"}
    cloud_profile = {"label": "sol", "provider": "openai", "model": "gpt-6.1-sol"}
    unused_profile = {"label": "idle", "provider": "local", "model": "idle-model"}
    paths = []
    for index, profile in enumerate((local_profile, cloud_profile, unused_profile)):
        path = tmp_path / f"profile-{index}.json"
        bench.save(path, profile)
        paths.append(path)
    save_comparison_attempt(tmp_path, "local", frozen, label="local27", model="qwen-27b", request_settings={
        "provider": "local", "model": "qwen-27b", "max_output_tokens": 4096, "temperature": 0, "sampling": "greedy",
        "reasoning": "disabled", "output_cap_includes_reasoning_tokens": False, "retries": 0, "api": "chat.completions"})
    save_comparison_attempt(tmp_path, "cloud", frozen, label="sol", provider="openai", model="gpt-6.1-sol", request_settings={
        "provider": "openai", "model": "gpt-6.1-sol", "max_output_tokens": 2048, "temperature": None, "sampling": "provider_default",
        "reasoning": "effort=medium", "output_cap_includes_reasoning_tokens": True, "retries": 0, "api": "responses"})
    report = comparison_report.render_report(tmp_path, frozen, paths)
    assert report.index("## Model Coverage") < report.index("## Request Settings") < report.index("## Summary")
    assert "| Configured model | Sampling | Temperature | Reasoning | Max output tokens | Cap includes reasoning tokens | API |" in report
    assert "| local27 | greedy | 0 | disabled | 4096 | no | chat.completions |" in report
    assert "| sol | provider_default | n/a | effort=medium | 2048 | yes | responses |" in report
    settings_section = report.split("## Request Settings")[1].split("## Summary")[0]
    assert "| idle |" not in settings_section
    assert "Local and cloud attempts are not identical in sampling/reasoning configuration; this must be considered when comparing" in report
    assert "## Request Settings" not in comparison_report.render_report(tmp_path, frozen, [])


def test_comparison_report_marks_incomplete_fees_as_lower_bounds(tmp_path):
    frozen = {"created_at": "fees"}
    save_comparison_attempt(tmp_path, "partial", frozen, label="sol", provider="openai", model="gpt-6.1-sol",
                            created_at="1", api_fee_usd=0.25, api_fee_incomplete=True)
    save_comparison_attempt(tmp_path, "complete", frozen, label="sol", provider="openai", model="gpt-6.1-sol",
                            created_at="2", api_fee_usd=0.5, api_fee_incomplete=False)
    save_comparison_attempt(tmp_path, "nofee", frozen, label="other", model="other-model", api_fee_usd=None, api_fee_incomplete=True)
    report = comparison_report.render_report(tmp_path, frozen, [])
    assert "| 2/2 (100%) | n/a | n/a | n/a | n/a | \u2265 $0.7500 (incomplete) |" in report
    assert "| `attempt-partial` | accepted | Submitted | n/a | n/a | n/a | n/a | n/a | \u2265 $0.2500 (incomplete) |" in report
    assert "| `attempt-complete` | accepted | Submitted | n/a | n/a | n/a | n/a | n/a | $0.5000 |" in report
    assert "| `attempt-nofee` | accepted | Submitted | n/a | n/a | n/a | n/a | n/a | unknown |" in report
    assert "| 1/1 (100%) | n/a | n/a | n/a | n/a | unknown |" in report


def test_comparison_report_shows_budget_and_format_normalization_columns(tmp_path):
    frozen = {"created_at": "budget"}
    save_comparison_attempt(tmp_path, "inside", frozen, created_at="1", accepted_within_budget=True, normalized_action_response_count=2)
    save_comparison_attempt(tmp_path, "late", frozen, created_at="2", accepted_within_budget=False, normalized_action_response_count=0)
    save_comparison_attempt(tmp_path, "legacy", frozen, created_at="3")
    report = comparison_report.render_report(tmp_path, frozen, [])
    assert "| Input / output tokens | Within budget | Fmt norm. |" in report
    assert "| `attempt-inside` | accepted | Submitted | n/a | n/a | n/a | n/a | n/a | unknown | n/a / n/a | yes | 2 |" in report
    assert "| `attempt-late` | accepted | Submitted | n/a | n/a | n/a | n/a | n/a | unknown | n/a / n/a | no | 0 |" in report
    assert "| `attempt-legacy` | accepted | Submitted | n/a | n/a | n/a | n/a | n/a | unknown | n/a / n/a | n/a | n/a |" in report
    assert "Fmt norm. counts responses whose extra action blocks were discarded." in report


def test_comparison_report_skips_malformed_artifacts(tmp_path):
    frozen = {"created_at": "robust"}
    save_comparison_attempt(tmp_path, "good", frozen)
    broken = tmp_path / "attempt-broken"
    broken.mkdir()
    bench.save(broken / "freeze.json", frozen)
    (broken / "result.json").write_text("{not json", encoding="utf-8")
    bad_freeze = tmp_path / "attempt-bad-freeze"
    bad_freeze.mkdir()
    (bad_freeze / "freeze.json").write_text("", encoding="utf-8")
    bench.save(bad_freeze / "result.json", {"attempt_id": bad_freeze.name, "mock": False})
    report = comparison_report.render_report(tmp_path, frozen, [], freeze_name="freeze.json")
    assert "Matching model attempts: 1; other saved attempts excluded: 0; matching mock attempts excluded: 0\nSkipped malformed artifacts: 2\n" in report
    assert "`attempt-good`" in report
    assert "attempt-broken" not in report and "attempt-bad-freeze" not in report
    assert comparison_report.read_json(broken / "result.json", strict=False) is None
    with pytest.raises(ValueError):
        comparison_report.read_json(broken / "result.json")