# -*- coding: utf-8 -*-
"""上传 Token 管理路由（仅管理员）。"""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.models import UploadToken
from backend.app.schemas import TokenCreate, TokenOut, TokenUpdate
from backend.app.security import generate_token

router = APIRouter(
    prefix="/api/admin/tokens",
    tags=["admin-tokens"],
    dependencies=[Depends(get_current_admin)],
)


def _serialize(token: UploadToken) -> TokenOut:
    """把 ORM Token 转为输出模型并计算剩余次数。"""
    out = TokenOut.model_validate(token)
    out.remaining = (
        None
        if token.max_uploads is None
        else max(token.max_uploads - token.used_uploads, 0)
    )
    return out


@router.get("", response_model=list[TokenOut])
def list_tokens(db: Session = Depends(get_db)) -> list[TokenOut]:
    """列出全部上传 Token（按创建时间倒序）。"""
    tokens = db.query(UploadToken).order_by(UploadToken.id.desc()).all()
    return [_serialize(token) for token in tokens]


@router.post("", response_model=TokenOut)
def create_token(
    payload: TokenCreate = Body(...), db: Session = Depends(get_db)
) -> TokenOut:
    """创建上传 Token（24 字节随机 hex）。"""
    token = UploadToken(
        token=generate_token(24),
        note=payload.note,
        expires_at=payload.expires_at,
        max_uploads=payload.max_uploads,
        max_file_size=payload.max_file_size,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return _serialize(token)


@router.patch("/{token_id}", response_model=TokenOut)
def update_token(
    token_id: int,
    payload: TokenUpdate = Body(...),
    db: Session = Depends(get_db),
) -> TokenOut:
    """更新上传 Token（仅更新显式提供的字段）。"""
    token = db.get(UploadToken, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token 不存在")
    data = payload.model_dump(exclude_unset=True)
    for field in ("note", "enabled", "expires_at", "max_uploads", "max_file_size"):
        if field in data:
            setattr(token, field, data[field])
    db.commit()
    db.refresh(token)
    return _serialize(token)


@router.delete("/{token_id}")
def delete_token(token_id: int, db: Session = Depends(get_db)) -> dict:
    """删除上传 Token。"""
    token = db.get(UploadToken, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token 不存在")
    db.delete(token)
    db.commit()
    return {"ok": True}


@router.post("/{token_id}/regenerate", response_model=TokenOut)
def regenerate_token(token_id: int, db: Session = Depends(get_db)) -> TokenOut:
    """重新生成 Token 值（其余配置不变）。"""
    token = db.get(UploadToken, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token 不存在")
    token.token = generate_token(24)
    db.commit()
    db.refresh(token)
    return _serialize(token)
