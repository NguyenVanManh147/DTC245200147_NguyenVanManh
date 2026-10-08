param()
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose không hợp lệ.' }
    docker compose ps -a
    python scripts/verify.py
    $verificationExitCode = $LASTEXITCODE
    python scripts/summarize-evidence.py
    if ($verificationExitCode -ne 0) { throw 'Có kiểm tra chưa đạt; đọc evidence/verification.json và docs/verification.md.' }
} finally {
    Pop-Location
}
