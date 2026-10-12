#requires -Version 5.1

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$script:workflowRoot = $PSScriptRoot
$script:workspaceRoot = Split-Path -Parent $script:workflowRoot
$script:modelRoot = Join-Path $script:workspaceRoot 'models'
$script:ovmsRoot = Join-Path $script:workspaceRoot 'ovms_downloaded\windows-2026.4.0-python-on\ovms'
$script:runnerPython = Join-Path $script:workflowRoot '.venv-runner\Scripts\python.exe'
$script:freezePath = Join-Path $script:workflowRoot 'artifacts\freeze-600s-v8.json'
$script:artifactRoot = Join-Path $script:workflowRoot 'artifacts'
$script:logRoot = Join-Path $script:artifactRoot 'demo-controller'
$script:serverProcess = $null
$script:taskProcess = $null
$script:serverReady = $false
$script:warmupReady = $false
$script:openReportPath = $null
$script:watchFiles = @{}
$script:profilePaths = @(
    'profiles\ptl-morteza89-27b.private.json',
    'profiles\ptl-8b.private.json',
    'profiles\ptl-openai.private.json'
)
$script:templatePaths = @(
    'profiles\article-27b.json',
    'profiles\local-8b.json',
    'profiles\openai.json'
)
$script:modelNames = @(
    'Qwen3.8 27B INT4 (local)',
    'Qwen3 8B INT8 (local)',
    'GPT-6.1 Sol (OpenAI API)'
)

New-Item -ItemType Directory -Force -Path $script:logRoot | Out-Null

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Dependency Migration Demo Controller'
$form.StartPosition = 'CenterScreen'
$form.Size = New-Object System.Drawing.Size(920, 700)
$form.MinimumSize = New-Object System.Drawing.Size(820, 620)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9)

$title = New-Object System.Windows.Forms.Label
$title.Text = 'Dependency Migration | Pydantic v1 to v2'
$title.Location = New-Object System.Drawing.Point(20, 16)
$title.Size = New-Object System.Drawing.Size(850, 30)
$title.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 15)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = '10-minute unscored demo runs. Each attempt uses a fresh task container and is independently verified.'
$subtitle.Location = New-Object System.Drawing.Point(22, 50)
$subtitle.Size = New-Object System.Drawing.Size(850, 24)
$form.Controls.Add($subtitle)

$modelLabel = New-Object System.Windows.Forms.Label
$modelLabel.Text = 'Model'
$modelLabel.Location = New-Object System.Drawing.Point(22, 91)
$modelLabel.Size = New-Object System.Drawing.Size(70, 24)
$form.Controls.Add($modelLabel)

$modelPicker = New-Object System.Windows.Forms.ComboBox
$modelPicker.DropDownStyle = 'DropDownList'
$modelPicker.Location = New-Object System.Drawing.Point(92, 88)
$modelPicker.Size = New-Object System.Drawing.Size(410, 28)
$modelPicker.Items.AddRange([object[]]$script:modelNames)
$modelPicker.SelectedIndex = 0
$form.Controls.Add($modelPicker)

$serverStatus = New-Object System.Windows.Forms.Label
$serverStatus.Text = 'Server: checking'
$serverStatus.Location = New-Object System.Drawing.Point(22, 128)
$serverStatus.Size = New-Object System.Drawing.Size(420, 24)
$form.Controls.Add($serverStatus)

$apiStatus = New-Object System.Windows.Forms.Label
$apiStatus.Text = 'OpenAI API key: checking'
$apiStatus.Location = New-Object System.Drawing.Point(470, 128)
$apiStatus.Size = New-Object System.Drawing.Size(390, 24)
$form.Controls.Add($apiStatus)

