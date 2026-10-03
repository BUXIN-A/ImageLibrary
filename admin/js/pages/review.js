/**
 * 审核队列：展示待审核图片，支持单张/批量通过与拒绝（可填原因）。
 */
(function () {
  "use strict";

  var PAGE_SIZE = 24;
  var state = { page: 1, pages: 0, items: [], selected: new Set() };
  var els = {};

  function cacheEls() {
    els.list = document.getElementById("review-list");
    els.pagination = document.getElementById("pagination");
    els.selectAll = document.getElementById("select-all");
    els.selectedCount = document.getElementById("selected-count");
    els.batchApprove = document.getElementById("batch-approve");
    els.batchReject = document.getElementById("batch-reject");
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
          '<span class="card-status"><span class="badge badge-pending">待审核</span></span>' +
        "</div>" +
        '<div class="card-info">' +
          '<div class="card-title" title="' + UI.escapeHtml(image.title || image.original_name) + '">' +
            UI.escapeHtml(image.title || image.original_name) + "</div>" +
          '<div class="card-sub">' +
            "<span>" + UI.escapeHtml(image.folder_name || "未分类") + "</span>" +
            "<span>" + UI.formatSize(image.size) + "</span>" +
            "<span>" + image.width + "×" + image.height + "</span>" +
          "</div>" +
          '<div class="card-sub"><span>提交于 ' + UI.formatDate(image.created_at) + "</span></div>" +
        "</div>" +
        '<div class="card-actions">' +
          '<button type="button" class="btn btn-success btn-sm" data-act="approve">通过</button>' +
          '<button type="button" class="btn btn-danger btn-sm" data-act="reject">拒绝</button>' +
        "</div>" +
      "</div>"
    );
  }

  function render() {
    if (!state.items.length) {
      els.list.innerHTML = UI.renderEmpty("暂无待审核图片");
      return;
    }
    els.list.innerHTML = '<div class="image-grid">' + state.items.map(cardHtml).join("") + "</div>";
    state.items.forEach(function (image) {
      var box = els.list.querySelector('.card-check[data-id="' + image.id + '"]');
      if (box) {
        box.checked = state.selected.has(image.id);
        box.closest(".image-card").classList.toggle("selected", box.checked);
      }
    });
    updateSelectionUI();
  }

  async function load() {
    els.list.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    try {
      var data = await API.get("/api/admin/review?page=" + state.page + "&page_size=" + PAGE_SIZE);
      state.items = (data && data.items) || [];
      state.pages = (data && data.pages) || 0;
      state.selected.clear();
      render();
      UI.renderPagination(els.pagination, { page: state.page, pages: state.pages }, function (p) {
        state.page = p;
        load();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    } catch (err) {
      els.list.innerHTML = UI.renderEmpty(err.message || "加载失败");
      els.pagination.innerHTML = "";
    }
  }

  async function approve(image) {
    try {
      await API.post("/api/admin/review/" + image.id + "/approve");
      UI.toast("已通过审核", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
    }
  }

  function reject(image) {
    UI.openModal(
      "拒绝原因",
      '<div class="form-field"><label>原因（可选）</label>' +
        '<textarea class="textarea" id="reject-reason" placeholder="填写拒绝原因，便于记录"></textarea></div>',
      async function (modal) {
        var reason = modal.querySelector("#reject-reason").value.trim();
        try {
          await API.post("/api/admin/review/" + image.id + "/reject", { reason: reason || null });
          UI.toast("已拒绝", "success");
          load();
          return true;
        } catch (err) {
          UI.toast(err.message || "操作失败", "error");
          return false;
        }
      }
    );
  }

  function batchApprove() {
    if (!state.selected.size) { UI.toast("请先选择图片", "warning"); return; }
    UI.confirmDialog("确定通过所选 " + state.selected.size + " 张图片吗？").then(function (yes) {
      if (!yes) return;
      API.post("/api/admin/review/batch", { ids: Array.from(state.selected), action: "approve" })
        .then(function (data) {
          UI.toast("已通过 " + (data.affected || 0) + " 张", "success");
          load();
        })
        .catch(function (err) { UI.toast(err.message || "操作失败", "error"); });
    });
  }

  function batchReject() {
    if (!state.selected.size) { UI.toast("请先选择图片", "warning"); return; }
    UI.openModal(
      "批量拒绝（" + state.selected.size + " 张）",
      '<div class="form-field"><label>拒绝原因（可选）</label>' +
        '<textarea class="textarea" id="reject-reason" placeholder="填写拒绝原因，便于记录"></textarea></div>',
      function (modal) {
        var reason = modal.querySelector("#reject-reason").value.trim();
        return API.post("/api/admin/review/batch", {
          ids: Array.from(state.selected),
          action: "reject",
          reason: reason || null
        }).then(function (data) {
          UI.toast("已拒绝 " + (data.affected || 0) + " 张", "success");
          load();
          return true;
        }).catch(function (err) {
          UI.toast(err.message || "操作失败", "error");
          return false;
        });
      }
    );
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
      if (btn.dataset.act === "approve") approve(image);
      else if (btn.dataset.act === "reject") reject(image);
    });
    els.selectAll.addEventListener("change", function () {
      state.items.forEach(function (image) {
        if (els.selectAll.checked) state.selected.add(image.id);
        else state.selected.delete(image.id);
      });
      render();
    });
    els.batchApprove.addEventListener("click", batchApprove);
    els.batchReject.addEventListener("click", batchReject);
    if (els.refreshBtn) els.refreshBtn.addEventListener("click", load);
  }

  // 统一启动入口：布局先同步渲染，再渲染可渲染内容并加载数据；
  // 兜底 catch 保证任何异常都不会导致整页空白。
  Layout.boot({
    active: "review",
    onReady: function () {
      cacheEls();
      bindEvents();
      // 先渲染可渲染的内容（空状态占位），再发起数据请求
      if (els.list) els.list.innerHTML = UI.renderEmpty("暂无待审核图片");
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "审核页初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
