"""Read-only authentication probe using an ignored local credential."""
import datetime
import json
from private_support import ROOT, docker, sql

report = {'checked_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(),
          'passed': False, 'account_changed': False}
try:
    credential = json.loads((ROOT / 'secrets/local-auth.json').read_text(encoding='utf-8'))
    identity = sql(credential['MYSQL_ROOT_CURRENT_PASSWORD'], 'SELECT CURRENT_USER();').decode().strip()
    report['passed'] = identity == 'root@localhost'
    report['authenticated_account'] = identity
except RuntimeError as exc:
    report['error'] = str(exc)
except Exception:
    report['error'] = 'Local credential unavailable or invalid; no secret printed.'
if not report['passed']:
    # Reuse the same supplied credential once from the application's network origin.
    # No guessing; this distinguishes root@localhost from root@other-host accounts.
    php = '''mysqli_report(MYSQLI_REPORT_OFF);
    $d=json_decode(stream_get_contents(STDIN),true);
    $c=@new mysqli("db","root",$d["password"]);
    if ($c->connect_errno) {echo json_encode(["passed"=>false,"mysql_error_code"=>$c->connect_errno]); exit(0);}
    $r=$c->query("SELECT CURRENT_USER()");
    echo json_encode(["passed"=>true,"authenticated_account"=>$r->fetch_row()[0]]);
    $c->close();'''
    try:
        result = docker('compose', 'exec', '-T', 'phpmyadmin', 'php', '-r', php,
                        input=json.dumps({'password': credential['MYSQL_ROOT_CURRENT_PASSWORD']}).encode())
        report['network_origin_probe'] = json.loads(result)
    except Exception:
        report['network_origin_probe'] = {'passed': False, 'error': 'Probe unavailable; no sensitive output printed.'}
(ROOT / 'evidence/local-root-auth.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
raise SystemExit(0 if report['passed'] else 1)
