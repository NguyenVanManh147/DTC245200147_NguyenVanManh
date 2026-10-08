# Đối chiếu hiện trạng trước khi sửa

Sinh viên: **Nguyễn Văn Mạnh — DTC245200147**. Kiểm tra ngày **08/10/2026**, múi giờ Asia/Saigon.

Workspace đúng: `D:\5_Thi_TrienKhaiThietKe\DTC245200147_NguyenVanManh`.
Ban đầu workspace trống, không có README, source, Compose, cấu hình hoặc `.git`.
Tuy nhiên nhãn Docker `com.docker.compose.project.working_dir` của dự án **portfolio-manh** trỏ đúng thư mục này.
Một dự án khác **dtc245200147** trỏ thư mục `NguyenVanManh_DTC245200147`; dự án đó không được chỉnh sửa.

Công nghệ xác minh từ container: WordPress 7.1.2, PHP 8.3.35/Apache, theme Twenty Twenty-Five, MySQL 8.4, Nginx 1.30.5, Prometheus 3.15.0, Grafana 13.2.3, Loki 3.6.0, Blackbox 0.28.0 và Alloy 1.17.1. Đây là phiên bản đã quan sát, không phải khẳng định phiên bản mới nhất.

| Yêu cầu | Hiện trạng trước sửa | Phần thiếu hoặc lỗi | Cách xử lý |
|---|---|---|---|
| Portfolio có quản trị | WordPress trả HTTP 200; có Trang chủ, Kỹ năng, Dự án, Liên hệ và `/wp-login.php` | Không còn source/cấu hình trên host | Giữ WordPress và volume; xuất WXR, sao chép uploads, khôi phục Compose |
| Giới thiệu, kỹ năng, dự án, liên hệ | Nội dung cá nhân tồn tại trong database; Trang chủ giới thiệu Nguyễn Văn Mạnh | Chưa có bản xuất trong repository | Xuất nội dung hiện có; không thay nội dung hoặc theme |
| MySQL + phpMyAdmin | Container đang chạy, database `portfolio_db`, user `portfolio_user` | Mật khẩu root trong container không đăng nhập được vào database hiện có | Sao lưu bằng user ứng dụng; giữ root và ghi giới hạn; kiểm tra kết nối user ứng dụng |
| Docker Compose | Nhãn container chỉ đến `compose.yaml` trong workspace | File Compose không còn | Khôi phục project name và đúng tên volumes; pin image hiện có bằng digest |
| Nginx reverse proxy | Website hoạt động nhờ cấu hình Nginx đang nằm trong bộ nhớ | `nginx -T` lỗi vì file bind mount đã mất | Khôi phục reverse proxy, Host và forwarding headers; kiểm tra `nginx -t` |
| HTTPS hoặc security headers | Chưa có cấu hình source để kiểm tra/rebuild | Không chứng minh được headers từ repository | Chọn nhánh security headers theo đề; không khai báo HTTPS/HSTS trên HTTP |
| Container metrics | Không có cAdvisor trong stack đang chạy | Blackbox không đo CPU/RAM container | Thêm cAdvisor tương thích Docker Engine 29 và PromQL theo Compose labels |
| Web server metrics | Chỉ có job `portfolio_http` qua Blackbox | Không có `nginx_http_requests_total` hoặc connections | Thêm listener stub_status nội bộ, nginx-exporter; phân biệt probe và server metrics |
| Database metrics | Không có MySQL exporter | Không có MySQL global status/variables | Thêm mysqld-exporter v0.17.2, chỉ bật collectors chạy được với user giới hạn schema |
| Grafana provisioning | Grafana đang chạy với volume cũ | Các file datasource/dashboard trên host đã mất | Provision hai datasources và hai dashboards, không xóa dashboard cũ |
| Loki + Promtail | Loki + Alloy đang chạy; không có Promtail | Không đáp ứng đúng tên collector theo đề; config bind mounts đã mất | Giữ Loki schema v13/TSDB cũ, thêm Promtail đọc file JSON; dừng Alloy cũ, giữ volume và profile tùy chọn |
| LogQL | Chưa có tài liệu truy vấn trong workspace | Không chứng minh truy vấn khớp labels/format | Labels `project`, `job`, `service`; ba truy vấn và kiểm tra bằng request HTTP thật |
| Hardening | Một network chung; user ứng dụng đã chỉ có quyền trên schema portfolio | Mật khẩu ngắn, cấu hình không nằm trong repository | Tách mạng internal, localhost ports, headers, non-root/capabilities khi hỗ trợ; đổi mật khẩu ứng dụng/Grafana |
| Secrets | Container có credential nhưng file `.env` không còn | Rủi ro mất credential khi recreate | Khôi phục `.env` riêng tư; `.env.example` mẫu, `.gitignore` loại secrets/backups |
| Git/GitHub | Không có `.git`, không kiểm tra được nhánh/remote/lịch sử cũ | Không có commit/remote và chưa xác minh username GitHub | Khởi tạo nhánh main; cung cấp nhóm commit thực, hướng dẫn tài khoản DTC245200147; chưa commit/push |
| Evidence và báo cáo | Chưa có trong workspace | Thiếu checklist và báo cáo ≥10 trang | Tạo checklist, kết quả kiểm thử máy đọc được, khung HTML 12 trang có vị trí ảnh |

Docker Desktop khả dụng sau khi được cấp quyền truy cập daemon; Engine 29.8.1, Compose v5.5.1, Linux/WSL2, cgroup v2. Dung lượng quan sát trước sửa: ổ C khoảng 17 GB trống, ổ D khoảng 47 GB trống. Không xóa Docker data để giải phóng dung lượng.

Các volumes cũ được giữ: `portfolio-manh_db_data`, `wordpress_data`, `grafana_data`, `prometheus_data`, `loki_data`, `alloy_data` (tất cả có tiền tố `portfolio-manh_`). Credentials cũ và SQL backup nằm trong `backups/`, không đưa vào Git.
