"""Replace fresh-install defaults with verified image digests; never copies credentials."""
import json
import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[1]
values = {}
for line in (root / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        key, value = line.split('=', 1)
        if key.endswith('_IMAGE'):
            values[key] = value.strip().strip("'\"")
for filename in ['compose.yaml', '.env.example']:
    text = (root / filename).read_text(encoding='utf-8')
    for key, value in values.items():
        if not re.fullmatch(r'[a-zA-Z0-9./_-]+@sha256:[0-9a-f]{64}', value):
            raise ValueError('Expected immutable Docker image digest')
        if filename == 'compose.yaml':
            text = re.sub(r'\$\{' + key + r':-[^}]+\}', '${' + key + ':-' + value + '}', text)
        else:
            text = re.sub(r'^' + key + r'=.*$', key + '=' + value, text, flags=re.M)
    (root / filename).write_text(text, encoding='utf-8')
(root / 'monitoring/images.lock.json').write_text(json.dumps(values, indent=2) + '\n', encoding='utf-8')
print('Locked image defaults to the images actually running; credentials were excluded.')
