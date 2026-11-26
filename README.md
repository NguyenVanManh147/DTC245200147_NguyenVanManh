# Đề 08 — Hệ thống theo dõi bưu gửi

Sinh viên: Nguyễn Văn Mạnh — DTC245200147.

Bài tập học phần Phát triển ứng dụng phân tán. C# / .NET 10 / ASP.NET Core Minimal API.
Nội dung được triển khai theo chín chapter người học cung cấp; lịch sử commit ghi nhận các giai đoạn thực hiện trong phiên phát triển hiện tại, không giả lập ngày học.

## Chapter 01 — Client/server và MEP

Chạy API: `dotnet run --project src/Tracking.Api --urls http://localhost:5080`.
Ở terminal khác: `dotnet run --project src/Operator.Client`.
Máy khách gọi HTTP và nhận JSON; hai chương trình là hai tiến trình độc lập.
