"""Real integration test in disposable Docker resources; never deletes live volumes."""
from datetime import datetime, timezone
import hashlib
import html as html_module
import http.cookiejar
import importlib.util
import json
from pathlib import Path
import secrets
import re
import socket
import subprocess
import sys
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootstrap', ROOT / 'scripts/bootstrap-wordpress.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def php(site, code):
    output = site.compose('exec', '-T', '--user', 'www-data', 'wordpress', 'php',
                          payload=('<?php define("WP_INSTALLING", true); '
                                   'require "/var/www/html/wp-load.php"; ' + code).encode())
    return json.loads(output)


def snapshot(site):
    return php(site, '''
global $wpdb;
$result = [];
foreach (['posts', 'postmeta', 'users'] as $table) {
    $rows = $wpdb->get_results("SELECT * FROM " . $wpdb->$table . " ORDER BY 1", ARRAY_A);
    $result[$table] = hash('sha256', serialize($rows));
}
foreach (['home','siteurl','show_on_front','page_on_front','stylesheet','template',
          'portfolio_bootstrap_state','wp_page_for_privacy_policy'] as $key) {
    $result['options'][$key] = get_option($key);
}
$directory = new RecursiveIteratorIterator(new RecursiveDirectoryIterator(
    ABSPATH . 'wp-content/uploads', FilesystemIterator::SKIP_DOTS));
foreach ($directory as $file) {
    if ($file->isFile()) { $result['media'][$file->getPathname()] = hash_file('sha256', $file->getPathname()); }
}
ksort($result['media']);
echo json_encode($result);
''')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return str(sock.getsockname()[1])


