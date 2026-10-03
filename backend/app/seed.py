# -*- coding: utf-8 -*-
"""数据库初始化：创建目录、建表、写入默认管理员与默认设置。"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import SessionLocal, init_db
from backend.app.models import Admin, Setting
from backend.app.security import hash_password, verify_password


def _default_settings() -> dict[str, str]:
    """返回默认设置项（value 均为字符串）。"""
    return {
        "site_name": "我的图库",
        "default_theme": "light",
        "enabled_themes": json.dumps(
            ["light", "dark", "ocean", "forest", "sunset", "sakura"],
            ensure_ascii=False,
        ),
        "upload_max_size": str(settings.MAX_UPLOAD_SIZE),
        # ---------- 站点元信息 ----------
        "site_title": "我的图库",
        "site_description": "",
        "site_keywords": "",
        "favicon": "",
        "allow_index": "true",
        "robots_extra": "",
        "sitemap_enabled": "true",
        "comments_enabled": "true",
        "footer_text": "",
        # ---------- 站点地址（留空则按 PUBLIC_HOST / 请求主机自动推断） ----------
        "api_base_url": "",
        "frontend_base_url": "",
        # 后台专属 API 地址：留空则与 api_base_url 相同（用于后台本地/内网快速上传）
        "admin_api_base_url": "",
        # ---------- 登录配置 ----------
        "login_local_enabled": "true",
        "login_github_enabled": "false",
        "github_client_id": "",
        "github_client_secret": "",
        "login_oauth2_enabled": "false",
        "oauth2_client_id": "",
        "oauth2_client_secret": "",
        "oauth2_authorize_url": "",
        "oauth2_token_url": "",
        "oauth2_userinfo_url": "",
        "oauth2_scope": "openid profile email",
        "oauth2_user_id_field": "sub",
        "oauth2_username_field": "preferred_username",
        "oauth2_nickname_field": "name",
        "oauth2_email_field": "email",
        "oauth2_avatar_field": "picture",
    }


def init_seed() -> None:
    """初始化数据目录、数据表、默认管理员与默认设置（幂等，可重复调用）。"""
    settings.ensure_dirs()
    init_db()

    db: Session = SessionLocal()
    try:
        # 默认管理员：仅在 admins 表为空时创建
        if db.query(Admin).count() == 0:
            db.add(
                Admin(
                    username=settings.ADMIN_USERNAME,
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                )
            )

        # 可选：用环境变量强制同步已有管理员的账号与密码（ADMIN_FORCE_SYNC=true）
        if settings.ADMIN_FORCE_SYNC:
            admin = db.query(Admin).first()
            if admin is not None:
                changed = False
                if admin.username != settings.ADMIN_USERNAME:
                    admin.username = settings.ADMIN_USERNAME
                    changed = True
                if not verify_password(settings.ADMIN_PASSWORD, admin.password_hash):
                    admin.password_hash = hash_password(settings.ADMIN_PASSWORD)
                    changed = True
                if changed:
                    db.commit()

        # 默认设置：仅补充缺失的键
        for key, value in _default_settings().items():
            if db.get(Setting, key) is None:
                db.add(Setting(key=key, value=value))

        db.commit()
    finally:
        db.close()


def get_setting(db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
    """读取设置值，不存在时返回 default。"""
    item = db.get(Setting, key)
    return item.value if item is not None else default


def set_setting(db: Session, key: str, value) -> None:
    """写入或更新设置值（统一以字符串存储）。"""
    text = None if value is None else (value if isinstance(value, str) else str(value))
    item = db.get(Setting, key)
    if item is None:
        db.add(Setting(key=key, value=text))
    else:
        item.value = text
    db.commit()


def get_bool_setting(db: Session, key: str, default: bool = False) -> bool:
    """读取布尔设置值（"true"/"1"/"yes"/"on" 视为真，其它为假）。"""
    raw = get_setting(db, key)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}
