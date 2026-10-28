param(
    [Parameter(Mandatory = $true)]
    [string]$DumpPath,
    [Parameter(Mandatory = $true)]
    [string]$ChecksumPath,
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [string]$AllowedDatabasePrefix = "bitora_restore_",
    [Parameter(Mandatory = $true)]
    [string]$ConfirmDestination
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    throw "DATABASE_URL es obligatorio."
}
if (-not (Test-Path -LiteralPath $DumpPath)) {
    throw "No existe el dump indicado."
}
if (-not (Test-Path -LiteralPath $ChecksumPath)) {
    throw "No existe el checksum SHA-256 indicado."
}
if (($env:APP_ENV -eq "production") -or ($env:BITORA_ENV -eq "production")) {
    throw "Restore bloqueado en production."
}
if ([string]::IsNullOrWhiteSpace($AllowedDatabasePrefix) -or $AllowedDatabasePrefix.Length -lt 8) {
    throw "AllowedDatabasePrefix debe ser explicito y suficientemente restrictivo."
}

$dsnPattern = '^(?<scheme>postgres(?:ql)?)://(?<authority>[^/?#]+)(?<path>/[^?#]+)(?:\?[^#]*)?$'
$dsnMatch = [regex]::Match($DatabaseUrl, $dsnPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
if (-not $dsnMatch.Success) {
    throw "DATABASE_URL debe ser un DSN PostgreSQL explicito y no ambiguo."
}
$databaseName = [System.Uri]::UnescapeDataString($dsnMatch.Groups['path'].Value.TrimStart('/'))
if ([string]::IsNullOrWhiteSpace($databaseName) -or $databaseName.Contains('/')) {
    throw "El DSN debe identificar exactamente una base destino."
}
if ($databaseName -notmatch '^[A-Za-z0-9_]+$') {
    throw "Nombre de base destino invalido."
}
if (-not $databaseName.StartsWith($AllowedDatabasePrefix, [System.StringComparison]::Ordinal)) {
    throw "Restore permitido solo sobre una base aislada con prefijo $AllowedDatabasePrefix."
}
$normalizedDsn = $DatabaseUrl.ToLowerInvariant()
if ($normalizedDsn -match '(^|[\W_])(prod|production)([\W_]|$)') {
    throw "Restore bloqueado: el DSN contiene indicadores de produccion."
}
$expectedConfirmation = "RESTORE $databaseName"
if (-not [System.String]::Equals($ConfirmDestination, $expectedConfirmation, [System.StringComparison]::Ordinal)) {
    throw "Confirmacion invalida. Debe escribir exactamente: $expectedConfirmation"
}

$checksumLine = (Get-Content -LiteralPath $ChecksumPath -Raw).Trim()
$checksumMatch = [regex]::Match($checksumLine, '^(?<hash>[A-Fa-f0-9]{64})(?:\s+\*?.+)?$')
if (-not $checksumMatch.Success) {
    throw "Archivo de checksum SHA-256 invalido."
}
$expectedHash = $checksumMatch.Groups['hash'].Value.ToLowerInvariant()
$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $DumpPath).Hash.ToLowerInvariant()
if (-not [System.String]::Equals($actualHash, $expectedHash, [System.StringComparison]::Ordinal)) {
    throw "Checksum SHA-256 del dump no coincide. Restore cancelado."
}

pg_restore --clean --if-exists --no-owner --no-acl --dbname "$DatabaseUrl" "$DumpPath"
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore fallo."
}

Write-Host "Restore PostgreSQL completado."
