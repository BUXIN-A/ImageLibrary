/**
 * 主题设置：双标签管理「主题」与「主题配置」。
 * - 主题标签：展示基础/导航两套主题，支持启用与下载内置预设。
 * - 主题配置标签：仅管理当前启用主题的预设（上传/删除/设为默认）与导航主题统计开关。
 */
(function () {
  "use strict";

  var STAT_KEYS = [
    "folder_images",
    "total_images",
    "total_views",
    "total_comments",
    "total_downloads"
  ];

  var state = {
    data: null,
    tab: "themes",
    configTheme: "base"
  };
  var els = {};

  function cacheEls() {
    els.summary = document.getElementById("themes-summary");
    els.tabBtns = document.querySelectorAll(".tabs[role='tablist'] .tab-btn");
    els.tabThemes = document.getElementById("tab-themes");
    els.tabConfig = document.getElementById("tab-config");
    els.themesList = document.getElementById("themes-list");
    els.configThemeSummary = document.getElementById("config-theme-summary");
    els.presetList = document.getElementById("preset-list");
    els.presetForm = document.getElementById("preset-form");
    els.presetFile = document.getElementById("preset-file");
    els.presetName = document.getElementById("preset-name");
    els.presetId = document.getElementById("preset-id");
    els.presetHint = document.getElementById("preset-hint");
    els.presetUploadBtn = document.getElementById("preset-upload-btn");
    els.navStatsCard = document.getElementById("nav-stats-card");
    els.navStatsSave = document.getElementById("nav-stats-save");
    els.refreshBtn = document.getElementById("refresh-btn");
  }

  function themePath(themeId) {
    return "/api/admin/theme-settings/" + encodeURIComponent(themeId);
  }

  function findTheme(id) {
    var themes = (state.data && state.data.themes) || [];
    return themes.find(function (item) { return String(item.id) === String(id); }) || null;
  }

  function themeName(id) {
    var theme = findTheme(id);
    if (theme && theme.name) return theme.name;
    return id === "nav" ? "导航" : "基础";
  }

  function themesWithNames() {
    var list = (state.data && state.data.themes) || [];
    if (list.length) return list;
    return [
      { id: "base", name: "基础" },
      { id: "nav", name: "导航" }
    ];
  }

  function renderSummary() {
    if (!els.summary) return;
    var active = state.data && state.data.active_theme;
    els.summary.textContent = "当前启用主题：" + themeName(active || "base") +
      " · 共 " + themesWithNames().length + " 套主题";
  }

  /** 内置预设下载按钮：两套主题均可下载，不受当前启用主题限制。 */
  function presetDownloadButtons(theme) {
    var presets = (state.data && state.data.presets && state.data.presets[theme.id]) || [];
    return presets
      .filter(function (preset) { return preset && preset.builtin; })
      .map(function (preset) {
        return '<button type="button" class="btn btn-ghost btn-sm" data-act="download" data-preset-id="' +
          UI.escapeHtml(preset.id) + '">下载 ' + UI.escapeHtml(preset.name || preset.id) + "</button>";
      })
      .join("");
  }

  function themeCardHtml(theme) {
    var preview = theme.preview_url
      ? '<img src="' + UI.escapeHtml(UI.mediaUrl(theme.preview_url)) + '" loading="lazy" alt="">'
      : '<div class="media-placeholder">暂无预览图</div>';
    var badges = theme.active
      ? '<span class="badge badge-approved">当前启用</span>'
      : '<span class="badge badge-muted">未启用</span>';
    var action = theme.active
      ? '<button type="button" class="btn btn-outline btn-sm" disabled>已启用</button>'
      : '<button type="button" class="btn btn-primary btn-sm" data-act="activate">启用</button>';

    return (
      '<div class="image-card" data-id="' + UI.escapeHtml(theme.id) + '">' +
        '<div class="thumb-wrap">' + preview + '<span class="card-status">' + badges + "</span></div>" +
        '<div class="card-info">' +
          '<div class="card-title" title="' + UI.escapeHtml(theme.name) + '">' + UI.escapeHtml(theme.name) + "</div>" +
          '<div class="card-sub"><span>ID：' + UI.escapeHtml(theme.id) + "</span>" +
            (theme.version ? "<span>版本：" + UI.escapeHtml(theme.version) + "</span>" : "") +
          "</div>" +
          (theme.description ? '<div class="card-sub"><span>' + UI.escapeHtml(theme.description) + "</span></div>" : "") +
        "</div>" +
        '<div class="card-actions">' + action + presetDownloadButtons(theme) + "</div>" +
      "</div>"
    );
  }

  function renderThemes() {
    if (!els.themesList) return;
    var themes = themesWithNames();
    if (!themes.length) {
      els.themesList.innerHTML = UI.renderEmpty("暂无主题");
      return;
    }
    els.themesList.innerHTML = '<div class="image-grid">' + themes.map(themeCardHtml).join("") + "</div>";
  }

  function renderConfigSummary() {
    if (!els.configThemeSummary) return;
    els.configThemeSummary.textContent = "当前启用主题：" + themeName(state.configTheme) +
      "（预设与统计仅对本主题生效）";
  }

  function presetRowHtml(preset) {
    var badges = "";
    if (preset.default) badges += '<span class="badge badge-approved">默认</span>';
    if (preset.builtin) badges += '<span class="badge badge-muted">内置</span>';

    return (
      "<tr data-preset-id=\"" + UI.escapeHtml(preset.id) + "\">" +
        "<td>" + UI.escapeHtml(preset.name || preset.id) + "</td>" +
        "<td><code>" + UI.escapeHtml(preset.id) + "</code></td>" +
        "<td>" + (badges || '<span class="badge badge-muted">自定义</span>') + "</td>" +
        '<td><div class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-sm" data-act="default"' +
            (preset.default ? " disabled" : "") + ">设为默认</button>" +
          '<button type="button" class="btn btn-ghost btn-sm text-danger" data-act="delete">删除</button>' +
        "</div></td>" +
      "</tr>"
    );
  }

  function renderPresets() {
    if (!els.presetList) return;
    var presets = (state.data && state.data.presets && state.data.presets[state.configTheme]) || [];
    if (!presets.length) {
      els.presetList.innerHTML = UI.renderEmpty("暂无预设");
    } else {
      els.presetList.innerHTML =
        '<div class="table-wrap"><table class="table">' +
          "<thead><tr><th>名称</th><th>ID</th><th>标识</th><th>操作</th></tr></thead>" +
          "<tbody>" + presets.map(presetRowHtml).join("") + "</tbody>" +
        "</table></div>";
    }
    if (els.presetHint) {
      els.presetHint.textContent = "正在配置：" + themeName(state.configTheme);
    }
  }

  function renderNavStats() {
    if (!els.navStatsCard) return;
    var isNav = state.configTheme === "nav";
    els.navStatsCard.classList.toggle("hidden", !isNav);
    if (!isNav) return;
    var stats = (state.data && state.data.config && state.data.config.nav && state.data.config.nav.stats) || {};
    var boxes = els.navStatsCard.querySelectorAll("input[data-stat]");
    Array.prototype.forEach.call(boxes, function (box) {
      var key = box.dataset.stat;
      box.checked = stats[key] !== false;
    });
  }

  function renderAll() {
    renderSummary();
    renderThemes();
    renderConfigSummary();
    renderPresets();
    renderNavStats();
  }

  function switchTab(tab) {
    state.tab = tab === "config" ? "config" : "themes";
    Array.prototype.forEach.call(els.tabBtns || [], function (btn) {
      btn.classList.toggle("active", btn.dataset.tab === state.tab);
    });
    if (els.tabThemes) els.tabThemes.classList.toggle("hidden", state.tab !== "themes");
    if (els.tabConfig) els.tabConfig.classList.toggle("hidden", state.tab !== "config");
  }

  function applyPayload(data) {
    if (!data || !Array.isArray(data.themes)) return false;
    state.data = data;
    if (data.active_theme) state.configTheme = String(data.active_theme);
    renderAll();
    return true;
  }

  async function load() {
    if (els.themesList) {
      els.themesList.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    }
    if (els.presetList) {
      els.presetList.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    }
    try {
      var data = await API.get("/api/admin/theme-settings");
      if (!applyPayload(data)) throw new Error("主题设置数据格式异常");
    } catch (err) {
      if (els.themesList) els.themesList.innerHTML = UI.renderEmpty(err.message || "加载失败");
      if (els.presetList) els.presetList.innerHTML = UI.renderEmpty(err.message || "加载失败");
      if (els.summary) els.summary.textContent = "加载失败";
    }
  }

  async function activateTheme(theme) {
    try {
      var data = await API.put("/api/admin/theme-settings/active", { theme_id: theme.id });
      applyPayload(data);
      UI.toast("已启用「" + (theme.name || theme.id) + "」主题", "success");
    } catch (err) {
      UI.toast(err.message || "启用失败", "error");
    }
  }

  async function downloadPreset(themeId, preset) {
    try {
      await API.downloadGet(
        themePath(themeId) + "/presets/" + encodeURIComponent(preset.id) + "/download",
        themeId + "-" + preset.id + ".css"
      );
      UI.toast("预设已下载", "success");
    } catch (err) {
      UI.toast(err.message || "下载失败", "error");
    }
  }

  async function setDefaultPreset(presetId) {
    try {
      var data = await API.put(
        themePath(state.configTheme) + "/presets/" + encodeURIComponent(presetId) + "/default"
      );
      applyPayload(data);
      UI.toast("已设为默认预设", "success");
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  async function deletePreset(preset) {
    var yes = await UI.confirmDialog(
      "确定删除预设「" + (preset.name || preset.id) + "」吗？该操作不可恢复。",
      "删除"
    );
    if (!yes) return;
    try {
      var data = await API.del(
        themePath(state.configTheme) + "/presets/" + encodeURIComponent(preset.id)
      );
      applyPayload(data);
      UI.toast("预设已删除", "success");
    } catch (err) {
      UI.toast(err.message || "删除失败", "error");
    }
  }

  async function uploadPreset(e) {
    e.preventDefault();
    var file = els.presetFile && els.presetFile.files && els.presetFile.files[0];
    if (!file) {
      UI.toast("请选择预设 CSS 文件", "warning");
      return;
    }
    if (!/\.css$/i.test(file.name)) {
      UI.toast("预设文件必须为 .css 格式", "warning");
      return;
    }

    var fd = new FormData();
    fd.append("file", file);
    var name = els.presetName ? els.presetName.value.trim() : "";
    var presetId = els.presetId ? els.presetId.value.trim() : "";
    if (name) fd.append("name", name);
    if (presetId) fd.append("id", presetId);

    els.presetUploadBtn.disabled = true;
    try {
      var data = await API.postForm(themePath(state.configTheme) + "/presets", fd);
      applyPayload(data);
      els.presetForm.reset();
      UI.toast("预设上传成功", "success");
    } catch (err) {
      UI.toast(err.message || "上传失败", "error");
    } finally {
      els.presetUploadBtn.disabled = false;
    }
  }

  async function saveNavStats() {
    var stats = {};
    var boxes = els.navStatsCard.querySelectorAll("input[data-stat]");
    Array.prototype.forEach.call(boxes, function (box) {
      stats[box.dataset.stat] = box.checked;
    });
    STAT_KEYS.forEach(function (key) {
      if (typeof stats[key] !== "boolean") stats[key] = true;
    });

    els.navStatsSave.disabled = true;
    try {
      var data = await API.put(themePath("nav") + "/config", { stats: stats });
      applyPayload(data);
      UI.toast("统计开关已保存", "success");
    } catch (err) {
      UI.toast(err.message || "保存失败", "error");
    } finally {
      els.navStatsSave.disabled = false;
    }
  }

  function bindEvents() {
    Array.prototype.forEach.call(els.tabBtns || [], function (btn) {
      btn.addEventListener("click", function () { switchTab(btn.dataset.tab); });
    });

    if (els.themesList) {
      els.themesList.addEventListener("click", function (e) {
        var btn = e.target.closest("button[data-act]");
        if (!btn || btn.disabled) return;
        var card = btn.closest(".image-card");
        var theme = card && findTheme(card.dataset.id);
        if (!theme) return;
        if (btn.dataset.act === "download") {
          var presets = (state.data && state.data.presets && state.data.presets[theme.id]) || [];
          var preset = presets.find(function (item) { return item.id === btn.dataset.presetId; });
          if (preset) downloadPreset(theme.id, preset);
          return;
        }
        if (btn.dataset.act === "activate") activateTheme(theme);
      });
    }

    if (els.presetList) {
      els.presetList.addEventListener("click", function (e) {
        var btn = e.target.closest("button[data-act]");
        if (!btn || btn.disabled) return;
        var row = btn.closest("tr");
        if (!row) return;
        var presetId = row.dataset.presetId;
        var presets = (state.data && state.data.presets && state.data.presets[state.configTheme]) || [];
        var preset = presets.find(function (item) { return item.id === presetId; });
        if (!preset) return;
        if (btn.dataset.act === "default") setDefaultPreset(preset.id);
        else if (btn.dataset.act === "delete") deletePreset(preset);
      });
    }

    if (els.presetForm) els.presetForm.addEventListener("submit", uploadPreset);
    if (els.navStatsSave) els.navStatsSave.addEventListener("click", saveNavStats);
    if (els.refreshBtn) els.refreshBtn.addEventListener("click", load);
  }

  Layout.boot({
    active: "themes",
    onReady: function () {
      cacheEls();
      bindEvents();
      switchTab("themes");
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
