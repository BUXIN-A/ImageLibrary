# -*- coding: utf-8 -*-
"""数据库初始化：创建目录、执行迁移、写入默认管理员与默认设置。"""
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import SessionLocal, run_migrations
from backend.app.models import Admin, Setting
from backend.app.security import hash_password, verify_password

# 视为弱口令的初始密码（命中时会在首次建库时替换为随机密码）
_WEAK_ADMIN_PASSWORDS = {
    "admin123",
    "admin",
    "123456",
    "12345678",
    "password",
    "change-me-please",
    "changeme",
}


def _default_settings() -> dict[str, str]:
    """返回默认设置项（value 均为字符串）。"""
    return {
        "site_name": "我的图库",
        "upload_max_size": str(settings.MAX_UPLOAD_SIZE),
        "upload_max_video_size": str(settings.MAX_VIDEO_UPLOAD_SIZE),
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
        # ---------- 通知 / 服务日志 ----------
        # 启动时自动检测已配置的站点地址可用性（默认开启）
        "site_check_on_startup": "true",
        # 记录用户关键访问（图片详情浏览、普通用户登录）
        "visit_log_enabled": "true",
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


def _resolve_initial_password() -> tuple[str, bool]:
    """解析首次建库使用的管理员密码。

    配置为空或属于弱口令时生成随机密码，返回 ``(密码, 是否为随机生成)``。
    """
    configured = (settings.ADMIN_PASSWORD or "").strip()
    if configured and configured.lower() not in _WEAK_ADMIN_PASSWORDS:
        return configured, False
    return secrets.token_urlsafe(12), True


def _print_generated_password(username: str, password: str) -> None:
    """把随机生成的管理员密码打印到控制台（仅本次显示，不写入数据库/日志）。"""
    banner = (
        "\n" + "=" * 56 + "\n"
        " 已生成随机管理员密码（仅本次显示，请立即妥善保存）\n"
        f" 用户名：{username}\n"
        f" 密码：{password}\n"
        " 如需固定密码，请在 .env 中设置 ADMIN_PASSWORD 后重新初始化数据库。\n"
        + "=" * 56 + "\n"
    )
    print(banner, flush=True)


def init_seed() -> None:
    """初始化数据目录、执行迁移、默认管理员与默认设置（幂等，可重复调用）。"""
    settings.ensure_dirs()
    run_migrations()

    db: Session = SessionLocal()
    try:
        generated_credentials: Optional[tuple[str, str]] = None
        # 默认管理员：仅在 admins 表为空时创建
        if db.query(Admin).count() == 0:
            password, generated = _resolve_initial_password()
            db.add(
                Admin(
                    username=settings.ADMIN_USERNAME,
                    password_hash=hash_password(password),
                )
            )
            if generated:
                generated_credentials = (settings.ADMIN_USERNAME, password)

        # 可选：用环境变量强制同步已有管理员的账号与密码（ADMIN_FORCE_SYNC=true）
        # 未配置强密码时跳过密码同步，避免把已有管理员改成弱口令/空口令
        sync_password = (settings.ADMIN_PASSWORD or "").strip()
        sync_password_ok = bool(sync_password) and sync_password.lower() not in _WEAK_ADMIN_PASSWORDS
        if settings.ADMIN_FORCE_SYNC:
            admin = db.query(Admin).first()
            if admin is not None:
                changed = False
                if admin.username != settings.ADMIN_USERNAME:
                    admin.username = settings.ADMIN_USERNAME
                    changed = True
                if sync_password_ok and not verify_password(sync_password, admin.password_hash):
                    admin.password_hash = hash_password(sync_password)
                    changed = True
                if changed:
                    db.commit()

        # 默认设置：仅补充缺失的键
        for key, value in _default_settings().items():
            if db.get(Setting, key) is None:
                db.add(Setting(key=key, value=value))

        db.commit()
        if generated_credentials:
            _print_generated_password(*generated_credentials)
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


def get_int_setting(db: Session, key: str, default: int) -> int:
    """读取整型设置值；缺失、空值或非法内容时返回 default。"""
    raw = get_setting(db, key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default
