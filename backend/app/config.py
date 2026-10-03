# -*- coding: utf-8 -*-
"""全局配置模块。

使用 pydantic-settings 的 BaseSettings，支持通过环境变量 / .env 覆盖默认值。
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录：backend/app/config.py -> parents[0]=app、[1]=backend、[2]=项目根
_DEFAULT_BASE_DIR = Path(__file__).resolve().parents[2]


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

    # ---------- 默认管理员 ----------
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    # 为 true 时：每次启动都用上面的环境变量覆盖已有管理员的账号与密码；
    # 为 false（默认）时：仅在数据库首次初始化（admins 表为空）时写入。
    ADMIN_FORCE_SYNC: bool = False

    # ---------- 上传限制 ----------
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 单文件最大字节数
    ALLOWED_EXTENSIONS: set[str] = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    ALLOWED_MIME_TYPES: set[str] = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
    }
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

    def resolve_api_base(self, request=None) -> str:
        """解析前端应使用的 API 基地址（用于动态生成 config.js）。

        优先级：PUBLIC_HOST -> 请求 Host（保留访问者使用的主机名，端口替换为 API 端口）-> API_BASE_URL。
        这样以服务器 IP 或域名直连时，前端会自动指向正确的 API 地址。
        """
        if self.PUBLIC_HOST:
            return f"{self.PUBLIC_SCHEME}://{self.PUBLIC_HOST}:{self.API_PORT}"
        if request is not None:
            host = request.headers.get("host", "") or ""
            hostname = host.split(":")[0].strip()
            if hostname:
                scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
                return f"{scheme}://{hostname}:{self.API_PORT}"
        return self.API_BASE_URL.rstrip("/")

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

    def ensure_dirs(self) -> None:
        """确保数据目录存在。"""
        for directory in (self.DATA_DIR, self.UPLOAD_DIR, self.THUMBNAIL_DIR):
            directory.mkdir(parents=True, exist_ok=True)


# 全局配置单例
settings = Settings()
