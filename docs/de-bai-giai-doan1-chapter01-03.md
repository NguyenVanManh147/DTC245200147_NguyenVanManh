# ĐỀ TÀI 08 — HỆ THỐNG THEO DÕI BƯU GỬI

## Giai đoạn 1: Hoàn thiện theo kiến thức Chapter 01–03

### 1. Nhiệm vụ và giới hạn

Hãy hỗ trợ tôi hoàn thiện đề tài 08 của học phần Phát triển ứng dụng phân tán bằng C# và .NET 10, đồng thời giải thích để tôi hiểu và tự trình bày được mã nguồn.

Hiện tại chỉ triển khai đến hết Chapter 03. Dừng sau khi hoàn thành, kiểm thử và báo cáo mốc này. Không tự chuyển sang Chapter 04 hoặc tích hợp trước công nghệ của các chương tiếp theo.

Đây là một giai đoạn của bài tập lớn. Yêu cầu cuối kì vẫn giữ nguyên; các thành phần chưa phù hợp với giai đoạn này phải được liệt kê là chưa triển khai, không được coi là đã hoàn thành toàn bộ đề 08.

### 2. Tài liệu và workspace

Đọc và đối chiếu các tài liệu tôi đã cung cấp:

- `D:\2_Phát triển ứng dụng phần mềm\1_Tài liệu\08-he-thong-theo-doi-buu-gui.md.pdf`.
- `D:\2_Phát triển ứng dụng phần mềm\1_Tài liệu\HUONG-DAN-CHUNG.md.pdf`.
- Chapter 01, 02 và 03 trong `D:\2_Phát triển ứng dụng phần mềm\Đề cương`.

Workspace bài làm: `D:\2_Phát triển ứng dụng phần mềm\Bài kiểm tra cuối kì\Hệ thống theo dõi bưu gửi`.

Trước khi sửa, kiểm tra mã nguồn, README, nhánh Git và kết quả chạy hiện có. Kế thừa các chức năng hoạt động đúng; không khởi tạo lại dự án, tạo thêm một bản sao hoặc đổi tên project chỉ để khớp cấu trúc minh họa.

Ưu tiên cách tổ chức đơn giản và cách giải thích tương tự ví dụ EduSubmit trong giáo trình, nhưng chuyển nghiệp vụ sang bưu gửi. Không cần sao chép nguyên tên tài nguyên hoặc nghiệp vụ nộp bài của EduSubmit.

Đề gốc và hướng dẫn chung xác định mục tiêu cuối cùng; Chapter 01–03 xác định phạm vi kỹ thuật hiện tại. Các quyết định bổ sung trong bản yêu cầu này phải được ghi là lựa chọn triển khai, không phải yêu cầu nguyên văn của giảng viên.

### 3. Phạm vi kỹ thuật

**Áp dụng trực tiếp kiến thức đã học:**

- C#, .NET 10, ASP.NET Core Minimal API.
- Client/server; HTTP, JSON, REST và HttpClient.
- DTO, kiểm tra đầu vào, mã trạng thái HTTP.
- SignalR, Hub, Group, IHubContext, callback nhận thông báo và reconnect.
- Git và tài liệu hướng dẫn chạy.

**Thành phần hỗ trợ được giữ nếu đã có:**

- SQLite để dữ liệu không mất khi API khởi động lại. Dùng một lớp truy cập dữ liệu đơn giản; không bổ sung ORM hoặc hệ quản trị khác chỉ cho giai đoạn này.
- Cấu hình bằng appsettings và biến môi trường, logging console, kiểm thử tích hợp.
- Các tiện ích sẵn có như version, EventId, Idempotency-Key hoặc CorrelationId có thể giữ nếu hoạt động đúng. Không coi chúng là nội dung bắt buộc của ba chapter và không mở rộng thành hạ tầng nâng cao.

Không triển khai GraphQL, gRPC, RabbitMQ, Worker Service, Docker, Docker Compose hoặc dịch vụ thông báo độc lập ở giai đoạn này. Không thêm CQRS, event sourcing, generic repository hay nhiều tầng abstraction cho một bài thực hành nhỏ.

Chỉ thêm package cần thiết cho chức năng được yêu cầu; ưu tiên bản vá tương thích .NET 10. Giải thích ngắn gọn lý do lựa chọn thư viện và cách lưu dữ liệu.

### 4. Kiến trúc và cấu trúc mã nguồn

