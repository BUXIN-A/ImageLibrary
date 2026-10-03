/**
 * 后台通知：服务日志分页查看、筛选、标记已读、删除与清空。
 */
(function () {
  "use strict";

  var PAGE_SIZE = 20;
  var LEVEL_BADGE = { info: "badge-primary", warning: "badge-pending", error: "badge-rejected" };
  var LEVEL_LABEL = { info: "信息", warning: "警告", error: "错误" };
  var state = { page: 1, pages: 0, total: 0, items: [], selected: new Set() };
  var els = {};

  function cacheEls() {
    els.level = document.getElementById("level-select");
    els.category = document.getElementById("category-select");
    els.q = document.getElementById("q-input");
    els.unreadOnly = document.getElementById("unread-only");
    els.filterBtn = document.getElementById("filter-btn");
    els.resetBtn = document.getElementById("reset-btn");
    els.refreshBtn = document.getElementById("refresh-btn");
    els.readAllBtn = document.getElementById("read-all-btn");
    els.clearReadBtn = document.getElementById("clear-read-btn");
    els.clearAllBtn = document.getElementById("clear-all-btn");
    els.tbody = document.getElementById("notif-tbody");
    els.pagination = document.getElementById("pagination");
    els.stats = document.getElementById("notif-stats");
    els.summary = document.getElementById("notif-summary");
    els.selectAll = document.getElementById("select-all");
    els.selectedCount = document.getElementById("selected-count");
    els.batchRead = document.getElementById("batch-read");
    els.batchDelete = document.getElementById("batch-delete");
  }

  function setOptions(select, items) {
    items.forEach(function (item) {
      var opt = document.createElement("option");
      opt.value = item.value;
      opt.textContent = item.label;
      select.appendChild(opt);
    });
  }

  async function loadMeta() {
    try {
      var data = await API.get("/api/admin/notifications/meta");
      setOptions(els.level, (data && data.levels) || []);
      setOptions(els.category, (data && data.categories) || []);
    } catch (err) { /* 元信息失败不影响列表 */ }
  }

  function buildQuery() {
    var params = new URLSearchParams();
    params.set("page", String(state.page));
    params.set("page_size", String(PAGE_SIZE));
    if (els.level.value) params.set("level", els.level.value);
    if (els.category.value) params.set("category", els.category.value);
    if (els.q.value.trim()) params.set("q", els.q.value.trim());
    if (els.unreadOnly.checked) params.set("unread_only", "1");
    return params.toString();
  }

  function renderStats(data) {
    data = data || {};
    var byLevel = data.by_level || {};
    var cards = [
      { label: "全部通知", value: data.total || 0, cls: "" },
      { label: "未读", value: data.unread || 0, cls: (data.unread || 0) > 0 ? "accent-pending" : "" },
      { label: "警告", value: byLevel.warning || 0, cls: (byLevel.warning || 0) > 0 ? "accent-pending" : "" },
      { label: "错误", value: byLevel.error || 0, cls: (byLevel.error || 0) > 0 ? "accent-danger" : "" }
    ];
    els.stats.innerHTML = cards.map(function (card) {
      return '<div class="stat-card ' + card.cls + '">' +
        '<span class="stat-label">' + UI.escapeHtml(card.label) + "</span>" +
        '<span class="stat-value">' + card.value + "</span></div>";
    }).join("");
    els.summary.textContent = "共 " + (data.total || 0) + " 条通知，未读 " + (data.unread || 0) + " 条";
  }

  function rowHtml(item) {
    var checked = state.selected.has(item.id) ? " checked" : "";
    var detail = item.detail
      ? '<div class="form-hint" style="margin-top:2px;word-break:break-word;">' + UI.escapeHtml(item.detail) + "</div>"
      : "";
    return (
      '<tr data-id="' + item.id + '">' +
        '<td><input type="checkbox" class="row-check" data-id="' + item.id + '"' + checked + "></td>" +
        '<td><span class="badge ' + (LEVEL_BADGE[item.level] || "badge-muted") + '">' +
          UI.escapeHtml(LEVEL_LABEL[item.level] || item.level) + "</span></td>" +
        "<td>" + UI.escapeHtml(categoryLabel(item.category)) + "</td>" +
        '<td style="word-break:break-word;">' + UI.escapeHtml(item.message) + detail + "</td>" +
        "<td>" + UI.escapeHtml(item.ip || "-") + "</td>" +
        "<td>" + UI.formatDate(item.created_at) + "</td>" +
        "<td>" + (item.is_read
          ? '<span class="badge badge-muted">已读</span>'
          : '<span class="badge badge-primary">未读</span>') + "</td>" +
        '<td><div class="row-actions">' +
          (item.is_read ? "" :
            '<button type="button" class="btn btn-outline btn-sm" data-act="read">标为已读</button>') +
          '<button type="button" class="btn btn-ghost btn-sm text-danger" data-act="delete">删除</button>' +
        "</div></td>" +
      "</tr>"
    );
  }

  var CATEGORY_LABELS = {};
  function categoryLabel(value) {
    return CATEGORY_LABELS[value] || value || "-";
  }

  function updateSelectionUI() {
    els.selectedCount.textContent = "已选 " + state.selected.size + " 条";
    var boxes = els.tbody.querySelectorAll(".row-check");
    var allChecked = boxes.length > 0;
    Array.prototype.forEach.call(boxes, function (box) {
      if (!box.checked) allChecked = false;
    });
    if (els.selectAll) els.selectAll.checked = allChecked;
  }

  function render() {
    if (!state.items.length) {
      els.tbody.innerHTML = '<tr><td colspan="8">' + UI.renderEmpty("没有符合条件的通知") + "</td></tr>";
      updateSelectionUI();
      return;
    }
    els.tbody.innerHTML = state.items.map(rowHtml).join("");
    updateSelectionUI();
  }

  async function loadStats() {
    try {
      var data = await API.get("/api/admin/notifications/summary");
      renderStats(data);
    } catch (err) { /* 统计失败不影响列表 */ }
  }

  async function load() {
    els.tbody.innerHTML = '<tr><td colspan="8"><div class="loading"><span class="spinner"></span>加载中…</div></td></tr>';
    try {
      var data = await API.get("/api/admin/notifications?" + buildQuery());
      state.items = (data && data.items) || [];
      state.page = (data && data.page) || 1;
      state.pages = (data && data.pages) || 0;
      state.total = (data && data.total) || 0;
      state.selected.clear();
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

  function findItem(id) {
    return state.items.find(function (item) { return String(item.id) === String(id); });
  }

  async function markRead(ids, all) {
    try {
      var data = await API.post("/api/admin/notifications/read", { ids: ids || [], all: !!all });
      UI.toast("已标记 " + ((data && data.affected) || 0) + " 条为已读", "success");
      loadStats();
      load();
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  async function deleteOne(item) {
    var yes = await UI.confirmDialog("确定删除该条通知吗？操作不可恢复。", "删除");
    if (!yes) return;
    try {
      await API.post("/api/admin/notifications/delete", { ids: [item.id] });
      UI.toast("通知已删除", "success");
      loadStats();
      load();
    } catch (err) {
      UI.toast(err.message || "删除失败", "error");
    }
  }

  async function batchAction(action) {
    var ids = Array.from(state.selected);
    if (!ids.length) { UI.toast("请先选择通知", "warning"); return; }
    if (action === "read") { markRead(ids, false); return; }
    var yes = await UI.confirmDialog("确定删除所选 " + ids.length + " 条通知吗？操作不可恢复。", "删除");
    if (!yes) return;
    try {
      var data = await API.post("/api/admin/notifications/delete", { ids: ids });
      UI.toast("已删除 " + ((data && data.affected) || 0) + " 条", "success");
      loadStats();
      load();
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  async function clearNotifications(onlyRead) {
    var message = onlyRead ? "确定清空全部已读通知吗？" : "确定清空全部通知吗？操作不可恢复。";
    var yes = await UI.confirmDialog(message, "清空");
    if (!yes) return;
    try {
      var data = await API.post("/api/admin/notifications/clear", { only_read: !!onlyRead });
      UI.toast("已清空 " + ((data && data.affected) || 0) + " 条通知", "success");
      loadStats();
      load();
    } catch (err) {
      UI.toast(err.message || "清空失败", "error");
    }
  }

  function bindEvents() {
    els.filterBtn.addEventListener("click", function () { state.page = 1; load(); });
    els.q.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { state.page = 1; load(); }
    });
    els.level.addEventListener("change", function () { state.page = 1; load(); });
    els.category.addEventListener("change", function () { state.page = 1; load(); });
    els.unreadOnly.addEventListener("change", function () { state.page = 1; load(); });
    els.resetBtn.addEventListener("click", function () {
      els.level.value = "";
      els.category.value = "";
      els.q.value = "";
      els.unreadOnly.checked = false;
      state.page = 1;
      load();
    });
    if (els.refreshBtn) els.refreshBtn.addEventListener("click", function () { loadStats(); load(); });
    if (els.readAllBtn) els.readAllBtn.addEventListener("click", function () { markRead([], true); });
    if (els.clearReadBtn) els.clearReadBtn.addEventListener("click", function () { clearNotifications(true); });
    if (els.clearAllBtn) els.clearAllBtn.addEventListener("click", function () { clearNotifications(false); });

    els.tbody.addEventListener("change", function (e) {
      var box = e.target.closest(".row-check");
      if (!box) return;
      var id = Number(box.dataset.id);
      if (box.checked) state.selected.add(id);
      else state.selected.delete(id);
      updateSelectionUI();
    });

    els.tbody.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-act]");
      if (!btn) return;
      var row = btn.closest("tr");
      var item = row && findItem(row.dataset.id);
      if (!item) return;
      if (btn.dataset.act === "read") markRead([item.id], false);
      else if (btn.dataset.act === "delete") deleteOne(item);
    });

    if (els.selectAll) {
      els.selectAll.addEventListener("change", function () {
        state.items.forEach(function (item) {
          if (els.selectAll.checked) state.selected.add(item.id);
          else state.selected.delete(item.id);
        });
        var boxes = els.tbody.querySelectorAll(".row-check");
        Array.prototype.forEach.call(boxes, function (box) { box.checked = els.selectAll.checked; });
        updateSelectionUI();
      });
    }

    els.batchRead.addEventListener("click", function () { batchAction("read"); });
    els.batchDelete.addEventListener("click", function () { batchAction("delete"); });
  }

  Layout.boot({
    active: "notifications",
    onReady: function () {
      cacheEls();
      loadMeta().then(function () {
        document.querySelectorAll("#category-select option").forEach(function (opt) {
          if (opt.value) CATEGORY_LABELS[opt.value] = opt.textContent;
        });
        bindEvents();
        els.tbody.innerHTML = '<tr><td colspan="8">' + UI.renderEmpty("暂无通知") + "</td></tr>";
        loadStats();
        load();
      }).catch(function (err) {
        try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
      });
    }
  });
})();
