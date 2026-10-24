/* 公共布局：渲染页头（站名/导航/搜索/用户区/预设选择器）与页脚，并绑定交互。
   主题预设来自 window.APP_CONFIG.THEME（同步），站点信息仅请求一次 /api/site；
   SEO/favicon 注入、页脚文案与用户区失败均静默兜底，不阻断渲染。 */
(function () {
  'use strict';

  var DEFAULT_SITE_NAME = '我的图库';
  var siteName = DEFAULT_SITE_NAME;
  var siteTitle = '';
  var footerText = '';
  var currentUser = null;
  var siteData = null;
  var sitePromise = null;
  var NAV_ITEMS = [
    { key: 'index', href: 'index.html', label: '首页' },
    { key: 'folder', href: 'folder.html', label: '分类' },
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

    // 预设选择器：选项来自 Theme.getThemes()（当前主题的预设列表）
    var presets = (window.Theme && Theme.getThemes) ? Theme.getThemes() : [];
    var presetOptions = presets.map(function (t) {
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
            '<select class="select select--sm js-theme-select" aria-label="选择配色预设">' +
            presetOptions + '</select>' +
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

    // 预设选择器
    var select = host.querySelector('.js-theme-select');
    if (select) {
      if (window.Theme && Theme.getCurrent) select.value = Theme.getCurrent();
      select.addEventListener('change', function () {
        if (window.Theme && Theme.apply) Theme.apply(select.value);
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

  /**
   * 请求站点信息（全局仅一次），应用 SEO/页脚/站名；失败返回 null。
   * 页面可复用该 Promise，避免重复请求 /api/site。
   */
  function loadSite() {
    if (sitePromise) return sitePromise;
    sitePromise = (async function () {
      try {
        var site = await window.API.get('/api/site');
        siteData = site;
        try { applySeo(site); } catch (e) { /* ignore */ }
        try {
          if (site && typeof site.footer_text === 'string') footerText = site.footer_text;
          if (site && site.site_name) siteName = site.site_name;
        } catch (e) { /* ignore */ }
        return site;
      } catch (e) {
        return null;
      }
    })();
    return sitePromise;
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

  /**
   * 初始化布局：同步应用预设并渲染页头/页脚 → 请求 /api/site 刷新站点信息
   * → 加载用户。永不 reject。
   */
  async function init(active) {
    // 1) 同步：应用预设（来自 APP_CONFIG.THEME），渲染页头/页脚骨架
    try { if (window.Theme && Theme.init) Theme.init(); } catch (e) { /* ignore */ }
    try { renderHeader(active); } catch (e) { /* 忽略渲染异常 */ }
    try { renderFooter(); } catch (e) { /* 忽略渲染异常 */ }

    // 2) 站点信息（仅一次请求；失败保持已渲染布局）
    await loadSite();
    try { renderHeader(active); } catch (e) { /* ignore */ }
    try { renderFooter(); } catch (e) { /* ignore */ }

    // 3) 用户区（失败静默）
    try { await loadUser(); } catch (e) { /* ignore */ }
  }

  window.Layout = {
    init: init,
    initLayout: init,
    renderHeader: renderHeader,
    renderFooter: renderFooter,
    loadSite: loadSite,
    getSite: function () { return siteData; },
    getSiteName: function () { return siteName; }
  };
})();
