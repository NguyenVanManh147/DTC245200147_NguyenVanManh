<?php
// CLI only; no public HTTP endpoint or credentials in this file.
if (PHP_SAPI !== 'cli') { exit(1); }
function result($data) {
    echo 'PORTFOLIO_BOOTSTRAP_RESULT=' . json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
}
function require_ok($value, $message) {
    if (is_wp_error($value) || !$value) { throw new RuntimeException($message); }
    return $value;
}
function replace_url($value, $from, $to) {
    if (is_string($value)) { return str_replace($from, $to, $value); }
    if (is_array($value)) {
        foreach ($value as $key => $item) { $value[$key] = replace_url($item, $from, $to); }
    }
    return $value;
}
function bind_navigation(&$blocks, $navigation_id) {
    $count = 0;
    foreach ($blocks as &$block) {
        if ($block['blockName'] === 'core/navigation') {
            $block['attrs']['ref'] = $navigation_id;
            $block['innerBlocks'] = [];
            $block['innerHTML'] = '';
            $block['innerContent'] = [];
            $count++;
        }
        $count += bind_navigation($block['innerBlocks'], $navigation_id);
    }
    return $count;
}
function database_guard() {
    global $wpdb;
    if (is_blog_installed()) {
        if (get_option('portfolio_bootstrap_state') === 'pending') {
            throw new RuntimeException('Lần khởi tạo trước bị gián đoạn. Kiểm tra site và log trước khi phục hồi; không tự nhập lại hoặc xóa dữ liệu.');
        }
        return ['status' => 'installed', 'site_url' => get_option('home')];
    }
    // Refuse even unrelated tables: this script owns only a completely empty DB.
    $tables = $wpdb->get_col('SHOW TABLES');
    if ($wpdb->last_error || $tables) {
        throw new RuntimeException('Database không trống hoặc không truy cập được. Dừng để bảo vệ dữ liệu hiện có.');
    }
    $uploads = ABSPATH . 'wp-content/uploads';
    if (is_dir($uploads)) {
        $iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($uploads, FilesystemIterator::SKIP_DOTS));
        foreach ($iterator as $file) {
            if ($file->isFile() || $file->isLink()) {
                throw new RuntimeException('Uploads đã có dữ liệu. Không ghi đè ảnh của site khác.');
            }
        }
    }
    return ['status' => 'empty'];
}

