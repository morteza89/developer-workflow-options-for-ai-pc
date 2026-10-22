"""Exercise installer boundaries in Windows PowerShell 5.1, never install software."""

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import stat
import subprocess
import sys
from urllib.parse import urlsplit
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "installer" / "install.ps1"
POWERSHELL = Path(os.environ.get("SystemRoot", "C:/Windows")) / (
    "System32/WindowsPowerShell/v1.0/powershell.exe"
)
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell 5.1 required")


def ps_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


@pytest.fixture
def powershell(tmp_path):
    assert POWERSHELL.is_file(), "Windows PowerShell 5.1 is required, not pwsh"

    def run(body, *, installer=INSTALLER, data=None):
        script = tmp_path / "test harness.ps1"
        case_path = tmp_path / "case.json"
        case_path.write_text(json.dumps(data or {}), encoding="utf-8")
        script.write_text(
            """
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
function Invoke-WebRequest { throw 'FORBIDDEN: network request' }
function Invoke-RestMethod { throw 'FORBIDDEN: network request' }
function Start-Process { throw 'FORBIDDEN: process launch or elevation' }
function Enable-WindowsOptionalFeature { throw 'FORBIDDEN: Windows feature installation' }
function Set-Acl { throw 'FORBIDDEN: ACL change' }
function Get-ItemProperty { throw 'FORBIDDEN: registry read' }
function New-ItemProperty { throw 'FORBIDDEN: registry change' }
function Set-ItemProperty { throw 'FORBIDDEN: registry change' }
function Remove-ItemProperty { throw 'FORBIDDEN: registry change' }
try {
    if ($PSVersionTable.PSEdition -ne 'Desktop' -or
        $PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
        throw 'Expected Windows PowerShell 5.1 Desktop'
    }
"""
            + f"    $case = Get-Content -LiteralPath {ps_literal(case_path)} -Raw | ConvertFrom-Json\n"
            + f"    . {ps_literal(installer)} -LibraryOnly\n"
            + """
    $installerFunctions = @{
        'Wait-Docker' = ${function:Wait-Docker}
        'Ensure-Ovms' = ${function:Ensure-Ovms}
    }
    function Request-SystemStage { throw 'FORBIDDEN: elevation' }
    function Confirm-DockerLicense { throw 'FORBIDDEN: interactive license prompt' }
    function Ensure-Uv { throw 'FORBIDDEN: uv setup' }
    function Ensure-Runner { throw 'FORBIDDEN: runner setup' }
    function Ensure-Ovms { throw 'FORBIDDEN: model server setup' }
    function Wait-Docker { throw 'FORBIDDEN: Docker startup' }
"""
            + body
            + """
    Write-Output '__TEST_COMPLETED__'
}
catch {
    [Console]::Error.WriteLine(($_ | Out-String))
    exit 1
}
""",
            encoding="utf-8-sig",
        )
        environment = os.environ.copy()
        environment["ProgramData"] = str(tmp_path / "program data")
        environment["PSModulePath"] = str(POWERSHELL.parent / "Modules")
        result = subprocess.run(
            [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-File", str(script)],
            cwd=tmp_path, env=environment, capture_output=True, encoding="utf-8",
            errors="replace", timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "__TEST_COMPLETED__" in result.stdout, result.stdout + result.stderr
        return result.stdout

    return run


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / "checkout with spaces and ' apostrophe"
    installer = root / "installer" / "install.ps1"
    installer.parent.mkdir(parents=True)
    shutil.copyfile(INSTALLER, installer)
    shutil.copyfile(ROOT / "installer/downloads.json", installer.with_name("downloads.json"))
    for relative in (
        "dependency-migration/requirements-runner.lock",
        "dependency-migration/requirements-v1.lock",
        "dependency-migration/requirements-v2.lock",
        "security-repair/requirements-task.lock",
        "regression-tests/requirements-task.lock",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="ascii")
    return root, installer


def isolated_installation(root):
    """Replace only the platform predicate; retain actual installation control flow."""
    return f"$fixtureInstallerRoot = {ps_literal(root / 'installer')}\n" + """
$PSScriptRoot = $fixtureInstallerRoot
$definition = [scriptblock]::Create((Get-Command Invoke-Installation).ScriptBlock.ToString())
$guards = @($definition.Ast.FindAll({ param($node)
    $node -is [Management.Automation.Language.IfStatementAst] -and
    $node.Clauses[0].Item1.Extent.Text -match 'Is64BitProcess'
}, $false))
if ($guards.Count -ne 1) { throw 'Expected exactly one installer platform guard' }
$condition = $guards[0].Clauses[0].Item1.Extent
$source = $definition.ToString()
$offset = $condition.StartOffset - $definition.Ast.Extent.StartOffset
$source = $source.Remove($offset, $condition.Text.Length).Insert($offset, '$false')
$source = '$PSScriptRoot = $fixtureInstallerRoot;' + $source
Set-Item Function:Invoke-Installation ([scriptblock]::Create($source))
function Find-Docker { return 'fixture-docker.exe' }
function Test-Wsl { return $true }
function Test-VcRuntime { return $true }
"""


def test_library_only_defines_functions_without_setup(powershell, installation):
    root, installer = installation
    powershell("""
foreach ($name in @('Assert-Payload', 'Get-Payload', 'Expand-SetupZip',
    'Invoke-SetupCommand', 'New-WorkflowShortcuts', 'Invoke-Installation')) {
    if (-not (Get-Command $name -CommandType Function)) { throw "Missing function: $name" }
}
""", installer=installer)
    assert not (root / ".installer").exists()


def test_checksum_mismatch_blocks_execution(powershell, tmp_path):
    payload = tmp_path / "untrusted payload.cmd"
    marker = tmp_path / "executed.txt"
    payload.write_text(f'@echo off\r\necho executed>"{marker}"\r\n', encoding="ascii")
    powershell("""
$failure = $null
try {
    Assert-Payload $case.path ([pscustomobject]@{ sha256 = ('0' * 64) })
    Invoke-SetupCommand $env:ComSpec @('/d', '/c', $case.path)
}
catch { $failure = $_.Exception.Message }
if ($failure -notlike '*Download checksum mismatch*') { throw "Wrong failure: $failure" }
""", data={"path": str(payload)})
    assert not marker.exists()


@pytest.mark.parametrize("corrupted", [False, True], ids=["valid-cache", "corrupt-cache"])
def test_cached_payload_is_verified_without_http(powershell, tmp_path, corrupted):
    cache = tmp_path / "download cache"
    cache.mkdir()
    payload = cache / "artifact.zip"
    expected = b"known pinned content"
    payload.write_bytes(b"corrupted" if corrupted else expected)
    powershell("""
$specification = [pscustomobject]@{
    url = 'https://invalid.example/artifact.zip'; file = 'artifact.zip'; sha256 = $case.sha256
}
$catalog = [pscustomobject]@{ sample = $specification }
$failure = $null
$result = $null
try { $result = Get-Payload 'sample' $case.directory $catalog }
catch { $failure = $_.Exception.Message }
if ($case.corrupted) {
    if ($failure -notlike '*Download checksum mismatch*') { throw "Wrong failure: $failure" }
} else {
    if ($failure) { throw $failure }
    if ($result -cne (Join-Path $case.directory 'artifact.zip')) { throw 'Wrong cached path' }
}
""", data={"directory": str(cache), "sha256": hashlib.sha256(expected).hexdigest(),
           "corrupted": corrupted})
    assert payload.read_bytes() == (b"corrupted" if corrupted else expected)
    assert sorted(path.name for path in cache.iterdir()) == ["artifact.zip"]


@pytest.mark.parametrize("field,value", [
    ("url", "http://invalid.example/payload.zip"),
    ("url", "file:///C:/payload.zip"),
    ("sha256", "bad-hash"),
    ("file", "../escape.zip"),
    ("file", "..\\escape.zip"),
    ("file", "C:\\escape.zip"),
    ("file", "nested/artifact.zip"),
])
def test_invalid_catalog_rejected_before_cache_creation(powershell, tmp_path, field, value):
    cache = tmp_path / "must not exist"
    specification = {"url": "https://invalid.example/payload.zip", "file": "payload.zip",
                     "sha256": "a" * 64}
    specification[field] = value
    powershell("""
$failure = $null
try { Get-Payload 'sample' $case.directory ([pscustomobject]@{ sample = $case.specification }) }
catch { $failure = $_.Exception.Message }
if ($failure -ne 'Invalid download specification.') { throw "Wrong failure: $failure" }
""", data={"directory": str(cache), "specification": specification})
    assert not cache.exists()


def test_download_catalog_has_https_hashes_and_safe_names():
    catalog = json.loads((ROOT / "installer/downloads.json").read_text(encoding="utf-8"))
    assert set(catalog) == {"uv", "ovms", "Docker", "Wsl", "VcRuntime"}
    for specification in catalog.values():
        url = urlsplit(specification["url"])
        assert url.scheme == "https" and url.hostname
        assert re.fullmatch(r"[a-fA-F0-9]{64}", specification["sha256"])
        filename = specification["file"]
        assert PureWindowsPath(filename).name == filename
        assert filename not in {"", ".", ".."} and ":" not in filename
    for name in ("Docker", "Wsl", "VcRuntime"):
        assert catalog[name]["publisher"]


@pytest.mark.parametrize("entry_name,symlink", [
    ("../escape.txt", False), ("..\\escape.txt", False),
    ("nested/../../escape.txt", False), ("/escape.txt", False),
    ("C:/escape.txt", False), ("file.txt:stream", False), ("link", True),
])
def test_unsafe_zip_rejected_before_any_extraction(powershell, tmp_path, entry_name, symlink):
    archive = tmp_path / "unsafe.zip"
    destination = tmp_path / "extract here"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("innocent.txt", "must not be extracted either")
        entry = zipfile.ZipInfo(entry_name)
        entry.create_system = 3
        entry.external_attr = ((stat.S_IFLNK if symlink else stat.S_IFREG) | 0o644) << 16
        bundle.writestr(entry, "../escape.txt" if symlink else "unsafe")
    powershell("""
$failure = $null
try { Expand-SetupZip $case.archive $case.destination }
catch { $failure = $_.Exception }
if ($null -eq $failure) { throw 'Unsafe archive was accepted' }
if ($failure.Message -notlike '*Unsafe archive entry:*') {
    while ($null -ne $failure.InnerException) { $failure = $failure.InnerException }
    if (-not $case.invalid_path -or $failure -isnot [NotSupportedException]) {
        throw "Wrong failure: $failure"
    }
}
""", data={"archive": str(archive), "destination": str(destination),
           "invalid_path": ":" in entry_name})
    assert not destination.exists()
    assert not (tmp_path / "escape.txt").exists()


def test_normal_zip_extracts_into_spaced_path_and_refuses_overwrite(powershell, tmp_path):
    archive = tmp_path / "normal archive.zip"
    destination = tmp_path / "extracted directory with spaces"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("nested directory/", b"")
        bundle.writestr("nested directory/payload.txt", b"exact content\x00\xff")
    powershell("""
Expand-SetupZip $case.archive $case.destination
$failure = $null
try { Expand-SetupZip $case.archive $case.destination }
catch { $failure = $_.Exception.Message }
if ($failure -notlike '*Extraction destination already exists:*') { throw "Wrong failure: $failure" }
""", data={"archive": str(archive), "destination": str(destination)})
    assert (destination / "nested directory/payload.txt").read_bytes() == b"exact content\x00\xff"


@pytest.mark.parametrize("exit_code", [0, 7])
def test_setup_command_propagates_real_cmd_exit(powershell, exit_code):
    powershell("""
$failure = $null
$LASTEXITCODE = 99
try { Invoke-SetupCommand $env:ComSpec @('/d', '/c', ('exit /b ' + $case.exit_code)) }
catch { $failure = $_.Exception.Message }
if ($case.exit_code -eq 0) {
    if ($failure) { throw $failure }
} elseif ($failure -notlike '*exited 7. Setup is incomplete*') { throw "Wrong failure: $failure" }
if ($LASTEXITCODE -ne $case.exit_code) { throw 'Did not observe the real child exit code' }
""", data={"exit_code": exit_code})


@pytest.mark.parametrize("exit_code", [0, 7])
@pytest.mark.parametrize("child", ["cmd", "powershell"])
def test_native_probe_captures_real_stderr_and_exit(powershell, tmp_path, exit_code, child):
    argument = "argument with spaces and ' apostrophe"
    suffix = "cmd" if child == "cmd" else "ps1"
    script = tmp_path / f"probe with spaces and ' apostrophe.{suffix}"
    if child == "cmd":
        script.write_text(
            '@echo off\n echo stdout:%~1\n echo stderr:%~1 1>&2\n'
            f'exit /b {exit_code}\n', encoding="ascii",
        )
        executable = os.environ["ComSpec"]
        arguments = ["/d", "/c", "call", str(script), argument]
    else:
        script.write_text(
            "param([string]$Value)\n"
            "[Console]::Out.WriteLine('stdout:' + $Value)\n"
            "[Console]::Error.WriteLine('stderr:' + $Value)\n"
            f"exit {exit_code}\n", encoding="utf-8-sig",
        )
        executable = str(POWERSHELL)
        arguments = ["-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                     "Bypass", "-File", str(script), argument]
    powershell("""
$LASTEXITCODE = 99
$results = @(Invoke-NativeProbe $case.executable $case.arguments)
if ($results.Count -ne 1) { throw 'Probe leaked output instead of returning one result' }
$result = $results[0]
if ($result.ExitCode -ne $case.exit_code) {
    throw "Wrong exit: $($result.ExitCode); output: $($result.Output)"
}
foreach ($stream in @('stdout:', 'stderr:')) {
    if (-not $result.Output.Contains($stream + $case.argument)) {
        throw "Missing or misquoted stream: $stream in $($result.Output)"
    }
}
if ($ErrorActionPreference -ne 'Stop') { throw 'Probe changed caller error preference' }
""", data={"executable": executable, "arguments": arguments, "argument": argument,
           "exit_code": exit_code})


@pytest.mark.parametrize("version_exit,status_exit", [(7, 0), (0, 7), (0, 0)])
def test_wsl_checks_probe_exit_codes_in_order(powershell, version_exit, status_exit):
    powershell(r"""
$script:probes = @()
function Test-Path {
    param([string]$LiteralPath)
    if ($LiteralPath -ne (Join-Path $env:SystemRoot 'System32\wsl.exe')) {
        throw "Unexpected path: $LiteralPath"
    }
    return $true
}
function Invoke-NativeProbe {
    param([string]$File, [string[]]$Arguments)
    if ($File -ne (Join-Path $env:SystemRoot 'System32\wsl.exe')) { throw 'Wrong WSL executable' }
    $script:probes += $Arguments -join ' '
    switch ($Arguments -join ' ') {
        '--version' { return [pscustomobject]@{ ExitCode = $case.version_exit; Output = 'WSL version: 3.0.3.0' } }
        '--status' { return [pscustomobject]@{ ExitCode = $case.status_exit; Output = 'stderr: status' } }
        default { throw 'Unexpected WSL arguments' }
    }
}
$result = Test-Wsl
$expected = $case.version_exit -eq 0 -and $case.status_exit -eq 0
if ($result -ne $expected) { throw 'WSL readiness ignored probe exit code' }
$calls = if ($case.version_exit -eq 0) { '--version,--status' } else { '--version' }
if (($script:probes -join ',') -cne $calls) { throw 'Wrong WSL probe order or short circuit' }
""", data={"version_exit": version_exit, "status_exit": status_exit})


@pytest.mark.parametrize("version_output,ready", [
    ("WSL version: 1.2.5", False),
    ("WSL version: 2.1.4", False),
    ("WSL version: 2.1.5", True),
    ("WSL version: 3.0.3", True),
    ("garbled output", False),
    ("\x00".join("WSL version: 2.1.5") + "\x00", True),
    ("WSL version: 1.2.5\nKernel version: 5.15.167.4", False),
    ("WSL version: 2.1.5\nOther version: 1.2.5", True),
], ids=["old-major", "below-minimum", "minimum", "new-major", "garbled",
        "nul-interspersed", "first-version-too-old", "first-version-supported"])
def test_wsl_requires_first_version_at_least_2_1_5(powershell, version_output, ready):
    powershell(r"""
$script:probes = @()
$script:pathChecks = 0
function Test-Path {
    param([string]$LiteralPath)
    if ($LiteralPath -cne (Join-Path $env:SystemRoot 'System32\wsl.exe')) {
        throw "Unexpected path: $LiteralPath"
    }
    $script:pathChecks++
    return $true
}
function Invoke-NativeProbe {
    param([string]$File, [string[]]$Arguments)
    if ($File -cne (Join-Path $env:SystemRoot 'System32\wsl.exe') -or
        $Arguments.Count -ne 1) { throw 'Wrong WSL probe' }
    $script:probes += $Arguments[0]
    switch ($Arguments[0]) {
        '--version' { return [pscustomobject]@{ ExitCode = 0; Output = $case.output } }
        '--status' {
            if (-not $case.ready) { throw 'Status must not run for unsupported version output' }
            return [pscustomobject]@{ ExitCode = 0; Output = 'ready' }
        }
        default { throw 'Unexpected WSL arguments' }
    }
}
$results = @(Test-Wsl)
if ($results.Count -ne 1 -or $results[0] -isnot [bool] -or $results[0] -ne $case.ready) {
    throw 'WSL readiness did not enforce the first version and minimum 2.1.5'
}
$expected = if ($case.ready) { '--version,--status' } else { '--version' }
if ($script:pathChecks -ne 1 -or ($script:probes -join ',') -cne $expected) {
    throw 'Wrong WSL probe order or version short circuit'
}
""", data={"output": version_output, "ready": ready})


@pytest.mark.parametrize("refresh", [False, True], ids=["reuse", "refresh"])
@pytest.mark.parametrize("exit_code", [None, 0, 7], ids=["null-exit", "success", "failure"])
def test_workflow_preparation_launch_contract(powershell, installation, refresh, exit_code):
    root, installer = installation
    runner = root / "runner with spaces and ' apostrophe" / "python.exe"
    arguments = f'-B "{installer.with_name("prepare_workflows.py")}" --root "{root}"'
    if refresh:
        arguments += " --refresh"
    powershell("""
$script:launches = @()
function Start-Process {
    [CmdletBinding()]
    param([string]$FilePath, [string[]]$ArgumentList, [string]$WorkingDirectory,
          [string]$WindowStyle, [switch]$Wait, [switch]$PassThru)
    $script:launches += @{
        FilePath = $FilePath; ArgumentList = $ArgumentList; WorkingDirectory = $WorkingDirectory
        WindowStyle = $WindowStyle; Wait = $Wait.IsPresent; PassThru = $PassThru.IsPresent
    }
    return [pscustomobject]@{ ExitCode = $case.exit_code }
}
$failure = $null
try { Invoke-WorkflowPreparation $case.runner $case.root $case.refresh }
catch { $failure = $_.Exception.Message }
if ($script:launches.Count -ne 1) { throw 'Expected exactly one preparation process' }
$launch = $script:launches[0]
if ($launch.FilePath -cne $case.runner -or $launch.WorkingDirectory -cne $case.root -or
    $launch.ArgumentList.Count -ne 1 -or $launch.ArgumentList[0] -cne $case.arguments) {
    throw 'Wrong preparation executable, quoted arguments, or working directory'
}
if ($launch.WindowStyle -cne 'Normal' -or -not $launch.Wait -or -not $launch.PassThru) {
    throw 'Preparation must use a visible window, wait, and return its process'
}
if ($null -ne $case.exit_code -and $case.exit_code -eq 0) {
    if ($null -ne $failure) { throw $failure }
} else {
    $expected = "Workflow preparation exited $($case.exit_code). See installation-local generation logs; setup is incomplete."
    if ($failure -cne $expected) { throw "Wrong preparation failure: $failure" }
}
""", installer=installer, data={"runner": str(runner), "root": str(root),
           "arguments": arguments, "refresh": refresh, "exit_code": exit_code})
    assert not (root / ".installer").exists()
    assert not (root / "dependency-migration/artifacts").exists()


@pytest.mark.parametrize("exit_code", [0, 7])
def test_workflow_preparation_checks_real_child_exit(powershell, installation, exit_code):
    root, installer = installation
    runner = root / "benign runner with spaces and ' apostrophe.cmd"
    runner.write_text(f"@echo off\nexit /b {exit_code}\n", encoding="ascii")
    powershell(r"""
$script:launches = 0
$script:observedExit = $null
function Start-Process {
    [CmdletBinding()]
    param([string]$FilePath, [string[]]$ArgumentList, [string]$WorkingDirectory,
          [string]$WindowStyle, [switch]$Wait, [switch]$PassThru)
    if ($FilePath -cne $case.runner -or $WorkingDirectory -cne $case.root -or
        $WindowStyle -cne 'Normal' -or -not $Wait -or -not $PassThru) {
        throw 'FORBIDDEN: unexpected child launch'
    }
    $script:launches++
    if ($script:launches -ne 1) { throw 'FORBIDDEN: repeated child launch' }
    $process = Microsoft.PowerShell.Management\Start-Process @PSBoundParameters
    $script:observedExit = $process.ExitCode
    return $process
}
$failure = $null
try { Invoke-WorkflowPreparation $case.runner $case.root $false }
catch { $failure = $_.Exception.Message }
if ($script:launches -ne 1 -or $null -eq $script:observedExit -or
    $script:observedExit -ne $case.exit_code) { throw 'Did not observe the real child exit code' }
if ($case.exit_code -eq 0) {
    if ($null -ne $failure) { throw $failure }
} elseif ($failure -cne 'Workflow preparation exited 7. See installation-local generation logs; setup is incomplete.') {
    throw "Wrong preparation failure: $failure"
}
""", installer=installer, data={"runner": str(runner), "root": str(root), "exit_code": exit_code})
    assert not (root / ".installer").exists()
    assert not (root / "dependency-migration/artifacts").exists()


@pytest.mark.parametrize("first_exit,first_output", [(7, "linux"), (0, "windows")])
def test_wait_docker_retries_probe_then_selects_linux(powershell, tmp_path, first_exit, first_output):
    docker = tmp_path / "Docker/resources/bin/docker.exe"
    powershell("""
Set-Item Function:Wait-Docker $installerFunctions['Wait-Docker']
$script:probes = 0
$env:DOCKER_HOST = 'tcp://forbidden.invalid:2375'
$env:DOCKER_TLS_VERIFY = '1'
$env:DOCKER_CERT_PATH = 'forbidden-certificates'
$env:DOCKER_CONTEXT = 'wrong-context'
function Invoke-NativeProbe {
    param([string]$File, [string[]]$Arguments)
    if ($File -cne $case.docker -or
        ($Arguments -join '|') -cne '--context|desktop-linux|info|--format|{{.OSType}}') {
        throw 'Unexpected Docker probe'
    }
    $script:probes++
    if ($script:probes -eq 1) {
        return [pscustomobject]@{ ExitCode = $case.first_exit; Output = $case.first_output }
    }
    if ($script:probes -ne 2) { throw 'Docker did not accept the ready Linux engine' }
    return [pscustomobject]@{ ExitCode = 0; Output = " linux`r`n" }
}
Wait-Docker $case.docker
if ($script:probes -ne 2) { throw 'Transient probe was not retried' }
if ($env:DOCKER_CONTEXT -cne 'desktop-linux') { throw 'Wrong Docker context' }
foreach ($name in @('DOCKER_HOST', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')) {
    if (Test-Path ('Env:' + $name)) { throw "Inherited Docker setting remains: $name" }
}
""", data={"docker": str(docker), "first_exit": first_exit, "first_output": first_output})
    assert not docker.parent.parent.parent.exists()


@pytest.mark.parametrize("exit_code,version", [
    (0, "stderr warning\nOpenVINO Model Server 2026.4.0"),
    (7, "OpenVINO Model Server 2026.4.0\nstderr failure"),
    (0, "OpenVINO Model Server 2025.4.0"),
])
def test_ovms_version_uses_probe_exit_and_output(powershell, installation, exit_code, version):
    root, installer = installation
    executable = root / "ovms_downloaded/windows-2026.4.0-python-on/ovms/ovms.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"not executable: probe must be mocked")
    powershell(r"""
Set-Item Function:Ensure-Ovms $installerFunctions['Ensure-Ovms']
function Get-Payload { throw 'FORBIDDEN: OVMS download' }
$script:probes = 0
function Invoke-NativeProbe {
    param([string]$File, [string[]]$Arguments)
    if ($File -cne (Join-Path $case.root 'models\start-27b-article.cmd') -or
        $Arguments.Count -ne 1 -or $Arguments[0] -cne '--version') { throw 'Wrong OVMS probe' }
    $script:probes++
    return [pscustomobject]@{ ExitCode = $case.exit_code; Output = $case.version }
}
$failure = $null
try { Ensure-Ovms $case.root (Join-Path $case.root '.installer') ([pscustomobject]@{}) }
catch { $failure = $_.Exception.Message }
if ($script:probes -ne 1) { throw 'OVMS did not use one native probe' }
if ($case.exit_code -eq 0 -and $case.version.Contains('2026.4.0')) {
    if ($failure) { throw $failure }
} elseif ($failure -cne ('OVMS version check failed: ' + $case.version)) {
    throw "Wrong OVMS failure: $failure"
}
""", installer=installer, data={"root": str(root), "exit_code": exit_code, "version": version})


@pytest.mark.parametrize("license_accepted,refresh,no_shortcuts", [
    (False, False, False), (True, False, False), (False, True, False),
    (False, False, True), (True, True, True),
])
def test_resume_shortcut_persists_pending_and_flags(
    powershell, installation, tmp_path, license_accepted, refresh, no_shortcuts,
):
    root, installer = installation
    state = root / ".installer"
    state.mkdir()
    startup = tmp_path / "temporary per-user Startup"
    powershell(r"""
$path = Get-ResumeShortcut $case.state $case.startup
if ($path -cne (Get-ResumeShortcut $case.state.ToUpperInvariant() $case.startup)) {
    throw 'Resume identity is not case insensitive'
}
if ($path -eq (Get-ResumeShortcut ($case.state + '-other') $case.startup)) {
    throw 'Different installations share a resume shortcut'
}
foreach ($attempt in 1..2) {
    Register-SetupResume $case.state $case.startup $case.license $case.refresh $case.no_shortcuts
    if (-not (Test-Path -LiteralPath (Join-Path $case.state 'resume.pending'))) {
        throw 'Missing persistent pending marker'
    }
    $links = @(Get-ChildItem -LiteralPath $case.startup -Filter '*.lnk')
    if ($links.Count -ne 1 -or $links[0].FullName -cne $path) { throw 'Resume link is not idempotent' }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($path)
    if ($shortcut.TargetPath -ine (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe')) {
        throw 'Wrong resume executable'
    }
    $expected = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -Resume' -f $case.installer
    if ($case.license) { $expected += ' -AcceptDockerLicense' }
    if ($case.refresh) { $expected += ' -RefreshWorkflows' }
    if ($case.no_shortcuts) { $expected += ' -NoShortcuts' }
    if ($shortcut.Arguments -cne $expected) { throw "Wrong resume flags: $($shortcut.Arguments)" }
    if ($shortcut.WorkingDirectory -ine (Split-Path $case.state)) { throw 'Wrong resume directory' }
}
""", installer=installer, data={"state": str(state), "startup": str(startup),
           "installer": str(installer), "license": license_accepted, "refresh": refresh,
           "no_shortcuts": no_shortcuts})
    assert "Setup is incomplete" in (state / "resume.pending").read_text(encoding="utf-8-sig")
    assert len(list(startup.glob("*.lnk"))) == 1


def test_resume_without_pending_returns_before_prerequisite_probes(powershell, installation):
    root, installer = installation
    installer.with_name("downloads.json").unlink()
    output = powershell(isolated_installation(root) + """
$Resume = $true
function Find-Docker { throw 'FORBIDDEN: Docker probe' }
function Test-Wsl { throw 'FORBIDDEN: WSL probe' }
function Test-VcRuntime { throw 'FORBIDDEN: VC runtime probe' }
function Get-CimInstance { throw 'FORBIDDEN: platform probe' }
function New-Item { throw 'FORBIDDEN: directory creation' }
function Start-Transcript { throw 'FORBIDDEN: transcript creation' }
function Invoke-SetupCommand { throw 'FORBIDDEN: workflow provisioning' }
function New-WorkflowShortcuts { throw 'FORBIDDEN: shortcut creation' }
function Register-SetupResume { throw 'FORBIDDEN: resume registration' }
function Get-ResumeShortcut { throw 'FORBIDDEN: Startup access' }
$result = @(Invoke-Installation)
if ($result.Count -ne 1 -or $result[0] -ne 0) { throw 'Resume no-op did not return zero' }
""", installer=installer)
    assert not (root / ".installer").exists()
    assert "SETUP COMPLETE" not in output


@pytest.mark.parametrize("docker_missing,license_accepted,refresh,no_shortcuts", [
    (True, False, True, True), (False, False, False, False),
    (False, True, True, False), (True, True, False, True),
])
def test_installation_restart_registers_resume_before_provisioning(
    powershell, installation, docker_missing, license_accepted, refresh, no_shortcuts,
):
    root, installer = installation
    output = powershell(isolated_installation(root) + """
$AcceptDockerLicense = [bool]$case.license
$RefreshWorkflows = [bool]$case.refresh
$NoShortcuts = [bool]$case.no_shortcuts
$script:events = @()
$script:registration = $null
function Find-Docker { if (-not $case.docker_missing) { return 'fixture-docker.exe' } }
function Test-Wsl { return $false }
function Test-VcRuntime { return $false }
function Start-Transcript { $script:events += 'start' }
function Stop-Transcript { $script:events += 'stop' }
function Confirm-DockerLicense { $script:events += 'license' }
function Request-SystemStage {
    param([string[]]$Names)
    $expected = 'VcRuntime,Wsl'
    if ($case.docker_missing) { $expected += ',Docker' }
    if (($Names -join ',') -cne $expected) { throw 'Wrong system stage components' }
    $script:events += 'system'
    return 3010
}
function Register-SetupResume {
    param($State, $StartupDirectory, $LicenseAccepted, $Refresh, $SkipDesktop)
    $script:events += 'register'
    $script:registration = @($State, $StartupDirectory, $LicenseAccepted, $Refresh, $SkipDesktop)
}
function Invoke-SetupCommand { throw 'FORBIDDEN: workflow provisioning' }
function New-WorkflowShortcuts { throw 'FORBIDDEN: shortcut creation' }
function Get-ResumeShortcut { throw 'FORBIDDEN: Startup cleanup' }
$result = @(Invoke-Installation)
if ($result.Count -ne 1 -or $result[0] -ne 3010) { throw 'Restart result was not propagated' }
$expectedEvents = if ($case.docker_missing -and -not $case.license) {
    'start,license,system,register,stop'
} else { 'start,system,register,stop' }
if (($script:events -join ',') -cne $expectedEvents) { throw 'Wrong restart sequence' }
$state = Join-Path $case.root '.installer'
$record = $script:registration
if ($null -eq $record -or $record.Count -ne 5 -or $record[0] -cne $state -or
    $record[1] -cne [Environment]::GetFolderPath('Startup') -or
    $record[2] -ne ($case.license -or $case.docker_missing) -or
    $record[3] -ne $case.refresh -or $record[4] -ne $case.no_shortcuts) {
    throw 'Wrong resume registration arguments'
}
$lock = [IO.File]::Open((Join-Path $state 'setup.lock'), 'Open', 'ReadWrite', 'None')
$lock.Dispose()
""", installer=installer, data={"root": str(root), "docker_missing": docker_missing,
           "license": license_accepted, "refresh": refresh, "no_shortcuts": no_shortcuts})
    assert "RESTART REQUIRED" in output
    assert "SETUP COMPLETE" not in output
    assert sorted(path.name for path in (root / ".installer").iterdir()) == ["setup.lock"]
    assert not (root / "dependency-migration/artifacts/installation-local").exists()


@pytest.mark.parametrize("failure_stage", ["docker", "provision"])
def test_failed_resume_retains_pending_and_startup_link(powershell, installation, tmp_path, failure_stage):
    root, installer = installation
    state = root / ".installer"
    state.mkdir()
    startup = tmp_path / "temporary Startup"
    output = powershell(isolated_installation(root) + """
Register-SetupResume $case.state $case.startup $true $true $true
$link = Get-ResumeShortcut $case.state $case.startup
$linkHash = (Get-FileHash -LiteralPath $link).Hash
$pending = Join-Path $case.state 'resume.pending'
$pendingHash = (Get-FileHash -LiteralPath $pending).Hash
$Resume = $true
$NoShortcuts = $true
$script:events = @()
function Start-Transcript { $script:events += 'start' }
function Stop-Transcript { $script:events += 'stop' }
function Wait-Docker {
    $script:events += 'docker'
    if ($case.stage -eq 'docker') { throw 'INJECTED: docker' }
}
if ($case.stage -eq 'provision') {
    function Ensure-Uv { $script:events += 'uv'; return 'fixture-uv.exe' }
    function Ensure-Runner { $script:events += 'runner'; return 'fixture-python.exe' }
    function Ensure-Ovms { $script:events += 'ovms' }
}
function Invoke-WorkflowPreparation { $script:events += 'provision'; throw 'INJECTED: provision' }
function New-WorkflowShortcuts { throw 'FORBIDDEN: shortcut creation' }
function Register-SetupResume { throw 'FORBIDDEN: resume reregistration' }
function Get-ResumeShortcut { throw 'FORBIDDEN: Startup cleanup after failure' }
$failure = $null
try { Invoke-Installation }
catch { $failure = $_.Exception.Message }
if ($failure -cne ('INJECTED: ' + $case.stage)) { throw "Wrong resume failure: $failure" }
$expected = if ($case.stage -eq 'docker') { 'start,docker,stop' } else {
    'start,docker,uv,runner,ovms,provision,stop'
}
if (($script:events -join ',') -cne $expected) { throw 'Wrong failed resume sequence' }
if ((Get-FileHash -LiteralPath $link).Hash -cne $linkHash -or
    (Get-FileHash -LiteralPath $pending).Hash -cne $pendingHash) { throw 'Resume state changed on failure' }
$lock = [IO.File]::Open((Join-Path $case.state 'setup.lock'), 'Open', 'ReadWrite', 'None')
$lock.Dispose()
""", installer=installer, data={"state": str(state), "startup": str(startup), "stage": failure_stage})
    assert (state / "resume.pending").exists()
    assert len(list(startup.glob("*.lnk"))) == 1
    assert "SETUP COMPLETE" not in output


def test_three_real_shortcuts_target_workflows_and_local_manifest(powershell, installation, tmp_path):
    root, installer = installation
    destination = tmp_path / "temporary shortcuts"
    powershell(r"""
New-WorkflowShortcuts $case.root $case.destination
$shell = New-Object -ComObject WScript.Shell
$expected = [ordered]@{
    'Dependency Migration' = 'dependency-migration'
    'Security Repair' = 'security-repair'
    'Regression Tests' = 'regression-tests'
}
$links = @(Get-ChildItem -LiteralPath $case.destination -Filter '*.lnk')
if ($links.Count -ne 3) { throw "Expected three shortcuts, got $($links.Count)" }
foreach ($label in $expected.Keys) {
    $path = Join-Path $case.destination ('AI PC - ' + $label + '.lnk')
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing shortcut: $label" }
    $shortcut = $shell.CreateShortcut($path)
    $target = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $controller = Join-Path $case.root 'dependency-migration\demo-controller.ps1'
    $manifest = Join-Path $case.root 'dependency-migration\artifacts\installation-local\workflows.json'
    $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -Workflow "{1}" -InstallationManifest "{2}"' -f $controller, $expected[$label], $manifest
    if ($shortcut.TargetPath -ine $target) { throw "Wrong target: $($shortcut.TargetPath)" }
    if ($shortcut.Arguments -cne $arguments) { throw "Wrong arguments: $($shortcut.Arguments)" }
    if ($shortcut.WorkingDirectory -ine $case.root) { throw 'Wrong working directory' }
}
""", installer=installer, data={"root": str(root), "destination": str(destination)})
    assert len(list(destination.glob("*.lnk"))) == 3


@pytest.mark.parametrize("missing_prerequisites", [False, True])
def test_check_only_is_read_only_and_never_elevates(powershell, installation, missing_prerequisites):
    root, installer = installation
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    output = powershell(isolated_installation(root) + """
$CheckOnly = $true
if ($case.missing) {
    function Find-Docker { return $null }
    function Test-Wsl { return $false }
    function Test-VcRuntime { return $false }
}
function Test-Administrator { throw 'FORBIDDEN: administrator check' }
function New-Item { throw 'FORBIDDEN: directory creation' }
function Start-Transcript { throw 'FORBIDDEN: log creation' }
function Invoke-SetupCommand { throw 'FORBIDDEN: setup command' }
function New-WorkflowShortcuts { throw 'FORBIDDEN: shortcut creation' }
$result = Invoke-Installation
if ($result -ne 0) { throw "CheckOnly returned $result" }
""", installer=installer, data={"missing": missing_prerequisites})
    assert "WslReady" in output and "WorkflowsManifestPresent" in output
    assert not (root / ".installer").exists()
    after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert after == before


def test_setup_lock_blocks_competitor_and_releases_after_failure(powershell, installation):
    root, installer = installation
    powershell(isolated_installation(root) + """
$state = Join-Path (Split-Path $PSScriptRoot) '.installer'
New-Item -ItemType Directory -Path $state | Out-Null
$lockPath = Join-Path $state 'setup.lock'
$script:started = 0
$script:stopped = 0
function Start-Transcript { $script:started++ }
function Stop-Transcript { $script:stopped++ }
function Wait-Docker { throw 'INJECTED: stop before Docker' }
$held = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
try {
    $failure = $null
    try { Invoke-Installation }
    catch { $failure = $_.Exception }
    if ($null -eq $failure) { throw 'Concurrent installer acquired the lock' }
    while ($null -ne $failure.InnerException) { $failure = $failure.InnerException }
    if ($failure -isnot [IO.IOException]) { throw "Expected sharing violation: $failure" }
    if ($script:started -ne 0) { throw 'Contending installer entered installation' }
} finally { $held.Dispose() }
foreach ($attempt in 1..2) {
    $failure = $null
    try { Invoke-Installation }
    catch { $failure = $_.Exception.Message }
    if ($failure -ne 'INJECTED: stop before Docker') { throw "Wrong failure: $failure" }
    $probe = [IO.File]::Open($lockPath, 'Open', 'ReadWrite', 'None')
    $probe.Dispose()
}
if ($script:started -ne 2 -or $script:stopped -ne 2) { throw 'Transcript cleanup mismatch' }
""", installer=installer)
    assert (root / ".installer/setup.lock").exists()


@pytest.mark.parametrize("names", [["Unknown"], ["Docker", "Unknown"], [""]])
def test_system_stage_rejects_bad_components_before_creating_folders(powershell, tmp_path, names):
    powershell("""
function Test-Administrator { return $true }
function New-Item { throw 'FORBIDDEN: staging directory creation' }
function Get-Payload { throw 'FORBIDDEN: payload retrieval' }
function Get-WindowsOptionalFeature { throw 'FORBIDDEN: system feature query' }
$failure = $null
try { Invoke-SystemStage $case.names ([pscustomobject]@{}) }
catch { $failure = $_.Exception.Message }
if ($failure -notlike 'Unsupported prerequisite:*') { throw "Wrong failure: $failure" }
""", data={"names": names})
    assert not (tmp_path / "program data").exists()


def test_all_repository_powershell_sources_parse_in_windows_powershell(powershell):
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
         "--", "*.ps1", "*.psm1", "*.psd1"],
        cwd=ROOT, capture_output=True, check=True,
    )
    paths = sorted({str(ROOT / os.fsdecode(path)) for path in result.stdout.split(b"\0") if path})
    assert str(INSTALLER) in paths
    powershell("""
foreach ($path in $case.paths) {
    $tokens = $null
    $parseErrors = $null
    $null = [Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count) { throw "$path : $($parseErrors | Out-String)" }
}
""", data={"paths": paths})