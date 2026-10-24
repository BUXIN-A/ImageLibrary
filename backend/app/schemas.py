# -*- coding: utf-8 -*-
"""Pydantic v2 数据模型（请求 / 响应）。"""
from datetime import datetime
from typing import Generic, Literal, Optional, TypeVar

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


# ---------------- 文件夹 / 分类 ----------------
class FolderOut(BaseModel):
    """一级分类信息。

    为兼容旧前端保留 ``parent_id`` / ``path`` / ``children`` 字段：
    ``parent_id`` 恒为 None，``path`` 恒为 ``/{id}/``，``children`` 恒为空。
    响应中不包含分类密码哈希，仅以 ``has_password`` 表示是否加密。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: Optional[int] = None
    path: str
    sort_order: int = 0
    # 加密分类在未解锁时为 None（不泄露受保护内容规模）
    image_count: Optional[int] = None
    has_password: bool = False
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
        """缩略图访问相对路径；视频无缩略图时返回空字符串。"""
        if not self.thumb_name:
            return ""
        return f"/thumbnails/{self.thumb_name}"

    @computed_field  # type: ignore[misc]
    @property
    def is_video(self) -> bool:
        """是否为视频媒体（按 MIME 前缀判断）。"""
        return (self.mime_type or "").startswith("video/")

    @computed_field  # type: ignore[misc]
    @property
    def media_type(self) -> str:
        """媒体类型：``video`` 或 ``image``。"""
        return "video" if self.is_video else "image"


class PublicImageOut(BaseModel):
    """公开接口图片信息。

    不包含 ``original_name``、``filename``、``share_token``、``is_deleted``、
    ``reject_reason`` 等内部字段；``filename`` / ``thumb_name`` 仅作为内部字段
    用于生成访问 URL，不会出现在响应中。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    mime_type: str
    size: int = 0
    width: int = 0
    height: int = 0
    folder_id: Optional[int] = None
    folder_name: Optional[str] = None
    views: int = 0
    downloads: int = 0
    tags: list[TagOut] = Field(default_factory=list)
    exif: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 所属分类是否设置了访问密码（由路由填充）
    folder_locked: bool = False

    # 内部字段：仅用于生成媒体 URL，不对外输出
    filename: str = Field(default="", exclude=True)
    thumb_name: str = Field(default="", exclude=True)

    @computed_field  # type: ignore[misc]
    @property
    def url(self) -> str:
        """原图访问相对路径。"""
        return f"/media/{self.filename}"

    @computed_field  # type: ignore[misc]
    @property
    def thumb_url(self) -> str:
        """缩略图访问相对路径；视频无缩略图时返回空字符串。"""
        if not self.thumb_name:
            return ""
        return f"/thumbnails/{self.thumb_name}"

    @computed_field  # type: ignore[misc]
    @property
    def is_video(self) -> bool:
        """是否为视频媒体（按 MIME 前缀判断）。"""
        return (self.mime_type or "").startswith("video/")

    @computed_field  # type: ignore[misc]
    @property
    def media_type(self) -> str:
        """媒体类型：``video`` 或 ``image``。"""
        return "video" if self.is_video else "image"


class AdminImageOut(ImageOut):
    """后台图片信息：在公开字段之外附带短时媒体签名令牌。"""

    media_token: Optional[str] = None


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
    status: Optional[Literal["pending", "approved", "rejected"]] = None


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
    """更新站点设置请求（主题配置已迁移至主题设置接口）。

    只允许显式声明过的字段，未知字段直接返回 422，避免「保存成功但未生效」。
    """

    model_config = ConfigDict(extra="forbid")

    site_name: Optional[str] = None


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


class OAuthExchangeRequest(BaseModel):
    """OAuth 一次性登录码换取令牌请求。"""

    code: str


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
    # 通知 / 服务日志开关
    site_check_on_startup: Optional[bool] = None
    visit_log_enabled: Optional[bool] = None
    # 注意：站点地址（api_base_url / frontend_base_url / admin_api_base_url）
    # 只能通过 POST /api/admin/site/address（需管理员账号密码二次校验）修改，
    # 不能经由本模型写入。


class SiteAddressUpdate(BaseModel):
    """设置/清除站点地址请求（需二次校验管理员账号密码）。

    ``targets`` 取值：``api``（API 站点地址）、``admin``（后台专属 API 地址）、
    ``frontend``（前台站点地址）；``base_url`` 为空表示清除所选目标（恢复自动推断）。
    """

    targets: list[str] = []
    base_url: Optional[str] = None
    username: str
    password: str


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


# ---------------- 后台通知 ----------------
class NotificationReadRequest(BaseModel):
    """标记通知为已读请求：ids 非空时按 id 标记，all 为真时全部标记。"""

    ids: list[int] = Field(default_factory=list)
    all: bool = False


class NotificationBatchRequest(BaseModel):
    """通知批量删除请求。"""

    ids: list[int] = Field(default_factory=list)


class NotificationClearRequest(BaseModel):
    """清空通知请求：only_read 为真时仅清空已读通知。"""

    only_read: bool = False
