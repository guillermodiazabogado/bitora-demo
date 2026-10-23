param(
    [Parameter(Mandatory = $true)]
    [string]$DumpPath,
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    throw "DATABASE_URL es obligatorio."
}
if (-not (Test-Path -LiteralPath $DumpPath)) {
    throw "No existe el dump indicado."
}
if (-not $Yes) {
    throw "Restore bloqueado. Reejecutar con -Yes solo sobre entorno staging/restore controlado."
}
if (($env:APP_ENV -eq "production") -or ($env:BITORA_ENV -eq "production")) {
    throw "Restore bloqueado en production."
}

pg_restore --clean --if-exists --no-owner --no-acl --dbname "$DatabaseUrl" "$DumpPath"
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore fallo."
}

Write-Host "Restore PostgreSQL completado."
