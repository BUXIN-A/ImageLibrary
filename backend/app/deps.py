# -*- coding: utf-8 -*-
"""FastAPI 依赖：管理员认证、上传 Token 校验、客户端 IP 提取。"""
from datetime import datetime
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Admin, UploadToken, User
from backend.app.security import decode_token

# auto_error=False：无凭证时返回 None，由依赖自行处理 401
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    """校验 Bearer JWT 并返回当前管理员；失败统一返回 401。"""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未授权")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未授权")

    # 旧令牌无 role 字段，默认按管理员处理；显式 role=user 的普通用户令牌一律拒绝
    if payload.get("role", "admin") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未授权")

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未授权")

    admin = db.query(Admin).filter(Admin.username == username).first()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未授权")
    return admin


def _load_user(credentials: Optional[HTTPAuthorizationCredentials], db: Session) -> Optional[User]:
    """从 Bearer 令牌解析普通用户；无效、角色不符、不存在或已禁用时返回 None。"""
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError:
        return None
    if payload.get("role") != "user":
        return None
    username = payload.get("sub")
    if not username:
        return None
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.enabled:
        return None
    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """校验 Bearer 用户令牌并返回当前用户；失败统一返回 401。"""
    user = _load_user(credentials, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未授权")
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """可选登录：无有效用户令牌时返回 None（用于公开接口的可选鉴权）。"""
    return _load_user(credentials, db)


def validate_upload_token(
    token_str: str, db: Session
) -> tuple[Optional[UploadToken], Optional[str]]:
    """校验上传 Token。

    返回 (token 对象, 错误原因)；校验通过时错误原因为 None。
    校验顺序：存在 -> 启用 -> 未过期 -> 未超额。
    """
    if not token_str:
        return None, "Token 不存在"

    token = db.query(UploadToken).filter(UploadToken.token == token_str).first()
    if token is None:
        return None, "Token 不存在"
    if not token.enabled:
        return None, "Token 已禁用"
    if token.expires_at is not None and token.expires_at < datetime.now():
        return None, "Token 已过期"
    if token.max_uploads is not None and token.used_uploads >= token.max_uploads:
        return None, "Token 上传次数已用尽"
    return token, None


def client_ip(request: Request) -> str:
    """获取客户端 IP，优先取 X-Forwarded-For 首段。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else ""