def main():
    checks = []
    def check(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})
        print(('PASS ' if condition else 'FAIL ') + name, flush=True)
        if not condition:
            raise RuntimeError('Integration assertion failed: ' + name)
    project = 'portfolio-bootstrap-check-' + uuid.uuid4().hex[:12]
    env_path = ROOT / 'secrets' / (project + '.env')
    env_path.parent.mkdir(exist_ok=True)
    template = (ROOT / '.env.example').read_text(encoding='utf-8-sig')
    lines = []
    for line in template.splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            if value.startswith('CHANGE_ME_'):
                value = secrets.token_hex(24)
            if key == 'COMPOSE_PROJECT_NAME':
                value = project
            if key.endswith('_PORT'):
                value = free_port()
            if key == 'WORDPRESS_ADMIN_USER':
                value = 'portfolio_test_admin'
            if key == 'WORDPRESS_ADMIN_PASSWORD':
                # Exercise an old env with a chosen username but no WP credential.
                continue
            line = key + '=' + value
        lines.append(line)
    env_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    site = bootstrap.Bootstrap(env_path, project)
    live = bootstrap.Bootstrap(ROOT / '.env')
    evidence = {'checked_at': datetime.now(timezone.utc).isoformat(), 'project': project,
                'checks': checks, 'fresh_install_verified': False, 'cleanup_verified': False}
    try:
        # Never attach any live volume, even if a Compose edit introduces an explicit name.
        config = json.loads(site.compose('config', '--format', 'json'))
        check('Temporary volumes belong exclusively to test project',
              all(v.get('name', '').startswith(project + '_') and not v.get('external')
                  for v in config['volumes'].values()))
        live_before = snapshot(live)
        live_env_hash = hashlib.sha256((ROOT / '.env').read_bytes()).hexdigest()
        site.compose('up', '-d', '--wait', '--wait-timeout', '240', 'db', 'wordpress')
        php(site, '''global $wpdb;
            $wpdb->query('CREATE TABLE bootstrap_sentinel (id INT PRIMARY KEY)');
            $wpdb->query('INSERT INTO bootstrap_sentinel VALUES (147)');
            echo json_encode(true);''')
        try:
            site.run(application_only=True)
            raise AssertionError('Nonempty DB was accepted')
        except RuntimeError as error:
            check('Nonempty database is refused before installation', 'Database không trống' in str(error))
        tables = php(site, '''global $wpdb; echo json_encode([
            'tables' => $wpdb->get_col('SHOW TABLES'),
            'sentinel' => $wpdb->get_var('SELECT id FROM bootstrap_sentinel')]);''')
        check('Refused database keeps original table and data',
              tables == {'tables': ['bootstrap_sentinel'], 'sentinel': '147'})
        php(site, "global $wpdb; $wpdb->query('DROP TABLE bootstrap_sentinel'); echo json_encode(true);")
        php(site, '''wp_mkdir_p(ABSPATH . 'wp-content/uploads');
            file_put_contents(ABSPATH . 'wp-content/uploads/bootstrap-sentinel.txt', 'preserve');
            echo json_encode(true);''')
        try:
            site.run(application_only=True)
            raise AssertionError('Existing uploads were accepted')
        except RuntimeError as error:
            check('Existing uploads are refused before installation', 'Uploads đã có dữ liệu' in str(error))
        preserved = php(site, '''global $wpdb; echo json_encode([
            'tables' => $wpdb->get_col('SHOW TABLES'),
            'file' => file_get_contents(ABSPATH . 'wp-content/uploads/bootstrap-sentinel.txt')]);''')
        check('Refused uploads keep file contents and database stays empty',
              preserved == {'tables': [], 'file': 'preserve'})
        php(site, "unlink(ABSPATH . 'wp-content/uploads/bootstrap-sentinel.txt'); echo json_encode(true);")
        result = site.run(application_only=True)
        check('Missing admin password is generated privately without replacing chosen username',
              site.env['WORDPRESS_ADMIN_USER'] == 'portfolio_test_admin'
              and len(site.env['WORDPRESS_ADMIN_PASSWORD']) == 48)
        payload = bootstrap.export_payload(result['site_url'])
        check('Fresh installation imports every exported post and image',
              result['status'] == 'created' and result['imported_posts'] == len(payload['posts'])
              and result['media_files'] == len(payload['media']))
        state = php(site, '''global $wpdb; echo json_encode([
            'front' => get_option('page_on_front'), 'show' => get_option('show_on_front'),
            'theme' => get_option('stylesheet'), 'locale' => get_option('WPLANG'),
            'languages' => get_available_languages(),
            'pages' => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type='page'"),
            'attachments' => (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type='attachment'"),
            'header' => get_block_template('twentytwentyfive//header', 'wp_template_part')->content,
            'metadata' => wp_get_attachment_metadata(9),
            'postmeta' => get_post_meta(5),
            'content' => $wpdb->get_results("SELECT ID,post_content,post_type FROM {$wpdb->posts}", ARRAY_A)
        ]);''')
        evidence['fresh_options'] = {key: state[key] for key in ('front', 'show', 'theme', 'locale')}
        print('Fresh options: ' + json.dumps(evidence['fresh_options'], ensure_ascii=False), flush=True)
        check('Static homepage and theme are set',
              int(state['front']) == 5 and state['show'] == 'page'
              and state['theme'] == 'twentytwentyfive')
        check('Locale matches installed language pack or explicit offline fallback',
              state['locale'] == ('vi' if 'vi' in state['languages'] else '')
              and result['locale'] == (state['locale'] or 'en_US'))
        check('All six pages and both media attachments exist', state['pages'] == 6 and state['attachments'] == 2)
        check('Header explicitly binds imported navigation', '"ref":8' in state['header'])
        check('Serialized attachment metadata keeps image dimensions and variants',
              state['metadata']['width'] == 1684 and len(state['metadata']['sizes']) == 6)
        restored = {int(p['ID']): p for p in state['content']}
        check('Exported block content is preserved with the new site URL',
              all(restored[p['import_id']]['post_content'] == p['post_content'].replace(
                  payload['source_url'], result['site_url']) for p in payload['posts']))
        url = result['site_url']
        response = urllib.request.urlopen(url + '/', timeout=30)
        html = response.read().decode()
        check('Fresh website responds HTTP 200 and displays portfolio',
              response.status == 200 and 'Nguyễn Văn Mạnh' in html and 'DTC245200147' in html)
        check('Public homepage renders all four navigation labels',
              all(label in html for label in ('Trang chủ', 'Kỹ năng', 'Dự án', 'Liên hệ')))
        for post_id in (17, 19, 21):
            response = urllib.request.urlopen(url + '/?page_id=' + str(post_id), timeout=30)
            # WordPress adds CSS classes to rendered blocks; compare visible text.
            def visible_text(content):
                return re.sub(r'\s+', ' ', html_module.unescape(re.sub(r'<[^>]*>', '', content))).strip()
            expected = visible_text(restored[post_id]['post_content'].split('\n')[1])[:60]
            rendered = visible_text(response.read().decode())
            check('Navigation page ' + str(post_id) + ' loads',
                  response.status == 200 and expected in rendered)
        for media in payload['media']:
            content = urllib.request.urlopen(url + '/wp-content/uploads/' + media['path'], timeout=30).read()
            check('Image checksum ' + media['path'], hashlib.sha256(content).hexdigest() == media['sha256'])
        cookies = http.cookiejar.CookieJar()
        browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
        browser.open(url + '/wp-login.php', timeout=30).read()
        fields = {'log': site.env['WORDPRESS_ADMIN_USER'], 'pwd': site.env['WORDPRESS_ADMIN_PASSWORD'],
                  'wp-submit': 'Log In', 'redirect_to': url + '/wp-admin/', 'testcookie': '1'}
        login = browser.open(url + '/wp-login.php', urllib.parse.urlencode(fields).encode(), timeout=30)
        check('Generated admin credential authenticates through real HTTP login',
              '/wp-admin/' in login.url and 'wp-admin-bar-my-account' in login.read().decode())
        before = snapshot(site)
        check('Second bootstrap run skips installed site', site.run(application_only=True)['status'] == 'skipped')
        check('Second run preserves posts, metadata, accounts, options and images', snapshot(site) == before)
        php(site, "update_option('portfolio_bootstrap_state', 'pending'); echo json_encode(true);")
        try:
            site.run(application_only=True)
            raise AssertionError('Interrupted install was accepted')
        except RuntimeError as error:
            check('Interrupted installation stops instead of silently importing again', 'bị gián đoạn' in str(error))
        php(site, "update_option('portfolio_bootstrap_state', 'complete'); echo json_encode(true);")
        check('Existing live site is skipped', live.run(application_only=True)['status'] == 'skipped')
        check('Live data and private env stay unchanged', snapshot(live) == live_before
              and hashlib.sha256((ROOT / '.env').read_bytes()).hexdigest() == live_env_hash)
        evidence['fresh_install_verified'] = True
    except Exception as error:
        print('Test incomplete: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
    finally:
        # Only resources from the unique project verified above may be removed.
        resolved = json.loads(site.compose('config', '--format', 'json'))
        if not project.startswith('portfolio-bootstrap-check-') or not all(
            v.get('name', '').startswith(project + '_') and not v.get('external')
            for v in resolved['volumes'].values()
        ):
            raise RuntimeError('Cleanup refused: resource ownership check failed.')
        site.compose('down', '--volumes', '--timeout', '30')
        remaining = subprocess.run(['docker', 'volume', 'ls', '--filter',
                                    'label=com.docker.compose.project=' + project, '-q'],
                                   capture_output=True, check=True).stdout.strip()
        evidence['cleanup_verified'] = not remaining
        (ROOT / 'evidence/bootstrap-validation.json').write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 0 if evidence['fresh_install_verified'] and evidence['cleanup_verified'] else 1


if __name__ == '__main__':
    sys.exit(main())
