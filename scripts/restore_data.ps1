Param(
    [Parameter(Mandatory=$true)]
    [string]$BackupDir
)

if (-not (Test-Path $BackupDir)) {
    throw "Backup directory not found: $BackupDir"
}

New-Item -ItemType Directory -Path "./data" -Force | Out-Null

$dbSource = Join-Path $BackupDir "healthbuddy.db"
$vectorSource = Join-Path $BackupDir "chroma_db"
$knowledgeSource = Join-Path $BackupDir "knowledge_base"

if (Test-Path $dbSource) {
    Copy-Item $dbSource -Destination "./data/healthbuddy.db" -Force
}
if (Test-Path $vectorSource) {
    if (Test-Path "./data/chroma_db") { Remove-Item "./data/chroma_db" -Recurse -Force }
    Copy-Item $vectorSource -Destination "./data/chroma_db" -Recurse -Force
}
if (Test-Path $knowledgeSource) {
    if (Test-Path "./data/knowledge_base") { Remove-Item "./data/knowledge_base" -Recurse -Force }
    Copy-Item $knowledgeSource -Destination "./data/knowledge_base" -Recurse -Force
}

Write-Output "Restore completed from $BackupDir"
