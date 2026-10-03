/**
 * 站点设置：站点信息、SEO、功能开关、favicon 与便捷链接。
 */
(function () {
  "use strict";

  var API_BASE = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "";
  var els = {};

  function cacheEls() {
    els.form = document.getElementById("site-form");
    els.siteName = document.getElementById("site-name");
    els.siteTitle = document.getElementById("site-title");
    els.siteDescription = document.getElementById("site-description");
    els.siteKeywords = document.getElementById("site-keywords");
    els.footerText = document.getElementById("footer-text");
    els.allowIndex = document.getElementById("allow-index");
    els.robotsExtra = document.getElementById("robots-extra");
    els.sitemapEnabled = document.getElementById("sitemap-enabled");
    els.commentsEnabled = document.getElementById("comments-enabled");
    els.saveBtn = document.getElementById("site-save");
    els.refreshBtn = document.getElementById("refresh-btn");
    els.faviconPreview = document.getElementById("favicon-preview");
    els.faviconHint = document.getElementById("favicon-hint");
    els.faviconFile = document.getElementById("favicon-file");
    els.faviconUpload = document.getElementById("favicon-upload");
    els.faviconClear = document.getElementById("favicon-clear");
  }

  function setFaviconPreview(favicon) {
    if (favicon) {
      els.faviconPreview.src = API_BASE + "/api/favicon?t=" + Date.now();
      els.faviconPreview.classList.remove("hidden");
      els.faviconHint.textContent = "已设置站点图标";
    } else {
      els.faviconPreview.removeAttribute("src");
      els.faviconPreview.classList.add("hidden");
      els.faviconHint.textContent = "未设置站点图标";
    }
  }

  function fill(data) {
    data = data || {};
    els.siteName.value = data.site_name || "";
    els.siteTitle.value = data.site_title || "";
    els.siteDescription.value = data.site_description || "";
    els.siteKeywords.value = data.site_keywords || "";
    els.footerText.value = data.footer_text || "";
    els.allowIndex.checked = data.allow_index !== false;
    els.robotsExtra.value = data.robots_extra || "";
    els.sitemapEnabled.checked = data.sitemap_enabled !== false;
    els.commentsEnabled.checked = data.comments_enabled !== false;
    setFaviconPreview(data.favicon || "");
  }

  async function load() {
    try {
      var data = await API.get("/api/admin/site");
      fill(data);
    } catch (err) {
      UI.toast("站点设置加载失败：" + err.message, "error");
    }
  }

  function bindForm() {
    els.form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var siteName = els.siteName.value.trim();
      if (!siteName) { UI.toast("请填写站点名称", "warning"); return; }
      els.saveBtn.disabled = true;
      try {
        await API.put("/api/admin/site", {
          site_name: siteName,
          site_title: els.siteTitle.value.trim(),
          site_description: els.siteDescription.value.trim(),
          site_keywords: els.siteKeywords.value.trim(),
          footer_text: els.footerText.value.trim(),
          allow_index: els.allowIndex.checked,
          robots_extra: els.robotsExtra.value,
          sitemap_enabled: els.sitemapEnabled.checked,
          comments_enabled: els.commentsEnabled.checked
        });
        UI.toast("站点设置已保存", "success");
      } catch (err) {
        UI.toast(err.message || "保存失败", "error");
      } finally {
        els.saveBtn.disabled = false;
      }
    });
  }

  function bindFavicon() {
    els.faviconUpload.addEventListener("click", async function () {
      var file = els.faviconFile.files && els.faviconFile.files[0];
      if (!file) { UI.toast("请先选择图标文件", "warning"); return; }
      var fd = new FormData();
      fd.append("file", file);
      els.faviconUpload.disabled = true;
      try {
        var data = await API.postForm("/api/admin/site/favicon", fd);
        setFaviconPreview((data && data.favicon) || "/api/favicon");
        els.faviconFile.value = "";
        UI.toast("图标已上传", "success");
      } catch (err) {
        UI.toast(err.message || "上传失败", "error");
      } finally {
        els.faviconUpload.disabled = false;
      }
    });

    els.faviconClear.addEventListener("click", async function () {
      var yes = await UI.confirmDialog("确定清除站点图标吗？", "清除");
      if (!yes) return;
      try {
        await API.put("/api/admin/site", { favicon: "" });
        setFaviconPreview("");
        UI.toast("图标已清除", "success");
      } catch (err) {
        UI.toast(err.message || "清除失败", "error");
      }
    });

    els.faviconPreview.addEventListener("error", function () {
      els.faviconPreview.classList.add("hidden");
      els.faviconHint.textContent = "图标加载失败";
    });
  }

  Layout.boot({
    active: "site-settings",
    onReady: function () {
      cacheEls();
      bindForm();
      bindFavicon();
      if (els.refreshBtn) els.refreshBtn.addEventListener("click", load);
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
