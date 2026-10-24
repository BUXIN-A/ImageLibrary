/* 分类页：一级分类（全部 / 未分类 / 分类列表），加密分类密码解锁与令牌复用。 */
(function () {
  'use strict';

  var PAGE_SIZE = 24;
  var state = {
    view: 'all',        // all | uncategorized | folder
    folderId: '',
    token: '',
    page: 1,
    pages: 0,
    total: 0,
    folders: [],
    summary: null
  };

  var listEl, titleEl, hintEl, grid, pagination, countEl;
  var allLink, uncatLink, countAll, countUncat;

  function findFolder(id) {
    for (var i = 0; i < state.folders.length; i++) {
      if (String(state.folders[i].id) === String(id)) return state.folders[i];
    }
    return null;
  }

  function readParams() {
    var params = new URLSearchParams(window.location.search);
    var view = params.get('view');
    var id = params.get('id');
    if (view === 'uncategorized') {
      state.view = 'uncategorized';
      state.folderId = '';
    } else if (id) {
      state.view = 'folder';
      state.folderId = String(id);
    } else {
      state.view = 'all';
      state.folderId = '';
    }
    state.token = state.view === 'folder' ? (FolderAccess.get(state.folderId) || '') : '';
  }

  function syncUrl() {
    var url = window.location.pathname;
    if (state.view === 'uncategorized') url += '?view=uncategorized';
    else if (state.view === 'folder') url += '?id=' + encodeURIComponent(state.folderId);
    window.history.replaceState(null, '', url);
  }

  function renderNav() {
    if (allLink) allLink.classList.toggle('is-active', state.view === 'all');
    if (uncatLink) uncatLink.classList.toggle('is-active', state.view === 'uncategorized');

    var summary = state.summary || {};
    if (countAll) countAll.textContent = summary.all_count !== undefined ? summary.all_count : '';
    if (countUncat) countUncat.textContent = summary.uncategorized_count !== undefined
      ? summary.uncategorized_count : '';

    if (!state.folders.length) {
      listEl.innerHTML = '<p class="muted folder-nav__empty">暂无分类</p>';
      return;
    }
    listEl.innerHTML = state.folders.map(function (folder) {
      var active = state.view === 'folder' && String(folder.id) === String(state.folderId);
      var lock = folder.has_password
        ? '<span class="folder-nav__lock" title="该分类已加密">' + UI.lockIcon(12) + '</span>'
        : '';
      return '<a class="folder-nav__item' + (active ? ' is-active' : '') +
        '" href="folder.html?id=' + encodeURIComponent(folder.id) + '" data-id="' + folder.id + '">' +
        '<span class="folder-nav__name">' + lock + UI.escapeHtml(folder.name) + '</span>' +
        '<span class="folder-nav__meta"><span class="folder-nav__count">' +
        (folder.image_count || 0) + '</span></span></a>';
    }).join('');
    bindFolderItems();
  }

  function bindFolderItems() {
    listEl.querySelectorAll('.folder-nav__item[data-id]').forEach(function (item) {
      item.addEventListener('click', function (e) {
        e.preventDefault();
        selectFolder(item.getAttribute('data-id'));
      });
    });
  }

  function renderHeading() {
    var html;
    var hint = '';
    if (state.view === 'all') {
      html = '全部';
      hint = '浏览全部分开内容（不含未解锁的加密分类）';
    } else if (state.view === 'uncategorized') {
      html = '未分类';
      hint = '未归入任何分类的内容';
    } else {
      var folder = findFolder(state.folderId);
      var name = folder ? folder.name : ('分类 #' + state.folderId);
      var lock = (folder && folder.has_password)
        ? '<span class="folder-title__lock" title="该分类已加密">' + UI.lockIcon(14) + '</span>'
        : '';
      html = lock + UI.escapeHtml(name);
      hint = (folder && folder.has_password)
        ? (state.token ? '已解锁，可查看该分类内容' : '该分类需要密码才能查看')
        : '';
    }
    titleEl.innerHTML = html;
    hintEl.textContent = hint;
  }

  async function selectFolder(id) {
    if (state.view === 'folder' && String(state.folderId) === String(id)) return;
    var folder = findFolder(id);
    var token = '';
    if (folder && folder.has_password) {
      token = await FolderAccess.ensure(id);
      if (!token) return; // 用户取消解锁
    }
    state.view = 'folder';
    state.folderId = String(id);
    state.token = token;
    state.page = 1;
    syncUrl();
    renderNav();
    renderHeading();
    load();
  }

  function selectView(view) {
    if (state.view === view) return;
    state.view = view;
    state.folderId = '';
    state.token = '';
    state.page = 1;
    syncUrl();
    renderNav();
    renderHeading();
    load();
  }

  function buildQuery() {
    var params = ['page=' + state.page, 'page_size=' + PAGE_SIZE];
    if (state.view === 'folder') {
      params.push('folder_id=' + encodeURIComponent(state.folderId));
      if (state.token) params.push('folder_token=' + encodeURIComponent(state.token));
    } else if (state.view === 'uncategorized') {
      params.push('uncategorized=1');
    }
    return params.join('&');
  }

  async function load() {
    grid.innerHTML = UI.renderSkeleton(12);
    pagination.innerHTML = '';
    countEl.textContent = '';

    try {
      var data = await API.get('/api/images?' + buildQuery());
      var items = data.items || [];
      state.pages = data.pages || 0;
      state.total = data.total || 0;
      countEl.textContent = state.total ? ('共 ' + state.total + ' 项') : '';

      if (!items.length) {
        grid.innerHTML = UI.renderEmpty('该分类下暂时没有内容');
      } else {
        grid.innerHTML = items.map(function (image) {
          return UI.renderImageCard(image, { folderToken: state.token });
        }).join('');
      }

      UI.renderPagination(pagination, { page: state.page, pages: state.pages }, function (page) {
        state.page = page;
        load();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    } catch (e) {
      // 令牌过期 / 分类密码变更：清除令牌后重新提示解锁
      if (e.status === 403 && state.view === 'folder' && state.folderId) {
        var folderId = state.folderId;
        FolderAccess.clear(folderId);
        state.token = '';
        UI.toast('分类访问已过期，请重新解锁', 'warning');
        var token = await FolderAccess.ensure(folderId);
        if (token) {
          state.token = token;
          renderHeading();
          load();
          return;
        }
        grid.innerHTML = UI.renderEmpty('该分类需要密码才能查看');
        return;
      }
      grid.innerHTML = UI.renderEmpty('加载失败，请稍后重试');
      UI.toast(e.message, 'error');
    }
  }

  async function loadFolders() {
    try {
      var folders = await API.get('/api/folders');
      state.folders = Array.isArray(folders) ? folders : [];
    } catch (e) {
      state.folders = [];
      UI.toast('分类加载失败', 'error');
    }
  }

  async function loadSummary() {
    try {
      state.summary = await API.get('/api/folders/summary');
    } catch (e) {
      state.summary = null;
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    listEl = document.getElementById('folder-list');
    titleEl = document.getElementById('folder-title');
    hintEl = document.getElementById('folder-hint');
    grid = document.getElementById('grid');
    pagination = document.getElementById('pagination');
    countEl = document.getElementById('result-count');
    allLink = document.getElementById('nav-all');
    uncatLink = document.getElementById('nav-uncategorized');
    countAll = document.getElementById('count-all');
    countUncat = document.getElementById('count-uncategorized');

    await Layout.init('folder');

    readParams();
    await Promise.all([loadFolders(), loadSummary()]);
    renderNav();
    renderHeading();

    // 直接访问加密分类且无有效令牌时，先弹窗解锁
    var blocked = false;
    if (state.view === 'folder' && state.folderId && !state.token) {
      var folder = findFolder(state.folderId);
      if (folder && folder.has_password) {
        var token = await FolderAccess.ensure(state.folderId);
        if (token) state.token = token;
        else blocked = true;
      }
    }

    if (allLink) {
      allLink.addEventListener('click', function (e) {
        e.preventDefault();
        selectView('all');
      });
    }
    if (uncatLink) {
      uncatLink.addEventListener('click', function (e) {
        e.preventDefault();
        selectView('uncategorized');
      });
    }

    renderNav();
    renderHeading();

    if (blocked) {
      countEl.textContent = '';
      grid.innerHTML = UI.renderEmpty('该分类需要密码才能查看');
      return;
    }
    load();
  });
})();
