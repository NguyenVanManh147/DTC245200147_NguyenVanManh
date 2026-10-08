"""Private credential helpers: no secret values in argv, exceptions, or public evidence."""
import pathlib
import re
import secrets
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

def read_env():
    values = {}
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            values[key] = value
    return values

def docker(*args, input=None, timeout=180):
    output = subprocess.run(['docker', *args], cwd=ROOT, input=input, capture_output=True, timeout=timeout)
    if output.returncode:
        error_code = re.search(rb'ERROR (\d+) \(', output.stderr)
        if error_code:
            raise RuntimeError('MySQL returned error ' + error_code.group(1).decode() + '; sensitive output omitted.')
        raise RuntimeError('Docker/MySQL operation failed; no sensitive output printed.')
    return output.stdout

def shell_quote(value):
    if '\x00' in value:
        raise ValueError('Invalid credential encoding')
    return "'" + value.replace("'", "'\"'\"'") + "'"

def sql(password, statement, container=None):
    delimiter = 'PRIVATE_SQL_' + secrets.token_hex(12)
    script = 'export MYSQL_PWD=' + shell_quote(password) + '\nmysql --no-defaults --protocol=socket -uroot --batch --skip-column-names --binary-mode <<\'' + delimiter + "'\n" + statement + '\n' + delimiter + '\n'
    args = ['exec', '-i', container, 'sh', '-s'] if container else ['compose', 'exec', '-T', 'db', 'sh', '-s']
    return docker(*args, input=script.encode())

def root_dump(password, options, container=None):
    script = 'export MYSQL_PWD=' + shell_quote(password) + '\nexec mysqldump --no-defaults --protocol=socket -uroot ' + options + '\n'
    args = ['exec', '-i', container, 'sh', '-s'] if container else ['compose', 'exec', '-T', 'db', 'sh', '-s']
    return docker(*args, input=script.encode())
