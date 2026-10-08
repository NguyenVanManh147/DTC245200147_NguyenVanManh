"""Back up the app schema and prove restore in an isolated disposable tmpfs MySQL.

Never mounts, stops, initializes, or modifies the original database volume.
The SQL contains personal data/password hashes and stays under ignored backups/.
"""
import datetime
import hashlib
import json
import pathlib
import re
import secrets
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]

def docker(*args, input=None, timeout=120):
    result = subprocess.run(['docker', *args], cwd=ROOT, input=input, capture_output=True, timeout=timeout)
    if result.returncode:
        # Raw stderr could contain statements/data; do not echo it.
        raise RuntimeError('Docker operation failed: ' + args[0] + ' (no sensitive output printed)')
    return result.stdout

def inserts_digest(content):
    statements = [line for line in content.splitlines() if line.startswith(b'INSERT INTO ')]
    return hashlib.sha256(b'\n'.join(statements)).hexdigest(), len(statements)

def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
    target = ROOT / 'backups' / ('verified-' + stamp)
    target.mkdir(parents=True, exist_ok=False)
    config = json.loads(docker('compose', 'config', '--format', 'json'))
    schema = config['services']['db']['environment']['MYSQL_DATABASE']
    if not re.fullmatch(r'[A-Za-z0-9_]+', schema):
        raise RuntimeError('Schema name needs identifier escaping review')
    db_id = docker('compose', 'ps', '-q', 'db').decode().strip()
    original = json.loads(docker('inspect', db_id))[0]
    original_volume = next(v['Name'] for v in original['Mounts'] if v['Destination'] == '/var/lib/mysql')
    metadata_script = b'''set -eu
export MYSQL_PWD="$MYSQL_PASSWORD"
mysql --no-defaults --protocol=socket -u"$MYSQL_USER" -D"$MYSQL_DATABASE" --batch --skip-column-names <<'PORTFOLIO_SQL'
SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME;
SHOW GRANTS FOR CURRENT_USER();
PORTFOLIO_SQL
'''
    metadata = docker('compose', 'exec', '-T', 'db', 'sh', '-s', input=metadata_script).decode().splitlines()
    tables = [line.split('\t')[0] for line in metadata if '\t' in line and not line.startswith('GRANT ')]
    if not tables or any(not re.fullmatch(r'[A-Za-z0-9_]+', table) for table in tables):
        raise RuntimeError('Cannot verify source table inventory')
    if any(not line.endswith('\tInnoDB') for line in metadata if '\t' in line and not line.startswith('GRANT ')):
        raise RuntimeError('Non-InnoDB table detected; consistent backup requires reviewed locking plan')
    dump_script = b'''set -eu
export MYSQL_PWD="$MYSQL_PASSWORD"
exec mysqldump --no-defaults -u"$MYSQL_USER" --single-transaction --quick --hex-blob --order-by-primary --routines --events --triggers --no-tablespaces --set-gtid-purged=OFF --databases "$MYSQL_DATABASE"
'''
    dump = docker('compose', 'exec', '-T', 'db', 'sh', '-s', input=dump_script)
    if b'-- Dump completed on ' not in dump[-400:] or not dump or len(dump) < 100:
        raise RuntimeError('Backup does not contain a successful dump completion marker')
    sql_path = target / 'application.sql'
    with sql_path.open('xb') as output:
        output.write(dump)
    expected_signature, insert_count = inserts_digest(dump)
    manifest = {
        'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
        'database': schema, 'source_volume': original_volume,
        'schema_scope': 'application only; MySQL system accounts are not included',
        'backup_file': str(sql_path.relative_to(ROOT)), 'bytes': len(dump),
        'sha256': hashlib.sha256(dump).hexdigest(),
        'table_count': len(tables), 'tables': tables,
        'dump_exit_code': 0, 'dump_complete_marker': True,
        'source_insert_statement_count': insert_count,
        'data_signature_sha256': expected_signature,
        'restore_verified': False,
        'original_volume_modified': False,
    }
    print('App schema dump complete; checking restore in isolated tmpfs MySQL.', flush=True)
    env_file = target / 'restore-check.env'
    with env_file.open('x', encoding='utf-8') as output:
        output.write('MYSQL_ROOT_PASSWORD=' + secrets.token_hex(24) + '\n')
    container = 'portfolio-manh-backup-check-' + stamp.lower()
    started = False
    try:
        docker('run', '-d', '--rm', '--name', container, '--network', 'none', '--log-driver', 'none',
               '--memory', '1536m', '--tmpfs', '/var/lib/mysql:rw,size=1073741824',
               '--env-file', str(env_file), original['Image'], '--skip-log-bin')
        started = True
        inspection = json.loads(docker('inspect', container))[0]
        if any(m.get('Name') == original_volume for m in inspection['Mounts']):
            raise RuntimeError('Unsafe restore mount detected')
        manifest['restore_network'] = inspection['HostConfig']['NetworkMode']
        manifest['restore_storage'] = inspection['HostConfig']['Tmpfs']
        manifest['restore_published_ports'] = inspection['HostConfig']['PortBindings']
        for attempt in range(60):
            result = subprocess.run(['docker', 'exec', '-i', container, 'sh', '-s'],
                                    input=b'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"\nmysql --no-defaults -uroot -N -e "SELECT 1" >/dev/null 2>&1\n',
                                    capture_output=True, timeout=20)
            if result.returncode == 0:
                break
            if attempt % 10 == 0:
                print('Waiting for isolated restore server readiness...', flush=True)
            time.sleep(2)
        else:
            raise RuntimeError('Restore test MySQL did not become ready')
        # mysql reads the dump from stdin; no data or password appears in command arguments.
        docker('exec', '-i', container, 'sh', '-c', 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --no-defaults -uroot --binary-mode', input=dump)
        restored = docker('exec', '-i', container, 'sh', '-s', input=(
            'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"\n'
            f'mysqldump --no-defaults -uroot --quick --hex-blob --order-by-primary --no-tablespaces --set-gtid-purged=OFF --no-create-info --skip-triggers --skip-comments --databases {schema}\n'
        ).encode())
        actual_signature, actual_count = inserts_digest(restored)
        table_queries = f"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='{schema}' ORDER BY TABLE_NAME;\n"
        table_result = docker('exec', '-i', container, 'sh', '-c', 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --no-defaults -uroot -N -B', input=table_queries.encode()).decode().splitlines()
        check_queries = '\n'.join(f'CHECK TABLE `{schema}`.`{table}`;' for table in tables) + '\n'
        check_output = docker('exec', '-i', container, 'sh', '-c', 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --no-defaults -uroot -N -B', input=check_queries.encode()).decode().splitlines()
        all_checks_ok = len(check_output) == len(tables) and all(line.endswith('\tstatus\tOK') for line in check_output)
        manifest.update({
            'restored_insert_statement_count': actual_count,
            'restored_data_signature_sha256': actual_signature,
            'restored_tables_match': sorted(table_result) == sorted(tables),
            'check_table_all_ok': all_checks_ok,
            'restore_verified': actual_signature == expected_signature and actual_count == insert_count and sorted(table_result) == sorted(tables) and all_checks_ok,
        })
        if not manifest['restore_verified']:
            raise RuntimeError('Restore verification differs from source backup; no account change is allowed')
    finally:
        if started:
            docker('stop', '-t', '30', container)
        manifest['restore_test_container_removed'] = bool(started) and not bool(docker('ps', '-aq', '--filter', 'name=^/' + container + '$').strip())
        manifest_path = target / 'manifest.json'
        with manifest_path.open('x', encoding='utf-8') as output:
            json.dump(manifest, output, indent=2, ensure_ascii=False)
        # Publish only the manifest; SQL and temporary credentials remain ignored/private.
        (ROOT / 'evidence/backup-validation.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Backup verified: {len(tables)} tables, data signature matches, CHECK TABLE OK; original volume untouched.', flush=True)
    print('Private backup location: ' + str(target.relative_to(ROOT)), flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Backup validation did not complete: ' + str(exc), flush=True)
        raise SystemExit(1)
