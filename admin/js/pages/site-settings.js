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
    els.apiBaseUrl = document.getElementById("api-base-url");
    els.frontendBaseUrl = document.getElementById("frontend-base-url");
    els.adminApiBaseUrl = document.getElementById("admin-api-base-url");
    els.apiBaseResolved = document.getElementById("api-base-resolved");
    els.frontendBaseResolved = document.getElementById("frontend-base-resolved");
    els.adminApiBaseResolved = document.getElementById("admin-api-base-resolved");
    els.robotsUrl = document.getElementById("robots-url");
    els.sitemapUrl = document.getElementById("sitemap-url");
    els.robotsLink = document.getElementById("robots-link");
    els.sitemapLink = document.getElementById("sitemap-link");
    els.allowIndex = document.getElementById("allow-index");
    els.robotsExtra = document.getElementById("robots-extra");
    els.sitemapEnabled = document.getElementById("sitemap-enabled");
    els.commentsEnabled = document.getElementById("comments-enabled");
    els.siteCheckOnStartup = document.getElementById("site-check-on-startup");
    els.visitLogEnabled = document.getElementById("visit-log-enabled");
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

  /** 展示实际生效的站点地址，并同步 robots/sitemap 便捷链接。 */
  function setResolved(data) {
    data = data || {};
    var apiBase = data.resolved_api_base_url || data.api_base_url || "";
    var adminApiBase = data.resolved_admin_api_base_url || apiBase;
    var frontendBase = (data.resolved_frontend_base_url || data.frontend_base_url || "").replace(/\/$/, "");
    els.apiBaseResolved.textContent = apiBase || "-";
    els.adminApiBaseResolved.textContent = adminApiBase || "-";
    els.frontendBaseResolved.textContent = frontendBase || "-";
    if (frontendBase) {
      var robotsUrl = frontendBase + "/robots.txt";
      var sitemapUrl = frontendBase + "/sitemap.xml";
      els.robotsUrl.value = robotsUrl;
      els.sitemapUrl.value = sitemapUrl;
      els.robotsLink.href = robotsUrl;
      els.sitemapLink.href = sitemapUrl;
    }
  }

  // ---------------- 站点地址：专门按钮 + 弹窗（二次校验 + 浏览器探测） ----------------

  var ADDRESS_TARGETS = [
    { id: "api", label: "API 站点地址" },
    { id: "admin", label: "后台专属 API 站点地址" },
    { id: "frontend", label: "前台站点地址" }
  ];

  /** 归一化地址输入：补全协议（按当前页面协议）、去掉尾部斜杠。 */
  function normalizeAddress(raw) {
    var value = (raw || "").trim().replace(/\/+$/, "");
    if (!value) return "";
    if (!/^https?:\/\//i.test(value)) {
      value = (location.protocol === "https:" ? "https://" : "http://") + value;
    }
    return value;
  }

  /** 校验地址格式：http(s)://主机[:端口]，不允许路径。 */
  function isValidAddress(value) {
    return /^https?:\/\/[^\s/]+(:\d+)?$/i.test(value);
  }

  /**
   * 探测地址是否可用。
   * API 类地址请求 /api/health（同时验证连通性与跨域）；前台地址仅探测可达性。
   */
  async function probeAddress(base, isApi) {
    var sep = "?t=" + Date.now();
    if (!isApi) {
      await fetch(base + "/" + sep, { mode: "no-cors", cache: "no-store" });
      return;
    }
    var res = await fetch(base + "/api/health" + sep, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    var data = await res.json();
    if (!data || data.status !== "ok") throw new Error("接口返回内容异常");
  }

  function targetsHtml() {
    return '<div class="form-field"><label>设置目标（可多选）</label>' +
      ADDRESS_TARGETS.map(function (item, index) {
        return '<label class="checkbox"><input type="checkbox" class="addr-target" value="' +
          item.id + '"' + (index === 0 ? " checked" : "") + '><span>' +
          UI.escapeHtml(item.label) + "</span></label>";
      }).join("") +
      "</div>";
  }

  function credentialsHtml() {
    return '<div class="form-field"><label for="addr-user">管理员账户</label>' +
        '<input class="input" id="addr-user" type="text" autocomplete="username"></div>' +
      '<div class="form-field"><label for="addr-pass">管理员密码</label>' +
        '<input class="input" id="addr-pass" type="password" autocomplete="current-password"></div>' +
      '<div class="form-hint" id="addr-hint"></div>';
  }

  function readTargets(mask) {
    var list = [];
    mask.querySelectorAll(".addr-target").forEach(function (box) {
      if (box.checked) list.push(box.value);
    });
    return list;
  }

  function setHint(mask, html) {
    var hint = mask.querySelector("#addr-hint");
    if (hint) hint.innerHTML = html;
  }

  function fail(mask, message) {
    setHint(mask, '<span class="text-danger">' + UI.escapeHtml(message) + "</span>");
    return false;
  }

  /** 读取并校验账号密码，缺失时提示并返回 null。 */
  function readCredentials(mask) {
    var username = mask.querySelector("#addr-user").value.trim();
    var password = mask.querySelector("#addr-pass").value;
    if (!username || !password) return null;
    return { username: username, password: password };
  }

  async function submitAddress(mask, targets, baseUrl) {
    var cred = readCredentials(mask);
    if (!cred) return fail(mask, "请填写管理员账户与密码");
    setHint(mask, "正在保存…");
    try {
      var data = await API.post("/api/admin/site/address", {
        targets: targets,
        base_url: baseUrl,
        username: cred.username,
        password: cred.password
      });
      fill(data);
      UI.toast(baseUrl ? "站点地址已保存，页面将刷新以生效" : "站点地址已清除，页面将刷新", "success");
      setTimeout(function () { location.reload(); }, 1200);
      return true;
    } catch (err) {
      return fail(mask, err.message || "保存失败");
    }
  }

  /** 「设置站点地址」弹窗确认：先探测新地址，通过后才提交。 */
  async function confirmSetAddress(mask) {
    var targets = readTargets(mask);
    if (!targets.length) return fail(mask, "请至少选择一个设置目标");
    var value = normalizeAddress(mask.querySelector("#addr-value").value);
    if (!value) return fail(mask, "请填写站点地址");
    if (!isValidAddress(value)) {
      return fail(mask, "地址格式不正确，应为 IP:端口 或 域名，例如 192.168.1.10:8080");
    }
    if (!readCredentials(mask)) return fail(mask, "请填写管理员账户与密码");

    setHint(mask, "正在探测新地址：" + UI.escapeHtml(value) + " …");
    try {
      if (targets.indexOf("api") !== -1) await probeAddress(value, true);
      if (targets.indexOf("admin") !== -1) await probeAddress(value, true);
      if (targets.indexOf("frontend") !== -1) await probeAddress(value, false);
    } catch (err) {
      return fail(mask, "新地址探测失败：" + (err.message || "无法访问") +
        "（已取消保存，原配置未改动）");
    }
    return submitAddress(mask, targets, value);
  }

  /** 「清除站点地址」弹窗确认：清空三项，恢复自动推断。 */
  async function confirmClearAddress(mask) {
    return submitAddress(mask, ["api", "admin", "frontend"], "");
  }

  function bindAddress() {
    var setBtn = document.getElementById("addr-set-btn");
    var clearBtn = document.getElementById("addr-clear-btn");

    if (setBtn) {
      setBtn.addEventListener("click", function () {
        UI.openModal(
          "设置站点地址",
          '<div class="form-hint">保存前会用当前浏览器探测该地址是否可用，探测通过才会写入；探测失败不会改动现有配置。</div>' +
            targetsHtml() +
            '<div class="form-field"><label for="addr-value">站点地址（IP:端口 或 域名）</label>' +
              '<input class="input" id="addr-value" type="text" placeholder="如 192.168.1.10:8080 或 galleryapi.example.com" autocomplete="off">' +
              '<div class="form-hint">未填写协议时按当前页面协议自动补全（当前为 ' +
                UI.escapeHtml(location.protocol) + "）</div></div>" +
            credentialsHtml(),
          confirmSetAddress
        );
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        UI.openModal(
          "清除站点地址",
          '<div class="form-hint">将清除 <strong>API 站点地址</strong>、<strong>前台站点地址</strong> 与 <strong>后台专属 API 站点地址</strong>，' +
            "恢复为按 <code>PUBLIC_HOST</code> 或访问主机自动推断。</div>" +
            credentialsHtml(),
          confirmClearAddress
        );
      });
    }
  }

  function fill(data) {
    data = data || {};
    els.siteName.value = data.site_name || "";
    els.siteTitle.value = data.site_title || "";
    els.siteDescription.value = data.site_description || "";
    els.siteKeywords.value = data.site_keywords || "";
    els.footerText.value = data.footer_text || "";
    els.apiBaseUrl.value = data.api_base_url || "";
    els.frontendBaseUrl.value = data.frontend_base_url || "";
    els.adminApiBaseUrl.value = data.admin_api_base_url || "";
    els.allowIndex.checked = data.allow_index !== false;
    els.robotsExtra.value = data.robots_extra || "";
    els.sitemapEnabled.checked = data.sitemap_enabled !== false;
    els.commentsEnabled.checked = data.comments_enabled !== false;
    els.siteCheckOnStartup.checked = data.site_check_on_startup !== false;
    els.visitLogEnabled.checked = data.visit_log_enabled !== false;
    setResolved(data);
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
          comments_enabled: els.commentsEnabled.checked,
          site_check_on_startup: els.siteCheckOnStartup.checked,
          visit_log_enabled: els.visitLogEnabled.checked
        });
        UI.toast("站点设置已保存", "success");
        load();
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
      bindAddress();
      if (els.refreshBtn) els.refreshBtn.addEventListener("click", load);
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
