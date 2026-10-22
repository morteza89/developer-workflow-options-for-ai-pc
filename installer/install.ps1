#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$RefreshWorkflows,
    [switch]$AcceptDockerLicense,
    [switch]$NoShortcuts,
    [switch]$Resume,
    [switch]$LibraryOnly,
    [switch]$SystemStage,
    [string]$Components
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Setup([string]$Message) {
    Write-Host ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $Message)
}

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-SetupCommand([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$File exited $LASTEXITCODE. Setup is incomplete; retry after resolving the error." }
}

function Invoke-NativeProbe([string]$File, [string[]]$Arguments) {
    $ErrorActionPreference = 'Continue'
    $output = & $File @Arguments 2>&1
    $code = $LASTEXITCODE
    return [pscustomobject]@{ ExitCode = $code; Output = ($output | ForEach-Object { $_.ToString() }) -join "`n" }
}

function Assert-Payload([string]$Path, $Specification) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf) -or
        (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ine $Specification.sha256) {
        throw "Download checksum mismatch: $Path. No downloaded program was executed. Remove this cached file and retry."
    }
    if ($Specification.PSObject.Properties['publisher']) {
        $signature = Get-AuthenticodeSignature -LiteralPath $Path
        if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate -or
            $signature.SignerCertificate.Subject -notmatch ('(?:^|,\s*)O="?' + [regex]::Escape($Specification.publisher) + '"?(?:,|$)')) {
            throw "Invalid Authenticode signature or publisher: $Path"
        }
    }
}

function Get-Payload([string]$Name, [string]$Directory, $Catalog) {
    $specification = $Catalog.$Name
    if ($specification.url -notmatch '^https://' -or $specification.sha256 -notmatch '^[a-fA-F0-9]{64}$' -or
        [IO.Path]::GetFileName($specification.file) -cne $specification.file) { throw 'Invalid download specification.' }
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $destination = Join-Path $Directory $specification.file
    if (-not (Test-Path -LiteralPath $destination)) {
        $partial = $destination + '.partial'
        Write-Setup "Downloading $Name. Large runtime downloads may take several minutes: $($specification.url)"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $previousProgress = $ProgressPreference
        try {
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $specification.url -UseBasicParsing -OutFile $partial
            Assert-Payload $partial $specification
            Move-Item -LiteralPath $partial -Destination $destination
        }
        finally { $ProgressPreference = $previousProgress }
    }
    Assert-Payload $destination $specification
    return $destination
}

