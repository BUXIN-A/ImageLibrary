/**
 * 仪表盘：展示统计卡片，待审核卡片可点击跳转审核队列。
 */
(function () {
  "use strict";

  var CARDS = [
    { key: "images_total", label: "图片总数", href: "images.html", icon: "M3 5a2 2 0 012-2h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5zm3 11l3-3 2 2 4-5 3 6" },
    { key: "pending_total", label: "待审核", href: "review.html", cls: "accent-pending", icon: "M12 8v5m0 3h.01M12 3l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V7l7-4z" },
    { key: "folders_total", label: "文件夹", href: "folders.html", icon: "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" },
    { key: "tags_total", label: "标签", href: "tags.html", icon: "M20.6 13.4l-7.2 7.2a2 2 0 01-2.8 0l-7.2-7.2a2 2 0 01-.6-1.4V5a2 2 0 012-2h7a2 2 0 011.4.6l7.2 7.2a2 2 0 010 2.6z" },
    { key: "recycle_total", label: "回收站", href: "recycle.html", cls: "accent-danger", icon: "M4 7h16M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2m-8 0l1 13a1 1 0 001 1h6a1 1 0 001-1l1-13" },
    { key: "tokens_total", label: "上传 Token", href: "tokens.html", icon: "M15 7a4 4 0 11-3.5 5.9L9 15.4l-2 .3.3-2 2.6-2.6A4 4 0 0115 7z" },
    { key: "views_total", label: "总浏览量", icon: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7zm10 3a3 3 0 100-6 3 3 0 000 6z" },
    { key: "downloads_total", label: "总下载量", icon: "M12 3v12m0 0l-4-4m4 4l4-4M4 19h16" }
  ];

  function iconSvg(path) {
    return '<span class="stat-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" ' +
      'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="' + path + '"/></svg></span>';
  }

  function renderCards(stats) {
    var grid = document.getElementById("stat-grid");
    grid.innerHTML = "";
    CARDS.forEach(function (card) {
      var el = document.createElement("div");
      el.className = "stat-card" + (card.href ? " clickable" : "") + (card.cls ? " " + card.cls : "");
      el.innerHTML =
        iconSvg(card.icon) +
        '<span class="stat-value">' + UI.escapeHtml(String(stats[card.key] || 0)) + "</span>" +
        '<span class="stat-label">' + UI.escapeHtml(card.label) + "</span>";
      if (card.href) {
        el.addEventListener("click", function () { location.href = card.href; });
      }
      grid.appendChild(el);
    });
  }

  async function load() {
    var grid = document.getElementById("stat-grid");
    grid.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    try {
      var stats = await API.get("/api/admin/stats");
      renderCards(stats || {});
    } catch (err) {
      grid.innerHTML = UI.renderEmpty(err.message || "加载失败");
    }
  }

  Layout.boot({
    active: "dashboard",
    onReady: function () {
      load();
      var btn = document.getElementById("refresh-btn");
      if (btn) btn.addEventListener("click", load);
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
