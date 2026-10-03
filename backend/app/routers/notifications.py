# -*- coding: utf-8 -*-
"""后台通知路由：分页查看服务日志、标记已读、删除与清空。"""
import math
from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.models import Notification
from backend.app.notify_service import CATEGORIES, CATEGORY_LABELS, LEVELS, LEVEL_LABELS
from backend.app.schemas import (
    NotificationBatchRequest,
    NotificationClearRequest,
    NotificationReadRequest,
)

admin_router = APIRouter(
    prefix="/api/admin/notifications",
    tags=["admin-notifications"],
    dependencies=[Depends(get_current_admin)],
)


def _serialize(item: Notification) -> dict:
    """序列化单条通知。"""
    return {
        "id": item.id,
        "level": item.level,
        "category": item.category,
        "message": item.message,
        "detail": item.detail,
        "ip": item.ip,
        "is_read": item.is_read,
        "created_at": item.created_at,
    }


@admin_router.get("/meta")
def notification_meta() -> dict:
    """返回可用的级别、分类及其显示名，供前端筛选使用。"""
    return {
        "levels": [{"value": v, "label": LEVEL_LABELS.get(v, v)} for v in LEVELS],
        "categories": [
            {"value": v, "label": CATEGORY_LABELS.get(v, v)} for v in CATEGORIES
        ],
    }


@admin_router.get("/summary")
def notification_summary(db: Session = Depends(get_db)) -> dict:
    """通知统计：总数、未读数与各级别数量。"""
    total = db.query(func.count(Notification.id)).scalar() or 0
    unread = (
        db.query(func.count(Notification.id))
        .filter(Notification.is_read.is_(False))
        .scalar()
        or 0
    )
    rows = (
        db.query(Notification.level, func.count(Notification.id))
        .group_by(Notification.level)
        .all()
    )
    by_level = {level: 0 for level in LEVELS}
    for level, count in rows:
        by_level[level] = count
    return {"total": total, "unread": unread, "by_level": by_level}


@admin_router.get("")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    level: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    unread_only: int = Query(0),
    db: Session = Depends(get_db),
) -> dict:
    """通知分页列表：支持级别、分类、关键词与仅看未读筛选。"""
    query = db.query(Notification)
    if level:
        query = query.filter(Notification.level == level)
    if category:
        query = query.filter(Notification.category == category)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            Notification.message.ilike(pattern) | Notification.detail.ilike(pattern)
        )
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))

    total = query.count()
    items = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pages = math.ceil(total / page_size) if page_size else 0
    return {
        "items": [_serialize(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@admin_router.post("/read")
def mark_read(
    payload: NotificationReadRequest = Body(...), db: Session = Depends(get_db)
) -> dict:
    """标记通知为已读：all 为真时全部标记，否则按 ids 标记。"""
    query = db.query(Notification).filter(Notification.is_read.is_(False))
    if not payload.all:
        if not payload.ids:
            return {"affected": 0}
        query = query.filter(Notification.id.in_(payload.ids))
    affected = query.update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {"affected": affected}


@admin_router.post("/delete")
def batch_delete(
    payload: NotificationBatchRequest = Body(...), db: Session = Depends(get_db)
) -> dict:
    """批量删除通知。"""
    if not payload.ids:
        return {"affected": 0}
    affected = (
        db.query(Notification)
        .filter(Notification.id.in_(payload.ids))
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"affected": affected}


@admin_router.post("/clear")
def clear_notifications(
    payload: NotificationClearRequest = Body(default=NotificationClearRequest()),
    db: Session = Depends(get_db),
) -> dict:
    """清空通知：only_read 为真时仅清空已读通知。"""
    query = db.query(Notification)
    if payload.only_read:
        query = query.filter(Notification.is_read.is_(True))
    affected = query.delete(synchronize_session=False)
    db.commit()
    return {"affected": affected}