function Expand-SetupZip([string]$Archive, [string]$Destination) {
    if (Test-Path -LiteralPath $Destination) { throw "Extraction destination already exists: $Destination" }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $prefix = [IO.Path]::GetFullPath($Destination).TrimEnd('\') + '\'
    $zip = [IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        foreach ($entry in $zip.Entries) {
            $resolved = [IO.Path]::GetFullPath((Join-Path $Destination $entry.FullName))
            if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
                $entry.FullName -match '(^[\\/]|:|(^|[\\/])\.\.([\\/]|$))' -or
                (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) {
                throw "Unsafe archive entry: $($entry.FullName)"
            }
        }
    }
    finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($Archive, $Destination)
}

function Find-Docker {
    $command = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($path in @("$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe", "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe")) {
        if (Test-Path -LiteralPath $path) { return $path }
    }
    return $null
}

function Test-VcRuntime {
    $runtime = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction SilentlyContinue
    return ($null -ne $runtime -and $runtime.Installed -eq 1 -and [version]$runtime.Version.TrimStart('v') -ge [version]'14.40.33810.0')
}

function Test-Wsl {
    $wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
    if (-not (Test-Path -LiteralPath $wsl)) { return $false }
    $version = Invoke-NativeProbe $wsl @('--version')
    if ($version.ExitCode -ne 0) { return $false }
    $number = [regex]::Match(($version.Output -replace "`0", ''), '\d+\.\d+\.\d+(?:\.\d+)?')
    if (-not $number.Success -or [version]$number.Value -lt [version]'2.1.5') { return $false }
    $status = Invoke-NativeProbe $wsl @('--status')
    return ($status.ExitCode -eq 0)
}

function Invoke-SystemStage([string[]]$Names, $Catalog) {
    if (-not (Test-Administrator)) { throw 'Windows administrator approval is required for system prerequisites.' }
    foreach ($name in $Names) {
        if ($name -notin @('Wsl', 'VcRuntime', 'Docker')) { throw "Unsupported prerequisite: $name" }
    }
    $staging = Join-Path $env:ProgramData ('AI-PC-Workflow-Setup\' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @('S-1-5-18', 'S-1-5-32-544')) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            (New-Object Security.Principal.SecurityIdentifier($sid)), 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $staging -AclObject $acl
    $restart = $false
    try {
        foreach ($name in @('VcRuntime', 'Wsl', 'Docker') | Where-Object { $_ -in $Names }) {
            if ($name -eq 'Wsl') {
                foreach ($feature in @('Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform')) {
                    if ((Get-WindowsOptionalFeature -Online -FeatureName $feature).State -ne 'Enabled') {
                        $result = Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart
                        if ($result.RestartNeeded) { $restart = $true }
                    }
                }
            }
            if ($name -eq 'Docker' -and $restart) { break }
            $payload = Get-Payload $name $staging $Catalog
            Assert-Payload $payload $Catalog.$name
            if ($name -eq 'Wsl') {
                $process = Start-Process msiexec.exe -ArgumentList ('/i "{0}" /qn /norestart' -f $payload) -PassThru -Wait
            }
            else {
                $arguments = if ($name -eq 'Docker') { 'install --quiet --accept-license --backend=wsl-2 --always-run-service' } else { '/install /quiet /norestart' }
                $process = Start-Process -FilePath $payload -ArgumentList $arguments -PassThru -Wait
            }
            if ($process.ExitCode -in @(3010, 1641)) { $restart = $true }
            elseif ($process.ExitCode -ne 0) { throw "$name installation exited $($process.ExitCode)." }
        }
    }
    finally { Remove-Item -LiteralPath $staging -Recurse -Force }
    if ($restart) { return 3010 }
    return 0
}

function Request-SystemStage([string[]]$Names) {
    $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -SystemStage -Components "{1}"' -f $PSCommandPath, ($Names -join ',')
    Write-Setup 'Windows may request administrator approval for missing system prerequisites.'
    $process = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList $arguments -Verb RunAs -PassThru -Wait
    if ($process.ExitCode -notin @(0, 3010)) { throw "System prerequisite installation exited $($process.ExitCode). Rerun Install.cmd to retry." }
    return $process.ExitCode
}

function Confirm-DockerLicense {
    Add-Type -AssemblyName System.Windows.Forms
    $answer = [Windows.Forms.MessageBox]::Show(
        'Docker Desktop is required. By choosing Yes you accept the Docker Subscription Service Agreement (https://www.docker.com/legal/docker-subscription-service-agreement/). Paid subscriptions are required for some organizations, including government entities. Choose No to stop without installing Docker.',
        'Docker Desktop License', 'YesNo', 'Question')
    if ($answer -ne 'Yes') { throw 'Docker license not accepted. No Docker installation was started.' }
}

function Wait-Docker([string]$Docker) {
    $env:PATH = (Split-Path $Docker) + ';' + $env:PATH
    $desktop = Join-Path (Split-Path (Split-Path (Split-Path $Docker))) 'Docker Desktop.exe'
    if (Test-Path -LiteralPath $desktop) { Start-Process -FilePath $desktop | Out-Null }
    Write-Setup 'Starting Docker Desktop. Waiting up to five minutes for the local Linux engine; finish any Docker first-run screen.'
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $details = Invoke-NativeProbe $Docker @('--context', 'desktop-linux', 'info', '--format', '{{.OSType}}')
        if ($details.ExitCode -eq 0 -and $details.Output.Trim() -eq 'linux') {
            $env:DOCKER_CONTEXT = 'desktop-linux'
            Remove-Item Env:DOCKER_HOST -ErrorAction SilentlyContinue
            Remove-Item Env:DOCKER_TLS_VERIFY, Env:DOCKER_CERT_PATH -ErrorAction SilentlyContinue
            return
        }
        $waiter = New-Object Threading.ManualResetEvent($false)
        try { $waiter.WaitOne(2000) | Out-Null } finally { $waiter.Dispose() }
    } while ($timer.Elapsed.TotalSeconds -lt 300)
    throw 'Docker Linux engine did not become ready. Open Docker Desktop, resolve its reported WSL/virtualization error, and rerun Install.cmd. No workflow was marked ready.'
}

function Ensure-Uv([string]$State, $Catalog) {
    $directory = Join-Path $State 'uv-0.12.7'
    $executable = Join-Path $directory 'uv.exe'
    if (-not (Test-Path -LiteralPath $executable)) {
        $archive = Get-Payload 'uv' (Join-Path $State 'downloads') $Catalog
        $staging = Join-Path $State ('uv-stage-' + [guid]::NewGuid().ToString('N'))
        Expand-SetupZip $archive $staging
        $candidates = @(Get-ChildItem -LiteralPath $staging -Filter uv.exe -Recurse)
        if ($candidates.Count -ne 1) { throw 'Pinned uv archive did not contain exactly one uv.exe.' }
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
        Copy-Item -LiteralPath $candidates[0].FullName -Destination $executable
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    $version = & $executable --version
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^uv 0\.12\.7(?:\s|$)') { throw 'Unexpected uv executable/version.' }
    $env:PATH = $directory + ';' + $env:PATH
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $State 'python'
    return $executable
}

function Ensure-Runner([string]$Root, [string]$Uv) {
    Remove-Item Env:PYTHONHOME, Env:PYTHONPATH, Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
    $runnerDirectory = Join-Path $Root 'dependency-migration\.venv-runner'
    $runner = Join-Path $runnerDirectory 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $runner)) {
        if (Test-Path -LiteralPath $runnerDirectory) { throw 'An incomplete runner directory exists. Move it aside before retrying; setup will not delete your environment.' }
        Invoke-SetupCommand $Uv @('python', 'install', '3.11.15') | Out-Host
        Invoke-SetupCommand $Uv @('venv', '--python', '3.11.15', $runnerDirectory) | Out-Host
    }
    Invoke-SetupCommand $runner @('-I', '-c', 'import sys; assert sys.version_info[:3] == (3,11,15), sys.version') | Out-Host
    Invoke-SetupCommand $Uv @('pip', 'sync', '--python', $runner, '--require-hashes', (Join-Path $Root 'dependency-migration\requirements-runner.lock')) | Out-Host
    return $runner
}

