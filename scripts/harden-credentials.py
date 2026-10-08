"""Rotate working app and Grafana credentials once. Does not guess or reset MySQL root."""
import base64
import json
import pathlib
import secrets
import subprocess
import urllib.request

root = pathlib.Path(__file__).resolve().parents[1]
path = root / '.env'
content = path.read_text(encoding='utf-8')
settings = {}
for line in content.splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        settings[key] = value.strip().strip("'\"")
backup = root / 'backups' / 'credentials-before-hardening.env'
backup.parent.mkdir(exist_ok=True)
if not backup.exists():
    backup.write_text(content, encoding='utf-8')

def update(key, value):
    global content
    content = '\n'.join(f"{key}='{value}'" if line.startswith(key + '=') else line for line in content.splitlines()) + '\n'
    path.write_text(content, encoding='utf-8')
    settings[key] = value

if len(settings['MYSQL_PASSWORD']) < 20:
    password = secrets.token_hex(24)
    script = '''set -eu
export MYSQL_PWD="$MYSQL_PASSWORD"
mysql -u"$MYSQL_USER" <<'PORTFOLIO_SQL'
ALTER USER CURRENT_USER() IDENTIFIED BY '%s';
PORTFOLIO_SQL
''' % password
    result = subprocess.run(['docker', 'compose', 'exec', '-T', 'db', 'sh', '-s'], cwd=root, input=script.encode(), capture_output=True)
    if result.returncode:
        raise SystemExit('Application password change failed; .env application credential was not changed.')
    update('MYSQL_PASSWORD', password)
    print('Application database password rotated; existing content preserved. Recreate affected services next.')

if len(settings['GRAFANA_ADMIN_PASSWORD']) < 20:
    password = secrets.token_hex(24)
    auth = settings.get('GRAFANA_ADMIN_USER', 'admin') + ':' + settings['GRAFANA_ADMIN_PASSWORD']
    data = json.dumps({'oldPassword': settings['GRAFANA_ADMIN_PASSWORD'], 'newPassword': password, 'confirmNew': password}).encode()
    request = urllib.request.Request('http://localhost:' + settings.get('GRAFANA_PORT', '3000') + '/api/user/password', data=data, method='PUT', headers={
        'Content-Type': 'application/json', 'Authorization': 'Basic ' + base64.b64encode(auth.encode()).decode(),
    })
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise SystemExit('Grafana password change failed; .env Grafana credential was not changed.')
    update('GRAFANA_ADMIN_PASSWORD', password)
    print('Grafana password rotated. New credentials are only in ignored .env.')
print('MySQL root credential preserved: existing root authentication remains unresolved.')
