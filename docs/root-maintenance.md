# Root MySQL: chẩn đoán, sao lưu và đổi mật khẩu

**Trạng thái hiện tại — 08/10/2026:** root đã được đặt lại theo yêu cầu người dùng. Đã sao lưu toàn bộ volume khi MySQL dừng sạch, so sánh archive với dữ liệu nguồn và kiểm tra checksums, lưu thêm full SQL dump trước khi đổi. Bảo trì dùng MySQL cô lập mạng/socket; container bảo trì đã dừng và xóa, Compose hoạt động lại với xác thực bình thường trên đúng volume cũ. `.env` và credential cục bộ đã đồng bộ. Mật khẩu do người dùng chọn dài 11 ký tự nên vẫn chưa đạt chính sách 20 ký tự. Xem `evidence/root-maintenance.json` và `docs/verification.md` cho kết quả mới.

Các lỗi 1045 và mô tả chưa hoàn thành bên dưới là lịch sử chẩn đoán trước lần đổi này; không cần chạy lại recovery.

## Hai lỗi đã xác định

`Password length policy: MYSQL_ROOT_PASSWORD` yêu cầu ít nhất 20 ký tự và không phải placeholder. Credential cấu hình hiện tại dài 10 ký tự nên kiểm tra thất bại.

`Existing MySQL root credential authentication` chạy MySQL client trong container, dùng MYSQL_ROOT_PASSWORD của container để đăng nhập root rồi `SELECT 1`. MySQL trả lỗi **1045**, không phải lỗi Docker/mạng hoặc thiếu volume.

`evidence/root-diagnosis.json` xác nhận giá trị `.env` khớp với Compose đã resolve và environment của db đang chạy. Database **MySQL 8.4.11** nằm ở `/var/lib/mysql`, volume **portfolio-manh_db_data**, dung lượng đã quan sát khoảng **223 MB**. Credential cũ trong backup cũng trùng giá trị đã thử; không thử lại bản trùng và không đoán mật khẩu.