```text
Operator Console ── REST ──> Tracking.Api ──> SQLite
Customer Console ── REST ──> Tracking.Api
Customer Console <─ SignalR ─ TrackingHub đặt trong Tracking.Api
```

Tracking.Api xử lý nghiệp vụ, ghi trạng thái hiện tại và lịch sử; chỉ phát thông báo sau khi dữ liệu được lưu thành công.

Giữ cấu trúc đang có:

```text
ParcelTracking.sln
src/
  Tracking.Contracts/
  Tracking.Api/
  Operator.Client/
  Customer.Client/
tests/Tracking.Checks/
requests/
docs/
README.md
```

Tracking.Contracts là thư viện DTO/enum dùng chung, không phải service chạy riêng. Có thể tạo thư mục Models, Services hoặc Hubs khi giúp dễ đọc; không bắt buộc tách mỗi kiểu dữ liệu thành một file.

Giữ ranh giới REST và thông báo rõ ràng để thuận lợi cho các chương sau; chưa tạo sẵn các service, broker hoặc lớp trừu tượng cho tương lai.

### 5. Dữ liệu và quy tắc nghiệp vụ

Giữ tên trường và hợp đồng hiện có nếu đáp ứng nghiệp vụ. Không đổi Sender thành SenderName, Recipient thành ReceiverName hoặc thêm ShipmentId chỉ để khớp một mô hình minh họa khác.

**Shipment tối thiểu:** TrackingCode, Sender, Recipient, Location, Status, CreatedAt, UpdatedAt.

**ShipmentEvent tối thiểu:** EventId, TrackingCode, Location, Status, OccurredAt, Note.

Có thể giữ Version và CorrelationId đã có. TrackingCode là định danh công khai duy nhất của bưu gửi; EventId phân biệt các sự kiện. Không bắt buộc thêm Id nội bộ nếu chưa có nhu cầu.

Quy định hành vi:

- Tạo mới phải sinh mã duy nhất, gán Created và lưu sự kiện đầu tiên.
- Hỗ trợ đủ Created, InTransit, AtHub, Delivered, Failed.
- Người gửi, người nhận và vị trí không được rỗng; giới hạn độ dài phải nhất quán giữa API, client và tài liệu.
- Thời điểm do server tạo, lưu UTC; client có thể hiển thị giờ địa phương.
- Trạng thái hiện tại và lịch sử phải được ghi nhất quán; thao tác thất bại không được thêm lịch sử một phần.
- Lịch sử có thứ tự ổn định: ưu tiên Version nếu đã có; thời gian là thông tin hiển thị, không phải khóa duy nhất để sắp thứ tự.
- Một thay đổi hợp lệ về vị trí vẫn phải được ghi nhận và thông báo dù Status không đổi, ví dụ InTransit ở hai điểm xử lý khác nhau. Nếu cả trạng thái và vị trí không đổi, chọn trả 409; ghi chú đơn lẻ không tạo thêm mốc hành trình. Nếu có Idempotency-Key thì giữ cơ chế trả lại kết quả cũ cho yêu cầu gửi lại đúng khóa. Không cập nhật bưu gửi đã Delivered.
- Delivered là trạng thái kết thúc trong lựa chọn nghiệp vụ của bài. Failed có thể được xử lý lại theo quy tắc đã ghi trong README.

Giữ bảng chuyển trạng thái đã triển khai nếu hợp lý; bổ sung trường hợp giữ nguyên trạng thái nhưng đổi vị trí. Không áp đặt một sơ đồ chuyển trạng thái mới mà không giải thích vì sao phù hợp bài toán.

### 6. Chapter 01 — Client/server và HTTP

Các mục cần hoàn thành hoặc xác nhận lại:

1. Kiểm tra .NET SDK, solution và các project.
2. Chạy Tracking.Api bằng Minimal API.
3. Chạy hai Console client thành các tiến trình riêng.
4. Dùng HttpClient gọi API và đọc JSON phản hồi.
5. Hiển thị lỗi dễ hiểu khi API chưa chạy hoặc địa chỉ không đúng.
6. Giải thích vai trò client/server, request/response và ranh giới tiến trình.

Build và chạy thử phần này trước khi xác nhận hoàn thành chapter. Nếu đã có mã hoạt động thì kiểm chứng lại, không tạo thêm mã chỉ để có commit riêng.

### 7. Chapter 02 — Bốn REST API bắt buộc

Giữ nguyên các endpoint của đề gốc:

