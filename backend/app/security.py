# -*- coding: utf-8 -*-
"""安全工具：密码哈希、JWT 签发/解码、随机 Token 生成。"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from backend.app.config import settings

# bcrypt 仅使用密码的前 72 字节
_BCRYPT_MAX_BYTES = 72


def _encode_password(password: str) -> bytes:
    """将密码编码为 UTF-8，并截断到 72 字节以内。"""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """使用 bcrypt 生成密码哈希（返回 utf-8 字符串）。"""
    hashed = bcrypt.hashpw(_encode_password(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(_encode_password(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    role: str = "admin",
    expires_minutes: Optional[int] = None,
) -> str:
    """签发 JWT，payload 含 sub、role 与 exp。"""
    minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并校验 JWT；失败时抛出 pyjwt 异常，交由调用方捕获。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def generate_token(nbytes: int = 32) -> str:
    """生成随机十六进制 Token（默认 32 字节 -> 64 字符）。"""
    return secrets.token_hex(nbytes)
