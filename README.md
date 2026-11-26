# Đề 08 — Hệ thống theo dõi bưu gửi: chapter 01–03

**Sinh viên:** Nguyễn Văn Mạnh — **MSSV:** DTC245200147.

Phiên bản thực hành đến hết **chapter 3**, học phần Phát triển ứng dụng phân tán.
C# / .NET 10 / ASP.NET Core Minimal API / SQLite / SignalR; hai client dạng Console.
Đã hoàn thiện menu của hai client, tra cứu/hủy theo dõi phía khách và cập nhật vị trí khi giữ trạng thái. Build không lỗi/cảnh báo; bộ kiểm thử hiện tại đạt **73/73**.

## Nội dung đã hoàn thành

| Chapter | Nội dung học | Áp dụng vào đề 8 |
| --- | --- | --- |
| 01 | Client/server, request/response, Minimal API, HttpClient | API và client chạy thành các tiến trình riêng, trao đổi HTTP/JSON |
| 02 | REST, DTO, URI, HTTP status và xử lý lỗi | Tạo bưu gửi, sinh mã, cập nhật trạng thái/vị trí, tra cứu trạng thái và lịch sử |
| 03 | SignalR hub, groups, reconnect, kết hợp REST và push | Khách theo dõi một hoặc nhiều mã, nhận cập nhật ngay, đọc lịch sử khi kết nối lại |

Đây là mốc trung gian của đề 8. Kiến trúc RabbitMQ → Notification Service độc lập và đóng gói Docker của bài cuối kì sẽ được thực hiện ở các chương sau. Ở mốc chapter 3, chức năng thông báo nằm trong Tracking.Api và dùng `IHubContext` đúng nội dung bài học.

## Kiến trúc hiện tại

```mermaid
flowchart LR
    O[Operator Console] -->|REST HTTP/JSON| A[Tracking.Api]
    A -->|Transaction| D[(SQLite)]
    C[Customer Console] -->|REST: trạng thái và lịch sử| A
    C -->|Watch: đăng ký nhóm theo mã| H[SignalR Hub trong API]
    A -->|Sau khi lưu: ShipmentUpdated| H
    H -->|Push đúng nhóm| C
```

```text
src/
  Tracking.Contracts/  DTO, enum trạng thái, quy tắc chuyển trạng thái
  Tracking.Api/        Bốn REST endpoint, SQLite, SignalR hub
  Operator.Client/     Nhân viên tạo, cập nhật và tra cứu bưu gửi
  Customer.Client/     Khách xem lịch sử và nhận thông báo trực tiếp
tests/Tracking.Checks/ Kiểm tra tích hợp HTTP + SignalR với API thật
docs/chapters/         Hướng dẫn và giải thích cho từng chapter
requests/             HTTP mẫu để thao tác trong IDE
```

## Cài đặt và build

Cần .NET SDK 10.x; lần restore đầu cần Internet. Không cần Docker ở mốc này.
Mở PowerShell tại thư mục có `ParcelTracking.sln`:

```powershell
dotnet restore ParcelTracking.sln
dotnet build ParcelTracking.sln --no-restore
```

## Chạy bằng menu

Mở ba terminal tại thư mục dự án. Terminal thứ nhất chạy API; hai terminal còn lại chạy client không có đối số:

```powershell
# Terminal 1
dotnet run --project src/Tracking.Api --no-build --urls http://localhost:5080
# Terminal 2
dotnet run --project src/Operator.Client --no-build
# Terminal 3
dotnet run --project src/Customer.Client --no-build
```

Operator có menu tạo, tra cứu, cập nhật và xem lịch sử. Customer có menu tra cứu, lịch sử, đăng ký/hủy theo dõi và danh sách mã đang theo dõi. Chọn `0` để thoát. Nhập sai lựa chọn hoặc trạng thái sẽ báo lỗi rồi quay lại menu.

