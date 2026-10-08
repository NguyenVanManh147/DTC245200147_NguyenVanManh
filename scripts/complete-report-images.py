"""Refresh the completed report; retain legacy placeholder migration below.

The placeholder migration describes the initial recovery snapshot. Completed
reports use the refresh path, preserving their current narrative and captions.
"""
import datetime
import hashlib
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/report.html'
content = REPORT.read_text(encoding='utf-8')
verification = json.loads((ROOT / 'evidence/verification.json').read_text(encoding='utf-8'))
passed = sum(c['passed'] for c in verification['checks'])
records_path = ROOT / 'evidence/screenshots.json'
records = json.loads(records_path.read_text(encoding='utf-8'))
for path in (ROOT / 'evidence').glob('*.capture.json'):
    records[path.name.replace('.capture.json','.png')] = json.loads(path.read_text(encoding='utf-8'))
for path in (ROOT / 'evidence').glob('*.png'):
    if path.name not in records:
        records[path.name] = {'captured_at':datetime.datetime.fromtimestamp(path.stat().st_mtime,datetime.timezone(datetime.timedelta(hours=7))).isoformat(timespec='seconds'),
            'source':'Trang dịch vụ hoặc trang kết quả lệnh cùng tên; xem scripts/capture-evidence.py',
            'label':path.stem,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
records_path.write_text(json.dumps(records,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
if '--refresh-times' in sys.argv or 'class="placeholder"' not in content:
    def refresh(match):
        name = match.group(2)
        return match.group(1) + 'Chụp: ' + html.escape(records[name]['captured_at']) + '.' + match.group(3)
    content = re.sub(r'(<figure[^>]*>.*?<img src="../evidence/([^\"]+)".*?<span class="capture-time">).*?(</span></figcaption></figure>)',refresh,content,flags=re.S)
    REPORT.write_text(content,encoding='utf-8')
    included = []
    for figure_html in re.findall(r'<figure\b.*?</figure>', content, flags=re.S):
        filename = re.search(r'<img src="\.\./evidence/([^\"]+)"', figure_html)
        caption = re.search(r'<figcaption>(.*?)<span class="capture-time">', figure_html, flags=re.S)
        if filename and caption:
            text = html.unescape(re.sub(r'<[^>]+>', '', caption[1])).strip()
            text = re.sub(r'^Hình \d+\.\s*', '', text)
            included.append({'file': 'evidence/' + filename[1], 'caption': text,
                             'captured_at': records[filename[1]]['captured_at']})
    (ROOT / 'evidence/report-image-index.json').write_text(json.dumps({
        'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
        'screenshot_count': len(included), 'images': included,
        'architecture': 'docs/architecture.svg',
        'result': f'{passed}/{len(verification["checks"])}'},
        indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Report capture timestamps synchronized with image metadata.')
    raise SystemExit(0)

number = 0
included = []
def figure(filename, caption, size='compact'):
    global number
    path = ROOT / 'evidence' / filename
    if not path.exists():
        raise RuntimeError('Required screenshot missing: ' + filename)
    number += 1
    included.append(filename)
    when = records[filename]['captured_at']
    return f'<figure class="evidence {size}"><a href="../evidence/{filename}"><img src="../evidence/{filename}" alt="{html.escape(caption,quote=True)}"></a><figcaption>Hình {number}. {html.escape(caption)} <span class="capture-time">Chụp: {html.escape(when)}.</span></figcaption></figure>'

def replace(old,new):
    global content
    if old not in content:
        raise RuntimeError('Expected original report text not found: ' + old[:90])
    content = content.replace(old,new,1)

replace('Khung báo cáo gồm 12 phần ngắt trang. Bổ sung thông tin lớp/giảng viên và ảnh thật, cập nhật kết quả từ evidence/verification.json. In A4, tắt header/footer trình duyệt. Kiểm tra số trang PDF sau khi thêm ảnh; không coi các ô trống là minh chứng.',
    'Báo cáo đã bổ sung ảnh giao diện thật, sơ đồ kiến trúc và kết quả kiểm thử hiện tại. Bấm vào từng hình để xem ảnh gốc. Thông tin lớp/giảng viên và minh chứng repository/commits cần hoàn thiện trước khi nộp. Bản PDF được xuất A4 cùng thư mục docs.')
replace('[Bổ sung tên trường / khoa]','Trường Đại học Công nghệ Thông tin và Truyền thông<br>Đại học Thái Nguyên')
replace('[Bổ sung học phần, lớp và giảng viên]','Học phần, khoa, lớp và giảng viên: chưa cung cấp')
replace('[Bổ sung địa điểm và thời gian nộp]','Ngày lập báo cáo: 08/10/2026<br>Thời gian nộp: bổ sung theo lịch học phần')
replace('Xác minh và xử lý credential root MySQL; chụp ảnh admin/dashboard/logs; tạo các commits thực; xác minh username GitHub và chỉ push khi được yêu cầu.',
    'Đã xác thực root, WordPress admin, phpMyAdmin và Grafana; đã chụp ảnh giao diện, dashboard và logs. Còn thiếu lịch sử ít nhất ba commits thực và repository công khai của bài. Mật khẩu người dùng chọn dài 11 ký tự nên chưa đạt chính sách 20 ký tự.')
replace('<div class="placeholder">[BỔ SUNG yêu cầu/phiếu đề bài thực tế nếu cần đối chiếu]</div>',
    '<p class="notice">Bảng yêu cầu được đối chiếu theo README và checklist của dự án. Phiếu đề bài gốc chưa được cung cấp trong workspace; cần đối chiếu lại trước khi nộp.</p>')
replace('<div class="placeholder">[BỔ SUNG HÌNH KIẾN TRÚC — có thể xuất Mermaid trong README, ghi rõ đây là sơ đồ thiết kế]</div>',
    '<figure class="evidence architecture"><img src="architecture.svg" alt="Sơ đồ Nginx, WordPress, MySQL, Prometheus, Grafana, Loki và Promtail"><figcaption>Sơ đồ thiết kế 1. Kiến trúc được vẽ từ compose.yaml và cấu hình monitoring; không phải ảnh chụp giao diện.</figcaption></figure>')
replace('Không thay theme, user quản trị hoặc nội dung cá nhân đã lưu.','Giữ theme và nội dung cá nhân; mật khẩu user quản trị đã được đổi theo yêu cầu người dùng.')
replace('HTTP của website và trang đăng nhập đã được kiểm tra; phiên đăng nhập quản trị và thao tác sửa/lưu nội dung cần chụp, xác nhận bổ sung. Không dùng HTTP 200 trang đăng nhập để khẳng định đã đăng nhập admin.',
    'Website trả HTTP 200. Đã đăng nhập thật bằng vanmanh_admin, truy cập Dashboard và danh sách Trang; ảnh dưới được chụp trong phiên quản trị đã xác thực. Chưa thử sửa/lưu một nội dung cá nhân.')
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 01 — website và các mục nội dung]</div>',figure('01-website.png','Trang chủ portfolio Nguyễn Văn Mạnh, ảnh cá nhân và navigation tới Kỹ năng / Dự án / Liên hệ.'))
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 02 — WordPress admin → Trang]</div>',figure('02-wordpress-admin.png','Phiên WordPress đã đăng nhập và danh sách các trang trong hệ thống.'))
replace('Mật khẩu ứng dụng đã được đổi sang 24 bytes ngẫu nhiên biểu diễn 48 ký tự hex bằng thay đổi mật khẩu của chính user; .env và các dịch vụ được đồng bộ. Không thay đổi bài viết/pages hoặc reset database.',
    'Mật khẩu ứng dụng, Grafana, WordPress admin và MySQL root đã được đặt theo yêu cầu người dùng; cấu hình và dịch vụ được đồng bộ. Không đưa giá trị mật khẩu vào báo cáo. Các mật khẩu cấu hình dài 11 ký tự, chưa đạt chính sách tối thiểu 20 ký tự.')
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 03 — phpMyAdmin đã đăng nhập và các bảng portfolio_db]</div>',figure('03-phpmyadmin-database.png','phpMyAdmin sau đăng nhập: database portfolio_db và danh sách 12 bảng.'))
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 15 — quyền của user ứng dụng trên schema]</div>',figure('15-database-grants.png','SHOW GRANTS FOR CURRENT_USER(): user portfolio_user có quyền trên schema portfolio_db.'))
content = re.sub(r'<p class="notice">Hai kiểm tra root chưa đạt:.*?</p>',
    '<p class="notice">Lỗi root 1045 trước đây đã được xử lý. Root đăng nhập thực tế thành công; MySQL đã trở lại xác thực bình thường và giữ volume cũ. Kiểm tra độ dài mật khẩu root vẫn chưa đạt vì mật khẩu người dùng chọn có 11 ký tự. Xem evidence/root-maintenance.json và evidence/local-root-auth.json.</p>' + figure('19-root-authentication.png','Kết quả lệnh thực tế: root@localhost đăng nhập thành công; skip_networking OFF, general_log OFF.'),content,count=1,flags=re.S)
replace('Đây là backup ứng dụng; full backup system accounts bằng root còn chờ xác thực root thành công.',
    'Đây là backup ứng dụng. Trong lần xử lý root, đã lưu thêm archive toàn bộ volume khi database dừng sạch, so sánh với dữ liệu nguồn, kiểm tra checksums và lưu full SQL dump gồm system accounts.')
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 05 — nginx -t và security headers]</div>',figure('05-nginx-headers.png','Kết quả lệnh thực tế: nginx -t thành công, HTTP 200 và năm security headers.','medium'))
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 06 — Prometheus targets UP]</div>',figure('06-prometheus-targets.png','Giao diện Prometheus hiển thị đủ tám jobs với trạng thái UP.','tall'))
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 07/08/09 — CPU/RAM, Nginx, MySQL thực tế; tách thành nhiều hình nếu cần]</div>',
    figure('07-grafana-container.png','Dashboard Grafana: CPU/RAM theo từng dịch vụ của project portfolio-manh.')+
    figure('08a-grafana-web-requests.png','Panel Nginx requests/giây lấy từ nginx_http_requests_total.')+
    figure('08b-grafana-web-connections.png','Panel số kết nối đang mở của Nginx.')+
    figure('08c-grafana-http-probe.png','Panel Blackbox probe_success cho khả dụng HTTP của website.')+
    figure('09a-grafana-database-queries.png','Panel MySQL queries/giây lấy từ exporter.')+
    figure('09b-grafana-database-threads.png','Panel MySQL threads đang kết nối.'))
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 10 — access logs; 11 — filter 4xx/5xx; 12 — request count theo thời gian]</div>',
    figure('10-logql-access.png','Grafana Explore / Portfolio Loki: truy vấn JSON access logs và dữ liệu thực.','medium')+
    figure('11-logql-errors.png','Grafana Explore: lọc numeric status 400–599, với request /.env trả 404 và /xmlrpc.php trả 403.','medium')+
    figure('12-logql-requests.png','Grafana Explore: biểu đồ số request trong từng cửa sổ một phút.','medium'))
