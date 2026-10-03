/**
 * 文件夹管理：树形展示，新建（可选父级）、重命名、移动、删除。
 */
(function () {
  "use strict";

  var state = { tree: [], flat: [] };
  var els = {};

  function cacheEls() {
    els.tree = document.getElementById("folder-tree");
    els.newBtn = document.getElementById("new-folder-btn");
  }

  function chevron() {
    return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>';
  }

  function nodeHtml(node) {
    var hasChildren = node.children && node.children.length > 0;
    var toggle = '<button type="button" class="tree-toggle' + (hasChildren ? "" : " placeholder") +
      '" aria-label="展开/折叠">' + (hasChildren ? chevron() : chevron()) + "</button>";
    var children = hasChildren
      ? '<ul class="tree-children">' + node.children.map(nodeHtml).join("") + "</ul>"
      : "";
    return (
      '<li>' +
        '<div class="tree-node" data-id="' + node.id + '">' +
          toggle +
          '<span class="tree-label">' + UI.escapeHtml(node.name) +
            '<span class="folder-count">' + (node.image_count || 0) + " 张</span></span>" +
          '<span class="tree-actions">' +
            '<button type="button" class="btn btn-ghost btn-sm" data-act="add">新建子级</button>' +
            '<button type="button" class="btn btn-ghost btn-sm" data-act="rename">重命名</button>' +
            '<button type="button" class="btn btn-ghost btn-sm" data-act="move">移动</button>' +
            '<button type="button" class="btn btn-ghost btn-sm text-danger" data-act="delete">删除</button>' +
          "</span>" +
        "</div>" +
        children +
      "</li>"
    );
  }

  function render() {
    if (!state.tree.length) {
      els.tree.innerHTML = "<li>" + UI.renderEmpty("暂无文件夹，点击右上角新建") + "</li>";
      return;
    }
    els.tree.innerHTML = state.tree.map(nodeHtml).join("");
  }

  async function load() {
    try {
      var tree = await API.get("/api/folders");
      state.tree = tree || [];
      state.flat = UI.flattenFolders(state.tree);
      render();
    } catch (err) {
      els.tree.innerHTML = "<li>" + UI.renderEmpty(err.message || "加载失败") + "</li>";
    }
  }

  function parentOptionsHtml(selectedId, excludeId) {
    var html = '<option value="">无（顶层）</option>';
    state.flat.forEach(function (f) {
      if (excludeId && f.id === excludeId) return;
      html += '<option value="' + f.id + '"' + (String(f.id) === String(selectedId) ? " selected" : "") +
        ">" + UI.escapeHtml(f.label) + "</option>";
    });
    return html;
  }

  function openCreateModal(parentId) {
    var body =
      '<div class="form-field"><label>文件夹名称</label>' +
        '<input class="input" id="folder-name" type="text" placeholder="请输入名称"></div>' +
      '<div class="form-field"><label>父文件夹</label><select class="select" id="folder-parent">' +
        parentOptionsHtml(parentId) + "</select></div>";
    UI.openModal("新建文件夹", body, async function (modal) {
      var name = modal.querySelector("#folder-name").value.trim();
      var parentVal = modal.querySelector("#folder-parent").value;
      if (!name) { UI.toast("请输入文件夹名称", "warning"); return false; }
      try {
        await API.post("/api/admin/folders", {
          name: name,
          parent_id: parentVal ? Number(parentVal) : null
        });
        UI.toast("已创建文件夹", "success");
        load();
        return true;
      } catch (err) {
        UI.toast(err.message || "创建失败", "error");
        return false;
      }
    });
  }

  function openRenameModal(node) {
    var body = '<div class="form-field"><label>文件夹名称</label>' +
      '<input class="input" id="folder-name" type="text" value="' + UI.escapeHtml(node.name) + '"></div>';
    UI.openModal("重命名文件夹", body, async function (modal) {
      var name = modal.querySelector("#folder-name").value.trim();
      if (!name) { UI.toast("请输入文件夹名称", "warning"); return false; }
      try {
        await API.patch("/api/admin/folders/" + node.id, { name: name });
        UI.toast("已重命名", "success");
        load();
        return true;
      } catch (err) {
        UI.toast(err.message || "重命名失败", "error");
        return false;
      }
    });
  }

  function openMoveModal(node) {
    var body = '<div class="form-field"><label>移动到</label><select class="select" id="folder-parent">' +
      parentOptionsHtml(node.parent_id, node.id) + "</select>" +
      '<div class="form-hint">不能移动到自身或其子文件夹下</div></div>';
    UI.openModal("移动文件夹", body, async function (modal) {
      var parentVal = modal.querySelector("#folder-parent").value;
      try {
        await API.patch("/api/admin/folders/" + node.id, {
          parent_id: parentVal ? Number(parentVal) : null
        });
        UI.toast("已移动", "success");
        load();
        return true;
      } catch (err) {
        UI.toast(err.message || "移动失败", "error");
        return false;
      }
    });
  }

  async function deleteFolder(node) {
    var yes = await UI.confirmDialog(
      "确定删除文件夹「" + node.name + "」吗？其下图片将归入父级（顶层则归为未分类），子文件夹将上移。"
    );
    if (!yes) return;
    try {
      await API.del("/api/admin/folders/" + node.id);
      UI.toast("已删除文件夹", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "删除失败", "error");
    }
  }

  function findNode(id) {
    var found = null;
    (function walk(nodes) {
      (nodes || []).forEach(function (n) {
        if (String(n.id) === String(id)) found = n;
        else if (n.children) walk(n.children);
      });
    })(state.tree);
    return found;
  }

  function bindTreeEvents() {
    if (!els.tree) return;
    els.tree.addEventListener("click", function (e) {
      var toggle = e.target.closest(".tree-toggle");
      if (toggle && !toggle.classList.contains("placeholder")) {
        toggle.closest(".tree-node").classList.toggle("collapsed");
        return;
      }
      var btn = e.target.closest("button[data-act]");
      if (!btn) return;
      var nodeEl = btn.closest(".tree-node");
      var node = findNode(nodeEl.dataset.id);
      if (!node) return;
      var act = btn.dataset.act;
      if (act === "add") openCreateModal(node.id);
      else if (act === "rename") openRenameModal(node);
      else if (act === "move") openMoveModal(node);
      else if (act === "delete") deleteFolder(node);
    });
  }

  Layout.boot({
    active: "folders",
    onReady: function () {
      cacheEls();
      bindTreeEvents();
      els.newBtn.addEventListener("click", function () { openCreateModal(null); });
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
