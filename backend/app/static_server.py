# -*- coding: utf-8 -*-
"""通用静态站点 ASGI 应用工厂（可自动生成 config.js，并为前台挂载动态 ROBOTS/SITEMAP/FAVICON 路由）。"""
import json
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Folder, Image
from backend.app.routers.site import favicon_file_path
from backend.app.seed import get_bool_setting, get_setting
from backend.app.site_config import (
    effective_admin_api_base,
    effective_api_base,
    effective_frontend_base,
)


def _robots_text(db: Session) -> str:
    """根据 allow_index 与 robots_extra 生成 robots.txt 内容。"""
    if not get_bool_setting(db, "allow_index", True):
        return "User-agent: *\nDisallow: /\n"
    lines = ["User-agent: *", "Allow: /"]
    extra = (get_setting(db, "robots_extra", "") or "").strip()
    if extra:
        lines.append(extra)
    return "\n".join(lines) + "\n"


def _sitemap_xml(db: Session) -> str:
    """生成 sitemap.xml 内容（首页 + 文件夹 + 已公开未删除图片）。"""
    base = effective_frontend_base(db).rstrip("/")
    entries: list[str] = [f"  <url><loc>{escape(f'{base}/index.html')}</loc></url>"]

    for folder in db.query(Folder).all():
        loc = escape(f"{base}/folder.html?id={folder.id}")
        entries.append(f"  <url><loc>{loc}</loc></url>")

    images = (
        db.query(Image)
        .filter(Image.status == "approved", Image.is_deleted.is_(False))
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
    def sitemap(db: Session = Depends(get_db)) -> Response:
        """输出 sitemap.xml（sitemap_enabled 为假时返回 404）。"""
        if not get_bool_setting(db, "sitemap_enabled", True):
            raise HTTPException(status_code=404, detail="站点地图未启用")
        return Response(content=_sitemap_xml(db), media_type="application/xml")

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
            headers={"Cache-Control": "no-store"},
        )


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
    _register_config_route(app, admin_config=admin_config)
    if site_routes:
        _register_site_routes(app)
    app.mount("/", StaticFiles(directory=directory, html=True), name="static")
    return app
