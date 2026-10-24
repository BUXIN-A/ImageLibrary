# -*- coding: utf-8 -*-
"""媒体访问授权：后台预览签名令牌与加密分类解锁令牌。

统一在媒体路由中调用 :func:`authorize_media`，避免各处重复实现授权规则。
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import Folder, Image
from backend.app.schemas import AdminImageOut
from backend.app.security import get_secret_key

MEDIA_SCOPE = "media_admin"
FOLDER_SCOPE = "folder"


def _encode(payload: dict) -> str:
    """使用应用密钥签发 JWT。"""
    return jwt.encode(payload, get_secret_key(), algorithm=settings.JWT_ALGORITHM)


def _decode(token: Optional[str]) -> Optional[dict]:
    """解码 JWT；签名错误、过期或格式非法时返回 None（不抛异常）。"""
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            get_secret_key(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp"]},
        )
    except jwt.PyJWTError:
        return None
    return payload if isinstance(payload, dict) else None


def _as_int(value) -> Optional[int]:
    """把令牌中的 id/版本字段安全地转为整数。"""
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def create_admin_media_token(image_id: int, minutes: Optional[int] = None) -> str:
    """为后台预览签发短时媒体令牌（scope=media_admin，绑定图片 id）。"""
    ttl = (
        minutes
        if minutes is not None
        else settings.MEDIA_TOKEN_EXPIRE_MINUTES
    )
    now = datetime.now(timezone.utc)
    return _encode(
        {
            "scope": MEDIA_SCOPE,
            "img": int(image_id),
            "iat": now,
            "exp": now + timedelta(minutes=ttl),
        }
    )


def decode_media_token(token: Optional[str]) -> Optional[dict]:
    """校验后台媒体令牌；失败时返回 None。"""
    payload = _decode(token)
    if payload is None or payload.get("scope") != MEDIA_SCOPE:
        return None
    image_id = _as_int(payload.get("img"))
    if image_id is None:
        return None
    return {**payload, "img": image_id}


def create_folder_token(folder: Folder, minutes: Optional[int] = None) -> str:
    """为加密分类签发限时解锁令牌（scope=folder，绑定分类 id 与 auth_version）。"""
    ttl = (
        minutes
        if minutes is not None
        else settings.FOLDER_TOKEN_EXPIRE_MINUTES
    )
    now = datetime.now(timezone.utc)
    return _encode(
        {
            "scope": FOLDER_SCOPE,
            "fid": int(folder.id),
            "ver": int(folder.auth_version or 0),
            "iat": now,
            "exp": now + timedelta(minutes=ttl),
        }
    )


def _decode_folder_token(token: Optional[str]) -> Optional[dict]:
    """解码分类解锁令牌并校验 scope；失败返回 None。"""
    payload = _decode(token)
    if payload is None or payload.get("scope") != FOLDER_SCOPE:
        return None
    folder_id = _as_int(payload.get("fid"))
    version = _as_int(payload.get("ver"))
    if folder_id is None or version is None:
        return None
    return {**payload, "fid": folder_id, "ver": version}


def parse_folder_token(token: Optional[str], db: Session) -> Optional[Folder]:
    """校验分类解锁令牌：分类存在且 auth_version 匹配时返回该分类。"""
    payload = _decode_folder_token(token)
    if payload is None:
        return None
    folder = db.get(Folder, payload["fid"])
    if folder is None:
        return None
    if int(folder.auth_version or 0) != payload["ver"]:
        return None
    return folder


def image_folder_locked(image: Image) -> bool:
    """判断图片是否属于设置了访问密码的分类。"""
    folder = image.folder
    return bool(folder is not None and folder.password_hash)


def _folder_token_matches(folder: Folder, folder_token: Optional[str]) -> bool:
    """校验分类令牌是否对指定分类有效（id 与 auth_version 均匹配）。"""
    payload = _decode_folder_token(folder_token)
    if payload is None:
        return False
    return (
        payload["fid"] == folder.id
        and payload["ver"] == int(folder.auth_version or 0)
    )


def authorize_media(
    image: Image,
    access_token: Optional[str] = None,
    folder_token: Optional[str] = None,
) -> bool:
    """判断当前请求是否有权读取该图片的原图/缩略图。

    规则：
    1. 有效的后台媒体令牌且绑定同一图片 → 允许（任何状态，含回收站）。
    2. 否则图片必须为「已通过且未删除」。
    3. 所属分类设置了密码时，还需提供该分类的有效解锁令牌。
    """
    payload = decode_media_token(access_token)
    if payload is not None and payload["img"] == image.id:
        return True

    if image.status != "approved" or image.is_deleted:
        return False

    folder = image.folder
    if folder is not None and folder.password_hash:
        if not _folder_token_matches(folder, folder_token):
            return False
    return True


def admin_image_out(image: Image) -> AdminImageOut:
    """构造附带短时媒体令牌的后台图片响应。"""
    out = AdminImageOut.model_validate(image)
    out.media_token = create_admin_media_token(image.id)
    return out
