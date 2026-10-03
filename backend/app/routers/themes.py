# -*- coding: utf-8 -*-
"""主题路由：公开读取主题 CSS/预览图 + 管理端导入、删除、下载与设为默认。"""
import json
import mimetypes

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from backend.app import theme_service
from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.export_service import cleanup_file
from backend.app.seed import get_setting, set_setting

router = APIRouter(prefix="/api/themes", tags=["themes"])
admin_router = APIRouter(
    prefix="/api/admin/themes",
    tags=["admin-themes"],
    dependencies=[Depends(get_current_admin)],
)


def _enabled_themes(db: Session) -> list[str]:
    """解析启用主题列表；解析失败时返回空列表由调用方处理。"""
    raw = get_setting(db, "enabled_themes")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (ValueError, TypeError):
        pass
    return []


@router.get("/{theme_id}/css")
def get_theme_css(theme_id: str):
    """返回主题 CSS 文件；不存在 404。"""
    path = theme_service.theme_css_path(theme_id)
    if path is None:
        raise HTTPException(status_code=404, detail="主题不存在")
    return FileResponse(path, media_type="text/css")


@router.get("/{theme_id}/preview")
def get_theme_preview(theme_id: str):
    """返回主题预览图；不存在 404。"""
    path = theme_service.theme_preview_path(theme_id)
    if path is None:
        raise HTTPException(status_code=404, detail="预览图不存在")
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    return FileResponse(path, media_type=media_type)


@admin_router.get("")
def list_themes() -> list[dict]:
    """列出全部主题（内置 + 自定义）。"""
    return theme_service.list_all_themes()


@admin_router.post("")
async def import_theme(file: UploadFile = File(...)) -> dict:
    """导入自定义主题 ZIP，失败返回 400 与中文原因。"""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件为空")
    try:
        return theme_service.import_theme_zip(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@admin_router.delete("/{theme_id}")
def delete_theme(theme_id: str) -> dict:
    """删除自定义主题（内置不可删除）。"""
    try:
        theme_service.delete_custom_theme(theme_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@admin_router.get("/{theme_id}/download")
def download_theme(theme_id: str) -> FileResponse:
    """下载主题 ZIP 包。"""
    try:
        zip_path = theme_service.export_theme_zip(theme_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{theme_id}-theme.zip",
        background=BackgroundTask(cleanup_file, zip_path),
    )


@admin_router.post("/{theme_id}/set-default")
def set_default_theme(theme_id: str, db: Session = Depends(get_db)) -> dict:
    """设置默认主题，并确保其包含在启用主题列表中。"""
    all_ids = {item["id"] for item in theme_service.list_all_themes()}
    if theme_id not in all_ids:
        raise HTTPException(status_code=404, detail="主题不存在")

    set_setting(db, "default_theme", theme_id)

    enabled = _enabled_themes(db)
    if theme_id not in enabled:
        enabled.append(theme_id)
        set_setting(db, "enabled_themes", json.dumps(enabled, ensure_ascii=False))
    return {"default_theme": theme_id}
