/**
 * 公共布局：渲染侧边导航与顶栏，绑定主题切换、移动端折叠与退出登录。
 */
(function () {
  "use strict";

  var NAV_GROUPS = [
    {
      title: "内容",
      items: [
        { id: "dashboard", href: "dashboard.html", label: "仪表盘", icon: "M3 13h8V3H3v10zm10 8h8V11h-8v10zM3 21h8v-6H3v6zm10-12h8V3h-8v6z" },
        { id: "upload", href: "upload.html", label: "上传", icon: "M12 3v12m0-12l-4 4m4-4l4 4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" },
        { id: "images", href: "images.html", label: "图库管理", icon: "M3 5a2 2 0 012-2h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5zm3 11l3-3 2 2 4-5 3 6" },
        { id: "review", href: "review.html", label: "审核队列", icon: "M9 12l2 2 4-4M12 3l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V7l7-4z" },
        { id: "comments", href: "comments.html", label: "评论管理", icon: "M21 11.5a8.5 8.5 0 01-8.5 8.5 9 9 0 01-3.7-.8L4 21l1.4-4.1A8.5 8.5 0 013.5 11.5 8.5 8.5 0 0112 3a8.5 8.5 0 019 8.5z" }
      ]
    },
    {
      title: "组织",
      items: [
        { id: "folders", href: "folders.html", label: "文件夹", icon: "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" },
        { id: "tags", href: "tags.html", label: "标签", icon: "M20.6 13.4l-7.2 7.2a2 2 0 01-2.8 0l-7.2-7.2a2 2 0 01-.6-1.4V5a2 2 0 012-2h7a2 2 0 011.4.6l7.2 7.2a2 2 0 010 2.6zM7.5 7.5h.01" }
      ]
    },
    {
      title: "站点",
      items: [
        { id: "site-settings", href: "site-settings.html", label: "站点设置", icon: "M12 3a9 9 0 100 18 9 9 0 000-18zM3.6 9h16.8M3.6 15h16.8M12 3a13 13 0 010 18M12 3a13 13 0 000 18" },
        { id: "themes", href: "themes.html", label: "主题管理", icon: "M12 3a9 9 0 00-9 9 9 9 0 009 9c1.6 0 2.1-1.2 1.3-2.2-.8-1 .1-2.8 1.7-2.8H17a4 4 0 004-4c0-5-4-9-9-9zM7.5 13.5h.01M9.5 9.5h.01M14 9h.01" }
      ]
    },
    {
      title: "系统",
      items: [
        { id: "notifications", href: "notifications.html", label: "后台通知", icon: "M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0" },
        { id: "users", href: "users.html", label: "用户管理", icon: "M16 21v-2a4 4 0 00-4-4H7a4 4 0 00-4 4v2M9.5 3.5a3.5 3.5 0 100 7 3.5 3.5 0 000-7zM21 21v-2a4 4 0 00-3-3.87M16.5 3.13a4 4 0 010 7.75" },
        { id: "login-settings", href: "login-settings.html", label: "登录设置", icon: "M6 11V8a6 6 0 0112 0v3M5 11h14v9a1 1 0 01-1 1H6a1 1 0 01-1-1v-9zM12 15v2" },
        { id: "tokens", href: "tokens.html", label: "上传 Token", icon: "M15 7a4 4 0 11-3.5 5.9L9 15.4l-2 .3.3-2 2.6-2.6A4 4 0 0115 7zM15 7h.01" },
        { id: "recycle", href: "recycle.html", label: "回收站", icon: "M4 7h16M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2m-8 0l1 13a1 1 0 001 1h6a1 1 0 001-1l1-13" },
        { id: "settings", href: "settings.html", label: "账号与安全", icon: "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.7 1.7 0 00.3 1.9l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-2.9 1.2 2 2 0 11-4 0 1.7 1.7 0 00-2.9-1.2l-.1.1a2 2 0 11-2.8-2.8l.1-.1A1.7 1.7 0 004 15a2 2 0 01-2-2 2 2 0 012-2 1.7 1.7 0 001.2-2.9l-.1-.1a2 2 0 112.8-2.8l.1.1A1.7 1.7 0 0011 4a2 2 0 014 0 1.7 1.7 0 002.9 1.2l.1-.1a2 2 0 112.8 2.8l-.1.1A1.7 1.7 0 0020 11a2 2 0 010 4z" }
      ]
    }
  ];

  // 兼容导出：扁平化的全部导航项
  var NAV_ITEMS = NAV_GROUPS.reduce(function (list, group) {
    return list.concat(group.items);
  }, []);

  var API_BASE = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "";
  // 站点版本号与当前高亮导航（供异步获取版本后重渲染侧边栏）
  var siteVersion = "";
  var currentActive = "";

  function iconSvg(path) {
    return '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" ' +
      'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="' + path + '"/></svg>';
  }

  function renderSidebar(active) {
    var aside = document.getElementById("app-sidebar");
    if (!aside) return;
    currentActive = active || "";
    var brand = Theme.getState().siteName || "图库后台";
    var html =
      '<div class="sidebar-brand">' +
        '<span class="brand-logo">' +
          '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8">' +
          '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 15l4-4 3 3 4-5 5 6"/></svg>' +
        "</span>" +
        '<span class="brand-text">' + UI.escapeHtml(brand) + "</span>" +
      "</div>" +
      '<nav class="sidebar-nav">';
    NAV_GROUPS.forEach(function (group) {
      html += '<div class="sidebar-group">';
      if (group.title) {
        html += '<div class="sidebar-group-title">' + UI.escapeHtml(group.title) + "</div>";
      }
      (group.items || []).forEach(function (item) {
        html += '<a class="nav-item' + (item.id === active ? " active" : "") + '" href="' + item.href + '">' +
          iconSvg(item.icon) + "<span>" + UI.escapeHtml(item.label) + "</span></a>";
      });
      html += "</div>";
    });
    html += "</nav>";
    if (siteVersion) {
      html += '<div class="sidebar-footer">ImageLibrary v' + UI.escapeHtml(siteVersion) + "</div>";
    }
    aside.innerHTML = html;
  }

  /**
   * 注入站点 favicon 与版本号：请求 /api/settings，失败静默；
   * favicon 为空时不注入 link，版本号获取成功后重渲染侧边栏底部。
   */
  async function loadSiteMeta() {
    try {
      var data = await API.get("/api/settings");
      var favicon = data && data.favicon;
      if (favicon) {
        var href = /^https?:\/\//i.test(favicon) ? favicon : API_BASE + favicon;
        var link = document.head && document.head.querySelector('link[rel="icon"]');
        if (!link) {
          link = document.createElement("link");
          link.rel = "icon";
          if (document.head) document.head.appendChild(link);
        }
        link.href = href;
      }
      var version = data && data.version;
      if (version && version !== siteVersion) {
        siteVersion = version;
        safeSidebar(currentActive);
      }
    } catch (err) { /* 静默：站点元信息获取失败不影响布局 */ }
  }

  function renderTopbar(admin) {
    var header = document.getElementById("app-topbar");
    if (!header) return;

    var themeOptions = Theme.enabledThemes().map(function (t) {
      return '<option value="' + t.id + '">' + UI.escapeHtml(t.name) + "</option>";
    }).join("");

    header.innerHTML =
      '<button type="button" class="icon-btn only-mobile" id="sidebar-toggle" aria-label="菜单">' +
        '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">' +
        '<path d="M4 6h16M4 12h16M4 18h16"/></svg>' +
      "</button>" +
      '<div class="topbar-title" id="topbar-title">' + UI.escapeHtml(Theme.getState().siteName || "管理后台") + "</div>" +
      '<div class="topbar-actions">' +
        '<label class="theme-select-wrap">' +
          '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8">' +
          '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 000 18z"/></svg>' +
          '<select id="theme-select" class="theme-select" aria-label="切换主题">' + themeOptions + "</select>" +
        "</label>" +
        '<span class="admin-name" id="admin-name">' + UI.escapeHtml(admin && admin.username ? admin.username : "管理员") + "</span>" +
        '<button type="button" class="btn btn-ghost btn-sm" id="logout-btn">退出</button>' +
      "</div>";

    var select = header.querySelector("#theme-select");
    if (select) {
      select.value = Theme.getState().current || Theme.getState().defaultTheme || "light";
      select.addEventListener("change", function () { Theme.apply(select.value); });
      document.addEventListener("themechange", function (e) {
        select.value = e.detail.id;
      });
    }
    var logoutBtn = header.querySelector("#logout-btn");
    if (logoutBtn) logoutBtn.addEventListener("click", function () { Auth.logout(); });

    var toggle = header.querySelector("#sidebar-toggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        document.getElementById("app-layout").classList.toggle("sidebar-open");
      });
    }
    var aside = document.getElementById("app-sidebar");
    if (aside) {
      aside.addEventListener("click", function (e) {
        if (e.target.closest(".nav-item")) {
          document.getElementById("app-layout").classList.remove("sidebar-open");
        }
      });
    }
  }

  /** 安全渲染侧边栏，任何异常都不外抛。 */
  function safeSidebar(active) {
    try { renderSidebar(active); } catch (err) { /* 布局兜底：忽略渲染异常 */ }
  }

  /** 安全渲染顶栏，任何异常都不外抛。 */
  function safeTopbar(admin) {
    try { renderTopbar(admin); } catch (err) { /* 布局兜底：忽略渲染异常 */ }
  }

  /**
   * 初始化公共布局：先同步渲染侧边栏与顶栏（不依赖网络），再异步鉴权。
   * 任何异常都不得中断布局渲染；永不 reject。
   * @param {{active:string}} options 当前高亮的导航 id
   * @returns {Promise<object|null>} 当前管理员信息
   */
  async function initLayout(options) {
    options = options || {};
    // 1) 同步渲染骨架，保证侧边栏/顶栏始终可见
    safeSidebar(options.active);
    safeTopbar(null);
    // 异步注入 favicon 与版本号（失败静默，不阻塞布局）
    loadSiteMeta();

    // 2) 异步鉴权（可能触发跳转登录页），异常时返回 null
    var admin = null;
    try {
      admin = await Auth.requireAuth();
    } catch (err) {
      admin = null;
    }

    // 3) 取到管理员信息后刷新（站点名/用户名），失败也不影响已渲染的布局
    if (admin) {
      safeSidebar(options.active);
      safeTopbar(admin);
      try {
        if (document.title.indexOf(" - ") === -1) {
          document.title = document.title + " - " + (Theme.getState().siteName || "管理后台");
        }
      } catch (err) { /* 忽略标题异常 */ }
    }
    return admin;
  }

  /**
   * 统一启动入口：同步渲染布局骨架 → 初始化主题 → 鉴权 → 执行 onReady。
   * 任一环节异常都不会中断布局渲染，也不会 reject。
   * @param {{active:string, onReady?:(admin:object)=>void}} options
   * @returns {Promise<object|null>} 当前管理员信息
   */
  async function boot(options) {
    options = options || {};
    safeSidebar(options.active);
    safeTopbar(null);

    // 主题初始化（失败已在 theme.js 内部兜底）
    try {
      if (window.Theme && typeof Theme.init === "function") await Theme.init();
    } catch (err) { /* ignore */ }

    // 主题就绪后再渲染一次（站点名、主题选项可能已更新）
    safeSidebar(options.active);
    safeTopbar(null);
    // 异步注入 favicon 与版本号（失败静默，不阻塞布局）
    loadSiteMeta();

    var admin = null;
    try {
      admin = await Auth.requireAuth();
    } catch (err) {
      admin = null;
    }

    if (admin) {
      safeSidebar(options.active);
      safeTopbar(admin);
      try {
        if (document.title.indexOf(" - ") === -1) {
          document.title = document.title + " - " + (Theme.getState().siteName || "管理后台");
        }
      } catch (err) { /* ignore */ }
    }

    if (admin && typeof options.onReady === "function") {
      try {
        options.onReady(admin);
      } catch (err) {
        try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
      }
    }
    return admin;
  }

  window.Layout = { initLayout: initLayout, boot: boot, NAV_ITEMS: NAV_ITEMS, NAV_GROUPS: NAV_GROUPS };
})();
