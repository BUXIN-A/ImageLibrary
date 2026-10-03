# -*- coding: utf-8 -*-
"""Pydantic v2 数据模型（请求 / 响应）。"""
from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field

T = TypeVar("T")


# ---------------- 认证 ----------------
class LoginRequest(BaseModel):
    """登录请求。"""

    username: str
    password: str


class TokenResponse(BaseModel):
    """登录成功返回的令牌。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ChangePasswordRequest(BaseModel):
    """修改密码请求。"""

    old_password: str
    new_password: str


class AdminOut(BaseModel):
    """管理员信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


# ---------------- 标签 ----------------
class TagOut(BaseModel):
    """标签信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    image_count: Optional[int] = None


# ---------------- 文件夹 ----------------
class FolderOut(BaseModel):
    """文件夹信息（递归树结构）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: Optional[int] = None
    path: str
    image_count: int = 0
    children: list["FolderOut"] = Field(default_factory=list)


# ---------------- 图片 ----------------
class ImageOut(BaseModel):
    """图片信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    original_name: str
    filename: str
    mime_type: str
    size: int = 0
    width: int = 0
    height: int = 0
    folder_id: Optional[int] = None
    folder_name: Optional[str] = None
    status: str = "approved"
    is_deleted: bool = False
    views: int = 0
    downloads: int = 0
    share_token: Optional[str] = None
    tags: list[TagOut] = Field(default_factory=list)
    exif: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # 内部字段：仅用于生成缩略图 URL，不对外输出
    thumb_name: str = Field(default="", exclude=True)

    @computed_field  # type: ignore[misc]
    @property
    def url(self) -> str:
        """原图访问相对路径。"""
        return f"/media/{self.filename}"

    @computed_field  # type: ignore[misc]
    @property
    def thumb_url(self) -> str:
        """缩略图访问相对路径。"""
        return f"/thumbnails/{self.thumb_name}"


# ---------------- 通用分页 ----------------
class PageResponse(BaseModel, Generic[T]):
    """通用分页响应。"""

    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 0
    pages: int = 0


# 兼容别名
PageOut = PageResponse

# 解析前向引用（FolderOut 自引用）
FolderOut.model_rebuild()


# ---------------- 上传 Token ----------------
class TokenCreate(BaseModel):
    """创建上传 Token 请求。"""

    note: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_uploads: Optional[int] = None
    max_file_size: Optional[int] = None


class TokenUpdate(BaseModel):
    """更新上传 Token 请求（仅更新显式提供的字段）。"""

    note: Optional[str] = None
    enabled: Optional[bool] = None
    expires_at: Optional[datetime] = None
    max_uploads: Optional[int] = None
    max_file_size: Optional[int] = None


class TokenOut(BaseModel):
    """上传 Token 信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str
    note: Optional[str] = None
    enabled: bool = True
    expires_at: Optional[datetime] = None
    max_uploads: Optional[int] = None
    used_uploads: int = 0
    max_file_size: Optional[int] = None
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    # 剩余可上传次数；max_uploads 为 null 表示不限，此时 remaining 为 null
    remaining: Optional[int] = None


# ---------------- 图片批处理 / 导出 ----------------
class ImageUpdate(BaseModel):
    """更新图片信息请求。"""

    title: Optional[str] = None
    description: Optional[str] = None
    folder_id: Optional[int] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


class BatchImagesRequest(BaseModel):
    """后台图片批量操作请求。"""

    ids: list[int] = Field(default_factory=list)
    action: str
    folder_id: Optional[int] = None
    tags: Optional[list[str]] = None
    reason: Optional[str] = None


class ExportRequest(BaseModel):
    """公开批量导出请求。"""

    ids: list[int] = Field(default_factory=list)


class AdminExportRequest(BaseModel):
    """后台导出请求：ids 为空时按筛选条件导出。"""

    ids: Optional[list[int]] = None
    q: Optional[str] = None
    folder_id: Optional[int] = None
    tag: Optional[str] = None
    status: Optional[str] = None
    include_deleted: bool = False


# ---------------- 审核 ----------------
class ReviewBatchRequest(BaseModel):
    """批量审核请求。"""

    ids: list[int] = Field(default_factory=list)
    action: str
    reason: Optional[str] = None


class ReviewRejectRequest(BaseModel):
    """拒绝审核请求。"""

    reason: Optional[str] = None


# ---------------- 站点设置 / 统计 ----------------
class SettingsUpdate(BaseModel):
    """更新站点设置请求。"""

    site_name: Optional[str] = None
    default_theme: Optional[str] = None
    enabled_themes: Optional[list[str]] = None


class StatsOut(BaseModel):
    """后台统计数据。"""

    images_total: int = 0
    pending_total: int = 0
    folders_total: int = 0
    tags_total: int = 0
    recycle_total: int = 0
    tokens_total: int = 0
    views_total: int = 0
    downloads_total: int = 0


# ---------------- 普通用户 ----------------
class UserOut(BaseModel):
    """普通用户信息（不含密码哈希）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    provider: str = "local"
    enabled: bool = True
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class UserRegisterRequest(BaseModel):
    """用户注册请求。"""

    username: str
    password: str
    email: Optional[str] = None


class UserLoginRequest(BaseModel):
    """用户登录请求。"""

    username: str
    password: str


class UserAuthResponse(BaseModel):
    """用户注册/登录成功响应。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserUpdate(BaseModel):
    """管理员更新用户状态请求。"""

    enabled: bool


class ResetPasswordRequest(BaseModel):
    """管理员重置用户密码请求。"""

    new_password: str


# ---------------- 站点设置 ----------------
class SiteUpdate(BaseModel):
    """更新站点设置请求（仅更新显式提供的字段）。"""

    site_name: Optional[str] = None
    site_title: Optional[str] = None
    site_description: Optional[str] = None
    site_keywords: Optional[str] = None
    favicon: Optional[str] = None
    allow_index: Optional[bool] = None
    robots_extra: Optional[str] = None
    sitemap_enabled: Optional[bool] = None
    comments_enabled: Optional[bool] = None
    footer_text: Optional[str] = None
    # 站点地址：留空表示自动推断（PUBLIC_HOST 或访问主机）
    api_base_url: Optional[str] = None
    frontend_base_url: Optional[str] = None


# ---------------- 登录配置 ----------------
class LoginSettingsUpdate(BaseModel):
    """更新登录配置请求。

    secret 字段：缺失或 null 表示不修改，空字符串表示清空，非空表示更新。
    """

    login_local_enabled: Optional[bool] = None
    login_github_enabled: Optional[bool] = None
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    login_oauth2_enabled: Optional[bool] = None
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None
    oauth2_authorize_url: Optional[str] = None
    oauth2_token_url: Optional[str] = None
    oauth2_userinfo_url: Optional[str] = None
    oauth2_scope: Optional[str] = None
    oauth2_user_id_field: Optional[str] = None
    oauth2_username_field: Optional[str] = None
    oauth2_nickname_field: Optional[str] = None
    oauth2_email_field: Optional[str] = None
    oauth2_avatar_field: Optional[str] = None


# ---------------- 评论 ----------------
class CommentCreateRequest(BaseModel):
    """发表评论请求。"""

    content: str


class CommentStatusUpdate(BaseModel):
    """管理端更新评论状态请求。"""

    status: str


class CommentBatchRequest(BaseModel):
    """管理端评论批量操作请求。"""

    ids: list[int] = Field(default_factory=list)
    action: str
