# -*- coding: utf-8 -*-
"""评论路由：公开查看/发表评论 + 管理端评论管理。"""
import math
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import get_current_admin, get_current_user
from backend.app.models import Comment, Image, User
from backend.app.schemas import (
    CommentBatchRequest,
    CommentCreateRequest,
    CommentStatusUpdate,
)
from backend.app.seed import get_bool_setting

router = APIRouter(prefix="/api/images", tags=["comments"])
admin_router = APIRouter(
    prefix="/api/admin/comments",
    tags=["admin-comments"],
    dependencies=[Depends(get_current_admin)],
)

_MAX_CONTENT_LEN = 1000


def _public_image(db: Session, image_id: int) -> Optional[Image]:
    """查询「已公开且未删除」的图片。"""
    return (
        db.query(Image)
        .filter(
            Image.id == image_id,
            Image.status == "approved",
            Image.is_deleted.is_(False),
        )
        .first()
    )


def _user_brief(user: Optional[User]) -> dict:
    """评论用户简要信息。"""
    if user is None:
        return {"id": 0, "username": "", "nickname": None, "avatar_url": None}
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
    }


def _serialize(comment: Comment) -> dict:
    """公开评论序列化。"""
    return {
        "id": comment.id,
        "content": comment.content,
        "created_at": comment.created_at,
        "user": _user_brief(comment.user),
    }


def _serialize_admin(comment: Comment) -> dict:
    """管理端评论序列化（附带所属图片信息）。"""
    image = comment.image
    return {
        "id": comment.id,
        "content": comment.content,
        "status": comment.status,
        "created_at": comment.created_at,
        "user": _user_brief(comment.user),
        "image": {
            "id": image.id if image else 0,
            "title": image.title if image else None,
            "filename": image.filename if image else "",
            "thumb_url": f"/thumbnails/{image.thumb_name}" if image else "",
        },
    }


@router.get("/{image_id}/comments")
def list_comments(
    image_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """公开评论列表：仅返回可见评论，按时间倒序。"""
    if _public_image(db, image_id) is None:
        raise HTTPException(status_code=404, detail="图片不存在")

    query = db.query(Comment).filter(
        Comment.image_id == image_id, Comment.status == "visible"
    )
    total = query.count()
    items = (
        query.order_by(Comment.created_at.desc(), Comment.id.desc())
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


@router.post("/{image_id}/comments")
def create_comment(
    image_id: int,
    payload: CommentCreateRequest = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """发表评论：评论功能需开启，内容去空格后非空且不超过 1000 字。"""
    if not get_bool_setting(db, "comments_enabled", True):
        raise HTTPException(status_code=403, detail="评论功能已关闭")
    if _public_image(db, image_id) is None:
        raise HTTPException(status_code=404, detail="图片不存在")

    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="评论内容不能为空")
    if len(content) > _MAX_CONTENT_LEN:
        raise HTTPException(status_code=400, detail=f"评论内容不能超过 {_MAX_CONTENT_LEN} 字")

    comment = Comment(
        image_id=image_id, user_id=user.id, content=content, status="visible"
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"comment": _serialize(comment)}


@admin_router.get("")
def list_all_comments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None),
    image_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """管理端评论分页列表。"""
    query = db.query(Comment)
    if q:
        query = query.filter(Comment.content.ilike(f"%{q}%"))
    if image_id is not None:
        query = query.filter(Comment.image_id == image_id)
    if status:
        query = query.filter(Comment.status == status)

    total = query.count()
    items = (
        query.order_by(Comment.created_at.desc(), Comment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pages = math.ceil(total / page_size) if page_size else 0
    return {
        "items": [_serialize_admin(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@admin_router.patch("/{comment_id}")
def update_comment_status(
    comment_id: int, payload: CommentStatusUpdate = Body(...), db: Session = Depends(get_db)
) -> dict:
    """更新评论状态（visible / hidden）。"""
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="评论不存在")
    if payload.status not in ("visible", "hidden"):
        raise HTTPException(status_code=400, detail="不支持的状态")

    comment.status = payload.status
    db.commit()
    db.refresh(comment)
    return _serialize_admin(comment)


@admin_router.delete("/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db)) -> dict:
    """删除单条评论。"""
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="评论不存在")
    db.delete(comment)
    db.commit()
    return {"ok": True}


@admin_router.post("/batch")
def batch_comments(
    payload: CommentBatchRequest = Body(...), db: Session = Depends(get_db)
) -> dict:
    """批量操作评论：delete / hide / show。"""
    comments = db.query(Comment).filter(Comment.id.in_(payload.ids)).all()
    action = payload.action
    if action == "delete":
        for comment in comments:
            db.delete(comment)
    elif action == "hide":
        for comment in comments:
            comment.status = "hidden"
    elif action == "show":
        for comment in comments:
            comment.status = "visible"
    else:
        raise HTTPException(status_code=400, detail="不支持的操作")

    db.commit()
    return {"affected": len(comments)}
