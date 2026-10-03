/* 图片详情页：根据 ?id= 加载并展示图片详情，并在下方渲染评论区。 */
(function () {
  'use strict';

  var PAGE_SIZE = 20;
  var imageId = null;
  var commentsEnabled = true;
  var commentState = { page: 1, pages: 0 };

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

  /** 渲染评论表单区：区分未登录 / 已登录 / 评论已关闭。 */
  function renderFormSlot() {
    var slot = document.getElementById('comment-form-slot');
    if (!slot) return;

    if (!commentsEnabled) {
      slot.innerHTML = '<p class="muted">评论已关闭</p>';
      return;
    }
    if (!window.UserSession || !UserSession.isLoggedIn()) {
      var redirect = encodeURIComponent('image.html?id=' + imageId);
      slot.innerHTML = '<div class="comment-form">' +
        '<p class="muted">登录后可评论</p>' +
        '<div class="comment-form__actions">' +
          '<a class="btn btn--primary" href="login.html?redirect=' + redirect + '">登录后评论</a>' +
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
      await API.postJSON('/api/images/' + encodeURIComponent(imageId) + '/comments', { content: content });
      if (textarea) textarea.value = '';
      UI.toast('评论已发表', 'success');
      commentState.page = 1;
      await loadComments();
    } catch (err) {
      if (err.status === 401) {
        UI.toast('请先登录后再评论', 'error');
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
      var data = await API.get('/api/images/' + encodeURIComponent(imageId) +
        '/comments?page=' + commentState.page + '&page_size=' + PAGE_SIZE);
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
    imageId = new URLSearchParams(window.location.search).get('id');
    var section = document.getElementById('comments');
    if (section) section.hidden = false;

    // 评论开关（GET /api/site），失败默认开启
    try {
      var site = await API.get('/api/site');
      if (site && site.comments_enabled === false) commentsEnabled = false;
    } catch (e) { /* 默认开启 */ }

    renderFormSlot();
    loadComments();
  }

  document.addEventListener('DOMContentLoaded', async function () {
    var wrap = document.getElementById('detail');
    await Layout.init('');

    var id = new URLSearchParams(window.location.search).get('id');
    if (!id) {
      wrap.innerHTML = UI.renderError('缺少图片 ID', '请从图库中选择一张图片进行查看。');
      return;
    }

    try {
      var image = await API.get('/api/images/' + encodeURIComponent(id));
      wrap.innerHTML = UI.renderImageDetail(image);
      document.title = UI.imageTitle(image) + ' - 图片详情';
    } catch (e) {
      wrap.innerHTML = UI.renderError('无法查看该图片', e.message);
      return;
    }

    await initComments();
  });
})();
