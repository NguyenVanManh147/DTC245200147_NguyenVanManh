"""Generate repository-owned Grafana dashboards without remote dashboard dependencies."""
import json
from pathlib import Path

destination = Path(__file__).resolve().parents[1] / 'monitoring/grafana/dashboards'
destination.mkdir(parents=True, exist_ok=True)
prom = {'type': 'prometheus', 'uid': 'portfolio-prometheus'}
loki = {'type': 'loki', 'uid': 'portfolio-loki'}

def panel(number, title, expression, unit='short', kind='timeseries', datasource=prom):
    return {
        'id': number, 'title': title, 'type': kind, 'datasource': datasource,
        'gridPos': {'h': 9, 'w': 12, 'x': ((number - 1) % 2) * 12, 'y': ((number - 1) // 2) * 9},
        'targets': [{'refId': 'A', 'expr': expression, 'legendFormat': '{{container_label_com_docker_compose_service}}', 'datasource': datasource}],
        'fieldConfig': {'defaults': {'unit': unit}, 'overrides': []},
        'options': {'legend': {'displayMode': 'list', 'placement': 'bottom'}},
    }

metrics = [
    ('Container CPU theo dịch vụ', 'sum by (container_label_com_docker_compose_service) (rate(container_cpu_usage_seconds_total{job="cadvisor",container_label_com_docker_compose_project="portfolio-manh"}[2m])) * 100', 'percent'),
    ('Container RAM theo dịch vụ', 'sum by (container_label_com_docker_compose_service) (container_memory_working_set_bytes{job="cadvisor",container_label_com_docker_compose_project="portfolio-manh"})', 'bytes'),
    ('Nginx requests mỗi giây (stub_status)', 'rate(nginx_http_requests_total{job="nginx"}[2m])', 'reqps'),
    ('Nginx kết nối đang mở', 'nginx_connections_active{job="nginx"}', 'short'),
    ('MySQL queries mỗi giây', 'rate(mysql_global_status_queries{job="mysql"}[2m])', 'ops'),
    ('MySQL threads đang kết nối', 'mysql_global_status_threads_connected{job="mysql"}', 'short'),
    ('Website HTTP khả dụng (Blackbox)', 'probe_success{job="portfolio_http"}', 'short'),
    ('Website HTTP thời gian phản hồi', 'probe_duration_seconds{job="portfolio_http"}', 's'),
    ('Nginx scrape thành công', 'nginx_up{job="nginx"}', 'short'),
    ('MySQL scrape thành công', 'mysql_up{job="mysql"}', 'short'),
]

def save(uid, title, panels):
    dashboard = {
        'uid': uid, 'title': title, 'tags': ['portfolio', 'DTC245200147'],
        'schemaVersion': 39, 'version': 1, 'editable': False,
        'timezone': 'Asia/Ho_Chi_Minh', 'refresh': '15s',
        'time': {'from': 'now-30m', 'to': 'now'}, 'panels': panels,
    }
    (destination / f'{uid}.json').write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

save('portfolio-infrastructure', 'Portfolio • Container / Nginx / MySQL', [panel(i, *entry) for i, entry in enumerate(metrics, 1)])
save('portfolio-logs', 'Portfolio • Nginx access logs', [
    panel(1, 'Log truy cập thực tế', '{project="portfolio-manh",job="nginx-access"} | json', kind='logs', datasource=loki),
    panel(2, 'HTTP 4xx / 5xx', '{project="portfolio-manh",job="nginx-access"} | json | __error__="" | status >= 400 | status < 600', kind='logs', datasource=loki),
    panel(3, 'Requests trong từng cửa sổ 1 phút', 'sum(count_over_time({project="portfolio-manh",job="nginx-access"}[1m]))', datasource=loki),
])
print('Generated 2 Grafana dashboards.')
