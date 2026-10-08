"""Real integration checks. Writes sanitized evidence; never manufactures screenshots."""
import base64
import datetime
import html.parser
import http.cookiejar
import json
import pathlib
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
settings = {}
for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
    if line.strip() and not line.lstrip().startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        settings[key] = value.strip().strip("'\"")
report = {'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(), 'checks': []}

def record(name, ok, detail):
    report['checks'].append({'name': name, 'passed': bool(ok), 'detail': detail})
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)

def run(*args, input=None):
    return subprocess.run(list(args), cwd=ROOT, input=input, capture_output=True)

def request(url, auth=None):
    headers = {}
    if auth:
        headers['Authorization'] = 'Basic ' + base64.b64encode(auth.encode()).decode()
    try:
        response = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15)
    except urllib.error.HTTPError as exc:
        response = exc
    return response.status, dict(response.headers), response.read()

def api(url, auth=None):
    status, _, body = request(url, auth)
    if status != 200:
        raise RuntimeError(f'HTTP {status}: {url.split("?")[0]}')
    return json.loads(body)

for name, args in [
    ('Compose syntax', ['docker', 'compose', 'config', '--quiet']),
    ('Nginx syntax', ['docker', 'compose', 'exec', '-T', 'nginx', 'nginx', '-t']),
    ('Prometheus syntax', ['docker', 'compose', 'exec', '-T', 'prometheus', 'promtool', 'check', 'config', '/etc/prometheus/prometheus.yml']),
    ('Loki syntax', ['docker', 'compose', 'exec', '-T', 'loki', '/usr/bin/loki', '-config.file=/etc/loki/loki.yml', '-verify-config=true']),
    ('Promtail syntax', ['docker', 'compose', 'exec', '-T', 'promtail', '/usr/bin/promtail', '-config.file=/etc/promtail/promtail.yml', '-check-syntax']),
]:
    result = run(*args)
    record(name, result.returncode == 0, (result.stdout + result.stderr).decode(errors='replace')[-3000:])

