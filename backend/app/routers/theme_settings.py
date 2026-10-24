# -*- coding: utf-8 -*-
"""主题设置路由：公开主题/导航统计/预览图 + 管理端主题与预设管理。"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app import theme_settings_service as service
from backend.app.database import get_db
from backend.app.deps import get_current_admin

router = APIRouter(prefix="/api/theme", tags=["theme"])
admin_router = APIRouter(
    prefix="/api/admin/theme-settings",
    tags=["admin-theme-settings"],
    dependencies=[Depends(get_current_admin)],
)


# ---------------- 请求模型 ----------------
class ActiveThemeUpdate(BaseModel):
    """切换启用主题请求。"""

    theme_id: str


class ThemeConfigUpdate(BaseModel):
    """主题配置更新请求（default_preset / stats 均可选）。"""

    default_preset: Optional[str] = None
    stats: Optional[dict] = None


# ---------------- 内部辅助 ----------------
def _theme_or_404(theme_id: str) -> str:
    """校验主题并返回 id；非法时 404。"""
    try:
        return service.require_theme(theme_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


def _preset_id_or_400(preset_id: str) -> str:
    """校验预设 id；非法时 400。"""
    try:
        return service.validate_preset_id(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _admin_payload(db: Session) -> dict:
    """管理端主题设置完整数据。"""
    active = service.get_active_theme(db)
    themes = [
        {
            "id": meta["id"],
            "name": meta["name"],
            "description": meta["description"],
            "version": meta["version"],
            "active": meta["id"] == active,
            "preview_url": (
                f"/api/theme/preview/{meta['id']}" if meta["has_preview"] else ""
            ),
        }
        for meta in service.list_themes()
    ]
    return {
        "active_theme": active,
        "themes": themes,
        "presets": {
            theme_id: service.list_presets(db, theme_id)
            for theme_id in service.THEME_IDS
        },
        "config": service.public_theme_payload(db)["config"],
    }


# ---------------- 公开接口 ----------------
@router.get("")
def get_theme(db: Session = Depends(get_db)) -> dict:
    """公开主题配置：当前主题、主题列表、预设与配置。"""
    return service.public_theme_payload(db)


@router.get("/nav-stats")
def get_nav_stats(db: Session = Depends(get_db)) -> dict:
    """导航主题首页统计（公开已通过且未删除口径）。"""
    return service.nav_stats(db)


@router.get("/preview/{theme_id}")
def get_theme_preview(theme_id: str):
    """返回主题预览图；主题或图片不存在时 404。"""
    if theme_id not in service.THEME_IDS:
        raise HTTPException(status_code=404, detail="主题不存在")
    path: Optional[Path] = service.preview_path(theme_id)
    if path is None:
        raise HTTPException(status_code=404, detail="预览图不存在")
    return FileResponse(path, media_type="image/png")


# ---------------- 管理端接口 ----------------
@admin_router.get("")
def get_theme_settings(db: Session = Depends(get_db)) -> dict:
    """管理端读取主题设置（主题、预设、配置）。"""
    return _admin_payload(db)


@admin_router.put("/active")
def update_active_theme(
    payload: ActiveThemeUpdate, db: Session = Depends(get_db)
) -> dict:
    """设置启用主题（仅 base/nav）。"""
    theme_id = _theme_or_404(payload.theme_id)
    service.set_active_theme(db, theme_id)
    return _admin_payload(db)


@admin_router.post("/{theme_id}/presets")
async def upload_preset(
    theme_id: str,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """上传预设 CSS：默认以文件名作为 id 与名称，可显式覆盖。"""
    theme = _theme_or_404(theme_id)

    stem = Path(file.filename or "").stem
    preset_id = (id or "").strip() or stem.lower()
    display_name = (name or "").strip() or stem or preset_id
    _preset_id_or_400(preset_id)

    raw = await file.read()
    try:
        preset = service.save_preset(db, theme, preset_id, display_name, raw)
    except service.PresetConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    payload = _admin_payload(db)
    payload["preset"] = preset
    return payload


@admin_router.delete("/{theme_id}/presets/{preset_id}")
def delete_preset(
    theme_id: str, preset_id: str, db: Session = Depends(get_db)
) -> dict:
    """删除预设；每个主题至少保留一个。"""
    theme = _theme_or_404(theme_id)
    _preset_id_or_400(preset_id)
    try:
        service.delete_preset(db, theme, preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _admin_payload(db)


@admin_router.put("/{theme_id}/presets/{preset_id}/default")
def set_default_preset(
    theme_id: str, preset_id: str, db: Session = Depends(get_db)
) -> dict:
    """把预设设为该主题的默认预设。"""
    theme = _theme_or_404(theme_id)
    _preset_id_or_400(preset_id)
    try:
        service.set_default_preset(db, theme, preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _admin_payload(db)


@admin_router.put("/{theme_id}/config")
def update_theme_config(
    theme_id: str,
    payload: ThemeConfigUpdate = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    """更新主题配置：默认预设；导航主题额外支持统计开关。"""
    theme = _theme_or_404(theme_id)
    data = payload.model_dump(exclude_unset=True)
    try:
        service.update_theme_config(
            db,
            theme,
            default_preset=data.get("default_preset"),
            stats=data.get("stats"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _admin_payload(db)
