/* 加密分类解锁：令牌存取（sessionStorage）、密码弹窗与 URL 拼接辅助。
   window.FolderAccess。 */
(function () {
  'use strict';

  var PREFIX = 'il_folder_token_';
  var EXPIRY_MARGIN_MS = 5000;

  function storageKey(folderId) {
    return PREFIX + String(folderId);
  }

  function isValidId(folderId) {
    return folderId !== null && folderId !== undefined && folderId !== '';
  }

  /** 读取未过期的解锁令牌；无令牌或已过期返回 null。 */
  function get(folderId) {
    if (!isValidId(folderId)) return null;
    try {
      var raw = sessionStorage.getItem(storageKey(folderId));
      if (!raw) return null;
      var data = JSON.parse(raw);
      if (!data || !data.token) return null;
      var expiresAt = Number(data.expires_at) || 0;
      if (expiresAt && Date.now() >= expiresAt - EXPIRY_MARGIN_MS) {
        clear(folderId);
        return null;
      }
      return data.token;
    } catch (e) {
      return null;
    }
  }

  /** 存储解锁令牌；expiresIn 为后端返回的有效期（秒）。 */
  function set(folderId, token, expiresIn) {
    if (!isValidId(folderId) || !token) return;
    var ttl = Number(expiresIn);
    var expiresAt = (isFinite(ttl) && ttl > 0) ? Date.now() + ttl * 1000 : 0;
    try {
      sessionStorage.setItem(storageKey(folderId), JSON.stringify({
        token: token,
        expires_at: expiresAt
      }));
    } catch (e) { /* 隐私模式等异常忽略 */ }
  }

  function clear(folderId) {
    if (!isValidId(folderId)) return;
    try { sessionStorage.removeItem(storageKey(folderId)); } catch (e) { /* ignore */ }
  }

  /** 在 URL / 路径后追加 folder_token 查询参数（保留已有 query 与 hash）。 */
  function appendToken(url, token) {
    if (!url || !token) return url;
    var hash = '';
    var hashIndex = url.indexOf('#');
    if (hashIndex !== -1) {
      hash = url.slice(hashIndex);
      url = url.slice(0, hashIndex);
    }
    var sep = url.indexOf('?') === -1 ? '?' : '&';
    return url + sep + 'folder_token=' + encodeURIComponent(token) + hash;
  }

  /** 同 appendToken，语义化别名：为接口路径带上分类令牌。 */
  function withToken(path, token) {
    return appendToken(path, token);
  }

  /** 密码弹窗：成功后存储并返回 token；取消返回 null。 */
  function promptUnlock(folderId) {
    return new Promise(function (resolve) {
      if (!window.UI || !UI.openModal) { resolve(null); return; }

      var overlay = UI.openModal(
        '<form class="modal__body folder-unlock" novalidate>' +
        '<h3 class="modal__title">该分类已加密</h3>' +
        '<p class="modal__text">请输入分类访问密码后查看内容。</p>' +
        '<label class="field folder-unlock__field">' +
        '<span class="field__label">访问密码</span>' +
        '<input class="input js-folder-password" type="password" autocomplete="off" required>' +
        '</label>' +
        '<div class="alert alert--error hidden js-folder-error" role="alert"></div>' +
        '</form>' +
        '<div class="modal__footer">' +
        '<button class="btn btn--ghost" type="button" data-act="cancel">取消</button>' +
        '<button class="btn btn--primary" type="button" data-act="ok">解锁</button>' +
        '</div>'
      );
      if (!overlay) { resolve(null); return; }

      var form = overlay.querySelector('form');
      var input = overlay.querySelector('.js-folder-password');
      var errorEl = overlay.querySelector('.js-folder-error');
      var okBtn = overlay.querySelector('[data-act="ok"]');
      var finished = false;

      function finish(token) {
        if (finished) return;
        finished = true;
        document.removeEventListener('keydown', onKeydown, true);
        resolve(token);
      }

      function cancel() {
        if (finished) return;
        UI.closeModal();
        finish(null);
      }

      function showError(text) {
        if (!errorEl) return;
        errorEl.textContent = text || '解锁失败，请重试';
        errorEl.classList.remove('hidden');
      }

      function onKeydown(e) {
        if (e.key === 'Escape') cancel();
      }

      document.addEventListener('keydown', onKeydown, true);
      overlay.addEventListener('click', function (e) {
        if (e.target === overlay) cancel();
      });
      overlay.querySelector('[data-act="cancel"]').addEventListener('click', cancel);

      function submit() {
        var password = input.value || '';
        if (!password) {
          showError('请输入访问密码');
          input.focus();
          return;
        }
        if (errorEl) errorEl.classList.add('hidden');
        okBtn.disabled = true;
        okBtn.textContent = '解锁中…';
        API.postJSON('/api/folders/' + encodeURIComponent(folderId) + '/unlock', { password: password })
          .then(function (data) {
            if (!data || !data.token) throw new Error('解锁失败，请重试');
            set(folderId, data.token, data.expires_in);
            UI.closeModal();
            UI.toast('分类已解锁', 'success');
            finish(data.token);
          })
          .catch(function (err) {
            var message = (err && err.message) || '解锁失败，请重试';
            if (err && err.status === 401) message = '密码错误，请重试';
            showError(message);
            okBtn.disabled = false;
            okBtn.textContent = '解锁';
            input.focus();
            input.select();
          });
      }

      okBtn.addEventListener('click', submit);
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        submit();
      });
      setTimeout(function () { input.focus(); }, 30);
    });
  }

  /**
   * 确保拥有某分类的解锁令牌：已有有效令牌直接返回；否则弹出密码框。
   * @returns {Promise<string|null>} 令牌或 null（用户取消）
   */
  function ensure(folderId) {
    if (!isValidId(folderId)) return Promise.resolve(null);
    var token = get(folderId);
    if (token) return Promise.resolve(token);
    return promptUnlock(folderId);
  }

  window.FolderAccess = {
    get: get,
    set: set,
    clear: clear,
    ensure: ensure,
    appendToken: appendToken,
    withToken: withToken
  };
})();
