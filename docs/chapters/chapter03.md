# Tuần 03 — SignalR

Nguồn: chapter03.pdf, mục 3.1–3.3. Hub và nhóm được áp dụng cho từng mã bưu gửi.

## Bài thực hành

`Tracking.Api` cung cấp `/hubs/tracking`. `Customer.Client` đăng ký `ShipmentUpdated`, gọi `Watch(code)`, rồi đọc lịch sử qua REST.
Kết nối lại tự động phải đăng ký lại nhóm; lịch sử REST bù các sự kiện bỏ lỡ. Retry lần kết nối đầu được xử lý riêng.

1. Chạy Tracking.Api cổng 5080; không cần service hay broker khác ở mốc này.
2. Tạo hai bưu gửi, chạy Customer.Client với cả hai mã; chạy một client khác chỉ theo dõi mã thứ nhất.
3. Cập nhật mã thứ nhất bằng Operator.Client: hai client đang theo dõi mã đó cùng nhận thông báo. Cập nhật mã thứ hai: chỉ client đăng ký mã thứ hai nhận.
4. Tạm dừng API rồi khởi động lại trong khoảng reconnect. Khách hàng đăng ký lại nhóm và đọc lại lịch sử.
5. Chạy client khi service chưa chạy: thấy retry ban đầu; Ctrl+C dừng nhẹ nhàng.

## Ôn tập và trả lời

- Polling gửi GET liên tục; push gửi khi có thay đổi, giảm request rỗng và độ trễ.
- Request/response có một phản hồi; push do server khởi tạo; streaming duy trì nhiều thông điệp trên một luồng.
- WebSocket là giao thức; SignalR là thư viện hub, groups, reconnect và fallback SSE/long polling.
- Hub quản lý kết nối; `IHubContext<TrackingHub>` cho REST handler gửi sự kiện ngoài hub sau khi dữ liệu được lưu.
- Nhóm `shipment:<code>` tránh phát mọi thông báo cho mọi khách hàng. `On<T>` cần được đăng ký trước khi phát sinh cập nhật.
- REST tạo/đọc dữ liệu; SignalR chỉ chuyển thông tin cập nhật. Reconnect không có nghĩa là phát lại sự kiện đã bỏ lỡ.
- Nếu scale-out nhiều API instance, cần backplane hoặc dịch vụ SignalR quản lý; phiên bản bài tập chạy một instance.
- Polling hợp lý nếu dữ liệu ít thay đổi hoặc hạ tầng không cho phép kết nối lâu dài.

## Bốn bài thực hành áp dụng từ cuối chapter

1. **Luồng hoàn chỉnh:** tạo bưu gửi qua REST, mở Customer.Client, cập nhật InTransit rồi Delivered. Đọc lại REST để đối chiếu thông báo.
2. **Nhánh lỗi Failed:** tạo mã mới, cập nhật InTransit rồi Failed; Customer.Client in cảnh báo riêng. Có thể chuyển Failed → InTransit để thử giao lại.
3. **Theo dõi hai mã:** `dotnet run --project src/Customer.Client -- MA_THU_NHAT MA_THU_HAI`. Các dòng luôn chứa mã bưu gửi để nhận diện.
4. **API chưa chạy:** khởi động client trước, quan sát retry ban đầu. `WithAutomaticReconnect` chỉ xử lý mất kết nối sau khi đã kết nối thành công; vì vậy client có vòng retry lần đầu riêng.

Hub từ chối `Watch` với mã sai hoặc không tồn tại. `Unwatch` rời nhóm. Client đăng ký callback trước `StartAsync`, tham gia nhóm trước khi đọc lịch sử để giảm khoảng hở bỏ lỡ cập nhật; EventId giúp loại bỏ bản trùng giữa REST và SignalR.

Các sự kiện từ REST khôi phục và live push có thể xen kẽ; version cho biết thứ tự nghiệp vụ. Đây là thông báo gần thời gian thực, không phải giao thức đảm bảo nhận tuyệt đối. Sau khi hết bốn lượt reconnect, cần chạy lại client.
