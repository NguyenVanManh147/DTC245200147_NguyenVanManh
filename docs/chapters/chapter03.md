# Tuần 03 — SignalR

Nguồn: chapter03.pdf, mục 3.1–3.3. Hub và nhóm được áp dụng cho từng mã bưu gửi.

## Bài thực hành

`Notification.Service` cung cấp `/hubs/tracking`. `Customer.Client` đăng ký `ShipmentUpdated`, gọi `Watch(code)`, rồi đọc lịch sử qua REST.
Kết nối lại tự động phải đăng ký lại nhóm; lịch sử REST bù các sự kiện bỏ lỡ. Retry lần kết nối đầu được xử lý riêng.

1. Chạy Notification.Service cổng 5081 và Tracking.Api cổng 5080.
2. Tạo hai bưu gửi, chạy Customer.Client với cả hai mã; chạy một client khác chỉ theo dõi mã thứ nhất.
3. Sau khi ghép RabbitMQ ở chapter 06–07, cập nhật cả hai và quan sát phạm vi nhận thông báo.
4. Tạm dừng Notification.Service rồi khởi động lại. Khách hàng đăng ký lại nhóm và đọc lại lịch sử.
5. Chạy client khi service chưa chạy: thấy retry ban đầu; Ctrl+C dừng nhẹ nhàng.

## Ôn tập và trả lời

- Polling gửi GET liên tục; push gửi khi có thay đổi, giảm request rỗng và độ trễ.
- Request/response có một phản hồi; push do server khởi tạo; streaming duy trì nhiều thông điệp trên một luồng.
- WebSocket là giao thức; SignalR là thư viện hub, groups, reconnect và fallback SSE/long polling.
- Hub quản lý kết nối; `IHubContext<TrackingHub>` cho worker gửi sự kiện ngoài hub.
- Nhóm `shipment:<code>` tránh phát mọi thông báo cho mọi khách hàng. `On<T>` cần được đăng ký trước khi phát sinh cập nhật.
- REST tạo/đọc dữ liệu; SignalR chỉ chuyển thông tin cập nhật. Reconnect không có nghĩa là phát lại sự kiện đã bỏ lỡ.
- Nếu scale-out nhiều Notification.Service, cần backplane hoặc dịch vụ SignalR quản lý; phiên bản bài tập chạy một instance.
- Polling hợp lý nếu dữ liệu ít thay đổi hoặc hạ tầng không cho phép kết nối lâu dài.
