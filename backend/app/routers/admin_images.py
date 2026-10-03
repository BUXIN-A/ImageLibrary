# -*- coding: utf-8 -*-
"""后台图片管理路由：列表、上传、批量操作、导出、编辑、回收站与分享。"""
import math
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.export_service import build_zip_file, cleanup_file
from backend.app.images_service import delete_files, process_upload
from backend.app.models import Folder, Image, Tag, now
from backend.app.schemas import (
    AdminExportRequest,
    BatchImagesRequest,
    ImageOut,
    ImageUpdate,
    PageResponse,
)
from backend.app.security import generate_token

router = APIRouter(
    prefix="/api/admin/images",
    tags=["admin-images"],
    dependencies=[Depends(get_current_admin)],
)


def _resolve_tags(db: Session, names: Optional[list[str]]) -> list[Tag]:
    """按名称 get-or-create 标签，返回 Tag 对象列表。"""
    tags: list[Tag] = []
    for raw_name in names or []:
        name = (raw_name or "").strip()
        if not name:
            continue
        tag = db.query(Tag).filter(Tag.name == name).first()
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def _build_query(
    db: Session,
    q: Optional[str],
    folder_id: Optional[int],
    tag: Optional[str],
    status: Optional[str],
    include_deleted: bool,
):
    """构造后台图片查询（可按关键词、文件夹、标签、状态与删除标记过滤）。"""
    query = db.query(Image)
    if not include_deleted:
        query = query.filter(Image.is_deleted.is_(False))
    if status:
        query = query.filter(Image.status == status)
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
        query = query.filter(Image.folder_id == folder_id)
    return query


def _apply_sort(query, sort: Optional[str]):
    """后台列表排序：latest / popular / name。"""
    if sort == "popular":
        return query.order_by(Image.views.desc(), Image.id.desc())
    if sort == "name":
        return query.order_by(Image.title.asc(), Image.id.desc())
    return query.order_by(Image.created_at.desc(), Image.id.desc())


