/* API 封装：统一拼接基址、解析错误 detail、下载处理。 */
(function () {
  'use strict';

  var cfg = window.APP_CONFIG || {};
  var API_BASE = String(cfg.API_BASE || '').replace(/\/+$/, '');

  /**
   * 拼接 API 绝对地址；已是绝对地址则原样返回。
   */
  function apiUrl(path) {
    if (!path) return API_BASE;
    if (/^https?:\/\//i.test(path) || path.indexOf('data:') === 0) return path;
    return API_BASE + (path.charAt(0) === '/' ? path : '/' + path);
  }

  /**
   * 拼接图片等静态资源地址（接口返回的是 /media、/thumbnails 相对路径）。
   */
  function mediaUrl(rel) {
    if (!rel) return '';
    return apiUrl(rel);
  }

  /** 读取前台用户令牌（localStorage: il_user_token）。 */
  function getUserToken() {
    try { return localStorage.getItem('il_user_token'); } catch (e) { return null; }
  }

  /**
   * 为请求附加用户令牌：存在 il_user_token 时自动带上 Authorization。
   * 若调用方已显式设置 Authorization，则不覆盖（公开接口忽略该头，无副作用）。
   */
  function withAuth(options) {
    var opts = options || {};
    var token = getUserToken();
    if (!token) return opts;
    var headers = opts.headers;
    if (headers) {
      if (typeof headers.has === 'function') {
        if (headers.has('Authorization')) return opts;
      } else if (headers['Authorization'] || headers['authorization']) {
        return opts;
      }
    }
    var merged = {};
    if (headers) {
      if (typeof headers.forEach === 'function') {
        headers.forEach(function (value, key) { merged[key] = value; });
      } else {
        Object.keys(headers).forEach(function (key) { merged[key] = headers[key]; });
      }
    }
    merged['Authorization'] = 'Bearer ' + token;
    opts.headers = merged;
    return opts;
  }

  /** 从响应中提取错误信息并构造 Error。 */
  async function parseError(res) {
    var message = '请求失败（' + res.status + '）';
    try {
      var data = await res.json();
      if (data && typeof data.detail === 'string' && data.detail) {
        message = data.detail;
      } else if (data && data.detail && typeof data.detail === 'object') {
        message = data.detail.message || JSON.stringify(data.detail);
      } else if (data && typeof data.message === 'string' && data.message) {
        message = data.message;
      }
    } catch (e) {
      /* 响应体不是 JSON，保留默认信息 */
    }
    var err = new Error(message);
    err.status = res.status;
    return err;
  }

  /** 基础请求：处理网络错误与非 2xx 状态。 */
  async function request(path, options) {
    var res;
    try {
      res = await fetch(apiUrl(path), withAuth(options));
    } catch (e) {
      var netErr = new Error('无法连接服务器，请确认后端服务已启动');
      netErr.status = 0;
      throw netErr;
    }
    if (!res.ok) {
      throw await parseError(res);
    }
    return res;
  }

  /** GET 请求，返回 JSON。 */
  async function get(path) {
    var res = await request(path, { method: 'GET' });
    return res.json();
  }

  /** POST JSON 请求，返回 JSON。 */
  async function postJSON(path, body) {
    var res = await request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    });
    return res.json();
  }

  /** POST 表单（FormData），返回 JSON。 */
  async function postForm(path, formData) {
    var res = await request(path, { method: 'POST', body: formData });
    return res.json();
  }

  /**
   * 带进度的表单上传（FormData）。
   * fetch 无法获取上传进度，故使用 XMLHttpRequest。
   * @param {string} path 接口路径
   * @param {FormData} formData 表单数据
   * @param {(loaded:number,total:number)=>void} [onProgress] 上传进度回调（字节）
   * @returns {Promise<object|null>} 解析后的 JSON 响应
   */
  function postFormWithProgress(path, formData, onProgress) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', apiUrl(path), true);
      var token = getUserToken();
      if (token) xhr.setRequestHeader('Authorization', 'Bearer ' + token);

      if (xhr.upload && typeof onProgress === 'function') {
        xhr.upload.onprogress = function (e) {
          if (e.lengthComputable) onProgress(e.loaded, e.total);
        };
      }

      xhr.onload = function () {
        var data = null;
        try {
          data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
        } catch (e) {
          data = null;
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data);
          return;
        }
        var message = (data && typeof data.detail === 'string' && data.detail) ||
          ('请求失败（' + xhr.status + '）');
        var err = new Error(message);
        err.status = xhr.status;
        err.data = data;
        reject(err);
      };
      xhr.onerror = function () {
        var netErr = new Error('无法连接服务器，请确认后端服务已启动');
        netErr.status = 0;
        reject(netErr);
      };
      xhr.send(formData);
    });
  }

  /**
   * 下载：
   * - 传入字符串路径：直接跳转下载（适用于下载原图等 GET 接口）。
   * - 传入 Response：读取 blob 并触发浏览器下载（适用于批量导出 ZIP）。
   */
  async function download(pathOrResponse, filename) {
    if (typeof pathOrResponse === 'string') {
      var a1 = document.createElement('a');
      a1.href = apiUrl(pathOrResponse);
      if (filename) a1.download = filename;
      a1.rel = 'noopener';
      document.body.appendChild(a1);
      a1.click();
      a1.remove();
      return;
    }
    var response = pathOrResponse;
    var blob = await response.blob();
    var objectUrl = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = objectUrl;
    a.download = filename || 'download';
    document.body.appendChild(a);
    a.click();
    a.remove();
    // 稍后释放，确保下载已开始
    setTimeout(function () { URL.revokeObjectURL(objectUrl); }, 1000);
  }

  window.API = {
    API_BASE: API_BASE,
    apiUrl: apiUrl,
    mediaUrl: mediaUrl,
    request: request,
    get: get,
    postJSON: postJSON,
    postForm: postForm,
    postFormWithProgress: postFormWithProgress,
    download: download
  };
})();
