/* 导航主题首页：统计面板、分类入口与全部图片网格。
   统计与分类数据来自 /api/theme/nav-stats 与 /api/folders/summary，
   二者失败时仅显示空状态/提示，不阻断 /api/images 图片列表。 */
(function () {
  'use strict';

  var PAGE_SIZE = 24;
  var state = { page: 1, pages: 0, total: 0 };

  var statsSection, statsGrid, folderGrid, folderSummary, grid, pagination, countEl;

  /** 读取导航统计开关（缺省视为开启）。 */
  function navStatsConfig() {
    var theme = (window.APP_CONFIG && window.APP_CONFIG.THEME) || {};
    var nav = theme.nav || {};
    var stats = nav.stats;
    return stats && typeof stats === 'object' ? stats : {};
  }

  function isEnabled(config, key) {
    return config[key] !== false;
  }

  function toCount(value) {
    var n = Number(value);
    return isFinite(n) && n > 0 ? Math.floor(n) : 0;
  }

  /* ---------- 统计面板 ---------- */
  function renderStats(stats) {
    var config = navStatsConfig();
    var cards = [
      { key: 'total_images', label: '总图片数', value: stats.total_images },
      { key: 'total_views', label: '总浏览数', value: stats.total_views },
      { key: 'total_comments', label: '总评论数', value: stats.total_comments },
      { key: 'total_downloads', label: '总下载数', value: stats.total_downloads }
    ].filter(function (card) {
      return isEnabled(config, card.key);
    });

    if (!cards.length) {
      statsSection.hidden = true;
      statsGrid.innerHTML = '';
      return;
    }

    statsSection.hidden = false;
    statsGrid.innerHTML = cards.map(function (card) {
      return '<div class="nav-stat" data-stat="' + card.key + '">' +
        '<span class="nav-stat__label">' + card.label + '</span>' +
        '<span class="nav-stat__value">' + toCount(card.value) + '</span></div>';
    }).join('');
  }

  /* ---------- 分类入口 ---------- */
  function renderFolderCard(card, showCounts) {
    var html = '<a class="nav-folder' + (card.modifier ? ' ' + card.modifier : '') +
      '" href="' + UI.escapeHtml(card.href) + '">';
    html += '<span class="nav-folder__head">' +
      '<span class="nav-folder__name">' + UI.escapeHtml(card.name) + '</span>';
    if (card.locked) {
      html += '<span class="nav-folder__lock" title="该分类已加密" aria-label="已加密">' +
        UI.lockIcon(13) + '</span>';
    }
    html += '</span>';
    if (showCounts && typeof card.count === 'number') {
      html += '<span class="nav-folder__meta">' +
        '<span class="nav-folder__count">' + toCount(card.count) + ' 张</span></span>';
    }
    html += '</a>';
    return html;
  }

  function renderFolderSummary(stats, summary) {
    if (!folderSummary) return;
    var folderCount = (stats && typeof stats.folder_count === 'number')
      ? stats.folder_count
      : (summary && typeof summary.folder_count === 'number' ? summary.folder_count : null);
    var parts = [];
    if (folderCount !== null) parts.push('共 ' + toCount(folderCount) + ' 个分类');
    var lockedCount = summary ? toCount(summary.locked_count) : 0;
    if (lockedCount > 0) parts.push(lockedCount + ' 个已加密');
    folderSummary.textContent = parts.length ? parts.join(' · ') : '分类信息暂时不可用';
  }

  function renderFolders(stats, summary) {
    var showCounts = isEnabled(navStatsConfig(), 'folder_images');
    var folders = (stats && Array.isArray(stats.folders)) ? stats.folders : [];

    var cards = [
      {
        href: 'folder.html',
        name: '全部',
        modifier: 'nav-folder--all',
        count: summary && typeof summary.all_count === 'number' ? summary.all_count : null
      },
      {
        href: 'folder.html?view=uncategorized',
        name: '未分类',
        modifier: 'nav-folder--uncategorized',
        count: summary && typeof summary.uncategorized_count === 'number'
          ? summary.uncategorized_count
          : null
      }
    ];

    folders.forEach(function (folder) {
      cards.push({
        href: 'folder.html?id=' + encodeURIComponent(folder.id),
        name: folder.name || ('分类 #' + folder.id),
        locked: !!folder.has_password,
        count: typeof folder.image_count === 'number' ? folder.image_count : 0
      });
    });

    var html = cards.map(function (card) {
      return renderFolderCard(card, showCounts);
    }).join('');
    if (!stats) {
      html += '<p class="nav-folders__note">分类列表暂时不可用</p>';
    } else if (!folders.length) {
      html += '<p class="nav-folders__note">还没有创建分类</p>';
    }
    folderGrid.innerHTML = html;
    renderFolderSummary(stats, summary);
  }

  async function loadOverview() {
    var results = await Promise.allSettled([
      API.get('/api/theme/nav-stats'),
      API.get('/api/folders/summary')
    ]);
    var stats = results[0].status === 'fulfilled' ? results[0].value : null;
    var summary = results[1].status === 'fulfilled' ? results[1].value : null;

    if (stats) {
      renderStats(stats);
    } else {
      statsSection.hidden = false;
      statsGrid.innerHTML = UI.renderEmpty('统计信息暂时不可用');
    }

    renderFolders(stats, summary);

    if (!stats) UI.toast('导航统计加载失败', 'warning');
    else if (!summary) UI.toast('分类汇总加载失败', 'warning');
  }

  /* ---------- 全部图片 ---------- */
  async function loadImages() {
    grid.innerHTML = UI.renderSkeleton(12);
    pagination.innerHTML = '';
    countEl.textContent = '';

    try {
      var data = await API.get('/api/images?page=' + state.page + '&page_size=' + PAGE_SIZE);
      var items = data.items || [];
      state.pages = data.pages || 0;
      state.total = data.total || 0;
      countEl.textContent = state.total ? ('共 ' + state.total + ' 项') : '';

      if (!items.length) {
        grid.innerHTML = UI.renderEmpty('图库暂时没有内容');
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
      countEl.textContent = '';
      grid.innerHTML = UI.renderEmpty('加载失败，请稍后重试');
      UI.toast(e.message, 'error');
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    statsSection = document.getElementById('stats-section');
    statsGrid = document.getElementById('stats-grid');
    folderGrid = document.getElementById('folder-grid');
    folderSummary = document.getElementById('folder-summary');
    grid = document.getElementById('grid');
    pagination = document.getElementById('pagination');
    countEl = document.getElementById('result-count');

    await Layout.init('index');

    var siteNameEl = document.getElementById('nav-site-name');
    var siteName = (window.Layout && Layout.getSiteName) ? Layout.getSiteName() : '';
    if (siteNameEl && siteName) siteNameEl.textContent = siteName;

    loadOverview();
    loadImages();
  });
})();
