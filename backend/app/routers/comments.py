# -*- coding: utf-8 -*-
"""评论路由：公开查看/发表评论 + 管理端评论管理。"""
import math
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from backend.app.database import get_db
from backend.app.deps import get_current_admin, get_current_user
from backend.app.media_service import create_admin_media_token, parse_folder_token
from backend.app.models import Comment, Image, User
from backend.app.schemas import (
    CommentBatchRequest,
    CommentCreateRequest,
    CommentStatusUpdate,
)
from backend.app.seed import get_bool_setting
from backend.app.site_config import effective_frontend_base

router = APIRouter(prefix="/api/images", tags=["comments"])
admin_router = APIRouter(
    prefix="/api/admin/comments",
    tags=["admin-comments"],
    dependencies=[Depends(get_current_admin)],
)

_MAX_CONTENT_LEN = 1000
_LOCKED_DETAIL = "该分类已加密，请先解锁"


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


def _ensure_folder_access(image: Image, db: Session, folder_token: Optional[str]) -> None:
    """加密分类图片需提供该分类的有效解锁令牌，否则返回 403。"""
    folder = image.folder
    if folder is None or not folder.password_hash:
        return
    unlocked = parse_folder_token(folder_token, db)
    if unlocked is None or unlocked.id != folder.id:
        raise HTTPException(status_code=403, detail=_LOCKED_DETAIL)


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


def _serialize_admin(comment: Comment, frontend_base: str) -> dict:
    """管理端评论序列化（附带所属图片信息与完整前台详情链接）。"""
    image = comment.image
    frontend_url = (
        f"{frontend_base}/image.html?id={image.id}"
        if image is not None and frontend_base
        else None
    )
    # 视频没有缩略图，避免拼接出空的 /thumbnails/ 路径
    thumb_url = ""
    if image is not None and image.thumb_name:
        thumb_url = f"/thumbnails/{image.thumb_name}"
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
            "thumb_url": thumb_url,
            "frontend_url": frontend_url,
            "media_token": create_admin_media_token(image.id) if image else None,
        },
    }


@router.get("/{image_id}/comments")
def list_comments(
    image_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    folder_token: Optional[str] = Query(None),
    x_folder_token: Optional[str] = Header(None, alias="X-Folder-Token"),
    db: Session = Depends(get_db),
) -> dict:
    """公开评论列表：仅返回可见评论，按时间倒序；加密分类需先解锁。"""
    image = _public_image(db, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    _ensure_folder_access(image, db, folder_token or x_folder_token)

    query = db.query(Comment).filter(
        Comment.image_id == image_id, Comment.status == "visible"
    )
    total = query.count()
    items = (
        query.options(joinedload(Comment.user))
        .order_by(Comment.created_at.desc(), Comment.id.desc())
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
    folder_token: Optional[str] = Query(None),
    x_folder_token: Optional[str] = Header(None, alias="X-Folder-Token"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """发表评论：评论功能需开启，内容去空格后非空且不超过 1000 字。"""
    if not get_bool_setting(db, "comments_enabled", True):
        raise HTTPException(status_code=403, detail="评论功能已关闭")
    image = _public_image(db, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    _ensure_folder_access(image, db, folder_token or x_folder_token)

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
    request: Request,
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
        query.options(
            joinedload(Comment.user),
            joinedload(Comment.image),
        )
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pages = math.ceil(total / page_size) if page_size else 0
    frontend_base = effective_frontend_base(db, request)
    return {
        "items": [_serialize_admin(item, frontend_base) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@admin_router.patch("/{comment_id}")
def update_comment_status(
    comment_id: int,
    payload: CommentStatusUpdate = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
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
    return _serialize_admin(comment, effective_frontend_base(db, request))


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
