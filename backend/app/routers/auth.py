# -*- coding: utf-8 -*-
"""认证路由：登录、获取当前管理员、修改密码。"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import client_ip, get_current_admin
from backend.app.models import Admin
from backend.app.notify_service import CATEGORY_LOGIN, LEVEL_INFO, LEVEL_WARNING, log
from backend.app.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
)
from backend.app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    """管理员登录：与 admins 表首条记录比对，成功签发 JWT。"""
    admin = db.query(Admin).order_by(Admin.id).first()
    if (
        admin is None
        or admin.username != payload.username
        or not verify_password(payload.password, admin.password_hash)
    ):
        log(
            db,
            LEVEL_WARNING,
            CATEGORY_LOGIN,
            f"管理员登录失败：{payload.username}",
            ip=client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    log(db, LEVEL_INFO, CATEGORY_LOGIN, f"管理员登录成功：{admin.username}", ip=client_ip(request))
    access_token = create_access_token(admin.username)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me")
def me(admin: Admin = Depends(get_current_admin)) -> dict:
    """返回当前登录管理员的基本信息。"""
    return {"id": admin.id, "username": admin.username}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """修改密码：校验旧密码后更新为新密码哈希。"""
    if not verify_password(payload.old_password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")

    admin.password_hash = hash_password(payload.new_password)
    db.add(admin)
    db.commit()
    return {"ok": True}
