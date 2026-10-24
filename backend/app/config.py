# -*- coding: utf-8 -*-
"""全局配置模块。

使用 pydantic-settings 的 BaseSettings，支持通过环境变量 / .env 覆盖默认值。
"""
from ipaddress import ip_address, ip_network
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：backend/app/config.py -> parents[0]=app、[1]=backend、[2]=项目根
_DEFAULT_BASE_DIR = Path(__file__).resolve().parents[2]

# 上传白名单（小写、含点）
_IMAGE_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
_VIDEO_EXTENSIONS: set[str] = {".mp4", ".m4v", ".mov", ".webm", ".ogv"}
_IMAGE_MIME_TYPES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
}
_VIDEO_MIME_TYPES: set[str] = {
    "video/mp4",
    "video/x-m4v",
    "video/quicktime",
    "video/webm",
    "video/ogg",
}


class Settings(BaseSettings):
    """应用配置项。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 路径 ----------
    BASE_DIR: Path = _DEFAULT_BASE_DIR
    DATA_DIR: Path = _DEFAULT_BASE_DIR / "data"
    UPLOAD_DIR: Path = _DEFAULT_BASE_DIR / "data" / "uploads"
    THUMBNAIL_DIR: Path = _DEFAULT_BASE_DIR / "data" / "thumbnails"
    DB_PATH: Path = _DEFAULT_BASE_DIR / "data" / "app.db"

    # ---------- 服务端口 ----------
    HOST: str = "127.0.0.1"
    API_PORT: int = 8080
    FRONTEND_PORT: int = 8000
    ADMIN_PORT: int = 8001

    # ---------- 认证与安全 ----------
    SECRET_KEY: str = "change-me-please-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    # 后台媒体预览签名 / 加密分类解锁令牌有效期（分钟）
    MEDIA_TOKEN_EXPIRE_MINUTES: int = 30
    FOLDER_TOKEN_EXPIRE_MINUTES: int = 120

    # ---------- 默认管理员 ----------
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    # 为 true 时：每次启动都用上面的环境变量覆盖已有管理员的账号与密码；
    # 为 false（默认）时：仅在数据库首次初始化（admins 表为空）时写入。
    ADMIN_FORCE_SYNC: bool = False

    # ---------- 上传限制 ----------
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 图片单文件最大字节数
    MAX_VIDEO_UPLOAD_SIZE: int = 200 * 1024 * 1024  # 视频单文件最大字节数
    ALLOWED_IMAGE_EXTENSIONS: set[str] = set(_IMAGE_EXTENSIONS)
    ALLOWED_VIDEO_EXTENSIONS: set[str] = set(_VIDEO_EXTENSIONS)
    ALLOWED_IMAGE_MIME_TYPES: set[str] = set(_IMAGE_MIME_TYPES)
    ALLOWED_VIDEO_MIME_TYPES: set[str] = set(_VIDEO_MIME_TYPES)
    # 旧配置名，保留为图片白名单以兼容既有引用
    ALLOWED_EXTENSIONS: set[str] = set(_IMAGE_EXTENSIONS)
    ALLOWED_MIME_TYPES: set[str] = set(_IMAGE_MIME_TYPES)
    THUMBNAIL_SIZE: int = 420  # 缩略图最长边像素

    # ---------- 凭证上传限流 ----------
    RATE_LIMIT_MAX_REQUESTS: int = 20
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # ---------- 前台地址（用于生成分享链接） ----------
    FRONTEND_BASE_URL: str = "http://127.0.0.1:8000"

    # ---------- API 对外地址（用于生成 OAuth 回调地址） ----------
    API_BASE_URL: str = "http://127.0.0.1:8080"

    # ---------- 对外访问主机（远程部署/反向代理时设置，如 192.168.1.10 或 gallery.example.com） ----------
    # 设置后：分享链接、OAuth 回调、前端 API 地址与 CORS 均以该主机为准；留空则按默认/请求主机自动推断。
    PUBLIC_HOST: str = ""
    PUBLIC_SCHEME: str = "http"

    # ---------- 额外允许的跨域来源（逗号分隔，如 https://gallery.example.com） ----------
    CORS_ORIGINS: str = ""

    # ---------- 可信反向代理（逗号分隔 IP/CIDR） ----------
    # 仅当直连地址属于该列表时才采信 X-Forwarded-For / X-Forwarded-Proto；
    # 留空表示不信任任何代理，始终使用直连地址。
    TRUSTED_PROXIES: str = ""

    # 是否放行任意来源跨域（默认 true）。
    # 反向代理到 80/443 时 Origin 头不带端口（如 https://gallery.buxin.us.kg），
    # 固定的"主机:端口"白名单无法覆盖；又因本项目鉴权使用 Authorization 头（Bearer）
    # 而非 Cookie，放宽来源不会造成越权。设为 false 时仅放行 cors_origins() 中的显式来源。
    CORS_ALLOW_ALL_ORIGINS: bool = True

    def api_base_url(self) -> str:
        """API 对外基地址：优先 PUBLIC_HOST，其次 API_BASE_URL。"""
        if self.PUBLIC_HOST:
            return f"{self.PUBLIC_SCHEME}://{self.PUBLIC_HOST}:{self.API_PORT}"
        return self.API_BASE_URL.rstrip("/")

    def frontend_base_url(self) -> str:
        """前台对外基地址：优先 PUBLIC_HOST，其次 FRONTEND_BASE_URL。"""
        if self.PUBLIC_HOST:
            return f"{self.PUBLIC_SCHEME}://{self.PUBLIC_HOST}:{self.FRONTEND_PORT}"
        return self.FRONTEND_BASE_URL.rstrip("/")

    def resolve_scheme(self, request=None) -> str:
        """解析请求协议；仅可信代理的 X-Forwarded-Proto 生效。"""
        if request is None:
            return self.PUBLIC_SCHEME or "http"
        scheme = request.url.scheme or "http"
        direct_host = request.client.host if request.client else ""
        if self.is_trusted_proxy(direct_host):
            forwarded = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
            if forwarded in ("http", "https"):
                scheme = forwarded
        return scheme

    def _request_hostname(self, request) -> str:
        """取请求 Host 的主机名（去掉端口）；无请求返回空字符串。"""
        if request is None:
            return ""
        host = request.headers.get("host", "") or ""
        return host.split(":")[0].strip()

    def resolve_api_base(self, request=None) -> str:
        """解析前端应使用的 API 基地址（用于动态生成 config.js）。

        优先级：PUBLIC_HOST -> 请求 Host（保留访问者使用的主机名，端口替换为 API 端口）-> API_BASE_URL。
        这样以服务器 IP 或域名直连时，前端会自动指向正确的 API 地址。
        """
        if self.PUBLIC_HOST:
            return f"{self.PUBLIC_SCHEME}://{self.PUBLIC_HOST}:{self.API_PORT}"
        hostname = self._request_hostname(request)
        if hostname:
            return f"{self.resolve_scheme(request)}://{hostname}:{self.API_PORT}"
        return self.API_BASE_URL.rstrip("/")

    def resolve_frontend_base(self, request=None) -> str:
        """解析前台基地址；优先 PUBLIC_HOST，其次请求 Host + 前台端口。"""
        if self.PUBLIC_HOST:
            return f"{self.PUBLIC_SCHEME}://{self.PUBLIC_HOST}:{self.FRONTEND_PORT}"
        hostname = self._request_hostname(request)
        if hostname:
            return f"{self.resolve_scheme(request)}://{hostname}:{self.FRONTEND_PORT}"
        return self.FRONTEND_BASE_URL.rstrip("/")

    def cors_origins(self) -> list[str]:
        """返回允许跨域访问的显式来源列表（本地回环 + PUBLIC_HOST + 自定义）。"""
        origins = [
            f"http://127.0.0.1:{self.FRONTEND_PORT}",
            f"http://127.0.0.1:{self.ADMIN_PORT}",
            f"http://localhost:{self.FRONTEND_PORT}",
            f"http://localhost:{self.ADMIN_PORT}",
        ]
        if self.PUBLIC_HOST:
            origins.append(f"{self.PUBLIC_SCHEME}://{self.PUBLIC_HOST}:{self.FRONTEND_PORT}")
            origins.append(f"{self.PUBLIC_SCHEME}://{self.PUBLIC_HOST}:{self.ADMIN_PORT}")
        for item in self.CORS_ORIGINS.split(","):
            item = item.strip()
            if item:
                origins.append(item)
        return list(dict.fromkeys(origins))

    def cors_origin_regex(self) -> str:
        """返回放行跨域的正则：默认匹配任意 http/https 来源（含带端口与不带端口）。

        使用正则而非 ``allow_origins=["*"]``，Starlette 会回显具体来源，
        因此与 ``allow_credentials=True`` 兼容。
        """
        if not self.CORS_ALLOW_ALL_ORIGINS:
            return ""
        return r"^https?://[^/]+$"

    def trusted_proxies(self) -> list:
        """解析 TRUSTED_PROXIES 为 ip_network 列表；非法条目忽略。"""
        networks = []
        for item in self.TRUSTED_PROXIES.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                networks.append(ip_network(item, strict=False))
            except ValueError:
                continue
        return networks

    def is_trusted_proxy(self, host: str) -> bool:
        """判断给定地址是否为可信代理；非法 IP 一律视为不可信。"""
        try:
            addr = ip_address((host or "").strip())
        except ValueError:
            return False
        return any(addr.version == net.version and addr in net for net in self.trusted_proxies())

    def ensure_dirs(self) -> None:
        """确保数据目录存在。"""
        for directory in (self.DATA_DIR, self.UPLOAD_DIR, self.THUMBNAIL_DIR):
            directory.mkdir(parents=True, exist_ok=True)


# 全局配置单例
settings = Settings()
