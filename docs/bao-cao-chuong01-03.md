# Báo cáo tiến độ đề 08 — đến chapter 3

**Sinh viên:** Nguyễn Văn Mạnh — **MSSV:** DTC245200147.

## 1. Bài toán và phạm vi

Nhân viên tạo bưu gửi và ghi nhận vị trí/trạng thái tại các điểm xử lý. Khách hàng dùng mã theo dõi để tra cứu và nhận thay đổi gần thời gian thực.
Mốc này áp dụng ba chương đầu: kiến trúc client/server, RESTful API và SignalR. Đây là báo cáo tiến độ; các yêu cầu RabbitMQ, Notification Service độc lập và Docker của phiên bản cuối chưa thuộc mốc này.

## 2. Phân tích yêu cầu

| Yêu cầu đề 8 | Thực hiện tại chapter 3 |
| --- | --- |
| Tạo bưu gửi, sinh mã | POST /shipments, mã BG + GUID |
| Cập nhật vị trí/trạng thái | POST /shipments/{code}/events, kiểm tra quy tắc chuyển trạng thái |
| Lưu lịch sử | SQLite, EventId và version, thời điểm UTC |
| Ghi nhận sự kiện thay đổi | Lưu ShipmentEvent trong cùng transaction với trạng thái |
| Thông báo đến người theo dõi | SignalR trực tiếp từ API qua nhóm theo mã |
| Tra cứu trạng thái | GET /shipments/{code} |
| Tra cứu hành trình | GET /shipments/{code}/history |
| Created/InTransit/AtHub/Delivered/Failed | Enum dùng chung, JSON biểu diễn bằng chuỗi |
| Luồng qua RabbitMQ và service thông báo riêng | Dành cho giai đoạn tiếp theo |

## 3. Thiết kế thành phần

- Tracking.Contracts quy định DTO, enum, quy tắc nghiệp vụ và JSON options dùng chung.
- Tracking.Api có REST handlers, ShipmentStore, TrackingHub. DI đăng ký store singleton; khóa ghi và transaction bảo vệ thay đổi trạng thái/lịch sử.
- Operator.Client nhận lệnh tạo/đọc/cập nhật/lịch sử, dùng HttpClient có timeout, in status và nội dung lỗi.
- Customer.Client thiết lập hub connection, theo dõi nhiều mã và khôi phục lịch sử sau reconnect.

Hai Console client cung cấp menu tương tác khi chạy không có đối số, đồng thời giữ cách chạy bằng dòng lệnh. Customer có tra cứu/lịch sử độc lập qua REST, đăng ký/hủy và danh sách mã theo dõi; callback vẫn in thông báo trong khi người dùng ở menu. CustomerSession chịu trách nhiệm kết nối và danh sách đăng ký, ConsoleView đồng bộ xuất console.

Ba tiến trình chạy khi trình diễn gồm API, console nhân viên và console khách hàng. SQLite được nhúng trong tiến trình API. Phần hub đang cùng API là thiết kế phù hợp nội dung chương 3; sẽ tách ranh giới ở chương xử lý bất đồng bộ.

## 4. Dữ liệu và hợp đồng

Shipment gồm TrackingCode, Sender, Recipient, Location, Status, CreatedAt, UpdatedAt, Version.
ShipmentEvent gồm EventId, TrackingCode, Status, Location, OccurredAt, Note, Version, CorrelationId.

Database có bảng shipments lưu trạng thái hiện tại, events lưu các sự kiện duy nhất theo (code, version), requests lưu kết quả theo Idempotency-Key.
Các giá trị SQL được truyền bằng parameter. Mỗi thay đổi ghi shipment và event trong một transaction.
Với bưu gửi chưa Delivered, cùng trạng thái tại vị trí mới được ghi thành sự kiện mới. Cùng trạng thái và vị trí thì 409, kể cả chỉ thay ghi chú; ghi lại cùng Idempotency-Key trả kết quả cũ. Delivered không cho chỉnh tiếp. Đây là lựa chọn quy tắc của bài, được ghi rõ để trình bày.

201 xác nhận thao tác đã lưu; 400 cho sai dữ liệu, 404 cho mã không tồn tại, 409 cho xung đột nghiệp vụ.
DTO tách cấu trúc truyền HTTP khỏi lược đồ SQLite. Mã theo dõi do server sinh để không phụ thuộc dữ liệu client nhập.

## 5. Luồng giao tiếp

1. Operator gửi POST tạo bưu gửi. API kiểm tra, lưu Created v1 và phản hồi 201 + Location.
2. Customer nối hub, đăng ký handler, gọi Watch(code) để vào nhóm, đọc lịch sử qua REST.
3. Operator gửi POST cập nhật. API xác minh quy tắc, ghi trạng thái và sự kiện trong transaction.
4. API dùng IHubContext gửi ShipmentUpdated tới nhóm shipment:<code>; các mã khác không bị phát kèm.
5. Nếu mất kết nối, Customer thử nối lại, đăng ký lại nhóm và đọc lịch sử REST. EventId loại bản trùng.

REST thể hiện request/response; SignalR thể hiện server push. Dữ liệu thay đổi độc lập với nhịp client gửi yêu cầu; khách không polling định kỳ.

## 6. Kịch bản kiểm tra và trình bày

- Bình thường: Created → InTransit → AtHub → Delivered; đối chiếu state, history và thông báo.
- Sự cố giao hàng: InTransit → Failed → InTransit → Delivered; client in cảnh báo Failed.
- Hai mã, nhiều khách: khách chỉ nhận nhóm đã đăng ký; một khách có thể đăng ký cả hai.
- Sai đầu vào: rỗng, enum không hợp lệ, mã không tồn tại và chuyển trạng thái trái quy tắc.
- Khởi động lại API: dữ liệu SQLite còn nguyên; đọc lịch sử khôi phục.
- Client chạy trước API: retry kết nối đầu; API bị ngắt sau kết nối: reconnect rồi đăng ký lại nhóm.

Lệnh build, chạy ba terminal và kiểm tra tự động được ghi trong README. `tests/Tracking.Checks` mở API thật và dùng SignalR client thật để kiểm tra hành vi, database kiểm thử tách khỏi dữ liệu demo.
Bộ kiểm thử mở cả hai Console App và điều khiển stdin/stdout: tạo/tra cứu/cập nhật/lịch sử từ menu, nhập sai, tiếng Việt, theo dõi/hủy, live push, khôi phục sau restart và retry trước khi API chạy. Không dùng kết quả kiểm tra hub thay cho bằng chứng chạy menu thực tế.

## 7. Đánh giá và bước tiếp theo

Phiên bản hoàn thiện giai đoạn 1 đã build với 0 warning/0 error và chạy đạt 73/73 kiểm tra. Những phần từng thiếu — menu hai client, tra cứu/hủy theo dõi phía khách và cập nhật vị trí khi giữ trạng thái — đã được triển khai, kiểm tra bằng API và Console thật. Kết quả chi tiết ở `kiem-thu-chuong01-03.md`.

Mốc chapter 3 đáp ứng chức năng nghiệp vụ và thông báo trực tiếp để thực hành ba chương đầu. Các giới hạn hiện tại: một API instance; chưa xác thực/phân quyền; SignalR không lưu thông báo bền vững; phải đọc REST history khi offline.
Ở mốc này chưa thể coi toàn bộ kiến trúc cuối kì đã hoàn thành. Tiếp theo sẽ triển khai đúng từng chapter theo yêu cầu người học, giữ nguyên các hợp đồng REST cơ bản.
