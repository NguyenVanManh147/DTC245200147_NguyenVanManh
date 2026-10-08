# Kết quả kiểm tra thực tế

Thời gian chạy: **2026-10-08T15:14:19.342627+07:00** (UTC+07:00).
Nguồn: [evidence/verification.json](../evidence/verification.json).

**37/40 kiểm tra đạt.** Giữ nguyên các kiểm tra gốc; không bỏ hoặc làm yếu kiểm tra để tăng số đạt.

| Kiểm tra | Kết quả |
|---|---|
| Compose syntax | Đạt |
| Nginx syntax | Đạt |
| Prometheus syntax | Đạt |
| Loki syntax | Đạt |
| Promtail syntax | Đạt |
| Website and existing content | Đạt |
| Nginx security headers | Đạt |
| WordPress login page | Đạt |
| phpMyAdmin page | Đạt |
| phpMyAdmin authenticated database access | Đạt |
| Existing WordPress pages preserved | Đạt |
| Application database privileges scoped to schema | Đạt |
| WordPress file editor disabled | Đạt |
| XML-RPC blocked (real 403 request) | Đạt |
| Hidden files blocked (real 404 request) | Đạt |
| Prometheus 8 targets | Đạt |
| PromQL: nginx_up{job="nginx"} | Đạt |
| PromQL: mysql_up{job="mysql"} | Đạt |
| PromQL: probe_success{job="portfolio_http"} | Đạt |
| PromQL: container_memory_working_set_bytes{job="cadvisor",container_label_com_docker_compose_project="portfolio-manh"} | Đạt |
| PromQL: rate(container_cpu_usage_seconds_total{job="cadvisor",container_label_com_docker_compose_project="portfolio-manh"}[2m]) | Đạt |
| PromQL: rate(nginx_http_requests_total{job="nginx"}[2m]) | Đạt |
| PromQL: mysql_global_status_threads_connected{job="mysql"} | Đạt |
| PromQL: rate(mysql_global_status_queries{job="mysql"}[2m]) | Đạt |
| Grafana datasource portfolio-prometheus | Đạt |
| Grafana datasource health portfolio-prometheus | Đạt |
| Grafana datasource portfolio-loki | Đạt |
| Grafana datasource health portfolio-loki | Đạt |
| Grafana provisioned dashboard portfolio-infrastructure | Đạt |
| Grafana provisioned dashboard portfolio-logs | Đạt |
| LogQL 1 | Đạt |
| LogQL 2 | Đạt |
| LogQL 3 | Đạt |
| Localhost published ports | Đạt |
| Internal application/database/monitoring networks | Đạt |
| Password length policy: MYSQL_PASSWORD | **CHƯA ĐẠT** |
| Password length policy: MYSQL_ROOT_PASSWORD | **CHƯA ĐẠT** |
| Password length policy: GRAFANA_ADMIN_PASSWORD | **CHƯA ĐẠT** |
| Existing MySQL root credential authentication | Đạt |
| Secrets and backup ignored by Git | Đạt |

## Kết quả bổ sung và giới hạn

