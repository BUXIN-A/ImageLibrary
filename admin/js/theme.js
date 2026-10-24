/**
 * 后台主题切换：使用后台自身静态 6 套主题，不再依赖站点设置。
 * localStorage 键：il_admin_theme
 * 切换主题只修改 <html data-theme="...">，样式由 themes/*.css 提供。
 *
 * 兜底策略：init() 永不 reject——任何异常都会回退到 6 套内置主题 + light。
 */
(function () {
  "use strict";

  var STORAGE_KEY = "il_admin_theme";
  var THEMES = [
    { id: "light", name: "明亮" },
    { id: "dark", name: "暗夜" },
    { id: "ocean", name: "海洋" },
    { id: "forest", name: "森林" },
    { id: "sunset", name: "日落" },
    { id: "sakura", name: "樱花" }
  ];

  var THEME_IDS = THEMES.map(function (t) { return t.id; });
  var DEFAULT_THEME = "light";

  var state = {
    available: THEMES.slice(),
    enabled: THEME_IDS.slice(),
    defaultTheme: DEFAULT_THEME,
    current: null,
    siteName: "我的图库"
  };

  /** 共享的站点设置请求：主题与布局各自初始化时只请求一次。 */
  var settingsPromise = null;

  function loadSettings() {
    if (settingsPromise) return settingsPromise;
    settingsPromise = (async function () {
      try {
        return await API.get("/api/settings");
      } catch (err) {
        return null;
      }
    })();
    return settingsPromise;
  }

  function isKnown(id) {
    return THEME_IDS.indexOf(id) !== -1;
  }

  /** 直接写入主题（不校验），用于 init 恢复本地记忆。 */
  function setTheme(id) {
    try {
      document.documentElement.setAttribute("data-theme", id);
    } catch (err) { /* documentElement 理论上始终存在，忽略极端情况 */ }
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch (err) { /* 忽略隐私模式下的存储异常 */ }
    state.current = id;
    try {
      document.dispatchEvent(new CustomEvent("themechange", { detail: { id: id } }));
    } catch (err) { /* 忽略事件派发异常 */ }
  }

  /** 应用主题并写入 localStorage；未知 id 回退到 light。 */
  function apply(id) {
    id = (id === null || id === undefined) ? "" : String(id);
    if (!isKnown(id)) id = DEFAULT_THEME;
    setTheme(id);
  }

  /**
   * 初始化：先应用本地记忆，再从 /api/settings 读取站点名（失败静默）。
   * 永不 reject。
   */
  async function init() {
    var stored = null;
    try {
      stored = localStorage.getItem(STORAGE_KEY);
    } catch (err) {
      stored = null;
    }

    try {
      apply(stored || DEFAULT_THEME);
    } catch (err) {
      /* 任何意外都不阻断页面：直接写入默认主题 */
      try { setTheme(DEFAULT_THEME); } catch (e) { /* ignore */ }
    }

    try {
      var settings = await loadSettings();
      if (settings && settings.site_name) {
        state.siteName = settings.site_name;
      }
    } catch (err) { /* 静默：站点名获取失败不影响主题 */ }

    return state;
  }

  /** 后台可用的静态主题列表。 */
  function enabledThemes() {
    return THEMES.slice();
  }

  window.Theme = {
    STORAGE_KEY: STORAGE_KEY,
    ALL: THEMES,
    init: init,
    apply: apply,
    enabledThemes: enabledThemes,
    loadSettings: loadSettings,
    getState: function () { return state; },
    getCurrent: function () { return state.current; },
    getThemes: function () { return enabledThemes(); }
  };
})();
