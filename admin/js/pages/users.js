/**
 * 用户管理：分页列表、筛选、启用/禁用、删除与重置密码。
 */
(function () {
  "use strict";

  var PAGE_SIZE = 20;
  var state = { page: 1, pages: 0, total: 0, items: [] };
  var els = {};

  var PROVIDER_TEXT = { local: "本地", github: "GitHub", oauth2: "OAuth2" };

  function cacheEls() {
    els.q = document.getElementById("q-input");
    els.provider = document.getElementById("provider-select");
    els.enabled = document.getElementById("enabled-select");
    els.filterBtn = document.getElementById("filter-btn");
    els.resetBtn = document.getElementById("reset-btn");
    els.refreshBtn = document.getElementById("refresh-btn");
    els.tbody = document.getElementById("users-tbody");
    els.pagination = document.getElementById("pagination");
    els.summary = document.getElementById("users-summary");
  }

  function buildQuery() {
    var params = new URLSearchParams();
    params.set("page", String(state.page));
    params.set("page_size", String(PAGE_SIZE));
    if (els.q.value.trim()) params.set("q", els.q.value.trim());
    if (els.provider.value) params.set("provider", els.provider.value);
    if (els.enabled.value) params.set("enabled", els.enabled.value);
    return params.toString();
  }

  function rowHtml(user) {
    return (
      "<tr data-id=\"" + user.id + "\">" +
        "<td>" + UI.escapeHtml(user.username) + "</td>" +
        "<td>" + UI.escapeHtml(user.email || "-") + "</td>" +
        "<td>" + UI.escapeHtml(user.nickname || "-") + "</td>" +
        "<td>" + UI.escapeHtml(PROVIDER_TEXT[user.provider] || user.provider || "-") + "</td>" +
        "<td>" + (user.enabled
          ? '<span class="badge badge-approved">已启用</span>'
          : '<span class="badge badge-hidden">已禁用</span>') + "</td>" +
        "<td>" + UI.formatDate(user.created_at) + "</td>" +
        "<td>" + UI.formatDate(user.last_login_at) + "</td>" +
        '<td><div class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-sm" data-act="toggle">' +
            (user.enabled ? "禁用" : "启用") + "</button>" +
          '<button type="button" class="btn btn-outline btn-sm" data-act="reset">重置密码</button>' +
          '<button type="button" class="btn btn-ghost btn-sm text-danger" data-act="delete">删除</button>' +
        "</div></td>" +
      "</tr>"
    );
  }

  function render() {
    if (!state.items.length) {
      els.tbody.innerHTML = '<tr><td colspan="8">' + UI.renderEmpty("没有符合条件的用户") + "</td></tr>";
      return;
    }
    els.tbody.innerHTML = state.items.map(rowHtml).join("");
    els.summary.textContent = "共 " + state.total + " 个用户";
  }

  async function load() {
    els.tbody.innerHTML = '<tr><td colspan="8"><div class="loading"><span class="spinner"></span>加载中…</div></td></tr>';
    try {
      var data = await API.get("/api/admin/users?" + buildQuery());
      state.items = (data && data.items) || [];
      state.page = (data && data.page) || 1;
      state.pages = (data && data.pages) || 0;
      state.total = (data && data.total) || 0;
      render();
      UI.renderPagination(els.pagination, { page: state.page, pages: state.pages }, function (p) {
        state.page = p;
        load();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    } catch (err) {
      els.tbody.innerHTML = '<tr><td colspan="8">' + UI.renderEmpty(err.message || "加载失败") + "</td></tr>";
      els.pagination.innerHTML = "";
    }
  }

  function findUser(id) {
    return state.items.find(function (u) { return String(u.id) === String(id); });
  }

  async function toggleEnabled(user) {
    try {
      await API.patch("/api/admin/users/" + user.id, { enabled: !user.enabled });
      UI.toast(user.enabled ? "已禁用该用户" : "已启用该用户", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  async function deleteUser(user) {
    var yes = await UI.confirmDialog(
      "确定删除用户「" + user.username + "」吗？其发表的评论将一并删除，操作不可恢复。", "删除");
    if (!yes) return;
    try {
      await API.del("/api/admin/users/" + user.id);
      UI.toast("用户已删除", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "删除失败", "error");
    }
  }

  function resetPassword(user) {
    UI.openModal(
      "重置密码",
      '<div class="form-field"><label>用户</label><input class="input" value="' +
        UI.escapeHtml(user.username) + '" readonly></div>' +
      '<div class="form-field"><label>新密码</label>' +
        '<input class="input" id="reset-password" type="password" autocomplete="new-password" placeholder="至少 6 位"></div>',
      async function (modal) {
        var value = modal.querySelector("#reset-password").value;
        if (!value || value.length < 6) {
          UI.toast("新密码长度至少 6 位", "warning");
          return false;
        }
        try {
          await API.post("/api/admin/users/" + user.id + "/reset-password", { new_password: value });
          UI.toast("密码已重置", "success");
          return true;
        } catch (err) {
          UI.toast(err.message || "重置失败", "error");
          return false;
        }
      }
    );
  }

  function bindEvents() {
    els.filterBtn.addEventListener("click", function () { state.page = 1; load(); });
    els.q.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { state.page = 1; load(); }
    });
    [els.provider, els.enabled].forEach(function (sel) {
      sel.addEventListener("change", function () { state.page = 1; load(); });
    });
    els.resetBtn.addEventListener("click", function () {
      els.q.value = "";
      els.provider.value = "";
      els.enabled.value = "";
      state.page = 1;
      load();
    });
    if (els.refreshBtn) els.refreshBtn.addEventListener("click", load);
    els.tbody.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-act]");
      if (!btn) return;
      var row = btn.closest("tr");
      var user = row && findUser(row.dataset.id);
      if (!user) return;
      var act = btn.dataset.act;
      if (act === "toggle") toggleEnabled(user);
      else if (act === "delete") deleteUser(user);
      else if (act === "reset") resetPassword(user);
    });
  }

  Layout.boot({
    active: "users",
    onReady: function () {
      cacheEls();
      bindEvents();
      if (els.tbody) {
        els.tbody.innerHTML = '<tr><td colspan="8">' + UI.renderEmpty("暂无用户") + "</td></tr>";
      }
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
