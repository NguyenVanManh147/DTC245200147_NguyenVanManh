# Kết quả kiểm thử đến chapter 3

Ngày thực hiện: 26/11/2026. Môi trường: Windows, .NET SDK 10.0.404, target net10.0.

## Build

`dotnet build ParcelTracking.sln --no-restore --nologo --disable-build-servers -m:1`

Kết quả: **thành công, 0 warning, 0 error**.
Các package SQLite và SignalR sử dụng bản vá đã qua NuGet audit tại thời điểm restore; không tắt cơ chế kiểm tra vulnerability.

## Kiểm thử tích hợp

`dotnet run --project tests/Tracking.Checks --no-build --no-restore`

Kết quả: **73/73 kiểm tra đạt**. API thật chạy trên một cổng loopback trống, database riêng. SignalR client kết nối WebSocket thực, không dùng mock hub. Bộ kiểm thử cũng chạy đúng Operator.Client và Customer.Client, nhập lựa chọn qua stdin và đọc kết quả stdout; đây là kiểm thử Console App tự động, không thay thế bằng một client giả cho menu.

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
| Chỉ đổi vị trí | Giữ InTransit, đổi Hà Nội → Lào Cai: 201, thêm đúng một sự kiện và gửi live push |
| Trùng vị trí/trạng thái | 409, không ghi trùng dù ghi chú khác; replay đúng khóa trả kết quả cũ, client loại push trùng |
| Menu Operator | Tạo, tra cứu, cập nhật, lịch sử, thoát; nhập lựa chọn/trạng thái sai vẫn tiếp tục; tiếng Việt UTF-8 |
| Menu Customer | Tra cứu hiện trạng và lịch sử độc lập; đăng ký, danh sách mã, hủy và thoát |
| Thông báo trong menu | Nhận live push khi đợi nhập; hủy thì dừng nhận, đăng ký lại đọc các mốc bị bỏ lỡ |
| Cảnh báo | Console hiển thị cảnh báo Failed |
| Console reconnect | Dừng API rồi khởi động lại: Console Customer tự nối lại, vào nhóm, đọc REST và nhận push tiếp, không lặp dữ liệu cũ |
| Retry ban đầu | Mở Console trước API rồi bật API: tự kết nối; nếu API vẫn tắt thì hết 3 lần thử, quay về menu và thoát được |
| Tương thích CLI | Operator vẫn dùng được lệnh get; Customer vẫn nhận mã theo dõi qua đối số |

Mỗi lần chạy sinh database và log cục bộ trong `artifacts/checks-<mã lần chạy>/`; thư mục artifacts được ignore để không đưa dữ liệu thử nghiệm vào Git và có thể dọn sau khi kiểm tra.
Có thể tái lập kết quả bằng lệnh trên; mỗi lần chạy dùng database và cổng riêng. Kết quả 73/73 ghi nhận lần kiểm thử sau khi hoàn thiện các chức năng còn thiếu. Kết quả không phụ thuộc việc giữ lại thư mục tạm của lần chạy đó.

## Đối chiếu tiêu chí giai đoạn 1

| Tiêu chí | Kết quả |
| --- | --- |
| Client/server .NET 10, HTTP/JSON và Console riêng | Đạt |
| Bốn REST API, DTO và mã trạng thái đúng | Đạt |
| Năm trạng thái, lịch sử, đổi vị trí và lưu dữ liệu | Đạt |
| Hub trong API, nhóm theo mã, phát sau khi lưu | Đạt |
| Theo dõi nhiều mã, hủy và khôi phục sau reconnect | Đạt |
| Hai menu, lỗi đầu vào, tra cứu độc lập và thoát | Đạt |
| README, HTTP mẫu và giải thích từng chapter | Đã cập nhật theo phiên bản hiện tại |
| Dừng ở chapter 3 | Giữ phạm vi; không triển khai broker, GraphQL, gRPC hay Docker |

## Giới hạn xác nhận

Các kiểm tra này áp dụng mốc chapter 1–3, một API instance trên loopback. Chưa xác nhận kiến trúc RabbitMQ, triển khai nhiều instance, phân quyền hay Docker của các chương tiếp theo.
Kiểm thử menu được tự động hóa qua stdin/stdout; bố cục khi gõ từng ký tự trong một cửa sổ terminal cụ thể không được kiểm tra bằng ảnh chụp giao diện.
Kết nối lại khôi phục theo lịch sử REST, không cam kết SignalR tự lưu và phát lại mọi thông điệp bị bỏ lỡ.

Logging dùng console để chạy được bằng tài khoản thông thường trên Windows; không phụ thuộc quyền ghi Windows Event Log.
