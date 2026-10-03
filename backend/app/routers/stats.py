# -*- coding: utf-8 -*-
"""后台统计路由（仅管理员）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.models import Folder, Image, Tag, UploadToken
from backend.app.schemas import StatsOut

router = APIRouter(
    prefix="/api/admin/stats",
    tags=["admin-stats"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)) -> StatsOut:
    """返回仪表盘统计数据。"""
    images_total = (
        db.query(func.count(Image.id))
        .filter(Image.status == "approved", Image.is_deleted.is_(False))
        .scalar()
        or 0
    )
    pending_total = (
        db.query(func.count(Image.id))
        .filter(Image.status == "pending", Image.is_deleted.is_(False))
        .scalar()
        or 0
    )
    recycle_total = (
        db.query(func.count(Image.id)).filter(Image.is_deleted.is_(True)).scalar() or 0
    )
    folders_total = db.query(func.count(Folder.id)).scalar() or 0
    tags_total = db.query(func.count(Tag.id)).scalar() or 0
    tokens_total = db.query(func.count(UploadToken.id)).scalar() or 0
    views_total = (
        db.query(func.coalesce(func.sum(Image.views), 0))
        .filter(Image.status == "approved", Image.is_deleted.is_(False))
        .scalar()
        or 0
    )
    downloads_total = (
        db.query(func.coalesce(func.sum(Image.downloads), 0))
        .filter(Image.status == "approved", Image.is_deleted.is_(False))
        .scalar()
        or 0
    )

    return StatsOut(
        images_total=images_total,
        pending_total=pending_total,
        folders_total=folders_total,
        tags_total=tags_total,
        recycle_total=recycle_total,
        tokens_total=tokens_total,
        views_total=views_total,
        downloads_total=downloads_total,
    )
