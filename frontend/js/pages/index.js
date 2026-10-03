/* 首页：图片网格浏览、排序、分页与批量导出。 */
(function () {
  'use strict';

  var PAGE_SIZE = 24;
  var state = { page: 1, sort: 'latest', pages: 0, total: 0, selected: new Set() };
  var grid, pagination, countEl, sortEl, exportBtn;

  function updateExportButton() {
    var count = state.selected.size;
    exportBtn.hidden = count === 0;
    exportBtn.textContent = '批量导出（' + count + '）';
    exportBtn.disabled = count === 0;
  }

  function bindCardSelect() {
    grid.querySelectorAll('.js-select').forEach(function (checkbox) {
      checkbox.addEventListener('change', function () {
        var id = parseInt(checkbox.value, 10);
        if (checkbox.checked) state.selected.add(id);
        else state.selected.delete(id);
        updateExportButton();
      });
    });
    // 阻止点击复选框区域时触发卡片跳转
    grid.querySelectorAll('.image-card__check').forEach(function (label) {
      label.addEventListener('click', function (e) { e.stopPropagation(); });
    });
  }

  async function load() {
    grid.innerHTML = UI.renderSkeleton(12);
    pagination.innerHTML = '';
    try {
      var data = await API.get('/api/images?page=' + state.page + '&page_size=' + PAGE_SIZE +
        '&sort=' + encodeURIComponent(state.sort));
      var items = data.items || [];
      state.pages = data.pages || 0;
      state.total = data.total || 0;
      countEl.textContent = state.total ? ('共 ' + state.total + ' 张图片') : '';

      if (!items.length) {
        grid.innerHTML = UI.renderEmpty('图库暂时没有图片');
      } else {
        grid.innerHTML = items.map(function (image) {
          return UI.renderImageCard(image, {
            selectable: true,
            checked: state.selected.has(image.id)
          });
        }).join('');
        bindCardSelect();
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

  async function doExport() {
    if (!state.selected.size) return;
    var ids = Array.from(state.selected);
    var originalText = exportBtn.textContent;
    exportBtn.disabled = true;
    exportBtn.textContent = '正在打包…';
    try {
      var response = await API.request('/api/images/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: ids })
      });
      await API.download(response, 'images_export.zip');
      UI.toast('导出完成', 'success');
    } catch (e) {
      UI.toast(e.message, 'error');
    } finally {
      exportBtn.textContent = originalText;
      updateExportButton();
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    grid = document.getElementById('grid');
    pagination = document.getElementById('pagination');
    countEl = document.getElementById('result-count');
    sortEl = document.getElementById('sort');
    exportBtn = document.getElementById('export-btn');

    await Layout.init('index');

    sortEl.addEventListener('change', function () {
      state.sort = sortEl.value;
      state.page = 1;
      load();
    });
    exportBtn.addEventListener('click', doExport);
    updateExportButton();
    load();
  });
})();
