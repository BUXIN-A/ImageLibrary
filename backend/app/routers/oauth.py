# -*- coding: utf-8 -*-
"""OAuth 路由：登录方式查询、GitHub/自定义 OAuth2 授权跳转与回调。

安全要点：
- ``state`` 同时保存在服务端内存与 HttpOnly Cookie 中，回调需两者一致，
  防止登录 CSRF / 账号固定；
- 登录成功后不再把 JWT 放进跳转 URL，而是签发一次性登录码，
  由前端调用 ``POST /api/auth/oauth/exchange`` 换取令牌。
"""
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.app import oauth_service
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import User, now
from backend.app.schemas import OAuthExchangeRequest, UserAuthResponse, UserOut
from backend.app.seed import get_bool_setting, get_setting
from backend.app.security import create_access_token
from backend.app.site_config import effective_frontend_base

router = APIRouter(prefix="/api/auth", tags=["oauth"])

# 用户名冲突时的后缀（按 provider 区分）
_USERNAME_SUFFIX = {"github": "_gh", "oauth2": "_oa"}
# state 绑定 Cookie 名称（仅回调路径可见，降低泄露面）
_STATE_COOKIE = "il_oauth_state"
_STATE_MAX_AGE = 300


def _login_url(query: str, db: Session) -> str:
    """构造前台登录页跳转地址（优先使用后台配置的前台站点地址）。"""
    return f"{effective_frontend_base(db)}/login.html?{query}"


def _error_redirect(message: str, db: Session) -> RedirectResponse:
    """跳转到登录页并携带 URL 编码的中文错误信息。"""
    return RedirectResponse(_login_url(f"error={quote(message)}", db), status_code=302)


def _state_cookie_secure(request: Request) -> bool:
    """HTTPS 下为 state Cookie 加 Secure 标记。"""
    if request.url.scheme == "https":
        return True
    forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    return forwarded == "https" and settings.is_trusted_proxy(
        request.client.host if request.client else ""
    )


def _authorize_redirect(url: str, state: str, request: Request) -> RedirectResponse:
    """跳转到第三方授权页，并把 state 写入 HttpOnly Cookie。"""
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        key=_STATE_COOKIE,
        value=state,
        max_age=_STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_state_cookie_secure(request),
        path="/api/auth",
    )
    return response


def _verify_state(request: Request, state: str) -> bool:
    """同时校验服务端 state 与 Cookie 中的绑定值。"""
    cookie = request.cookies.get(_STATE_COOKIE) or ""
    if not cookie or not secrets.compare_digest(cookie, state or ""):
        return False
    return oauth_service.verify_state(state)


def _clear_state_cookie(response: RedirectResponse) -> RedirectResponse:
    """清除 state Cookie。"""
    response.delete_cookie(_STATE_COOKIE, path="/api/auth")
    return response


