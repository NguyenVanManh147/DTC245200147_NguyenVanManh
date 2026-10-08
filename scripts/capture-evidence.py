"""Capture real browser views and render sanitized command output for the report."""
import argparse
import datetime
import hashlib
import html
import json
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'secrets/browser-deps'))
from playwright.sync_api import sync_playwright
from private_support import read_env, docker, sql

EVIDENCE = ROOT / 'evidence'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
META = EVIDENCE / 'screenshots.json'
settings = read_env()
WEB = 'http://localhost:' + settings.get('WEB_PORT', '8080')
PMA = 'http://localhost:' + settings.get('PMA_PORT', '8081')
GRAFANA = 'http://localhost:' + settings.get('GRAFANA_PORT', '3000')
PROM = 'http://localhost:' + settings.get('PROMETHEUS_PORT', '9090')
records = json.loads(META.read_text(encoding='utf-8')) if META.exists() else {}

def timestamp():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(timespec='seconds')

def snap(page, name, source, label, full=False, target=None):
    if target is None:
        page.screenshot(path=str(EVIDENCE / name), full_page=full, animations='disabled')
    else:
        target.screenshot(path=str(EVIDENCE / name),animations='disabled')
    records[name] = {'captured_at':timestamp(), 'source':source, 'label':label,
        'sha256':hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest()}
    (EVIDENCE / (pathlib.Path(name).stem + '.capture.json')).write_text(json.dumps(records[name],indent=2,ensure_ascii=False),encoding='utf-8')
    for entry in EVIDENCE.glob('*.capture.json'):
        records[entry.name.replace('.capture.json','.png')] = json.loads(entry.read_text(encoding='utf-8'))
    META.write_text(json.dumps(records, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Captured ' + name, flush=True)

def run_command(args):
    completed = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=90)
    return completed.returncode, completed.stdout.decode(errors='replace') + completed.stderr.decode(errors='replace')

def command_view(page, name, title, blocks):
    when = timestamp()
    sections = ''.join('<section><h2>' + html.escape(command) + '</h2><pre>' + html.escape(output) + '</pre></section>' for command, output in blocks)
    content = '<!doctype html><html lang="vi"><meta charset="utf-8"><style>body{margin:0;background:#edf2f7;color:#14243a;font:18px/1.5 Segoe UI,Arial;padding:32px}main{max-width:1420px;margin:auto;background:white;border:1px solid #c8d5e1;border-radius:12px;padding:28px}h1{font-size:27px;color:#164e63;margin:0 0 10px}h2{font:16px Consolas,monospace;background:#e7eef5;padding:10px;margin-top:24px}pre{font:15px/1.65 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}p{color:#54667c;font-size:15px}</style><main><h1>' + html.escape(title) + '</h1><p>Kết quả lệnh/API thực tế • ' + when + ' • Portfolio Nguyễn Văn Mạnh / DTC245200147</p>' + sections + '</main></html>'
    source = EVIDENCE / (pathlib.Path(name).stem + '.html')
    content = content.replace('\r\n', '\n').replace('\r', '')
    content = '\n'.join(line.rstrip() for line in content.splitlines()) + '\n'
    source.write_text(content, encoding='utf-8', newline='\n')
    page.goto(source.as_uri())
    snap(page, name, str(source.relative_to(ROOT)), title, target=page.locator('main'))

def commands(page):
    code, output = run_command(['docker','compose','ps','-a','--format','table {{.Service}}\t{{.Status}}\t{{.Ports}}'])
    if code:
        raise RuntimeError('Compose status command failed')
    command_view(page,'04-compose-status.png','Trạng thái Docker Compose', [('docker compose ps -a (Service / Status / Ports)',output)])
    code, syntax = run_command(['docker','compose','exec','-T','nginx','nginx','-t'])
    code2, headers = run_command(['curl.exe','--max-time','15','-sS','-I',WEB + '/'])
    if code or code2:
        raise RuntimeError('Nginx evidence commands failed')
    command_view(page,'05-nginx-headers.png','Nginx: cấu hình hợp lệ và security headers', [('docker compose exec -T nginx nginx -t',syntax),('curl.exe -I ' + WEB + '/',headers)])
    networks = [settings.get('COMPOSE_PROJECT_NAME','portfolio-manh') + '_' + n for n in ['application','database','monitoring']]
    network_data = json.loads(docker('network','inspect',*networks))
    network_output = json.dumps([{'Name':n['Name'],'Internal':n['Internal'],'Driver':n['Driver'],'Containers':len(n['Containers'])} for n in network_data],indent=2)
    command_view(page,'13-hardening-networks.png','Ba mạng nội bộ của dự án', [('docker network inspect (chỉ Name / Internal / Driver / Containers)',network_output)])
    ids = docker('compose','ps','-q').decode().split()
    instances = json.loads(docker('inspect',*ids))
    lines = []
    for c in sorted(instances,key=lambda c:c['Config']['Labels']['com.docker.compose.service']):
        service = c['Config']['Labels']['com.docker.compose.service']
        ports = [b['HostIp'] + ':' + b['HostPort'] + ' -> ' + port for port,bindings in (c['HostConfig']['PortBindings'] or {}).items() for b in (bindings or [])]
        lines.append(f"{service:<17} user={c['Config']['User'] or 'entrypoint'}  privileged={c['HostConfig']['Privileged']}  read_only={c['HostConfig']['ReadonlyRootfs']}\n  ports={', '.join(ports) or 'không publish'}; cap_drop={c['HostConfig']['CapDrop'] or []}; security_opt={c['HostConfig']['SecurityOpt'] or []}")
    command_view(page,'14-hardening-ports-users.png','Cổng localhost và quyền container', [('docker inspect (chọn trường user / ports / security_opt / cap_drop; không lấy Config.Env)','\n'.join(lines))])
    git_views(page)
    backup = json.loads((EVIDENCE / 'backup-validation.json').read_text(encoding='utf-8'))
    root = json.loads((EVIDENCE / 'root-maintenance.json').read_text(encoding='utf-8'))
    selected = {k:backup[k] for k in ['checked_at','database','table_count','dump_exit_code','restore_verified','restored_tables_match','check_table_all_ok','original_volume_modified','restore_network']}
    command_view(page,'18-backup-validation.png','Sao lưu ứng dụng và bản sao toàn bộ volume đã kiểm tra', [('evidence/backup-validation.json (các trường kiểm chứng công khai)',json.dumps(selected,indent=2)),('evidence/root-maintenance.json (metadata, không chứa credential)',json.dumps({k:root[k] for k in ['checked_at','cold_archive_verified','same_data_volume','normal_authentication_restored']},indent=2))])
    root_output = sql(settings['MYSQL_ROOT_PASSWORD'],"SELECT CURRENT_USER(); SHOW GLOBAL VARIABLES WHERE Variable_name IN ('skip_networking','general_log');").decode()
    command_view(page,'19-root-authentication.png','MySQL root: đăng nhập thành công và xác thực bình thường', [('MySQL client qua socket; credential lấy từ .env, không hiển thị\nSELECT CURRENT_USER();\nSHOW GLOBAL VARIABLES WHERE Variable_name IN (\'skip_networking\',\'general_log\');',root_output)])
    verification = json.loads((EVIDENCE / 'verification.json').read_text(encoding='utf-8'))
    output = 'Thời gian kiểm tra: ' + verification['checked_at'] + '\n\n' + '\n'.join(('PASS  ' if c['passed'] else 'FAIL  ') + c['name'] for c in verification['checks'])
    count = sum(item['passed'] for item in verification['checks'])
    command_view(page,'20-verification-results.png',f"Kết quả kiểm thử tích hợp: {count}/{len(verification['checks'])} đạt", [('evidence/verification.json — kết quả bộ kiểm tra thực tế',output)])

def git_views(page):
    _, branch = run_command(['git','branch','--show-current'])
    _, status = run_command(['git','status','--short'])
    log_code, log = run_command(['git','log','--oneline','--graph','--decorate','-8'])
    _, remotes = run_command(['git','remote','-v'])
    if log_code:
        raise RuntimeError('Git commit history is unavailable')
    command_view(page,'16-git-status.png','Lịch sử commits và repository GitHub của bài', [('git branch --show-current',branch),('git status --short',status or '(Working tree sạch)'),('git log --oneline --graph --decorate -8',log),('git remote -v',remotes or '(Chưa cấu hình remote)')])

def ui(page):
    page.goto(WEB + '/',wait_until='networkidle')
    page.wait_for_timeout(1200)
    snap(page,'01-website.png',WEB + '/','Website portfolio Nguyễn Văn Mạnh',full=True)
    local = json.loads((ROOT / 'secrets/local-auth.json').read_text(encoding='utf-8'))
    page.goto(WEB + '/wp-login.php')
    page.locator('#user_login').fill(local['WORDPRESS_ADMIN_USER'])
    page.locator('#user_pass').fill(local['WORDPRESS_ADMIN_PASSWORD'])
    page.locator('#wp-submit').click()
    page.wait_for_url('**/wp-admin/**')
    page.goto(WEB + '/wp-admin/edit.php?post_type=page',wait_until='networkidle')
    page.locator('#the-list').wait_for()
    snap(page,'02-wordpress-admin.png',WEB + '/wp-admin/edit.php?post_type=page','WordPress đã đăng nhập: danh sách Trang')
    database(page)
    monitoring(page)

def database(page):
    page.goto(PMA + '/',wait_until='networkidle')
    page.locator('input[name="pma_username"]').fill(settings['MYSQL_USER'])
    page.locator('input[name="pma_password"]').fill(settings['MYSQL_PASSWORD'])
    page.locator('#input_go').click()
    page.wait_for_timeout(1800)
    page.goto(PMA + '/index.php?route=/database/structure&db=' + urllib.parse.quote(settings['MYSQL_DATABASE']),wait_until='networkidle')
    page.wait_for_timeout(1000)
    snap(page,'03-phpmyadmin-database.png',PMA + '/ (database structure)','phpMyAdmin đã đăng nhập: các bảng portfolio_db')
    page.goto(PMA + '/index.php?route=/database/sql&db=' + urllib.parse.quote(settings['MYSQL_DATABASE']),wait_until='networkidle')
    page.wait_for_timeout(1500)
    editors = page.locator('.CodeMirror:visible')
    if editors.count():
        editors.first.click()
        page.keyboard.press('Control+A')
        page.keyboard.insert_text('SHOW GRANTS FOR CURRENT_USER();')
    else:
        page.locator('textarea[name="sql_query"]').fill('SHOW GRANTS FOR CURRENT_USER();')
    page.locator('#button_submit_query').click()
    page.wait_for_function("document.body.innerText.includes('GRANT USAGE')",timeout=15000)
    snap(page,'15-database-grants.png',PMA + '/ (SHOW GRANTS FOR CURRENT_USER)','Quyền của tài khoản ứng dụng trên portfolio_db')

def monitoring(page):
    page.goto(PROM + '/targets',wait_until='domcontentloaded')
    page.wait_for_timeout(1500)
    snap(page,'06-prometheus-targets.png',PROM + '/targets','Tám mục tiêu Prometheus',full=True)
    page.goto(GRAFANA + '/login',wait_until='domcontentloaded')
    page.locator('input[name="user"]').fill(settings.get('GRAFANA_ADMIN_USER','admin'))
    page.locator('input[name="password"]').fill(settings['GRAFANA_ADMIN_PASSWORD'])
    page.get_by_role('button',name='Log in',exact=True).click()
    page.wait_for_timeout(1200)
    page.goto(GRAFANA + '/d/portfolio-infrastructure?orgId=1&from=now-30m&to=now&kiosk',wait_until='domcontentloaded')
    page.wait_for_timeout(5000)
    snap(page,'07-grafana-container.png',GRAFANA + '/d/portfolio-infrastructure','Grafana: CPU/RAM của các container')
    print('PANEL MARKUP ' + json.dumps(page.evaluate("""() => Array.from(document.querySelectorAll('[data-testid]')).filter(e => /Panel header/.test(e.getAttribute('data-testid'))).slice(0,10).map(e => ({testid:e.getAttribute('data-testid'),ancestors:[e.parentElement,e.parentElement.parentElement,e.parentElement.parentElement.parentElement].map(a=>({tag:a.tagName,cls:a.className,testid:a.getAttribute('data-testid'),panel:a.getAttribute('data-panelid')}))}))"""),ensure_ascii=False),flush=True)
    for path in ['/', '/xmlrpc.php', '/.env']:
        try:
            urllib.request.urlopen(WEB + path,timeout=15).read()
        except urllib.error.HTTPError:
            pass
    for panel,name,label in [(3,'08a-grafana-web-requests.png','Nginx requests mỗi giây'),(4,'08b-grafana-web-connections.png','Nginx kết nối đang mở'),(7,'08c-grafana-http-probe.png','HTTP probe khả dụng'),(5,'09a-grafana-database-queries.png','MySQL queries mỗi giây'),(6,'09b-grafana-database-threads.png','MySQL threads đang kết nối')]:
        url = GRAFANA + '/d-solo/portfolio-infrastructure?orgId=1&from=now-30m&to=now&panelId=' + str(panel)
        page.goto(url,wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        snap(page,name,url,'Grafana: ' + label)
    queries = ['{project="portfolio-manh",job="nginx-access"} | json','{project="portfolio-manh",job="nginx-access"} | json | __error__="" | status >= 400 | status < 600','sum(count_over_time({project="portfolio-manh",job="nginx-access"}[1m]))']
    for index,query in enumerate(queries):
        panes = {'A':{'datasource':'portfolio-loki','queries':[{'refId':'A','expr':query,'queryType':'range','datasource':{'type':'loki','uid':'portfolio-loki'}}],'range':{'from':'now-15m','to':'now'}}}
        url = GRAFANA + '/explore?' + urllib.parse.urlencode({'schemaVersion':'1','panes':json.dumps(panes),'orgId':'1'})
        page.goto(url,wait_until='domcontentloaded')
        page.wait_for_timeout(3500)
        name = ['10-logql-access.png','11-logql-errors.png','12-logql-requests.png'][index]
        snap(page,name,GRAFANA + '/explore (Portfolio Loki)','Grafana Explore: ' + query)
        print('Explore ' + str(index + 1) + ': ' + page.locator('body').inner_text()[-1100:],flush=True)

def github(page):
    url = 'https://github.com/NguyenVanManh147?tab=repositories'
    page.goto(url,wait_until='domcontentloaded',timeout=60000)
    page.wait_for_timeout(2500)
    snap(page,'17a-github-account.png',url,'Tài khoản GitHub do người dùng cung cấp: NguyenVanManh147',full=True)
    links = page.locator('a[href^="/NguyenVanManh147/"]').evaluate_all("els => Array.from(new Set(els.map(e=>e.getAttribute('href')).filter(h=>/^\\/NguyenVanManh147\\/[^/?#]+$/.test(h))))")
    print('GitHub repositories: ' + json.dumps(links),flush=True)
    _, remotes = run_command(['git','remote','-v'])
    repo_url = 'https://github.com/NguyenVanManh147/DTC245200147_NguyenVanManh'
    page.goto(repo_url,wait_until='domcontentloaded',timeout=60000)
    page.wait_for_timeout(1800)
    text = page.locator('body').inner_text()
    source_visible = 'README.md' in text and 'compose.yaml' in text
    if not source_visible:
        raise RuntimeError('Published repository source is not visible yet')
    snap(page,'17b-github-repository.png',repo_url,'Repository GitHub của bài: source và README',full=True)
    (EVIDENCE / 'github-observation.json').write_text(json.dumps({'checked_at':timestamp(),'profile_url':url,'username':'NguyenVanManh147','repository_links':links,'local_remotes_configured':bool(remotes.strip()),'repository_url':repo_url,'public_source_visible':source_visible},indent=2),encoding='utf-8')

def report_pdf(page):
    page.goto((ROOT / 'docs/report.html').as_uri(),wait_until='networkidle')
    missing = page.locator('img').evaluate_all('(images) => images.filter(i => !i.complete || i.naturalWidth === 0).map(i => i.getAttribute("src"))')
    if missing:
        raise RuntimeError('Missing report images: ' + str(missing))
    page.pdf(path=str(ROOT / 'docs/BaoCao_DTC245200147_NguyenVanManh.pdf'),format='A4',print_background=True,prefer_css_page_size=True)
    snap(page,'21-report-preview.png','docs/report.html','Báo cáo đã chèn ảnh minh chứng')
    from pypdf import PdfReader
    reader = PdfReader(ROOT / 'docs/BaoCao_DTC245200147_NguyenVanManh.pdf')
    count = len(reader.pages)
    print('PDF pages: ' + str(count),flush=True)
    if count < 10:
        raise RuntimeError('PDF has fewer than 10 pages')
    (EVIDENCE / 'report-validation.json').write_text(json.dumps({'checked_at':timestamp(),'images':page.locator('img').count(),'missing_images':missing,'pdf_pages':count,'pdf_file':'docs/BaoCao_DTC245200147_NguyenVanManh.pdf'},indent=2),encoding='utf-8')

parser = argparse.ArgumentParser()
parser.add_argument('phase',choices=['ui','commands','pdf','github','git','database','monitoring'])
args = parser.parse_args()
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=EDGE,headless=True,args=['--disable-gpu','--no-first-run'])
    context = browser.new_context(viewport={'width':1440,'height':950},locale='vi-VN',timezone_id='Asia/Ho_Chi_Minh',device_scale_factor=1)
    context.set_default_timeout(25000)
    page = context.new_page()
    try:
        {'ui':ui,'commands':commands,'pdf':report_pdf,'github':github,'git':git_views,'database':database,'monitoring':monitoring}[args.phase](page)
    finally:
        context.close()
        browser.close()
