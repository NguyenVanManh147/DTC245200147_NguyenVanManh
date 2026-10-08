"""Non-destructive database backup and WordPress content export from existing containers."""
import pathlib
import subprocess
import datetime

root = pathlib.Path(__file__).resolve().parents[1]
(root / "backups").mkdir(exist_ok=True)
(root / "wordpress").mkdir(exist_ok=True)
script = b'''set -eu
export MYSQL_PWD="$MYSQL_PASSWORD"
exec mysqldump -u"$MYSQL_USER" --single-transaction --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"
'''
r = subprocess.run(["docker", "exec", "-i", "portfolio-manh-db-1", "sh", "-s"], input=script, capture_output=True)
if r.returncode:
    print(r.stderr.decode(errors="replace"))
    raise SystemExit(r.returncode)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup_path = root / "backups" / "before-changes.sql"
if backup_path.exists():
    backup_path = root / 'backups' / f'database-{stamp}.sql'
with backup_path.open('xb') as output:
    output.write(r.stdout)
php = b'''<?php
require '/var/www/html/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/export.php';
export_wp(['content' => 'all']);
'''
r = subprocess.run(["docker", "exec", "-i", "portfolio-manh-wordpress-1", "php"], input=php, capture_output=True, check=True)
content_path = root / 'wordpress' / 'portfolio-export.xml'
if content_path.exists():
    content_path = root / 'backups' / f'portfolio-export-{stamp}.xml'
with content_path.open('xb') as output:
    output.write(r.stdout)
print("Backed up database privately and exported existing WordPress content (WXR). No database changed.")
