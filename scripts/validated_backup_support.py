"""Verify full root dump in disposable tmpfs MySQL, never in the original volume."""
import hashlib
import json
import re
import secrets
import subprocess
import time
from private_support import docker, root_dump, sql

def data_digest(dump):
    return hashlib.sha256(b'\n'.join(line for line in dump.splitlines() if line.startswith(b'INSERT INTO '))).hexdigest()

def validate_full_restore(dump, original_password, schema, accounts_before, image, original_volume, private):
    name = 'portfolio-manh-full-restore-' + secrets.token_hex(6)
    env_file = private / 'temporary-restore.env'
    env_file.write_text('MYSQL_ROOT_PASSWORD=' + secrets.token_hex(24) + '\n', encoding='utf-8')
    report = {'passed': False, 'network_mode': 'none', 'storage': 'tmpfs', 'original_volume_mounted': False}
    started = False
    try:
        docker('run', '-d', '--rm', '--name', name, '--network', 'none', '--log-driver', 'none', '--memory', '1536m',
               '--tmpfs', '/var/lib/mysql:rw,size=1073741824', '--env-file', str(env_file), image, '--skip-log-bin')
        started = True
        test = json.loads(docker('inspect', name))[0]
        if any(m.get('Name') == original_volume for m in test['Mounts']):
            raise RuntimeError('Unsafe restore mount')
        for attempt in range(60):
            result = subprocess.run(['docker', 'exec', '-i', name, 'sh', '-s'], input=b'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"\nmysql --no-defaults -uroot -N -e "SELECT 1" >/dev/null 2>&1\n', capture_output=True, timeout=20)
            if result.returncode == 0:
                break
            if attempt % 10 == 0:
                print('Waiting for full-backup restore server...', flush=True)
            time.sleep(2)
        else:
            raise RuntimeError('Full-backup restore server did not become ready')
        docker('exec', '-i', name, 'sh', '-c', 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql --no-defaults -uroot --binary-mode', input=dump)
        accounts_restored = sql(original_password, 'SELECT User,Host,plugin,authentication_string,account_locked,password_expired FROM mysql.user ORDER BY User,Host;', container=name)
        report['account_metadata_matches'] = accounts_before == accounts_restored
        marker = '-- Current Database: `' + schema + '`'
        pieces = dump.decode('utf-8').split(marker, 1)
        if len(pieces) != 2:
            raise RuntimeError('Application schema missing from full backup')
        original_app = re.split(r'^-- Current Database: `', pieces[1], maxsplit=1, flags=re.M)[0].encode()
        restored_app = root_dump(original_password, '--quick --hex-blob --order-by-primary --no-tablespaces --set-gtid-purged=OFF --no-create-info --skip-triggers --skip-comments --databases ' + schema, container=name)
        report['app_data_signature_matches'] = data_digest(original_app) == data_digest(restored_app)
        tables = sql(original_password, f"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='{schema}' ORDER BY TABLE_NAME;", container=name).decode().splitlines()
        if not tables or any(not re.fullmatch(r'[A-Za-z0-9_]+', name) for name in tables):
            raise RuntimeError('Restored table inventory invalid')
        result = sql(original_password, '\n'.join(f'CHECK TABLE `{schema}`.`{table}`;' for table in tables), container=name).decode().splitlines()
        report['restored_app_table_count'] = len(tables)
        report['check_table_all_ok'] = len(result) == len(tables) and all(line.endswith('\tstatus\tOK') for line in result)
        report['passed'] = report['account_metadata_matches'] and report['app_data_signature_matches'] and report['check_table_all_ok']
    finally:
        if started:
            docker('stop', '-t', '30', name)
            report['temporary_container_removed'] = not bool(docker('ps', '-aq', '--filter', 'name=^/' + name + '$').strip())
        (private / 'full-restore-validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
