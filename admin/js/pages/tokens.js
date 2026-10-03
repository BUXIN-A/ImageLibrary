/**
 * 上传 Token 管理：列表、新建、启用/禁用、删除、重新生成、复制。
 */
(function () {
  "use strict";

  var state = { tokens: [] };
  var els = {};

  function cacheEls() {
    els.tbody = document.getElementById("token-tbody");
    els.newBtn = document.getElementById("new-token-btn");
  }

  function isExpired(token) {
    if (!token.expires_at) return false;
    var t = new Date(token.expires_at).getTime();
    return isFinite(t) && t < Date.now();
  }

  function statusHtml(token) {
    if (isExpired(token)) return '<span class="dot dot-expired"></span>已过期';
    if (!token.enabled) return '<span class="dot dot-off"></span>已禁用';
    return '<span class="dot dot-on"></span>启用中';
  }

  function render() {
    if (!state.tokens.length) {
      els.tbody.innerHTML = '<tr><td colspan="9">' + UI.renderEmpty("暂无 Token，点击右上角新建") + "</td></tr>";
      return;
    }
    els.tbody.innerHTML = state.tokens.map(function (token) {
      var used = token.used_uploads || 0;
      var max = token.max_uploads === null || token.max_uploads === undefined ? "不限" : token.max_uploads;
      var remaining = token.remaining === null || token.remaining === undefined ? "不限" : token.remaining;
      var maxFile = token.max_file_size ? UI.formatSize(token.max_file_size) : "跟随全局";
      return (
        '<tr data-id="' + token.id + '">' +
          "<td>" + UI.escapeHtml(token.note || "-") + "</td>" +
          '<td><span class="mono" title="' + UI.escapeHtml(token.token) + '">' +
            UI.escapeHtml(shorten(token.token)) + "</span></td>" +
          "<td>" + statusHtml(token) + "</td>" +
          "<td>" + (token.expires_at ? UI.formatDate(token.expires_at) : "永久") + "</td>" +
          "<td>" + used + " / " + max + "</td>" +
          "<td>" + remaining + "</td>" +
          "<td>" + maxFile + "</td>" +
          "<td>" + (token.last_used_at ? UI.formatDate(token.last_used_at) : "-") + "</td>" +
          '<td><div class="row-actions">' +
            '<button type="button" class="btn btn-outline btn-sm" data-act="copy">复制</button>' +
            '<button type="button" class="btn btn-outline btn-sm" data-act="toggle">' +
              (token.enabled ? "禁用" : "启用") + "</button>" +
            '<button type="button" class="btn btn-outline btn-sm" data-act="regen">重新生成</button>' +
            '<button type="button" class="btn btn-ghost btn-sm text-danger" data-act="delete">删除</button>' +
          "</div></td>" +
        "</tr>"
      );
    }).join("");
  }

  function shorten(token) {
    if (!token) return "";
    return token.length > 20 ? token.slice(0, 10) + "…" + token.slice(-6) : token;
  }

  async function load() {
    els.tbody.innerHTML = '<tr><td colspan="9"><div class="loading"><span class="spinner"></span>加载中…</div></td></tr>';
    try {
      state.tokens = (await API.get("/api/admin/tokens")) || [];
      render();
    } catch (err) {
      els.tbody.innerHTML = '<tr><td colspan="9">' + UI.renderEmpty(err.message || "加载失败") + "</td></tr>";
    }
  }

  function openCreateModal() {
    var body =
      '<div class="form-field"><label>备注（可选）</label>' +
        '<input class="input" id="tk-note" type="text" placeholder="用于识别用途，如：张三投稿"></div>' +
      '<div class="form-field"><label>有效期（可选）</label>' +
        '<input class="input" id="tk-expires" type="datetime-local"></div>' +
      '<div class="form-field"><label>最大上传次数（可选，留空不限）</label>' +
        '<input class="input" id="tk-max" type="number" min="1" placeholder="如：100"></div>' +
      '<div class="form-field"><label>单文件大小上限（MB，留空跟随全局）</label>' +
        '<input class="input" id="tk-size" type="number" min="1" step="1" placeholder="如：10"></div>';
    UI.openModal("新建上传 Token", body, async function (modal) {
      var payload = {};
      var note = modal.querySelector("#tk-note").value.trim();
      var expires = modal.querySelector("#tk-expires").value;
      var maxUp = modal.querySelector("#tk-max").value;
      var maxSize = modal.querySelector("#tk-size").value;
      if (note) payload.note = note;
      if (expires) payload.expires_at = new Date(expires).toISOString();
      if (maxUp) payload.max_uploads = Number(maxUp);
      if (maxSize) payload.max_file_size = Math.round(Number(maxSize) * 1024 * 1024);
      try {
        await API.post("/api/admin/tokens", payload);
        UI.toast("已创建 Token", "success");
        load();
        return true;
      } catch (err) {
        UI.toast(err.message || "创建失败", "error");
        return false;
      }
    });
  }

  function bindEvents() {
    els.newBtn.addEventListener("click", openCreateModal);

    els.tbody.addEventListener("click", async function (e) {
      var btn = e.target.closest("button[data-act]");
      if (!btn) return;
      var tr = btn.closest("tr");
      var id = tr.dataset.id;
      var token = state.tokens.find(function (t) { return String(t.id) === id; });
      if (!token) return;
      var act = btn.dataset.act;

      if (act === "copy") {
        var ok = await UI.copyToClipboard(token.token);
        UI.toast(ok ? "Token 已复制" : "复制失败，请手动复制", ok ? "success" : "error");
      } else if (act === "toggle") {
        try {
          await API.patch("/api/admin/tokens/" + id, { enabled: !token.enabled });
          UI.toast(token.enabled ? "已禁用" : "已启用", "success");
          load();
        } catch (err) {
          UI.toast(err.message || "操作失败", "error");
        }
      } else if (act === "regen") {
        var yes = await UI.confirmDialog("确定重新生成该 Token 吗？旧 Token 将立即失效。");
        if (!yes) return;
        try {
          await API.post("/api/admin/tokens/" + id + "/regenerate");
          UI.toast("已重新生成", "success");
          load();
        } catch (err) {
          UI.toast(err.message || "操作失败", "error");
        }
      } else if (act === "delete") {
        var sure = await UI.confirmDialog("确定删除该 Token 吗？删除后不可恢复。");
        if (!sure) return;
        try {
          await API.del("/api/admin/tokens/" + id);
          UI.toast("已删除", "success");
          load();
        } catch (err) {
          UI.toast(err.message || "删除失败", "error");
        }
      }
    });
  }

  Layout.boot({
    active: "tokens",
    onReady: function () {
      cacheEls();
      bindEvents();
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
