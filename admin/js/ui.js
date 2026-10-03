/**
 * 通用 UI 工具：提示、格式化、空状态、分页、弹窗、徽章、复制、文件夹展平。
 */
(function () {
  "use strict";

  var STATUS_TEXT = {
    approved: "已通过",
    pending: "待审核",
    rejected: "已拒绝"
  };

  /** HTML 转义，防止 XSS。 */
  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** 把后端返回的字节数格式化为可读大小。 */
  function formatSize(bytes) {
    var n = Number(bytes);
    if (!isFinite(n) || n < 0) return "-";
    if (n < 1024) return n + " B";
    var units = ["KB", "MB", "GB", "TB"];
    var i = -1;
    do {
      n /= 1024;
      i += 1;
    } while (n >= 1024 && i < units.length - 1);
    return n.toFixed(n >= 100 ? 0 : 1) + " " + units[i];
  }

  /** 把 ISO 时间格式化为本地可读字符串。 */
  function formatDate(iso) {
    if (!iso) return "-";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    function pad(v) { return v < 10 ? "0" + v : String(v); }
    return (
      d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      " " + pad(d.getHours()) + ":" + pad(d.getMinutes())
    );
  }

  /** 返回媒体（原图/缩略图）完整地址。 */
  function mediaUrl(path) {
    if (!path) return "";
    if (/^https?:\/\//i.test(path)) return path;
    return (window.API && API.base ? API.base : "") + path;
  }

  /** 轻提示。type: info | success | error | warning */
  function toast(message, type) {
    try {
      if (!message) return;
      var host = document.body || document.documentElement;
      if (!host) return;
      var root = document.getElementById("toast-root");
      if (!root) {
        root = document.createElement("div");
        root.id = "toast-root";
        host.appendChild(root);
      }
      var el = document.createElement("div");
      el.className = "toast toast-" + (type || "info");
      el.textContent = message;
      root.appendChild(el);
      setTimeout(function () {
        el.classList.add("toast-hide");
        setTimeout(function () {
          if (el.parentNode) el.parentNode.removeChild(el);
        }, 260);
      }, 2800);
    } catch (err) { /* 提示失败不应影响业务逻辑 */ }
  }

  /** 渲染空状态 HTML 字符串。 */
  function renderEmpty(text) {
    return '<div class="empty-state">' +
      '<svg viewBox="0 0 24 24" width="44" height="44" fill="none" stroke="currentColor" stroke-width="1.5">' +
      '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 15l4-4 3 3 4-5 5 6"/></svg>' +
      '<p>' + escapeHtml(text || "暂无数据") + "</p></div>";
  }

  /** 状态徽章 HTML。 */
  function statusBadge(status) {
    var map = {
      approved: "badge-approved",
      pending: "badge-pending",
      rejected: "badge-rejected"
    };
    var cls = map[status] || "badge-muted";
    return '<span class="badge ' + cls + '">' + escapeHtml(STATUS_TEXT[status] || status || "-") + "</span>";
  }

  /**
   * 渲染分页控件。
   * @param {HTMLElement} container
   * @param {{page:number,pages:number}} info
   * @param {(page:number)=>void} onChange
   */
  function renderPagination(container, info, onChange) {
    if (!container) return;
    info = info || {};
    var page = info.page || 1;
    var pages = info.pages || 0;
    container.innerHTML = "";
    if (pages <= 1) return;
    onChange = (typeof onChange === "function") ? onChange : function () {};

    var wrap = document.createElement("div");
    wrap.className = "pagination";

    function makeBtn(text, targetPage, opts) {
      opts = opts || {};
      var b = document.createElement("button");
      b.type = "button";
      b.className = "page-btn" + (opts.active ? " active" : "") + (opts.disabled ? " disabled" : "");
      b.textContent = text;
      if (opts.disabled) {
        b.disabled = true;
      } else {
        b.addEventListener("click", function () { onChange(targetPage); });
      }
      return b;
    }

    wrap.appendChild(makeBtn("上一页", page - 1, { disabled: page <= 1 }));

    // 页码窗口：最多显示 7 个
    var start = Math.max(1, page - 3);
    var end = Math.min(pages, start + 6);
    start = Math.max(1, end - 6);
    if (start > 1) {
      wrap.appendChild(makeBtn("1", 1, { active: page === 1 }));
      if (start > 2) wrap.appendChild(makeSpan("…"));
    }
    for (var p = start; p <= end; p += 1) {
      wrap.appendChild(makeBtn(String(p), p, { active: p === page }));
    }
    if (end < pages) {
      if (end < pages - 1) wrap.appendChild(makeSpan("…"));
      wrap.appendChild(makeBtn(String(pages), pages, { active: page === pages }));
    }

    wrap.appendChild(makeBtn("下一页", page + 1, { disabled: page >= pages }));
    container.appendChild(wrap);

    function makeSpan(text) {
      var s = document.createElement("span");
      s.className = "page-ellipsis";
      s.textContent = text;
      return s;
    }
  }

  /** 关闭当前弹窗。 */
  function closeModal() {
    var mask = document.getElementById("ui-modal-mask");
    if (mask && mask.parentNode) mask.parentNode.removeChild(mask);
    document.body.classList.remove("modal-open");
  }

  /**
   * 打开弹窗。
   * @param {string} title 标题
   * @param {string} bodyHtml 内容 HTML
   * @param {(modal:HTMLElement)=>any} [onConfirm] 确认回调；返回 false 或 Promise<false> 时不关闭
   */
  function openModal(title, bodyHtml, onConfirm) {
    closeModal();
    if (!document.body) return null;
    var mask = document.createElement("div");
    mask.id = "ui-modal-mask";
    mask.className = "modal-mask";
    mask.innerHTML =
      '<div class="modal" role="dialog" aria-modal="true">' +
        '<div class="modal-header">' +
          '<h3 class="modal-title">' + escapeHtml(title) + "</h3>" +
          '<button type="button" class="modal-close" aria-label="关闭">&times;</button>' +
        "</div>" +
        '<div class="modal-body">' + bodyHtml + "</div>" +
        '<div class="modal-footer">' +
          '<button type="button" class="btn btn-ghost" data-act="cancel">取消</button>' +
          '<button type="button" class="btn btn-primary" data-act="confirm">确定</button>' +
        "</div>" +
      "</div>";
    document.body.appendChild(mask);
    document.body.classList.add("modal-open");

    var confirmBtn = mask.querySelector('[data-act="confirm"]');
    var cancelBtn = mask.querySelector('[data-act="cancel"]');
    var closeBtn = mask.querySelector(".modal-close");

    function cancel() { closeModal(); }
    cancelBtn.addEventListener("click", cancel);
    closeBtn.addEventListener("click", cancel);
    mask.addEventListener("mousedown", function (e) {
      if (e.target === mask) cancel();
    });

    confirmBtn.addEventListener("click", async function () {
      if (typeof onConfirm !== "function") { closeModal(); return; }
      confirmBtn.disabled = true;
      try {
        var result = await onConfirm(mask);
        if (result !== false) closeModal();
      } finally {
        confirmBtn.disabled = false;
      }
    });

    return mask;
  }

  /** 确认对话框，返回 Promise<boolean>。 */
  function confirmDialog(message, confirmText) {
    return new Promise(function (resolve) {
      openModal(
        "确认操作",
        '<p class="confirm-text">' + escapeHtml(message) + "</p>",
        function () {
          resolve(true);
          return true;
        }
      );
      var mask = document.getElementById("ui-modal-mask");
      if (mask && confirmText) {
        var btn = mask.querySelector('[data-act="confirm"]');
        if (btn) {
          btn.textContent = confirmText;
          btn.classList.remove("btn-primary");
          btn.classList.add("btn-danger");
        }
      }
      if (mask) {
        var cancel = mask.querySelector('[data-act="cancel"]');
        cancel.addEventListener("click", function () { resolve(false); });
        mask.querySelector(".modal-close").addEventListener("click", function () { resolve(false); });
        mask.addEventListener("mousedown", function (e) {
          if (e.target === mask) resolve(false);
        });
      }
    });
  }

  /** 复制文本到剪贴板，返回 Promise<boolean>。 */
  async function copyToClipboard(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (err) {
      /* 回退到 execCommand */
    }
    try {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      var ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (err) {
      return false;
    }
  }

  /**
   * 把文件夹树展平为带缩进的列表，供下拉框使用。
   * @returns {Array<{id:number,name:string,depth:number,label:string}>}
   */
  function flattenFolders(tree) {
    var result = [];
    function walk(nodes, depth) {
      (nodes || []).forEach(function (node) {
        result.push({
          id: node.id,
          name: node.name,
          depth: depth,
          label: new Array(depth + 1).join("　") + node.name,
          image_count: node.image_count || 0
        });
        if (node.children && node.children.length) {
          walk(node.children, depth + 1);
        }
      });
    }
    walk(tree, 0);
    return result;
  }

  /** 填充文件夹下拉框。 */
  function fillFolderSelect(select, folders, opts) {
    opts = opts || {};
    var current = select.value;
    select.innerHTML = "";
    var allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = opts.allLabel || "全部文件夹";
    select.appendChild(allOption);
    folders.forEach(function (f) {
      var opt = document.createElement("option");
      opt.value = String(f.id);
      opt.textContent = f.label;
      select.appendChild(opt);
    });
    if (current) select.value = current;
  }

  window.UI = {
    escapeHtml: escapeHtml,
    formatSize: formatSize,
    formatDate: formatDate,
    mediaUrl: mediaUrl,
    toast: toast,
    renderEmpty: renderEmpty,
    statusBadge: statusBadge,
    renderPagination: renderPagination,
    confirmDialog: confirmDialog,
    openModal: openModal,
    closeModal: closeModal,
    copyToClipboard: copyToClipboard,
    flattenFolders: flattenFolders,
    fillFolderSelect: fillFolderSelect
  };
})();
