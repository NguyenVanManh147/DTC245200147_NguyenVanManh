"""Verify a real password login and pages admin screen without saving session cookies."""
import argparse
import datetime
import getpass
import http.cookiejar
import json
import urllib.parse
import urllib.request
from private_support import ROOT, read_env

parser = argparse.ArgumentParser()
parser.add_argument('--from-local', action='store_true', help='Use the ignored local password dialog file; no terminal prompt')
args = parser.parse_args()
settings = read_env()
path = ROOT / 'secrets/local-auth.json'
local = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
username = local.get('WORDPRESS_ADMIN_USER', 'vanmanh_admin')
password = local.get('WORDPRESS_ADMIN_PASSWORD', '')
if not password and args.from_local:
    raise SystemExit('WordPress password is not available locally; enter it through the dialog or local terminal.')
if not password:
    username = input('WordPress username [vanmanh_admin]: ').strip() or 'vanmanh_admin'
    password = getpass.getpass('WordPress password (hidden): ')
web = 'http://localhost:' + settings.get('WEB_PORT', '8080')
jar = http.cookiejar.CookieJar()
session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
report = {'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
          'username': username, 'password_login_verified': False, 'dashboard_access': False, 'pages_admin_access': False,
          'cookies_saved': False, 'content_modified': False}
try:
    # WordPress requires the test cookie set on the initial login page.
    session.open(web + '/wp-login.php', timeout=15).read()
    data = urllib.parse.urlencode({'log': username, 'pwd': password, 'wp-submit': 'Log In',
                                  'redirect_to': web + '/wp-admin/', 'testcookie': '1'}).encode()
    response = session.open(web + '/wp-login.php', data=data, timeout=15)
    dashboard = response.read().decode('utf-8')
    report['password_login_verified'] = any(cookie.name.startswith('wordpress_logged_in_') for cookie in jar)
    report['dashboard_access'] = report['password_login_verified'] and '/wp-admin/' in response.geturl() and 'id="wpbody-content"' in dashboard and 'wp-admin-bar-my-account' in dashboard
    response = session.open(web + '/wp-admin/edit.php?post_type=page', timeout=15)
    pages = response.read().decode('utf-8')
    report['pages_admin_access'] = report['dashboard_access'] and 'edit.php' in response.geturl() and 'post_type=page' in pages and 'id="the-list"' in pages
    report['passed'] = report['password_login_verified'] and report['dashboard_access'] and report['pages_admin_access']
except Exception as exc:
    report['passed'] = False
    report['error_type'] = type(exc).__name__
finally:
    jar.clear()
    password = None
(ROOT / 'evidence/wordpress-admin.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('WordPress password login, Dashboard and pages admin: ' + ('PASS' if report['passed'] else 'FAIL') + '. No cookies/password logged; no content modified.')
raise SystemExit(0 if report['passed'] else 1)
