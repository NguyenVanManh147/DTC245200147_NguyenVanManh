"""Render actual results; optional root/admin evidence is separate from the 40 checks."""
import json
import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
data = json.loads((root / 'evidence/verification.json').read_text(encoding='utf-8'))
checks = data['checks']
by_name = {item['name']: item for item in checks}
passed = sum(item['passed'] for item in checks)

def ok(*names):
    return all(by_name.get(name, {}).get('passed', False) for name in names)

def artifact(name):
    path = root / 'evidence' / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

backup = artifact('backup-validation.json')
maintenance = artifact('root-maintenance.json')
admin = artifact('wordpress-admin.json')
edit_artifact = 'wordpress-edit-validation.json' if (root / 'evidence/wordpress-edit-validation.json').exists() else 'wordpress-edit.json'
edit_validation = artifact(edit_artifact)
git_delivery = artifact('git-delivery.json')
privacy = artifact('git-privacy.json')
local_auth = artifact('local-root-auth.json')
captures = artifact('screenshots.json')
report_validation = artifact('report-validation.json')
bootstrap_validation = artifact('bootstrap-validation.json')
has_captures = bool(captures) and all((root / 'evidence' / name).exists() for name in captures)
password_failures = [item for item in checks if item['name'].startswith('Password length policy:') and not item['passed']]
edit_verified = bool(edit_validation.get('passed'))
commit_count = git_delivery.get('commit_count', 0)
git_commits_verified = isinstance(commit_count, int) and commit_count >= 3
git_pushed = bool(git_delivery.get('pushed'))
lines = [
    '# Kết quả kiểm tra thực tế', '',
    f"Thời gian chạy: **{data['checked_at']}** (UTC+07:00).",
    'Nguồn: [evidence/verification.json](../evidence/verification.json).', '',
    f'**{passed}/{len(checks)} kiểm tra đạt.** Giữ nguyên các kiểm tra gốc; không bỏ hoặc làm yếu kiểm tra để tăng số đạt.', '',
    '| Kiểm tra | Kết quả |', '|---|---|',
]
for item in checks:
    name = item['name'].replace('|', '\\|')
    lines.append(f"| {name} | {'Đạt' if item['passed'] else '**CHƯA ĐẠT**'} |")
lines += ['', '## Kết quả bổ sung và giới hạn', '']
if ok('Compose syntax', 'Nginx syntax', 'Prometheus syntax', 'Loki syntax', 'Promtail syntax'):
    lines.append('- Syntax Compose/Nginx/Prometheus/Loki/Promtail đạt bằng các công cụ kiểm tra thực.')
if ok('Website and existing content', 'Existing WordPress pages preserved'):
    count = by_name['Existing WordPress pages preserved']['detail']['page_count']
    lines.append(f'- Website HTTP 200; **{count} pages** so sánh với WXR gốc không thay đổi.')
if ok('phpMyAdmin authenticated database access'):
    lines.append('- phpMyAdmin đăng nhập thành công bằng tài khoản ứng dụng qua phiên HTTP thật và thấy database portfolio_db.')
if ok('Prometheus 8 targets') and all(item['passed'] for item in checks if item['name'].startswith('PromQL:')):
    lines.append('- 8 Prometheus targets UP; nginx_up/mysql_up/probe_success=1; metrics CPU/RAM/Nginx/MySQL có dữ liệu thực.')
if ok('Grafana datasource health portfolio-prometheus', 'Grafana datasource health portfolio-loki', 'Grafana provisioned dashboard portfolio-infrastructure', 'Grafana provisioned dashboard portfolio-logs'):
    lines.append('- Hai datasource Grafana health OK và hai dashboard provisioned=true; ' + ('đã chụp dashboard/Explore, xem evidence/screenshots.json.' if has_captures else 'chưa chụp ảnh giao diện.'))
if ok('LogQL 1', 'LogQL 2', 'LogQL 3'):
    lines.append('- Ba LogQL trả dữ liệu thực; request 403/404 do kiểm thử HTTP tạo ra. Chưa thử gây lỗi 5xx.')
if backup.get('restore_verified'):
    lines.append(f"- Snapshot ứng dụng đã restore-verify trên MySQL tmpfs/network none: **{backup['table_count']} bảng**, chữ ký INSERT khớp, CHECK TABLE OK. SQL riêng tư trong backups/, chỉ manifest ở evidence/backup-validation.json.")
