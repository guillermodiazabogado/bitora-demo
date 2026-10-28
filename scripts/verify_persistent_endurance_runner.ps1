[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'persistent_endurance_runner.ps1'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("bitora-runner-verify-" + [Guid]::NewGuid().ToString('N'))
$fakeJob = Join-Path $testRoot 'fake-job.ps1'
$pwsh = (Get-Process -Id $PID).Path
$verified = $false
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
try {
    @'
param([int]$Seconds = 2)
for ($i = 0; $i -lt $Seconds; $i++) {
    Write-Output "fake-checkpoint-$i"
    Start-Sleep -Seconds 1
}
'@ | Set-Content -LiteralPath $fakeJob -Encoding utf8

    $completeDir = Join-Path $testRoot 'complete'
    & $runner -Action Start -RunDirectory $completeDir -JobExecutable $pwsh -JobArguments @('-NoProfile', '-File', $fakeJob, '-Seconds', '2') -ExpectedSha 'verify-sha' -HeartbeatSeconds 1 -MaximumHours 1 | Out-Null
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds(45)
    do {
        Start-Sleep -Milliseconds 250
        $status = (& $runner -Action Status -RunDirectory $completeDir | ConvertFrom-Json)
    } while ($status.status -notin @('complete', 'failed', 'runner_failed', 'timed_out', 'stopped') -and [DateTimeOffset]::UtcNow -lt $deadline)
    if ($status.status -ne 'complete') {
        $monitorError = Join-Path $completeDir 'monitor.stderr.log'
        $detail = if (Test-Path -LiteralPath $monitorError) { (Get-Content -LiteralPath $monitorError -Raw) } else { '<monitor stderr missing>' }
        throw "Short fake job did not complete before timeout: status=$($status.status), runner_running=$($status.runner_running), job_running=$($status.job_running), monitor_stderr=$detail, evidence=$completeDir"
    }
    foreach ($name in @('run-metadata.json', 'runner.pid', 'job.pid', 'heartbeat.json', 'runner-checkpoints.jsonl', 'stdout.log', 'stderr.log')) {
        if (-not (Test-Path -LiteralPath (Join-Path $completeDir $name))) { throw "Missing evidence file: $name" }
    }
    $metadata = Get-Content -LiteralPath (Join-Path $completeDir 'run-metadata.json') -Raw | ConvertFrom-Json
    if ($metadata.expected_sha -ne 'verify-sha' -or $metadata.exit_code -ne 0 -or $metadata.monotonic_elapsed_seconds -lt 2) { throw 'Completion metadata is invalid.' }
    if ($metadata.PSObject.Properties.Name -contains 'job_arguments') { throw 'Plain job arguments leaked into metadata.' }

    $stopDir = Join-Path $testRoot 'stop'
    & $runner -Action Start -RunDirectory $stopDir -JobExecutable $pwsh -JobArguments @('-NoProfile', '-File', $fakeJob, '-Seconds', '60') -ExpectedSha 'verify-sha' -HeartbeatSeconds 1 -MaximumHours 1 | Out-Null
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds(10)
    do {
        Start-Sleep -Milliseconds 250
        $running = (& $runner -Action Status -RunDirectory $stopDir | ConvertFrom-Json)
    } while (-not $running.job_running -and [DateTimeOffset]::UtcNow -lt $deadline)
    if (-not $running.job_running) { throw 'Long fake job never reached running state.' }
    & $runner -Action Stop -RunDirectory $stopDir | Out-Null
    Start-Sleep -Seconds 2
    $stopped = (& $runner -Action Status -RunDirectory $stopDir | ConvertFrom-Json)
    if ($stopped.runner_running -or $stopped.job_running) { throw 'Stop did not terminate runner and job.' }
    $stopMetadata = Get-Content -LiteralPath (Join-Path $stopDir 'run-metadata.json') -Raw | ConvertFrom-Json
    if ($stopMetadata.status -ne 'stopped') { throw "Expected stopped metadata, got $($stopMetadata.status)." }

    [ordered]@{
        ok = $true
        completion_status = $metadata.status
        stop_status = $stopMetadata.status
        evidence_files_verified = 7
        plaintext_arguments_in_metadata = $false
    } | ConvertTo-Json
    $verified = $true
} finally {
    if ($verified -and (Test-Path -LiteralPath $testRoot)) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    } elseif (Test-Path -LiteralPath $testRoot) {
        Write-Warning "Verification evidence retained after failure: $testRoot"
    }
}
