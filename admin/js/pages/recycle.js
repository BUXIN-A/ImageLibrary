/**
 * 回收站：列出已删除图片，支持还原与彻底删除（单条/批量）。
 * 说明：后端未提供「仅已删除」过滤，此处拉取包含已删除的列表后在前端筛选。
 */
(function () {
  "use strict";

  var PAGE_SIZE = 24;
  var state = {
    all: [],
    items: [],
    page: 1,
    pages: 0,
    selected: new Set()
  };
  var els = {};

  function cacheEls() {
    els.list = document.getElementById("recycle-list");
    els.pagination = document.getElementById("pagination");
    els.selectAll = document.getElementById("select-all");
    els.selectedCount = document.getElementById("selected-count");
    els.batchRestore = document.getElementById("batch-restore");
    els.batchPurge = document.getElementById("batch-purge");
    els.refreshBtn = document.getElementById("refresh-btn");
  }

  function updateSelectionUI() {
    els.selectedCount.textContent = "已选 " + state.selected.size + " 张";
    var boxes = els.list.querySelectorAll(".card-check");
    var allChecked = boxes.length > 0;
    Array.prototype.forEach.call(boxes, function (box) {
      if (!box.checked) allChecked = false;
    });
    els.selectAll.checked = allChecked;
  }

  function cardHtml(image) {
    return (
      '<div class="image-card" data-id="' + image.id + '">' +
        '<div class="thumb-wrap">' +
          '<img src="' + UI.escapeHtml(UI.mediaUrl(image.thumb_url)) + '" loading="lazy" alt="">' +
          '<input type="checkbox" class="card-check" data-id="' + image.id + '" aria-label="选择">' +
          '<span class="card-status">' + UI.statusBadge(image.status) + "</span>" +
        "</div>" +
        '<div class="card-info">' +
          '<div class="card-title" title="' + UI.escapeHtml(image.title || image.original_name) + '">' +
            UI.escapeHtml(image.title || image.original_name) + "</div>" +
          '<div class="card-sub">' +
            "<span>" + UI.escapeHtml(image.folder_name || "未分类") + "</span>" +
            "<span>" + UI.formatSize(image.size) + "</span>" +
          "</div>" +
        "</div>" +
        '<div class="card-actions">' +
          '<button type="button" class="btn btn-outline btn-sm" data-act="restore">还原</button>' +
          '<button type="button" class="btn btn-danger btn-sm" data-act="purge">彻底删除</button>' +
        "</div>" +
      "</div>"
    );
  }

  function renderPage() {
    if (!state.all.length) {
      els.list.innerHTML = UI.renderEmpty("回收站为空");
      els.pagination.innerHTML = "";
      els.selectedCount.textContent = "已选 0 张";
      els.selectAll.checked = false;
      return;
    }
    state.pages = Math.ceil(state.all.length / PAGE_SIZE);
    if (state.page > state.pages) state.page = state.pages || 1;
    var start = (state.page - 1) * PAGE_SIZE;
    state.items = state.all.slice(start, start + PAGE_SIZE);

    els.list.innerHTML = '<div class="image-grid">' + state.items.map(cardHtml).join("") + "</div>";
    state.items.forEach(function (image) {
      var box = els.list.querySelector('.card-check[data-id="' + image.id + '"]');
      if (box) {
        box.checked = state.selected.has(image.id);
        box.closest(".image-card").classList.toggle("selected", box.checked);
      }
    });
    updateSelectionUI();

    UI.renderPagination(els.pagination, { page: state.page, pages: state.pages }, function (p) {
      state.page = p;
      renderPage();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  async function load() {
    els.list.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    try {
      var all = [];
      var page = 1;
      var pages = 1;
      do {
        var data = await API.get(
          "/api/admin/images?page=" + page + "&page_size=200&include_deleted=1&sort=latest"
        );
        all = all.concat((data && data.items) || []);
        pages = (data && data.pages) || 1;
        page += 1;
      } while (page <= pages);

      state.all = all.filter(function (image) { return image.is_deleted; });
      state.selected.clear();
      state.page = 1;
      renderPage();
    } catch (err) {
      els.list.innerHTML = UI.renderEmpty(err.message || "加载失败");
      els.pagination.innerHTML = "";
    }
  }

  async function restore(image) {
    try {
      await API.post("/api/admin/images/" + image.id + "/restore");
      UI.toast("已还原", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "还原失败", "error");
    }
  }

  async function purge(image) {
    var yes = await UI.confirmDialog(
      "彻底删除后图片记录与磁盘文件都将被移除且不可恢复，确定继续吗？",
      "彻底删除"
    );
    if (!yes) return;
    try {
      await API.del("/api/admin/images/" + image.id + "/purge");
      UI.toast("已彻底删除", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "删除失败", "error");
    }
  }

  async function batch(action) {
    if (!state.selected.size) { UI.toast("请先选择图片", "warning"); return; }
    var ids = Array.from(state.selected);
    var msg = action === "purge"
      ? "彻底删除后不可恢复，确定删除所选 " + ids.length + " 张图片吗？"
      : "确定还原所选 " + ids.length + " 张图片吗？";
    var yes = await UI.confirmDialog(msg, action === "purge" ? "彻底删除" : "确定");
    if (!yes) return;
    try {
      var data = await API.post("/api/admin/images/batch", { ids: ids, action: action });
      UI.toast("操作完成，共影响 " + (data.affected || 0) + " 张", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  function bindEvents() {
    els.list.addEventListener("change", function (e) {
      var box = e.target.closest(".card-check");
      if (!box) return;
      var id = Number(box.dataset.id);
      if (box.checked) state.selected.add(id);
      else state.selected.delete(id);
      box.closest(".image-card").classList.toggle("selected", box.checked);
      updateSelectionUI();
    });
    els.list.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-act]");
      if (!btn) return;
      var card = btn.closest(".image-card");
      var image = state.items.find(function (it) { return String(it.id) === card.dataset.id; });
      if (!image) return;
      if (btn.dataset.act === "restore") restore(image);
      else if (btn.dataset.act === "purge") purge(image);
    });
    els.selectAll.addEventListener("change", function () {
      state.items.forEach(function (image) {
        if (els.selectAll.checked) state.selected.add(image.id);
        else state.selected.delete(image.id);
      });
      renderPage();
    });
    els.batchRestore.addEventListener("click", function () { batch("restore"); });
    els.batchPurge.addEventListener("click", function () { batch("purge"); });
    if (els.refreshBtn) els.refreshBtn.addEventListener("click", load);
  }

  Layout.boot({
    active: "recycle",
    onReady: function () {
      cacheEls();
      bindEvents();
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
