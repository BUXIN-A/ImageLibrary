/* 导航页预取：鼠标悬停/键盘聚焦链接时按需预取，避免额外空闲请求拖慢首屏。 */
(function () {
  'use strict';

  var PAGES = ['index.html', 'folder.html', 'search.html', 'upload.html'];
  var added = {};

  /** 判断 URL 对应哪个导航页（按路径后缀）。 */
  function pageOf(url) {
    if (!url) return null;
    for (var i = 0; i < PAGES.length; i++) {
      if (url.pathname.slice(-PAGES[i].length) === PAGES[i]) return PAGES[i];
    }
    return null;
  }

  function toUrl(href) {
    try {
      return new URL(href, window.location.href);
    } catch (e) {
      return null;
    }
  }

  function alreadyLinked(page) {
    var links = document.querySelectorAll('link[rel="prefetch"]');
    for (var i = 0; i < links.length; i++) {
      var url = toUrl(links[i].getAttribute('href'));
      if (url && pageOf(url) === page) return true;
    }
    return false;
  }

  /** 预取指定页面（同源、非当前页、未预取过）。 */
  function prefetch(url) {
    if (!url || url.origin !== window.location.origin) return;
    var page = pageOf(url);
    if (!page) return;
    if (url.pathname === window.location.pathname) return;
    if (added[page] || alreadyLinked(page)) return;
    added[page] = true;
    var link = document.createElement('link');
    link.rel = 'prefetch';
    link.as = 'document';
    link.href = page;
    document.head.appendChild(link);
  }

  function anchorFrom(target) {
    var node = target;
    while (node && node !== document) {
      if (node.tagName === 'A' && node.getAttribute('href')) return node;
      node = node.parentElement;
    }
    return null;
  }

  // 事件委托：页头导航由 layout 异步渲染，委托可覆盖后插入的链接
  document.addEventListener('mouseover', function (e) {
    var anchor = anchorFrom(e.target);
    if (!anchor) return;
    prefetch(toUrl(anchor.getAttribute('href')));
  }, { passive: true });

  document.addEventListener('focusin', function (e) {
    var anchor = anchorFrom(e.target);
    if (!anchor) return;
    prefetch(toUrl(anchor.getAttribute('href')));
  });
})();
