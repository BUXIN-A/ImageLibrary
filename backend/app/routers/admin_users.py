# -*- coding: utf-8 -*-
"""管理端用户管理路由：列表、启禁用、删除与重置密码。"""
import math
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.models import User
from backend.app.schemas import ResetPasswordRequest, UserOut, UserUpdate
from backend.app.security import hash_password

router = APIRouter(
    prefix="/api/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(get_current_admin)],
)

_PASSWORD_MIN = 6


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """用户分页列表：支持关键词、来源与启用状态筛选。"""
    query = db.query(User)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.nickname.ilike(pattern),
            )
        )
    if provider:
        query = query.filter(User.provider == provider)
    if enabled is not None:
        query = query.filter(User.enabled.is_(enabled))

    total = query.count()
    items = (
        query.order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pages = math.ceil(total / page_size) if page_size else 0
    return {
        "items": [UserOut.model_validate(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, payload: UserUpdate = Body(...), db: Session = Depends(get_db)
) -> User:
    """更新用户启用状态。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.enabled = payload.enabled
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    """删除用户（其评论由外键级联一并删除）。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"ok": True}


@router.post("/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: int, payload: ResetPasswordRequest = Body(...), db: Session = Depends(get_db)
) -> User:
    """重置用户密码（OAuth 无密码用户也可设置，provider 保持不变）。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    new_password = payload.new_password or ""
    if len(new_password) < _PASSWORD_MIN:
        raise HTTPException(status_code=400, detail=f"密码长度至少 {_PASSWORD_MIN} 位")

    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user
