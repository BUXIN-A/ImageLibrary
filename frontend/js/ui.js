/* 通用 UI 工具：Toast、格式化、空状态、分页、弹窗、图片卡片与详情渲染。 */
(function () {
  'use strict';

  /* ---------- Toast ---------- */
  function ensureToastRoot() {
    var host = document.body || document.documentElement;
    if (!host) return null;
    var root = document.getElementById('toast-root');
    if (!root) {
      root = document.createElement('div');
      root.id = 'toast-root';
      host.appendChild(root);
    }
    return root;
  }

  /**
   * 显示轻提示。
   * @param {string} message 文案
   * @param {string} [type] info | success | error | warning
   */
  function toast(message, type) {
    try {
      if (!message) return;
      var root = ensureToastRoot();
      if (!root) return;
      var el = document.createElement('div');
      el.className = 'toast toast--' + (type || 'info');
      el.setAttribute('role', 'status');
      el.textContent = message;
      root.appendChild(el);
      requestAnimationFrame(function () { el.classList.add('is-visible'); });
      var timer = setTimeout(function () {
        el.classList.remove('is-visible');
        setTimeout(function () { el.remove(); }, 260);
      }, 3200);
      el.addEventListener('click', function () {
        clearTimeout(timer);
        el.remove();
      });
    } catch (e) { /* 提示失败不应影响业务逻辑 */ }
  }

  /* ---------- 格式化 ---------- */
  function formatSize(bytes) {
    var n = Number(bytes);
    if (!isFinite(n) || n <= 0) return '0 B';
    var units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var i = Math.floor(Math.log(n) / Math.log(1024));
    if (i < 0) i = 0;
    if (i >= units.length) i = units.length - 1;
    var val = n / Math.pow(1024, i);
    return (i === 0 ? String(val) : val.toFixed(val >= 100 ? 0 : 1)) + ' ' + units[i];
  }

  function pad2(x) { return x < 10 ? '0' + x : '' + x; }

  function formatDate(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) +
      ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }

  function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function imageTitle(image) {
    if (!image) return '未命名图片';
    return image.title || image.original_name || '未命名图片';
  }

  /* ---------- 空状态 / 骨架屏 / 错误块 ---------- */
  function renderEmpty(text) {
    return '<div class="empty-state">' +
      '<svg viewBox="0 0 24 24" width="46" height="46" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<rect x="3" y="3" width="18" height="18" rx="2"></rect>' +
      '<circle cx="8.5" cy="8.5" r="1.5"></circle><path d="m21 15-5-5L5 21"></path></svg>' +
      '<p>' + escapeHtml(text || '暂无数据') + '</p></div>';
  }

  function renderSkeleton(count) {
    var n = count || 12;
    var html = '';
    for (var i = 0; i < n; i++) {
      html += '<div class="skeleton-card"><div class="skeleton skeleton--media"></div>' +
        '<div class="skeleton skeleton--line"></div><div class="skeleton skeleton--line skeleton--short"></div></div>';
    }
    return html;
  }

  function renderError(title, text) {
    return '<div class="error-block">' +
      '<h2 class="error-block__title">' + escapeHtml(title || '出错了') + '</h2>' +
      '<p class="error-block__text">' + escapeHtml(text || '') + '</p>' +
      '<a class="btn btn--primary" href="index.html">返回首页</a></div>';
  }

  /* ---------- 分页 ---------- */
  function pageItems(page, pages) {
    var out = [];
    function add(v) { if (out.indexOf(v) === -1) out.push(v); }
    if (pages <= 7) {
      for (var i = 1; i <= pages; i++) add(i);
      return out;
    }
    add(1);
    var start = Math.max(2, page - 1);
    var end = Math.min(pages - 1, page + 1);
    if (start > 2) add('...');
    for (var j = start; j <= end; j++) add(j);
    if (end < pages - 1) add('...');
    add(pages);
    return out;
  }

  /**
   * 渲染分页控件。
   * @param {HTMLElement} container 容器
   * @param {{page:number,pages:number}} opts 分页信息
   * @param {(page:number)=>void} onChange 切页回调
   */
  function renderPagination(container, opts, onChange) {
    if (!container) return;
    var page = opts.page || 1;
    var pages = opts.pages || 0;
    if (pages <= 1) { container.innerHTML = ''; return; }
    var items = pageItems(page, pages);
    var html = '<button class="page-btn" type="button" data-page="' + (page - 1) + '"' +
      (page <= 1 ? ' disabled' : '') + '>上一页</button>';
    items.forEach(function (it) {
      if (it === '...') { html += '<span class="page-ellipsis">…</span>'; return; }
      html += '<button class="page-btn' + (it === page ? ' is-active' : '') +
        '" type="button" data-page="' + it + '">' + it + '</button>';
    });
    html += '<button class="page-btn" type="button" data-page="' + (page + 1) + '"' +
      (page >= pages ? ' disabled' : '') + '>下一页</button>';
    container.innerHTML = html;
    container.querySelectorAll('button[data-page]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var p = parseInt(btn.getAttribute('data-page'), 10);
        if (!p || p < 1 || p > pages || p === page) return;
        onChange(p);
      });
    });
  }

  /* ---------- 弹窗 ---------- */
  function openModal(html) {
    closeModal();
    if (!document.body) return null;
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = '<div class="modal" role="dialog" aria-modal="true">' + html + '</div>';
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal();
    });
    document.body.appendChild(overlay);
    document.body.classList.add('modal-open');
    return overlay;
  }

  function closeModal() {
    var el = document.querySelector('.modal-overlay');
    if (el) el.remove();
    document.body.classList.remove('modal-open');
  }

  /** 确认弹窗，返回 Promise<boolean>。 */
  function confirmDialog(message, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var overlay = openModal(
        '<div class="modal__body">' +
        '<h3 class="modal__title">' + escapeHtml(opts.title || '确认操作') + '</h3>' +
        '<p class="modal__text">' + escapeHtml(message || '') + '</p></div>' +
        '<div class="modal__footer">' +
        '<button class="btn btn--ghost" type="button" data-act="cancel">取消</button>' +
        '<button class="btn btn--danger" type="button" data-act="ok">' + escapeHtml(opts.okText || '确定') + '</button>' +
        '</div>'
      );
      overlay.querySelector('[data-act="cancel"]').addEventListener('click', function () {
        closeModal(); resolve(false);
      });
      overlay.querySelector('[data-act="ok"]').addEventListener('click', function () {
        closeModal(); resolve(true);
      });
    });
  }

  // 点击遮罩或按 Esc 关闭弹窗
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeModal();
  });

  /* ---------- 图片卡片 ---------- */
  /**
   * 渲染图片卡片 HTML。
   * @param {object} image ImageOut
   * @param {{selectable?:boolean, checked?:boolean}} [opts]
   */
  function renderImageCard(image, opts) {
    opts = opts || {};
    var id = image.id;
    var thumb = window.API.mediaUrl(image.thumb_url);
    var title = imageTitle(image);
    var html = '<article class="image-card" data-id="' + id + '">';
    html += '<div class="image-card__media">';
    html += '<a class="image-card__link" href="image.html?id=' + id + '">';
    html += '<img loading="lazy" src="' + escapeHtml(thumb) + '" alt="' + escapeHtml(title) + '">';
    html += '</a>';
    if (opts.selectable) {
      html += '<label class="image-card__check" title="选择此图片">' +
        '<input type="checkbox" class="js-select" value="' + id + '"' + (opts.checked ? ' checked' : '') + '>' +
        '<span class="image-card__check-box"></span></label>';
    }
    html += '</div>';
    html += '<div class="image-card__body">';
    html += '<a class="image-card__title" href="image.html?id=' + id + '" title="' + escapeHtml(title) + '">' +
      escapeHtml(title) + '</a>';
    html += '<div class="image-card__meta"><span class="meta-view">' +
      '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>' +
      (image.views || 0) + '</span></div>';
    html += '</div></article>';
    return html;
  }

  /* ---------- 详情渲染（image.html 与 share.html 复用） ---------- */
  var EXIF_LABELS = {
    taken_at: '拍摄时间',
    camera_make: '相机厂商',
    camera_model: '相机型号',
    lens: '镜头',
    iso: 'ISO',
    f_number: '光圈',
    exposure_time: '快门',
    focal_length: '焦距',
    orientation: '方向'
  };

  function renderExif(exif) {
    if (!exif || typeof exif !== 'object') return '';
    var rows = '';
    Object.keys(EXIF_LABELS).forEach(function (key) {
      var v = exif[key];
      if (v === null || v === undefined || v === '') return;
      rows += '<tr><th>' + EXIF_LABELS[key] + '</th><td>' + escapeHtml(String(v)) + '</td></tr>';
    });
    if (!rows) return '';
    return '<section class="detail__section">' +
      '<h2 class="detail__section-title">EXIF 信息</h2>' +
      '<table class="table exif-table"><tbody>' + rows + '</tbody></table></section>';
  }

  function renderImageDetail(image) {
    var url = window.API.mediaUrl(image.url);
    var thumb = window.API.mediaUrl(image.thumb_url);
    var title = imageTitle(image);
    var downloadUrl = window.API.apiUrl('/api/images/' + image.id + '/download');

    var html = '<div class="detail">';
    html += '<div class="detail__media"><img src="' + escapeHtml(url) + '" alt="' + escapeHtml(title) + '"></div>';
    html += '<div class="detail__info">';
    html += '<a class="detail__back" href="index.html">← 返回图库</a>';
    html += '<h1 class="detail__title">' + escapeHtml(title) + '</h1>';
    if (image.description) {
      html += '<p class="detail__desc">' + escapeHtml(image.description).replace(/\n/g, '<br>') + '</p>';
    }
    html += '<div class="detail__actions">';
    html += '<a class="btn btn--primary" href="' + escapeHtml(downloadUrl) + '">下载原图</a>';
    if (image.folder_id) {
      html += '<a class="btn btn--ghost" href="folder.html?id=' + image.folder_id + '">查看文件夹</a>';
    }
    html += '</div>';

    var meta = [
      ['尺寸', (image.width || 0) + ' × ' + (image.height || 0) + ' 像素'],
      ['类型', image.mime_type || '未知'],
      ['大小', formatSize(image.size)],
      ['浏览', (image.views || 0) + ' 次'],
      ['下载', (image.downloads || 0) + ' 次']
    ];
    if (image.created_at) meta.push(['上传时间', formatDate(image.created_at)]);
    if (image.folder_name) meta.push(['所属文件夹', image.folder_name]);
    html += '<dl class="meta-list">';
    meta.forEach(function (row) {
      html += '<div class="meta-list__row"><dt>' + row[0] + '</dt><dd>' + escapeHtml(row[1]) + '</dd></div>';
    });
    html += '</dl>';

    if (image.tags && image.tags.length) {
      html += '<div class="tag-list">';
      image.tags.forEach(function (tag) {
        html += '<a class="tag" href="search.html?tag=' + encodeURIComponent(tag.name) + '">' +
          escapeHtml(tag.name) + '</a>';
      });
      html += '</div>';
    }

    html += renderExif(image.exif);
    html += '</div></div>';
    return html;
  }

  /* ---------- 文件夹工具 ---------- */
  /** 将文件夹树展平为带层级深度的数组，供下拉选择使用。 */
  function flattenFolders(nodes, depth) {
    var out = [];
    depth = depth || 0;
    (nodes || []).forEach(function (n) {
      out.push({ id: n.id, name: n.name, depth: depth, image_count: n.image_count || 0 });
      if (n.children && n.children.length) {
        out = out.concat(flattenFolders(n.children, depth + 1));
      }
    });
    return out;
  }

  // 全局捕获图片加载失败，统一显示占位样式（避免内联事件注入问题）
  window.addEventListener('error', function (e) {
    var t = e.target;
    if (t && t.tagName === 'IMG') {
      var media = (t.closest && (t.closest('.image-card__media') || t.closest('.detail__media')));
      if (media) media.classList.add('is-error');
    }
  }, true);

  window.UI = {
    toast: toast,
    formatSize: formatSize,
    formatDate: formatDate,
    escapeHtml: escapeHtml,
    imageTitle: imageTitle,
    renderEmpty: renderEmpty,
    renderSkeleton: renderSkeleton,
    renderError: renderError,
    renderPagination: renderPagination,
    confirmDialog: confirmDialog,
    openModal: openModal,
    closeModal: closeModal,
    renderImageCard: renderImageCard,
    renderImageDetail: renderImageDetail,
    renderExif: renderExif,
    flattenFolders: flattenFolders
  };
})();
