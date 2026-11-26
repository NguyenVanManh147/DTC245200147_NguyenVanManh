param([string]$ApiUrl = 'http://localhost:5080')
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$api = $ApiUrl.TrimEnd('/')
try {
    $null = Invoke-RestMethod -Uri "$api/health/ready"
    $body = @{ sender = 'Nguyễn Văn Mạnh'; recipient = 'Trần An'; location = 'Thái Nguyên' } | ConvertTo-Json
    $shipment = Invoke-RestMethod -Method Post -Uri "$api/shipments" -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
    $code = $shipment.trackingCode
    Write-Host "Đã tạo bưu gửi: $code" -ForegroundColor Green
    Write-Host 'Mở terminal khác tại thư mục dự án và chạy:'
    Write-Host "dotnet run --project src/Customer.Client --no-build -- $code" -ForegroundColor Cyan
    $null = Read-Host 'Khi khách đã kết nối, nhấn Enter để cập nhật hành trình'
    foreach ($status in @('InTransit', 'AtHub', 'Delivered')) {
        $update = @{ status = $status; location = "Điểm xử lý $status"; note = "Demo chapter 3: $status" } | ConvertTo-Json
        $null = Invoke-RestMethod -Method Post -Uri "$api/shipments/$code/events" -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($update))
        Write-Host "Đã cập nhật $status. Kiểm tra thông báo tại terminal khách hàng."
        if ($status -ne 'Delivered') { $null = Read-Host 'Nhấn Enter để sang bước tiếp theo' }
    }
    Invoke-RestMethod -Uri "$api/shipments/$code/history" | Format-Table version,status,location,occurredAt
}
catch {
    Write-Error "Không thực hiện được demo: $($_.Exception.Message). Kiểm tra API đã chạy tại $api."
    exit 1
}
