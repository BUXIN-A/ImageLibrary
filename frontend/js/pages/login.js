/* 登录页：账号密码登录/注册切换、第三方登录入口与 OAuth 回调处理。 */
(function () {
  'use strict';

  function getParams() {
    return new URLSearchParams(window.location.search);
  }

  /** 仅允许站内相对地址，防止开放重定向。 */
  function safeRedirect(target) {
    var t = String(target || '').trim();
    if (!t) return 'index.html';
    if (/^https?:\/\//i.test(t) || t.indexOf('//') === 0 || t.charAt(0) === '\\') return 'index.html';
    return t;
  }

  function redirectTarget() {
    return safeRedirect(getParams().get('redirect'));
  }

  /** 将 OAuth 错误码/信息转为可读中文。 */
  function readableError(raw) {
    if (!raw) return '登录失败，请重试';
    var map = {
      account_disabled: '账号已被禁用',
      state_failed: '登录状态校验失败，请重试'
    };
    if (map[raw]) return map[raw];
    try { return decodeURIComponent(raw); } catch (e) { return raw; }
  }

  function showMessage(text, type) {
    var box = document.getElementById('auth-message');
    if (!box) return;
    if (text) {
      box.textContent = text;
      box.className = 'alert alert--' + (type || 'error');
    } else {
      box.textContent = '';
      box.className = 'alert alert--error hidden';
    }
  }

  function currentLoggedIn() {
    return window.UserSession && window.UserSession.isLoggedIn();
  }

  /** 切换登录/注册标签。 */
  function switchTab(name) {
    var loginTab = document.getElementById('tab-login');
    var registerTab = document.getElementById('tab-register');
    var loginForm = document.getElementById('login-form');
    var registerForm = document.getElementById('register-form');
    if (!loginTab || !registerTab || !loginForm || !registerForm) return;
    var isLogin = name !== 'register';
    loginTab.classList.toggle('is-active', isLogin);
    loginTab.setAttribute('aria-selected', isLogin ? 'true' : 'false');
    registerTab.classList.toggle('is-active', !isLogin);
    registerTab.setAttribute('aria-selected', isLogin ? 'false' : 'true');
    loginForm.classList.toggle('hidden', !isLogin);
    registerForm.classList.toggle('hidden', isLogin);
    showMessage('');
  }

  /** 绑定登录表单提交。 */
  function bindLoginForm() {
    var form = document.getElementById('login-form');
    if (!form) return;
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      showMessage('');
      var username = (document.getElementById('login-username').value || '').trim();
      var password = document.getElementById('login-password').value || '';
      var btn = document.getElementById('login-submit');
      if (!username || !password) { showMessage('请输入用户名和密码'); return; }
      btn.disabled = true;
      btn.textContent = '登录中…';
      try {
        var data = await API.postJSON('/api/user/login', { username: username, password: password });
        if (data && data.access_token) UserSession.setToken(data.access_token);
        UI.toast('登录成功', 'success');
        window.location.replace(redirectTarget());
      } catch (err) {
        showMessage(err.message || '登录失败', 'error');
        btn.disabled = false;
        btn.textContent = '登录';
      }
    });
  }

  /** 绑定注册表单提交。 */
  function bindRegisterForm() {
    var form = document.getElementById('register-form');
    if (!form) return;
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      showMessage('');
      var username = (document.getElementById('register-username').value || '').trim();
      var password = document.getElementById('register-password').value || '';
      var email = (document.getElementById('register-email').value || '').trim();
      var btn = document.getElementById('register-submit');
      if (!username || !password) { showMessage('请输入用户名和密码'); return; }
      btn.disabled = true;
      btn.textContent = '注册中…';
      try {
        var payload = { username: username, password: password };
        if (email) payload.email = email;
        var data = await API.postJSON('/api/user/register', payload);
        if (data && data.access_token) UserSession.setToken(data.access_token);
        UI.toast('注册成功', 'success');
        window.location.replace(redirectTarget());
      } catch (err) {
        showMessage(err.message || '注册失败', 'error');
        btn.disabled = false;
        btn.textContent = '注册';
      }
    });
  }

  /** 渲染可见的第三方登录入口（local 由账号密码表单承载）。 */
  function renderProviders(providers) {
    var host = document.getElementById('providers');
    if (!host) return;
    var list = Array.isArray(providers) ? providers : [];
    var localEnabled = list.some(function (p) { return p.id === 'local' && p.enabled; });
    var thirdParty = list.filter(function (p) {
      return p.enabled && (p.id === 'github' || p.id === 'oauth2');
    });

    // 本地登录被关闭时，隐藏账号密码表单与标签
    var tabs = document.getElementById('auth-tabs');
    var loginForm = document.getElementById('login-form');
    var registerForm = document.getElementById('register-form');
    if (!localEnabled) {
      if (tabs) tabs.classList.add('hidden');
      if (loginForm) loginForm.classList.add('hidden');
      if (registerForm) registerForm.classList.add('hidden');
    }

    var html = '';
    if (localEnabled && thirdParty.length) {
      html += '<div class="auth-divider"><span>或</span></div>';
    }
    thirdParty.forEach(function (p) {
      var label = p.id === 'github' ? '使用 GitHub 登录' : '使用 OAuth2 登录';
      html += '<button class="btn btn--outline btn--block auth-provider" type="button" data-provider="' +
        UI.escapeHtml(p.id) + '">' + UI.escapeHtml(label) + '</button>';
    });

    if (!localEnabled && !thirdParty.length) {
      html = '<p class="muted text-center">暂无可用登录方式</p>';
    }

    host.innerHTML = html;
    host.querySelectorAll('[data-provider]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-provider');
        window.location.href = API.API_BASE + '/api/auth/' + encodeURIComponent(id) + '/authorize';
      });
    });
  }

  async function loadProviders() {
    try {
      var providers = await API.get('/api/auth/providers');
      renderProviders(providers);
    } catch (e) {
      renderProviders([]);
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    await Layout.init('');

    var params = getParams();

    // OAuth 回调：URL 带 token，写入令牌后跳转
    var oauthToken = params.get('token');
    if (oauthToken) {
      UserSession.setToken(oauthToken);
      UI.toast('登录成功', 'success');
      var target = redirectTarget();
      setTimeout(function () { window.location.replace(target); }, 400);
      return;
    }

    // OAuth 回调错误
    var err = params.get('error');
    if (err) showMessage(readableError(err), 'error');

    // 已登录直接跳转
    if (currentLoggedIn()) {
      window.location.replace(redirectTarget());
      return;
    }

    var loginTab = document.getElementById('tab-login');
    var registerTab = document.getElementById('tab-register');
    if (loginTab) loginTab.addEventListener('click', function () { switchTab('login'); });
    if (registerTab) registerTab.addEventListener('click', function () { switchTab('register'); });

    bindLoginForm();
    bindRegisterForm();
    await loadProviders();
  });
})();