replace('Ứng dụng/Grafana random 48 hex; .env ignore; root cũ còn cần xác minh.',
    'Mật khẩu được đặt theo yêu cầu, .env ignore; root đã xác thực. Độ dài 11 ký tự chưa đạt chính sách 20 ký tự.')
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 13/14 — Internal=true, ports localhost, users/capabilities; không chụp toàn bộ Config.Env]</div>',
    figure('13-hardening-networks.png','Kết quả inspect thực tế: application, database, monitoring đều Internal=true.','medium')+
    figure('14-hardening-ports-users.png','Các trường runtime được chọn: user, cổng localhost, cap_drop và no-new-privileges; không hiển thị Config.Env.','tall'))
content = re.sub(r'<p>Nguồn kết quả: evidence/verification.json.*?</p>',
    f'<p>Nguồn kết quả: evidence/verification.json do scripts/verify.py chạy trực tiếp trên stack lúc <strong>{html.escape(verification["checked_at"])}</strong>; đạt <strong>{passed}/{len(verification["checks"])} kiểm tra</strong>. Ba kiểm tra chưa đạt là độ dài MYSQL_PASSWORD, MYSQL_ROOT_PASSWORD và GRAFANA_ADMIN_PASSWORD: 11 ký tự thay vì tối thiểu 20. Các kiểm tra gốc được giữ nguyên; lỗi xác thực root trước đây đã được xử lý.</p>',content,count=1,flags=re.S)
