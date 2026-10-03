# -*- coding: utf-8 -*-
"""站点设置路由：公开读取 + 管理端读写。"""
import json

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from backend.app import theme_service
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.models import Setting
from backend.app.schemas import SettingsUpdate
from backend.app.seed import get_bool_setting, get_setting, set_setting
from backend.app.themes import THEME_IDS

router = APIRouter(prefix="/api", tags=["settings"])
admin_router = APIRouter(
    prefix="/api/admin/settings",
    tags=["admin-settings"],
    dependencies=[Depends(get_current_admin)],
)


def _enabled_themes(db: Session) -> list[str]:
    """解析启用的主题列表；解析失败时回退为全部预设主题。"""
    raw = get_setting(db, "enabled_themes")
    if not raw:
        return list(THEME_IDS)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            return [str(item) for item in parsed]
    except (ValueError, TypeError):
        pass
    return list(THEME_IDS)


@router.get("/settings")
def public_settings(db: Session = Depends(get_db)) -> dict:
    """公开站点设置（供前台读取）。"""
    upload_max_size = get_setting(db, "upload_max_size")
    try:
        upload_max_size_int = int(upload_max_size) if upload_max_size else settings.MAX_UPLOAD_SIZE
    except (ValueError, TypeError):
        upload_max_size_int = settings.MAX_UPLOAD_SIZE

    return {
        "site_name": get_setting(db, "site_name", "我的图库"),
        "default_theme": get_setting(db, "default_theme", "light"),
        "enabled_themes": _enabled_themes(db),
        "themes": theme_service.list_all_themes(),
        "upload_max_size": upload_max_size_int,
        "frontend_base_url": settings.frontend_base_url(),
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
    """返回设置表中全部键值。"""
    items = db.query(Setting).all()
    return {item.key: item.value for item in items}


@admin_router.put("")
def update_settings(
    payload: SettingsUpdate = Body(...), db: Session = Depends(get_db)
) -> dict:
    """更新站点设置（enabled_themes 以 JSON 字符串存储）。"""
    data = payload.model_dump(exclude_unset=True)
    if data.get("site_name") is not None:
        set_setting(db, "site_name", data["site_name"])
    if data.get("default_theme") is not None:
        set_setting(db, "default_theme", data["default_theme"])
    if "enabled_themes" in data and data["enabled_themes"] is not None:
        set_setting(
            db,
            "enabled_themes",
            json.dumps(data["enabled_themes"], ensure_ascii=False),
        )

    items = db.query(Setting).all()
    return {item.key: item.value for item in items}
