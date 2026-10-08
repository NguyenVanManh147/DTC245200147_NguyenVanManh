"""Install the exported portfolio into an empty database; preserve installed sites.

Uses Python's standard library and WordPress APIs in the existing Docker image.
Credentials travel through stdin, never command arguments or public artifacts.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {'wp': 'http://wordpress.org/export/1.2/',
      'content': 'http://purl.org/rss/1.0/modules/content/',
      'excerpt': 'http://wordpress.org/export/1.2/excerpt/'}


def read_env(path):
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('\"\'')
    return values


def export_payload(site_url):
    channel = ET.parse(ROOT / 'wordpress/portfolio-export.xml').getroot().find('channel')
    def value(node, field):
        return node.findtext(field, default='', namespaces=NS)
    posts = []
    for item in channel.findall('item'):
        post = {field: value(item, 'wp:' + field) for field in (
            'post_type', 'post_date', 'post_date_gmt', 'post_modified',
            'post_modified_gmt', 'post_name', 'post_parent', 'menu_order',
            'post_password', 'post_mime_type', 'comment_status', 'ping_status')}
        post.update(import_id=int(value(item, 'wp:post_id')),
                    post_title=value(item, 'title'), post_status=value(item, 'wp:status'),
                    post_content=value(item, 'content:encoded'),
                    post_excerpt=value(item, 'excerpt:encoded'), guid=value(item, 'guid'))
        post['meta'] = [{'key': value(m, 'wp:meta_key'), 'value': value(m, 'wp:meta_value')}
                        for m in item.findall('wp:postmeta', NS)]
        post['terms'] = [{'taxonomy': term.get('domain'), 'slug': term.get('nicename'),
                          'name': term.text or ''} for term in item.findall('category')]
        post['comments'] = []
        for comment in item.findall('wp:comment', NS):
            fields = ('comment_author', 'comment_author_email', 'comment_author_url',
                      'comment_author_IP', 'comment_date', 'comment_date_gmt',
                      'comment_content', 'comment_approved', 'comment_type',
                      'comment_parent', 'comment_id', 'comment_user_id')
            post['comments'].append({f: value(comment, 'wp:' + f) for f in fields})
        posts.append(post)
    if len({p['import_id'] for p in posts}) != len(posts):
        raise RuntimeError('Export has duplicate post IDs.')
    if not any(p['post_name'] == 'trang-chu' and p['post_type'] == 'page' for p in posts):
        raise RuntimeError('Export is missing Trang chủ.')
    media = []
    uploads = ROOT / 'wordpress/uploads'
    for path in sorted(uploads.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(uploads).as_posix()
        if path.is_symlink() or '..' in PurePosixPath(relative).parts:
            raise RuntimeError('Unsafe upload path.')
        if path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
            raise RuntimeError('Only portfolio image assets can be imported.')
        content = path.read_bytes()
        media.append({'path': relative, 'sha256': hashlib.sha256(content).hexdigest(),
                      'data': base64.b64encode(content).decode('ascii')})
    files = {m['path'] for m in media}
    for post in posts:
        for meta in post['meta']:
            if meta['key'] == '_wp_attached_file' and meta['value'] not in files:
                raise RuntimeError('An exported attachment has no local image.')
    return {'site_url': site_url.rstrip('/'), 'source_url': value(channel, 'wp:base_site_url'),
            'title': value(channel, 'title'), 'posts': posts, 'media': media}


class Bootstrap:
    def __init__(self, env_file, project=None):
        self.env_file = Path(env_file).resolve()
        self.env = read_env(self.env_file)
        self.project = project or self.env.get('COMPOSE_PROJECT_NAME', 'portfolio-manh')
        self.command = ['docker', 'compose', '--project-directory', str(ROOT),
                        '--env-file', str(self.env_file), '-p', self.project]

    def compose(self, *args, payload=None, timeout=300):
        # dotenv is the source of truth, independent of inherited shell variables.
        child_env = os.environ.copy()
        for key in self.env:
            child_env.pop(key, None)
        result = subprocess.run(self.command + list(args), cwd=ROOT, env=child_env,
                                input=payload, capture_output=True, timeout=timeout)
        if result.returncode:
            # Compose errors may echo env values. Do not log raw stderr/stdout.
            raise RuntimeError('Docker Compose failed (' + args[0] + '). '
                               'Check Docker Desktop, available ports and service health.')
        return result.stdout

    def php(self, helper, payload):
        output = self.compose('exec', '-T', '--user', 'www-data', 'wordpress', 'php', helper,
                              payload=json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        marker = b'PORTFOLIO_BOOTSTRAP_RESULT='
        line = next((line for line in output.splitlines() if line.startswith(marker)), None)
        if line is None:
            raise RuntimeError('WordPress did not return a bootstrap result.')
        result = json.loads(line[len(marker):])
        if result['status'] == 'error':
            raise RuntimeError(result['message'])
        return result

    def run(self, application_only=False):
        url = 'http://localhost:' + self.env.get('WEB_PORT', '8080')
        # Validate the export and images before starting an installation.
        payload = export_payload(url)
        self.compose('config', '--quiet')
        self.compose('up', '-d', '--wait', '--wait-timeout', '240', 'db', 'wordpress')
        helper = '/tmp/portfolio-bootstrap-' + uuid.uuid4().hex + '.php'
        self.compose('cp', str(ROOT / 'scripts/bootstrap-wordpress.php'), 'wordpress:' + helper)
        try:
            probe = self.php(helper, {'mode': 'probe'})
            if probe['status'] == 'installed':
                print('WordPress đã cài đặt; giữ nguyên nội dung, uploads và tài khoản.', flush=True)
                result = {'status': 'skipped', 'site_url': probe['site_url']}
            else:
                password = self.env.get('WORDPRESS_ADMIN_PASSWORD', '')
                if not password:
                    password = secrets.token_hex(24)
                    # Save privately before install, so a failed run cannot lose credentials.
                    with self.env_file.open('a', encoding='utf-8') as stream:
                        stream.write('\n')
                        for key, default in (
                            ('WORDPRESS_ADMIN_USER', 'vanmanh_admin'),
                            ('WORDPRESS_ADMIN_EMAIL', 'dtc245200147@ictu.edu.vn'),
                        ):
                            if key not in self.env:
                                stream.write(key + '=' + default + '\n')
                        stream.write('WORDPRESS_ADMIN_PASSWORD=' + password + '\n')
                    self.env = read_env(self.env_file)
                if password.startswith('CHANGE_ME_'):
                    raise RuntimeError('Replace the WordPress password placeholder in the private .env file.')
                payload.update(mode='install', admin_user=self.env.get('WORDPRESS_ADMIN_USER', 'vanmanh_admin'),
                               admin_email=self.env.get('WORDPRESS_ADMIN_EMAIL', 'dtc245200147@ictu.edu.vn'),
                               admin_password=password)
                result = self.php(helper, payload)
                print('Đã cài WordPress, nhập nội dung/ảnh, đặt Trang chủ và navigation.', flush=True)
                print('Tài khoản: WORDPRESS_ADMIN_USER / WORDPRESS_ADMIN_PASSWORD trong file .env riêng tư.', flush=True)
                if result.get('locale') != 'vi':
                    print('Chưa tải được gói tiếng Việt; giao diện quản trị dùng tiếng Anh. '
                          'Có thể chọn tiếng Việt trong Settings khi truy cập được WordPress.org.', flush=True)
        finally:
            self.compose('exec', '-T', 'wordpress', 'php', '-r',
                         'unlink($argv[1]);', helper)
        services = ['db', 'wordpress', 'nginx'] if application_only else []
        self.compose('up', '-d', '--wait', '--wait-timeout', '240', *services)
        self.compose('exec', '-T', 'nginx', 'nginx', '-s', 'reload')
        print('Website: ' + result['site_url'] + '/', flush=True)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--project-name', help='Use separate Docker resources for a fresh installation.')
    parser.add_argument('--application-only', action='store_true', help='Start only db, WordPress and Nginx.')
    args = parser.parse_args()
    try:
        if not args.env_file.exists():
            raise RuntimeError('Create .env first using scripts/Initialize-Env.ps1.')
        Bootstrap(args.env_file, args.project_name).run(args.application_only)
        return 0
    except (RuntimeError, OSError, ValueError, ET.ParseError, subprocess.TimeoutExpired) as error:
        print('Khởi tạo chưa hoàn tất: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
