Param(
    [string]$OutputDir = "./backups"
)

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $OutputDir "healthbuddy_$timestamp"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

$dbPath = "./data/healthbuddy.db"
$vectorPath = "./data/chroma_db"
$knowledgePath = "./data/knowledge_base"

if (Test-Path $dbPath) {
    Copy-Item $dbPath -Destination (Join-Path $backupRoot "healthbuddy.db") -Force
}
if (Test-Path $vectorPath) {
    Copy-Item $vectorPath -Destination (Join-Path $backupRoot "chroma_db") -Recurse -Force
}
if (Test-Path $knowledgePath) {
    Copy-Item $knowledgePath -Destination (Join-Path $backupRoot "knowledge_base") -Recurse -Force
}

Write-Output "Backup completed at $backupRoot"
