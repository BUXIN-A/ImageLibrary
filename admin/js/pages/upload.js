/**
 * 上传页：拖拽 / 多选文件 + 标题、描述、文件夹、标签，批量上传并展示逐条结果。
 */
(function () {
  "use strict";

  var state = {
    files: [],
    folders: []
  };

  var els = {};

  function cacheEls() {
    els.form = document.getElementById("upload-form");
    els.title = document.getElementById("up-title");
    els.folder = document.getElementById("up-folder");
    els.tags = document.getElementById("up-tags");
    els.desc = document.getElementById("up-desc");
    els.dropzone = document.getElementById("dropzone");
    els.fileInput = document.getElementById("file-input");
    els.fileList = document.getElementById("file-list");
    els.selectedInfo = document.getElementById("selected-info");
    els.uploadBtn = document.getElementById("upload-btn");
    els.resultCard = document.getElementById("result-card");
    els.resultList = document.getElementById("result-list");
    els.resultSummary = document.getElementById("result-summary");
  }

  /** 合并新选择的文件（按 name+size 去重）。 */
  function addFiles(fileList) {
    Array.prototype.forEach.call(fileList, function (file) {
      if (!/^image\//.test(file.type)) {
        UI.toast("已忽略非图片文件：" + file.name, "warning");
        return;
      }
      var exists = state.files.some(function (f) {
        return f.name === file.name && f.size === file.size;
      });
      if (!exists) state.files.push(file);
    });
    renderFileList();
  }

  function renderFileList() {
    els.fileList.innerHTML = "";
    state.files.forEach(function (file, index) {
      var item = document.createElement("div");
      item.className = "file-item";
      item.innerHTML =
        '<span class="file-name">' + UI.escapeHtml(file.name) + "</span>" +
        '<span class="file-size">' + UI.formatSize(file.size) + "</span>" +
        '<button type="button" class="remove-file" title="移除">&times;</button>';
      item.querySelector(".remove-file").addEventListener("click", function () {
        state.files.splice(index, 1);
        renderFileList();
      });
      els.fileList.appendChild(item);
    });
    var count = state.files.length;
    els.selectedInfo.textContent = count ? "已选择 " + count + " 个文件" : "未选择文件";
    els.uploadBtn.disabled = count === 0;
  }

  function renderResults(data) {
    els.resultCard.classList.remove("hidden");
    els.resultSummary.textContent = "成功 " + (data.success || 0) + " 张，失败 " + (data.failed || 0) + " 张";
    els.resultList.innerHTML = "";
    (data.results || []).forEach(function (result) {
      var item = document.createElement("div");
      item.className = "result-item " + (result.ok ? "ok" : "fail");
      var thumb = result.ok && result.image
        ? '<img src="' + UI.escapeHtml(UI.mediaUrl(result.image.thumb_url)) + '" loading="lazy" alt="">'
        : '<div class="empty-state" style="padding:26px 8px;"><p class="text-danger">上传失败</p></div>';
      var meta = result.ok
        ? "<div>" + UI.escapeHtml(result.image && result.image.title ? result.image.title : result.filename) + "</div>"
        : '<div class="text-danger">' + UI.escapeHtml(result.error || "处理失败") + "</div>";
      item.innerHTML = thumb + '<div class="result-meta">' + meta + "</div>";
      els.resultList.appendChild(item);
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!state.files.length) return;
    els.uploadBtn.disabled = true;
    els.uploadBtn.textContent = "上传中…";

    var fd = new FormData();
    state.files.forEach(function (file) { fd.append("files", file); });
    var title = els.title.value.trim();
    var desc = els.desc.value.trim();
    var tags = els.tags.value.trim();
    var folderId = els.folder.value;
    if (title) fd.append("title", title);
    if (desc) fd.append("description", desc);
    if (tags) fd.append("tags", tags);
    if (folderId) fd.append("folder_id", folderId);

    try {
      var data = await API.postForm("/api/admin/images", fd);
      renderResults(data || { results: [], success: 0, failed: 0 });
      UI.toast("上传完成：成功 " + (data.success || 0) + "，失败 " + (data.failed || 0),
        (data.failed || 0) > 0 ? "warning" : "success");
      state.files = [];
      renderFileList();
      els.fileInput.value = "";
    } catch (err) {
      UI.toast(err.message || "上传失败", "error");
    } finally {
      els.uploadBtn.disabled = state.files.length === 0;
      els.uploadBtn.textContent = "开始上传";
    }
  }

  function bindDropzone() {
    els.dropzone.addEventListener("click", function () { els.fileInput.click(); });
    els.fileInput.addEventListener("change", function () { addFiles(els.fileInput.files); });

    ["dragenter", "dragover"].forEach(function (evt) {
      els.dropzone.addEventListener(evt, function (e) {
        e.preventDefault();
        els.dropzone.classList.add("dragover");
      });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      els.dropzone.addEventListener(evt, function (e) {
        e.preventDefault();
        els.dropzone.classList.remove("dragover");
      });
    });
    els.dropzone.addEventListener("drop", function (e) {
      if (e.dataTransfer && e.dataTransfer.files) addFiles(e.dataTransfer.files);
    });
  }

  async function loadFolders() {
    try {
      var tree = await API.get("/api/folders");
      state.folders = UI.flattenFolders(tree);
      UI.fillFolderSelect(els.folder, state.folders, { allLabel: "未分类" });
    } catch (err) {
      UI.toast("文件夹加载失败：" + err.message, "error");
    }
  }

  Layout.boot({
    active: "upload",
    onReady: function () {
      cacheEls();
      bindDropzone();
      loadFolders();
      els.form.addEventListener("submit", handleSubmit);
      renderFileList();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
