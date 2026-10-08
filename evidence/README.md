# Danh mục minh chứng

Minh chứng được lấy từ hệ thống WordPress/Docker đang chạy và các trang quản trị thật. Ảnh trình duyệt dùng Edge headless với phiên đăng nhập xác thực; mật khẩu, cookies, nonce và token không đưa vào báo cáo/Git. Những ảnh kết quả lệnh được tạo bằng cách hiển thị output thực tế qua HTML rồi chụp bằng trình duyệt; đây không phải ảnh terminal Windows.

`screenshots.json` và các file `*.capture.json` ghi nguồn, thời gian và SHA-256 của ảnh. `report-image-index.json` liệt kê hình được chèn vào `docs/report.html`; `report-validation.json` ghi số trang PDF, ảnh thiếu và trang trắng. Sơ đồ thiết kế ở `docs/architecture.svg`. Xem thời điểm trong từng file để phân biệt minh chứng lịch sử với lần kiểm tra mới nhất.

## Ảnh hệ thống

| File | Nội dung minh chứng | Nguồn |
|---|---|---|
| `01-website.png` | Portfolio Nguyễn Văn Mạnh, nội dung cá nhân | http://localhost:8080/ |
| `02-wordpress-admin.png` | Đăng nhập WordPress và danh sách Trang | http://localhost:8080/wp-admin/ |
| `03-phpmyadmin-database.png` | Đăng nhập phpMyAdmin, database `portfolio_db`, bảng `wp_*` | http://localhost:8081/ |
| `04-compose-status.png` | Trạng thái các services; `loki-init` exit 0 là bình thường | `docker compose ps -a` |
| `05-nginx-headers.png` | HTTP 200, security headers và Nginx syntax | `curl.exe -I` và `nginx -t` |
| `06-prometheus-targets.png` | Tám targets UP | http://localhost:9090/targets |
| `07-grafana-container.png` | CPU/RAM theo service của project `portfolio-manh` | Grafana infrastructure dashboard |
| `08a-grafana-web-requests.png` | Nginx requests/s | Grafana infrastructure dashboard |
| `08b-grafana-web-connections.png` | Nginx active connections | Grafana infrastructure dashboard |
| `08c-grafana-http-probe.png` | HTTP availability/latency của website | Grafana infrastructure dashboard |
| `09a-grafana-database-queries.png` | MySQL queries/s | Grafana infrastructure dashboard |
| `09b-grafana-database-threads.png` | MySQL connected threads | Grafana infrastructure dashboard |
| `10-logql-access.png` | Access log JSON, labels đúng project/job | Grafana Explore / Portfolio Loki |
| `11-logql-errors.png` | HTTP 403/404 thật, lọc status từ 400 đến 599 | Requests `/xmlrpc.php`, `/.env` và LogQL |
| `12-logql-requests.png` | Số requests trong mỗi cửa sổ một phút | LogQL `count_over_time` |
| `13-hardening-networks.png` | Các mạng application/database/monitoring internal | `docker network inspect` |
| `14-hardening-ports-users.png` | Ports localhost, users, capabilities; ngoại lệ cAdvisor | `docker compose ps` và inspect đã chọn trường |
| `15-database-grants.png` | User ứng dụng chỉ có quyền trong schema | phpMyAdmin `SHOW GRANTS FOR CURRENT_USER();` |
| `16-git-status.png` | Snapshot lịch sử bốn commits thực, origin/main và remote của bài | Các lệnh Git lúc 15:32 ngày 08/10/2026 |
| `17a-github-account.png` | Trang repositories của tài khoản `NguyenVanManh147` | GitHub công khai, cập nhật lúc 15:31 ngày 08/10/2026 |
| `17b-github-repository.png` | Repository bài chứa source và README sau push | GitHub công khai; thời gian chụp trong file capture tương ứng |
| `18-backup-validation.png` | Import thử backup vào MySQL cô lập, kiểm tra bảng/chữ ký | `backup-validation.json` |
| `19-root-authentication.png` | Root xác thực thành công, không lộ credential | `local-root-auth.json` |
| `20-verification-results.png` | Kết quả kiểm thử hệ thống | `verification.json` |
| `21-report-preview.png` | Xem trước báo cáo PDF | Bản PDF tại `docs/` |
| `24-wordpress-edit-admin.png` | Trang thử đã sửa nội dung và xuất bản trong quản trị | Phiên admin WordPress thật |
| `25-wordpress-edit-public.png` | Nội dung mới hiển thị HTTP 200 cho khách ẩn danh | Trang công khai trước khi dọn nội dung thử |