function Ensure-Ovms([string]$Root, [string]$State, $Catalog) {
    $directory = Join-Path $Root 'ovms_downloaded\windows-2026.4.0-python-on'
    if (-not (Test-Path -LiteralPath (Join-Path $directory 'ovms\ovms.exe'))) {
        if (Test-Path -LiteralPath $directory) { throw "Incomplete OVMS directory: $directory. Move it aside and retry; no runtime files were deleted." }
        $archive = Get-Payload 'ovms' (Join-Path $State 'downloads') $Catalog
        $staging = Join-Path $State ('ovms-stage-' + [guid]::NewGuid().ToString('N'))
        Expand-SetupZip $archive $staging
        if (-not (Test-Path -LiteralPath (Join-Path $staging 'ovms\setupvars.bat'))) { throw 'Pinned OVMS archive has an unexpected layout.' }
        New-Item -ItemType Directory -Path (Split-Path $directory) -Force | Out-Null
        Move-Item -LiteralPath $staging -Destination $directory
    }
    $version = Invoke-NativeProbe (Join-Path $Root 'models\start-27b-article.cmd') @('--version')
    if ($version.ExitCode -ne 0 -or $version.Output -notmatch '2026\.4\.0') { throw "OVMS version check failed: $($version.Output)" }
    Write-Setup 'OVMS 2026.4.0 runtime is available. GPU execution still requires a supported Intel GPU and driver.'
}

