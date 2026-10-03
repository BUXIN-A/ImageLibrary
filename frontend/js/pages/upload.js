/* 上传页：校验 Token、选择/拖拽图片并提交上传。 */
(function () {
  'use strict';

  var files = [];
  var tokenInput, validateBtn, tokenResult, dropzone, fileInput, fileList, uploadBtn, clearBtn, uploadResultEl;

  function renderTokenResult(html, type) {
    tokenResult.innerHTML = html
      ? '<div class="alert ' + (type ? 'alert--' + type : '') + '">' + html + '</div>'
      : '';
  }

  async function validateToken() {
    var token = (tokenInput.value || '').trim();
    if (!token) {
      renderTokenResult('请先输入上传 Token', 'warning');
      return;
    }
    validateBtn.disabled = true;
    validateBtn.textContent = '校验中…';
    try {
      var data = await API.get('/api/credential/validate?token=' + encodeURIComponent(token));
      if (data && data.valid) {
        var parts = ['Token 有效'];
        if (data.note) parts.push('备注：' + UI.escapeHtml(data.note));
        parts.push('剩余额度：' + (data.remaining === null || data.remaining === undefined ? '不限' : data.remaining));
        parts.push('单文件大小上限：' + (data.max_file_size ? UI.formatSize(data.max_file_size) : '按站点默认'));
        renderTokenResult(parts.join(' ｜ '), 'success');
      } else {
        renderTokenResult('Token 无效：' + UI.escapeHtml((data && data.reason) || '未知原因'), 'error');
      }
    } catch (e) {
      renderTokenResult('校验失败：' + UI.escapeHtml(e.message), 'error');
    } finally {
      validateBtn.disabled = false;
      validateBtn.textContent = '校验';
    }
  }

  function isImageFile(file) {
    return file && (file.type.indexOf('image/') === 0 || /\.(jpe?g|png|gif|webp|bmp)$/i.test(file.name || ''));
  }

  function addFiles(fileListObj) {
    var added = 0;
    Array.prototype.forEach.call(fileListObj, function (file) {
      if (!isImageFile(file)) return;
      var duplicate = files.some(function (f) { return f.name === file.name && f.size === file.size; });
      if (duplicate) return;
      files.push(file);
      added++;
    });
    if (added === 0) UI.toast('没有新增可上传的图片文件', 'warning');
    renderFileList();
  }

  function renderFileList() {
    fileList.innerHTML = files.map(function (file, index) {
      return '<li class="file-item">' +
        '<span class="file-item__name" title="' + UI.escapeHtml(file.name) + '">' + UI.escapeHtml(file.name) + '</span>' +
        '<span class="file-item__size">' + UI.formatSize(file.size) + '</span>' +
        '<button class="file-item__remove" type="button" data-index="' + index + '" aria-label="移除">×</button>' +
        '</li>';
    }).join('');
    fileList.querySelectorAll('.file-item__remove').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var index = parseInt(btn.getAttribute('data-index'), 10);
        files.splice(index, 1);
        renderFileList();
      });
    });
    uploadBtn.disabled = files.length === 0;
    uploadBtn.textContent = files.length ? ('开始上传（' + files.length + '）') : '开始上传';
  }

  function renderUploadResults(data) {
    var html = '<div class="alert ' + (data.failed ? 'alert--warning' : 'alert--success') + '">' +
      UI.escapeHtml(data.message || '已提交') +
      '　成功 ' + (data.success || 0) + ' 个，失败 ' + (data.failed || 0) + ' 个' +
      '<ul class="alert__list">';
    (data.results || []).forEach(function (item) {
      html += '<li>' + (item.ok
        ? '<span class="result-ok">✔</span> '
        : '<span class="result-fail">✘</span> ') +
        UI.escapeHtml(item.filename || '') +
        (item.ok ? '' : '　' + UI.escapeHtml(item.error || '失败')) + '</li>';
    });
    html += '</ul></div>';
    uploadResultEl.innerHTML = html;
  }

  async function upload() {
    var token = (tokenInput.value || '').trim();
    if (!token) {
      UI.toast('请先输入上传 Token', 'warning');
      tokenInput.focus();
      return;
    }
    if (!files.length) {
      UI.toast('请先选择要上传的图片', 'warning');
      return;
    }

    var formData = new FormData();
    formData.append('token', token);
    files.forEach(function (file) { formData.append('files', file); });

    uploadBtn.disabled = true;
    uploadBtn.textContent = '上传中…';
    uploadResultEl.innerHTML = '';

    try {
      var data = await API.postForm('/api/credential/upload', formData);
      renderUploadResults(data);
      UI.toast(data.message || '已提交，等待管理员审核', data.failed ? 'warning' : 'success');
      // 上传成功后清空文件，便于继续上传
      files = [];
      renderFileList();
    } catch (e) {
      if (e.status === 429) {
        uploadResultEl.innerHTML = '<div class="alert alert--error">上传过于频繁，请稍后再试</div>';
        UI.toast('上传过于频繁，请稍后再试', 'error');
      } else {
        uploadResultEl.innerHTML = '<div class="alert alert--error">' + UI.escapeHtml(e.message) + '</div>';
        UI.toast(e.message, 'error');
      }
    } finally {
      uploadBtn.disabled = files.length === 0;
      uploadBtn.textContent = files.length ? ('开始上传（' + files.length + '）') : '开始上传';
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    tokenInput = document.getElementById('token');
    validateBtn = document.getElementById('validate-btn');
    tokenResult = document.getElementById('token-result');
    dropzone = document.getElementById('dropzone');
    fileInput = document.getElementById('file-input');
    fileList = document.getElementById('file-list');
    uploadBtn = document.getElementById('upload-btn');
    clearBtn = document.getElementById('clear-btn');
    uploadResultEl = document.getElementById('upload-result');

    await Layout.init('upload');

    validateBtn.addEventListener('click', validateToken);
    tokenInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); validateToken(); }
    });

    dropzone.addEventListener('click', function () { fileInput.click(); });
    dropzone.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
    });
    fileInput.addEventListener('change', function () {
      addFiles(fileInput.files);
      fileInput.value = '';
    });

    ['dragenter', 'dragover'].forEach(function (evt) {
      dropzone.addEventListener(evt, function (e) {
        e.preventDefault();
        dropzone.classList.add('is-dragover');
      });
    });
    ['dragleave', 'dragend'].forEach(function (evt) {
      dropzone.addEventListener(evt, function (e) {
        e.preventDefault();
        dropzone.classList.remove('is-dragover');
      });
    });
    dropzone.addEventListener('drop', function (e) {
      e.preventDefault();
      dropzone.classList.remove('is-dragover');
      if (e.dataTransfer && e.dataTransfer.files) addFiles(e.dataTransfer.files);
    });

    clearBtn.addEventListener('click', function () {
      files = [];
      renderFileList();
      uploadResultEl.innerHTML = '';
    });

    uploadBtn.addEventListener('click', upload);

    renderFileList();
  });
})();
