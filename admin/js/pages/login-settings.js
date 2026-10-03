/**
 * 登录设置：本地 / GitHub / 自定义 OAuth2 登录配置。
 * secret 语义：不修改则不提交；更新提交新值；清除提交空字符串。
 */
(function () {
  "use strict";

  var els = {};
  var state = {
    secretSet: { github: false, oauth2: false },
    secretMode: { github: null, oauth2: null }
  };

  function cacheEls() {
    els.form = document.getElementById("login-form");
    els.saveBtn = document.getElementById("login-save");
    els.refreshBtn = document.getElementById("refresh-btn");

    els.localEnabled = document.getElementById("login-local-enabled");

    els.githubEnabled = document.getElementById("login-github-enabled");
    els.githubClientId = document.getElementById("github-client-id");
    els.githubSecretStatus = document.getElementById("github-secret-status");
    els.githubSecretInput = document.getElementById("github-secret-input");
    els.githubSecretClear = document.getElementById("github-secret-clear");
    els.githubCallback = document.getElementById("github-callback");

    els.oauth2Enabled = document.getElementById("login-oauth2-enabled");
    els.oauth2ClientId = document.getElementById("oauth2-client-id");
    els.oauth2Scope = document.getElementById("oauth2-scope");
    els.oauth2SecretStatus = document.getElementById("oauth2-secret-status");
    els.oauth2SecretInput = document.getElementById("oauth2-secret-input");
    els.oauth2SecretClear = document.getElementById("oauth2-secret-clear");
    els.oauth2AuthorizeUrl = document.getElementById("oauth2-authorize-url");
    els.oauth2TokenUrl = document.getElementById("oauth2-token-url");
    els.oauth2UserinfoUrl = document.getElementById("oauth2-userinfo-url");
    els.oauth2UserIdField = document.getElementById("oauth2-user-id-field");
    els.oauth2UsernameField = document.getElementById("oauth2-username-field");
    els.oauth2NicknameField = document.getElementById("oauth2-nickname-field");
    els.oauth2EmailField = document.getElementById("oauth2-email-field");
    els.oauth2AvatarField = document.getElementById("oauth2-avatar-field");
    els.oauth2Callback = document.getElementById("oauth2-callback");
  }

  function renderSecretStatus(kind) {
    var statusEl = kind === "github" ? els.githubSecretStatus : els.oauth2SecretStatus;
    var mode = state.secretMode[kind];
    var text, cls;
    if (mode === "clear") { text = "将清除"; cls = "badge-rejected"; }
    else if (mode === "update") { text = "将更新"; cls = "badge-pending"; }
    else if (state.secretSet[kind]) { text = "已设置"; cls = "badge-approved"; }
    else { text = "未设置"; cls = "badge-muted"; }
    statusEl.textContent = text;
    statusEl.className = "badge " + cls;
  }

  function fill(data) {
    data = data || {};
    els.localEnabled.checked = !!data.login_local_enabled;

    els.githubEnabled.checked = !!data.login_github_enabled;
    els.githubClientId.value = data.github_client_id || "";
    els.githubCallback.value = data.github_callback_url || "";
    state.secretSet.github = !!data.github_client_secret_set;
    state.secretMode.github = null;
    els.githubSecretInput.value = "";
    renderSecretStatus("github");

    els.oauth2Enabled.checked = !!data.login_oauth2_enabled;
    els.oauth2ClientId.value = data.oauth2_client_id || "";
    els.oauth2Scope.value = data.oauth2_scope || "";
    els.oauth2AuthorizeUrl.value = data.oauth2_authorize_url || "";
    els.oauth2TokenUrl.value = data.oauth2_token_url || "";
    els.oauth2UserinfoUrl.value = data.oauth2_userinfo_url || "";
    els.oauth2UserIdField.value = data.oauth2_user_id_field || "";
    els.oauth2UsernameField.value = data.oauth2_username_field || "";
    els.oauth2NicknameField.value = data.oauth2_nickname_field || "";
    els.oauth2EmailField.value = data.oauth2_email_field || "";
    els.oauth2AvatarField.value = data.oauth2_avatar_field || "";
    els.oauth2Callback.value = data.oauth2_callback_url || "";
    state.secretSet.oauth2 = !!data.oauth2_client_secret_set;
    state.secretMode.oauth2 = null;
    els.oauth2SecretInput.value = "";
    renderSecretStatus("oauth2");
  }

  async function load() {
    try {
      var data = await API.get("/api/admin/login-settings");
      fill(data);
    } catch (err) {
      UI.toast("登录设置加载失败：" + err.message, "error");
    }
  }

  function bindSecret(kind, inputEl, clearEl) {
    inputEl.addEventListener("input", function () {
      state.secretMode[kind] = inputEl.value ? "update" : null;
      renderSecretStatus(kind);
    });
    clearEl.addEventListener("click", function () {
      inputEl.value = "";
      state.secretMode[kind] = "clear";
      renderSecretStatus(kind);
    });
  }

  function secretPayloadKind(kind, inputEl) {
    var mode = state.secretMode[kind];
    if (mode === "clear") return "";
    if (mode === "update" && inputEl.value) return inputEl.value;
    return undefined;
  }

  function bindForm() {
    els.form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var payload = {
        login_local_enabled: els.localEnabled.checked,
        login_github_enabled: els.githubEnabled.checked,
        github_client_id: els.githubClientId.value.trim(),
        login_oauth2_enabled: els.oauth2Enabled.checked,
        oauth2_client_id: els.oauth2ClientId.value.trim(),
        oauth2_scope: els.oauth2Scope.value.trim(),
        oauth2_authorize_url: els.oauth2AuthorizeUrl.value.trim(),
        oauth2_token_url: els.oauth2TokenUrl.value.trim(),
        oauth2_userinfo_url: els.oauth2UserinfoUrl.value.trim(),
        oauth2_user_id_field: els.oauth2UserIdField.value.trim(),
        oauth2_username_field: els.oauth2UsernameField.value.trim(),
        oauth2_nickname_field: els.oauth2NicknameField.value.trim(),
        oauth2_email_field: els.oauth2EmailField.value.trim(),
        oauth2_avatar_field: els.oauth2AvatarField.value.trim()
      };
      var githubSecret = secretPayloadKind("github", els.githubSecretInput);
      if (githubSecret !== undefined) payload.github_client_secret = githubSecret;
      var oauth2Secret = secretPayloadKind("oauth2", els.oauth2SecretInput);
      if (oauth2Secret !== undefined) payload.oauth2_client_secret = oauth2Secret;

      els.saveBtn.disabled = true;
      try {
        var data = await API.put("/api/admin/login-settings", payload);
        fill(data);
        UI.toast("登录设置已保存", "success");
      } catch (err) {
        UI.toast(err.message || "保存失败", "error");
      } finally {
        els.saveBtn.disabled = false;
      }
    });
  }

  function bindCopyButtons() {
    var buttons = document.querySelectorAll("button[data-copy]");
    Array.prototype.forEach.call(buttons, function (btn) {
      btn.addEventListener("click", async function () {
        var input = document.getElementById(btn.dataset.copy);
        if (!input || !input.value) { UI.toast("暂无可复制的内容", "warning"); return; }
        var ok = await UI.copyToClipboard(input.value);
        UI.toast(ok ? "已复制" : "复制失败，请手动复制", ok ? "success" : "error");
      });
    });
  }

  Layout.boot({
    active: "login-settings",
    onReady: function () {
      cacheEls();
      bindForm();
      bindSecret("github", els.githubSecretInput, els.githubSecretClear);
      bindSecret("oauth2", els.oauth2SecretInput, els.oauth2SecretClear);
      bindCopyButtons();
      if (els.refreshBtn) els.refreshBtn.addEventListener("click", load);
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