- Syntax Compose/Nginx/Prometheus/Loki/Promtail đạt bằng các công cụ kiểm tra thực.
- Website HTTP 200; **6 pages** so sánh với WXR gốc không thay đổi.
- phpMyAdmin đăng nhập thành công bằng tài khoản ứng dụng qua phiên HTTP thật và thấy database portfolio_db.
- 8 Prometheus targets UP; nginx_up/mysql_up/probe_success=1; metrics CPU/RAM/Nginx/MySQL có dữ liệu thực.
- Hai datasource Grafana health OK và hai dashboard provisioned=true; đã chụp dashboard/Explore, xem evidence/screenshots.json.
- Ba LogQL trả dữ liệu thực; request 403/404 do kiểm thử HTTP tạo ra. Chưa thử gây lỗi 5xx.
- Snapshot ứng dụng đã restore-verify trên MySQL tmpfs/network none: **12 bảng**, chữ ký INSERT khớp, CHECK TABLE OK. SQL riêng tư trong backups/, chỉ manifest ở evidence/backup-validation.json.
- MySQL root đăng nhập thực tế thành công bằng credential cấu hình hiện tại.
- Root được đặt lại theo yêu cầu người dùng sau sao lưu toàn bộ volume bằng mount read-only, so sánh archive và checksums. Bảo trì cô lập mạng đã kết thúc; xác thực bình thường được bật lại, giữ đúng volume cũ; xem evidence/root-maintenance.json.
- `MYSQL_PASSWORD` dài 11 ký tự, chưa đạt tối thiểu 20. Kiểm tra độ dài giữ nguyên; đăng nhập được đánh giá riêng.
- `MYSQL_ROOT_PASSWORD` dài 11 ký tự, chưa đạt tối thiểu 20. Kiểm tra độ dài giữ nguyên; đăng nhập được đánh giá riêng.
- `GRAFANA_ADMIN_PASSWORD` dài 11 ký tự, chưa đạt tối thiểu 20. Kiểm tra độ dài giữ nguyên; đăng nhập được đánh giá riêng.
- **WordPress admin đã kiểm thử** vào 2026-10-08T15:23:50.118624+07:00: đăng nhập bằng password thật, truy cập Dashboard và danh sách Trang. Không lưu cookies; xem evidence/wordpress-admin.json.
- **WordPress sửa/lưu đã kiểm thử** vào 2026-10-08T15:21:29+07:00; xem evidence/wordpress-edit.json.
- Nội dung thử sau khi lưu đã được xác minh hiển thị qua trang công khai của website.
- Các trang portfolio gốc được đối chiếu và giữ nguyên sau kiểm thử nội dung.
- Nội dung thử đã được dọn sau kiểm thử; việc dọn được xác minh riêng.
- Kiểm tra Git: 141 files là candidates; không có private files hoặc credential thực bị phát hiện trong candidates.
- Git được kiểm tra vào 2026-10-08T15:31:27.524165+07:00: nhánh `main`, 4 commits; xem evidence/git-delivery.json.
- Repository bài: [https://github.com/NguyenVanManh147/DTC245200147_NguyenVanManh](https://github.com/NguyenVanManh147/DTC245200147_NguyenVanManh). Trạng thái push: **đã xác minh**.
- Báo cáo HTML đã chèn 26 ảnh minh chứng thật và sơ đồ kiến trúc; ảnh không chứa mật khẩu/cookies/token. Các hình output lệnh là kết quả thật được hiển thị qua HTML để chụp, không phải terminal Windows.
- Lần xuất PDF được xác minh tại 2026-10-08T15:34:40+07:00: 28 trang A4; 27 ảnh/sơ đồ tải thành công, không thiếu file. Xem docs/BaoCao_DTC245200147_NguyenVanManh.pdf và evidence/report-validation.json.
- Người dùng yêu cầu giữ nguyên mật khẩu hiện tại. Các kiểm tra độ dài chưa đạt được giữ và ghi rõ, không đổi mật khẩu hoặc hạ chính sách kiểm tra.

## Công việc còn cần bổ sung

1. Đối chiếu lịch nộp và yêu cầu với phiếu đề bài gốc. Khoa Công nghệ Thông tin, lớp CNTTK23B, học phần Triển khai và Quản trị Hệ thống Phần mềm và giảng viên Nguyễn Anh Chuyên đã được sinh viên xác nhận.

Khởi tạo tự động đã kiểm thử trên volumes Docker mới: nội dung, ảnh, menu, đăng nhập và bảo vệ dữ liệu khi chạy lại; xem evidence/bootstrap-validation.json. Chưa thử trên một máy vật lý khác.

## Giới hạn có chủ đích

Triển khai HTTP với security headers; chưa có HTTPS tự ký. Cần đối chiếu lựa chọn triển khai với phiếu đề bài gốc. MySQL exporter dùng collectors cơ bản; cAdvisor có đặc quyền cho Linux VM; file access logs chưa có rotation tự động. Promtail EOL nhưng được giữ theo checklist hiện có.

Kết quả lấy từ JSON thật. Chạy `python scripts/summarize-evidence.py` sau kiểm tra mới để đồng bộ tài liệu.
