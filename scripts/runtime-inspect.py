"""Print selected non-secret runtime configuration before migration."""
import json
import re
import subprocess
import urllib.request

config = subprocess.check_output(['docker', 'exec', 'portfolio-manh-nginx-1', 'wget', '-qO-', 'http://loki:3100/config']).decode()
for section in ['schema_config', 'storage_config']:
    match = re.search(r'^' + section + r':\n.*?(?=^[a-z_]+:|\Z)', config, flags=re.M | re.S)
    if match:
        print(match.group(0)[:3500])
data = json.load(urllib.request.urlopen('http://localhost:9090/api/v1/targets'))
print('Existing jobs:', [(x['labels']['job'], x['health']) for x in data['data']['activeTargets']])