Tạo bưu gửi ở Operator, sao chép mã sang Customer và chọn `3` để theo dõi. Sau đó cập nhật tại Operator; thông báo xuất hiện ngay trong menu Customer. Chọn `4` ở Customer để hủy theo dõi. Tra cứu và xem lịch sử bằng mục `1`/`2` hoạt động qua REST, không cần đăng ký SignalR.

Customer thử kết nối đầu tối đa 3 lần, mỗi lần timeout 5 giây, chờ 1/2 giây giữa các lần. Nếu API chưa chạy, có thể bật API trong lúc thử lại; sau khi hết lượt, menu báo lỗi và cho chọn lại hoặc thoát. Ctrl+C hủy thao tác đang chờ. Sau kết nối thành công, mất mạng tạm thời dùng 4 lượt automatic reconnect (0/2/5/10 giây), đăng ký lại nhóm và đọc lịch sử.

## Chạy bằng dòng lệnh trong ba terminal

**Terminal 1 — API:**

```powershell
dotnet run --project src/Tracking.Api --no-build --urls http://localhost:5080
```

**Terminal 2 — Nhân viên tạo bưu gửi:**

```powershell
dotnet run --project src/Operator.Client --no-build -- create "Nguyễn Văn Mạnh" "Trần An" "Thái Nguyên"
```

Sao chép trường `trackingCode` trong JSON (bắt đầu bằng `BG`). Ví dụ dưới đây dùng `MA_BUU_GUI` làm chỗ điền mã thật.

**Terminal 3 — Khách bắt đầu theo dõi:**

```powershell
dotnet run --project src/Customer.Client --no-build -- MA_BUU_GUI
```

**Quay lại terminal 2 — Cập nhật hành trình:**

```powershell
dotnet run --project src/Operator.Client --no-build -- update MA_BUU_GUI InTransit "Hà Nội" "Đã xuất kho"
dotnet run --project src/Operator.Client --no-build -- update MA_BUU_GUI AtHub "Bưu cục nhận" "Đến điểm xử lý"
dotnet run --project src/Operator.Client --no-build -- update MA_BUU_GUI Delivered "Địa chỉ người nhận" "Giao thành công"
dotnet run --project src/Operator.Client --no-build -- get MA_BUU_GUI
dotnet run --project src/Operator.Client --no-build -- history MA_BUU_GUI
```

Terminal 3 nhận các dòng `[SignalR] ... InTransit/AtHub/Delivered` mà không phải gọi GET liên tục.
Để theo dõi hai mã, truyền hai đối số cho Customer.Client. Ctrl+C dừng client.
Client tự thử lại khi API chưa chạy, tự nối lại khi kết nối bị ngắt tạm thời và đăng ký lại nhóm khi kết nối mới được lập.

Có thể chạy `powershell -ExecutionPolicy Bypass -File scripts/demo.ps1` sau khi API chạy để tạo dữ liệu và hướng dẫn trình diễn từng bước.

## API và dữ liệu

| Method | Endpoint | Kết quả |
| --- | --- | --- |
| POST | `/shipments` | 201 + Location, sinh mã theo dõi |
| GET | `/shipments/{trackingCode}` | 200 + trạng thái hiện tại hoặc 404 |
| POST | `/shipments/{trackingCode}/events` | 201 + trạng thái mới; phát SignalR sau khi lưu |
| GET | `/shipments/{trackingCode}/history` | 200 + lịch sử theo version tăng dần hoặc 404 |
| GET | `/health/live`, `/health/ready` | Kiểm tra tiến trình và SQLite |
| SignalR | `/hubs/tracking` | `Watch(code)`, `Unwatch(code)`, sự kiện `ShipmentUpdated` |

Body tạo: `{"sender":"Mạnh","recipient":"An","location":"Thái Nguyên"}`.
Body cập nhật: `{"status":"InTransit","location":"Hà Nội","note":"Đã xuất kho"}`.