if ok('Existing MySQL root credential authentication'):
    lines.append('- MySQL root đăng nhập thực tế thành công bằng credential cấu hình hiện tại.')
    if maintenance.get('root_changed'):
        if maintenance.get('recovery_mode_used'):
            lines.append('- Root được đặt lại theo yêu cầu người dùng sau sao lưu toàn bộ volume bằng mount read-only, so sánh archive và checksums. Bảo trì cô lập mạng đã kết thúc; xác thực bình thường được bật lại, giữ đúng volume cũ; xem evidence/root-maintenance.json.')
        else:
            lines.append('- Root được đổi bằng credential thực và ALTER USER bình thường sau full backup restore-verify; không dùng skip-grant-tables. .env/environment đồng bộ, giữ đúng volume cũ; xem evidence/root-maintenance.json.')
else:
    lines.append('- **Root còn chưa hoàn thành**: xem các dòng CHƯA ĐẠT. evidence/root-diagnosis.json ghi credential cấu hình khớp Compose/container nhưng bị MySQL từ chối 1045; sửa .env không tự đổi password trong volume đã khởi tạo.')
    if local_auth and not local_auth.get('passed'):
        lines.append(f"- Thử credential root nhập kín vào {local_auth['checked_at']} chưa xác thực được: {local_auth.get('error', 'authentication failed').rstrip('.')}. Quy trình dừng trước full backup/ALTER USER; không đổi tài khoản. Xem evidence/local-root-auth.json.")
        network_probe = local_auth.get('network_origin_probe', {})
        if 'mysql_error_code' in network_probe:
            lines.append(f"- Cùng credential cũng bị MySQL từ chối qua mạng từ phpMyAdmin: mã {network_probe['mysql_error_code']}. Không phải đã đăng nhập được root từ mạng nhưng chỉ lỗi socket.")
for item in checks:
    if item['name'].startswith('Password length policy:') and not item['passed']:
        key = item['name'].split(': ', 1)[1]
        lines.append(f"- `{key}` dài {item['detail']['length']} ký tự, chưa đạt tối thiểu {item['detail']['minimum']}. Kiểm tra độ dài giữ nguyên; đăng nhập được đánh giá riêng.")
if admin.get('passed'):
    lines.append(f"- **WordPress admin đã kiểm thử** vào {admin['checked_at']}: đăng nhập bằng password thật, truy cập Dashboard và danh sách Trang. Không lưu cookies; xem evidence/wordpress-admin.json.")
else:
    lines.append('- **WordPress admin chưa xác minh phiên đăng nhập**: administrator vanmanh_admin tồn tại; login HTTP 200 không chứng minh đăng nhập. Nhập kín bằng scripts/capture-local-credentials.py hoặc chạy scripts/check-wordpress-admin.py trong terminal local.')
if edit_verified:
    lines.append(f"- **WordPress sửa/lưu đã kiểm thử** vào {edit_validation.get('checked_at', 'thời gian ghi trong artifact')}; xem evidence/{edit_artifact}.")
    if edit_validation.get('public_render_verified') or edit_validation.get('anonymous_public_view_verified'):
        lines.append('- Nội dung thử sau khi lưu đã được xác minh hiển thị qua trang công khai của website.')
    if edit_validation.get('original_pages_preserved') or edit_validation.get('original_posts_unchanged'):
        lines.append('- Các trang portfolio gốc được đối chiếu và giữ nguyên sau kiểm thử nội dung.')
    if edit_validation.get('cleanup_verified') or edit_validation.get('test_content_removed'):
        lines.append('- Nội dung thử đã được dọn sau kiểm thử; việc dọn được xác minh riêng.')
else:
    lines.append('- Chưa có artifact xác nhận kiểm thử sửa/lưu WordPress thành công; đăng nhập admin được đánh giá riêng.')
if privacy:
    private_files = privacy.get('private_files_in_git_candidates', [])
    secret_matches = privacy.get('actual_secret_matches', [])
    if not private_files and not secret_matches:
        lines.append(f"- Kiểm tra Git: {privacy['candidate_file_count']} files là candidates; không có private files hoặc credential thực bị phát hiện trong candidates.")
    else:
        lines.append('- **Kiểm tra riêng tư Git chưa đạt**: xem evidence/git-privacy.json; không xuất credential hoặc nội dung private vào báo cáo.')