function New-WorkflowShortcuts([string]$Root, [string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $names = [ordered]@{ 'dependency-migration' = 'Dependency Migration'; 'security-repair' = 'Security Repair'; 'regression-tests' = 'Regression Tests' }
    foreach ($workflow in $names.Keys) {
        $shortcut = $shell.CreateShortcut((Join-Path $Destination ("AI PC - {0}.lnk" -f $names[$workflow])))
        $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        $shortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -Workflow "{1}" -InstallationManifest "{2}"' -f (Join-Path $Root 'dependency-migration\demo-controller.ps1'), $workflow, (Join-Path $Root 'dependency-migration\artifacts\installation-local\workflows.json')
        $shortcut.WorkingDirectory = $Root
        $shortcut.Description = 'Installation-local unscored workflow. Start a model, test connection, then run a pilot.'
        $shortcut.Save()
    }
}

function Invoke-WorkflowPreparation([string]$Runner, [string]$Root, [bool]$Refresh) {
    $arguments = '-B "{0}" --root "{1}"' -f (Join-Path $PSScriptRoot 'prepare_workflows.py'), $Root
    if ($Refresh) { $arguments += ' --refresh' }
    Write-Setup 'Workflow preparation opens a separate progress window. Keep it open until checks finish.'
    $process = Start-Process -FilePath $Runner -ArgumentList $arguments -WorkingDirectory $Root -WindowStyle Normal -PassThru -Wait
    if ($null -eq $process.ExitCode -or $process.ExitCode -ne 0) {
        throw "Workflow preparation exited $($process.ExitCode). See installation-local generation logs; setup is incomplete."
    }
}

function Get-ResumeShortcut([string]$State, [string]$StartupDirectory) {
    $hash = [Security.Cryptography.SHA256]::Create()
    try { $identity = [BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($State.ToLowerInvariant()))).Replace('-', '').Substring(0, 12) }
    finally { $hash.Dispose() }
    return Join-Path $StartupDirectory ("AI PC Setup Resume-$identity.lnk")
}

function Register-SetupResume([string]$State, [string]$StartupDirectory, [bool]$LicenseAccepted, [bool]$Refresh, [bool]$SkipDesktop) {
    New-Item -ItemType Directory -Path $StartupDirectory -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $State 'resume.pending') -Value 'Setup is incomplete. Resume at sign-in or double-click Install.cmd.' -Encoding UTF8
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Get-ResumeShortcut $State $StartupDirectory))
    $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $shortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}" -Resume' -f $PSCommandPath
    if ($LicenseAccepted) { $shortcut.Arguments += ' -AcceptDockerLicense' }
    if ($Refresh) { $shortcut.Arguments += ' -RefreshWorkflows' }
    if ($SkipDesktop) { $shortcut.Arguments += ' -NoShortcuts' }
    $shortcut.WorkingDirectory = Split-Path $State
    $shortcut.Save()
}

