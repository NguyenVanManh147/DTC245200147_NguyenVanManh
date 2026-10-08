<?php
/** Runtime hardening; does not edit existing posts, users, theme, or database. */
if (!defined('ABSPATH')) {
    exit;
}
if (!defined('DISALLOW_FILE_EDIT')) {
    define('DISALLOW_FILE_EDIT', true);
}
add_filter('xmlrpc_enabled', '__return_false');
remove_action('wp_head', 'wp_generator');