replace('HTTP 200, giữ tên sinh viên/nội dung; login page không chứng minh phiên admin.','HTTP 200, giữ tên/nội dung; đã kiểm tra riêng phiên đăng nhập admin thật.')
replace('Internal networks, localhost mappings, application/Grafana random password; root còn hạn chế.','Internal networks và localhost mappings đạt. Ba mật khẩu cấu hình chưa đạt độ dài tối thiểu.')
replace('Credential từ environment không đăng nhập được; không reset hoặc xóa volume.','Root đăng nhập thành công bằng credential cấu hình; giữ nguyên volume dữ liệu.')
replace('Phiên admin vẫn chờ xác nhận Dashboard và danh sách Trang từ người dùng; chưa tự kiểm thử sửa/lưu nội dung.',
    'Phiên admin đã xác thực Dashboard và danh sách Trang qua HTTP thật; chưa thử sửa/lưu nội dung.')
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 04 — Compose trạng thái; chèn bảng tổng hợp kiểm thử từ JSON và ngày chạy cuối]</div>',
    figure('04-compose-status.png','Kết quả Docker Compose thực tế: 12 dịch vụ chạy, các healthchecks đạt; loki-init Exited (0).','medium')+
    figure('18-backup-validation.png','Metadata công khai của restore-test ứng dụng và cold archive toàn bộ volume.','medium')+
    figure('20-verification-results.png',f'Kết quả bộ kiểm tra thực tế: {passed}/40 PASS, ba FAIL chỉ liên quan độ dài mật khẩu.','tall'))
