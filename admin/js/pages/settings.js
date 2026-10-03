/**
 * 账号与安全：修改管理员密码。
 */
(function () {
  "use strict";

  var els = {};

  function cacheEls() {
    els.pwForm = document.getElementById("password-form");
    els.oldPw = document.getElementById("old-password");
    els.newPw = document.getElementById("new-password");
    els.confirmPw = document.getElementById("confirm-password");
    els.pwSubmit = document.getElementById("password-submit");
  }

  function bindPasswordForm() {
    els.pwForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      var oldPw = els.oldPw.value;
      var newPw = els.newPw.value;
      var confirmPw = els.confirmPw.value;
      if (!oldPw || !newPw) { UI.toast("请填写原密码与新密码", "warning"); return; }
      if (newPw.length < 6) { UI.toast("新密码长度至少 6 位", "warning"); return; }
      if (newPw !== confirmPw) { UI.toast("两次输入的新密码不一致", "warning"); return; }

      els.pwSubmit.disabled = true;
      try {
        await API.post("/api/auth/change-password", {
          old_password: oldPw,
          new_password: newPw
        });
        els.pwForm.reset();
        UI.toast("密码修改成功，请重新登录", "success");
        var yes = await UI.confirmDialog("密码已修改，建议立即重新登录。是否现在退出登录？", "退出登录");
        if (yes) Auth.logout();
      } catch (err) {
        UI.toast(err.message || "修改失败", "error");
      } finally {
        els.pwSubmit.disabled = false;
      }
    });
  }

  Layout.boot({
    active: "settings",
    onReady: function () {
      cacheEls();
      bindPasswordForm();
    }
  }).catch(function (err) {
    try { UI.toast((err && err.message) || "页面初始化失败", "error"); } catch (e) { /* ignore */ }
  });
})();