Source và hồ sơ đã được push lên repository công khai [NguyenVanManh147/DTC245200147_NguyenVanManh](https://github.com/NguyenVanManh147/DTC245200147_NguyenVanManh), nhánh **main**. `git-delivery.json` lúc **15:31 ngày 08/10/2026** xác nhận snapshot **4 commits thực**, `pushed=true`, `remote_checked=true`, local và remote cùng revision `7d27e84`. Lịch sử GitHub có thể chứa thêm commits cập nhật hồ sơ sau snapshot này; ảnh `16-git-status.png` thể hiện bốn commits đã push, ảnh `17a/17b` lấy từ trang GitHub sau push.

## Sửa và lưu nội dung WordPress

Chạy kiểm thử bằng:

```powershell
python -u .\scripts\test-wordpress-edit.py
```

Script dùng phiên đăng nhập admin để tạo một trang nháp riêng, sửa nội dung, xuất bản qua REST API và kiểm tra trang bằng HTTP ẩn danh. Cuối cùng chỉ xóa trang kiểm thử và các revisions của trang đó; đối chiếu dữ liệu các trang, metadata và tùy chọn cá nhân trước/sau để xác minh nội dung gốc được giữ.

Lần kiểm thử lúc **15:21 ngày 08/10/2026 đạt 13/13**, ghi tại `wordpress-edit.json`. Hai ảnh thật `24-wordpress-edit-admin.png` và `25-wordpress-edit-public.png` chứng minh nội dung đã lưu và hiển thị công khai. Sau khi dọn trang thử và revisions của nó, các posts/pages, metadata cùng tùy chọn site/theme/navigation/widget khớp chữ ký trước kiểm thử. Tham số chụp ảnh `--capture` cần Edge và Playwright trong môi trường minh chứng; kiểm thử thông thường dùng thư viện chuẩn Python.

## Kết quả dạng JSON

| File | Ý nghĩa |
|---|---|
| `verification.json` | Kiểm tra cấu hình, website, database, 8 targets, PromQL, LogQL, networks/ports và credential policies |
| `compose-status.json` | Trạng thái Compose tại thời điểm lấy minh chứng |
| `wordpress-admin.json` | Password login, Dashboard và danh sách Trang qua phiên admin thật |
| `wordpress-edit.json` | Sửa/xuất bản, hiển thị ẩn danh, cleanup và bảo toàn nội dung gốc |
| `bootstrap-validation.json` | Kiểm thử volumes mới, nhập nội dung/ảnh/menu, đăng nhập, chạy lại và bảo vệ dữ liệu có sẵn |
| `backup-validation.json` | Khôi phục thử WordPress vào MySQL cô lập: 12 bảng, chữ ký dữ liệu khớp và CHECK TABLE OK |
| `local-root-auth.json` | Xác thực `root@localhost`, không chứa mật khẩu |
| `root-diagnosis.json` | Chẩn đoán lịch sử bằng metadata/boolean/error code |
| `root-maintenance.json` | Quá trình bảo trì root sau backup, cold archive, kiểm tra dữ liệu và full SQL dump |
| `git-privacy.json` | Quét các file dự kiến đưa vào Git; không lưu giá trị credential |
| `github-access.json` | Xác minh quyền truy cập đúng tài khoản GitHub; không lưu token |
| `github-observation.json` | Quan sát tài khoản và repository công khai sau push, xác minh source hiển thị |
| `git-delivery.json` | Snapshot đã push, ít nhất ba commits thực và revision local/remote khớp |
| `report-image-index.json` | Danh sách hình và captions được chèn trong HTML |
| `report-validation.json` | Số trang/ảnh và kiểm tra bản PDF |

Kết quả hệ thống ngày **08/10/2026: 37/40**. Ba FAIL là mật khẩu **MySQL user, MySQL root và Grafana dài 11 ký tự**, dưới mức **20 ký tự** của bộ kiểm tra. Sinh viên chọn **giữ mật khẩu hiện tại và ghi rõ giới hạn**. Xác thực root, user database, WordPress và Grafana thành công; các kiểm tra chức năng còn lại PASS. SQL backup và dữ liệu xác thực nằm trong thư mục riêng tư bị ignore, không có trong repository.

Bootstrap đã được kiểm tra trên volumes mới của Docker Desktop hiện tại; kết quả chưa thay thế kiểm thử trên một máy vật lý khác. Các ảnh/log minh chứng có thời điểm cụ thể; khi trình bày cần bật Docker Desktop và tái kiểm tra trạng thái đang chạy.

## Hồ sơ nộp bài

Báo cáo HTML và PDF ở `docs/`. Thông tin bìa đã xác nhận: **Nguyễn Văn Mạnh — DTC245200147 — Khoa Công Nghệ Thông Tin — CNTTK23B**, học phần **Triển khai và Quản trị Hệ thống Phần mềm**, giảng viên **Nguyễn Anh Chuyên**. Chỉ hạn nộp chưa được cung cấp, cần đối chiếu lịch chính thức. Phần kết luận cần được sinh viên đọc và điều chỉnh theo trải nghiệm học tập thực tế.

Workspace chưa có phiếu đề gốc. Cần đối chiếu trước khi nộp về tên tài khoản/repository GitHub, số commits, nhánh HTTPS/security headers và quy cách báo cáo; không suy ra username GitHub bắt buộc trùng mã sinh viên khi chưa có điều kiện gốc.
