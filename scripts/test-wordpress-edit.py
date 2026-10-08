"""Exercise password login and page editing through WordPress HTTP endpoints.

Creates one uniquely named draft, edits and publishes it using the logged-in
administrator's REST nonce, verifies it anonymously, and removes only that
test page and its revisions. Credentials, nonce and cookies stay in memory.

Usage: python scripts/test-wordpress-edit.py [--capture]
Requires a running Compose stack. --capture uses the existing private
Playwright installation and Edge to capture real admin/public browser views.
The public, sanitized result is evidence/wordpress-edit.json.

WordPress documents the authentication used here at:
https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/
https://developer.wordpress.org/reference/functions/wp_ajax_rest_nonce/
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import html
import http.cookiejar
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from private_support import ROOT, docker, read_env


EVIDENCE = ROOT / 'evidence'
RESULT_PREFIX = 'PORTFOLIO_EDIT_RESULT='
PERSONAL_OPTIONS = [
    'home', 'siteurl', 'blogname', 'blogdescription', 'show_on_front',
    'page_on_front', 'page_for_posts', 'stylesheet', 'template',
    'wp_page_for_privacy_policy', 'WPLANG', 'timezone_string',
    'portfolio_bootstrap_state', 'sidebars_widgets', 'nav_menu_options',
    'active_plugins', 'permalink_structure',
]


def timestamp():
    return datetime.now(timezone(timedelta(hours=7))).isoformat(timespec='seconds')


def php(code):
    """Use PHP only for read-only snapshots and tightly scoped cleanup."""
    source = ('<?php define("WP_INSTALLING", true); '
              'require "/var/www/html/wp-load.php"; global $wpdb; '
              '$result = (function () use ($wpdb) { ' + code + ' })(); '
              'echo "\n' + RESULT_PREFIX + '" . json_encode($result, '
              'JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";')
    output = docker('compose', 'exec', '-T', '--user', 'www-data',
                    'wordpress', 'php', input=source.encode(), timeout=90)
    lines = output.decode('utf-8', errors='replace').splitlines()
    for line in reversed(lines):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX):])
    raise RuntimeError('WordPress CLI result was not available; raw output omitted.')


def snapshot():
    # Transients/cron and user login sessions can legitimately change. Preserve
    # all posts/postmeta and the site's personal content/theme/navigation options.
    option_json = json.dumps(PERSONAL_OPTIONS)
    code = '''
    $posts = $wpdb->get_results("SELECT * FROM {$wpdb->posts} ORDER BY ID", ARRAY_A);
    $meta = $wpdb->get_results("SELECT * FROM {$wpdb->postmeta} ORDER BY meta_id", ARRAY_A);
    $names = json_decode(%s, true);
    foreach ($wpdb->get_col("SELECT option_name FROM {$wpdb->options} ORDER BY option_name") as $name) {
        if (strpos($name, 'theme_mods_') === 0 || strpos($name, 'widget_') === 0) {
            $names[] = $name;
        }
    }
    $names = array_values(array_unique($names));
    sort($names);
    $options = [];
    foreach ($names as $name) { $options[$name] = get_option($name, null); }
    if ($wpdb->last_error) { throw new RuntimeException('Snapshot database read failed'); }
    return [
        'post_count' => count($posts),
        'postmeta_count' => count($meta),
        'post_ids' => array_map('intval', array_column($posts, 'ID')),
        'posts_sha256' => hash('sha256', serialize($posts)),
        'postmeta_sha256' => hash('sha256', serialize($meta)),
        'personal_option_names' => $names,
        'personal_options_sha256' => hash('sha256', serialize($options)),
    ];
    ''' % php_string(option_json)
    return php(code)


def php_string(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def cleanup(post_id, slug, baseline_ids):
    """Also locate the exact unique slug if an HTTP response was interrupted."""
    code = '''
    $known_id = %d;
    $slug = %s;
    $baseline_ids = json_decode(%s, true);
    $ids = array_map('intval', $wpdb->get_col($wpdb->prepare(
        "SELECT ID FROM {$wpdb->posts} WHERE post_type='page' AND post_name=%%s", $slug)));
    if ($known_id && get_post($known_id) && !in_array($known_id, $ids, true)) {
        throw new RuntimeException('Test page identity changed; refusing deletion');
    }
    $removed = [];
    $revision_ids = [];
    foreach ($ids as $id) {
        $post = get_post($id);
        if (in_array($id, $baseline_ids, true) || !$post || $post->post_type !== 'page'
            || $post->post_name !== $slug) {
            throw new RuntimeException('Cleanup identity guard rejected deletion');
        }
        $revisions = array_map('intval', $wpdb->get_col($wpdb->prepare(
            "SELECT ID FROM {$wpdb->posts} WHERE post_type='revision' AND post_parent=%%d", $id)));
        foreach ($revisions as $revision_id) {
            if (in_array($revision_id, $baseline_ids, true)) {
                throw new RuntimeException('Baseline revision must never be removed');
            }
        }
        $revision_ids = array_merge($revision_ids, $revisions);
        if (!wp_delete_post($id, true)) { throw new RuntimeException('Test page removal failed'); }
        $removed[] = $id;
        if ((int) $wpdb->get_var($wpdb->prepare(
            "SELECT COUNT(*) FROM {$wpdb->posts} WHERE ID=%%d OR (post_type='revision' AND post_parent=%%d)",
            $id, $id)) !== 0) { throw new RuntimeException('Test page or revisions remain'); }
    }
    return ['verified' => true, 'deleted_page_ids' => $removed,
            'deleted_revision_ids' => $revision_ids,
            'scope' => 'Unique test page and its child revisions only'];
    ''' % (post_id or 0, php_string(slug), php_string(json.dumps(baseline_ids)))
    return php(code)


def request_http(opener, url, *, payload=None, headers=None, method=None):
    request = urllib.request.Request(url, data=payload, headers=headers or {}, method=method)
    with opener.open(request, timeout=30) as response:
        return response.status, response.geturl(), response.read().decode('utf-8')


def rest(opener, web, nonce, route, payload=None):
    # Query routing also works when pretty permalinks are disabled.
    url = web + '/index.php?' + urllib.parse.urlencode(
        {'rest_route': '/wp/v2/' + route, 'context': 'edit'})
    headers = {'X-WP-Nonce': nonce, 'Accept': 'application/json'}
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    status, _, text = request_http(opener, url, payload=body, headers=headers)
    return status, json.loads(text)


def capture(web, username, password, post_id, title, marker, progress):
    """Capture actual views; never write a browser profile or authentication state."""
    sys.path.insert(0, str(ROOT / 'secrets/browser-deps'))
    from playwright.sync_api import sync_playwright
    edge = pathlib.Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    if not edge.exists():
        raise RuntimeError('Edge is unavailable for requested screenshots.')
    records = []

    def editor_text_visible(page):
        # Current Gutenberg versions render the page canvas inside an iframe.
        # Textarea values also do not necessarily appear in body.innerText.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            for frame in page.frames:
                try:
                    found = frame.evaluate('''([title, marker]) => {
                        const text = document.body ? document.body.innerText : '';
                        const values = Array.from(document.querySelectorAll(
                            'input, textarea, [contenteditable="true"]'))
                            .map(element => element.value || element.innerText || '')
                            .join('\\n');
                        return (text + '\\n' + values).includes(title)
                            && (text + '\\n' + values).includes(marker);
                    }''', [title, marker])
                    if found:
                        return
                except Exception:
                    # The editor frame can detach while Gutenberg initializes.
                    continue
            page.wait_for_timeout(500)
        raise TimeoutError('Published editor content did not become visible.')

    def snap(page, filename, url, label):
        path = EVIDENCE / filename
        page.screenshot(path=str(path), full_page=False, animations='disabled')
        record = {'captured_at': timestamp(), 'source': url, 'label': label,
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        (EVIDENCE / (path.stem + '.capture.json')).write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        records.append({'file': 'evidence/' + filename, **record})

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(edge), headless=True,
            args=['--disable-gpu', '--no-first-run'])
        admin = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                    locale='vi-VN', timezone_id='Asia/Ho_Chi_Minh')
        anonymous = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                        locale='vi-VN', timezone_id='Asia/Ho_Chi_Minh')
        try:
            admin.set_default_timeout(30000)
            page = admin.new_page()
            progress['capture_stage'] = 'browser_login'
            page.goto(web + '/wp-login.php', wait_until='domcontentloaded')
            page.locator('#user_login').fill(username)
            page.locator('#user_pass').fill(password)
            page.locator('#wp-submit').click()
            page.wait_for_url('**/wp-admin/**', wait_until='domcontentloaded')
            admin_url = web + '/wp-admin/post.php?post=' + str(post_id) + '&action=edit'
            progress['capture_stage'] = 'editor_dom'
            page.goto(admin_url, wait_until='domcontentloaded')
            page.wait_for_timeout(2500)
            # A first-login welcome guide can hide the actual editor canvas.
            close = page.locator('.components-modal__header button[aria-label="Close"], '
                                 '.components-modal__header button[aria-label="Đóng"]')
            if close.count() and close.first.is_visible():
                close.first.click()
            progress['capture_stage'] = 'editor_visible_content'
            editor_text_visible(page)
            page.wait_for_timeout(1500)
            progress['capture_stage'] = 'editor_screenshot'
            snap(page, '24-wordpress-edit-admin.png', admin_url,
                 'WordPress: trang kiểm thử đã sửa nội dung và xuất bản')
            public_url = web + '/?page_id=' + str(post_id)
            public = anonymous.new_page()
            progress['capture_stage'] = 'public_dom'
            public.goto(public_url, wait_until='domcontentloaded')
            public.wait_for_function('(marker) => document.body.innerText.includes(marker)', arg=marker)
            public.wait_for_timeout(1500)
            progress['capture_stage'] = 'public_screenshot'
            snap(public, '25-wordpress-edit-public.png', public_url,
                 'Truy cập ẩn danh: nội dung mới hiển thị ngoài website')
            progress['capture_stage'] = 'completed'
        finally:
            anonymous.close()
            admin.close()
            browser.close()
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true', help='Capture real Edge admin/public views before cleanup')
    args = parser.parse_args()
    EVIDENCE.mkdir(exist_ok=True)
    checks = []
    report = {'checked_at': timestamp(), 'workflow': 'Password login -> draft -> edit/publish -> anonymous GET -> cleanup',
              'transport': 'WordPress HTTP admin login and REST API with session cookie + wp_rest nonce',
              'checks': checks, 'passed': False, 'cookies_saved': False,
              'credentials_logged': False, 'test_content_removed': False,
              'public_render_verified': False, 'cleanup_verified': False,
              'original_pages_preserved': False,
              'original_posts_unchanged': False, 'original_postmeta_unchanged': False,
              'personal_options_unchanged': False}
    jar = http.cookiejar.CookieJar()
    session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    public = urllib.request.build_opener()  # Does not share admin cookies.
    before = None
    post_id = None
    password = None
    nonce = None
    slug = 'portfolio-edit-check-' + uuid.uuid4().hex

    def check(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})
        print(('PASS ' if condition else 'FAIL ') + name, flush=True)
        if not condition:
            raise RuntimeError('A verification assertion failed.')

    try:
        settings = read_env()
        local_path = ROOT / 'secrets/local-auth.json'
        local = json.loads(local_path.read_text(encoding='utf-8-sig')) if local_path.exists() else {}
        username = local.get('WORDPRESS_ADMIN_USER') or settings.get('WORDPRESS_ADMIN_USER', 'vanmanh_admin')
        password = local.get('WORDPRESS_ADMIN_PASSWORD') or settings.get('WORDPRESS_ADMIN_PASSWORD', '')
        check('Private local administrator credential is available',
              bool(username and password and not password.startswith('CHANGE_ME_')))
        web = 'http://localhost:' + settings.get('WEB_PORT', '8080')
        report['site_url'] = web
        before = snapshot()
        report['baseline'] = before
        check('Existing site snapshot was recorded before mutation', before['post_count'] > 0)

        request_http(session, web + '/wp-login.php')
        form = urllib.parse.urlencode({'log': username, 'pwd': password, 'wp-submit': 'Log In',
                                     'redirect_to': web + '/wp-admin/', 'testcookie': '1'}).encode()
        status, final_url, dashboard = request_http(session, web + '/wp-login.php', payload=form)
        check('Password login grants the real WordPress dashboard',
              status == 200 and '/wp-admin/' in final_url and 'id="wpbody-content"' in dashboard
              and any(c.name.startswith('wordpress_logged_in_') for c in jar))
        status, _, nonce = request_http(session, web + '/wp-admin/admin-ajax.php?action=rest-nonce')
        nonce = nonce.strip()
        check('Logged-in admin supplies a REST nonce without a persisted token',
              status == 200 and bool(re.fullmatch(r'[0-9a-f]{10}', nonce)))

        first_title = 'Kiểm thử quản trị — trang tạm thời'
        first_marker = 'Nội dung bản nháp ban đầu ' + slug
        status, created = rest(session, web, nonce, 'pages',
                               {'title': first_title, 'slug': slug, 'status': 'draft',
                                'content': '<!-- wp:paragraph --><p>' + first_marker + '</p><!-- /wp:paragraph -->'})
        returned_id = created.get('id')
        post_id = returned_id if isinstance(returned_id, int) and returned_id > 0 else None
        report['test_page_id'] = post_id
        report['test_slug'] = slug
        check('HTTP REST creates only the uniquely named test draft',
              status == 201 and isinstance(post_id, int) and post_id not in before['post_ids']
              and created.get('slug') == slug and created.get('status') == 'draft')
        status, stored = rest(session, web, nonce, 'pages/' + str(post_id))
        check('New draft content is saved by WordPress',
              status == 200 and first_marker in stored.get('content', {}).get('raw', ''))

        final_title = 'Kiểm thử quản trị — đã sửa và xuất bản'
        final_marker = 'NỘI DUNG ĐÃ CẬP NHẬT THÀNH CÔNG ' + slug
        final_content = ('<!-- wp:paragraph --><p>' + final_marker + '</p><!-- /wp:paragraph -->'
                         '\n<!-- wp:paragraph --><p>Minh chứng sửa, lưu và hiển thị ngoài website. '
                         'Trang kiểm thử được xóa ngay sau khi xác minh.</p><!-- /wp:paragraph -->')
        status, updated = rest(session, web, nonce, 'pages/' + str(post_id),
                               {'title': final_title, 'content': final_content, 'status': 'publish'})
        report['draft_response_status'] = 201
        report['edit_response_status'] = status
        check('HTTP REST edits the same page and publishes the saved update',
              status == 200 and updated.get('id') == post_id and updated.get('status') == 'publish'
              and final_marker in updated.get('content', {}).get('raw', ''))
        status, _, rendered = request_http(public, web + '/?page_id=' + str(post_id))
        report['public_response_status'] = status
        report['public_page_sha256'] = hashlib.sha256(rendered.encode()).hexdigest()
        visible = html.unescape(rendered)
        check('Anonymous public HTTP 200 displays the updated title and content',
              status == 200 and final_marker in visible and final_title in visible
              and first_marker not in visible)
        report['anonymous_public_view_verified'] = True
        report['public_render_verified'] = True
        if args.capture:
            report['screenshots'] = capture(web, username, password, post_id, final_title, final_marker, report)
            check('Real admin and anonymous public browser screenshots were captured',
                  len(report['screenshots']) == 2)
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        if isinstance(exc, urllib.error.HTTPError):
            report['http_error_status'] = exc.code
        # Never print str(exc), request headers, HTML, cookies, nonce or passwords.
        print('WordPress edit verification stopped; see sanitized error type in evidence.', flush=True)
    finally:
        if before is not None:
            try:
                report['cleanup'] = cleanup(post_id, slug, before['post_ids'])
                report['test_content_removed'] = report['cleanup']['verified']
                report['cleanup_verified'] = report['test_content_removed']
                check('Only the unique test page and its revisions were removed permanently',
                      report['test_content_removed'])
                after = snapshot()
                report['after_cleanup'] = after
                for field, key, label in [
                    ('posts_sha256', 'original_posts_unchanged', 'All original posts and pages remain byte-for-byte unchanged'),
                    ('postmeta_sha256', 'original_postmeta_unchanged', 'All original post metadata remains unchanged'),
                    ('personal_options_sha256', 'personal_options_unchanged', 'Personal site, theme, navigation and widget options remain unchanged'),
                ]:
                    report[key] = before[field] == after[field]
                    checks.append({'name': label, 'passed': report[key]})
                    print(('PASS ' if report[key] else 'FAIL ') + label, flush=True)
                report['original_pages_preserved'] = report['original_posts_unchanged']
            except Exception as exc:
                report['cleanup_error_type'] = type(exc).__name__
                checks.append({'name': 'Cleanup and preservation were fully verified', 'passed': False})
                print('Cleanup verification needs attention; raw output omitted.', flush=True)
        jar.clear()
        password = None
        nonce = None
        report['finished_at'] = timestamp()
        report['passed'] = bool(checks) and all(item['passed'] for item in checks) and not any(
            key in report for key in ('error_type', 'cleanup_error_type')) and report['test_content_removed']
        (EVIDENCE / 'wordpress-edit.json').write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('WordPress edit/publish/public-view/cleanup: ' + ('PASS' if report['passed'] else 'FAIL')
          + '. Evidence: evidence/wordpress-edit.json. No credentials or cookies logged.', flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
