/**
 * 图库管理：筛选、网格展示、多选批量操作、单条编辑/分享/删除、导出 ZIP。
 */
(function () {
  "use strict";

  var PAGE_SIZE = 24;
  var state = {
    page: 1,
    pages: 0,
    total: 0,
    items: [],
    selected: new Set(),
    folders: [],
    tags: []
  };

  var els = {};

  function cacheEls() {
    els.q = document.getElementById("q-input");
    els.folder = document.getElementById("folder-select");
    els.tag = document.getElementById("tag-select");
    els.status = document.getElementById("status-select");
    els.sort = document.getElementById("sort-select");
    els.filterBtn = document.getElementById("filter-btn");
    els.resetBtn = document.getElementById("reset-btn");
    els.grid = document.getElementById("grid");
    els.pagination = document.getElementById("pagination");
    els.selectAll = document.getElementById("select-all");
    els.selectedCount = document.getElementById("selected-count");
    els.batchApprove = document.getElementById("batch-approve");
    els.batchReject = document.getElementById("batch-reject");
    els.batchMove = document.getElementById("batch-move");
    els.batchTag = document.getElementById("batch-tag");
    els.batchExport = document.getElementById("batch-export");
    els.batchDelete = document.getElementById("batch-delete");
  }

  function buildQuery() {
    var params = new URLSearchParams();
    params.set("page", String(state.page));
    params.set("page_size", String(PAGE_SIZE));
    if (els.q.value.trim()) params.set("q", els.q.value.trim());
    if (els.folder.value) params.set("folder_id", els.folder.value);
    if (els.tag.value) params.set("tag", els.tag.value);
    if (els.status.value) params.set("status", els.status.value);
    if (els.sort.value) params.set("sort", els.sort.value);
    return params.toString();
  }

  function updateSelectionUI() {
    els.selectedCount.textContent = "已选 " + state.selected.size + " 张";
    var boxes = els.grid.querySelectorAll(".card-check");
    var allChecked = boxes.length > 0;
    Array.prototype.forEach.call(boxes, function (box) {
      if (!box.checked) allChecked = false;
    });
    els.selectAll.checked = allChecked;
  }

  function renderGrid() {
    if (!state.items.length) {
      els.grid.innerHTML = UI.renderEmpty("没有符合条件的图片");
      return;
    }
    els.grid.innerHTML = '<div class="image-grid">' + state.items.map(cardHtml).join("") + "</div>";
    // 恢复勾选状态
    state.items.forEach(function (image) {
      var box = els.grid.querySelector('.card-check[data-id="' + image.id + '"]');
      if (box) {
        box.checked = state.selected.has(image.id);
        box.closest(".image-card").classList.toggle("selected", box.checked);
      }
    });
    updateSelectionUI();
  }

  function cardHtml(image) {
    var thumb = image.thumb_url
      ? '<img src="' + UI.escapeHtml(UI.mediaUrl(image.thumb_url)) + '" loading="lazy" alt="">'
      : "";
    return (
      '<div class="image-card" data-id="' + image.id + '">' +
        '<div class="thumb-wrap">' +
          thumb +
          '<input type="checkbox" class="card-check" data-id="' + image.id + '" aria-label="选择">' +
          '<span class="card-status">' + UI.statusBadge(image.status) + "</span>" +
        "</div>" +
        '<div class="card-info">' +
          '<div class="card-title" title="' + UI.escapeHtml(image.title || image.original_name) + '">' +
            UI.escapeHtml(image.title || image.original_name) + "</div>" +
          '<div class="card-sub">' +
            "<span>" + UI.escapeHtml(image.folder_name || "未分类") + "</span>" +
            "<span>浏览 " + (image.views || 0) + "</span>" +
            "<span>下载 " + (image.downloads || 0) + "</span>" +
          "</div>" +
          '<div class="card-sub">' +
            "<span>" + UI.formatSize(image.size) + "</span>" +
            "<span>" + image.width + "×" + image.height + "</span>" +
            "<span>" + UI.formatDate(image.created_at) + "</span>" +
          "</div>" +
        "</div>" +
        '<div class="card-actions">' +
          '<button type="button" class="btn btn-outline btn-sm" data-act="edit">编辑</button>' +
          '<button type="button" class="btn btn-outline btn-sm" data-act="share">分享</button>' +
          '<button type="button" class="btn btn-ghost btn-sm text-danger" data-act="delete">删除</button>' +
        "</div>" +
      "</div>"
    );
  }

  async function load() {
    els.grid.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    try {
      var data = await API.get("/api/admin/images?" + buildQuery());
      state.items = (data && data.items) || [];
      state.page = (data && data.page) || 1;
      state.pages = (data && data.pages) || 0;
      state.total = (data && data.total) || 0;
      state.selected.clear();
      renderGrid();
      UI.renderPagination(els.pagination, { page: state.page, pages: state.pages }, function (p) {
        state.page = p;
        load();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    } catch (err) {
      els.grid.innerHTML = UI.renderEmpty(err.message || "加载失败");
      els.pagination.innerHTML = "";
    }
  }

  function getSelectedIds() {
    return Array.from(state.selected);
  }

  function folderOptionsHtml(selectedId) {
    var html = '<option value="">未分类</option>';
    state.folders.forEach(function (f) {
      html += '<option value="' + f.id + '"' + (String(f.id) === String(selectedId) ? " selected" : "") +
        ">" + UI.escapeHtml(f.label) + "</option>";
    });
    return html;
  }

  function openEditModal(image) {
    var tagNames = (image.tags || []).map(function (t) { return t.name; }).join(",");
    var body =
      '<div class="form-field"><label>标题</label><input class="input" id="edit-title" value="' +
        UI.escapeHtml(image.title || "") + '"></div>' +
      '<div class="form-field"><label>描述</label><textarea class="textarea" id="edit-desc">' +
        UI.escapeHtml(image.description || "") + "</textarea></div>" +
      '<div class="form-field"><label>文件夹</label><select class="select" id="edit-folder">' +
        folderOptionsHtml(image.folder_id) + "</select></div>" +
      '<div class="form-field"><label>标签（英文逗号分隔）</label><input class="input" id="edit-tags" value="' +
        UI.escapeHtml(tagNames) + '"></div>' +
      '<div class="form-field"><label>状态</label><select class="select" id="edit-status">' +
        ["approved", "pending", "rejected"].map(function (s) {
          return '<option value="' + s + '"' + (image.status === s ? " selected" : "") + ">" +
            ({ approved: "已通过", pending: "待审核", rejected: "已拒绝" }[s]) + "</option>";
        }).join("") +
      "</select></div>";

    UI.openModal("编辑图片", body, async function (modal) {
      var title = modal.querySelector("#edit-title").value.trim();
      var desc = modal.querySelector("#edit-desc").value.trim();
      var folderVal = modal.querySelector("#edit-folder").value;
      var tagsVal = modal.querySelector("#edit-tags").value;
      var status = modal.querySelector("#edit-status").value;
      var payload = {
        title: title,
        description: desc,
        folder_id: folderVal ? Number(folderVal) : null,
        status: status,
        tags: tagsVal.split(",").map(function (t) { return t.trim(); }).filter(Boolean)
      };
      try {
        await API.patch("/api/admin/images/" + image.id, payload);
        UI.toast("已保存修改", "success");
        load();
        return true;
      } catch (err) {
        UI.toast(err.message || "保存失败", "error");
        return false;
      }
    });
  }

  async function shareImage(image) {
    try {
      var data = await API.post("/api/admin/images/" + image.id + "/share");
      var ok = await UI.copyToClipboard(data.share_url);
      UI.toast(ok ? "分享链接已复制：" + data.share_url : "分享链接：" + data.share_url, ok ? "success" : "info");
    } catch (err) {
      UI.toast(err.message || "生成分享失败", "error");
    }
  }

  async function deleteImage(image) {
    var yes = await UI.confirmDialog("确定将「" + (image.title || image.original_name) + "」移入回收站吗？");
    if (!yes) return;
    try {
      await API.del("/api/admin/images/" + image.id);
      UI.toast("已移入回收站", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "删除失败", "error");
    }
  }

  async function batchAction(action, extra) {
    var ids = getSelectedIds();
    if (!ids.length) {
      UI.toast("请先选择图片", "warning");
      return false;
    }
    var payload = Object.assign({ ids: ids, action: action }, extra || {});
    try {
      var data = await API.post("/api/admin/images/batch", payload);
      UI.toast("操作完成，共影响 " + (data.affected || 0) + " 张", "success");
      load();
      return true;
    } catch (err) {
      UI.toast(err.message || "操作失败", "error");
      return false;
    }
  }

  function requireSelection() {
    if (!state.selected.size) {
      UI.toast("请先选择图片", "warning");
      return false;
    }
    return true;
  }

  function bindEvents() {
    els.filterBtn.addEventListener("click", function () {
      state.page = 1;
      load();
    });
    els.q.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { state.page = 1; load(); }
    });
    [els.folder, els.tag, els.status, els.sort].forEach(function (sel) {
      sel.addEventListener("change", function () { state.page = 1; load(); });
    });
    els.resetBtn.addEventListener("click", function () {
      els.q.value = "";
      els.folder.value = "";
      els.tag.value = "";
      els.status.value = "";
      els.sort.value = "latest";
      state.page = 1;
      load();
    });

    els.grid.addEventListener("change", function (e) {
      var box = e.target.closest(".card-check");
      if (!box) return;
      var id = Number(box.dataset.id);
      if (box.checked) state.selected.add(id);
      else state.selected.delete(id);
      box.closest(".image-card").classList.toggle("selected", box.checked);
      updateSelectionUI();
    });

    els.grid.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-act]");
      if (!btn) return;
      var card = btn.closest(".image-card");
      var image = state.items.find(function (it) { return String(it.id) === card.dataset.id; });
      if (!image) return;
      var act = btn.dataset.act;
      if (act === "edit") openEditModal(image);
      else if (act === "share") shareImage(image);
      else if (act === "delete") deleteImage(image);
    });

    els.selectAll.addEventListener("change", function () {
      state.items.forEach(function (image) {
        if (els.selectAll.checked) state.selected.add(image.id);
        else state.selected.delete(image.id);
      });
      renderGrid();
    });

    els.batchApprove.addEventListener("click", function () {
      if (requireSelection()) batchAction("approve");
    });
    els.batchReject.addEventListener("click", async function () {
      if (!requireSelection()) return;
      var yes = await UI.confirmDialog("确定拒绝所选 " + state.selected.size + " 张图片吗？");
      if (yes) batchAction("reject");
    });
    els.batchDelete.addEventListener("click", async function () {
      if (!requireSelection()) return;
      var yes = await UI.confirmDialog("确定将所选 " + state.selected.size + " 张图片移入回收站吗？");
      if (yes) batchAction("delete");
    });
    els.batchMove.addEventListener("click", function () {
      if (!requireSelection()) return;
      var body = '<div class="form-field"><label>目标文件夹</label><select class="select" id="batch-folder">' +
        folderOptionsHtml("") + "</select></div>";
      UI.openModal("移动到文件夹", body, function (modal) {
        var val = modal.querySelector("#batch-folder").value;
        return batchAction("move", { folder_id: val ? Number(val) : null });
      });
    });
    els.batchTag.addEventListener("click", function () {
      if (!requireSelection()) return;
      var body = '<div class="form-field"><label>要添加的标签（英文逗号分隔）</label>' +
        '<input class="input" id="batch-tags" placeholder="如：风景,精选"></div>';
      UI.openModal("添加标签", body, function (modal) {
        var tags = modal.querySelector("#batch-tags").value.split(",")
          .map(function (t) { return t.trim(); }).filter(Boolean);
        if (!tags.length) {
          UI.toast("请输入至少一个标签", "warning");
          return false;
        }
        return batchAction("tag", { tags: tags });
      });
    });
    els.batchExport.addEventListener("click", async function () {
      if (!requireSelection()) return;
      try {
        await API.download("/api/admin/images/export", { ids: getSelectedIds() }, "images_export.zip");
        UI.toast("已开始导出 ZIP", "success");
      } catch (err) {
        UI.toast(err.message || "导出失败", "error");
      }
    });
  }

  async function loadOptions() {
    try {
      var results = await Promise.all([API.get("/api/folders"), API.get("/api/tags")]);
      state.folders = UI.flattenFolders(results[0]);
      state.tags = results[1] || [];
      UI.fillFolderSelect(els.folder, state.folders, { allLabel: "全部文件夹" });
      els.tag.innerHTML = '<option value="">全部标签</option>' + state.tags.map(function (t) {
        return '<option value="' + UI.escapeHtml(t.name) + '">' + UI.escapeHtml(t.name) +
          " (" + (t.image_count || 0) + ")</option>";
      }).join("");
    } catch (err) {
      UI.toast("筛选项加载失败：" + err.message, "error");
    }
  }

  Layout.boot({
    active: "images",
    onReady: function () {
      cacheEls();
      bindEvents();
      Promise.resolve(loadOptions()).then(function () { load(); }, function () { load(); });
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
