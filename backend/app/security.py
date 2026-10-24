# -*- coding: utf-8 -*-
"""安全工具：密码哈希、JWT 签发/解码、随机 Token 生成、签名密钥管理。"""
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt

from backend.app.config import settings

# bcrypt 仅使用密码的前 72 字节
_BCRYPT_MAX_BYTES = 72
# 签名密钥最小字节数（HS256 建议 >= 32 字节）
_SECRET_KEY_MIN_BYTES = 32
# 已知的示例/弱密钥（命中时自动替换为随机密钥）
_INSECURE_SECRET_KEYS = {
    "change-me-please-in-production",
    "change-me-to-a-long-random-string",
    "change-me",
    "secret",
    "changeme",
}
# 进程内缓存的生效密钥与「是否为自动生成」标记
_effective_secret_key: Optional[str] = None
_secret_key_generated = False


def _secret_key_file() -> Path:
    """自动生成密钥的持久化路径：``<DATA_DIR>/.secret_key``。"""
    return settings.DATA_DIR / ".secret_key"


def get_secret_key() -> str:
    """返回实际用于签名的密钥。

    - 环境变量 / .env 中配置了足够长的强密钥时直接使用；
    - 留空或仍为示例值时，生成随机密钥并持久化到 ``data/.secret_key``
      （重启后复用，避免每次重启都让所有登录令牌失效）。
    """
    global _effective_secret_key, _secret_key_generated
    if _effective_secret_key:
        return _effective_secret_key

    configured = (settings.SECRET_KEY or "").strip()
    if (
        configured
        and configured.lower() not in _INSECURE_SECRET_KEYS
        and len(configured.encode("utf-8")) >= _SECRET_KEY_MIN_BYTES
    ):
        _effective_secret_key = configured
        return configured

    path = _secret_key_file()
    try:
        existing = path.read_text(encoding="utf-8").strip()
    except OSError:
        existing = ""
    if existing and len(existing.encode("utf-8")) >= _SECRET_KEY_MIN_BYTES:
        _effective_secret_key = existing
        return existing

    generated = secrets.token_urlsafe(48)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generated + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError:
        # 无法持久化时仍使用本次随机值，至少不会退回公开的默认密钥
        pass
    _effective_secret_key = generated
    _secret_key_generated = True
    return generated


def secret_key_was_generated() -> bool:
    """本次启动是否自动生成了签名密钥（供启动日志提示）。"""
    get_secret_key()
    return _secret_key_generated


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
    return jwt.encode(payload, get_secret_key(), algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并校验 JWT；失败时抛出 pyjwt 异常，交由调用方捕获。"""
    return jwt.decode(token, get_secret_key(), algorithms=[settings.JWT_ALGORITHM])


def generate_token(nbytes: int = 32) -> str:
    """生成随机十六进制 Token（默认 32 字节 -> 64 字符）。"""
    return secrets.token_hex(nbytes)
