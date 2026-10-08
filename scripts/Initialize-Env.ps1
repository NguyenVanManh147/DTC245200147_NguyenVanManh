param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot '.env'
if (Test-Path -LiteralPath $envPath) {
    Write-Host '.env đã tồn tại; giữ nguyên thông tin của database hiện có.'
    exit 0
}
$template = Get-Content -LiteralPath (Join-Path $projectRoot '.env.example') -Raw
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
foreach ($placeholder in @('CHANGE_ME_USE_RANDOM_48_HEX','CHANGE_ME_USE_DIFFERENT_RANDOM_48_HEX')) {
    while ($template.Contains($placeholder)) {
        $randomBytes = New-Object byte[] 24
        $generator.GetBytes($randomBytes)
        $randomValue = ([BitConverter]::ToString($randomBytes)).Replace('-', '').ToLowerInvariant()
        $position = $template.IndexOf($placeholder)
        $template = $template.Substring(0, $position) + $randomValue + $template.Substring($position + $placeholder.Length)
    }
}
$generator.Dispose()
[System.IO.File]::WriteAllText($envPath, $template, (New-Object System.Text.UTF8Encoding($false)))
Write-Host 'Đã tạo .env với bốn mật khẩu ngẫu nhiên khác nhau. Không đưa file này vào Git.'
