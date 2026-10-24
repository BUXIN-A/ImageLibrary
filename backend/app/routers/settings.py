# -*- coding: utf-8 -*-
"""站点设置路由：公开读取 + 管理端读写。"""
from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.models import Setting
from backend.app.schemas import SettingsUpdate
from backend.app.seed import get_bool_setting, get_int_setting, get_setting, set_setting
from backend.app.site_config import effective_api_base, effective_frontend_base
from backend.app.version import __version__

router = APIRouter(prefix="/api", tags=["settings"])
admin_router = APIRouter(
    prefix="/api/admin/settings",
    tags=["admin-settings"],
    dependencies=[Depends(get_current_admin)],
)


def _is_sensitive_key(key: str) -> bool:
    """判断设置键是否为敏感项（密钥/口令类，不应明文返回）。"""
    lowered = (key or "").strip().lower()
    return "secret" in lowered


def _safe_settings_map(items) -> dict:
    """把设置项序列化为键值字典，过滤敏感键以避免密钥明文外泄。"""
    return {item.key: item.value for item in items if not _is_sensitive_key(item.key)}


@router.get("/settings")
def public_settings(request: Request, db: Session = Depends(get_db)) -> dict:
    """公开站点设置（供前台读取；主题配置见 ``/api/theme``）。"""
    return {
        "site_name": get_setting(db, "site_name", "我的图库"),
        "upload_max_size": get_int_setting(
            db, "upload_max_size", settings.MAX_UPLOAD_SIZE
        ),
        "max_video_size": get_int_setting(
            db, "upload_max_video_size", settings.MAX_VIDEO_UPLOAD_SIZE
        ),
        "allowed_image_extensions": sorted(settings.ALLOWED_IMAGE_EXTENSIONS),
        "allowed_video_extensions": sorted(settings.ALLOWED_VIDEO_EXTENSIONS),
        "frontend_base_url": effective_frontend_base(db, request),
        "api_base_url": effective_api_base(db, request),
        "version": __version__,
        # ---------- 站点元信息 / 功能开关 ----------
        "site_title": get_setting(db, "site_title") or get_setting(db, "site_name", "我的图库"),
        "site_description": get_setting(db, "site_description", ""),
        "site_keywords": get_setting(db, "site_keywords", ""),
        "favicon": get_setting(db, "favicon", ""),
        "allow_index": get_bool_setting(db, "allow_index", True),
        "sitemap_enabled": get_bool_setting(db, "sitemap_enabled", True),
        "comments_enabled": get_bool_setting(db, "comments_enabled", True),
        "footer_text": get_setting(db, "footer_text", ""),
    }


@admin_router.get("")
def get_all_settings(db: Session = Depends(get_db)) -> dict:
    """返回设置表中的键值（已过滤敏感键）。"""
    items = db.query(Setting).all()
    return _safe_settings_map(items)


@admin_router.put("")
def update_settings(
    payload: SettingsUpdate = Body(...), db: Session = Depends(get_db)
) -> dict:
    """更新站点设置（主题相关配置已迁移至主题设置接口）。"""
    data = payload.model_dump(exclude_unset=True)
    if data.get("site_name") is not None:
        set_setting(db, "site_name", data["site_name"])

    items = db.query(Setting).all()
    return _safe_settings_map(items)