$freezeStatus = New-Object System.Windows.Forms.Label
$freezeStatus.Text = 'Freeze: ' + (Split-Path -Leaf $script:freezePath)
$freezeStatus.Location = New-Object System.Drawing.Point(22, 155)
$freezeStatus.Size = New-Object System.Drawing.Size(850, 24)
$form.Controls.Add($freezeStatus)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = 'Start selected local model'
$startButton.Location = New-Object System.Drawing.Point(22, 196)
$startButton.Size = New-Object System.Drawing.Size(190, 34)
$form.Controls.Add($startButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = 'Stop local model'
$stopButton.Location = New-Object System.Drawing.Point(220, 196)
$stopButton.Size = New-Object System.Drawing.Size(155, 34)
$stopButton.Enabled = $false
$form.Controls.Add($stopButton)

$warmupButton = New-Object System.Windows.Forms.Button
$warmupButton.Text = 'Test connection'
$warmupButton.Location = New-Object System.Drawing.Point(383, 196)
$warmupButton.Size = New-Object System.Drawing.Size(145, 34)
$form.Controls.Add($warmupButton)

$runButton = New-Object System.Windows.Forms.Button
$runButton.Text = 'Run unscored pilot'
$runButton.Location = New-Object System.Drawing.Point(536, 196)
$runButton.Size = New-Object System.Drawing.Size(165, 34)
$form.Controls.Add($runButton)

$reportButton = New-Object System.Windows.Forms.Button
$reportButton.Text = 'Refresh report'
$reportButton.Location = New-Object System.Drawing.Point(709, 196)
$reportButton.Size = New-Object System.Drawing.Size(150, 34)
$form.Controls.Add($reportButton)

$openButton = New-Object System.Windows.Forms.Button
$openButton.Text = 'Open latest attempt'
$openButton.Location = New-Object System.Drawing.Point(22, 238)
$openButton.Size = New-Object System.Drawing.Size(190, 32)
$form.Controls.Add($openButton)

$comparisonButton = New-Object System.Windows.Forms.Button
$comparisonButton.Text = 'Generate comparison report'
$comparisonButton.Location = New-Object System.Drawing.Point(220, 238)
$comparisonButton.Size = New-Object System.Drawing.Size(195, 32)
$form.Controls.Add($comparisonButton)

$hint = New-Object System.Windows.Forms.Label
$hint.Text = 'For OpenAI, launch this window from the PowerShell session that has OPENAI_API_KEY set. The key is never displayed or saved by this app.'
$hint.Location = New-Object System.Drawing.Point(425, 241)
$hint.Size = New-Object System.Drawing.Size(440, 28)
$form.Controls.Add($hint)

$outputBox = New-Object System.Windows.Forms.TextBox
$outputBox.Location = New-Object System.Drawing.Point(22, 280)
$outputBox.Size = New-Object System.Drawing.Size(837, 350)
$outputBox.Anchor = 'Top,Bottom,Left,Right'
$outputBox.Multiline = $true
$outputBox.ReadOnly = $true
$outputBox.ScrollBars = 'Vertical'
$outputBox.WordWrap = $true
$outputBox.Font = New-Object System.Drawing.Font('Consolas', 9)
$form.Controls.Add($outputBox)

function Write-Log([string]$Message) {
    $stamp = Get-Date -Format 'HH:mm:ss'
    $outputBox.AppendText("[$stamp] $Message`r`n")
}

function Get-SelectedModel {
    $index = $modelPicker.SelectedIndex
    if ($index -lt 0 -or $index -ge $script:profilePaths.Count) { throw 'Select a model first.' }
    $profilePath = Join-Path $script:workflowRoot $script:profilePaths[$index]
    if (-not (Test-Path $profilePath)) {
        $templatePath = Join-Path $script:workflowRoot $script:templatePaths[$index]
        if (-not (Test-Path $templatePath)) { throw "Neither the private profile nor its template exists: $profilePath" }
        Copy-Item -LiteralPath $templatePath -Destination $profilePath
        Write-Log "Created private profile from template: $($script:profilePaths[$index]). Fill host metadata before scored studies."
    }
    $profile = Get-Content $profilePath -Raw | ConvertFrom-Json
    return [pscustomobject]@{ Index = $index; Name = $script:modelNames[$index]; Path = $profilePath; Profile = $profile }
}

function Test-Port8000 {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $result = $client.BeginConnect('127.0.0.1', 8000, $null, $null)
        return $result.AsyncWaitHandle.WaitOne(150) -and $client.Connected
    }
    catch { return $false }
    finally { $client.Close() }
}

