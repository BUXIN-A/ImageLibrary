/**
 * 认证相关操作：登录、登出、鉴权守卫。
 */
(function () {
  "use strict";

  var TOKEN_KEY = "il_admin_token";
  var LOGIN_PAGE = "login.html";
  var DASHBOARD_PAGE = "dashboard.html";

  /** 读取本地 token。 */
  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  /**
   * 登录：成功后把 access_token 写入 localStorage。
   * @returns {Promise<object>} 登录响应
   */
  async function login(username, password) {
    var data = await API.post("/api/auth/login", {
      username: username,
      password: password
    });
    if (data && data.access_token) {
      localStorage.setItem(TOKEN_KEY, data.access_token);
    }
    return data;
  }

  /** 退出登录：清除 token 并回到登录页。 */
  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    location.href = LOGIN_PAGE;
  }

  /**
   * 页面鉴权守卫：无 token 跳登录页；有 token 但 /api/auth/me 失败也跳登录页。
   * @returns {Promise<object|null>} 当前管理员信息
   */
  async function requireAuth() {
    if (!getToken()) {
      location.href = LOGIN_PAGE;
      return null;
    }
    try {
      return await API.get("/api/auth/me");
    } catch (err) {
      // api.js 已在 401 时清除 token 并跳转登录页
      return null;
    }
  }

  /**
   * 登录页守卫：已登录则直接跳转仪表盘。
   * @returns {Promise<boolean>} 是否已跳转
   */
  async function redirectIfAuthed() {
    if (!getToken()) return false;
    try {
      await API.get("/api/auth/me");
      location.href = DASHBOARD_PAGE;
      return true;
    } catch (err) {
      return false;
    }
  }

  window.Auth = {
    TOKEN_KEY: TOKEN_KEY,
    getToken: getToken,
    login: login,
    logout: logout,
    requireAuth: requireAuth,
    redirectIfAuthed: redirectIfAuthed
  };
})();
