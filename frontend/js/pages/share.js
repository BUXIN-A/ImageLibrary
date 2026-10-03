/* 分享页：根据 ?token= 加载分享图片详情。 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', async function () {
    var wrap = document.getElementById('detail');
    await Layout.init('');

    var token = new URLSearchParams(window.location.search).get('token');
    if (!token) {
      wrap.innerHTML = UI.renderError('分享链接无效', '缺少分享 token，请确认链接是否完整。');
      return;
    }

    try {
      var image = await API.get('/api/share/' + encodeURIComponent(token));
      wrap.innerHTML = UI.renderImageDetail(image);
      document.title = UI.imageTitle(image) + ' - 分享';
    } catch (e) {
      wrap.innerHTML = UI.renderError('分享不存在或已失效', e.message);
    }
  });
})();
