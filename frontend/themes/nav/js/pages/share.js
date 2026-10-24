/* 分享页：根据 ?token= 加载分享详情；加密分类 403 时解锁后重试并带令牌渲染。 */
(function () {
  'use strict';

  var state = { shareToken: '', folderId: '', folderToken: '', retried: false };

  function sharePath() {
    var path = '/api/share/' + encodeURIComponent(state.shareToken);
    if (state.folderToken) path = FolderAccess.withToken(path, state.folderToken);
    return path;
  }

  async function load(wrap) {
    try {
      var image = await API.get(sharePath());
      wrap.innerHTML = UI.renderImageDetail(image, { folderToken: state.folderToken });
      document.title = UI.imageTitle(image) + ' - 分享';
    } catch (e) {
      var lockedId = e.folder_id || (e.detail && typeof e.detail === 'object' ? e.detail.folder_id : null);
      if (e.status === 403 && lockedId && !state.retried) {
        state.retried = true;
        state.folderId = String(lockedId);
        FolderAccess.clear(lockedId);
        UI.toast('该分享所属分类已加密，请先解锁', 'warning');
        var token = await FolderAccess.ensure(lockedId);
        if (token) {
          state.folderToken = token;
          return load(wrap);
        }
        wrap.innerHTML = UI.renderError('分享内容已加密', '需要输入分类访问密码后才能查看该分享。');
        return;
      }
      wrap.innerHTML = UI.renderError('分享不存在或已失效', e.message);
    }
  }

  document.addEventListener('DOMContentLoaded', async function () {
    var wrap = document.getElementById('detail');
    await Layout.init('');

    var token = new URLSearchParams(window.location.search).get('token');
    if (!token) {
      wrap.innerHTML = UI.renderError('分享链接无效', '缺少分享 token，请确认链接是否完整。');
      return;
    }

    state.shareToken = token;
    await load(wrap);
  });
})();
