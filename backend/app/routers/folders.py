# -*- coding: utf-8 -*-
"""分类路由：公开一级分类列表 / 汇总 / 解锁 + 管理端增删改（分类密码）。"""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.deps import client_ip, get_current_admin
from backend.app.media_service import create_folder_token, parse_folder_token
from backend.app.models import Folder, Image
from backend.app.ratelimit import folder_unlock_limiter
from backend.app.schemas import FolderOut
from backend.app.security import hash_password, verify_password

router = APIRouter(prefix="/api", tags=["folders"])
admin_router = APIRouter(
    prefix="/api/admin/folders",
    tags=["admin-folders"],
    dependencies=[Depends(get_current_admin)],
)


# ---------------- 请求模型 ----------------
class FolderCreate(BaseModel):
    """新建分类请求：仅名称与可选访问密码。"""

    name: str
    password: Optional[str] = None


class FolderUpdate(BaseModel):
    """更新分类请求（仅更新显式提供的字段）。"""

    name: Optional[str] = None
    sort_order: Optional[int] = None
    password: Optional[str] = None


class FolderUnlockRequest(BaseModel):
    """分类解锁请求。"""

    password: str


# ---------------- 公共辅助 ----------------
def _folder_out(folder: Folder, image_count: Optional[int] = 0) -> FolderOut:
    """构造一级分类响应（不暴露 password_hash）。

    加密分类在未解锁时不返回图片数量（``image_count=None``），避免泄露受保护内容规模。
    """
    return FolderOut(
        id=folder.id,
        name=folder.name,
        parent_id=None,
        path=f"/{folder.id}/",
        sort_order=folder.sort_order or 0,
        image_count=image_count,
        has_password=bool(folder.password_hash),
        children=[],
    )


def _image_counts(db: Session) -> dict[int, int]:
    """统计各分类下「已公开且未删除」的图片数。"""
    return dict(
        db.query(Image.folder_id, func.count(Image.id))
        .filter(
            Image.status == "approved",
            Image.is_deleted.is_(False),
            Image.folder_id.isnot(None),
        )
        .group_by(Image.folder_id)
        .all()
    )


def _locked_folder_ids():
    """设置了访问密码的分类 id 子查询。"""
    return select(Folder.id).where(Folder.password_hash.isnot(None))