web = 'http://localhost:' + settings.get('WEB_PORT', '8080')
status, headers, body = request(web + '/')
record('Website and existing content', status == 200 and 'Nguyễn Văn Mạnh' in body.decode('utf-8'), {'status': status})
record('Nginx security headers', all(k.lower() in {h.lower() for h in headers} for k in ['X-Content-Type-Options', 'X-Frame-Options', 'Referrer-Policy', 'Permissions-Policy', 'Content-Security-Policy']), headers)
status, _, _ = request(web + '/wp-login.php')
record('WordPress login page', status == 200, {'status': status})
status, _, _ = request('http://localhost:' + settings.get('PMA_PORT', '8081') + '/')
record('phpMyAdmin page', status == 200, {'status': status})
try:
    class FormInputs(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.hidden = {}
        def handle_starttag(self, tag, attrs):
            data = dict(attrs)
            if tag == 'input' and data.get('type') == 'hidden' and 'name' in data:
                self.hidden[data['name']] = data.get('value', '')
    pma = 'http://localhost:' + settings.get('PMA_PORT', '8081')
    session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    form = FormInputs()
    form.feed(session.open(pma + '/', timeout=15).read().decode('utf-8'))
    form.hidden.update({'pma_username': settings['MYSQL_USER'], 'pma_password': settings['MYSQL_PASSWORD'], 'server': '1'})
    response = session.open(pma + '/index.php?route=/', data=urllib.parse.urlencode(form.hidden).encode(), timeout=15)
    authenticated_html = response.read().decode('utf-8')
    logged_in = 'route=/logout' in authenticated_html or 'route=%2Flogout' in authenticated_html
    record('phpMyAdmin authenticated database access', logged_in and settings['MYSQL_DATABASE'] in authenticated_html, {'status': response.status, 'authenticated': logged_in, 'database_visible': settings['MYSQL_DATABASE'] in authenticated_html})
except Exception as exc:
    record('phpMyAdmin authenticated database access', False, type(exc).__name__)

php = b'''<?php
require '/var/www/html/wp-load.php';
global $wpdb;
echo json_encode([
 'pages' => $wpdb->get_results("SELECT ID, post_title, post_content FROM {$wpdb->posts} WHERE post_type='page'", ARRAY_A),
 'grants' => $wpdb->get_results('SHOW GRANTS FOR CURRENT_USER()', ARRAY_N),
 'file_editor_disabled' => defined('DISALLOW_FILE_EDIT') && DISALLOW_FILE_EDIT,
]);
'''
wordpress_info = run('docker', 'compose', 'exec', '-T', 'wordpress', 'php', input=php)
info = json.loads(wordpress_info.stdout)
xml = ET.parse(ROOT / 'wordpress/portfolio-export.xml')
ns = {'wp': 'http://wordpress.org/export/1.2/', 'content': 'http://purl.org/rss/1.0/modules/content/'}
expected_pages = {item.findtext('wp:post_id', namespaces=ns): {'title': item.findtext('title'), 'content': item.findtext('content:encoded', default='', namespaces=ns)} for item in xml.findall('./channel/item') if item.findtext('wp:post_type', namespaces=ns) == 'page'}
unchanged = all(page['ID'] in expected_pages and page['post_title'] == expected_pages[page['ID']]['title'] and page['post_content'] == expected_pages[page['ID']]['content'] for page in info['pages'])
record('Existing WordPress pages preserved', unchanged and len(info['pages']) == len(expected_pages), {'page_count': len(info['pages']), 'baseline_count': len(expected_pages)})
grants = [row[0] for row in info['grants']]
record('Application database privileges scoped to schema', any('ALL PRIVILEGES ON' in grant for grant in grants) and not any('ON *.*' in grant and not grant.startswith('GRANT USAGE') for grant in grants), grants)
record('WordPress file editor disabled', info['file_editor_disabled'], {'DISALLOW_FILE_EDIT': info['file_editor_disabled']})
status, _, _ = request(web + '/xmlrpc.php')
record('XML-RPC blocked (real 403 request)', status == 403, {'status': status})
status, _, _ = request(web + '/.env')
record('Hidden files blocked (real 404 request)', status == 404, {'status': status})

prom = 'http://localhost:' + settings.get('PROMETHEUS_PORT', '9090')
targets = api(prom + '/api/v1/targets')['data']['activeTargets']
target_summary = [{'job': t['labels']['job'], 'health': t['health'], 'error': t['lastError']} for t in targets]
record('Prometheus 8 targets', len(targets) == 8 and all(t['health'] == 'up' for t in targets), target_summary)
expressions = [
    'nginx_up{job="nginx"}', 'mysql_up{job="mysql"}', 'probe_success{job="portfolio_http"}',
    'container_memory_working_set_bytes{job="cadvisor",container_label_com_docker_compose_project="portfolio-manh"}',
    'rate(container_cpu_usage_seconds_total{job="cadvisor",container_label_com_docker_compose_project="portfolio-manh"}[2m])',
    'rate(nginx_http_requests_total{job="nginx"}[2m])',
    'mysql_global_status_threads_connected{job="mysql"}', 'rate(mysql_global_status_queries{job="mysql"}[2m])',
]
for expr in expressions:
    result = api(prom + '/api/v1/query?' + urllib.parse.urlencode({'query': expr}))['data']['result']
    is_up = all(float(item['value'][1]) == 1 for item in result) if expr.startswith(('nginx_up', 'mysql_up', 'probe_success')) else True
    record('PromQL: ' + expr, bool(result) and is_up, {'series_count': len(result), 'samples': result[:2]})

grafana = 'http://localhost:' + settings.get('GRAFANA_PORT', '3000')
auth = settings.get('GRAFANA_ADMIN_USER', 'admin') + ':' + settings['GRAFANA_ADMIN_PASSWORD']
try:
    for uid in ['portfolio-prometheus', 'portfolio-loki']:
        item = api(grafana + '/api/datasources/uid/' + uid, auth)
        record('Grafana datasource ' + uid, item.get('url') in ['http://prometheus:9090', 'http://loki:3100'], {'uid': item.get('uid'), 'url': item.get('url')})
        health = api(grafana + '/api/datasources/uid/' + uid + '/health', auth)
        record('Grafana datasource health ' + uid, health.get('status') == 'OK', health)
    for uid in ['portfolio-infrastructure', 'portfolio-logs']:
        item = api(grafana + '/api/dashboards/uid/' + uid, auth)
        record('Grafana provisioned dashboard ' + uid, item['meta'].get('provisioned'), {'title': item['dashboard']['title'], 'provisioned': item['meta'].get('provisioned')})
except Exception as exc:
    record('Grafana authenticated API', False, str(exc))

queries = [
    '{project="portfolio-manh",job="nginx-access"} | json',
    '{project="portfolio-manh",job="nginx-access"} | json | __error__="" | status >= 400 | status < 600',
    'sum(count_over_time({project="portfolio-manh",job="nginx-access"}[1m]))',
]
# Query Loki inside the network; no need to publish its unauthenticated API.
for index, query in enumerate(queries, 1):
    now = time.time_ns()
    url = 'http://loki:3100/loki/api/v1/query_range?' + urllib.parse.urlencode({'query': query, 'start': now - 900_000_000_000, 'end': now, 'step': '15', 'limit': '30'})
    output = run('docker', 'compose', 'exec', '-T', 'nginx', 'wget', '-qO-', url)
    try:
        item = json.loads(output.stdout)
        samples = item['data']['result']
        record('LogQL ' + str(index), item['status'] == 'success' and bool(samples), {'query': query, 'series_count': len(samples), 'samples': samples[:2]})
    except Exception as exc:
        record('LogQL ' + str(index), False, str(exc))

ids = run('docker', 'compose', 'ps', '-q').stdout.decode().split()
inspection = json.loads(run('docker', 'inspect', *ids).stdout)
metadata = [{
    'service': item['Config']['Labels']['com.docker.compose.service'],
    'user': item['Config']['User'], 'privileged': item['HostConfig']['Privileged'],
    'security_options': item['HostConfig']['SecurityOpt'], 'cap_drop': item['HostConfig']['CapDrop'],
    'ports': item['HostConfig']['PortBindings'], 'networks': list(item['NetworkSettings']['Networks']),
    'volumes': [{'name': v.get('Name'), 'target': v['Destination'], 'writable': v['RW']} for v in item['Mounts']],
} for item in inspection]
record('Localhost published ports', all(v['HostIp'] == '127.0.0.1' for item in inspection for bindings in (item['HostConfig']['PortBindings'] or {}).values() for v in (bindings or [])), metadata)
network_ids = [settings.get('COMPOSE_PROJECT_NAME', 'portfolio-manh') + '_' + n for n in ['application', 'database', 'monitoring']]
network_meta = json.loads(run('docker', 'network', 'inspect', *network_ids).stdout)
record('Internal application/database/monitoring networks', all(x['Internal'] for x in network_meta), [{'name': x['Name'], 'internal': x['Internal']} for x in network_meta])
for key in ['MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'GRAFANA_ADMIN_PASSWORD']:
    value = settings[key]
    record('Password length policy: ' + key, len(value) >= 20 and not value.startswith('CHANGE_ME'), {'length': len(value), 'minimum': 20, 'note': 'Checks the configured value; service authentication is checked separately. Length alone does not prove entropy.'})
root_test = run('docker', 'compose', 'exec', '-T', 'db', 'sh', '-s', input=b'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"\nmysql -uroot -e "SELECT 1" >/dev/null 2>&1\n')
record('Existing MySQL root credential authentication', root_test.returncode == 0, {'authenticated': root_test.returncode == 0, 'note': 'No root reset or volume deletion attempted.'})
ignored = run('git', 'check-ignore', '.env', 'backups/before-changes.sql')
record('Secrets and backup ignored by Git', ignored.returncode == 0, ignored.stdout.decode())
(ROOT / 'evidence').mkdir(exist_ok=True)
(ROOT / 'evidence' / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
failures = sum(not c['passed'] for c in report['checks'])
print(f'{len(report["checks"])} checks, {failures} failures; evidence/verification.json contains actual results.')
raise SystemExit(1 if failures else 0)
