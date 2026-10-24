/* 预设管理（沿用 window.Theme 名称以兼容 layout）：
   预设列表来自 window.APP_CONFIG.THEME，主题 id 取 html[data-theme-id]，
   用户选择记忆在 localStorage 的 il_preset_<themeId>。init() 同步且永不抛错。 */
(function () {
  'use strict';

  var THEME = (window.APP_CONFIG && window.APP_CONFIG.THEME) || {};
  var FALLBACK_PRESET = { id: 'light', name: '明亮' };
  var VERSION = '2.0.1';
  var initialized = false;

  /** 当前主题 id：优先 html[data-theme-id]，其次服务端注入的 active_theme。 */
  function themeId() {
    var root = document.documentElement;
    var id = root && root.getAttribute('data-theme-id');
    if (id) return id;
    return THEME.active_theme || 'base';
  }

  /** 可用预设列表：{id,name}[]，缺失时回退明亮。 */
  function presetList() {
    var presets = THEME.presets;
    var list = presets && presets[themeId()];
    if (!Array.isArray(list) || !list.length) return [FALLBACK_PRESET];
    return list.map(function (item) {
      return { id: item.id, name: item.name || item.id };
    });
  }

  function defaultPreset() {
    var list = presetList();
    var wanted = THEME.default_preset;
    for (var i = 0; i < list.length; i++) {
      if (list[i].id === wanted) return wanted;
    }
    return list[0].id;
  }

  function storageKey() {
    return 'il_preset_' + themeId();
  }

  function getStored() {
    try { return localStorage.getItem(storageKey()); } catch (e) { return null; }
  }

  function setStored(id) {
    try { localStorage.setItem(storageKey(), id); } catch (e) { /* 忽略隐私模式等异常 */ }
  }

  function hasPreset(list, id) {
    return list.some(function (t) { return t.id === id; });
  }

  /** 预设 CSS 路径（由后端 /presets/{id}.css 提供）。 */
  function presetHref(id) {
    return '/presets/' + encodeURIComponent(id) + '.css?v=' + VERSION;
  }

  /** 同步 <link id="preset-style"> 的 href；缺失时补建。 */
  function applyPresetLink(id) {
    var head = document.head || document.documentElement;
    if (!head) return;
    var link = document.getElementById('preset-style');
    if (!link) {
      link = document.createElement('link');
      link.id = 'preset-style';
      link.rel = 'stylesheet';
      head.appendChild(link);
    }
    var href = presetHref(id);
    if (link.getAttribute('href') !== href) link.setAttribute('href', href);
  }

  /** 应用预设：写 html[data-preset]、改写预设 CSS、记忆并派发 themechange。 */
  function apply(id) {
    var list = presetList();
    id = (id === null || id === undefined) ? '' : String(id);
    if (!hasPreset(list, id)) id = defaultPreset();

    try { document.documentElement.setAttribute('data-preset', id); } catch (e) { /* ignore */ }
    try { applyPresetLink(id); } catch (e) { /* ignore */ }
    setStored(id);
    document.querySelectorAll('.js-theme-select').forEach(function (sel) {
      sel.value = id;
    });
    try {
      document.dispatchEvent(new CustomEvent('themechange', {
        detail: { theme: themeId(), preset: id }
      }));
    } catch (e) { /* 旧浏览器不支持 CustomEvent 构造时忽略 */ }
  }

  /** 初始化：同步应用本地记忆（或默认预设），永不 reject。 */
  function init() {
    if (initialized) return getState();
    initialized = true;
    var list = presetList();
    var stored = getStored();
    var pick;
    if (stored && hasPreset(list, stored)) pick = stored;
    else pick = defaultPreset();
    apply(pick);
    return getState();
  }

  function getCurrent() {
    var root = document.documentElement;
    var current = root && root.getAttribute('data-preset');
    return current || defaultPreset();
  }

  function getThemes() {
    return presetList();
  }

  function getState() {
    return { current: getCurrent(), themes: presetList(), theme: themeId() };
  }

  window.Theme = {
    init: init,
    apply: apply,
    getCurrent: getCurrent,
    getThemes: getThemes,
    enabledThemes: getThemes,
    getState: getState
  };

  // 尽早同步一次，保证选择器与 data-preset 一致（幂等）
  try { init(); } catch (e) { /* ignore */ }
})();
