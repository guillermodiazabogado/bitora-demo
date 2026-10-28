[CmdletBinding()]
param(
    [ValidateSet('Start', 'Monitor', 'Status', 'Stop')]
    [string]$Action = 'Status',
    [Parameter(Mandatory = $true)]
    [string]$RunDirectory,
    [string]$JobExecutable,
    [string[]]$JobArguments = @(),
    [string]$JobArgumentsBase64,
    [string]$JobWorkingDirectory = '',
    [string]$ExpectedSha = '',
    [ValidateRange(1, 3600)]
    [int]$HeartbeatSeconds = 30,
    [ValidateRange(1, 168)]
    [int]$MaximumHours = 8
)

$ErrorActionPreference = 'Stop'
$runPath = [System.IO.Path]::GetFullPath($RunDirectory)
$metadataPath = Join-Path $runPath 'run-metadata.json'
$heartbeatPath = Join-Path $runPath 'heartbeat.json'
$runnerPidPath = Join-Path $runPath 'runner.pid'
$jobPidPath = Join-Path $runPath 'job.pid'
$stopPath = Join-Path $runPath 'STOP'
$stdoutPath = Join-Path $runPath 'stdout.log'
$stderrPath = Join-Path $runPath 'stderr.log'
$monitorStdoutPath = Join-Path $runPath 'monitor.stdout.log'
$monitorStderrPath = Join-Path $runPath 'monitor.stderr.log'
$checkpointPath = Join-Path $runPath 'runner-checkpoints.jsonl'

function Write-AtomicJson([string]$Path, [hashtable]$Payload) {
    $temp = "$Path.tmp.$PID"
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $temp -Encoding utf8
    Move-Item -LiteralPath $temp -Destination $Path -Force
}
function Write-Metadata([string]$Status, [hashtable]$Extra = @{}) {
    $payload = [ordered]@{
        schema_version = 1
        status = $Status
        run_directory = $runPath
        expected_sha = $ExpectedSha
        updated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    }
    foreach ($item in $Extra.GetEnumerator()) { $payload[$item.Key] = $item.Value }
    Write-AtomicJson $metadataPath $payload
}

