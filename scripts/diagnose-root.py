"""Read-only root diagnosis. Never prints passwords, environment values, or auth hashes."""
import datetime
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

def run(*args, input=None):
    return subprocess.run(['docker', *args], cwd=ROOT, input=input, capture_output=True, timeout=60)

def read_env(path):
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            values[key] = value
    return values

resolved = run('compose', 'config', '--format', 'json')
if resolved.returncode:
    raise SystemExit('Compose config failed; credentials not printed.')
config = json.loads(resolved.stdout)
env = read_env(ROOT / '.env')
db_id = run('compose', 'ps', '-q', 'db').stdout.decode().strip()
if not db_id:
    raise SystemExit('Database is not running; diagnosis did not start/recreate anything.')
db = json.loads(run('inspect', db_id).stdout)[0]
live_env = dict(item.split('=', 1) for item in db['Config']['Env'])
report = {
    'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
    'configured_root_password_length': len(env['MYSQL_ROOT_PASSWORD']),
    'env_matches_compose_root': env['MYSQL_ROOT_PASSWORD'] == config['services']['db']['environment']['MYSQL_ROOT_PASSWORD'],
    'env_matches_running_container_root': env['MYSQL_ROOT_PASSWORD'] == live_env['MYSQL_ROOT_PASSWORD'],
    'data_mounts': [{'type': m['Type'], 'name': m.get('Name'), 'destination': m['Destination']} for m in db['Mounts']],
    'database_image_id': db['Image'],
    'attempts': [],
}
sources = [('.env', env['MYSQL_ROOT_PASSWORD']), ('running db environment', live_env['MYSQL_ROOT_PASSWORD'])]
old = ROOT / 'backups/credentials-before-hardening.env'
if old.exists():
    sources.append(('private credential backup', read_env(old).get('MYSQL_ROOT_PASSWORD', '')))
seen = set()
for name, password in sources:
    if password in seen or not password:
        continue
    seen.add(password)
    # Password sent via stdin to the container shell, never as an argv/log value.
    quoted = "'" + password.replace("'", "'\"'\"'") + "'"
    script = ('export MYSQL_PWD=' + quoted + '\nexec mysql --no-defaults --protocol=socket -uroot --batch --skip-column-names -e "SELECT CURRENT_USER();"\n').encode()
    result = run('compose', 'exec', '-T', 'db', 'sh', '-s', input=script)
    report['attempts'].append({'credential_source': name, 'authenticated': result.returncode == 0,
                               'error_code': '1045' if b'1045' in result.stderr else ('none' if result.returncode == 0 else 'other'),
                               'current_user': result.stdout.decode().strip() if result.returncode == 0 else None})

sql = b'''set -eu
export MYSQL_PWD="$MYSQL_PASSWORD"
mysql --no-defaults --protocol=socket -u"$MYSQL_USER" -D"$MYSQL_DATABASE" --batch --skip-column-names <<'PORTFOLIO_SQL'
SELECT VERSION(), CURRENT_USER(), @@datadir;
SHOW GRANTS FOR CURRENT_USER();
SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME;
SHOW GLOBAL VARIABLES WHERE Variable_name IN ('general_log','log_raw','log_bin','slow_query_log','read_only');
PORTFOLIO_SQL
'''
result = run('compose', 'exec', '-T', 'db', 'sh', '-s', input=sql)
if result.returncode:
    raise SystemExit('Application account diagnosis failed; no database changed.')
report['app_account_database_metadata'] = result.stdout.decode().splitlines()
php = b'''<?php
require '/var/www/html/wp-load.php';
$items = [];
foreach (get_users(['role' => 'administrator']) as $user) {
    $items[] = ['id' => $user->ID, 'login' => $user->user_login, 'role' => 'administrator'];
}
echo json_encode($items, JSON_UNESCAPED_UNICODE);
'''
result = run('compose', 'exec', '-T', 'wordpress', 'php', input=php)
report['wordpress_administrator_accounts'] = json.loads(result.stdout) if result.returncode == 0 else []
(ROOT / 'evidence/root-diagnosis.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2, ensure_ascii=False))
