/* 公共布局：渲染页头（站名/导航/搜索/用户区/主题选择器）与页脚，并绑定交互。
   同时负责站点 SEO（title/meta/OG）与 favicon 注入、页脚文案，全部失败静默不阻断渲染。 */
(function () {
  'use strict';

  var siteName = '我的图库';
  var siteTitle = '';
  var footerText = '';
  var currentUser = null;
  var NAV_ITEMS = [
    { key: 'index', href: 'index.html', label: '首页' },
    { key: 'folder', href: 'folder.html', label: '文件夹' },
    { key: 'search', href: 'search.html', label: '搜索' },
    { key: 'upload', href: 'upload.html', label: '上传' }
  ];

  var LOGO_SVG = '<svg class="brand__logo" viewBox="0 0 24 24" width="26" height="26" fill="none" ' +
    'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<rect x="3" y="3" width="18" height="18" rx="3"></rect>' +
    '<circle cx="8.5" cy="8.5" r="1.6"></circle><path d="m21 15-5-5L5 21"></path></svg>';

  /** 兼容 renderHeader('index') 与 renderHeader({active:'index'}) 两种调用方式。 */
  function normalizeActive(arg) {
    if (arg && typeof arg === 'object') return arg.active || '';
    return arg || '';
  }

  /** 读取用户会话模块（可能未加载，做空值兜底）。 */
  function userSession() {
    return window.UserSession || null;
  }

  /** 渲染页头用户区：未登录显示「登录 / 注册」，已登录显示头像/昵称与退出。 */
  function renderUserArea() {
    var host = document.getElementById('header-user');
    if (!host) return;
    var session = userSession();

    if (!currentUser) {
      host.innerHTML =
        '<a class="header-user__link" href="login.html">登录</a>' +
        '<span class="header-user__sep">/</span>' +
        '<a class="header-user__link" href="login.html">注册</a>';
      return;
    }

    var name = currentUser.nickname || currentUser.username || '用户';
    var avatar = currentUser.avatar_url
      ? '<img class="header-user__avatar" src="' + UI.escapeHtml(currentUser.avatar_url) + '" alt="" loading="lazy">'
      : '<span class="header-user__avatar header-user__avatar--text">' +
        UI.escapeHtml(String(name).charAt(0).toUpperCase()) + '</span>';

    host.innerHTML =
      '<span class="header-user__profile">' + avatar +
      '<span class="header-user__name">' + UI.escapeHtml(name) + '</span></span>' +
      '<button class="header-user__logout" type="button" id="header-logout">退出</button>';

    var logoutBtn = host.querySelector('#header-logout');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', function () {
        if (session) session.clear();
        window.location.reload();
      });
    }
  }

  function renderHeader(activeArg) {
    var host = document.getElementById('app-header');
    if (!host) return;
    var active = normalizeActive(activeArg);

    var navHtml = NAV_ITEMS.map(function (item) {
      var cls = 'site-nav__link' + (item.key === active ? ' is-active' : '');
      return '<a class="' + cls + '" href="' + item.href + '">' + item.label + '</a>';
    }).join('');

    var themeOptions = window.Theme.getThemes().map(function (t) {
      return '<option value="' + UI.escapeHtml(t.id) + '">' + UI.escapeHtml(t.name) + '</option>';
    }).join('');

    host.innerHTML =
      '<header class="site-header">' +
        '<div class="container site-header__inner">' +
          '<a class="brand" href="index.html">' + LOGO_SVG +
            '<span class="brand__name">' + UI.escapeHtml(siteName) + '</span></a>' +
          '<button class="nav-toggle" type="button" aria-label="展开导航" aria-expanded="false">' +
            '<span></span><span></span><span></span></button>' +
          '<nav class="site-nav" id="site-nav">' + navHtml + '</nav>' +
          '<form class="header-search" role="search">' +
            '<input class="input input--sm header-search__input" type="search" placeholder="搜索图片…" aria-label="搜索图片">' +
            '<button class="btn btn--primary btn--sm" type="submit">搜索</button>' +
          '</form>' +
          '<div class="header-user" id="header-user"></div>' +
          '<div class="theme-picker">' +
            '<select class="select select--sm js-theme-select" aria-label="选择主题">' + themeOptions + '</select>' +
          '</div>' +
        '</div>' +
      '</header>';

    renderUserArea();

    // 移动端导航折叠
    var toggle = host.querySelector('.nav-toggle');
    var nav = host.querySelector('#site-nav');
    if (toggle && nav) {
      toggle.addEventListener('click', function () {
        var open = nav.classList.toggle('is-open');
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    }

    // 主题选择器
    var select = host.querySelector('.js-theme-select');
    if (select) {
      select.value = window.Theme.getCurrent();
      select.addEventListener('change', function () {
        window.Theme.apply(select.value);
      });
    }

    // 页头搜索
    var form = host.querySelector('.header-search');
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = form.querySelector('input');
        var q = (input.value || '').trim();
        if (!q) { input.focus(); return; }
        window.location.href = 'search.html?q=' + encodeURIComponent(q);
      });
    }
  }

  function renderFooter() {
    var host = document.getElementById('app-footer');
    if (!host) return;
    var year = new Date().getFullYear();
    var text = footerText || ('© ' + year + ' ' + siteName);
    host.innerHTML =
      '<footer class="site-footer"><div class="container site-footer__inner">' +
        '<span class="site-footer__text">' + UI.escapeHtml(text) + '</span>' +
        '<span class="site-footer__muted">图片库 · 原生 HTML/CSS/JS</span>' +
      '</div></footer>';
  }

  /* ---------- SEO / favicon 注入 ---------- */

  /** 创建或更新 <meta>。 */
  function setMeta(attr, key, content) {
    if (!content) return;
    var head = document.head || document.documentElement;
    if (!head) return;
    var el = head.querySelector('meta[' + attr + '="' + key + '"]');
    if (!el) {
      el = document.createElement('meta');
      el.setAttribute(attr, key);
      head.appendChild(el);
    }
    el.setAttribute('content', content);
  }

  /** 注入 favicon（favicon 为空则不处理）。 */
  function applyFavicon(favicon) {
    if (!favicon) return;
    var head = document.head || document.documentElement;
    if (!head) return;
    var href = window.API.apiUrl(favicon);
    var el = head.querySelector('link[rel="icon"]');
    if (!el) {
      el = document.createElement('link');
      el.setAttribute('rel', 'icon');
      head.appendChild(el);
    }
    el.setAttribute('href', href);
  }

  /** 应用站点 SEO 信息：title / description / keywords / OG。 */
  function applySeo(site) {
    if (!site) return;

    siteTitle = site.site_title || site.site_name || siteTitle;
    var current = document.title || '';
    var titleToUse = siteTitle;
    if (siteTitle && current && current.indexOf(siteTitle) === -1) {
      titleToUse = current + ' | ' + siteTitle;
    }
    if (titleToUse) document.title = titleToUse;

    setMeta('name', 'description', site.site_description);
    setMeta('name', 'keywords', site.site_keywords);
    setMeta('property', 'og:title', titleToUse || siteTitle);
    setMeta('property', 'og:description', site.site_description);
    setMeta('property', 'og:site_name', site.site_name || siteTitle);

    applyFavicon(site.favicon);
  }

  /** 拉取站点信息并注入 SEO/页脚；失败静默。 */
  async function loadSiteMeta() {
    var site = null;
    try {
      site = await window.API.get('/api/site');
    } catch (e) {
      return;
    }
    try { applySeo(site); } catch (e) { /* ignore */ }
    try {
      if (site && typeof site.footer_text === 'string') footerText = site.footer_text;
      if (site && site.site_name) siteName = site.site_name;
      renderFooter();
    } catch (e) { /* ignore */ }
  }

  /** 加载当前登录用户并刷新用户区；失败静默。 */
  async function loadUser() {
    var session = userSession();
    if (!session || !session.isLoggedIn()) {
      currentUser = null;
      renderUserArea();
      return;
    }
    try {
      currentUser = await session.me();
    } catch (e) {
      currentUser = null;
    }
    renderUserArea();
  }

  /** 初始化布局：先同步渲染页头与页脚（不依赖网络），再异步拉取设置并刷新。永不 reject。 */
  async function init(active) {
    // 1) 同步渲染骨架，保证页头/页脚始终可见
    try { renderHeader(active); } catch (e) { /* 忽略渲染异常 */ }
    try { renderFooter(); } catch (e) { /* 忽略渲染异常 */ }

    // 2) 异步初始化主题并拉取站点设置，失败时保持已渲染布局
    try {
      var settings = await window.Theme.init();
      if (settings && settings.site_name) siteName = settings.site_name;
      try { renderHeader(active); } catch (e) { /* ignore */ }
      try { renderFooter(); } catch (e) { /* ignore */ }
    } catch (e) { /* 布局兜底：忽略主题/设置异常 */ }

    // 3) 站点 SEO / favicon / 页脚文案（失败静默）
    try { await loadSiteMeta(); } catch (e) { /* ignore */ }

    // 4) 用户区（失败静默）
    try { await loadUser(); } catch (e) { /* ignore */ }
  }

  window.Layout = {
    init: init,
    initLayout: init,
    renderHeader: renderHeader,
    renderFooter: renderFooter,
    getSiteName: function () { return siteName; }
  };
})();
