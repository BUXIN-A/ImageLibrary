# -*- coding: utf-8 -*-
"""站点设置路由：公开站点信息/图标 + 管理端读写站点设置与上传图标。"""
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from PIL import Image
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.schemas import SiteUpdate
from backend.app.seed import get_bool_setting, get_setting, set_setting
from backend.app.site_config import (
    configured_api_base,
    configured_frontend_base,
    effective_api_base,
    effective_frontend_base,
)
from backend.app.version import __version__

router = APIRouter(prefix="/api", tags=["site"])
admin_router = APIRouter(
    prefix="/api/admin/site",
    tags=["admin-site"],
    dependencies=[Depends(get_current_admin)],
)

# favicon 上传大小上限
_FAVICON_MAX_SIZE = 2 * 1024 * 1024
# 允许作为 favicon 存储的扩展名（其余统一按 .png 保存）
_FAVICON_EXTS = {".ico", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def favicon_file_path() -> Optional[Path]:
    """返回 data 目录下已存储的 favicon 文件路径；不存在返回 None。"""
    for path in sorted(settings.DATA_DIR.glob("favicon.*")):
        if path.is_file() and path.suffix.lower() in _FAVICON_EXTS:
            return path
    return None


def _site_public(db: Session) -> dict:
    """组装公开站点信息（布尔项转为 bool）。"""
    return {
        "site_name": get_setting(db, "site_name", "我的图库"),
        "site_title": get_setting(db, "site_title") or get_setting(db, "site_name", "我的图库"),
        "site_description": get_setting(db, "site_description", ""),
        "site_keywords": get_setting(db, "site_keywords", ""),
        "favicon": get_setting(db, "favicon", ""),
        "allow_index": get_bool_setting(db, "allow_index", True),
        "sitemap_enabled": get_bool_setting(db, "sitemap_enabled", True),
        "comments_enabled": get_bool_setting(db, "comments_enabled", True),
        "footer_text": get_setting(db, "footer_text", ""),
        "frontend_base_url": effective_frontend_base(db),
        "api_base_url": effective_api_base(db),
        "version": __version__,
    }


def _site_admin(db: Session) -> dict:
    """管理端站点设置（在公开字段基础上追加原始配置值与 robots_extra）。"""
    data = _site_public(db)
    # 实际生效值（只读展示）
    data["resolved_api_base_url"] = data["api_base_url"]
    data["resolved_frontend_base_url"] = data["frontend_base_url"]
    # 后台配置值（可编辑，留空表示自动）
    data["api_base_url"] = configured_api_base(db)
    data["frontend_base_url"] = configured_frontend_base(db)
    data["robots_extra"] = get_setting(db, "robots_extra", "")
    return data


@router.get("/site")
def get_site(db: Session = Depends(get_db)) -> dict:
    """公开站点信息。"""
    return _site_public(db)


@router.get("/favicon")
def get_favicon(db: Session = Depends(get_db)):
    """返回站点图标：外链则重定向，本地文件则直接返回，未设置则 404。"""
    favicon = get_setting(db, "favicon", "") or ""
    if not favicon:
        raise HTTPException(status_code=404, detail="未设置站点图标")
    if favicon.startswith("http://") or favicon.startswith("https://"):
        return RedirectResponse(favicon, status_code=302)
    path = favicon_file_path()
    if path is None:
        raise HTTPException(status_code=404, detail="图标文件不存在")
    return FileResponse(path)


@admin_router.get("")
def get_site_settings(db: Session = Depends(get_db)) -> dict:
    """管理端读取完整站点设置。"""
    return _site_admin(db)


@admin_router.put("")
def update_site_settings(payload: SiteUpdate, db: Session = Depends(get_db)) -> dict:
    """管理端更新站点设置（仅更新显式提供的字段）。"""
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, bool):
            set_setting(db, key, "true" if value else "false")
        else:
            set_setting(db, key, value)
    return _site_admin(db)


@admin_router.post("/favicon")
async def upload_favicon(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict:
    """上传站点图标：校验为有效图片、限制大小，覆盖旧文件并更新设置。"""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(raw) > _FAVICON_MAX_SIZE:
        raise HTTPException(status_code=400, detail="图标文件过大")

    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception:  # noqa: BLE001 - 无法识别为图片
        raise HTTPException(status_code=400, detail="不是有效的图片文件")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _FAVICON_EXTS:
        ext = ".png"

    # 覆盖旧图标
    for old in settings.DATA_DIR.glob("favicon.*"):
        try:
            old.unlink()
        except OSError:
            pass
    (settings.DATA_DIR / f"favicon{ext}").write_bytes(raw)
    set_setting(db, "favicon", "/api/favicon")
    return {"favicon": "/api/favicon"}
