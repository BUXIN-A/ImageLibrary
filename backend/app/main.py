# -*- coding: utf-8 -*-
"""FastAPI 应用装配：CORS、静态媒体挂载、路由注册与初始化。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.routers import (
    admin_images,
    admin_users,
    auth,
    comments,
    credential,
    folders,
    images,
    login_settings,
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

# 确保数据目录存在（StaticFiles 挂载时目录必须存在）
settings.ensure_dirs()

app = FastAPI(title="ImageLibrary API", version="1.0.0")

# 允许前台(8000)与后台(8001)跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_origin_regex=settings.cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    """启动时初始化数据表、默认管理员与默认设置。"""
    init_seed()


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


@app.get("/api/health")
def health() -> dict:
    """健康检查。"""
    return {"status": "ok"}