function Add-WatchedFile([string]$Path) {
    $script:watchFiles[$Path] = 0
}

function Read-WatchedFiles {
    foreach ($path in @($script:watchFiles.Keys)) {
        if (-not (Test-Path $path)) { continue }
        $stream = $null
        $reader = $null
        try {
            $stream = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            $offset = [long]$script:watchFiles[$path]
            if ($stream.Length -le $offset) { continue }
            $stream.Position = $offset
            $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8, $true)
            $chunk = $reader.ReadToEnd()
            $script:watchFiles[$path] = $stream.Position
            if ($chunk) {
                foreach ($line in ($chunk -split "`r?`n")) {
                    if (-not $line) { continue }
                    Write-Log $line
                    if ($line -match 'state changed to: AVAILABLE') { $script:serverReady = $true }
                }
            }
        }
        catch { }
        finally {
            if ($reader) { $reader.Dispose() }
            elseif ($stream) { $stream.Dispose() }
        }
    }
}

function Update-Status {
    $selected = Get-SelectedModel
    if ($selected.Profile.provider -eq 'openai') {
        if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
            $apiStatus.Text = 'OpenAI API key: missing in this process'
            $apiStatus.ForeColor = [System.Drawing.Color]::DarkRed
        }
        else {
            $apiStatus.Text = 'OpenAI API key: set (value hidden)'
            $apiStatus.ForeColor = [System.Drawing.Color]::DarkGreen
        }
        $serverStatus.Text = 'Server: cloud API; no local server required'
        $serverStatus.ForeColor = [System.Drawing.Color]::DimGray
        $startButton.Enabled = $false
        $stopButton.Enabled = $false
        $warmupButton.Enabled = -not $script:taskProcess -and -not [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)
        $runButton.Enabled = -not $script:taskProcess -and -not [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)
        return
    }

    $apiStatus.Text = 'OpenAI API key: not used by local profile'
    $apiStatus.ForeColor = [System.Drawing.Color]::DimGray
    Read-WatchedFiles
    if ($script:serverProcess -and -not $script:serverProcess.HasExited) {
        if ($script:serverReady) {
            $serverStatus.Text = 'Server: AVAILABLE'
            $serverStatus.ForeColor = [System.Drawing.Color]::DarkGreen
        }
        else {
            $serverStatus.Text = 'Server: starting; waiting for AVAILABLE'
            $serverStatus.ForeColor = [System.Drawing.Color]::DarkOrange
        }
        $stopButton.Enabled = -not $script:taskProcess
        $startButton.Enabled = $false
        $warmupButton.Enabled = -not $script:taskProcess
        $runButton.Enabled = -not $script:taskProcess -and $script:serverReady
    }
    elseif (Test-Port8000) {
        $serverStatus.Text = 'Server: port 8000 is occupied outside this controller'
        $serverStatus.ForeColor = [System.Drawing.Color]::DarkOrange
        $startButton.Enabled = $false
        $stopButton.Enabled = $false
        $warmupButton.Enabled = -not $script:taskProcess
        $runButton.Enabled = -not $script:taskProcess -and $script:warmupReady
    }
    else {
        $serverStatus.Text = 'Server: stopped'
        $serverStatus.ForeColor = [System.Drawing.Color]::DimGray
        $startButton.Enabled = -not $script:taskProcess
        $stopButton.Enabled = $false
        $warmupButton.Enabled = $false
        $runButton.Enabled = $false
    }
}

