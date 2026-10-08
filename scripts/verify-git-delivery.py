"""Record a timestamped Git delivery snapshot without exposing credentials.

The recorded revision is a snapshot before any later documentation commits.
--remote checks the actual remote branch; it never pushes or rewrites history.
"""
import argparse
import datetime
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
URL = 'https://github.com/NguyenVanManh147/DTC245200147_NguyenVanManh'


def git(*args):
    result = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Git verification failed: ' + args[0] + '; raw output omitted.')
    return result.stdout.decode().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote', action='store_true', help='Check the pushed main branch with git ls-remote')
    args = parser.parse_args()
    branch = git('branch', '--show-current')
    remote = git('remote', 'get-url', 'origin')
    if remote.removesuffix('.git') != URL:
        raise RuntimeError('Origin does not match the user-confirmed repository.')
    head = git('rev-parse', 'HEAD')
    lines = git('log', '--reverse', '--format=%H\t%s').splitlines()
    commits = [{'hash': line.split('\t', 1)[0], 'subject': line.split('\t', 1)[1]} for line in lines]
    remote_head = None
    if args.remote:
        advertised = git('ls-remote', 'origin', 'refs/heads/' + branch)
        remote_head = advertised.split()[0] if advertised else None
    data = {'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
            'username': 'NguyenVanManh147', 'branch': branch, 'commit_count': len(commits),
            'remote_url': remote, 'repository_url': URL, 'commits': commits,
            'verified_local_commit': head, 'verified_remote_commit': remote_head,
            'remote_checked': args.remote, 'pushed': bool(remote_head) and remote_head == head,
            'at_least_three_real_commits': len(commits) >= 3,
            'scope': 'Timestamped snapshot; later report/evidence commits may follow this revision.',
            'credentials_in_evidence': False}
    (ROOT / 'evidence/git-delivery.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Git snapshot:', len(commits), 'commits; branch', branch, '; remote matches:', data['pushed'])
    return 0 if len(commits) >= 3 and (not args.remote or data['pushed']) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('Git snapshot stopped:', str(error) if isinstance(error, RuntimeError) else type(error).__name__)
        raise SystemExit(1)