function Read-Pid([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $value = (Get-Content -LiteralPath $Path -Raw).Trim()
    if ($value -notmatch '^\d+$') { return $null }
    return [int]$value
}

function Test-ProcessId([Nullable[int]]$Id) {
    if ($null -eq $Id) { return $false }
    return $null -ne (Get-Process -Id $Id -ErrorAction SilentlyContinue)
}

function Quote-PowerShellLiteral([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

function Stop-ProcessTree([int]$Id) {
    $process = Get-Process -Id $Id -ErrorAction SilentlyContinue
    if ($null -eq $process) { return }
    try { Stop-Process -Id $Id -ErrorAction Stop } catch { }
    $process.WaitForExit(5000) | Out-Null
    if (Get-Process -Id $Id -ErrorAction SilentlyContinue) {
        & taskkill.exe /PID $Id /T /F 2>$null | Out-Null
    }
}

if ($Action -eq 'Status') {
    $runnerPid = Read-Pid $runnerPidPath
    $jobPid = Read-Pid $jobPidPath
    $metadata = if (Test-Path -LiteralPath $metadataPath) { Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json } else { $null }
    [ordered]@{
        status = if ($metadata) { $metadata.status } else { 'not_started' }
        runner_pid = $runnerPid
        runner_running = Test-ProcessId $runnerPid
        job_pid = $jobPid
        job_running = Test-ProcessId $jobPid
        stop_requested = Test-Path -LiteralPath $stopPath
        metadata = $metadataPath
    } | ConvertTo-Json -Depth 6
    exit 0
}

if ($Action -eq 'Stop') {
    New-Item -ItemType Directory -Path $runPath -Force | Out-Null
    [DateTimeOffset]::UtcNow.ToString('o') | Set-Content -LiteralPath $stopPath -Encoding ascii
    $runnerPid = Read-Pid $runnerPidPath
    $graceSeconds = 45
    if (Test-Path -LiteralPath $metadataPath) {
        try {
            $currentMetadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
            if ($currentMetadata.heartbeat_seconds) { $graceSeconds = [Math]::Min(90, [int]$currentMetadata.heartbeat_seconds + 15) }
        } catch { }
    }
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($graceSeconds)
    while ((Test-ProcessId $runnerPid) -and [DateTimeOffset]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 250 }
    if (Test-ProcessId $runnerPid) { Stop-ProcessTree $runnerPid }
    [ordered]@{ stop_requested = $true; runner_stopped = -not (Test-ProcessId $runnerPid) } | ConvertTo-Json
    exit 0
}

if ($Action -eq 'Start') {
    if ([string]::IsNullOrWhiteSpace($JobExecutable)) { throw 'JobExecutable is required for Start.' }
    New-Item -ItemType Directory -Path $runPath -Force | Out-Null
    $existingPid = Read-Pid $runnerPidPath
    if (Test-ProcessId $existingPid) { throw "Runner is already active with PID $existingPid." }
    Remove-Item -LiteralPath $stopPath -Force -ErrorAction SilentlyContinue
    $argumentsJson = ConvertTo-Json @($JobArguments) -Compress
    $argumentsBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($argumentsJson))
    $scriptPath = $MyInvocation.MyCommand.Path
    $command = @(
        '&', (Quote-PowerShellLiteral $scriptPath),
        '-Action Monitor',
        '-RunDirectory', (Quote-PowerShellLiteral $runPath),
        '-JobExecutable', (Quote-PowerShellLiteral ([IO.Path]::GetFullPath($JobExecutable))),
        '-JobArgumentsBase64', (Quote-PowerShellLiteral $argumentsBase64),
        '-JobWorkingDirectory', (Quote-PowerShellLiteral $(if ($JobWorkingDirectory) { [IO.Path]::GetFullPath($JobWorkingDirectory) } else { (Get-Location).Path })),
        '-ExpectedSha', (Quote-PowerShellLiteral $ExpectedSha),
        '-HeartbeatSeconds', $HeartbeatSeconds,
        '-MaximumHours', $MaximumHours
    ) -join ' '
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
    # Prefer PowerShell 7 even when Start is invoked from Windows PowerShell
    # 5.1. The runner uses the same explicit host for a reproducible monitor.
    $pwshCommand = Get-Command pwsh.exe -ErrorAction SilentlyContinue
    $pwsh = if ($pwshCommand) { $pwshCommand.Source } else { (Get-Process -Id $PID).Path }
    # Publish the request before launching.  The detached monitor is the sole
    # writer of subsequent lifecycle states, avoiding a late "starting" write
    # that could overwrite "running" or "complete".
    Write-Metadata 'starting' @{ runner_pid = $null; start_requested_at_utc = [DateTimeOffset]::UtcNow.ToString('o') }
    $monitor = Start-Process -FilePath $pwsh -ArgumentList @('-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', $encoded) -RedirectStandardOutput $monitorStdoutPath -RedirectStandardError $monitorStderrPath -WindowStyle Hidden -PassThru
    $monitor.Id | Set-Content -LiteralPath $runnerPidPath -Encoding ascii
    [ordered]@{ status = 'starting'; runner_pid = $monitor.Id; run_directory = $runPath } | ConvertTo-Json
    exit 0
}

# Monitor action runs in the detached process.
if ([string]::IsNullOrWhiteSpace($JobExecutable) -or [string]::IsNullOrWhiteSpace($JobArgumentsBase64)) {
    throw 'Monitor requires JobExecutable and JobArgumentsBase64.'
}
New-Item -ItemType Directory -Path $runPath -Force | Out-Null
$PID | Set-Content -LiteralPath $runnerPidPath -Encoding ascii
$decodedArguments = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($JobArgumentsBase64)) | ConvertFrom-Json
$decodedArguments = @($decodedArguments)
$sha256 = [Security.Cryptography.SHA256]::Create()
try {
    $hashBytes = $sha256.ComputeHash([Text.Encoding]::UTF8.GetBytes(($decodedArguments | ConvertTo-Json -Compress)))
    $argumentHash = ([BitConverter]::ToString($hashBytes)).Replace('-', '').ToLowerInvariant()
} finally {
    $sha256.Dispose()
}
$startedAt = [DateTimeOffset]::UtcNow
$clock = [Diagnostics.Stopwatch]::StartNew()
$job = $null
$resolvedWorkingDirectory = if ($JobWorkingDirectory) { [IO.Path]::GetFullPath($JobWorkingDirectory) } else { (Get-Location).Path }
$finalStatus = 'runner_failed'
$exitCode = $null
try {
    $job = Start-Process -FilePath $JobExecutable -ArgumentList $decodedArguments -WorkingDirectory $resolvedWorkingDirectory -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -WindowStyle Hidden -PassThru
    $job.Id | Set-Content -LiteralPath $jobPidPath -Encoding ascii
    Write-Metadata 'running' @{
        runner_pid = $PID; job_pid = $job.Id; job_executable = $JobExecutable
        job_arguments_sha256 = $argumentHash; job_working_directory = $resolvedWorkingDirectory; started_at_utc = $startedAt.ToString('o')
        maximum_hours = $MaximumHours; heartbeat_seconds = $HeartbeatSeconds
    }
    while (-not $job.HasExited) {
        $stopRequested = Test-Path -LiteralPath $stopPath
        $timedOut = $clock.Elapsed.TotalHours -ge $MaximumHours
        $sample = [ordered]@{
            timestamp_utc = [DateTimeOffset]::UtcNow.ToString('o')
            monotonic_elapsed_seconds = [Math]::Round($clock.Elapsed.TotalSeconds, 3)
            runner_pid = $PID; job_pid = $job.Id; job_running = -not $job.HasExited
            stop_requested = $stopRequested; timed_out = $timedOut
        }
        Write-AtomicJson $heartbeatPath $sample
        ($sample | ConvertTo-Json -Compress) | Add-Content -LiteralPath $checkpointPath -Encoding utf8
        if ($stopRequested -or $timedOut) {
            Stop-ProcessTree $job.Id
            $finalStatus = if ($stopRequested) { 'stopped' } else { 'timed_out' }
            break
        }
        Start-Sleep -Seconds $HeartbeatSeconds
        $job.Refresh()
    }
    if ($job.HasExited) {
        $exitCode = $job.ExitCode
        if ($finalStatus -eq 'runner_failed') { $finalStatus = if ($exitCode -eq 0) { 'complete' } else { 'failed' } }
    }
} catch {
    $_ | Out-String | Add-Content -LiteralPath $stderrPath -Encoding utf8
    $finalStatus = 'runner_failed'
} finally {
    $clock.Stop()
    if ($job -and -not $job.HasExited) { Stop-ProcessTree $job.Id }
    Write-Metadata $finalStatus @{
        runner_pid = $PID; job_pid = if ($job) { $job.Id } else { $null }
        job_executable = $JobExecutable; job_arguments_sha256 = $argumentHash
        started_at_utc = $startedAt.ToString('o'); finished_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
        monotonic_elapsed_seconds = [Math]::Round($clock.Elapsed.TotalSeconds, 3); exit_code = $exitCode
    }
}

