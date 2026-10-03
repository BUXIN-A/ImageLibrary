/**
 * 标签管理：列表、新建、删除。
 */
(function () {
  "use strict";

  var els = {};

  function cacheEls() {
    els.form = document.getElementById("tag-form");
    els.name = document.getElementById("tag-name");
    els.list = document.getElementById("tag-list");
    els.total = document.getElementById("tag-total");
  }

  function render(tags) {
    els.total.textContent = "共 " + tags.length + " 个";
    if (!tags.length) {
      els.list.innerHTML = UI.renderEmpty("暂无标签，请在上方新建");
      return;
    }
    els.list.innerHTML = tags.map(function (tag) {
      return '<span class="tag-chip" data-id="' + tag.id + '" data-name="' +
        UI.escapeHtml(tag.name) + '">' +
        UI.escapeHtml(tag.name) +
        '<span class="tag-count">(' + (tag.image_count || 0) + ")</span>" +
        '<button type="button" class="tag-remove" data-act="delete" title="删除">&times;</button>' +
        "</span>";
    }).join("");
  }

  async function load() {
    els.list.innerHTML = '<div class="loading"><span class="spinner"></span>加载中…</div>';
    try {
      var tags = await API.get("/api/tags");
      render(tags || []);
    } catch (err) {
      els.list.innerHTML = UI.renderEmpty(err.message || "加载失败");
      els.total.textContent = "";
    }
  }

  function bindEvents() {
    els.form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var name = els.name.value.trim();
      if (!name) { UI.toast("请输入标签名称", "warning"); return; }
      try {
        await API.post("/api/admin/tags", { name: name });
        els.name.value = "";
        UI.toast("已创建标签", "success");
        load();
      } catch (err) {
        UI.toast(err.message || "创建失败", "error");
      }
    });

    els.list.addEventListener("click", async function (e) {
      var btn = e.target.closest('[data-act="delete"]');
      if (!btn) return;
      var chip = btn.closest(".tag-chip");
      var name = chip.dataset.name;
      var yes = await UI.confirmDialog("确定删除标签「" + name + "」吗？将解除其与图片的关联。");
      if (!yes) return;
      try {
        await API.del("/api/admin/tags/" + chip.dataset.id);
        UI.toast("已删除标签", "success");
        load();
      } catch (err) {
        UI.toast(err.message || "删除失败", "error");
      }
    });
  }

  Layout.boot({
    active: "tags",
    onReady: function () {
      cacheEls();
      bindEvents();
      load();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
