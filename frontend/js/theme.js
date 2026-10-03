/* 主题管理：读取站点启用主题、记忆用户选择并即时应用。
   兜底策略：init() 永不 reject；apply() 对未知 id 容错。 */
(function () {
  'use strict';

  var STORAGE_KEY = 'il_theme';
  var DYNAMIC_LINK_ID = 'theme-custom-dynamic';
  var ALL_THEMES = [
    { id: 'light', name: '明亮', source: 'builtin' },
    { id: 'dark', name: '暗夜', source: 'builtin' },
    { id: 'ocean', name: '海洋', source: 'builtin' },
    { id: 'forest', name: '森林', source: 'builtin' },
    { id: 'sunset', name: '日落', source: 'builtin' },
    { id: 'sakura', name: '樱花', source: 'builtin' }
  ];

  var themes = ALL_THEMES.slice();
  var current = 'light';
  var settings = null;
  var initialized = false;

  function getStored() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }

  function setStored(id) {
    try { localStorage.setItem(STORAGE_KEY, id); } catch (e) { /* 忽略隐私模式等异常 */ }
  }

  function hasTheme(list, id) {
    return list.some(function (t) { return t.id === id; });
  }

  /** 查询主题来源（builtin | custom），未知按 builtin 处理。 */
  function themeSource(id) {
    for (var i = 0; i < themes.length; i++) {
      if (themes[i].id === id) return themes[i].source || 'builtin';
    }
    return 'builtin';
  }

  /**
   * 应用自定义主题样式表：custom 主题确保存在 <link id="theme-custom-dynamic">
   * 指向 ${API_BASE}/api/themes/{id}/css；切回内置主题时移除该 link。
   */
  function applyDynamicTheme(id) {
    var head = document.head || document.documentElement;
    if (!head) return;
    var link = document.getElementById(DYNAMIC_LINK_ID);
    if (themeSource(id) === 'custom') {
      var href = window.API.apiUrl('/api/themes/' + encodeURIComponent(id) + '/css');
      if (link) {
        if (link.getAttribute('href') !== href) link.setAttribute('href', href);
      } else {
        link = document.createElement('link');
        link.id = DYNAMIC_LINK_ID;
        link.rel = 'stylesheet';
        link.href = href;
        head.appendChild(link);
      }
    } else if (link) {
      link.remove();
    }
  }

  /** 应用主题：改写 html[data-theme]、同步选择器、写入 localStorage；未知 id 回退。 */
  function apply(id) {
    id = (id === null || id === undefined) ? '' : String(id);
    if (!hasTheme(themes, id)) {
      id = themes.length ? themes[0].id : 'light';
    }
    current = id;
    try { applyDynamicTheme(id); } catch (e) { /* ignore */ }
    try { document.documentElement.setAttribute('data-theme', id); } catch (e) { /* ignore */ }
    setStored(id);
    document.querySelectorAll('.js-theme-select').forEach(function (sel) {
      sel.value = id;
    });
  }

  /** 初始化：读取 /api/settings，决定启用主题与默认主题；失败时回退全部主题 + light。永不 reject。 */
  async function init() {
    if (initialized) return settings;
    initialized = true;

    try {
      settings = await window.API.get('/api/settings');
    } catch (e) {
      settings = null;
    }

    try {
      if (settings && Array.isArray(settings.themes) && settings.themes.length) {
        var enabled = (Array.isArray(settings.enabled_themes) && settings.enabled_themes.length)
          ? settings.enabled_themes
          : settings.themes.map(function (t) { return t.id; });
        var list = settings.themes.filter(function (t) { return enabled.indexOf(t.id) !== -1; });
        if (list.length) themes = list;
      } else {
        themes = ALL_THEMES.slice();
      }

      var stored = getStored();
      var defaultId = (settings && settings.default_theme) || 'light';
      var pick;
      if (stored && hasTheme(themes, stored)) pick = stored;
      else if (hasTheme(themes, defaultId)) pick = defaultId;
      else pick = themes.length ? themes[0].id : 'light';

      apply(pick);
    } catch (e) {
      themes = ALL_THEMES.slice();
      apply('light');
    }
    return settings;
  }

  window.Theme = {
    init: init,
    apply: apply,
    getCurrent: function () { return current; },
    getThemes: function () { return themes.slice(); },
    enabledThemes: function () { return themes.slice(); },
    getState: function () { return { current: current, themes: themes.slice() }; }
  };
})();