replace('[Bổ sung thao tác đăng nhập admin, sửa/lưu một nội dung được phép và kết quả quan sát; không khẳng định đã kiểm thử nếu chưa làm.]',
    'Ảnh quản trị chứng minh đăng nhập và xem danh sách Trang. Thao tác sửa/lưu nội dung vẫn cần kiểm thử trên nội dung được phép trước khi tuyên bố hoàn tất yêu cầu này.')
replace('Ban đầu không có repository Git nên không khôi phục hoặc giả lập lịch sử. Nhánh main đã được khởi tạo; chưa có commit/remote/push khi thực hiện công việc cấu hình.',
    'Nhánh main đã được khởi tạo. Kiểm tra hiện tại cho thấy source còn untracked, chưa có commit và chưa cấu hình remote. Ảnh dưới ghi đúng trạng thái quan sát, chưa đáp ứng yêu cầu ít nhất ba commits thực.')
replace('Yêu cầu tài khoản GitHub dùng mã sinh viên: DTC245200147. Chưa có bằng chứng account/remote để xác minh điều kiện này. Tên repository hoặc display name chứa mã sinh viên không thay cho username.',
    'Người dùng cung cấp tài khoản <a href="https://github.com/NguyenVanManh147?tab=repositories">NguyenVanManh147</a>. Trang Repositories công khai hiện hiển thị chưa có repository public. Username quan sát là NguyenVanManh147, khác DTC245200147 trong checklist; cần đối chiếu điều kiện tài khoản theo đề trước khi nộp. Chưa có URL repository của bài hoặc bằng chứng push source.')
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 16 — lịch sử ít nhất ba commits sau khi tạo]</div>',figure('16-git-status.png','Kết quả Git thực tế: nhánh main, source untracked, chưa có commit và remote.','medium'))
replace('<div class="placeholder">[BỔ SUNG ẢNH THẬT 17 — username GitHub và repository sau khi được phép push]</div>',figure('17a-github-account.png','Trang GitHub do người dùng cung cấp: NguyenVanManh147, hiện chưa có repository công khai.'))
replace('[BỔ SUNG ẢNH THẬT 18 — manifest backup và kết quả restore-test, không mở SQL/private accounts. Ảnh 19 — root auth chỉ bổ sung sau khi kiểm tra thực sự PASS.]',
    'Ảnh backup đã được chèn ở phần kiểm thử; ảnh root authentication đã được chèn ở phần MySQL. File evidence/screenshots.json lưu nguồn, thời gian và SHA-256 của các ảnh. Các hình kết quả lệnh là trang hiển thị output thực tế, không phải ảnh terminal của Windows.')
