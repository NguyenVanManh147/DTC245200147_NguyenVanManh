# Tuần 01 — Client/server và mô hình trao đổi thông điệp

Nguồn đối chiếu: chapter01.pdf, mục 1.1–1.3. Áp dụng bài mẫu sang đề 08: Hệ thống theo dõi bưu gửi.

## Mục tiêu và sản phẩm

- `Tracking.Api`: ASP.NET Core Minimal API, cung cấp HTTP endpoint.
- `Operator.Client`: HttpClient gọi API và in JSON nhận được.
- `Tracking.Contracts`: hợp đồng dữ liệu dùng chung, biên dịch thành thư viện; không chạy riêng.
- `ParcelTracking.sln`: tổ chức các project, không phải một tiến trình của hệ thống.

## Thực hành

1. Chạy `dotnet build ParcelTracking.sln`.
2. Terminal 1: `dotnet run --project src/Tracking.Api --urls http://localhost:5080`.
3. Terminal 2: `Invoke-RestMethod http://localhost:5080/` để thấy tên hệ thống và mốc chương.
4. Chạy `dotnet run --project src/Operator.Client -- create "Mạnh" "An" "Thái Nguyên"`.
5. Dừng API rồi gọi lại client: client báo lỗi kết nối. Chạy lại API và thử lại.

Kết quả mong đợi: API và client là hai tiến trình, yêu cầu đi qua mạng loopback bằng HTTP, phản hồi là JSON; việc dừng API không làm tiến trình client sập toàn bộ hệ thống.

## Giải thích và ôn tập

1. **Ứng dụng phân tán:** các thành phần tự trị phối hợp qua mạng. Dù chạy trên một máy, API và console vẫn có ranh giới tiến trình và lỗi mạng.
2. **Client/server:** client khởi tạo yêu cầu; server lắng nghe, kiểm tra dữ liệu, xử lý và trả phản hồi. Một thành phần có thể đổi vai trò tùy tương tác.
3. **MEP request/response:** nhân viên gửi POST tạo bưu gửi; API trả mã mới. GET tra cứu cũng dùng mô hình này.
4. **One-way message:** bên gửi không đợi kết quả nghiệp vụ trực tiếp; phù hợp khi chuyển tác vụ sang xử lý nền ở chương sau.
5. **Queue:** một thông điệp được giao cho một consumer trong nhóm cạnh tranh; giúp tách producer và consumer về thời gian.
6. **Pub/sub:** nhiều subscriber quan tâm nhận các bản sao độc lập của sự kiện. Khác queue ở phạm vi bên nhận.
7. **Push/streaming:** server đẩy cập nhật sau khi client đăng ký. Ở chương 3, vị trí áp dụng là thông báo trạng thái bưu gửi qua SignalR.
8. **Gọi hàm so với gọi mạng:** gọi mạng có độ trễ, timeout, mất kết nối và lỗi một phần. Cần kiểm tra URL, route, status và JSON.
9. **Minimal API:** `MapGet`/`MapPost` gắn route với handler; DI cung cấp ShipmentStore; `Results` tạo phản hồi HTTP.
10. **Lựa chọn MEP:** tạo/tra cứu cần phản hồi trực tiếp dùng REST; thông báo sau thay đổi dùng push. Các MEP không gắn độc quyền với một công nghệ.

## Ánh xạ mã nguồn

| Nội dung | Vị trí |
| --- | --- |
| Tạo host và định tuyến | `src/Tracking.Api/Program.cs` |
| Tạo request và đọc response | `src/Operator.Client/Program.cs` |
| DTO và enum | `src/Tracking.Contracts/Models.cs` |
| Cấu hình nền tảng .NET 10 | `Directory.Build.props`, `global.json` |

Ở snapshot cuối chapter 3, chương trình client được mở rộng thành các lệnh nghiệp vụ. Bài thực hành chương 1 vẫn minh họa cùng ranh giới HTTP, không cần nhân bản thành nhiều bộ mã gần giống nhau.
