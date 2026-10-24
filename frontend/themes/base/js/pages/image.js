/* 图片详情页：按 ?id=（可选 folder_id）加载详情，加密分类自动解锁重试；
   评论请求携带 X-Folder-Token。 */
(function () {
  'use strict';

  var PAGE_SIZE = 20;
  var state = { imageId: null, folderId: '', folderToken: '', detailRetried: false };
  var commentsEnabled = true;
  var commentState = { page: 1, pages: 0 };

  function folderHeaders() {
    return state.folderToken ? { 'X-Folder-Token': state.folderToken } : null;
  }

  function detailPath() {
    var path = '/api/images/' + encodeURIComponent(state.imageId);
    if (state.folderToken) {
      path = FolderAccess.withToken(path, state.folderToken);
    }
    return path;
  }

  /* ---------- 评论区 ---------- */

  function commentAvatar(user) {
    var name = (user && (user.nickname || user.username)) || '匿';
    if (user && user.avatar_url) {
      return '<span class="comment__avatar"><img src="' + UI.escapeHtml(user.avatar_url) +
        '" alt="" loading="lazy"></span>';
    }
    return '<span class="comment__avatar comment__avatar--text">' +
      UI.escapeHtml(String(name).charAt(0).toUpperCase()) + '</span>';
  }

  function commentHtml(comment) {
    var user = comment.user || {};
    var name = user.nickname || user.username || '匿名用户';
    return '<article class="comment">' + commentAvatar(user) +
      '<div class="comment__body">' +
        '<div class="comment__meta">' +
          '<span class="comment__author">' + UI.escapeHtml(name) + '</span>' +
          '<span class="comment__time">' + UI.escapeHtml(UI.formatDate(comment.created_at)) + '</span>' +
        '</div>' +
        '<div class="comment__content">' + UI.escapeHtml(comment.content) + '</div>' +
      '</div>' +
    '</article>';
  }

  function loginRedirect() {
    var target = 'image.html?id=' + encodeURIComponent(state.imageId);
    if (state.folderId) target += '&folder_id=' + encodeURIComponent(state.folderId);
    return encodeURIComponent(target);
  }

  /** 渲染评论表单区：区分未登录 / 已登录 / 评论已关闭。 */
  function renderFormSlot() {
    var slot = document.getElementById('comment-form-slot');
    if (!slot) return;

    if (!commentsEnabled) {
      slot.innerHTML = '<p class="muted">评论已关闭</p>';
      return;
    }
    if (!window.UserSession || !UserSession.isLoggedIn()) {
      slot.innerHTML = '<div class="comment-form">' +
        '<p class="muted">登录后可评论</p>' +
        '<div class="comment-form__actions">' +
          '<a class="btn btn--primary" href="login.html?redirect=' + loginRedirect() + '">登录后评论</a>' +
        '</div>' +
      '</div>';
      return;
    }

    slot.innerHTML = '<form class="comment-form" id="comment-form">' +
      '<textarea id="comment-content" class="textarea" maxlength="1000" placeholder="写下你的评论…"></textarea>' +
      '<div class="comment-form__actions">' +
        '<button class="btn btn--primary" type="submit" id="comment-submit">发表评论</button>' +
      '</div>' +
    '</form>';
    var form = document.getElementById('comment-form');
    if (form) form.addEventListener('submit', submitComment);
  }

  async function submitComment(e) {
    e.preventDefault();
    var textarea = document.getElementById('comment-content');
    var btn = document.getElementById('comment-submit');
    var content = (textarea && textarea.value ? textarea.value : '').trim();
    if (!content) { UI.toast('请输入评论内容', 'warning'); return; }

    btn.disabled = true;
    btn.textContent = '发表中…';
    try {
      await API.postJSON(
        '/api/images/' + encodeURIComponent(state.imageId) + '/comments',
        { content: content },
        { headers: folderHeaders() }
      );
      if (textarea) textarea.value = '';
      UI.toast('评论已发表', 'success');
      commentState.page = 1;
      await loadComments();
    } catch (err) {
      if (err.status === 401) {
        // 令牌已失效：清理本地登录态，避免继续显示“已登录”的评论表单
        if (window.UserSession) UserSession.clear();
        UI.toast('登录已过期，请重新登录', 'error');
        renderFormSlot();
      } else {
        UI.toast(err.message || '发表失败', 'error');
      }
    } finally {
      var btnNow = document.getElementById('comment-submit');
      if (btnNow) { btnNow.disabled = false; btnNow.textContent = '发表评论'; }
    }
  }

  async function loadComments() {
    var listEl = document.getElementById('comment-list');
    var pagEl = document.getElementById('comment-pagination');
    if (!listEl || !pagEl) return;

    listEl.innerHTML = '<p class="muted">评论加载中…</p>';
    pagEl.innerHTML = '';
    try {
      var data = await API.get(
        '/api/images/' + encodeURIComponent(state.imageId) +
        '/comments?page=' + commentState.page + '&page_size=' + PAGE_SIZE,
        { headers: folderHeaders() }
      );
      var items = data.items || [];
      commentState.pages = data.pages || 0;
      listEl.innerHTML = items.length
        ? items.map(commentHtml).join('')
        : '<p class="muted">暂无评论</p>';
      UI.renderPagination(pagEl, { page: commentState.page, pages: commentState.pages }, function (page) {
        commentState.page = page;
        loadComments();
      });
    } catch (e) {
      listEl.innerHTML = '<p class="muted">评论加载失败</p>';
    }
  }

  async function initComments() {
    var section = document.getElementById('comments');
    if (section) section.hidden = false;

    // 评论开关复用布局已请求的 /api/site（仅一次请求），失败默认开启
    try {
      var site = await Layout.loadSite();
      if (site && site.comments_enabled === false) commentsEnabled = false;
    } catch (e) { /* 默认开启 */ }

    renderFormSlot();
    loadComments();
  }

  /* ---------- 详情加载 ---------- */

  function syncFolderToUrl() {
    if (!state.folderId) return;
    var params = new URLSearchParams(window.location.search);
    params.set('id', state.imageId);
    params.set('folder_id', state.folderId);
    window.history.replaceState(null, '', window.location.pathname + '?' + params.toString());
  }

  async function loadDetail(wrap) {
    try {
      var image = await API.get(detailPath());
      wrap.innerHTML = UI.renderImageDetail(image, { folderToken: state.folderToken });
      document.title = UI.imageTitle(image) + ' - 图片详情';
      await initComments();
    } catch (e) {
      var lockedId = e.folder_id || (e.detail && typeof e.detail === 'object' ? e.detail.folder_id : null);
      if (e.status === 403 && !state.detailRetried) {
        state.detailRetried = true;
        if (lockedId) {
          state.folderId = String(lockedId);
          FolderAccess.clear(lockedId);
          UI.toast('该分类已加密，请先解锁', 'warning');
          var token = await FolderAccess.ensure(lockedId);
          if (token) {
            state.folderToken = token;
            syncFolderToUrl();
            return loadDetail(wrap);
          }
          wrap.innerHTML = UI.renderError('分类已加密', '需要输入分类访问密码后才能查看该图片。');
          return;
        }
        wrap.innerHTML = UI.renderError('无法查看该图片', '该图片所属分类已加密，请从分类页进入并解锁。');
        return;
      }
      wrap.innerHTML = UI.renderError('无法查看该图片', e.message);
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    var wrap = document.getElementById('detail');
    await Layout.init('');

    var params = new URLSearchParams(window.location.search);
    var id = params.get('id');
    if (!id) {
      wrap.innerHTML = UI.renderError('缺少图片 ID', '请从图库中选择一张图片进行查看。');
      return;
    }

    state.imageId = id;
    state.folderId = params.get('folder_id') || '';
    state.folderToken = state.folderId ? (FolderAccess.get(state.folderId) || '') : '';

    await loadDetail(wrap);
  });
})();