replace('Xác minh credential root MySQL trên máy, thống nhất cách cập nhật nếu cần; không xóa volume.',
    'Độ dài mật khẩu hiện là 11 ký tự theo yêu cầu người dùng; cần tăng lên tối thiểu 20 nếu muốn đáp ứng cả ba kiểm tra chính sách.')
replace('Đăng nhập WordPress admin, kiểm thử thao tác nội dung và chụp minh chứng.','Đã đăng nhập và chụp admin; còn kiểm thử sửa/lưu nội dung được phép.')
replace('Chụp các ảnh dashboard, targets, LogQL, database và hardening theo checklist.','Đã chèn ảnh dashboard, targets, LogQL, database và hardening; kiểm tra hình trong PDF cuối.')
replace('Chỉ push khi được yêu cầu; chèn ảnh thật và xuất bản báo cáo PDF cuối.','Bổ sung thông tin khoa, lớp, học phần, giảng viên; hoàn tất repository/commits và ảnh GitHub của bài khi có.')
replace('[Bổ sung nhận xét cá nhân về kiến thức học được, khó khăn và hướng phát triển phù hợp, dựa trên quá trình thực tế.]',
    'Phần nhận xét cá nhân của sinh viên cần bổ sung dựa trên quá trình học và triển khai thực tế.')
replace('.footer::after { content: "Trang khung " counter(sheet); float: right; }','.footer::after { content: "Phần " counter(sheet); float: right; }')
extra = '''
figure.evidence { margin: 5mm 0 7mm; break-inside: avoid; page-break-inside: avoid; }
figure.evidence img { display: block; width: 100%; height: auto; object-fit: contain; border: 1px solid #cbd5e1; background: #fff; }
figure.evidence.compact img { max-height: 95mm; }
figure.evidence.medium img { max-height: 130mm; }
figure.evidence.tall img { max-height: 190mm; }
figure.evidence.architecture img { max-height: 120mm; border: 0; }
figcaption { margin-top: 2mm; font-size: 9pt; line-height: 1.45; color: #334155; }
.capture-time { display: block; font-size: 8pt; color: #64748b; }
.footer { position: static; margin-top: 10mm; }
a { color: #164e63; }
@media print {
 .page { min-height: 0; padding: 0; }
 .cover { min-height: 257mm; padding-top: 15mm; }
 .footer { display: none; }
 h2, h3 { break-after: avoid; }
 figure, table { break-inside: avoid; }
 figure a { display: block; }
}
'''
replace('</style>',extra+'</style>')
if re.search(r'BỔ SUNG ẢNH|class="placeholder"',content):
    raise RuntimeError('Unfilled image placeholder remains')
if len(re.findall(r'<section class="page',content)) != 12:
    raise RuntimeError('Original twelve report sections must be retained')
REPORT.write_text(content,encoding='utf-8')
(ROOT / 'evidence/report-image-index.json').write_text(json.dumps({'screenshot_count':len(included),'images':included,'architecture':'docs/architecture.svg','result':f'{passed}/40'},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(f'Report updated: {len(included)} real screenshots, architecture diagram, {passed}/40 checks; 12 original sections retained.')