@router.get("", response_model=PageResponse[ImageOut])
def list_images(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=200),
    q: Optional[str] = Query(None),
    folder_id: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    include_deleted: int = Query(0),
    sort: str = Query("latest"),
    db: Session = Depends(get_db),
) -> PageResponse[ImageOut]:
    """后台图片分页列表（默认不含回收站）。"""
    query = _build_query(db, q, folder_id, tag, status, include_deleted == 1)
    query = _apply_sort(query, sort)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = math.ceil(total / page_size) if page_size else 0
    return PageResponse[ImageOut](
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


@router.post("")
async def upload_images(
    files: list[UploadFile] = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    folder_id: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """管理员批量上传：逐文件处理，单个失败不影响其它文件，状态为 approved。"""
    # 文件夹不存在时归为未分类，避免外键错误
    if folder_id is not None and db.get(Folder, folder_id) is None:
        folder_id = None

    tag_names = [t.strip() for t in (tags or "").split(",") if t.strip()]

    results: list[dict] = []
    success = 0
    failed = 0
    for upload in files:
        raw = await upload.read()
        original_name = upload.filename or ""
        try:
            info = process_upload(raw, original_name)
            image = Image(
                filename=info["filename"],
                original_name=original_name,
                title=title,
                description=description,
                mime_type=info["mime_type"],
                size=info["size"],
                width=info["width"],
                height=info["height"],
                thumb_name=info["thumb_name"],
                folder_id=folder_id,
                status="approved",
                exif=info["exif"],
            )
            if tag_names:
                image.tags = _resolve_tags(db, tag_names)
            db.add(image)
            db.commit()
            db.refresh(image)
            results.append(
                {
                    "filename": original_name,
                    "ok": True,
                    "error": None,
                    "image": ImageOut.model_validate(image),
                }
            )
            success += 1
        except ValueError as exc:
            db.rollback()
            results.append(
                {"filename": original_name, "ok": False, "error": str(exc), "image": None}
            )
            failed += 1
        except Exception:  # noqa: BLE001 - 单文件异常不影响其它文件
            db.rollback()
            results.append(
                {
                    "filename": original_name,
                    "ok": False,
                    "error": "处理失败",
                    "image": None,
                }
            )
            failed += 1

    return {"results": results, "success": success, "failed": failed}


@router.post("/batch")
def batch_images(
    payload: BatchImagesRequest = Body(...), db: Session = Depends(get_db)
) -> dict:
    """批量操作：delete/restore/purge/move/tag/approve/reject。"""
    images = db.query(Image).filter(Image.id.in_(payload.ids)).all()
    action = payload.action

    if action == "delete":
        for image in images:
            image.is_deleted = True
            image.deleted_at = now()
    elif action == "restore":
        for image in images:
            image.is_deleted = False
            image.deleted_at = None
    elif action == "purge":
        for image in images:
            delete_files(image)
            db.delete(image)
    elif action == "move":
        for image in images:
            image.folder_id = payload.folder_id
    elif action == "tag":
        new_tags = _resolve_tags(db, payload.tags)
        for image in images:
            existing_ids = {t.id for t in image.tags}
            for tag in new_tags:
                if tag.id not in existing_ids:
                    image.tags.append(tag)
    elif action == "approve":
        for image in images:
            image.status = "approved"
            image.reject_reason = None
    elif action == "reject":
        for image in images:
            image.status = "rejected"
            image.reject_reason = payload.reason
    else:
        raise HTTPException(status_code=400, detail="不支持的操作")

    db.commit()
    return {"affected": len(images)}


@router.post("/export")
def export_images(
    payload: AdminExportRequest = Body(...), db: Session = Depends(get_db)
) -> FileResponse:
    """后台导出：ids 非空时按 id 导出，否则按筛选条件导出。"""
    if payload.ids:
        images = (
            db.query(Image)
            .filter(Image.id.in_(payload.ids))
            .order_by(Image.id.asc())
            .all()
        )
    else:
        query = _build_query(
            db,
            payload.q,
            payload.folder_id,
            payload.tag,
            payload.status,
            payload.include_deleted,
        )
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


@router.patch("/{image_id}", response_model=ImageOut)
def update_image(
    image_id: int, payload: ImageUpdate = Body(...), db: Session = Depends(get_db)
) -> Image:
    """编辑图片信息；tags 传入时整体替换该图片标签。"""
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")

    data = payload.model_dump(exclude_unset=True)
    for field in ("title", "description", "folder_id", "status"):
        if field in data:
            setattr(image, field, data[field])
    if "tags" in data:
        image.tags = _resolve_tags(db, data["tags"])

    db.commit()
    db.refresh(image)
    return image


@router.delete("/{image_id}")
def soft_delete_image(image_id: int, db: Session = Depends(get_db)) -> dict:
    """软删除图片（移入回收站）。"""
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    image.is_deleted = True
    image.deleted_at = now()
    db.commit()
    return {"ok": True}


@router.delete("/{image_id}/purge")
def purge_image(image_id: int, db: Session = Depends(get_db)) -> dict:
    """彻底删除图片：同时删除数据库记录与磁盘文件。"""
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    delete_files(image)
    db.delete(image)
    db.commit()
    return {"ok": True}


@router.post("/{image_id}/restore")
def restore_image(image_id: int, db: Session = Depends(get_db)) -> dict:
    """从回收站还原图片。"""
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    image.is_deleted = False
    image.deleted_at = None
    db.commit()
    return {"ok": True}


@router.post("/{image_id}/share")
def share_image(image_id: int, db: Session = Depends(get_db)) -> dict:
    """为图片生成分享 token 与分享链接（若已存在则复用）。"""
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    if not image.share_token:
        image.share_token = generate_token(16)
        db.commit()
        db.refresh(image)
    share_url = (
        f"{settings.frontend_base_url()}/share.html?token={image.share_token}"
    )
    return {"share_token": image.share_token, "share_url": share_url}
