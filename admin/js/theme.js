/**
 * 主题管理：读取站点可用主题，应用/记忆当前主题。
 * localStorage 键：il_admin_theme
 * 切换主题只修改 <html data-theme="...">，样式由 themes/*.css 提供。
 *
 * 兜底策略：init() 永不 reject——任何异常都会回退到 6 套内置主题 + light。
 */
(function () {
  "use strict";

  var STORAGE_KEY = "il_admin_theme";
  var FALLBACK_THEMES = [
    { id: "light", name: "明亮" },
    { id: "dark", name: "暗夜" },
    { id: "ocean", name: "海洋" },
    { id: "forest", name: "森林" },
    { id: "sunset", name: "日落" },
    { id: "sakura", name: "樱花" }
  ];

  var state = {
    available: FALLBACK_THEMES.slice(),
    enabled: FALLBACK_THEMES.map(function (t) { return t.id; }),
    defaultTheme: "light",
    current: null,
    siteName: "我的图库"
  };

  function resetToFallback() {
    state.available = FALLBACK_THEMES.slice();
    state.enabled = FALLBACK_THEMES.map(function (t) { return t.id; });
    state.defaultTheme = "light";
  }

  function knownIds() {
    var map = {};
    FALLBACK_THEMES.forEach(function (t) { map[t.id] = true; });
    (state.available || []).forEach(function (t) { if (t && t.id) map[t.id] = true; });
    (state.enabled || []).forEach(function (id) { if (id) map[id] = true; });
    return map;
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

  /**
   * 应用主题并写入 localStorage。
   * 对未知 id 容错：回退到默认主题（再兜底 light），不抛错。
   */
  function apply(id) {
    id = (id === null || id === undefined) ? "" : String(id);
    if (!id) id = state.defaultTheme || "light";
    var known = knownIds();
    if (!known[id]) id = state.defaultTheme || "light";
    if (!known[id]) id = "light";
    setTheme(id);
  }

  /**
   * 初始化：先应用本地记忆，再拉取站点设置修正可用集合与默认值。
   * 接口失败时回退全部 6 套主题 + light。永不 reject。
   */
  async function init() {
    try {
      var stored = null;
      try {
        stored = localStorage.getItem(STORAGE_KEY);
      } catch (err) {
        stored = null;
      }
      if (stored) setTheme(stored);

      try {
        var settings = await API.get("/api/settings");
        if (settings) {
          state.siteName = settings.site_name || state.siteName;
          var themes = Array.isArray(settings.themes) && settings.themes.length
            ? settings.themes
            : FALLBACK_THEMES;
          state.available = themes;
          state.enabled = Array.isArray(settings.enabled_themes) && settings.enabled_themes.length
            ? settings.enabled_themes
            : themes.map(function (t) { return t.id; });
          state.defaultTheme = settings.default_theme || "light";
        } else {
          resetToFallback();
        }
      } catch (err) {
        resetToFallback();
      }

      if (!stored) apply(state.defaultTheme);
    } catch (err) {
      /* 任何意外都不阻断页面：回退内置主题 */
      resetToFallback();
      try { setTheme(state.defaultTheme || "light"); } catch (e) { /* ignore */ }
    }
    return state;
  }

  /** 取当前启用主题的 {id,name} 列表（保持内置顺序，附加未知项）。 */
  function enabledThemes() {
    var byId = {};
    (state.available || []).forEach(function (t) { if (t && t.id) byId[t.id] = t; });
    FALLBACK_THEMES.forEach(function (t) { if (!byId[t.id]) byId[t.id] = t; });
    var list = (state.enabled || []).map(function (id) {
      return byId[id] || { id: id, name: id };
    });
    return list.length ? list : FALLBACK_THEMES.slice();
  }

  window.Theme = {
    STORAGE_KEY: STORAGE_KEY,
    ALL: FALLBACK_THEMES,
    init: init,
    apply: apply,
    enabledThemes: enabledThemes,
    getState: function () { return state; },
    getCurrent: function () { return state.current; },
    getThemes: function () { return enabledThemes(); }
  };
})();