# ---------------- 公开接口 ----------------
@router.get("/folders", response_model=list[FolderOut])
def list_folders(
    folder_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[FolderOut]:
    """返回扁平分类列表。

    ``image_count`` 为该分类下已公开未删除图片数；加密分类仅在提供有效
    ``folder_token`` 时返回数量，否则为 ``None``（前端显示为「—」）。
    """
    folders = db.query(Folder).order_by(Folder.sort_order, Folder.name).all()
    counts = _image_counts(db)
    unlocked = parse_folder_token(folder_token, db)
    unlocked_id = unlocked.id if unlocked is not None else None
    result: list[FolderOut] = []
    for folder in folders:
        count: Optional[int] = counts.get(folder.id, 0)
        if folder.password_hash and folder.id != unlocked_id:
            count = None
        result.append(_folder_out(folder, count))
    return result


@router.get("/folders/summary")
def folder_summary(db: Session = Depends(get_db)) -> dict:
    """分类汇总：公开图片总数、未分类数、分类总数与加密分类数。"""
    locked_ids = _locked_folder_ids()
    public_filter = (Image.status == "approved", Image.is_deleted.is_(False))

    all_count = (
        db.query(func.count(Image.id))
        .filter(
            *public_filter,
            or_(Image.folder_id.is_(None), Image.folder_id.notin_(locked_ids)),
        )
        .scalar()
        or 0
    )
    uncategorized_count = (
        db.query(func.count(Image.id))
        .filter(*public_filter, Image.folder_id.is_(None))
        .scalar()
        or 0
    )
    folder_count = db.query(func.count(Folder.id)).scalar() or 0
    locked_count = (
        db.query(func.count(Folder.id))
        .filter(Folder.password_hash.isnot(None))
        .scalar()
        or 0
    )
    return {
        "all_count": int(all_count),
        "uncategorized_count": int(uncategorized_count),
        "folder_count": int(folder_count),
        "locked_count": int(locked_count),
    }


@router.post("/folders/{folder_id}/unlock")
def unlock_folder(
    folder_id: int,
    request: Request,
    payload: FolderUnlockRequest = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    """校验分类密码并签发限时解锁令牌。"""
    key = f"{client_ip(request)}:{folder_id}"
    if not folder_unlock_limiter.allow(key):
        raise HTTPException(status_code=429, detail="尝试过于频繁，请稍后再试")

    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="分类不存在")
    if not folder.password_hash:
        raise HTTPException(status_code=400, detail="该分类未设置密码")
    if not verify_password(payload.password, folder.password_hash):
        raise HTTPException(status_code=401, detail="密码错误")

    return {
        "token": create_folder_token(folder),
        "expires_in": settings.FOLDER_TOKEN_EXPIRE_MINUTES * 60,
        "folder": {
            "id": folder.id,
            "name": folder.name,
            "has_password": True,
        },
    }


# ---------------- 管理端接口 ----------------
@admin_router.post("", response_model=FolderOut)
def create_folder(
    payload: FolderCreate = Body(...), db: Session = Depends(get_db)
) -> FolderOut:
    """新建一级分类；可选设置访问密码。"""
    folder = Folder(name=payload.name, parent_id=None, path="/")
    if payload.password:
        folder.password_hash = hash_password(payload.password)
        folder.auth_version = 1
    db.add(folder)
    db.flush()
    folder.path = f"/{folder.id}/"
    db.commit()
    db.refresh(folder)
    return _folder_out(folder)


@admin_router.patch("/{folder_id}", response_model=FolderOut)
def update_folder(
    folder_id: int,
    payload: FolderUpdate = Body(...),
    db: Session = Depends(get_db),
) -> FolderOut:
    """更新分类名称 / 排序 / 密码。

    ``password`` 未提供时不修改；空字符串表示清除密码；非空表示设置新密码。
    密码发生任何变化都会递增 ``auth_version``，使旧解锁令牌立即失效。
    """
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="分类不存在")

    data = payload.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        folder.name = data["name"]
    if data.get("sort_order") is not None:
        folder.sort_order = data["sort_order"]

    if "password" in data:
        new_password = data["password"]
        if new_password is None:
            pass
        elif new_password == "":
            if folder.password_hash:
                folder.password_hash = None
                folder.auth_version = int(folder.auth_version or 0) + 1
        else:
            folder.password_hash = hash_password(new_password)
            folder.auth_version = int(folder.auth_version or 0) + 1

    db.commit()
    db.refresh(folder)
    # 仅统计当前分类下的公开图片数，避免全表分组统计
    image_count = (
        db.query(func.count(Image.id))
        .filter(
            Image.folder_id == folder.id,
            Image.status == "approved",
            Image.is_deleted.is_(False),
        )
        .scalar()
        or 0
    )
    return _folder_out(folder, int(image_count))


@admin_router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict:
    """删除分类：该分类图片变为未分类，分类本身删除。

    加密分类默认拒绝删除：图片转为未分类后会绕过密码保护变为公开，
    必须显式传 ``force=true`` 确认。
    """
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="分类不存在")

    if folder.password_hash and not force:
        raise HTTPException(
            status_code=400,
            detail="该分类已加密：删除后其图片将变为未分类并公开，请确认后使用强制删除",
        )

    db.query(Image).filter(Image.folder_id == folder.id).update(
        {Image.folder_id: None}, synchronize_session=False
    )
    # 兼容历史多级数据：解除子分类对当前分类的外键引用，避免删除失败
    db.query(Folder).filter(Folder.parent_id == folder.id).update(
        {Folder.parent_id: None}, synchronize_session=False
    )

    db.delete(folder)
    db.commit()
    return {"ok": True}
