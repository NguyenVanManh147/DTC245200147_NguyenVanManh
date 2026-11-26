# Tuần 02 — RESTful API

Nguồn: chapter02.pdf, mục 2.1–2.3. Áp dụng tài nguyên bưu gửi thay cho bài nộp trong ví dụ EduSubmit.

## Bài thực hành đã triển khai

DTO ở `src/Tracking.Contracts/Models.cs`; bốn endpoint đề bài ở `src/Tracking.Api/Program.cs`.
SQLite lưu dữ liệu qua lần khởi động. `Operator.Client` xử lý HTTP thành công và lỗi, có timeout 10 giây.
Mẫu yêu cầu đầy đủ nằm ở `requests/shipments.http`.

1. Chạy API tại cổng 5080. Chạy client `create "Mạnh" "An" "Thái Nguyên"` và lưu mã bưu gửi trả về.
2. Chạy `get <mã>`, `update <mã> InTransit "Hà Nội"`, rồi `history <mã>`.
3. Gửi người gửi rỗng: nhận 400. Tra mã `UNKNOWN`: nhận 404.
4. Chuyển trực tiếp `Created` sang `Delivered`: nhận 409. Gửi lại POST cùng `Idempotency-Key`: không tạo sự kiện trùng.
5. Khi đang InTransit tại Hà Nội, giữ InTransit và đổi vị trí sang Lào Cai: nhận 201 và thêm một mốc lịch sử. Gửi lại cùng trạng thái/vị trí với khóa mới: 409; không ghi thêm chỉ vì đổi ghi chú.

Chạy Operator.Client không có đối số để dùng menu. Có thể tạo, tra cứu, cập nhật và xem lịch sử mà không phải nhớ cú pháp dòng lệnh. Chọn sai hoặc nhập trạng thái sai sẽ báo lỗi và quay lại menu.

## Giải thích khi trình bày

- HTTP gồm method, URI, headers và body; phản hồi có status, headers và body.
- GET đọc tài nguyên, POST tạo bưu gửi hoặc thêm sự kiện; URI biểu diễn danh từ và quan hệ tài nguyên con.
- Path xác định bưu gửi; query dành cho lọc/phân trang nếu mở rộng danh sách.
- 201 kèm Location chỉ tài nguyên đã tạo; 400 sai dữ liệu; 404 không tồn tại; 409 xung đột nghiệp vụ.
- Stateless nghĩa là mỗi request có đủ thông tin xử lý, vẫn được phép lưu dữ liệu nghiệp vụ trong database.
- DTO giữ ổn định hợp đồng JSON khi cấu trúc lưu trữ thay đổi; client phải xem status trước khi giải mã kết quả.

Kết quả cần quan sát: mã do server sinh, lịch sử bắt đầu bằng Created, version tăng, lỗi có thông điệp giải thích.