def _create_user_from_profile(db: Session, provider: str, mapped: dict) -> User:
    """按第三方资料创建用户（处理用户名/邮箱冲突）。"""
    uid = str(mapped.get("provider_uid") or "").strip()
    if not uid:
        raise ValueError("无法获取第三方用户唯一标识")

    username = str(mapped.get("username") or "").strip() or f"{provider}_{uid}"
    base = username
    if db.query(User).filter(User.username == username).first() is not None:
        suffix = _USERNAME_SUFFIX.get(provider, "_oa")
        username = f"{base}{suffix}{secrets.token_hex(2)}"
        while db.query(User).filter(User.username == username).first() is not None:
            username = f"{base}{suffix}{secrets.token_hex(3)}"

    email = mapped.get("email") or None
    if email and db.query(User).filter(User.email == email).first() is not None:
        email = None

    user = User(
        username=username,
        email=email,
        password_hash=None,
        provider=provider,
        provider_uid=uid,
        nickname=mapped.get("nickname"),
        avatar_url=mapped.get("avatar_url"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _handle_callback(
    provider: str, code: str, state: str, request: Request, db: Session
) -> RedirectResponse:
    """通用回调处理：校验 state、换令牌、取资料、查/建用户并签发一次性登录码。"""
    if not _verify_state(request, state):
        return _clear_state_cookie(_error_redirect("state 校验失败，请重试", db))

    try:
        token_data = oauth_service.exchange_code(provider, code)
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(token_data.get("error_description") or "未获取到访问令牌")
        raw_profile = oauth_service.fetch_profile(provider, access_token)
        mapped = oauth_service.map_profile(provider, raw_profile)
    except ValueError as exc:
        return _clear_state_cookie(_error_redirect(str(exc), db))

    uid = str(mapped.get("provider_uid") or "").strip()
    if not uid:
        return _clear_state_cookie(_error_redirect("无法获取第三方用户唯一标识", db))

    user = (
        db.query(User)
        .filter(User.provider == provider, User.provider_uid == uid)
        .first()
    )
    if user is None:
        try:
            user = _create_user_from_profile(db, provider, mapped)
        except ValueError as exc:
            return _clear_state_cookie(_error_redirect(str(exc), db))

    if not user.enabled:
        return _clear_state_cookie(
            RedirectResponse(_login_url("error=account_disabled", db), status_code=302)
        )

    user.last_login_at = now()
    db.commit()

    login_code = oauth_service.issue_login_code(user.username)
    return _clear_state_cookie(
        RedirectResponse(
            _login_url(f"oauth_code={quote(login_code)}&provider={quote(provider)}", db),
            status_code=302,
        )
    )


@router.post("/oauth/exchange", response_model=UserAuthResponse)
def exchange_oauth_code(
    payload: OAuthExchangeRequest = Body(...), db: Session = Depends(get_db)
) -> UserAuthResponse:
    """用一次性登录码换取用户令牌（避免 JWT 出现在跳转 URL 中）。"""
    username = oauth_service.consume_login_code(payload.code)
    if not username:
        raise HTTPException(status_code=400, detail="登录码无效或已过期，请重新登录")

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在，请重新登录")
    if not user.enabled:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    token = create_access_token(user.username, role="user")
    return UserAuthResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.get("/providers")
def list_providers(db: Session = Depends(get_db)) -> list[dict]:
    """返回可用的登录方式及启用状态。"""
    github_enabled = get_bool_setting(db, "login_github_enabled", False) and bool(
        get_setting(db, "github_client_id", "")
    )
    oauth2_enabled = get_bool_setting(db, "login_oauth2_enabled", False) and bool(
        get_setting(db, "oauth2_client_id", "")
    )
    return [
        {
            "id": "local",
            "name": "账号密码",
            "enabled": get_bool_setting(db, "login_local_enabled", True),
        },
        {"id": "github", "name": "GitHub", "enabled": github_enabled},
        {"id": "oauth2", "name": "自定义 OAuth2", "enabled": oauth2_enabled},
    ]


@router.get("/github/authorize")
def github_authorize(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    """跳转到 GitHub 授权页（state 绑定 HttpOnly Cookie）。"""
    if not (
        get_bool_setting(db, "login_github_enabled", False)
        and get_setting(db, "github_client_id", "")
    ):
        raise HTTPException(status_code=400, detail="GitHub 登录未启用")
    state = oauth_service.generate_state()
    url = oauth_service.build_authorize_url("github", state, db)
    return _authorize_redirect(url, state, request)


@router.get("/github/callback")
def github_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """GitHub 授权回调。"""
    return _handle_callback("github", code, state, request, db)


@router.get("/oauth2/authorize")
def oauth2_authorize(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    """跳转到自定义 OAuth2 授权页（state 绑定 HttpOnly Cookie）。"""
    if not (
        get_bool_setting(db, "login_oauth2_enabled", False)
        and get_setting(db, "oauth2_client_id", "")
    ):
        raise HTTPException(status_code=400, detail="OAuth2 登录未启用")
    state = oauth_service.generate_state()
    try:
        url = oauth_service.build_authorize_url("oauth2", state, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _authorize_redirect(url, state, request)


@router.get("/oauth2/callback")
def oauth2_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """自定义 OAuth2 授权回调。"""
    return _handle_callback("oauth2", code, state, request, db)
