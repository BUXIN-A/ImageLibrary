/**
 * API 请求封装。
 * - 自动为每个请求附加 Authorization: Bearer <token>
 * - 收到 401 时清除本地 token 并跳转登录页
 * - 错误信息统一取响应 JSON 的 detail 字段
 */
(function () {
  "use strict";

  var cfg = window.APP_CONFIG || {};
  var API_BASE = cfg.API_BASE || "";
  var TOKEN_KEY = "il_admin_token";
  var LOGIN_PAGE = "login.html";

  /** 读取本地保存的登录 token。 */
  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  /** 拼接完整请求地址（绝对地址直接返回）。 */
  function buildUrl(path) {
    if (/^https?:\/\//i.test(path)) return path;
    return API_BASE + path;
  }

  /** 401 处理：清除登录态并跳转登录页。 */
  function onUnauthorized() {
    localStorage.removeItem(TOKEN_KEY);
    var current = (location.pathname.split("/").pop() || "").toLowerCase();
    if (current !== LOGIN_PAGE) {
      location.href = LOGIN_PAGE;
    }
  }

  /** 从错误响应中提取可读的中文提示。 */
  function extractDetail(data, status) {
    if (data && typeof data === "object") {
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.detail) && data.detail.length) {
        return data.detail
          .map(function (item) {
            return item && item.msg ? item.msg : JSON.stringify(item);
          })
          .join("；");
      }
    }
    return "请求失败（HTTP " + status + "）";
  }

  /** 解析响应体：JSON 返回对象，其余返回 null。 */
  async function parseBody(res) {
    var ct = res.headers.get("content-type") || "";
    if (ct.indexOf("application/json") !== -1) {
      try {
        return await res.json();
      } catch (err) {
        return null;
      }
    }
    return null;
  }

  /**
   * 通用请求方法。
   * @param {string} path 接口路径
   * @param {object} [options] { method, body, form, headers }
   */
  async function request(path, options) {
    options = options || {};
    var headers = Object.assign({}, options.headers || {});
    var token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;

    var fetchOptions = { method: options.method || "GET", headers: headers };

    if (options.body !== undefined && options.body !== null) {
      if (options.form) {
        // FormData：交由浏览器自动设置 multipart 边界
        fetchOptions.body = options.body;
      } else {
        headers["Content-Type"] = "application/json";
        fetchOptions.body = JSON.stringify(options.body);
      }
    }

    var res;
    try {
      res = await fetch(buildUrl(path), fetchOptions);
    } catch (err) {
      var netErr = new Error("网络请求失败，请确认后端服务已启动");
      netErr.network = true;
      throw netErr;
    }

    if (res.status === 401) {
      var body401 = await parseBody(res);
      onUnauthorized();
      var authErr = new Error(extractDetail(body401, 401));
      authErr.status = 401;
      throw authErr;
    }

    if (!res.ok) {
      var body = await parseBody(res);
      var err = new Error(extractDetail(body, res.status));
      err.status = res.status;
      err.data = body;
      throw err;
    }

    return parseBody(res);
  }

  /** POST 表单（multipart）上传。 */
  function postForm(path, formData) {
    return request(path, { method: "POST", body: formData, form: true });
  }

  /**
   * 下载类接口：POST 后把响应当作文件保存。
   * @param {string} path 接口路径
   * @param {object} body 请求体
   * @param {string} [fallbackName] 无法从响应头取文件名时的默认名
   */
  async function download(path, body, fallbackName) {
    var headers = { "Content-Type": "application/json" };
    var token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;

    var res;
    try {
      res = await fetch(buildUrl(path), {
        method: "POST",
        headers: headers,
        body: JSON.stringify(body || {})
      });
    } catch (err) {
      throw new Error("网络请求失败，请确认后端服务已启动");
    }

    if (res.status === 401) {
      onUnauthorized();
      throw new Error("登录已过期，请重新登录");
    }
    if (!res.ok) {
      var data = await parseBody(res);
      throw new Error(extractDetail(data, res.status));
    }

    var name = fallbackName || "export.zip";
    var cd = res.headers.get("content-disposition");
    if (cd) {
      var match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
      if (match && match[1]) {
        try {
          name = decodeURIComponent(match[1]);
        } catch (err) {
          name = match[1];
        }
      }
    }

    var blob = await res.blob();
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1500);
  }

  window.API = {
    base: API_BASE,
    getToken: getToken,
    request: request,
    get: function (path) {
      return request(path, { method: "GET" });
    },
    post: function (path, body) {
      return request(path, { method: "POST", body: body });
    },
    put: function (path, body) {
      return request(path, { method: "PUT", body: body });
    },
    patch: function (path, body) {
      return request(path, { method: "PATCH", body: body });
    },
    del: function (path) {
      return request(path, { method: "DELETE" });
    },
    postForm: postForm,
    download: download
  };
})();
