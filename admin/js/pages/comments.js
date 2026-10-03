/**
 * 评论管理：分页列表、筛选、单条隐藏/恢复/删除与批量操作。
 */
(function () {
  "use strict";

  var PAGE_SIZE = 20;
  var FRONTEND_BASE = "http://127.0.0.1:8000";
  var state = { page: 1, pages: 0, total: 0, items: [], selected: new Set() };
  var els = {};

  function cacheEls() {
    els.q = document.getElementById("q-input");
    els.status = document.getElementById("status-select");
    els.filterBtn = document.getElementById("filter-btn");
    els.resetBtn = document.getElementById("reset-btn");
    els.refreshBtn = document.getElementById("refresh-btn");
    els.tbody = document.getElementById("comments-tbody");
    els.pagination = document.getElementById("pagination");
    els.summary = document.getElementById("comments-summary");
    els.selectAll = document.getElementById("select-all");
    els.selectedCount = document.getElementById("selected-count");
    els.batchHide = document.getElementById("batch-hide");
    els.batchShow = document.getElementById("batch-show");
    els.batchDelete = document.getElementById("batch-delete");
  }

  function buildQuery() {
    var params = new URLSearchParams();
    params.set("page", String(state.page));
    params.set("page_size", String(PAGE_SIZE));
    if (els.q.value.trim()) params.set("q", els.q.value.trim());
    if (els.status.value) params.set("status", els.status.value);
    return params.toString();
  }

  function userLabel(user) {
    if (!user) return "-";
    return user.nickname || user.username || "-";
  }

  function imageCell(image) {
    if (!image || !image.id) return "-";
    var thumb = image.thumb_url
      ? '<img class="table-thumb" src="' + UI.escapeHtml(UI.mediaUrl(image.thumb_url)) + '" loading="lazy" alt="">'
      : "";
    var url = FRONTEND_BASE + "/image.html?id=" + image.id;
    var title = image.title || image.filename || ("#" + image.id);
    return '<div class="flex items-center gap-sm">' + thumb +
      '<a href="' + UI.escapeHtml(url) + '" target="_blank" rel="noopener">' +
      UI.escapeHtml(title) + "</a></div>";
  }

  function rowHtml(comment) {
    var visible = comment.status !== "hidden";
    var checked = state.selected.has(comment.id) ? " checked" : "";
    return (
      '<tr data-id="' + comment.id + '">' +
        '<td><input type="checkbox" class="row-check" data-id="' + comment.id + '"' + checked + "></td>" +
        '<td style="max-width:360px;word-break:break-word;">' + UI.escapeHtml(comment.content) + "</td>" +
        "<td>" + UI.escapeHtml(userLabel(comment.user)) + "</td>" +
        "<td>" + imageCell(comment.image) + "</td>" +
        "<td>" + UI.formatDate(comment.created_at) + "</td>" +
        "<td>" + (visible
          ? '<span class="badge badge-approved">可见</span>'
          : '<span class="badge badge-hidden">已隐藏</span>') + "</td>" +
        '<td><div class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-sm" data-act="toggle">' +
            (visible ? "隐藏" : "恢复") + "</button>" +
          '<button type="button" class="btn btn-ghost btn-sm text-danger" data-act="delete">删除</button>' +
        "</div></td>" +
      "</tr>"
    );
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
      els.tbody.innerHTML = '<tr><td colspan="7">' + UI.renderEmpty("没有符合条件的评论") + "</td></tr>";
      updateSelectionUI();
      return;
    }
    els.tbody.innerHTML = state.items.map(rowHtml).join("");
    els.summary.textContent = "共 " + state.total + " 条评论";
    updateSelectionUI();
  }

  async function load() {
    els.tbody.innerHTML = '<tr><td colspan="7"><div class="loading"><span class="spinner"></span>加载中…</div></td></tr>';
    try {
      var data = await API.get("/api/admin/comments?" + buildQuery());
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
      els.tbody.innerHTML = '<tr><td colspan="7">' + UI.renderEmpty(err.message || "加载失败") + "</td></tr>";
      els.pagination.innerHTML = "";
    }
  }

  function findComment(id) {
    return state.items.find(function (c) { return String(c.id) === String(id); });
  }

  async function toggleStatus(comment) {
    var next = comment.status === "hidden" ? "visible" : "hidden";
    try {
      await API.patch("/api/admin/comments/" + comment.id, { status: next });
      UI.toast(next === "hidden" ? "评论已隐藏" : "评论已恢复", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  async function deleteComment(comment) {
    var yes = await UI.confirmDialog("确定删除该条评论吗？操作不可恢复。", "删除");
    if (!yes) return;
    try {
      await API.del("/api/admin/comments/" + comment.id);
      UI.toast("评论已删除", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "删除失败", "error");
    }
  }

  async function batchAction(action) {
    var ids = Array.from(state.selected);
    if (!ids.length) { UI.toast("请先选择评论", "warning"); return; }
    if (action === "delete") {
      var yes = await UI.confirmDialog("确定删除所选 " + ids.length + " 条评论吗？操作不可恢复。", "删除");
      if (!yes) return;
    }
    try {
      var data = await API.post("/api/admin/comments/batch", { ids: ids, action: action });
      UI.toast("操作完成，共影响 " + ((data && data.affected) || 0) + " 条", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  function bindEvents() {
    els.filterBtn.addEventListener("click", function () { state.page = 1; load(); });
    els.q.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { state.page = 1; load(); }
    });
    els.status.addEventListener("change", function () { state.page = 1; load(); });
    els.resetBtn.addEventListener("click", function () {
      els.q.value = "";
      els.status.value = "";
      state.page = 1;
      load();
    });
    if (els.refreshBtn) els.refreshBtn.addEventListener("click", load);

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
      var comment = row && findComment(row.dataset.id);
      if (!comment) return;
      var act = btn.dataset.act;
      if (act === "toggle") toggleStatus(comment);
      else if (act === "delete") deleteComment(comment);
    });

    if (els.selectAll) {
      els.selectAll.addEventListener("change", function () {
        state.items.forEach(function (comment) {
          if (els.selectAll.checked) state.selected.add(comment.id);
          else state.selected.delete(comment.id);
        });
        var boxes = els.tbody.querySelectorAll(".row-check");
        Array.prototype.forEach.call(boxes, function (box) { box.checked = els.selectAll.checked; });
        updateSelectionUI();
      });
    }

    els.batchHide.addEventListener("click", function () { batchAction("hide"); });
    els.batchShow.addEventListener("click", function () { batchAction("show"); });
    els.batchDelete.addEventListener("click", function () { batchAction("delete"); });
  }

  Layout.boot({
    active: "comments",
    onReady: function () {
      cacheEls();
      bindEvents();
      if (els.tbody) {
        els.tbody.innerHTML = '<tr><td colspan="7">' + UI.renderEmpty("暂无评论") + "</td></tr>";
      }
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
