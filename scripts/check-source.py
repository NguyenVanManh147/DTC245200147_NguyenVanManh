"""Check local file references and accidental credential publication without printing secrets."""
import datetime
import json
import pathlib
import re
import subprocess

root = pathlib.Path(__file__).resolve().parents[1]
compose = (root / 'compose.yaml').read_text(encoding='utf-8')
mounts = re.findall(r'^\s+- (\./[^:\n]+):', compose, re.M)
missing = [name for name in mounts if not (root / name).exists()]
if missing:
    raise SystemExit('Missing bind sources: ' + ', '.join(missing))
assert len(re.findall(r'<section class="page', (root / 'docs/report.html').read_text(encoding='utf-8'))) == 12
assert 'CHANGE_ME' in (root / '.env.example').read_text(encoding='utf-8')
settings = {}
for line in (root / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        key, value = line.split('=', 1)
        settings[key] = value.strip().strip("'\"")
credentials = {value.encode() for key, value in settings.items() if 'PASSWORD' in key and value}
for private_env in (root / 'backups').rglob('*.env'):
    for line in private_env.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and 'PASSWORD' in line.split('=', 1)[0]:
            value = line.split('=', 1)[1].strip().strip("'\"")
            if value:
                credentials.add(value.encode())
for private_json in (root / 'secrets').glob('*.json'):
    values = json.loads(private_json.read_text(encoding='utf-8'))
    credentials.update(value.encode() for key, value in values.items() if 'PASSWORD' in key and isinstance(value, str) and value)
candidates = set(subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root).decode('utf-8').strip('\0').split('\0'))
for candidate in candidates:
    if not candidate:
        continue
    path = root / candidate
    relative = path.relative_to(root)
    if any(part in ['backups', 'secrets', '__pycache__'] for part in relative.parts) or (path.name.startswith('.env') and path.name != '.env.example') or path.suffix in ['.sql', '.log']:
        raise SystemExit('Private file is a Git candidate: ' + candidate)
    if any(secret in path.read_bytes() for secret in credentials):
        raise SystemExit('Possible actual credential in Git candidate: ' + candidate)
(root / 'evidence/git-privacy.json').write_text(json.dumps({'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(), 'candidate_file_count': len(candidates), 'private_files_in_git_candidates': [], 'actual_secret_matches': [], 'checker_performed_commit_or_push': False}, indent=2) + '\n', encoding='utf-8')
status = subprocess.check_output(['docker', 'compose', 'ps', '-a', '--format', 'json'], cwd=root).decode()
items = json.loads(status) if status.lstrip().startswith('[') else [json.loads(line) for line in status.splitlines() if line.strip()]
summary = [{key: item.get(key) for key in ['Service', 'State', 'Health', 'ExitCode', 'Ports']} for item in items]
(root / 'evidence/compose-status.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
assert sum(item['State'] == 'running' for item in summary) == 12
assert next(item for item in summary if item['Service'] == 'loki-init')['ExitCode'] == 0
print('Source bind paths, 12 report sections, secret exclusion and 12 running services verified.')
