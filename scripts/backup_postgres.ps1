param(
    [string]$OutputDir = "backups\postgres",
    [string]$DatabaseUrl = $env:DATABASE_URL
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    throw "DATABASE_URL es obligatorio."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dumpPath = Join-Path $OutputDir "bitora-postgres-$stamp.dump"
$checksumPath = "$dumpPath.sha256"

pg_dump --format=custom --no-owner --no-acl --file "$dumpPath" "$DatabaseUrl"
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump fallo."
}

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $dumpPath
"$($hash.Hash.ToLowerInvariant())  $(Split-Path -Leaf $dumpPath)" | Set-Content -Encoding UTF8 -LiteralPath $checksumPath

Write-Host "Backup PostgreSQL generado."
Write-Host "Archivo: $dumpPath"
Write-Host "Checksum: $checksumPath"
