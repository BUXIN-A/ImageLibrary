# -*- coding: utf-8 -*-
"""管理端登录配置路由：读取/更新本地、GitHub 与自定义 OAuth2 登录设置。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app import oauth_service
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.schemas import LoginSettingsUpdate
from backend.app.seed import get_bool_setting, get_setting, set_setting

router = APIRouter(
    prefix="/api/admin/login-settings",
    tags=["admin-login-settings"],
    dependencies=[Depends(get_current_admin)],
)

_BOOL_KEYS = ("login_local_enabled", "login_github_enabled", "login_oauth2_enabled")
_SECRET_KEYS = ("github_client_secret", "oauth2_client_secret")
_STR_KEYS = (
    "github_client_id",
    "oauth2_client_id",
    "oauth2_authorize_url",
    "oauth2_token_url",
    "oauth2_userinfo_url",
    "oauth2_scope",
    "oauth2_user_id_field",
    "oauth2_username_field",
    "oauth2_nickname_field",
    "oauth2_email_field",
    "oauth2_avatar_field",
)


def _build(db: Session) -> dict:
    """组装登录配置响应（密钥不回传明文）。"""
    github_secret = get_setting(db, "github_client_secret", "") or ""
    oauth2_secret = get_setting(db, "oauth2_client_secret", "") or ""
    data = {
        "login_local_enabled": get_bool_setting(db, "login_local_enabled", True),
        "login_github_enabled": get_bool_setting(db, "login_github_enabled", False),
        "github_client_id": get_setting(db, "github_client_id", "") or "",
        "github_client_secret_set": bool(github_secret),
        "github_client_secret_masked": "****" if github_secret else "",
        "login_oauth2_enabled": get_bool_setting(db, "login_oauth2_enabled", False),
        "oauth2_client_id": get_setting(db, "oauth2_client_id", "") or "",
        "oauth2_client_secret_set": bool(oauth2_secret),
        "oauth2_client_secret_masked": "****" if oauth2_secret else "",
        "oauth2_authorize_url": get_setting(db, "oauth2_authorize_url", "") or "",
        "oauth2_token_url": get_setting(db, "oauth2_token_url", "") or "",
        "oauth2_userinfo_url": get_setting(db, "oauth2_userinfo_url", "") or "",
        "oauth2_scope": get_setting(db, "oauth2_scope", "openid profile email") or "",
        "oauth2_user_id_field": get_setting(db, "oauth2_user_id_field", "sub") or "",
        "oauth2_username_field": get_setting(db, "oauth2_username_field", "preferred_username") or "",
        "oauth2_nickname_field": get_setting(db, "oauth2_nickname_field", "name") or "",
        "oauth2_email_field": get_setting(db, "oauth2_email_field", "email") or "",
        "oauth2_avatar_field": get_setting(db, "oauth2_avatar_field", "picture") or "",
        "callback_base": settings.api_base_url(),
        "github_callback_url": oauth_service.callback_url("github"),
        "oauth2_callback_url": oauth_service.callback_url("oauth2"),
    }
    return data


@router.get("")
def get_login_settings(db: Session = Depends(get_db)) -> dict:
    """读取登录配置。"""
    return _build(db)


@router.put("")
def update_login_settings(
    payload: LoginSettingsUpdate, db: Session = Depends(get_db)
) -> dict:
    """更新登录配置。

    布尔与普通字段按提供值更新；secret 字段缺失或为 null 表示不修改，
    空字符串表示清空，非空表示更新。
    """
    data = payload.model_dump(exclude_unset=True)

    for key in _BOOL_KEYS:
        if key in data and data[key] is not None:
            set_setting(db, key, "true" if data[key] else "false")

    for key in _STR_KEYS:
        if key in data and data[key] is not None:
            set_setting(db, key, data[key])

    for key in _SECRET_KEYS:
        if key in data and data[key] is not None:
            set_setting(db, key, data[key])

    return _build(db)
