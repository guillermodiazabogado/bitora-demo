$ErrorActionPreference = "Stop"

$workspace = "C:\Users\Noxie-PC\.codex\worktrees\bitora-qr-latency-phase-6-2\qr white label"
$auditRelative = "auditoria/bitora_5_8_2_phase_6_3"
$runtimeConfig = Join-Path $workspace "$($auditRelative.Replace('/', '\'))\phase63_campaign_config.json"
$campaignId = (Get-Content -Raw -LiteralPath $runtimeConfig | ConvertFrom-Json).campaign_id
$wslWorkspace = "/mnt/c/Users/Noxie-PC/.codex/worktrees/bitora-qr-latency-phase-6-2/qr white label"
$campaignRoot = "$wslWorkspace/$auditRelative/evidence/$campaignId"
$localCampaignRoot = Join-Path $workspace "$($auditRelative.Replace('/', '\'))\evidence\$campaignId"
New-Item -ItemType Directory -Force -Path $localCampaignRoot | Out-Null

$command = @"
cd '$wslWorkspace' && exec python3 '$auditRelative/phase63_campaign_supervisor.py' \
  --config '$auditRelative/phase63_campaign_config.json' \
  >> '$campaignRoot/supervisor.stdout.log' \
  2>> '$campaignRoot/supervisor.stderr.log'
"@

& wsl.exe -d Ubuntu -- bash -lc $command
exit $LASTEXITCODE
