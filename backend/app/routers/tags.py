# -*- coding: utf-8 -*-
"""标签路由：公开标签列表 + 管理端创建/删除。"""
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.models import Image, ImageTag, Tag
from backend.app.schemas import TagOut

router = APIRouter(prefix="/api", tags=["tags"])
admin_router = APIRouter(
    prefix="/api/admin/tags",
    tags=["admin-tags"],
    dependencies=[Depends(get_current_admin)],
)


class TagCreate(BaseModel):
    """创建标签请求。"""

    name: str


@router.get("/tags", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db)) -> list[TagOut]:
    """公开标签列表，image_count 为已公开未删除图片数。"""
    counts = dict(
        db.query(ImageTag.tag_id, func.count(Image.id))
        .join(Image, Image.id == ImageTag.image_id)
        .filter(Image.status == "approved", Image.is_deleted.is_(False))
        .group_by(ImageTag.tag_id)
        .all()
    )
    tags = db.query(Tag).order_by(Tag.name).all()
    return [
        TagOut(id=tag.id, name=tag.name, image_count=counts.get(tag.id, 0))
        for tag in tags
    ]


@admin_router.post("", response_model=TagOut)
def create_tag(payload: TagCreate = Body(...), db: Session = Depends(get_db)) -> TagOut:
    """创建标签（同名则返回已存在的标签）。"""
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="标签名不能为空")
    tag = db.query(Tag).filter(Tag.name == name).first()
    if tag is None:
        tag = Tag(name=name)
        db.add(tag)
        db.commit()
        db.refresh(tag)
    return TagOut(id=tag.id, name=tag.name, image_count=0)


@admin_router.delete("/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)) -> dict:
    """删除标签（图片关联随外键级联删除）。"""
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    db.delete(tag)
    db.commit()
    return {"ok": True}