`.env` là cấu hình container; mật khẩu thực tế do MySQL lưu dưới dạng dữ liệu xác thực trong system schema của volume. Theo [tài liệu Docker image MySQL](https://hub.docker.com/_/mysql), các biến khởi tạo không sửa database đã có. Chỉ sửa `.env` hoặc recreate container không khắc phục mismatch này.

## Sao lưu đã kiểm tra

`scripts/validated-backup.py` đã tạo snapshot ứng dụng bằng tài khoản portfolio_user đủ quyền trên schema portfolio_db, kiểm tra exit code/completion marker/SHA-256 và import vào một MySQL tạm cùng image:

- Network none, không publish cổng, `/var/lib/mysql` của container thử dùng tmpfs.
- Không gắn volume gốc; không dừng/sửa db gốc.
- Đủ 12 bảng; chữ ký các INSERT khớp; mọi CHECK TABLE trả OK.
- Container thử tự được dừng/xóa, chỉ tmpfs thử nghiệm mất đi. SQL và credential thử nằm trong backups/ bị Git ignore.

Kết quả thật: `evidence/backup-validation.json`. Snapshot ứng dụng không chứa system accounts MySQL. Vì vậy script đổi root vẫn tạo **bản sao lưu đầy đủ bằng root đã xác thực** và thử phục hồi cả thông tin accounts trước khi thay đổi tài khoản.

## Phương án ưu tiên: bạn biết mật khẩu root thực tế

Không cần chế độ recovery. Hộp thoại nhập kín lưu credentials vào `secrets/local-auth.json`, nằm ngoài Git. Không nhập password vào câu lệnh, phản hồi chat hoặc chụp màn hình `.env`/secrets.

Lần xác thực credential nhập cục bộ lúc **01:58:06 ngày 08/10/2026 (UTC+07:00)** trả lỗi **1045**; xem `evidence/local-root-auth.json`. Quy trình đã dừng trước full backup và ALTER USER, không thay đổi tài khoản. Người dùng đang nhập lại credential thực; chưa có kết quả đổi root thành công.

Kiểm tra bổ sung lúc **02:03:56** với cùng credential: cả Unix socket (`root@localhost`) và kết nối từ container phpMyAdmin đều bị từ chối **1045**. Không có trường hợp credential này đăng nhập được từ mạng nhưng bị lỗi riêng ở socket. Probe chỉ chạy SELECT CURRENT_USER(), không thay đổi dữ liệu.

```powershell
Set-Location 'D:\5_Thi_TrienKhaiThietKe\DTC245200147_NguyenVanManh'
python .\scripts\capture-local-credentials.py
```

Điền root thực tế. Có thể điền username/password WordPress để kiểm thử admin cùng lần, hoặc để trống WordPress và nhập sau. Nhấn **Lưu credentials cục bộ** chỉ lưu riêng tư, chưa đổi tài khoản.

Script đổi root thực hiện theo thứ tự:

1. Xác thực root bằng credential được nhập; đọc các root account hiện có và kiểm tra general/slow/raw logs OFF.
2. Kiểm tra snapshot ứng dụng đã restore-verify và hash của file còn khớp.
3. Tạo full dump với root, gồm application/system schema; sao lưu metadata accounts và `.env` cũ trong thư mục backups/root-before-... riêng tư.
4. Thử import full dump trên MySQL cùng image, network none/tmpfs. So sánh account metadata/xác thực và dữ liệu ứng dụng; CHECK TABLE. Nếu lỗi, dừng trước ALTER USER.
5. Sinh 24 bytes ngẫu nhiên → 48 ký tự hex, lưu state riêng tư trước khi đổi để không mất credential khi host gặp lỗi.
6. Dùng ALTER USER cho các root account đã tồn tại, giữ quyền/host restriction/account lock policy; không tạo, xóa hoặc tăng quyền user ứng dụng. Tắt binlog cho phiên đổi mật khẩu; không in SQL chứa password.
7. Xác thực lại root bằng mật khẩu mới; cập nhật `.env` nguyên tử, recreate **chỉ db** để environment khớp; xác minh vẫn gắn đúng volume cũ. Có thể gián đoạn database/website ngắn trong lúc db restart.
8. Chạy lại 40 kiểm tra gốc và kiểm thử admin riêng; lưu kết quả thật.

```powershell
# Chỉ sau khi đã nhập credential thực tế vào hộp thoại:
python .\scripts\check-local-root.py
python -u .\scripts\harden-root-known.py --apply
python -u .\scripts\verify.py
python .\scripts\summarize-evidence.py
python .\scripts\check-wordpress-admin.py --from-local
python .\scripts\check-source.py
```

`--apply` là thao tác đổi credential bình thường đã được yêu cầu; script này **không tự chuyển sang recovery** nếu password nhập sai. Mật khẩu mới nằm trong `.env`/state riêng tư, không hiển thị. Không import bản backup vào volume gốc để “thử”.

Nếu cần hướng dẫn thao tác hộp thoại: VS Code → **Terminal → New Terminal**, dán hai lệnh ở trên, nhấn Enter. Điền mật khẩu root của **MySQL** trong ô đầu; tài khoản WordPress là hệ đăng nhập riêng. Bấm **Lưu credentials cục bộ**, không chỉ đóng cửa sổ. Nếu `python` không tìm thấy, thử `py -3 .\scripts\capture-local-credentials.py`. Không đổi `.env` để thử mật khẩu. Nếu thấy `1045`, kiểm tra lại credential hoặc duyệt kế hoạch phục hồi ở dưới, không chạy thử nhiều password.

Đặc điểm backup/restore dựa trên [mysqldump 8.4](https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html); sử dụng `--flush-privileges` khi dump gồm mysql system schema. File backup được ghi binary bằng Python, tránh redirection UTF-16 của Windows PowerShell.

## Phương án dự phòng: không đăng nhập được với credential thực

**Chưa được duyệt, chưa thực hiện.** Chỉ dùng nếu bạn không còn credential đúng và đồng ý một lần bảo trì. Tham chiếu [quy trình reset root chính thức MySQL 8.4](https://dev.mysql.com/doc/refman/8.4/en/resetting-permissions.html).

Kế hoạch để duyệt:

1. Kiểm tra snapshot ứng dụng đã restore-verify, đúng project/image/volume và dung lượng ổ đĩa.
2. Dừng nginx, WordPress, phpMyAdmin, mysql-exporter và db bằng stop bình thường để không có writer; tạo **cold archive toàn bộ volume**, bao gồm system accounts, bằng helper mount volume **ro**. Kiểm tra archive giải nén đọc được, file inventory/checksums; không ghi đè volume.
3. Khởi động **duy nhất một** MySQL dùng đúng image và đúng volume với `--skip-grant-tables`, `--skip-networking`, Docker `network_mode: none`, không ports. Không chạy hai mysqld ghi cùng volume.
4. Qua Unix socket trong container: đọc các root account, tạo backup đủ quyền và kiểm tra hoàn tất trước khi thay đổi. Sau đó FLUSH PRIVILEGES, ALTER USER đúng các root account đã có với password ngẫu nhiên; không sửa trực tiếp mysql.user bằng UPDATE.
5. Dừng recovery sạch; bỏ mọi tùy chọn recovery; khởi động lại Compose bình thường với `.env` đã đồng bộ; xác minh không còn skip-grant-tables, original volume giữ nguyên, kiểm tra website/PMA/metrics/logs.

Rủi ro thực tế: downtime vài phút; authentication bị tắt tạm thời trong container recovery; lỗi nguồn/host có thể khiến cần đối chiếu state trước khi mở lại hệ thống. Vì vậy recovery phải cô lập socket/network, có cold archive trước và không tự rollback bằng cách ghi đè dữ liệu. Nếu xảy ra lỗi, dừng để xem xét snapshot và xin duyệt việc phục hồi tiếp, không xóa volumes/reset DB.

Không có lệnh recovery tự chạy trong workflow hiện tại. Cần bạn duyệt phương án cụ thể trước khi bắt đầu bước dừng dịch vụ cho recovery.

## WordPress admin

Tài khoản administrator đã xác minh tồn tại: `vanmanh_admin`. Không đọc/khôi phục password hash thành mật khẩu, không reset tài khoản cá nhân.

`scripts/check-wordpress-admin.py` nhận password từ hộp thoại hoặc getpass trên terminal, đăng nhập qua wp-login.php thật, kiểm tra authentication cookie trong RAM, truy cập Dashboard và danh sách Trang, sau đó bỏ cookies. Không lưu cookie/nonce/password trong evidence, không sửa nội dung.

```powershell
# Nhập kín bằng terminal nếu không sử dụng hộp thoại:
python .\scripts\check-wordpress-admin.py
```

Nếu tự kiểm tra bằng trình duyệt: mở http://localhost:8080/wp-admin/, đăng nhập, xác nhận Dashboard và **Trang → Tất cả các trang**, chụp `02-wordpress-admin.png`. Không coi trang login HTTP 200 hoặc việc user tồn tại trong DB là một phiên đăng nhập đã kiểm thử.
