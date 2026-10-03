/* 搜索页：关键词 + 标签 + 文件夹筛选，展示结果网格与分页。 */
(function () {
  'use strict';

  var PAGE_SIZE = 24;
  var state = { page: 1, q: '', tag: '', folderId: '', pages: 0, total: 0 };
  var grid, pagination, countEl, form, qInput, tagSelect, folderSelect, resetBtn;

  function readParams() {
    var params = new URLSearchParams(window.location.search);
    state.q = params.get('q') || '';
    state.tag = params.get('tag') || '';
    var folderId = params.get('folder_id');
    state.folderId = folderId || '';
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
      var tree = await API.get('/api/folders');
      var flat = UI.flattenFolders(tree);
      flat.forEach(function (folder) {
        var opt = document.createElement('option');
        opt.value = folder.id;
        opt.textContent = '　'.repeat(folder.depth) + folder.name +
          '（' + folder.image_count + '）';
        folderSelect.appendChild(opt);
      });
      folderSelect.value = state.folderId;
    } catch (e) {
      /* 文件夹加载失败不阻断搜索 */
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

  function applyFiltersFromForm() {
    state.q = (qInput.value || '').trim();
    state.tag = tagSelect.value || '';
    state.folderId = folderSelect.value || '';
    state.page = 1;
    syncUrl();
    load();
  }

  async function load() {
    grid.innerHTML = UI.renderSkeleton(12);
    pagination.innerHTML = '';
    var params = ['page=' + state.page, 'page_size=' + PAGE_SIZE];
    if (state.q) params.push('q=' + encodeURIComponent(state.q));
    if (state.tag) params.push('tag=' + encodeURIComponent(state.tag));
    if (state.folderId !== '' && state.folderId !== null) {
      params.push('folder_id=' + encodeURIComponent(state.folderId));
    }

    try {
      var data = await API.get('/api/images?' + params.join('&'));
      var items = data.items || [];
      state.pages = data.pages || 0;
      state.total = data.total || 0;

      var hasFilter = state.q || state.tag || state.folderId !== '';
      countEl.textContent = state.total
        ? ('共找到 ' + state.total + ' 张图片')
        : (hasFilter ? '没有找到匹配的图片' : '');

      if (!items.length) {
        grid.innerHTML = UI.renderEmpty(hasFilter ? '没有找到匹配的图片' : '图库暂时没有图片');
      } else {
        grid.innerHTML = items.map(function (image) {
          return UI.renderImageCard(image);
        }).join('');
      }

      UI.renderPagination(pagination, { page: state.page, pages: state.pages }, function (page) {
        state.page = page;
        load();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    } catch (e) {
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
      state.page = 1;
      syncUrl();
      load();
    });

    load();
  });
})();
