/* 前台用户会话：令牌存取与当前用户信息查询。 */
(function () {
  'use strict';

  var TOKEN_KEY = 'il_user_token';

  /** 读取本地用户令牌。 */
  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
  }

  /** 写入用户令牌（传空则清除）。 */
  function setToken(token) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch (e) { /* 隐私模式等异常忽略 */ }
  }

  /** 清除用户令牌。 */
  function clear() {
    try { localStorage.removeItem(TOKEN_KEY); } catch (e) { /* ignore */ }
  }

  /** 是否已登录（仅本地令牌存在性判断）。 */
  function isLoggedIn() {
    return !!getToken();
  }

  /**
   * 获取当前用户信息：调用 GET /api/user/me。
   * 无令牌返回 null；401 时自动清除令牌并返回 null；其它错误同样返回 null。
   */
  async function me() {
    if (!getToken()) return null;
    try {
      return await window.API.get('/api/user/me');
    } catch (e) {
      if (e && e.status === 401) clear();
      return null;
    }
  }

  window.UserSession = {
    TOKEN_KEY: TOKEN_KEY,
    getToken: getToken,
    setToken: setToken,
    clear: clear,
    isLoggedIn: isLoggedIn,
    me: me
  };
})();
