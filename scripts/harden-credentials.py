"""Rotate short app/Grafana credentials; persist secrets before account changes.

Requires working root authentication. Reconciles interrupted changes and preserves
the WordPress administrator password and original database volume.
"""
import base64
import json
import datetime
import re
import secrets
import urllib.error
import urllib.request
from private_support import ROOT, docker, read_env, sql

STATE = ROOT / 'secrets/application-credential-rotation-state.json'

def save(state):
    pending = STATE.with_suffix('.pending.json')
    pending.write_text(json.dumps(state, indent=2), encoding='utf-8')
    pending.replace(STATE)

def update_env(key, value):
    path = ROOT / '.env'
    content = path.read_text(encoding='utf-8-sig')
    if len(re.findall('^' + key + '=', content, re.M)) != 1:
        raise RuntimeError('Expected exactly one environment entry: ' + key)
    content = re.sub('^' + key + '=.*$', key + "='" + value + "'", content, flags=re.M)
    pending = ROOT / '.env.credentials-next'
    pending.write_text(content, encoding='utf-8')
    pending.replace(path)

def grafana(settings, password, endpoint='/api/user', body=None):
    auth = settings.get('GRAFANA_ADMIN_USER', 'admin') + ':' + password
    request = urllib.request.Request(
        'http://localhost:' + settings.get('GRAFANA_PORT', '3000') + endpoint,
        data=json.dumps(body).encode() if body is not None else None,
        method='PUT' if body is not None else 'GET',
        headers={'Authorization': 'Basic ' + base64.b64encode(auth.encode()).decode(),
                 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        if error.code == 401:
            return None
        raise RuntimeError('Grafana request failed; sensitive response omitted.') from None


def main():
    settings = read_env()
    root_password = settings['MYSQL_ROOT_PASSWORD']
    if sql(root_password, 'SELECT CURRENT_USER();').decode().strip() != 'root@localhost':
        raise RuntimeError('Known configured root authentication required.')
    flags = sql(root_password, "SHOW GLOBAL VARIABLES WHERE Variable_name IN ('general_log','slow_query_log','log_raw');").decode().splitlines()
    if any(not line.endswith('\tOFF') for line in flags):
        raise RuntimeError('Database query logging must be disabled before rotation.')
    db_id = docker('compose', 'ps', '-q', 'db').decode().strip()
    instance = json.loads(docker('inspect', db_id))[0]
    volume = next(m['Name'] for m in instance['Mounts'] if m['Destination'] == '/var/lib/mysql')
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding='utf-8'))
        if state['source_volume'] != volume:
            raise RuntimeError('Rotation state belongs to another database volume.')
    else:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = ROOT / 'backups' / ('application-credentials-before-' + stamp)
        backup.mkdir(exist_ok=False)
        (backup / 'configured-before.env').write_bytes((ROOT / '.env').read_bytes())
        state = {'source_volume': volume, 'completed': [], 'credentials': {}}
        for key in ('MYSQL_PASSWORD', 'GRAFANA_ADMIN_PASSWORD'):
            state['credentials'][key] = {'before': settings[key],
                'after': secrets.token_hex(24) if len(settings[key]) < 20 else settings[key]}
        STATE.parent.mkdir(exist_ok=True)
        save(state)

    db_password = state['credentials']['MYSQL_PASSWORD']['after']
    if not re.fullmatch(r'[A-Za-z0-9]+', db_password):
        raise RuntimeError('Rotation password requires reviewed SQL escaping.')
    user = settings['MYSQL_USER']
    if not re.fullmatch(r'[A-Za-z0-9_]+', user):
        raise RuntimeError('Database username requires reviewed SQL escaping.')
    hosts = sql(root_password, "SELECT Host FROM mysql.user WHERE User='" + user + "' ORDER BY Host;").decode().splitlines()
    if not hosts or any(not re.fullmatch(r'[A-Za-z0-9.%:_-]+', host) for host in hosts):
        raise RuntimeError('Unexpected application account hosts.')
    if 'MYSQL_PASSWORD' not in state['completed']:
        statements = 'SET SESSION sql_log_bin=0;\n' + '\n'.join(
            f"ALTER USER '{user}'@'{host}' IDENTIFIED BY '{db_password}';" for host in hosts)
        sql(root_password, statements)
        update_env('MYSQL_PASSWORD', db_password)
        state['completed'].append('MYSQL_PASSWORD')
        save(state)
        print('Application database password updated; secret retained privately.', flush=True)

    entry = state['credentials']['GRAFANA_ADMIN_PASSWORD']
    if 'GRAFANA_ADMIN_PASSWORD' not in state['completed']:
        if grafana(settings, entry['after']) is None:
            if grafana(settings, entry['before']) is None:
                raise RuntimeError('Neither saved Grafana credential authenticates.')
            grafana(settings, entry['before'], '/api/user/password', {
                'oldPassword': entry['before'], 'newPassword': entry['after'], 'confirmNew': entry['after']})
        if grafana(settings, entry['after']) is None:
            raise RuntimeError('New Grafana credential failed authentication.')
        update_env('GRAFANA_ADMIN_PASSWORD', entry['after'])
        state['completed'].append('GRAFANA_ADMIN_PASSWORD')
        save(state)
        print('Grafana password updated and password login verified.', flush=True)

    local_path = ROOT / 'secrets/local-auth.json'
    local = json.loads(local_path.read_text(encoding='utf-8')) if local_path.exists() else {}
    local['MYSQL_ROOT_CURRENT_PASSWORD'] = root_password
    pending = local_path.with_suffix('.pending.json')
    pending.write_text(json.dumps(local, indent=2), encoding='utf-8')
    pending.replace(local_path)
    docker('compose', 'up', '-d', '--wait', '--wait-timeout', '180',
           'db', 'wordpress', 'mysql-exporter', 'grafana', timeout=240)
    docker('compose', 'exec', '-T', 'nginx', 'nginx', '-s', 'reload')
    live_id = docker('compose', 'ps', '-q', 'db').decode().strip()
    live = json.loads(docker('inspect', live_id))[0]
    if not any(m.get('Name') == volume and m['Destination'] == '/var/lib/mysql' for m in live['Mounts']):
        raise RuntimeError('Database volume identity changed unexpectedly.')
    if sql(root_password, 'SELECT CURRENT_USER();').decode().strip() != 'root@localhost':
        raise RuntimeError('Root authentication failed after service recreation.')
    state['services_synchronized'] = True
    save(state)
    report = {'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
              'password_lengths': {k: len(read_env()[k]) for k in
                  ('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'GRAFANA_ADMIN_PASSWORD')},
              'minimum_length': 20, 'same_data_volume': True,
              'grafana_password_login_verified': grafana(read_env(), entry['after']) is not None,
              'root_password_login_verified': True, 'services_synchronized': True,
              'wordpress_admin_password_changed': False, 'credentials_in_evidence': False}
    (ROOT / 'evidence/credential-hardening.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Credential rotation complete; services synchronized and original database volume retained.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Credential rotation stopped:', type(error).__name__,
              str(error) if isinstance(error, RuntimeError) else '(sensitive output omitted)', flush=True)
        raise SystemExit(1)
