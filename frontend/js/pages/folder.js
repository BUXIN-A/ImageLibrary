/* 文件夹页：左侧文件夹树，右侧该文件夹图片（可含子文件夹）。 */
(function () {
  'use strict';

  var PAGE_SIZE = 24;
  var state = { folderId: '', includeSub: false, page: 1, pages: 0, total: 0, tree: [] };
  var treeEl, titleEl, subEl, grid, pagination, includeSubEl;

  function findFolder(nodes, id) {
    for (var i = 0; i < (nodes || []).length; i++) {
      if (String(nodes[i].id) === String(id)) return nodes[i];
      var found = findFolder(nodes[i].children, id);
      if (found) return found;
    }
    return null;
  }

  function treeHtml(nodes, currentId) {
    return '<ul>' + nodes.map(function (node) {
      var hasChildren = node.children && node.children.length;
      var isActive = String(node.id) === String(currentId);
      var html = '<li class="tree__item">';
      html += '<div class="tree__row' + (isActive ? ' is-active' : '') + '" data-id="' + node.id + '">';
      html += hasChildren
        ? '<button class="tree__toggle" type="button" data-toggle="1" aria-label="展开/收起"></button>'
        : '<span class="tree__toggle tree__toggle--empty"></span>';
      html += '<span class="tree__name">' + UI.escapeHtml(node.name) + '</span>';
      html += '<span class="tree__count">' + (node.image_count || 0) + '</span>';
      html += '</div>';
      if (hasChildren) {
        html += '<div class="tree__children">' + treeHtml(node.children, currentId) + '</div>';
      }
      html += '</li>';
      return html;
    }).join('') + '</ul>';
  }

  function renderTree() {
    var html = '<div class="tree__all">' +
      '<div class="tree__row' + (state.folderId === '' ? ' is-active' : '') + '" data-id="">' +
      '<span class="tree__toggle tree__toggle--empty"></span>' +
      '<span class="tree__name">未分类</span></div></div>';
    if (state.tree.length) {
      html += treeHtml(state.tree, state.folderId);
    } else {
      html += '<p class="muted" style="padding:6px 8px;">暂无文件夹</p>';
    }
    treeEl.innerHTML = html;
    expandToActive();
    bindTree();
  }

  function expandToActive() {
    var active = treeEl.querySelector('.tree__row.is-active');
    var node = active;
    while (node) {
      if (node.classList && node.classList.contains('tree__children')) {
        node.classList.add('is-open');
      }
      node = node.parentElement;
    }
  }

  function bindTree() {
    treeEl.querySelectorAll('.tree__toggle[data-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var row = btn.closest('.tree__row');
        var children = row.nextElementSibling;
        if (children) {
          var open = children.classList.toggle('is-open');
          row.classList.toggle('is-open', open);
        }
      });
    });
    treeEl.querySelectorAll('.tree__row').forEach(function (row) {
      row.addEventListener('click', function () {
        var id = row.getAttribute('data-id');
        if (id === state.folderId) return;
        state.folderId = id;
        state.page = 1;
        var url = window.location.pathname + (id ? ('?id=' + encodeURIComponent(id)) : '');
        window.history.replaceState(null, '', url);
        renderTree();
        renderHeading();
        loadImages();
      });
    });
  }

  function renderHeading() {
    if (!state.folderId) {
      titleEl.textContent = '未分类 / 全部图片';
      subEl.innerHTML = '';
      return;
    }
    var folder = findFolder(state.tree, state.folderId);
    titleEl.textContent = folder ? folder.name : '文件夹';
    if (folder && folder.children && folder.children.length) {
      subEl.innerHTML = folder.children.map(function (child) {
        return '<a class="subfolder-chip" href="folder.html?id=' + child.id + '">' +
          UI.escapeHtml(child.name) +
          '<span class="subfolder-chip__count">' + (child.image_count || 0) + '</span></a>';
      }).join('');
    } else {
      subEl.innerHTML = '';
    }
  }

  async function loadImages() {
    grid.innerHTML = UI.renderSkeleton(12);
    pagination.innerHTML = '';
    var params = ['page=' + state.page, 'page_size=' + PAGE_SIZE];
    if (state.folderId) params.push('folder_id=' + encodeURIComponent(state.folderId));
    if (state.includeSub) params.push('include_subfolders=1');

    try {
      var data = await API.get('/api/images?' + params.join('&'));
      var items = data.items || [];
      state.pages = data.pages || 0;
      state.total = data.total || 0;

      if (!items.length) {
        grid.innerHTML = UI.renderEmpty('该文件夹下暂时没有图片');
      } else {
        grid.innerHTML = items.map(function (image) {
          return UI.renderImageCard(image);
        }).join('');
      }

      UI.renderPagination(pagination, { page: state.page, pages: state.pages }, function (page) {
        state.page = page;
        loadImages();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    } catch (e) {
      grid.innerHTML = UI.renderEmpty('加载失败，请稍后重试');
      UI.toast(e.message, 'error');
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    treeEl = document.getElementById('folder-tree');
    titleEl = document.getElementById('folder-title');
    subEl = document.getElementById('subfolders');
    grid = document.getElementById('grid');
    pagination = document.getElementById('pagination');
    includeSubEl = document.getElementById('include-sub');

    await Layout.init('folder');

    var id = new URLSearchParams(window.location.search).get('id') || '';
    state.folderId = id;

    try {
      state.tree = await API.get('/api/folders');
    } catch (e) {
      state.tree = [];
      UI.toast(e.message, 'error');
    }

    renderTree();
    renderHeading();

    includeSubEl.addEventListener('change', function () {
      state.includeSub = includeSubEl.checked;
      state.page = 1;
      loadImages();
    });

    loadImages();
  });
})();