| Method | Endpoint | Hành vi và phản hồi |
| --- | --- | --- |
| POST | `/shipments` | Tạo bưu gửi và sự kiện Created; trả 201 Created cùng Location |
| GET | `/shipments/{trackingCode}` | Trả 200 với thông tin hiện tại; mã không tồn tại trả 404 |
| POST | `/shipments/{trackingCode}/events` | Ghi nhận vị trí/trạng thái và lịch sử; chọn 201 cho sự kiện được tạo và ghi rõ DTO trả về |
| GET | `/shipments/{trackingCode}/history` | Trả 200 với lịch sử có thứ tự; mã không tồn tại trả 404 |

Sử dụng DTO và JSON thống nhất. 400 cho đầu vào sai hoặc enum không hợp lệ; 409 cho xung đột nghiệp vụ. Không trả 200 cho mọi trường hợp lỗi.

Hai client phải đọc mã trạng thái trước khi xử lý kết quả thành công. Có timeout cho yêu cầu HTTP và thông báo dễ hiểu khi lỗi kết nối.

Cập nhật file `.http` hoặc hướng dẫn tương đương để thử đủ bốn endpoint, gồm cả trường hợp lỗi. Build và kiểm thử REST trước khi xác nhận hoàn thành chapter.

### 8. Chapter 03 — SignalR theo mã bưu gửi

- Đăng ký SignalR và ánh xạ `/hubs/tracking` trong Tracking.Api.
- Giữ hợp đồng hiện có: `Watch(trackingCode)`, `Unwatch(trackingCode)` và sự kiện `ShipmentUpdated`. Không đổi tên chỉ vì khác ví dụ đề xuất.
- Tên group: `shipment:{trackingCode}`. Hub kiểm tra mã hợp lệ và bưu gửi tồn tại trước khi cho đăng ký.
- REST handler dùng IHubContext để gửi DTO sự kiện sau khi lưu thành công.
- Khách chỉ nhận cập nhật của các mã đã đăng ký; một khách có thể theo dõi nhiều mã.
- Thông báo gồm mã bưu gửi, trạng thái, vị trí, thời điểm và thông tin nhận diện sự kiện để đối chiếu lịch sử.
- Client đăng ký callback trước khi bắt đầu nhận thông báo; tham gia group trước khi đọc lại dữ liệu nhằm giảm khoảng hở bỏ lỡ cập nhật.
- Khi kết nối lại, phải đăng ký lại các group và đồng bộ lịch sử qua REST. Nếu dùng EventId, loại trùng giữa dữ liệu khôi phục và live push.
- Xử lý retry lần kết nối đầu riêng; không mô tả WithAutomaticReconnect là cơ chế tự thử mọi lỗi khởi tạo kết nối.
- Có thời hạn hoặc số lượt thử lại rõ ràng; sau khi hết lượt phải báo cách khởi động lại hoặc kết nối lại cho người dùng.
- Không để việc gửi thông báo thất bại làm client hiểu nhầm rằng dữ liệu đã lưu cũng thất bại. Ghi log và cho phép đọc lại qua REST.

Luồng nghiệm thu: nhân viên cập nhật bằng REST → API lưu → API phát SignalR → khách đúng group nhận và hiển thị thay đổi.

Nhóm SignalR chỉ phân luồng thông báo, chưa thay thế xác thực/phân quyền. Giai đoạn này chạy một API instance; không tuyên bố SignalR lưu bền hoặc đảm bảo nhận mọi thông điệp khi offline.

### 9. Giao diện Console

Ưu tiên menu tiếng Việt dễ sử dụng. Khi chương trình chạy không có đối số, mở menu; giữ chế độ dòng lệnh đang có để thuận tiện demo và kiểm thử.

**Operator.Client:**

```text
1. Tạo bưu gửi
2. Tra cứu bưu gửi
3. Cập nhật trạng thái và vị trí
4. Xem lịch sử hành trình
0. Thoát
```

**Customer.Client:**

```text
1. Tra cứu bưu gửi
2. Xem lịch sử hành trình
3. Đăng ký theo dõi bưu gửi
4. Hủy theo dõi bưu gửi
5. Xem các mã đang theo dõi
0. Thoát
```

Nhập sai lựa chọn, mã hoặc trạng thái không làm chương trình thoát đột ngột. Hiển thị mã vừa tạo để dễ sao chép; lịch sử có cột/trường rõ ràng. Khi Failed, hiển thị cảnh báo dễ nhận biết.