function Invoke-Installation {
    $root = Split-Path $PSScriptRoot
    $state = Join-Path $root '.installer'
    if ($Resume -and -not (Test-Path -LiteralPath (Join-Path $state 'resume.pending'))) { return 0 }
    $catalog = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'downloads.json') -Raw | ConvertFrom-Json
    if ($SystemStage) { return (Invoke-SystemStage ($Components -split ',') $catalog) }
    if (-not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64' -or [Environment]::OSVersion.Version.Build -lt 22631 -or
        (Get-CimInstance Win32_OperatingSystem).ProductType -ne 1) {
        throw 'This installer requires Windows 11 23H2 or newer, x64. ARM64 and Windows Server are not supported.'
    }
    foreach ($file in @('dependency-migration\requirements-runner.lock', 'dependency-migration\requirements-v1.lock', 'dependency-migration\requirements-v2.lock', 'security-repair\requirements-task.lock', 'regression-tests\requirements-task.lock')) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $file))) { throw "Missing package file $file. Extract the full repository before running Install.cmd." }
    }
    $docker = Find-Docker
    $wslReady = Test-Wsl
    $vcReady = Test-VcRuntime
    if ($CheckOnly) {
        [pscustomobject]@{ Root = $root; Docker = $docker; WslReady = $wslReady; VcRuntimeReady = $vcReady;
            RunnerPresent = (Test-Path (Join-Path $root 'dependency-migration\.venv-runner\Scripts\python.exe'));
            OvmsPresent = (Test-Path (Join-Path $root 'ovms_downloaded\windows-2026.4.0-python-on\ovms\ovms.exe'));
            WorkflowsManifestPresent = (Test-Path (Join-Path $root 'dependency-migration\artifacts\installation-local\workflows.json')) } | Format-List | Out-Host
        return 0
    }
    New-Item -ItemType Directory -Path $state -Force | Out-Null
    $lock = [IO.File]::Open((Join-Path $state 'setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $transcriptStarted = $false
    try {
        Start-Transcript -Path (Join-Path $state ('setup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')) | Out-Null
        $transcriptStarted = $true
        Write-Setup 'Installing AI PC workflows. Existing models, caches, profiles and historical results will be retained.'
        $missing = @()
        if (-not $vcReady) { $missing += 'VcRuntime' }
        if (-not $wslReady) { $missing += 'Wsl' }
        if (-not $docker) {
            if (-not $AcceptDockerLicense) { Confirm-DockerLicense }
            $missing += 'Docker'
        }
        if ($missing.Count) {
            $result = Request-SystemStage $missing
            if ($result -eq 3010) {
                Register-SetupResume $state ([Environment]::GetFolderPath('Startup')) ($AcceptDockerLicense -or 'Docker' -in $missing) ([bool]$RefreshWorkflows) ([bool]$NoShortcuts)
                Write-Setup 'RESTART REQUIRED. Restart Windows yourself; setup will resume at your next sign-in. You can also rerun Install.cmd.'
                return 3010
            }
        }
        $docker = Find-Docker
        if (-not $docker) { throw 'Docker installation did not provide docker.exe. Sign out/in if Windows requires it, then retry.' }
        Wait-Docker $docker
        $uv = Ensure-Uv $state $catalog
        $runner = Ensure-Runner $root $uv
        Ensure-Ovms $root $state $catalog
        Write-Setup 'Building and checking three installation-local workflow packages. This can take many minutes on first setup.'
        Invoke-WorkflowPreparation $runner $root ([bool]$RefreshWorkflows)
        Invoke-SetupCommand $runner @('-B', (Join-Path $PSScriptRoot 'prepare_workflows.py'), '--root', $root, '--verify-only') | Out-Host
        New-WorkflowShortcuts $root (Join-Path $state 'Workflows')
        if (-not $NoShortcuts) { New-WorkflowShortcuts $root ([Environment]::GetFolderPath('Desktop')) }
        Remove-Item -LiteralPath (Join-Path $state 'resume.pending') -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath (Get-ResumeShortcut $state ([Environment]::GetFolderPath('Startup'))) -ErrorAction SilentlyContinue
        Write-Setup ('SETUP COMPLETE. Double-click a workflow shortcut on your Desktop or in ' + (Join-Path $state 'Workflows') + '.')
        Write-Setup 'Model files download when you first click Start selected local model. Cloud models require your own API key and incur charges. No model or cloud pilot was run by setup.'
        return 0
    }
    finally {
        if ($transcriptStarted) { Stop-Transcript | Out-Null }
        $lock.Dispose()
    }
}

if (-not $LibraryOnly) {
    try { exit (Invoke-Installation) }
    catch { Write-Host ('SETUP BLOCKED: ' + $_.Exception.Message) -ForegroundColor Red; exit 1 }
}