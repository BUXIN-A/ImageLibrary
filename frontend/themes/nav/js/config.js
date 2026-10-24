/* 全局配置（静态兜底）：服务端会在 /js/config.js 动态注入 API_BASE 与 THEME。 */
(function () {
  'use strict';
  window.APP_CONFIG = window.APP_CONFIG || {};
  if (!window.APP_CONFIG.API_BASE) {
    window.APP_CONFIG.API_BASE = 'http://127.0.0.1:8080';
  }
  if (!window.APP_CONFIG.THEME) {
    window.APP_CONFIG.THEME = {
      active_theme: 'nav',
      default_preset: 'light',
      presets: { nav: [{ id: 'light', name: '亮色' }, { id: 'dark', name: '暗色' }] },
      nav: {
        stats: {
          folder_images: true,
          total_images: true,
          total_views: true,
          total_comments: true,
          total_downloads: true
        }
      }
    };
  }
})();
