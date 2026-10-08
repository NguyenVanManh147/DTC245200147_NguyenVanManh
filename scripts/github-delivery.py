"""Inspect GitHub access or create the requested portfolio repository.

Uses the configured Git credential helper. Tokens never enter arguments,
console output, evidence, or repository files. Publishing is a separate git push.
"""
import argparse
import datetime
import json
import os
import pathlib
import subprocess
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OWNER = 'NguyenVanManh147'
REPO = 'DTC245200147_NguyenVanManh'


def credential():
    environment = os.environ.copy()
    environment.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    result = subprocess.run(['git', 'credential', 'fill'], cwd=ROOT,
                            input=b'protocol=https\nhost=github.com\n\n',
                            capture_output=True, env=environment, timeout=30)
    if result.returncode:
        return None
    fields = dict(line.split('=', 1) for line in result.stdout.decode().splitlines() if '=' in line)
    return fields.get('password')


def request(path, token=None, payload=None):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'portfolio-submission-check',
               'X-GitHub-Api-Version': '2022-11-28'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None if payload is None else json.dumps(payload).encode()
    if data is not None:
        headers['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request('https://api.github.com' + path,
                                                          data=data, headers=headers), timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create', action='store_true', help='Create the authorized public portfolio repository if absent')
    args = parser.parse_args()
    token = credential()
    status, profile = request('/users/' + OWNER)
    auth_status, user = request('/user', token) if token else (0, {})
    repo_status, repository = request('/repos/' + OWNER + '/' + REPO, token)
    observation = {'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
                   'profile_url': 'https://github.com/' + OWNER, 'username': OWNER,
                   'profile_verified': status == 200 and profile.get('login', '').lower() == OWNER.lower(),
                   'credential_available': bool(token), 'authenticated': auth_status == 200,
                   'authenticated_login': user.get('login'), 'repository_exists': repo_status == 200,
                   'repository_url': repository.get('html_url'),
                   'repository_write_access': bool(repository.get('permissions', {}).get('push')),
                   'tokens_saved': False}
    if args.create:
        if not token or auth_status != 200 or user.get('login', '').lower() != OWNER.lower():
            raise RuntimeError('GitHub authentication for the requested owner is required; no repository created.')
        if repo_status == 404:
            code, repository = request('/user/repos', token, {
                'name': REPO, 'description': 'Portfolio Nguyễn Văn Mạnh — DTC245200147: WordPress, Docker Compose, monitoring và logging.',
                'private': False, 'auto_init': False})
            if code != 201:
                raise RuntimeError('GitHub repository creation returned HTTP ' + str(code) + '; no sensitive output printed.')
            observation.update(repository_exists=True, repository_url=repository['html_url'],
                               repository_write_access=True, repository_created=True)
        elif repo_status != 200 or not observation['repository_write_access']:
            raise RuntimeError('Requested repository cannot be safely created or written; existing repository was not modified.')
    (ROOT / 'evidence/github-access.json').write_text(json.dumps(observation, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(observation, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('GitHub check stopped: ' + (str(error) if isinstance(error, RuntimeError) else type(error).__name__))
        raise SystemExit(1)
