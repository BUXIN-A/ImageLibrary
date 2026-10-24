# -*- coding: utf-8 -*-
"""通用静态站点 ASGI 应用工厂（可自动生成 config.js，并为前台挂载动态 ROBOTS/SITEMAP/FAVICON 路由）。"""
import json
import time
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import Receive, Scope, Send

from backend.app import theme_settings_service as theme_service
from backend.app.database import SessionLocal, get_db
from backend.app.models import Folder, Image
from backend.app.routers.site import favicon_file_path
from backend.app.seed import get_bool_setting, get_setting
from backend.app.site_config import (
    effective_admin_api_base,
    effective_api_base,
    effective_frontend_base,
)

# 前台 active_theme 缓存有效期（秒），避免每个静态请求都查询数据库
_ACTIVE_THEME_TTL = 3.0
_active_theme_cache: dict[str, object] = {"theme": "", "expires": 0.0}


def invalidate_active_theme_cache() -> None:
    """清理 active_theme 缓存（切换主题后立即生效）。"""
    _active_theme_cache["theme"] = ""
    _active_theme_cache["expires"] = 0.0


def _load_active_theme() -> str:
    """从数据库读取启用主题；异常或非法值回退 base。"""
    db: Session = SessionLocal()
    try:
        return theme_service.get_active_theme(db)
    except Exception:  # noqa: BLE001 - 静态服务不因数据库异常中断
        return "base"
    finally:
        db.close()


def _active_theme() -> str:
    """带短 TTL 缓存的 active_theme 读取。"""
    now = time.monotonic()
    cached = str(_active_theme_cache.get("theme") or "")
    if cached in theme_service.THEME_IDS and now < float(_active_theme_cache["expires"]):
        return cached

    theme = _load_active_theme()
    if theme not in theme_service.THEME_IDS:
        theme = "base"
    _active_theme_cache["theme"] = theme
    _active_theme_cache["expires"] = now + _ACTIVE_THEME_TTL
    return theme


def _robots_text(db: Session) -> str:
    """根据 allow_index 与 robots_extra 生成 robots.txt 内容。"""
    if not get_bool_setting(db, "allow_index", True):
        return "User-agent: *\nDisallow: /\n"
    lines = ["User-agent: *", "Allow: /"]
    extra = (get_setting(db, "robots_extra", "") or "").strip()
    if extra:
        lines.append(extra)
    return "\n".join(lines) + "\n"


