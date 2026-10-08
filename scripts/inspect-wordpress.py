import json
import subprocess

php = b'''<?php
require '/var/www/html/wp-load.php';
global $wpdb, $wp_version;
echo json_encode([
 'wordpress_version' => $wp_version,
 'theme' => get_option('stylesheet'),
 'pages' => $wpdb->get_results("SELECT ID,post_title,post_name,post_status FROM {$wpdb->posts} WHERE post_type='page'"),
 'grants' => $wpdb->get_results('SHOW GRANTS FOR CURRENT_USER()', ARRAY_N),
 'database' => DB_NAME,
 'table_prefix' => $wpdb->prefix
], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
'''
r = subprocess.run(['docker', 'exec', '-i', 'portfolio-manh-wordpress-1', 'php'], input=php, capture_output=True, check=True)
print(r.stdout.decode('utf-8'))
