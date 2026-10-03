# -*- coding: utf-8 -*-
"""审核队列路由（仅管理员）：待审列表与通过/拒绝/批量审核。"""
import math
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.models import Image
from backend.app.schemas import (
    ImageOut,
    PageResponse,
    ReviewBatchRequest,
    ReviewRejectRequest,
)

router = APIRouter(
    prefix="/api/admin/review",
    tags=["admin-review"],
    dependencies=[Depends(get_current_admin)],
)


def _pending_query(db: Session):
    """待审核图片基础查询。"""
    return db.query(Image).filter(
        Image.status == "pending", Image.is_deleted.is_(False)
    )


@router.get("", response_model=PageResponse[ImageOut])
def list_pending(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PageResponse[ImageOut]:
    """分页返回待审核图片。"""
    query = _pending_query(db).order_by(Image.created_at.asc(), Image.id.asc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = math.ceil(total / page_size) if page_size else 0
    return PageResponse[ImageOut](
        items=items, total=total, page=page, page_size=page_size, pages=pages
    )


@router.post("/batch")
def batch_review(
    payload: ReviewBatchRequest = Body(...), db: Session = Depends(get_db)
) -> dict:
    """批量审核：action 为 approve 或 reject。"""
    images = db.query(Image).filter(Image.id.in_(payload.ids)).all()
    if payload.action == "approve":
        for image in images:
            image.status = "approved"
            image.reject_reason = None
    elif payload.action == "reject":
        for image in images:
            image.status = "rejected"
            image.reject_reason = payload.reason
    else:
        raise HTTPException(status_code=400, detail="不支持的操作")
    db.commit()
    return {"affected": len(images)}


@router.post("/{image_id}/approve", response_model=ImageOut)
def approve_image(image_id: int, db: Session = Depends(get_db)) -> Image:
    """通过审核：状态置为 approved。"""
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    image.status = "approved"
    image.reject_reason = None
    db.commit()
    db.refresh(image)
    return image


@router.post("/{image_id}/reject", response_model=ImageOut)
def reject_image(
    image_id: int,
    payload: Optional[ReviewRejectRequest] = Body(None),
    db: Session = Depends(get_db),
) -> Image:
    """拒绝审核：状态置为 rejected 并记录原因。"""
    image = db.get(Image, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    image.status = "rejected"
    image.reject_reason = payload.reason if payload is not None else None
    db.commit()
    db.refresh(image)
    return image