def _sitemap_xml(db: Session, request: Optional[Request] = None) -> str:
    """生成 sitemap.xml 内容（首页 + 分类 + 公开且非加密分类的图片）。"""
    base = effective_frontend_base(db, request).rstrip("/")
    entries: list[str] = [f"  <url><loc>{escape(f'{base}/index.html')}</loc></url>"]

    for folder in db.query(Folder).all():
        loc = escape(f"{base}/folder.html?id={folder.id}")
        entries.append(f"  <url><loc>{loc}</loc></url>")

    locked_ids = select(Folder.id).where(Folder.password_hash.isnot(None))
    images = (
        db.query(Image)
        .filter(
            Image.status == "approved",
            Image.is_deleted.is_(False),
            or_(Image.folder_id.is_(None), Image.folder_id.notin_(locked_ids)),
        )
        .all()
    )
    for image in images:
        loc = escape(f"{base}/image.html?id={image.id}")
        lastmod = image.updated_at.strftime("%Y-%m-%d") if image.updated_at else None
        if lastmod:
            entries.append(
                f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>"
            )
        else:
            entries.append(f"  <url><loc>{loc}</loc></url>")

    body = "\n".join(entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


def _register_site_routes(app: FastAPI) -> None:
    """为前台静态站注册 robots.txt / sitemap.xml / favicon.ico 动态路由。

    必须在 ``mount("/")`` 之前调用，确保这些具体路径优先于静态文件匹配。
    """

    @app.get("/robots.txt")
    def robots(db: Session = Depends(get_db)) -> Response:
        """输出 robots.txt（allow_index 为假时禁止抓取）。"""
        return Response(content=_robots_text(db), media_type="text/plain")

    @app.get("/sitemap.xml")
    def sitemap(request: Request, db: Session = Depends(get_db)) -> Response:
        """输出 sitemap.xml（sitemap_enabled 为假时返回 404）。"""
        if not get_bool_setting(db, "sitemap_enabled", True):
            raise HTTPException(status_code=404, detail="站点地图未启用")
        return Response(content=_sitemap_xml(db, request), media_type="application/xml")

    @app.get("/favicon.ico")
    def favicon(db: Session = Depends(get_db)):
        """返回站点图标；未设置或文件缺失时 404，外链则重定向。"""
        setting = get_setting(db, "favicon", "") or ""
        if not setting:
            raise HTTPException(status_code=404, detail="未设置站点图标")
        if setting.startswith("http://") or setting.startswith("https://"):
            return RedirectResponse(setting, status_code=302)
        path: Optional[Path] = favicon_file_path()
        if path is None:
            raise HTTPException(status_code=404, detail="图标文件不存在")
        return FileResponse(path)


def _register_config_route(app: FastAPI, admin_config: bool = False) -> None:
    """注册动态 ``/js/config.js``（在 mount("/") 之前），按访问主机自动生成 API 地址。

    这样无论以 localhost、服务器 IP 还是域名访问，前端都能指向正确的 API 端口，
    无需在构建镜像时写死地址。admin_config=True（后台站点）时优先使用
    「后台专属 API 地址」，便于本地/内网快速上传而不走域名。
    """

    @app.get("/js/config.js")
    def config_js(request: Request, db: Session = Depends(get_db)) -> Response:
        """返回前端运行时配置（API 基地址）。"""
        base = effective_admin_api_base(db, request) if admin_config else effective_api_base(db, request)
        body = (
            "/* 由后端动态生成：自动适配访问主机与 API 端口 */\n"
            "(function () {\n"
            f"  window.APP_CONFIG = {{ API_BASE: {json.dumps(base)} }};\n"
            "})();\n"
        )
        return Response(
            content=body,
            media_type="application/javascript",
            headers={"Cache-Control": "private, max-age=60"},
        )


def _register_frontend_config_route(app: FastAPI) -> None:
    """注册前台 ``/js/config.js``：额外注入当前主题、默认预设、预设列表与导航统计开关。"""

    @app.get("/js/config.js")
    def config_js(request: Request, db: Session = Depends(get_db)) -> Response:
        """返回前台运行时配置（API 基地址 + 主题信息）。"""
        base = effective_api_base(db, request)
        payload = theme_service.public_theme_payload(db)
        config = payload["config"]
        active = payload["active_theme"]
        theme_info = {
            "active_theme": active,
            "default_preset": config[active]["default_preset"],
            "presets": payload["presets"],
            "nav": {"stats": config["nav"]["stats"]},
        }
        body = (
            "/* 由后端动态生成：自动适配访问主机与 API 端口，并注入主题配置 */\n"
            "(function () {\n"
            f"  window.APP_CONFIG = {{ API_BASE: {json.dumps(base)},"
            f" THEME: {json.dumps(theme_info, ensure_ascii=False)} }};\n"
            "})();\n"
        )
        return Response(
            content=body,
            media_type="application/javascript",
            headers={"Cache-Control": "private, max-age=60"},
        )


def _register_preset_route(app: FastAPI) -> None:
    """注册 ``/presets/{preset_id}.css``：按当前启用主题返回预设 CSS。"""

    @app.get("/presets/{preset_id}.css")
    def preset_css(preset_id: str):
        """返回当前主题的预设 CSS；非法 id 或文件缺失时 404。"""
        theme_id = _active_theme()
        try:
            path = theme_service.preset_css_path(theme_id, preset_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="预设不存在")
        if not path.is_file():
            raise HTTPException(status_code=404, detail="预设不存在")
        return FileResponse(
            path,
            media_type="text/css",
            headers={"Cache-Control": "no-cache"},
        )


class CachedStaticFiles(StaticFiles):
    """静态文件响应：HTML 不缓存，其余资源长缓存（配合 ``?v=`` 版本参数）。"""

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        is_html = Path(path).suffix.lower() in {"", ".html", ".htm"}
        if is_html:
            response.headers["Cache-Control"] = "no-cache"
        else:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


class ThemeDispatcher:
    """按数据库 ``active_theme`` 把请求分发给对应主题目录的静态应用。"""

    def __init__(self, themes_dir: Path) -> None:
        self.themes_dir = themes_dir
        self._apps: dict[Path, CachedStaticFiles] = {}

    def _app_for(self, directory: Path) -> CachedStaticFiles:
        """获取（或创建）某主题目录的静态应用。"""
        key = directory.resolve()
        app = self._apps.get(key)
        if app is None:
            directory.mkdir(parents=True, exist_ok=True)
            app = CachedStaticFiles(directory=str(directory), html=True)
            self._apps[key] = app
        return app

    def _resolve_dir(self, theme_id: str) -> Path:
        """解析主题目录；目录缺失时回退 base。"""
        directory = self.themes_dir / theme_id
        if directory.is_dir():
            return directory
        return self.themes_dir / "base"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        directory = self._resolve_dir(_active_theme())
        await self._app_for(directory)(scope, receive, send)


class AdminStaticFiles(StaticFiles):
    """后台静态文件响应。

    后台 HTML/CSS/JS 必须及时更新（避免旧版页面脚本与新接口不匹配），
    因此统一使用 ``no-cache`` 触发协商缓存；图片等二进制资源仍可长缓存。
    """

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        suffix = Path(path).suffix.lower()
        if suffix in {"", ".html", ".htm", ".js", ".css"}:
            response.headers["Cache-Control"] = "no-cache"
        else:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def create_static_app(
    directory: str, site_routes: bool = False, admin_config: bool = False
) -> FastAPI:
    """创建一个托管指定目录静态文件的 FastAPI 应用。

    html=True 支持首页与目录索引；动态 ``/js/config.js`` 始终注册（优先于静态文件）；
    site_routes=True 时额外注册前台动态路由（robots.txt、sitemap.xml、favicon.ico）；
    admin_config=True 时 config.js 使用「后台专属 API 地址」（留空回退普通地址）。
    """
    Path(directory).mkdir(parents=True, exist_ok=True)
    app = FastAPI(title=f"Static: {Path(directory).name}")
    # 压缩 HTML/CSS/JS/JSON 等文本响应（大于 500 字节时）
    app.add_middleware(GZipMiddleware, minimum_size=500)
    _register_config_route(app, admin_config=admin_config)
    if site_routes:
        _register_site_routes(app)
    app.mount("/", AdminStaticFiles(directory=directory, html=True), name="static")
    return app


def create_frontend_app(themes_dir: str) -> FastAPI:
    """创建前台主题静态应用：按 active_theme 动态切换主题目录。

    先注册动态 ``/js/config.js``、站点动态路由与 ``/presets/{id}.css``，
    最后把主题调度器挂载到 ``/``；主题目录暂不存在时回退 base，不中断服务。
    """
    root = Path(themes_dir)
    root.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Static: frontend themes")
    # 压缩 HTML/CSS/JS/JSON 等文本响应（大于 500 字节时）
    app.add_middleware(GZipMiddleware, minimum_size=500)
    _register_frontend_config_route(app)
    _register_site_routes(app)
    _register_preset_route(app)
    app.mount("/", ThemeDispatcher(root), name="theme")
    return app
