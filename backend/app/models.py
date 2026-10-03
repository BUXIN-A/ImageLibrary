# -*- coding: utf-8 -*-
"""SQLAlchemy ORM 模型定义（SQLAlchemy 2.x 风格：Mapped + mapped_column）。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


def now() -> datetime:
    """返回当前本地时间（统一使用朴素 datetime）。"""
    return datetime.now()


class Admin(Base):
    """管理员账号（单管理员）。"""

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class UploadToken(Base):
    """上传令牌：用于授权其他用户上传图片。"""

    __tablename__ = "upload_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 32 字节 hex 字符串（64 字符）
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    max_uploads: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    used_uploads: Mapped[int] = mapped_column(Integer, default=0)
    max_file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Folder(Base):
    """多级分类文件夹（自引用树结构，使用物化路径 path 如 "/1/5/"）。"""

    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("folders.id"), nullable=True)
    path: Mapped[str] = mapped_column(String(512), default="/")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    # 自引用关系：不使用级联删除，删除文件夹时由业务层处理子节点与图片归属
    parent: Mapped[Optional["Folder"]] = relationship(
        "Folder", remote_side="Folder.id", back_populates="children"
    )
    children: Mapped[list["Folder"]] = relationship("Folder", back_populates="parent")


class Tag(Base):
    """标签。"""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ImageTag(Base):
    """图片与标签的多对多关联表。"""

    __tablename__ = "image_tags"

    image_id: Mapped[int] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class Image(Base):
    """图片元数据。"""

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    thumb_name: Mapped[str] = mapped_column(String(255), default="")
    folder_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("folders.id", ondelete="SET NULL"), nullable=True
    )
    # pending / approved / rejected
    status: Mapped[str] = mapped_column(String(16), default="approved", index=True)
    reject_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    share_token: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    exif: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("upload_tokens.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    # 关系
    tags: Mapped[list["Tag"]] = relationship(secondary="image_tags", lazy="selectin")
    folder: Mapped[Optional["Folder"]] = relationship("Folder")
    uploaded_token: Mapped[Optional["UploadToken"]] = relationship("UploadToken")

    @property
    def folder_name(self) -> Optional[str]:
        """所属文件夹名称（供序列化使用）。"""
        return self.folder.name if self.folder is not None else None


class Setting(Base):
    """站点设置键值对（value 统一以字符串存储，JSON 值存其字符串形式）。"""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class User(Base):
    """普通用户账号（支持本地账号与第三方 OAuth 登录）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    # OAuth 用户可能没有本地密码，故可空
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="local")
    provider_uid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 关系：用户删除时其评论随之删除（数据库层由 ondelete 级联）
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="user", cascade="all, delete-orphan"
    )


class Notification(Base):
    """后台通知 / 服务日志。

    记录服务启动、站点地址检测与变更、服务端错误、管理员登录、用户访问等事件，
    供后台「通知」界面查看。
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    # info / warning / error
    level: Mapped[str] = mapped_column(String(16), default="info", index=True)
    # startup / site / error / login / visit
    category: Mapped[str] = mapped_column(String(32), default="startup", index=True)
    message: Mapped[str] = mapped_column(String(500))
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class Comment(Base):
    """图片评论。"""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    # visible / hidden
    status: Mapped[str] = mapped_column(String(16), default="visible", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="comments")
    image: Mapped["Image"] = relationship("Image")

    @property
    def thumb_url(self) -> str:
        """所属图片的缩略图访问相对路径（供管理端序列化使用）。"""
        if self.image is None:
            return ""
        return f"/thumbnails/{self.image.thumb_name}"
