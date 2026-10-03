# -*- coding: utf-8 -*-
"""OAuth 服务：授权 URL 构建、code 换取令牌、拉取并映射用户资料与 state 管理。

使用标准库 urllib.request 发起 HTTP 请求（同步），所有异常统一转为 ValueError（中文）。
"""
import json
import secrets
import threading
import time
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.seed import get_setting
from backend.app.site_config import effective_api_base

# GitHub 固定端点
_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"
_GITHUB_EMAILS_URL = "https://api.github.com/user/emails"
_GITHUB_SCOPE = "read:user user:email"

# state 有效期（秒）与内存存储
_STATE_TTL = 300
_state_store: dict[str, float] = {}
_state_lock = threading.Lock()


def _cfg(key: str, default: str = "") -> str:
    """从设置表读取配置项（缺失时返回 default）。"""
    db = SessionLocal()
    try:
        value = get_setting(db, key)
    finally:
        db.close()
    return default if value is None else value


def callback_url(provider: str, db=None) -> str:
    """返回指定 provider 的回调地址（优先使用后台配置的 API 站点地址）。"""
    if db is None:
        session = SessionLocal()
        try:
            base = effective_api_base(session)
        finally:
            session.close()
    else:
        base = effective_api_base(db)
    return f"{base}/api/auth/{provider}/callback"


# ---------------- state 管理 ----------------
def generate_state() -> str:
    """生成随机 state 并登记（5 分钟有效）。"""
    state = secrets.token_urlsafe(24)
    now_ts = time.monotonic()
    with _state_lock:
        # 顺带清理过期项
        expired = [key for key, ts in _state_store.items() if now_ts - ts > _STATE_TTL]
        for key in expired:
            _state_store.pop(key, None)
        _state_store[state] = now_ts
    return state


def verify_state(state: str) -> bool:
    """校验并消费 state；无效或过期返回 False。"""
    if not state:
        return False
    now_ts = time.monotonic()
    with _state_lock:
        ts = _state_store.pop(state, None)
    return ts is not None and (now_ts - ts) <= _STATE_TTL


# ---------------- HTTP 辅助 ----------------
def _http_post_form(url: str, data: dict, headers: Optional[dict] = None) -> dict:
    """以表单方式 POST 并把响应解析为 dict（JSON 优先，回退查询串）。"""
    body = urlencode(data).encode("utf-8")
    merged = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    if headers:
        merged.update(headers)
    request = Request(url, data=body, method="POST", headers=merged)
    try:
        with urlopen(request, timeout=10) as response:
            text = response.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - 统一转换为中文错误
        raise ValueError(f"请求失败：{exc}")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass
    # 兼容 application/x-www-form-urlencoded 响应
    from urllib.parse import parse_qs

    return {key: values[0] for key, values in parse_qs(text).items()}


def _http_get_json(url: str, headers: dict) -> object:
    """GET 请求并解析 JSON 响应。"""
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            text = response.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"请求失败：{exc}")
    try:
        return json.loads(text)
    except ValueError:
        raise ValueError("服务返回内容无法解析")


# ---------------- 对外能力 ----------------
def build_authorize_url(provider: str, state: str, db=None) -> str:
    """构建第三方授权跳转 URL。"""
    redirect_uri = callback_url(provider, db)
    if provider == "github":
        client_id = _cfg("github_client_id")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": _GITHUB_SCOPE,
            "state": state,
        }
        return f"{_GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    params = {
        "response_type": "code",
        "client_id": _cfg("oauth2_client_id"),
        "redirect_uri": redirect_uri,
        "scope": _cfg("oauth2_scope", "openid profile email"),
        "state": state,
    }
    authorize_url = _cfg("oauth2_authorize_url")
    if not authorize_url:
        raise ValueError("未配置 OAuth2 授权地址")
    separator = "&" if "?" in authorize_url else "?"
    return f"{authorize_url}{separator}{urlencode(params)}"


def exchange_code(provider: str, code: str) -> dict:
    """使用授权 code 换取访问令牌，返回令牌响应 dict。"""
    redirect_uri = callback_url(provider)
    if provider == "github":
        data = {
            "client_id": _cfg("github_client_id"),
            "client_secret": _cfg("github_client_secret"),
            "code": code,
            "redirect_uri": redirect_uri,
        }
        return _http_post_form(_GITHUB_TOKEN_URL, data)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": _cfg("oauth2_client_id"),
        "client_secret": _cfg("oauth2_client_secret"),
    }
    token_url = _cfg("oauth2_token_url")
    if not token_url:
        raise ValueError("未配置 OAuth2 令牌地址")
    return _http_post_form(token_url, data)


def fetch_profile(provider: str, access_token: str) -> dict:
    """使用访问令牌拉取用户资料。"""
    if not access_token:
        raise ValueError("未获取到访问令牌")

    if provider == "github":
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ImageLibrary",
        }
        profile = _http_get_json(_GITHUB_USER_URL, headers)
        if not isinstance(profile, dict):
            raise ValueError("获取用户资料失败")
        if not profile.get("email"):
            emails = _http_get_json(_GITHUB_EMAILS_URL, headers)
            if isinstance(emails, list):
                for item in emails:
                    if item.get("primary") and item.get("verified"):
                        profile["email"] = item.get("email")
                        break
                else:
                    for item in emails:
                        if item.get("verified"):
                            profile["email"] = item.get("email")
                            break
        return profile

    userinfo_url = _cfg("oauth2_userinfo_url")
    if not userinfo_url:
        raise ValueError("未配置 OAuth2 用户信息地址")
    profile = _http_get_json(
        userinfo_url,
        {"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    if not isinstance(profile, dict):
        raise ValueError("获取用户资料失败")
    return profile


def map_profile(provider: str, raw: dict) -> dict:
    """把原始资料映射为标准结构 {provider_uid, username, nickname, email, avatar_url}。"""
    if provider == "github":
        uid = raw.get("id")
        username = raw.get("login")
        return {
            "provider_uid": str(uid) if uid is not None else "",
            "username": str(username) if username else "",
            "nickname": raw.get("name") or (str(username) if username else None),
            "email": raw.get("email"),
            "avatar_url": raw.get("avatar_url"),
        }

    uid = raw.get(_cfg("oauth2_user_id_field", "sub"))
    username = raw.get(_cfg("oauth2_username_field", "preferred_username"))
    return {
        "provider_uid": str(uid) if uid is not None else "",
        "username": str(username) if username else (str(uid) if uid is not None else ""),
        "nickname": raw.get(_cfg("oauth2_nickname_field", "name")),
        "email": raw.get(_cfg("oauth2_email_field", "email")),
        "avatar_url": raw.get(_cfg("oauth2_avatar_field", "picture")),
    }