Thông báo SignalR vẫn hiển thị khi đang ở menu; đồng bộ thao tác in console nếu cần, tránh thông báo và lời nhắc bị trộn khó đọc. Khi thoát, đóng kết nối và dừng các lần thử lại.

Không xây dựng Web App hoặc cài thêm thư viện giao diện chỉ cho giai đoạn này.

### 10. Kiểm thử và tiêu chí hoàn thành

Đối chiếu từng yêu cầu với kiểm thử có thể tái lập:

1. Build toàn solution thành công; ghi số warning/error thực tế.
2. Tạo bưu gửi, nhận 201 và Location, mã không trùng, có Created trong lịch sử.
3. Tra cứu mã tồn tại và không tồn tại; kiểm tra cả lịch sử của mã không tồn tại.
4. Cập nhật trạng thái và vị trí; xác nhận trạng thái hiện tại khớp sự kiện mới.
5. Giữ nguyên trạng thái nhưng đổi vị trí: lưu một sự kiện mới và nhận thông báo.
6. Đầu vào rỗng, enum sai, dữ liệu trùng và chuyển trạng thái bị cấm trả lỗi đúng, không làm hỏng lịch sử.
7. Thử đủ năm trạng thái bằng luồng hợp lệ, gồm Failed và xử lý lại.
8. Hai khách theo dõi hai mã không nhận nhầm; một khách theo dõi hai mã nhận đúng cả hai.
9. Hủy theo dõi thì không còn nhận live push của mã đó.
10. Mất kết nối tạm thời: reconnect, đăng ký lại group, khôi phục lịch sử và nhận tiếp cập nhật mới.
11. API chưa chạy: client hiển thị lỗi hoặc retry có thông báo; người dùng vẫn có thể thoát.
12. Khởi động lại API: nếu dùng SQLite, dữ liệu và lịch sử còn nguyên.
13. Thử trực tiếp các thao tác menu trên hai Console client; không chỉ kiểm thử API thay cho kiểm thử giao diện.

Tận dụng kiểm thử tích hợp hiện có và chỉ bổ sung kiểm tra cho hành vi mới hoặc chưa được xác nhận. Không giả lập kết quả, không giữ nguyên số lượng kiểm thử cũ nếu bộ kiểm thử đã thay đổi. Nếu không chạy được bước nào, ghi rõ bước, nguyên nhân và ảnh hưởng đến nghiệm thu.

### 11. Git và tài liệu

Repository: `https://github.com/NguyenVanManh147/DTC245200147_NguyenVanManh`.

Làm việc và đồng bộ phần bưu gửi trên nhánh mặc định `he-thong-theo-doi-buu-gui`. Chỉ giữ nội dung phục vụ đề 08 đến hết Chapter 03 trong lần bàn giao này.

Tạo commit theo thay đổi thực tế: sửa nghiệp vụ, hoàn thiện client, kiểm thử hoặc tài liệu. Không giả ngày commit, tạo commit rỗng hoặc viết lại lịch sử chỉ để mô phỏng ba tuần học.

README tiếng Việt phải có: phạm vi đến chapter 3; kiến trúc; vai trò project; cách build/chạy; thao tác menu và dòng lệnh; bốn API; cấu hình địa chỉ/lưu trữ; kiểm thử; giới hạn; các yêu cầu cuối kì còn lại.

Cập nhật tài liệu từng chapter và kết quả kiểm thử khi hành vi thay đổi. Không đưa database, bin/obj, log chạy thử hoặc thông tin bí mật lên GitHub.

### 12. Báo cáo bàn giao và điểm dừng

Khi hoàn thành, báo cáo ngắn gọn:

- Chức năng đã làm và kiến thức tương ứng từng chapter.
- Những thay đổi so với workspace ban đầu; các file quan trọng và vai trò.
- Lệnh chạy API, Operator.Client, Customer.Client và kiểm thử.
- Kết quả build/kiểm thử thực tế, hạn chế hoặc bước chưa xác nhận.
- Commit, nhánh và trạng thái đồng bộ GitHub.
- Yêu cầu cuối kì chưa triển khai và hướng học Chapter 04, chỉ mô tả bằng văn bản.

Chỉ bắt đầu bằng việc kiểm tra workspace và lập danh sách phần còn thiếu. Sau đó thực hiện những thay đổi cần thiết để đạt tiêu chí trên. Hoàn thành đến hết Chapter 03 thì dừng; không tự triển khai chương tiếp theo.