if git_delivery:
    lines.append(f"- Git được kiểm tra vào {git_delivery.get('checked_at', 'thời gian ghi trong artifact')}: nhánh `{git_delivery.get('branch', 'không ghi nhận')}`, {commit_count} commits; xem evidence/git-delivery.json.")
    repository_url = git_delivery.get('repository_url')
    if repository_url:
        lines.append(f"- Repository bài: [{repository_url}]({repository_url}). Trạng thái push: **{'đã xác minh' if git_pushed else 'chưa xác minh'}**.")
if has_captures:
    image_index = artifact('report-image-index.json')
    lines.append(f"- Báo cáo HTML đã chèn {image_index.get('screenshot_count', 0)} ảnh minh chứng thật và sơ đồ kiến trúc; ảnh không chứa mật khẩu/cookies/token. Các hình output lệnh là kết quả thật được hiển thị qua HTML để chụp, không phải terminal Windows.")
    if report_validation:
        lines.append(f"- PDF: {report_validation['pdf_pages']} trang A4; {report_validation['images']} ảnh/sơ đồ tải thành công, không thiếu file. Xem {report_validation['pdf_file']} và evidence/report-validation.json.")
remaining = []
if password_failures:
    lines.append('- Người dùng yêu cầu giữ nguyên mật khẩu hiện tại. Các kiểm tra độ dài chưa đạt được giữ và ghi rõ, không đổi mật khẩu hoặc hạ chính sách kiểm tra.')
if not ok('Existing MySQL root credential authentication'):
    remaining.append('Xác minh root và xử lý theo docs/root-maintenance.md; giữ nguyên volume dữ liệu.')
if not edit_verified:
    remaining.append('Kiểm thử sửa/lưu nội dung WordPress trên trang thử; xác minh kết quả hiển thị và giữ nguyên các trang portfolio gốc.')
if not has_captures:
    remaining.append('Chụp ảnh theo checklist evidence/README.md: website/admin, database, dashboards, LogQL và hardening.')
if not git_commits_verified:
    remaining.append('Tạo ít nhất ba commits có nội dung thực và ghi nhận lịch sử trong evidence/git-delivery.json.')
if not git_pushed:
    remaining.append('Push source vào repository thuộc tài khoản NguyenVanManh147 do người dùng xác nhận, sau khi kiểm tra riêng tư; xác minh URL và commit remote.')
remaining.append('Đối chiếu lịch nộp và yêu cầu với phiếu đề bài gốc. Khoa Công nghệ Thông tin, lớp CNTTK23B, học phần Triển khai và Quản trị Hệ thống Phần mềm và giảng viên Nguyễn Anh Chuyên đã được sinh viên xác nhận.')
if not (bootstrap_validation.get('fresh_install_verified') and bootstrap_validation.get('cleanup_verified')):
    remaining.append('Xác minh khởi tạo trên volumes mới bằng scripts/test-bootstrap.py và lưu evidence/bootstrap-validation.json.')
lines += ['', '## Công việc còn cần bổ sung', '']
lines += [f'{i}. {item}' for i, item in enumerate(remaining, 1)]
if bootstrap_validation.get('fresh_install_verified') and bootstrap_validation.get('cleanup_verified'):
    lines += ['', 'Khởi tạo tự động đã kiểm thử trên volumes Docker mới: nội dung, ảnh, menu, đăng nhập và bảo vệ dữ liệu khi chạy lại; xem evidence/bootstrap-validation.json. Chưa thử trên một máy vật lý khác.']
lines += [
    '', '## Giới hạn có chủ đích', '',
    'Triển khai HTTP với security headers; chưa có HTTPS tự ký. Cần đối chiếu lựa chọn triển khai với phiếu đề bài gốc. MySQL exporter dùng collectors cơ bản; cAdvisor có đặc quyền cho Linux VM; file access logs chưa có rotation tự động. Promtail EOL nhưng được giữ theo checklist hiện có.',
    '', 'Kết quả lấy từ JSON thật. Chạy `python scripts/summarize-evidence.py` sau kiểm tra mới để đồng bộ tài liệu.',
]
(root / 'docs/verification.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f'Wrote docs/verification.md from {passed}/{len(checks)} real passing checks; optional artifacts reported separately.')
