# -*- coding: utf-8 -*-
"""FastAPI 应用装配：CORS、静态媒体挂载、路由注册与初始化。"""
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.deps import client_ip
from backend.app.notify_service import (
    CATEGORY_ERROR,
    CATEGORY_SITE,
    CATEGORY_STARTUP,
    LEVEL_ERROR,
    LEVEL_INFO,
    LEVEL_WARNING,
    log,
    record,
)
from backend.app.routers import (
    admin_images,
    admin_users,
    auth,
    comments,
    credential,
    folders,
    images,
    login_settings,
    notifications,
    oauth,
    review,
    settings as settings_router,
    site,
    stats,
    tags,
    themes,
    tokens,
    user,
)
from backend.app.seed import init_seed
from backend.app.site_monitor import run_startup_check
from backend.app.version import __version__

# 确保数据目录存在（StaticFiles 挂载时目录必须存在）
settings.ensure_dirs()

app = FastAPI(title="ImageLibrary API", version=__version__)

# 允许前台(8000)与后台(8001)跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_origin_regex=settings.cors_origin_regex() or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _startup_site_check() -> None:
    """后台线程执行站点地址自检，避免阻塞服务启动。"""
    try:
        run_startup_check()
    except Exception as exc:  # noqa: BLE001 - 自检失败不应影响服务
        record(LEVEL_WARNING, CATEGORY_SITE, "启动站点地址自检失败", detail=str(exc))


@app.on_event("startup")
def _on_startup() -> None:
    """启动时初始化数据，记录服务启动并异步执行站点地址自检。"""
    init_seed()
    try:
        db = SessionLocal()
        try:
            log(db, LEVEL_INFO, CATEGORY_STARTUP, f"服务启动（v{__version__}）")
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - 启动日志失败不应影响服务
        pass
    threading.Thread(target=_startup_site_check, daemon=True).start()


@app.exception_handler(Exception)
async def _handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """捕获未处理异常：写入后台通知并返回统一的 500 响应。"""
    try:
        record(
            LEVEL_ERROR,
            CATEGORY_ERROR,
            f"服务端错误：{request.method} {request.url.path}",
            detail=f"{type(exc).__name__}: {exc}",
            ip=client_ip(request),
        )
    except Exception:  # noqa: BLE001 - 记录失败时仍需返回错误响应
        pass
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


@app.get("/")
def root_redirect() -> RedirectResponse:
    """根路径重定向到交互式文档。"""
    return RedirectResponse(url="/docs", status_code=302)


# 静态资源：原图与缩略图
app.mount("/media", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="media")
app.mount(
    "/thumbnails",
    StaticFiles(directory=str(settings.THUMBNAIL_DIR)),
    name="thumbnails",
)

# 认证与公开路由
app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(user.router)
app.include_router(images.router)
app.include_router(comments.router)
app.include_router(folders.router)
app.include_router(tags.router)
app.include_router(site.router)
app.include_router(themes.router)
app.include_router(settings_router.router)
app.include_router(credential.router)

# 管理端路由
app.include_router(folders.admin_router)
app.include_router(tags.admin_router)
app.include_router(tokens.router)
app.include_router(review.router)
app.include_router(settings_router.admin_router)
app.include_router(site.admin_router)
app.include_router(themes.admin_router)
app.include_router(login_settings.router)
app.include_router(comments.admin_router)
app.include_router(admin_users.router)
app.include_router(stats.router)
app.include_router(admin_images.router)
app.include_router(notifications.admin_router)


@app.get("/api/health")
def health() -> dict:
    """健康检查。"""
    return {"status": "ok", "version": __version__}