Các trạng thái: `Created`, `InTransit`, `AtHub`, `Delivered`, `Failed`.
Quy tắc: Created → InTransit/AtHub/Failed; InTransit → AtHub/Delivered/Failed; AtHub → InTransit/Delivered/Failed; Failed → InTransit/AtHub; Delivered là kết thúc.
Các trạng thái chưa kết thúc được giữ nguyên khi chuyển sang vị trí khác; mỗi lần đổi vị trí tạo một sự kiện và gửi SignalR. Ví dụ `update MA_BUU_GUI InTransit "Lào Cai" "Qua điểm trung chuyển"` sau khi đang InTransit tại Hà Nội.
Nếu trạng thái và vị trí đều không đổi (bỏ khoảng trắng hai đầu và không phân biệt hoa/thường ở vị trí), trả 409; thay ghi chú đơn lẻ không tạo mốc hành trình mới. Delivered không cho cập nhật tiếp kể cả chỉ đổi vị trí.
Người gửi/nhận/vị trí: 1–200 ký tự; ghi chú tối đa 1000 ký tự.
400 cho dữ liệu sai, 404 cho mã không tồn tại, 409 cho chuyển trạng thái trái quy tắc.

SQLite tự tạo ở `src/Tracking.Api/data/tracking.db` khi dùng `dotnet run --project`; đường dẫn tương đối với working directory của tiến trình API. Có thể đặt `Storage__Path` bằng đường dẫn tuyệt đối.
Mỗi thao tác ghi trạng thái và lịch sử trong cùng transaction. Dữ liệu vẫn còn khi khởi động lại; thời điểm lưu UTC, client hiển thị giờ địa phương.
Header `Idempotency-Key` là bổ sung để thử lại POST mà không tạo trùng; `X-Correlation-ID` hỗ trợ đối chiếu log.

Đổi cổng/địa chỉ bằng `--urls` cho API và `$env:TRACKING_API_URL = "http://localhost:5080"` cho hai client.

## Kiểm tra tự động

```powershell
dotnet run --project tests/Tracking.Checks
```

Chương trình tự mở API ở một cổng trống, dùng database kiểm thử riêng trong `artifacts/`, kiểm tra REST, nhóm SignalR, theo dõi nhiều mã, lỗi, cập nhật đồng thời và dữ liệu sau restart, rồi dừng đúng tiến trình do nó tạo.
Các client kiểm thử dùng kết nối SignalR thật; không cần mở API thủ công trước. Bộ kiểm thử còn chạy chính hai Console App bằng stdin/stdout để thử menu, dữ liệu tiếng Việt, đăng ký/hủy, thông báo trong menu, retry ban đầu và reconnect.

## Tài liệu học và giới hạn của mốc này

- [Chapter 01: Client/server và MEP](docs/chapters/chapter01.md)
- [Chapter 02: RESTful API](docs/chapters/chapter02.md)
- [Chapter 03: SignalR](docs/chapters/chapter03.md)
- [Báo cáo tiến độ chương 1–3](docs/bao-cao-chuong01-03.md)
- [Kết quả kiểm thử: 73/73 đạt](docs/kiem-thu-chuong01-03.md)
- [Bản yêu cầu hoàn thiện giai đoạn 1 đã rà soát](docs/de-bai-giai-doan1-chapter01-03.md)

Thông báo SignalR không được lưu bền trong kết nối: nếu offline, client đọc lại lịch sử REST. Nếu hết lượt reconnect, client hướng dẫn chạy lại để đồng bộ.
Nhóm theo mã phục vụ minh họa phạm vi thông báo; phiên bản học tập chưa có xác thực/phân quyền và chỉ chạy một API instance. Không coi nhóm SignalR là cơ chế phân quyền.
Lịch sử commit ghi nhận quá trình phát triển thực tế trong phiên làm bài, không thay đổi ngày commit để giả lập các tuần học.
