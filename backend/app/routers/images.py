# -*- coding: utf-8 -*-
"""公开图片路由：列表、详情、下载、分享与批量导出（仅返回已公开未删除图片）。

加密分类的图片默认不出现在公开列表中；提供该分类的有效解锁令牌
（``folder_token`` query 或 ``X-Folder-Token`` header）后才可访问。
"""
import math
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload
from starlette.background import BackgroundTask

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import client_ip
from backend.app.export_service import build_zip_file, cleanup_file
from backend.app.media_service import (
    image_folder_locked,
    parse_folder_token,
)
from backend.app.models import Folder, Image, Tag
from backend.app.notify_service import CATEGORY_VISIT, LEVEL_INFO, log
from backend.app.schemas import ExportRequest, PageResponse, PublicImageOut
from backend.app.seed import get_bool_setting

router = APIRouter(prefix="/api", tags=["images"])

_LOCKED_DETAIL = "该分类已加密，请先解锁"


def _public_query(db: Session):
    """构造仅含「已公开且未删除」图片的基础查询。"""
    return db.query(Image).filter(
        Image.status == "approved", Image.is_deleted.is_(False)
    )


def _locked_folder_ids():
    """设置了访问密码的分类 id 子查询。"""
    return select(Folder.id).where(Folder.password_hash.isnot(None))


def _apply_sort(query, sort: str):
    """按排序方式调整查询排序。"""
    if sort == "popular":
        return query.order_by(Image.views.desc(), Image.id.desc())
    if sort == "name":
        return query.order_by(Image.title.asc(), Image.id.desc())
    return query.order_by(Image.created_at.desc(), Image.id.desc())


def _public_out(image: Image) -> PublicImageOut:
    """构造公开图片响应，并标记所属分类是否加密。"""
    out = PublicImageOut.model_validate(image)
    out.folder_locked = image_folder_locked(image)
    return out


def _folder_accessible(image: Image, db: Session, folder_token: Optional[str]) -> bool:
    """判断当前请求是否有权访问图片所属分类（无密码分类恒为 True）。"""
    folder = image.folder
    if folder is None or not folder.password_hash:
        return True
    unlocked = parse_folder_token(folder_token, db)
    return unlocked is not None and unlocked.id == folder.id


def _apply_public_scope(query, db: Session, folder_token: Optional[str]):
    """「全部」口径：默认排除加密分类；有效令牌可纳入其对应分类。"""
    locked_ids = _locked_folder_ids()
    unlocked = parse_folder_token(folder_token, db)
    if unlocked is not None:
        return query.filter(
            or_(
                Image.folder_id.is_(None),
                Image.folder_id.notin_(locked_ids),
                Image.folder_id == unlocked.id,
            )
        )
    return query.filter(
        or_(Image.folder_id.is_(None), Image.folder_id.notin_(locked_ids))
    )


@router.get("/images", response_model=PageResponse[PublicImageOut])
def list_images(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=200),
    q: Optional[str] = Query(None),
    folder_id: Optional[int] = Query(None),
    uncategorized: int = Query(0),
    tag: Optional[str] = Query(None),
    sort: str = Query("latest"),
    folder_token: Optional[str] = Query(None),
    x_folder_token: Optional[str] = Header(None, alias="X-Folder-Token"),
    db: Session = Depends(get_db),
) -> PageResponse[PublicImageOut]:
    """公开图片列表：支持关键词、分类、未分类、标签与排序。"""
    token = folder_token or x_folder_token
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
        folder = db.get(Folder, folder_id)
        if folder is None:
            return PageResponse[PublicImageOut](
                items=[], total=0, page=page, page_size=page_size, pages=0
            )
        if folder.password_hash:
            unlocked = parse_folder_token(token, db)
            if unlocked is None or unlocked.id != folder.id:
                raise HTTPException(status_code=403, detail=_LOCKED_DETAIL)
        query = query.filter(Image.folder_id == folder_id)
    elif uncategorized == 1:
        query = query.filter(Image.folder_id.is_(None))
    else:
        query = _apply_public_scope(query, db, token)

    query = _apply_sort(query, sort)
    total = query.count()
    items = (
        query.options(selectinload(Image.folder))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pages = math.ceil(total / page_size) if page_size else 0
    return PageResponse[PublicImageOut](
        items=[_public_out(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/images/export")
def export_images(
    payload: ExportRequest = Body(...),
    folder_token: Optional[str] = Query(None),
    x_folder_token: Optional[str] = Header(None, alias="X-Folder-Token"),
    db: Session = Depends(get_db),
) -> FileResponse:
    """公开批量导出：仅打包其中可公开访问的图片（加密分类需先解锁）。"""
    if not payload.ids:
        raise HTTPException(status_code=400, detail="未选择要导出的图片")

    query = _public_query(db).filter(Image.id.in_(payload.ids))
    query = _apply_public_scope(query, db, folder_token or x_folder_token)
    images = query.order_by(Image.id.asc()).all()
    if not images:
        raise HTTPException(status_code=400, detail="没有可导出的图片")

    zip_path = build_zip_file(images, prefix="images_export")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="images_export.zip",
        background=BackgroundTask(cleanup_file, zip_path),
    )


@router.get("/images/{image_id}", response_model=PublicImageOut)
def get_image(
    image_id: int,
    request: Request,
    folder_token: Optional[str] = Query(None),
    x_folder_token: Optional[str] = Header(None, alias="X-Folder-Token"),
    db: Session = Depends(get_db),
) -> PublicImageOut:
    """公开图片详情，浏览量 +1；不存在返回 404，加密分类未解锁返回 403。"""
    image = _public_query(db).filter(Image.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    if not _folder_accessible(image, db, folder_token or x_folder_token):
        folder = image.folder
        raise HTTPException(
            status_code=403,
            detail={
                "message": _LOCKED_DETAIL,
                "folder_id": folder.id if folder is not None else None,
                "folder_locked": True,
            },
        )

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
    return _public_out(image)


@router.get("/images/{image_id}/download")
def download_image(
    image_id: int,
    folder_token: Optional[str] = Query(None),
    x_folder_token: Optional[str] = Header(None, alias="X-Folder-Token"),
    db: Session = Depends(get_db),
) -> FileResponse:
    """下载公开图片原图，下载量 +1；加密分类未解锁时不返回文件。"""
    image = _public_query(db).filter(Image.id == image_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    if not _folder_accessible(image, db, folder_token or x_folder_token):
        raise HTTPException(status_code=403, detail=_LOCKED_DETAIL)

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


@router.get("/share/{token}", response_model=PublicImageOut)
def get_shared_image(
    token: str,
    folder_token: Optional[str] = Query(None),
    x_folder_token: Optional[str] = Header(None, alias="X-Folder-Token"),
    db: Session = Depends(get_db),
) -> PublicImageOut:
    """通过分享 token 获取公开图片详情；加密分类需先解锁。"""
    image = _public_query(db).filter(Image.share_token == token).first()
    if image is None:
        raise HTTPException(status_code=404, detail="分享不存在")

    folder = image.folder
    if folder is not None and folder.password_hash:
        unlocked = parse_folder_token(folder_token or x_folder_token, db)
        if unlocked is None or unlocked.id != folder.id:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "该分享所属分类已加密",
                    "folder_id": folder.id,
                    "folder_locked": True,
                },
            )
    return _public_out(image)
