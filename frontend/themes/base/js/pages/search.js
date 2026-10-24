/* 搜索页：关键词 + 标签 + 扁平分类筛选；加密分类需解锁后携带 folder_token。 */
(function () {
  'use strict';

  var PAGE_SIZE = 24;
  var state = {
    page: 1, q: '', tag: '', folderId: '', token: '', pages: 0, total: 0, folders: []
  };
  var grid, pagination, countEl, form, qInput, tagSelect, folderSelect, resetBtn;

  function findFolder(id) {
    for (var i = 0; i < state.folders.length; i++) {
      if (String(state.folders[i].id) === String(id)) return state.folders[i];
    }
    return null;
  }

  function readParams() {
    var params = new URLSearchParams(window.location.search);
    state.q = params.get('q') || '';
    state.tag = params.get('tag') || '';
    state.folderId = params.get('folder_id') || '';
    state.token = state.folderId ? (FolderAccess.get(state.folderId) || '') : '';
  }

  async function loadTags() {
    try {
      var tags = await API.get('/api/tags');
      (tags || []).forEach(function (tag) {
        var opt = document.createElement('option');
        opt.value = tag.name;
        opt.textContent = tag.name + '（' + (tag.image_count || 0) + '）';
        tagSelect.appendChild(opt);
      });
      tagSelect.value = state.tag;
    } catch (e) {
      /* 标签加载失败不阻断搜索 */
    }
  }

  async function loadFolders() {
    try {
      var folders = await API.get('/api/folders');
      state.folders = Array.isArray(folders) ? folders : [];
      state.folders.forEach(function (folder) {
        var opt = document.createElement('option');
        opt.value = folder.id;
        opt.textContent = (folder.has_password ? '🔒 ' : '') + folder.name +
          '（' + (typeof folder.image_count === 'number' ? folder.image_count : '—') + '）';
        folderSelect.appendChild(opt);
      });
      folderSelect.value = state.folderId;
    } catch (e) {
      /* 分类加载失败不阻断搜索 */
    }
  }

  function syncUrl() {
    var params = new URLSearchParams();
    if (state.q) params.set('q', state.q);
    if (state.tag) params.set('tag', state.tag);
    if (state.folderId !== '' && state.folderId !== null) params.set('folder_id', state.folderId);
    var qs = params.toString();
    var url = window.location.pathname + (qs ? '?' + qs : '');
    window.history.replaceState(null, '', url);
  }

  /** 选择加密分类时先解锁；cancelled 时清空选择。 */
  async function resolveFolderToken() {
    var id = folderSelect.value || '';
    state.folderId = id;
    state.token = '';
    if (!id) return true;
    var folder = findFolder(id);
    if (folder && folder.has_password) {
      var token = await FolderAccess.ensure(id);
      if (!token) {
        folderSelect.value = '';
        state.folderId = '';
        return false;
      }
      state.token = token;
    }
    return true;
  }

  async function applyFiltersFromForm() {
    state.q = (qInput.value || '').trim();
    state.tag = tagSelect.value || '';
    var ok = await resolveFolderToken();
    if (!ok) {
      state.page = 1;
      syncUrl();
      load();
      return;
    }
    state.page = 1;
    syncUrl();
    load();
  }

  function buildQuery() {
    var params = ['page=' + state.page, 'page_size=' + PAGE_SIZE];
    if (state.q) params.push('q=' + encodeURIComponent(state.q));
    if (state.tag) params.push('tag=' + encodeURIComponent(state.tag));
    if (state.folderId !== '' && state.folderId !== null) {
      params.push('folder_id=' + encodeURIComponent(state.folderId));
      if (state.token) params.push('folder_token=' + encodeURIComponent(state.token));
    }
    return params.join('&');
  }

  async function load() {
    grid.innerHTML = UI.renderSkeleton(12);
    pagination.innerHTML = '';

    try {
      var data = await API.get('/api/images?' + buildQuery());
      var items = data.items || [];
      state.pages = data.pages || 0;
      state.total = data.total || 0;

      var hasFilter = state.q || state.tag || state.folderId !== '';
      countEl.textContent = state.total
        ? ('共找到 ' + state.total + ' 项')
        : (hasFilter ? '没有找到匹配的内容' : '');

      if (!items.length) {
        grid.innerHTML = UI.renderEmpty(hasFilter ? '没有找到匹配的内容' : '图库暂时没有内容');
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
      // 令牌过期：清除后重新提示解锁并重试一次
      if (e.status === 403 && state.folderId) {
        var folderId = state.folderId;
        FolderAccess.clear(folderId);
        state.token = '';
        UI.toast('分类访问已过期，请重新解锁', 'warning');
        var token = await FolderAccess.ensure(folderId);
        if (token) {
          state.token = token;
          load();
          return;
        }
      }
      countEl.textContent = '';
      grid.innerHTML = UI.renderEmpty('加载失败，请稍后重试');
      UI.toast(e.message, 'error');
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    grid = document.getElementById('grid');
    pagination = document.getElementById('pagination');
    countEl = document.getElementById('result-count');
    form = document.getElementById('search-form');
    qInput = document.getElementById('q');
    tagSelect = document.getElementById('tag');
    folderSelect = document.getElementById('folder');
    resetBtn = document.getElementById('reset-btn');

    await Layout.init('search');
    readParams();
    qInput.value = state.q;

    await Promise.all([loadTags(), loadFolders()]);

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      applyFiltersFromForm();
    });

    tagSelect.addEventListener('change', applyFiltersFromForm);
    folderSelect.addEventListener('change', applyFiltersFromForm);

    resetBtn.addEventListener('click', function () {
      qInput.value = '';
      tagSelect.value = '';
      folderSelect.value = '';
      state.q = '';
      state.tag = '';
      state.folderId = '';
      state.token = '';
      state.page = 1;
      syncUrl();
      load();
    });

    load();
  });
})();
