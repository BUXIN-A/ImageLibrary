/**
 * 主题管理：列表展示、上传、下载、删除、设为默认与启用/禁用。
 */
(function () {
  "use strict";

  var API_BASE = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "";
  var state = { themes: [], enabled: [], defaultTheme: "" };
  var els = {};

  function cacheEls() {
    els.list = document.getElementById("themes-list");
    els.summary = document.getElementById("themes-summary");
    els.file = document.getElementById("theme-file");
    els.uploadBtn = document.getElementById("upload-theme");
    els.refreshBtn = document.getElementById("refresh-btn");
  }

  function parseEnabled(raw) {
    if (!raw) return [];
    try {
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch (err) {
      return [];
    }
  }

  function isEnabled(id) {
    return state.enabled.indexOf(id) !== -1;
  }

  function cardHtml(theme) {
    var badges = "";
    badges += '<span class="badge ' + (theme.source === "custom" ? "badge-primary" : "badge-muted") + '">' +
      (theme.source === "custom" ? "自定义" : "内置") + "</span>";
    if (theme.id === state.defaultTheme) badges += '<span class="badge badge-approved">默认</span>';
    badges += isEnabled(theme.id)
      ? '<span class="badge badge-approved">已启用</span>'
      : '<span class="badge badge-hidden">已禁用</span>';

    var preview = theme.has_preview
      ? '<img src="' + API_BASE + "/api/themes/" + encodeURIComponent(theme.id) + '/preview" loading="lazy" alt="">'
      : '<div class="empty-state" style="padding:var(--space-6) 0;">无预览图</div>';

    var meta = [];
    if (theme.author) meta.push("作者：" + UI.escapeHtml(theme.author));
    if (theme.version) meta.push("版本：" + UI.escapeHtml(theme.version));

    return (
      '<div class="image-card" data-id="' + UI.escapeHtml(theme.id) + '">' +
        '<div class="thumb-wrap">' + preview + '<span class="card-status">' + badges + "</span></div>" +
        '<div class="card-info">' +
          '<div class="card-title" title="' + UI.escapeHtml(theme.name) + '">' + UI.escapeHtml(theme.name) + "</div>" +
          '<div class="card-sub"><span>ID：' + UI.escapeHtml(theme.id) + "</span></div>" +
          (meta.length ? '<div class="card-sub"><span>' + meta.join("　") + "</span></div>" : "") +
          (theme.description ? '<div class="card-sub"><span>' + UI.escapeHtml(theme.description) + "</span></div>" : "") +
        "</div>" +
        '<div class="card-actions">' +
          '<button type="button" class="btn btn-outline btn-sm" data-act="download">下载</button>' +
          (theme.id === state.defaultTheme ? "" :
            '<button type="button" class="btn btn-outline btn-sm" data-act="default">设为默认</button>') +
          '<button type="button" class="btn btn-outline btn-sm" data-act="toggle">' +
            (isEnabled(theme.id) ? "禁用" : "启用") + "</button>" +
          (theme.source === "custom"
            ? '<button type="button" class="btn btn-ghost btn-sm text-danger" data-act="delete">删除</button>'
            : "") +
        "</div>" +
      "</div>"
    );
  }

  function render() {
    if (!state.themes.length) {
      els.list.innerHTML = UI.renderEmpty("暂无主题");
      return;
    }
    els.list.innerHTML = '<div class="image-grid">' + state.themes.map(cardHtml).join("") + "</div>";
  }

  function renderSummary() {
    var defaultName = state.defaultTheme;
    var found = state.themes.find(function (t) { return t.id === state.defaultTheme; });
    if (found && found.name) defaultName = found.name;
    els.summary.textContent = "当前默认主题：" + (defaultName || "未设置") +
      " · 已启用 " + state.enabled.length + " / " + state.themes.length + " 个";
  }

  async function load() {
    els.list.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    try {
      var results = await Promise.all([
        API.get("/api/admin/themes"),
        API.get("/api/admin/settings")
      ]);
      state.themes = results[0] || [];
      var settings = results[1] || {};
      state.defaultTheme = settings.default_theme || "";
      state.enabled = parseEnabled(settings.enabled_themes);
      renderSummary();
      render();
    } catch (err) {
      els.list.innerHTML = UI.renderEmpty(err.message || "加载失败");
      els.summary.textContent = "加载失败";
    }
  }

  function findTheme(id) {
    return state.themes.find(function (t) { return String(t.id) === String(id); });
  }

  function uploadTheme() {
    var file = els.file.files && els.file.files[0];
    if (!file) { UI.toast("请选择主题 ZIP 文件", "warning"); return; }
    var fd = new FormData();
    fd.append("file", file);
    els.uploadBtn.disabled = true;
    API.postForm("/api/admin/themes", fd)
      .then(function () {
        UI.toast("主题上传成功", "success");
        els.file.value = "";
        load();
      })
      .catch(function (err) { UI.toast(err.message || "上传失败", "error"); })
      .finally(function () { els.uploadBtn.disabled = false; });
  }

  async function downloadTheme(theme) {
    try {
      var res = await fetch(API_BASE + "/api/admin/themes/" + encodeURIComponent(theme.id) + "/download", {
        headers: { Authorization: "Bearer " + API.getToken() }
      });
      if (!res.ok) {
        var data = null;
        try { data = await res.json(); } catch (e) { /* ignore */ }
        throw new Error((data && data.detail) || ("下载失败（HTTP " + res.status + "）"));
      }
      var blob = await res.blob();
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = theme.id + "-theme.zip";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1500);
    } catch (err) {
      UI.toast(err.message || "下载失败", "error");
    }
  }

  async function setDefault(theme) {
    try {
      await API.post("/api/admin/themes/" + encodeURIComponent(theme.id) + "/set-default");
      UI.toast("已设为默认主题", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  async function toggleEnabled(theme) {
    var wasEnabled = isEnabled(theme.id);
    var next = state.enabled.slice();
    var idx = next.indexOf(theme.id);
    if (idx === -1) next.push(theme.id);
    else next.splice(idx, 1);
    try {
      await API.put("/api/admin/settings", { enabled_themes: next });
      UI.toast(wasEnabled ? "已禁用该主题" : "已启用该主题", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  async function deleteTheme(theme) {
    var yes = await UI.confirmDialog("确定删除自定义主题「" + theme.name + "」吗？该操作不可恢复。", "删除");
    if (!yes) return;
    try {
      await API.del("/api/admin/themes/" + encodeURIComponent(theme.id));
      UI.toast("主题已删除", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "删除失败", "error");
    }
  }

  function bindEvents() {
    els.uploadBtn.addEventListener("click", function () { els.file.click(); });
    els.file.addEventListener("change", uploadTheme);
    els.refreshBtn.addEventListener("click", load);
    els.list.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-act]");
      if (!btn) return;
      var card = btn.closest(".image-card");
      var theme = card && findTheme(card.dataset.id);
      if (!theme) return;
      var act = btn.dataset.act;
      if (act === "download") downloadTheme(theme);
      else if (act === "default") setDefault(theme);
      else if (act === "toggle") toggleEnabled(theme);
      else if (act === "delete") deleteTheme(theme);
    });
  }

  Layout.boot({
    active: "themes",
    onReady: function () {
      cacheEls();
      bindEvents();
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