try {
    $lock = fopen('/tmp/portfolio-bootstrap.lock', 'c');
    if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) {
        throw new RuntimeException('Một tiến trình khởi tạo khác đang chạy.');
    }
    $input = json_decode(stream_get_contents(STDIN), true, 512, JSON_THROW_ON_ERROR);
    define('WP_INSTALLING', true);
    require '/var/www/html/wp-load.php';
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $status = database_guard();
    if (($input['mode'] ?? '') === 'probe' || $status['status'] === 'installed') {
        result($status);
        exit(0);
    }
    if (($input['mode'] ?? '') !== 'install') { throw new RuntimeException('Chế độ khởi tạo không hợp lệ.'); }
    $theme = wp_get_theme('twentytwentyfive');
    if (!$theme->exists()) { throw new RuntimeException('Image WordPress thiếu theme Twenty Twenty-Five.'); }
    if (!is_email($input['admin_email']) || !validate_username($input['admin_user']) || !$input['admin_password']) {
        throw new RuntimeException('Thông tin tài khoản quản trị trong .env không hợp lệ.');
    }
    // Validate every path/checksum before any database or upload writes.
    foreach ($input['media'] as $media) {
        if (!preg_match('~^\d{4}/\d{2}/[A-Za-z0-9_.-]+\.(jpg|jpeg|png|gif|webp)$~i', $media['path'])) {
            throw new RuntimeException('Đường dẫn ảnh trong export không hợp lệ.');
        }
        $bytes = base64_decode($media['data'], true);
        if ($bytes === false || hash('sha256', $bytes) !== $media['sha256']) {
            throw new RuntimeException('Checksum ảnh không khớp.');
        }
    }
    $installed = wp_install($input['title'], $input['admin_user'], $input['admin_email'],
                            true, '', $input['admin_password'], '');
    $admin_id = require_ok($installed['user_id'] ?? 0, 'Không tạo được tài khoản quản trị.');
    wp_set_current_user($admin_id);
    update_option('portfolio_bootstrap_state', 'pending');
    update_option('home', $input['site_url']);
    update_option('siteurl', $input['site_url']);
    update_option('timezone_string', 'Asia/Ho_Chi_Minh');
    // WordPress refuses locales without an installed language pack. Download
    // through its own API; an offline machine can still import the portfolio.
    require_once ABSPATH . 'wp-admin/includes/file.php';
    require_once ABSPATH . 'wp-admin/includes/translation-install.php';
    $language = wp_download_language_pack('vi') ?: '';
    update_option('WPLANG', $language);
    switch_theme('twentytwentyfive');
    // These are only wp_install defaults in a database proven empty above.
    global $wpdb;
    foreach ($wpdb->get_col("SELECT ID FROM {$wpdb->posts}") as $id) {
        wp_delete_post((int) $id, true);
    }
    $ids = [];
    $front = 0;
    $navigation = 0;
    foreach ($input['posts'] as $post) {
        $source_id = (int) $post['import_id'];
        $meta = $post['meta'];
        $terms = $post['terms'];
        $comments = $post['comments'];
        unset($post['meta'], $post['terms'], $post['comments']);
        $post['post_author'] = $admin_id;
        $post['post_parent'] = 0; // Relationships are resolved after all posts exist.
        foreach (['post_content', 'post_excerpt', 'guid'] as $field) {
            $post[$field] = replace_url($post[$field], $input['source_url'], $input['site_url']);
        }
        if ($post['post_type'] === 'attachment') {
            foreach ($meta as $entry) {
                if ($entry['key'] === '_wp_attached_file') {
                    $post['post_mime_type'] = wp_check_filetype($entry['value'])['type'];
                }
            }
        }
        $id = require_ok(wp_insert_post(wp_slash($post), true), 'Không nhập được bài/trang.');
        // IDs are referenced by Gutenberg blocks, metadata and query-style URLs.
        if ($id !== $source_id) {
            throw new RuntimeException('ID export bị trùng ngoài dự kiến; dừng để tránh navigation sai.');
        }
        $ids[$source_id] = $id;
        foreach ($meta as $entry) {
            if (in_array($entry['key'], ['_edit_lock', '_edit_last'], true)) { continue; }
            $value = replace_url(maybe_unserialize($entry['value']), $input['source_url'], $input['site_url']);
            update_post_meta($id, $entry['key'], wp_slash($value));
        }
        $term_ids = [];
        foreach ($terms as $term) {
            if (!taxonomy_exists($term['taxonomy'])) { throw new RuntimeException('Export có taxonomy chưa hỗ trợ.'); }
            $existing = term_exists($term['slug'], $term['taxonomy']);
            $added = $existing ?: wp_insert_term($term['name'], $term['taxonomy'], ['slug' => $term['slug']]);
            require_ok($added, 'Không nhập được taxonomy.');
            $term_ids[$term['taxonomy']][] = (int) (is_array($added) ? $added['term_id'] : $added);
        }
        foreach ($term_ids as $taxonomy => $assigned) {
            require_ok(wp_set_object_terms($id, $assigned, $taxonomy), 'Không gắn được taxonomy.');
        }
        foreach ($comments as $comment) {
            unset($comment['comment_id']);
            $comment['comment_post_ID'] = $id;
            $comment['user_id'] = $comment['comment_user_id'] ? $admin_id : 0;
            unset($comment['comment_user_id']);
            require_ok(wp_insert_comment(wp_slash($comment)), 'Không nhập được comment.');
        }
        if ($post['post_type'] === 'page' && $post['post_name'] === 'trang-chu') { $front = $id; }
        if ($post['post_type'] === 'page' && $post['post_name'] === 'chinh-sach-bao-mat') {
            update_option('wp_page_for_privacy_policy', $id);
        }
        if ($post['post_type'] === 'wp_navigation') { $navigation = $id; }
    }
    foreach ($input['posts'] as $post) {
        if ((int) $post['post_parent']) {
            require_ok(wp_update_post(['ID' => $ids[$post['import_id']],
                'post_parent' => $ids[$post['post_parent']] ?? 0], true), 'Không nối được quan hệ bài/trang.');
        }
    }
    foreach ($input['media'] as $media) {
        $path = ABSPATH . 'wp-content/uploads/' . $media['path'];
        require_ok(wp_mkdir_p(dirname($path)), 'Không tạo được thư mục ảnh.');
        $file = fopen($path, 'xb'); // Never overwrite a concurrently created file.
        require_ok($file, 'Ảnh đã tồn tại hoặc không có quyền ghi.');
        $bytes = base64_decode($media['data'], true);
        $written = fwrite($file, $bytes);
        fclose($file);
        if ($written !== strlen($bytes) || hash_file('sha256', $path) !== $media['sha256']) {
            throw new RuntimeException('Không ghi được ảnh đầy đủ.');
        }
    }
    require_ok($front, 'Export thiếu Trang chủ.');
    require_ok($navigation, 'Export thiếu navigation.');
    // An empty DB has no active theme at wp-load time, so init did not register
    // its patterns. Load the known header pattern from the pinned theme first.
    if (!WP_Block_Patterns_Registry::get_instance()->is_registered('twentytwentyfive/header')) {
        $pattern_path = $theme->get_stylesheet_directory() . '/patterns/header.php';
        if (!is_file($pattern_path)) { throw new RuntimeException('Theme thiếu mẫu header.'); }
        ob_start();
        include $pattern_path;
        $pattern_content = ob_get_clean();
        register_block_pattern('twentytwentyfive/header', [
            'title' => 'Header', 'content' => $pattern_content,
        ]);
    }
    $header = get_block_template('twentytwentyfive//header', 'wp_template_part');
    require_ok($header, 'Không tìm thấy header của theme.');
    $blocks = resolve_pattern_blocks(parse_blocks($header->content));
    require_ok(bind_navigation($blocks, $navigation), 'Header không có block navigation.');
    $header_id = require_ok(wp_insert_post(wp_slash([
        'post_type' => 'wp_template_part', 'post_name' => 'header',
        'post_title' => 'Header', 'post_status' => 'publish', 'post_author' => $admin_id,
        'post_content' => serialize_blocks($blocks),
    ]), true), 'Không lưu được header.');
    require_ok(wp_set_object_terms($header_id, 'twentytwentyfive', 'wp_theme'), 'Không gắn theme cho header.');
    wp_set_object_terms($header_id, 'header', 'wp_template_part_area');
    update_option('show_on_front', 'page');
    update_option('page_on_front', $front);
    update_option('page_for_posts', 0);
    update_option('permalink_structure', '');
    flush_rewrite_rules(false);
    update_option('portfolio_bootstrap_state', 'complete');
    result(['status' => 'created', 'site_url' => $input['site_url'],
            'imported_posts' => count($ids), 'media_files' => count($input['media']),
            'front_page' => $front, 'navigation' => $navigation,
            'locale' => $language ?: 'en_US']);
} catch (Throwable $error) {
    // Avoid raw SQL/WordPress errors which can include credentials or private data.
    $message = $error instanceof RuntimeException ? $error->getMessage()
        : 'Lỗi WordPress/PHP khi khởi tạo. Kiểm tra trạng thái site; không xóa volume hoặc nhập lại vào dữ liệu hiện có.';
    result(['status' => 'error', 'message' => $message]);
}
