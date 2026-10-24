/**
 * 文件夹管理：扁平分类列表，支持新建、重命名、访问密码、排序与删除。
 */
(function () {
  "use strict";

  var state = { folders: [] };
  var els = {};

  function cacheEls() {
    els.tbody = document.getElementById("folder-tbody");
    els.newBtn = document.getElementById("new-folder-btn");
  }

  function findFolder(id) {
    return state.folders.find(function (f) { return String(f.id) === String(id); }) || null;
  }

  function rowHtml(folder, index) {
    var locked = folder.has_password
      ? '<span class="badge badge-primary">已加密</span>'
      : '<span class="badge badge-muted">公开</span>';
    var clearBtn = folder.has_password
      ? '<button type="button" class="btn btn-ghost btn-sm" data-act="clear-password">清除密码</button>'
      : "";

    return (
      '<tr data-id="' + folder.id + '">' +
        "<td>" + UI.escapeHtml(folder.name) + "</td>" +
        "<td>" + (folder.image_count || 0) + "</td>" +
        "<td>" + locked + "</td>" +
        "<td>" + (folder.sort_order || 0) + "</td>" +
        '<td><div class="row-actions">' +
          '<button type="button" class="btn btn-outline btn-sm" data-act="up"' +
            (index === 0 ? " disabled" : "") + ">上移</button>" +
          '<button type="button" class="btn btn-outline btn-sm" data-act="down"' +
            (index === state.folders.length - 1 ? " disabled" : "") + ">下移</button>" +
          '<button type="button" class="btn btn-ghost btn-sm" data-act="rename">重命名</button>' +
          '<button type="button" class="btn btn-ghost btn-sm" data-act="password">' +
            (folder.has_password ? "修改密码" : "设置密码") + "</button>" +
          clearBtn +
          '<button type="button" class="btn btn-ghost btn-sm text-danger" data-act="delete">删除</button>' +
        "</div></td>" +
      "</tr>"
    );
  }

  function render() {
    if (!els.tbody) return;
    if (!state.folders.length) {
      els.tbody.innerHTML = '<tr><td colspan="5">' + UI.renderEmpty("暂无分类，点击右上角新建") + "</td></tr>";
      return;
    }
    els.tbody.innerHTML = state.folders.map(rowHtml).join("");
  }

  async function load() {
    if (els.tbody) {
      els.tbody.innerHTML = '<tr><td colspan="5"><div class="loading"><span class="spinner"></span>加载中…</div></td></tr>';
    }
    try {
      var folders = await API.get("/api/folders");
      state.folders = Array.isArray(folders) ? folders : [];
      render();
    } catch (err) {
      els.tbody.innerHTML = '<tr><td colspan="5">' + UI.renderEmpty(err.message || "加载失败") + "</td></tr>";
    }
  }

  function openCreateModal() {
    var body =
      '<div class="form-field"><label for="folder-name">分类名称</label>' +
        '<input class="input" id="folder-name" type="text" placeholder="请输入分类名称"></div>' +
      '<div class="form-field"><label for="folder-password">访问密码（可选）</label>' +
        '<input class="input" id="folder-password" type="password" autocomplete="new-password" placeholder="留空表示公开访问"></div>' +
      '<div class="form-hint">设置密码后，访客进入该分类需要先输入密码。</div>';

    UI.openModal("新建分类", body, async function (modal) {
      var name = modal.querySelector("#folder-name").value.trim();
      var password = modal.querySelector("#folder-password").value;
      if (!name) { UI.toast("请输入分类名称", "warning"); return false; }
      var payload = { name: name };
      if (password) payload.password = password;
      try {
        await API.post("/api/admin/folders", payload);
        UI.toast("已创建分类", "success");
        load();
        return true;
      } catch (err) {
        UI.toast(err.message || "创建失败", "error");
        return false;
      }
    });
  }

  function openRenameModal(folder) {
    var body = '<div class="form-field"><label for="folder-name">分类名称</label>' +
      '<input class="input" id="folder-name" type="text" value="' + UI.escapeHtml(folder.name) + '"></div>';
    UI.openModal("重命名分类", body, async function (modal) {
      var name = modal.querySelector("#folder-name").value.trim();
      if (!name) { UI.toast("请输入分类名称", "warning"); return false; }
      try {
        await API.patch("/api/admin/folders/" + folder.id, { name: name });
        UI.toast("已重命名", "success");
        load();
        return true;
      } catch (err) {
        UI.toast(err.message || "重命名失败", "error");
        return false;
      }
    });
  }

  function openPasswordModal(folder) {
    var hint = folder.has_password
      ? "该分类已设置密码，填写新密码将覆盖原密码。"
      : "设置密码后，访客进入该分类需要先输入密码。";
    var body =
      '<div class="form-field"><label for="folder-password">新访问密码</label>' +
        '<input class="input" id="folder-password" type="password" autocomplete="new-password" placeholder="请输入新密码"></div>' +
      '<div class="form-hint">' + UI.escapeHtml(hint) + "</div>";

    UI.openModal("设置访问密码", body, async function (modal) {
      var password = modal.querySelector("#folder-password").value;
      if (!password) { UI.toast("请输入访问密码", "warning"); return false; }
      try {
        await API.patch("/api/admin/folders/" + folder.id, { password: password });
        UI.toast("密码已更新", "success");
        load();
        return true;
      } catch (err) {
        UI.toast(err.message || "设置失败", "error");
        return false;
      }
    });
  }

  async function clearPassword(folder) {
    var yes = await UI.confirmDialog(
      "确定清除分类「" + folder.name + "」的访问密码吗？清除后该分类将公开访问。",
      "清除密码"
    );
    if (!yes) return;
    try {
      await API.patch("/api/admin/folders/" + folder.id, { password: "" });
      UI.toast("密码已清除", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "清除失败", "error");
    }
  }

  async function deleteFolder(folder) {
    var yes = await UI.confirmDialog(
      "确定删除分类「" + folder.name + "」吗？该分类下的图片将变为未分类。",
      "删除"
    );
    if (!yes) return;
    try {
      await API.del("/api/admin/folders/" + folder.id);
      UI.toast("已删除分类", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "删除失败", "error");
    }
  }

  async function moveFolder(folder, direction) {
    var index = state.folders.indexOf(folder);
    var neighbor = state.folders[index + direction];
    if (!neighbor) return;

    var currentOrder = Number(folder.sort_order) || 0;
    var neighborOrder = Number(neighbor.sort_order) || 0;
    var targetOrder;
    var neighborTarget = currentOrder;

    if (currentOrder === neighborOrder) {
      targetOrder = neighborOrder + (direction < 0 ? -1 : 1);
      neighborTarget = neighborOrder;
    } else {
      targetOrder = neighborOrder;
    }

    try {
      await API.patch("/api/admin/folders/" + folder.id, { sort_order: targetOrder });
      if (neighborTarget !== targetOrder) {
        await API.patch("/api/admin/folders/" + neighbor.id, { sort_order: neighborTarget });
      }
      UI.toast("排序已更新", "success");
      load();
    } catch (err) {
      UI.toast(err.message || "排序失败", "error");
    }
  }

  function bindEvents() {
    if (els.newBtn) els.newBtn.addEventListener("click", openCreateModal);
    if (!els.tbody) return;

    els.tbody.addEventListener("click", function (e) {
      var btn = e.target.closest("button[data-act]");
      if (!btn || btn.disabled) return;
      var row = btn.closest("tr");
      var folder = row && findFolder(row.dataset.id);
      if (!folder) return;
      var act = btn.dataset.act;
      if (act === "up") moveFolder(folder, -1);
      else if (act === "down") moveFolder(folder, 1);
      else if (act === "rename") openRenameModal(folder);
      else if (act === "password") openPasswordModal(folder);
      else if (act === "clear-password") clearPassword(folder);
      else if (act === "delete") deleteFolder(folder);
    });
  }

  Layout.boot({
    active: "folders",
    onReady: function () {
      cacheEls();
      bindEvents();
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
