# Kết quả kiểm thử đến chapter 3

Ngày thực hiện: 26/11/2026. Môi trường: Windows, .NET SDK 10.0.404, target net10.0.

## Build

`dotnet build ParcelTracking.sln --no-restore --nologo --disable-build-servers -m:1`

Kết quả: **thành công, 0 warning, 0 error**.
Các package SQLite và SignalR sử dụng bản vá đã qua NuGet audit tại thời điểm restore; không tắt cơ chế kiểm tra vulnerability.

## Kiểm thử tích hợp

`dotnet run --project tests/Tracking.Checks --no-build --no-restore`

Kết quả: **41/41 kiểm tra đạt**. API thật chạy trên một cổng loopback trống, database riêng. SignalR client kết nối WebSocket thực, không dùng mock hub.

| Nhóm | Hành vi đã xác nhận |
| --- | --- |
| Chapter 01 | Tiến trình client gọi HTTP đến API độc lập |
| Tạo dữ liệu | 201, Location đúng, mã riêng, Created v1 |
| Gửi lại | Cùng Idempotency-Key không tạo trùng; khóa với nội dung khác trả 409 |
| Lỗi | Dữ liệu rỗng 400, Problem Details, mã không có 404, enum sai hoặc số 400 |
| Nghiệp vụ | Chặn Created → Delivered; cho phép InTransit/AtHub/Failed và thử giao lại; Delivered kết thúc |
| SignalR | Watch hợp lệ, từ chối mã sai; đẩy đúng status/location/version |
| Groups | Khách theo dõi B không nhận A; một khách nhận được cả hai mã khi đăng ký cả hai |
| Unwatch | Rời nhóm thì dừng nhận cập nhật của mã đó |
| Hành trình | Lịch sử đủ 6 sự kiện, version tăng liên tục, UTC và EventId riêng |
| Đồng thời | Hai yêu cầu cùng chuyển Created → InTransit: một 201, một 409, không ghi trùng |
| Khởi động lại | SignalR tự reconnect, đăng ký lại nhóm, đọc lịch sử REST và nhận live push mới |
| Bền vững | Trạng thái Delivered v6 và đủ lịch sử còn nguyên sau khi dừng/khởi động lại API |

Mỗi lần chạy sinh database và log cục bộ trong `artifacts/checks-<mã lần chạy>/`; thư mục artifacts được ignore để không đưa dữ liệu thử nghiệm vào Git và có thể dọn sau khi kiểm tra.
Có thể tái lập kết quả bằng lệnh trên; mỗi lần chạy dùng database và cổng riêng. Kết quả 41/41 ở đây ghi nhận lần kiểm thử đã thực hiện, không phụ thuộc việc giữ lại thư mục tạm của lần chạy đó.

## Giới hạn xác nhận

Các kiểm tra này áp dụng mốc chapter 1–3, một API instance trên loopback. Chưa xác nhận kiến trúc RabbitMQ, triển khai nhiều instance, phân quyền hay Docker của các chương tiếp theo.
Kết nối lại khôi phục theo lịch sử REST, không cam kết SignalR tự lưu và phát lại mọi thông điệp bị bỏ lỡ.

Logging dùng console để chạy được bằng tài khoản thông thường trên Windows; không phụ thuộc quyền ghi Windows Event Log.