function Start-TrackedProcess([string]$FileName, [string]$Arguments, [string]$WorkingDirectory, [string]$Tag) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $stdout = Join-Path $script:logRoot "$Tag-$stamp.out.log"
    $stderr = Join-Path $script:logRoot "$Tag-$stamp.err.log"
    $process = Start-Process -FilePath $FileName -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    Add-WatchedFile $stdout
    Add-WatchedFile $stderr
    return $process
}

$startButton.Add_Click({
    try {
        $selected = Get-SelectedModel
        if ($selected.Profile.provider -ne 'local') { throw 'The selected model does not use a local server.' }
        if (Test-Port8000) { throw 'Port 8000 is already in use. Stop the existing model server before starting another.' }
        $wrapper = Join-Path $script:logRoot 'start-local-model.cmd'
        if ($selected.Profile.model -eq 'qwen3.8-27b-ov') {
            $launcher = Join-Path $script:modelRoot 'start-27b-article.cmd'
            $modelFile = Join-Path $script:modelRoot 'morteza89-qwen3.8-27b-int4-ov\openvino_language_model.xml'
            if (-not (Test-Path $launcher) -or -not (Test-Path $modelFile)) { throw 'The pinned 27B launcher or model files are missing; see MODELS.md.' }
            [System.IO.File]::WriteAllText($wrapper, "@echo off`r`ncall `"$launcher`"`r`n", [System.Text.Encoding]::ASCII)
        }
        else {
            $setupvars = Join-Path $script:ovmsRoot 'setupvars.bat'
            $ovms = Join-Path $script:ovmsRoot 'ovms.exe'
            $modelFile = Join-Path $script:modelRoot 'qwen3-8b-int8\graph.pbtxt'
            $config = Join-Path $script:modelRoot 'migration-ovms.json'
            if (-not (Test-Path $setupvars) -or -not (Test-Path $ovms) -or -not (Test-Path $modelFile) -or -not (Test-Path $config)) { throw '8B weights, graph, config, or OVMS runtime are missing. Follow the setup steps in MODELS.md first.' }
            $lines = @('@echo off', "call `"$setupvars`"", 'if errorlevel 1 exit /b 1', "`"$ovms`" --config_path `"$config`" --rest_bind_address 127.0.0.1 --rest_port 8000 --idle_unload_timeout_seconds 0")
            [System.IO.File]::WriteAllLines($wrapper, $lines, [System.Text.Encoding]::ASCII)
        }
        $workingDirectory = if ($selected.Profile.model -eq 'qwen3.8-27b-ov') { $script:workspaceRoot } else { $script:ovmsRoot }
        $script:serverReady = $false
        $script:warmupReady = $false
        $script:serverProcess = Start-TrackedProcess $env:ComSpec ("/d /c call `"$wrapper`"") $workingDirectory 'server'
        Write-Log "Started $($selected.Name); wait for AVAILABLE in the server log."
    }
    catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Could not start server', 'OK', 'Warning') | Out-Null }
    Update-Status
})

$stopButton.Add_Click({
    if ($script:serverProcess -and -not $script:serverProcess.HasExited) {
        $confirm = [System.Windows.Forms.MessageBox]::Show('Stop the local model server started by this controller?', 'Stop server', 'YesNo', 'Question')
        if ($confirm -eq 'Yes') {
            Start-Process -FilePath 'taskkill.exe' -ArgumentList "/PID $($script:serverProcess.Id) /T /F" -WindowStyle Hidden -Wait | Out-Null
            $script:serverProcess = $null
            $script:serverReady = $false
            $script:warmupReady = $false
            Write-Log 'Stopped the local model server process tree.'
        }
    }
    Update-Status
})

$warmupButton.Add_Click({
    try {
        $selected = Get-SelectedModel
        if ($selected.Profile.provider -eq 'openai') {
            $confirm = [System.Windows.Forms.MessageBox]::Show('This sends one small, billable OpenAI API warmup request. Continue?', 'Billable API warmup', 'YesNo', 'Warning')
            if ($confirm -ne 'Yes') { return }
        }
        $script:warmupReady = $false
        $warmupButton.Enabled = $false
        $form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor
        Write-Log "Testing $($selected.Name) with a small READY request..."
        [System.Windows.Forms.Application]::DoEvents()
        if ($selected.Profile.provider -eq 'openai') {
            $headers = @{ Authorization = "Bearer $env:OPENAI_API_KEY" }
            $body = @{ model = $selected.Profile.model; input = 'Reply READY only.'; max_output_tokens = 64; reasoning = @{ effort = $selected.Profile.inference.reasoning_effort } } | ConvertTo-Json -Depth 6
            $response = Invoke-RestMethod -Uri ($selected.Profile.base_url.TrimEnd('/') + '/responses') -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 90
            $text = (@($response.output | ForEach-Object { $_.content } | ForEach-Object { if ($_.type -eq 'output_text') { $_.text } }) -join '')
        }
        else {
            $body = @{ model = $selected.Profile.model; messages = @(@{ role = 'user'; content = 'Return the single word READY.' }); max_tokens = 32; temperature = 0 }
            if ($selected.Profile.extra_body.chat_template_kwargs) { $body.chat_template_kwargs = $selected.Profile.extra_body.chat_template_kwargs }
            $json = $body | ConvertTo-Json -Depth 8
            $uri = $selected.Profile.base_url.TrimEnd('/') + '/chat/completions'
            $response = Invoke-RestMethod -Uri $uri -Method Post -ContentType 'application/json' -Body $json -TimeoutSec 120
            $text = $response.choices[0].message.content
        }
        if ($response.model -ne $selected.Profile.expected_returned_model -or $text -notmatch 'READY') { throw "Unexpected warmup identity or output. Returned model: $($response.model); output: $text" }
        $script:warmupReady = $true
        Write-Log "Warmup passed: $($response.model) returned READY. Usage: $($response.usage | ConvertTo-Json -Compress -Depth 5)"
    }
    catch {
        $message = $_.Exception.Message -replace 'sk-[A-Za-z0-9_-]{20,}', '[REDACTED]'
        Write-Log "Warmup failed: $message"
        [System.Windows.Forms.MessageBox]::Show($message, 'Warmup failed', 'OK', 'Error') | Out-Null
    }
    finally {
        $form.Cursor = [System.Windows.Forms.Cursors]::Default
        Update-Status
    }
})

$runButton.Add_Click({
    try {
        $selected = Get-SelectedModel
        if ($selected.Profile.provider -eq 'local' -and -not ($script:serverReady -or $script:warmupReady)) { throw 'Start the selected local server and pass Test connection first.' }
        if ($selected.Profile.provider -eq 'openai' -and [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) { throw 'OPENAI_API_KEY is not set in the PowerShell process that launched this controller.' }
        if ($selected.Profile.provider -eq 'openai') {
            $confirm = [System.Windows.Forms.MessageBox]::Show('This runs an unscored pilot for up to 10 minutes. OpenAI usage is billable; the work deadline is not a dollar cap. Continue?', 'Billable OpenAI pilot', 'YesNo', 'Warning')
            if ($confirm -ne 'Yes') { return }
        }
        $args = @('bench.py', 'run', '--profile', $selected.Path, '--freeze', $script:freezePath)
        if ($selected.Profile.provider -eq 'openai') { $args += '--allow-cloud' }
        $quoted = foreach ($arg in $args) { if ($arg -match '\s') { '"' + $arg.Replace('"', '\"') + '"' } else { $arg } }
        $script:taskProcess = Start-TrackedProcess $script:runnerPython ($quoted -join ' ') $script:workflowRoot 'pilot'
        Write-Log "Started unscored pilot for $($selected.Name) on freeze $(Split-Path -Leaf $script:freezePath)."
    }
    catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Could not start pilot', 'OK', 'Warning') | Out-Null }
    Update-Status
})

$openButton.Add_Click({
    $latest = Get-ChildItem (Join-Path $script:artifactRoot 'attempt-*') -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) { Start-Process explorer.exe -ArgumentList ('"' + $latest.FullName + '"') }
    else { Write-Log 'No attempt artifacts found yet.' }
})

$reportButton.Add_Click({
    if ($script:taskProcess -and -not $script:taskProcess.HasExited) { Write-Log 'Wait for the active attempt to finish before refreshing the report.'; return }
    $quoted = @('bench.py', 'report') | ForEach-Object { '"' + $_ + '"' }
    $script:taskProcess = Start-TrackedProcess $script:runnerPython ($quoted -join ' ') $script:workflowRoot 'report'
    Write-Log 'Refreshing the grouped attempt report...'
    Update-Status
})

$comparisonButton.Add_Click({
    if ($script:taskProcess -and -not $script:taskProcess.HasExited) { Write-Log 'Wait for the active task to finish before generating the comparison.'; return }
    $reportPath = Join-Path $script:artifactRoot ('comparison-report-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.md')
    $args = @('comparison_report.py', '--directory', $script:artifactRoot, '--freeze', $script:freezePath, '--output', $reportPath)
    foreach ($profilePath in $script:profilePaths) { $args += @('--profile', (Join-Path $script:workflowRoot $profilePath)) }
    $quoted = foreach ($arg in $args) { if ($arg -match '\s') { '"' + $arg.Replace('"', '\"') + '"' } else { $arg } }
    $script:openReportPath = $reportPath
    $script:taskProcess = Start-TrackedProcess $script:runnerPython ($quoted -join ' ') $script:workflowRoot 'comparison-report'
    Write-Log 'Generating a comparison from attempts matching the selected freeze; the report will open when ready.'
    Update-Status
})

$modelPicker.Add_SelectedIndexChanged({
    $script:warmupReady = $false
    Update-Status
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 700
$timer.Add_Tick({
    Read-WatchedFiles
    if ($script:serverProcess -and $script:serverProcess.HasExited) {
        Write-Log "Server process exited with code $($script:serverProcess.ExitCode)."
        $script:serverProcess = $null
        $script:serverReady = $false
    }
    if ($script:taskProcess -and $script:taskProcess.HasExited) {
        $script:taskProcess.Refresh()
        $taskExitCode = $script:taskProcess.ExitCode
        if ($null -eq $taskExitCode) { Write-Log 'Task process finished; exit code unavailable.' }
        else { Write-Log "Task process exited with code $taskExitCode." }
        $script:taskProcess = $null
        if ($script:openReportPath) {
            $reportPath = $script:openReportPath
            $script:openReportPath = $null
            if (Test-Path $reportPath) {
                Write-Log "Opening comparison report: $reportPath"
                Start-Process -FilePath $reportPath
            }
            else { Write-Log 'Comparison report generation failed; inspect the process output above.' }
        }
    }
    Update-Status
})

$form.Add_FormClosing({
    if ($script:serverProcess -and -not $script:serverProcess.HasExited) {
        $choice = [System.Windows.Forms.MessageBox]::Show('A local server started by this controller is still running. Stop it before closing?', 'Local server running', 'YesNoCancel', 'Question')
        if ($choice -eq 'Cancel') { $_.Cancel = $true; return }
        if ($choice -eq 'Yes') { Start-Process -FilePath 'taskkill.exe' -ArgumentList "/PID $($script:serverProcess.Id) /T /F" -WindowStyle Hidden -Wait | Out-Null }
    }
    $timer.Stop()
})

Write-Log 'Choose a model. Start a local server when needed, test the endpoint, then run an unscored pilot.'
Write-Log "Freeze: $script:freezePath"
if (-not (Test-Path $script:runnerPython)) { Write-Log "Runner Python is missing: $script:runnerPython" }
if (-not (Test-Path $script:freezePath)) { Write-Log "Freeze is missing: $script:freezePath" }
Update-Status
$timer.Start()
[void]$form.ShowDialog()