# -*- coding: utf-8 -*-
"""OAuth 路由：登录方式查询、GitHub/自定义 OAuth2 授权跳转与回调。"""
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.app import oauth_service
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import User, now
from backend.app.seed import get_bool_setting, get_setting
from backend.app.security import create_access_token

router = APIRouter(prefix="/api/auth", tags=["oauth"])

# 用户名冲突时的后缀（按 provider 区分）
_USERNAME_SUFFIX = {"github": "_gh", "oauth2": "_oa"}


def _login_url(query: str) -> str:
    """构造前台登录页跳转地址。"""
    return f"{settings.frontend_base_url()}/login.html?{query}"


def _error_redirect(message: str) -> RedirectResponse:
    """跳转到登录页并携带 URL 编码的中文错误信息。"""
    return RedirectResponse(_login_url(f"error={quote(message)}"), status_code=302)


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


def _handle_callback(provider: str, code: str, state: str, db: Session) -> RedirectResponse:
    """通用回调处理：校验 state、换令牌、取资料、查/建用户并签发用户令牌。"""
    if not oauth_service.verify_state(state):
        return _error_redirect("state 校验失败，请重试")

    try:
        token_data = oauth_service.exchange_code(provider, code)
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(token_data.get("error_description") or "未获取到访问令牌")
        raw_profile = oauth_service.fetch_profile(provider, access_token)
        mapped = oauth_service.map_profile(provider, raw_profile)
    except ValueError as exc:
        return _error_redirect(str(exc))

    uid = str(mapped.get("provider_uid") or "").strip()
    if not uid:
        return _error_redirect("无法获取第三方用户唯一标识")

    user = (
        db.query(User)
        .filter(User.provider == provider, User.provider_uid == uid)
        .first()
    )
    if user is None:
        try:
            user = _create_user_from_profile(db, provider, mapped)
        except ValueError as exc:
            return _error_redirect(str(exc))

    if not user.enabled:
        return RedirectResponse(_login_url("error=account_disabled"), status_code=302)

    user.last_login_at = now()
    db.commit()

    jwt_token = create_access_token(user.username, role="user")
    return RedirectResponse(
        _login_url(f"token={jwt_token}&provider={provider}"), status_code=302
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
def github_authorize(db: Session = Depends(get_db)) -> RedirectResponse:
    """跳转到 GitHub 授权页。"""
    if not (
        get_bool_setting(db, "login_github_enabled", False)
        and get_setting(db, "github_client_id", "")
    ):
        raise HTTPException(status_code=400, detail="GitHub 登录未启用")
    url = oauth_service.build_authorize_url("github", oauth_service.generate_state())
    return RedirectResponse(url, status_code=302)


@router.get("/github/callback")
def github_callback(
    code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    """GitHub 授权回调。"""
    return _handle_callback("github", code, state, db)


@router.get("/oauth2/authorize")
def oauth2_authorize(db: Session = Depends(get_db)) -> RedirectResponse:
    """跳转到自定义 OAuth2 授权页。"""
    if not (
        get_bool_setting(db, "login_oauth2_enabled", False)
        and get_setting(db, "oauth2_client_id", "")
    ):
        raise HTTPException(status_code=400, detail="OAuth2 登录未启用")
    try:
        url = oauth_service.build_authorize_url("oauth2", oauth_service.generate_state())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url, status_code=302)


@router.get("/oauth2/callback")
def oauth2_callback(
    code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    """自定义 OAuth2 授权回调。"""
    return _handle_callback("oauth2", code, state, db)
