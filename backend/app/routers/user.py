# -*- coding: utf-8 -*-
"""普通用户路由：注册、登录与获取当前用户信息。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import get_current_user
from backend.app.models import User, now
from backend.app.schemas import (
    UserAuthResponse,
    UserLoginRequest,
    UserOut,
    UserRegisterRequest,
)
from backend.app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/user", tags=["user"])

_USERNAME_MIN = 3
_USERNAME_MAX = 32
_PASSWORD_MIN = 6


def _auth_response(user: User) -> UserAuthResponse:
    """构造注册/登录成功响应（含用户令牌与用户信息）。"""
    token = create_access_token(user.username, role="user")
    return UserAuthResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=UserAuthResponse)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> UserAuthResponse:
    """用户注册：校验用户名/密码长度与唯一性，成功后直接签发用户令牌。"""
    username = (payload.username or "").strip()
    password = payload.password or ""
    email = (payload.email or "").strip() or None

    if not (_USERNAME_MIN <= len(username) <= _USERNAME_MAX):
        raise HTTPException(
            status_code=400, detail=f"用户名长度需为 {_USERNAME_MIN}-{_USERNAME_MAX} 个字符"
        )
    if len(password) < _PASSWORD_MIN:
        raise HTTPException(status_code=400, detail=f"密码长度至少 {_PASSWORD_MIN} 位")
    if db.query(User).filter(User.username == username).first() is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")
    if email and db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="邮箱已被使用")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        provider="local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _auth_response(user)


@router.post("/login", response_model=UserAuthResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)) -> UserAuthResponse:
    """用户登录：校验存在、密码与启用状态，成功后更新最后登录时间。"""
    user = db.query(User).filter(User.username == payload.username).first()
    if (
        user is None
        or not user.password_hash
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    if not user.enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    user.last_login_at = now()
    db.commit()
    db.refresh(user)
    return _auth_response(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """返回当前登录用户信息。"""
    return user
