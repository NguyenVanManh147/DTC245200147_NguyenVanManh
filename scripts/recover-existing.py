"""Recover only configuration metadata and credentials; never overwrite .env or volumes."""
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

def docker(*args, input=None):
    return subprocess.run(["docker", *args], input=input, capture_output=True, check=True).stdout

def env_of(name):
    item = json.loads(docker("inspect", name))[0]
    return dict(v.split("=", 1) for v in item["Config"]["Env"])

def quoted(value):
    if "'" in value or "\n" in value or "\r" in value:
        raise ValueError("Credential needs manual .env quoting; no files written")
    return "'" + value + "'"

if (ROOT / ".env").exists():
    raise SystemExit(".env already exists; recovery did not overwrite it")
db = env_of("portfolio-manh-db-1")
gf = env_of("portfolio-manh-grafana-1")
settings = {
    "COMPOSE_PROJECT_NAME": "portfolio-manh", "WEB_PORT": "8080",
    "PMA_PORT": "8081", "GRAFANA_PORT": "3000", "PROMETHEUS_PORT": "9090",
    "MYSQL_DATABASE": db["MYSQL_DATABASE"], "MYSQL_USER": db["MYSQL_USER"],
    "MYSQL_PASSWORD": db["MYSQL_PASSWORD"], "MYSQL_ROOT_PASSWORD": db["MYSQL_ROOT_PASSWORD"],
    "GRAFANA_ADMIN_USER": gf["GF_SECURITY_ADMIN_USER"],
    "GRAFANA_ADMIN_PASSWORD": gf["GF_SECURITY_ADMIN_PASSWORD"],
}
for key, name in {
    "WORDPRESS_IMAGE": "portfolio-manh-wordpress-1", "MYSQL_IMAGE": "portfolio-manh-db-1",
    "NGINX_IMAGE": "portfolio-manh-nginx-1", "GRAFANA_IMAGE": "portfolio-manh-grafana-1",
    "PROMETHEUS_IMAGE": "portfolio-manh-prometheus-1", "BLACKBOX_IMAGE": "portfolio-manh-blackbox-1",
    "LOKI_IMAGE": "portfolio-manh-loki-1", "PHPMYADMIN_IMAGE": "portfolio-manh-phpmyadmin-1",
}.items():
    item = json.loads(docker("inspect", name))[0]
    img = json.loads(docker("image", "inspect", item["Image"]))[0]
    settings[key] = img["RepoDigests"][0]
(ROOT / "backups").mkdir(exist_ok=True)
dump = docker("exec", "-i", "portfolio-manh-db-1", "sh", "-s", input=b'''set -eu
export MYSQL_PWD="$MYSQL_PASSWORD"
exec mysqldump -u"$MYSQL_USER" --single-transaction --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"
''')
backup_path = ROOT / "backups" / "before-changes.sql"
if backup_path.exists():
    raise SystemExit("Original backup already exists; recovery did not overwrite it or .env")
backup_path.write_bytes(dump)
(ROOT / ".env").write_text("\n".join(f"{k}={quoted(v)}" for k, v in settings.items()) + "\n", encoding="utf-8")
print("Recovered .env (ignored by Git), locked existing image digests, and backed up application database. No secrets printed.")
