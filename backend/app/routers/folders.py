# -*- coding: utf-8 -*-
"""文件夹路由：公开树形浏览 + 管理端增删改（物化路径维护）。"""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import get_current_admin
from backend.app.models import Folder, Image
from backend.app.schemas import FolderOut

router = APIRouter(prefix="/api", tags=["folders"])
admin_router = APIRouter(
    prefix="/api/admin/folders",
    tags=["admin-folders"],
    dependencies=[Depends(get_current_admin)],
)


# ---------------- 请求模型 ----------------
class FolderCreate(BaseModel):
    """创建文件夹请求。"""

    name: str
    parent_id: Optional[int] = None


class FolderUpdate(BaseModel):
    """更新文件夹请求（仅更新显式提供的字段）。"""

    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


# ---------------- 公共辅助 ----------------
def _path_for(db: Session, folder_id: int, parent_id: Optional[int]) -> str:
    """根据父节点计算物化路径：父为空 -> "/{id}/"，否则 parent.path + "{id}/"。"""
    if parent_id is None:
        return f"/{folder_id}/"
    parent = db.get(Folder, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="父文件夹不存在")
    return f"{parent.path}{folder_id}/"


@router.get("/folders", response_model=list[FolderOut])
def list_folders(db: Session = Depends(get_db)) -> list[FolderOut]:
    """返回文件夹树，image_count 为该文件夹直属已公开未删除图片数。"""
    folders = db.query(Folder).order_by(Folder.sort_order, Folder.name).all()
    counts = dict(
        db.query(Image.folder_id, func.count(Image.id))
        .filter(
            Image.status == "approved",
            Image.is_deleted.is_(False),
            Image.folder_id.isnot(None),
        )
        .group_by(Image.folder_id)
        .all()
    )

    nodes: dict[int, FolderOut] = {
        folder.id: FolderOut(
            id=folder.id,
            name=folder.name,
            parent_id=folder.parent_id,
            path=folder.path,
            image_count=counts.get(folder.id, 0),
            children=[],
        )
        for folder in folders
    }

    roots: list[FolderOut] = []
    for folder in folders:
        node = nodes[folder.id]
        if folder.parent_id is not None and folder.parent_id in nodes:
            nodes[folder.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@admin_router.post("", response_model=FolderOut)
def create_folder(
    payload: FolderCreate = Body(...), db: Session = Depends(get_db)
) -> FolderOut:
    """新建文件夹（先插入取 id，再按父节点计算 path）。"""
    folder = Folder(name=payload.name, parent_id=payload.parent_id, path="/")
    db.add(folder)
    db.flush()
    folder.path = _path_for(db, folder.id, folder.parent_id)
    db.commit()
    db.refresh(folder)
    return FolderOut(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        path=folder.path,
        image_count=0,
        children=[],
    )


@admin_router.patch("/{folder_id}", response_model=FolderOut)
def update_folder(
    folder_id: int,
    payload: FolderUpdate = Body(...),
    db: Session = Depends(get_db),
) -> FolderOut:
    """更新文件夹；改变父节点时重算自身与全部后代的物化路径。"""
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="文件夹不存在")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        folder.name = data["name"]
    if "sort_order" in data and data["sort_order"] is not None:
        folder.sort_order = data["sort_order"]

    if "parent_id" in data:
        new_parent_id = data["parent_id"]
        old_path = folder.path
        new_path = _path_for(db, folder.id, new_parent_id)
        # 不允许移动到自身或其子孙下（新父节点路径以旧路径为前缀即为其后代或自身）
        if new_parent_id is not None and new_path != old_path:
            parent = db.get(Folder, new_parent_id)
            if parent is not None and parent.path.startswith(old_path):
                raise HTTPException(status_code=400, detail="不能移动到自身或其子文件夹下")
        if new_path != old_path:
            # 先按旧前缀替换全部后代路径
            descendants = (
                db.query(Folder)
                .filter(Folder.path.like(f"{old_path}%"), Folder.id != folder.id)
                .all()
            )
            for descendant in descendants:
                descendant.path = f"{new_path}{descendant.path[len(old_path):]}"
            folder.parent_id = new_parent_id
            folder.path = new_path

    db.commit()
    db.refresh(folder)
    return FolderOut(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        path=folder.path,
        image_count=0,
        children=[],
    )


@admin_router.delete("/{folder_id}")
def delete_folder(folder_id: int, db: Session = Depends(get_db)) -> dict:
    """删除文件夹：图片归入父文件夹，子文件夹上移到父节点，并重算受影响路径。"""
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="文件夹不存在")

    parent = db.get(Folder, folder.parent_id) if folder.parent_id else None
    new_base = parent.path if parent is not None else "/"

    # 图片归入父文件夹（顶层则未分类）
    db.query(Image).filter(Image.folder_id == folder.id).update(
        {Image.folder_id: folder.parent_id}
    )

    # 子文件夹上移一层并重算自身及后代路径
    children = db.query(Folder).filter(Folder.parent_id == folder.id).all()
    for child in children:
        old_child_path = child.path
        child_new_path = f"{new_base}{child.id}/"
        descendants = (
            db.query(Folder)
            .filter(Folder.path.like(f"{old_child_path}%"), Folder.id != child.id)
            .all()
        )
        for descendant in descendants:
            descendant.path = f"{child_new_path}{descendant.path[len(old_child_path):]}"
        child.parent_id = folder.parent_id
        child.path = child_new_path

    db.delete(folder)
    db.commit()
    return {"ok": True}
