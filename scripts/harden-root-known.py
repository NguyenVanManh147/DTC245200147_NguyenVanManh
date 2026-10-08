"""Rotate root using a known credential after a verified full backup.

No skip-grant-tables, root guessing, privilege escalation inside MySQL, or volume reset.
All secrets are local ignored files/stdin; errors deliberately omit raw server SQL.
"""
import argparse
import datetime
import hashlib
import json
import re
import secrets
import subprocess
import time
from private_support import ROOT, docker, read_env, root_dump, shell_quote, sql
from validated_backup_support import validate_full_restore

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Perform the requested normal root rotation after backup validation')
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit('Use --apply only for authorized normal root rotation; this script never runs recovery mode.')
    local_path = ROOT / 'secrets/local-auth.json'
    if not local_path.exists():
        raise SystemExit('Known root credential missing. Use the local dialog; no account changed.')
    local = json.loads(local_path.read_text(encoding='utf-8'))
    password = local['MYSQL_ROOT_CURRENT_PASSWORD']
    settings = read_env()
    schema = settings['MYSQL_DATABASE']
    if not re.fullmatch(r'[A-Za-z0-9_]+', schema):
        raise RuntimeError('Schema identifier needs review')
    identity = sql(password, 'SELECT CURRENT_USER();').decode().strip()
    if not identity.startswith('root@'):
        raise RuntimeError('Authenticated account is not root; no account changed')
    print('Known root credential authenticated through local socket.', flush=True)
    flags = dict(line.split('\t', 1) for line in sql(password, "SHOW GLOBAL VARIABLES WHERE Variable_name IN ('general_log','log_raw','slow_query_log');").decode().splitlines())
    if any(flags.get(key) != 'OFF' for key in ['general_log', 'log_raw', 'slow_query_log']):
        raise RuntimeError('Logging policy needs review before password change; no account changed')
    roots = [line.split('\t') for line in sql(password, "SELECT Host,plugin,account_locked FROM mysql.user WHERE User='root' ORDER BY Host;").decode().splitlines()]
    if not roots or not any(host == 'localhost' for host, _, _ in roots):
        raise RuntimeError('Expected root@localhost is missing; no recovery attempted')
    if any(not re.fullmatch(r'[A-Za-z0-9.%:_-]+', host) for host, _, _ in roots):
        raise RuntimeError('Root host identifier needs manual review')
    baseline = json.loads((ROOT / 'evidence/backup-validation.json').read_text(encoding='utf-8'))
    backup_path = ROOT / baseline['backup_file']
    if not baseline['restore_verified'] or hashlib.sha256(backup_path.read_bytes()).hexdigest() != baseline['sha256']:
        raise RuntimeError('Application backup is not validated or its hash changed; no account changed')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
    private = ROOT / 'backups' / ('root-before-' + stamp)
    private.mkdir(exist_ok=False)
    (private / 'configured-before.env').write_bytes((ROOT / '.env').read_bytes())
    account_rows = sql(password, 'SELECT User,Host,plugin,authentication_string,account_locked,password_expired FROM mysql.user ORDER BY User,Host;')
    (private / 'accounts-before.private.tsv').write_bytes(account_rows)
    dump = root_dump(password, '--single-transaction --quick --hex-blob --order-by-primary --routines --events --triggers --flush-privileges --no-tablespaces --set-gtid-purged=OFF --all-databases')
    if b'-- Dump completed on ' not in dump[-400:] or b'-- Current Database: `mysql`' not in dump:
        raise RuntimeError('Full backup completion/system schema missing; no account changed')
    full_path = private / 'full-before-root.sql'
    full_path.write_bytes(dump)
    digest = hashlib.sha256(dump).hexdigest()
    if hashlib.sha256(full_path.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Saved full backup integrity check failed; no account changed')
    db_id = docker('compose', 'ps', '-q', 'db').decode().strip()
    instance = json.loads(docker('inspect', db_id))[0]
    source_volume = next(v['Name'] for v in instance['Mounts'] if v['Destination'] == '/var/lib/mysql')
    print('Full backup saved privately. Verifying full restore, app data and account metadata before ALTER USER.', flush=True)
    full_validation = validate_full_restore(dump, password, schema, account_rows, instance['Image'], source_volume, private)
    if not full_validation['passed']:
        raise RuntimeError('Full restore validation failed; no account changed')
    manifest = {'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
                'authenticated_account': identity, 'source_volume': source_volume,
                'backup_file': str(full_path.relative_to(ROOT)), 'bytes': len(dump), 'sha256': digest,
                'dump_exit_code': 0, 'full_restore_validation': full_validation,
                'root_accounts': [{'host': host, 'plugin_before': plugin, 'locked_before': locked} for host, plugin, locked in roots],
                'recovery_mode_used': False, 'root_changed': False}
    (private / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (ROOT / 'evidence/root-maintenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    new_password = secrets.token_hex(24)
    # Persist the new secret before changing the account so a host crash cannot lose it.
    state = ROOT / 'secrets/root-rotation-state.json'
    if state.exists():
        raise RuntimeError('Existing private rotation state needs review; no account changed')
    state.write_text(json.dumps({'MYSQL_ROOT_PASSWORD': new_password, 'backup_folder': str(private.relative_to(ROOT)), 'phase': 'backup-verified'}), encoding='utf-8')
    statements = 'SET SESSION sql_log_bin=0;\n' + '\n'.join(f"ALTER USER 'root'@'{host}' IDENTIFIED BY '{new_password}';" for host, _, _ in roots)
    manifest['account_changes_started'] = True
    (ROOT / 'evidence/root-maintenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    state.write_text(json.dumps({'MYSQL_ROOT_PASSWORD': new_password, 'backup_folder': str(private.relative_to(ROOT)), 'phase': 'account-changes-started'}), encoding='utf-8')
    sql(password, statements)
    if sql(new_password, 'SELECT CURRENT_USER();').decode().strip() != 'root@localhost':
        raise RuntimeError('New root socket login failed; preserve private rotation state for reconciliation')
    content = (ROOT / '.env').read_text(encoding='utf-8-sig')
    if not re.search(r'^MYSQL_ROOT_PASSWORD=', content, flags=re.M):
        raise RuntimeError('Cannot update .env safely; new secret remains in ignored rotation state')
    content = re.sub(r'^MYSQL_ROOT_PASSWORD=.*$', "MYSQL_ROOT_PASSWORD='" + new_password + "'", content, flags=re.M)
    pending = ROOT / '.env.root-next'
    pending.write_text(content, encoding='utf-8')
    pending.replace(ROOT / '.env')
    manifest['root_changed'] = True
    manifest['new_password_length'] = len(new_password)
    manifest['new_root_socket_login'] = True
    (private / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (ROOT / 'evidence/root-maintenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    state.write_text(json.dumps({'MYSQL_ROOT_PASSWORD': new_password, 'backup_folder': str(private.relative_to(ROOT)), 'phase': 'database-and-env-updated'}), encoding='utf-8')
    print('Root password changed and .env synchronized. Recreating only db to synchronize its environment.', flush=True)
    docker('compose', 'up', '-d', '--no-deps', 'db')
    for attempt in range(60):
        try:
            if sql(new_password, 'SELECT CURRENT_USER();').decode().strip() == 'root@localhost':
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        raise RuntimeError('Database readiness needs review; no volume reset attempted')
    live_id = docker('compose', 'ps', '-q', 'db').decode().strip()
    live = json.loads(docker('inspect', live_id))[0]
    live_values = dict(value.split('=', 1) for value in live['Config']['Env'])
    manifest['container_env_synchronized'] = live_values.get('MYSQL_ROOT_PASSWORD') == new_password
    manifest['same_data_volume'] = any(v.get('Name') == source_volume and v['Destination'] == '/var/lib/mysql' for v in live['Mounts'])
    if not manifest['container_env_synchronized'] or not manifest['same_data_volume']:
        raise RuntimeError('Container/volume verification failed; stop for review')
    (private / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (ROOT / 'evidence/root-maintenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Root rotation complete using normal authenticated SQL; no password logged, original data volume preserved.', flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Root maintenance stopped: ' + str(exc), flush=True)
        raise SystemExit(1)
