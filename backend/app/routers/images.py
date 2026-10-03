# -*- coding: utf-8 -*-
"""公开图片路由：列表、详情、下载、分享与批量导出（仅返回已公开未删除图片）。"""
import math
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import client_ip
from backend.app.export_service import build_zip_file, cleanup_file
from backend.app.models import Folder, Image, Tag
from backend.app.notify_service import CATEGORY_VISIT, LEVEL_INFO, log
from backend.app.schemas import ExportRequest, ImageOut, PageResponse
from backend.app.seed import get_bool_setting

router = APIRouter(prefix="/api", tags=["images"])


def _public_query(db: Session):
    """构造仅含「已公开且未删除」图片的基础查询。"""
    return db.query(Image).filter(
        Image.status == "approved", Image.is_deleted.is_(False)
    )


def _apply_sort(query, sort: str):
    """按排序方式调整查询排序。"""
    if sort == "popular":
        return query.order_by(Image.views.desc(), Image.id.desc())
    if sort == "name":
        return query.order_by(Image.title.asc(), Image.id.desc())
    return query.order_by(Image.created_at.desc(), Image.id.desc())


@router.get("/images", response_model=PageResponse[ImageOut])
def list_images(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=200),
    q: Optional[str] = Query(None),
    folder_id: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    sort: str = Query("latest"),
    include_subfolders: int = Query(0),
    db: Session = Depends(get_db),
) -> PageResponse[ImageOut]:
    """公开图片列表：支持关键词、文件夹（可含子文件夹）、标签与排序。"""
    query = _public_query(db)

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                Image.title.ilike(pattern),
                Image.description.ilike(pattern),
                Image.original_name.ilike(pattern),
            )
        )

    if tag:
        query = query.filter(Image.tags.any(Tag.name == tag))

    if folder_id is not None:
        if include_subfolders == 1:
            folder = db.get(Folder, folder_id)
            if folder is None:
                return PageResponse[ImageOut](
                    items=[], total=0, page=page, page_size=page_size, pages=0
                )
            # 物化路径前缀匹配该文件夹及其全部后代
            sub_ids = select(Folder.id).where(Folder.path.like(f"{folder.path}%"))
            query = query.filter(Image.folder_id.in_(sub_ids))
        else:
            query = query.filter(Image.folder_id == folder_id)

    query = _apply_sort(query, sort)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = math.ceil(total / page_size) if page_size else 0
    return PageResponse[ImageOut](
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


@router.post("/images/export")
def export_images(
    payload: ExportRequest = Body(...), db: Session = Depends(get_db)
) -> FileResponse:
    """公开批量导出：仅打包其中已公开且未删除的图片。"""
    if not payload.ids:
        raise HTTPException(status_code=400, detail="未选择要导出的图片")

    images = (
        _public_query(db)
        .filter(Image.id.in_(payload.ids))
        .order_by(Image.id.asc())
        .all()
    )
    if not images:
        raise HTTPException(status_code=400, detail="没有可导出的图片")

    zip_path = build_zip_file(images, prefix="images_export")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="images_export.zip",
        background=BackgroundTask(cleanup_file, zip_path),
    )


@router.get("/images/{image_id}", response_model=ImageOut)
def get_image(image_id: int, request: Request, db: Session = Depends(get_db)) -> Image:
    """公开图片详情，浏览量 +1；不存在或未公开返回 404。"""
    image = _public_query(db).filter(Image.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    image.views = (image.views or 0) + 1
    db.commit()
    db.refresh(image)
    if get_bool_setting(db, "visit_log_enabled", True):
        log(
            db,
            LEVEL_INFO,
            CATEGORY_VISIT,
            f"浏览图片 #{image.id}：{image.title or image.original_name}",
            ip=client_ip(request),
        )
    return image


@router.get("/images/{image_id}/download")
def download_image(image_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """下载公开图片原图，下载量 +1。"""
    image = _public_query(db).filter(Image.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")

    file_path = settings.UPLOAD_DIR / image.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="图片文件不存在")

    image.downloads = (image.downloads or 0) + 1
    db.commit()
    return FileResponse(
        file_path,
        media_type=image.mime_type,
        filename=image.original_name,
    )


@router.get("/share/{token}", response_model=ImageOut)
def get_shared_image(token: str, db: Session = Depends(get_db)) -> Image:
    """通过分享 token 获取公开图片详情；不存在返回 404。"""
    image = _public_query(db).filter(Image.share_token == token).first()
    if image is None:
        raise HTTPException(status_code=404, detail="分享不存在")
    return image
