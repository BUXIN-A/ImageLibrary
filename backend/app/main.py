# -*- coding: utf-8 -*-
"""FastAPI 应用装配：CORS、受控媒体路由、路由注册与初始化。"""
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.deps import client_ip
from backend.app.http_middleware import BodySizeLimitMiddleware, SelectiveGZipMiddleware
from backend.app.models import Admin
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
    media,
    notifications,
    oauth,
    review,
    settings as settings_router,
    site,
    stats,
    tags,
    theme_settings,
    tokens,
    user,
)
from backend.app.seed import init_seed
from backend.app.security import secret_key_was_generated, verify_password
from backend.app.site_monitor import run_startup_check
from backend.app.theme_settings_service import ensure_theme_state
from backend.app.version import __version__

# 确保数据目录存在
settings.ensure_dirs()

app = FastAPI(title="ImageLibrary API", version=__version__)

# 中间件顺序：后添加的更靠外层。GZip（选择性）→ 请求体限制 → CORS（最外层，
# 保证 413 等提前返回的响应也带上跨域头）。
app.add_middleware(SelectiveGZipMiddleware, minimum_size=500)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.MAX_REQUEST_BODY_SIZE)
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


# 启动时检测的弱口令候选（仅用于提示，不会自动修改已有密码）
_WEAK_ADMIN_CANDIDATES = ("admin123", "admin", "123456", "password")


def _warn_security_defaults(db) -> None:
    """启动时提示自动生成的签名密钥与仍在使用的弱管理员密码。"""
    try:
        if secret_key_was_generated():
            print(
                "\n" + "=" * 56 + "\n"
                " 未配置 SECRET_KEY，已自动生成随机密钥并保存到 data/.secret_key\n"
                " 如需固定密钥，请在 .env 中设置 SECRET_KEY（建议 >= 32 字节随机串）\n"
                + "=" * 56 + "\n",
                flush=True,
            )
    except Exception:  # noqa: BLE001 - 提示失败不影响启动
        pass

    try:
        admin = db.query(Admin).order_by(Admin.id).first()
        if admin is None:
            return
        for candidate in _WEAK_ADMIN_CANDIDATES:
            if verify_password(candidate, admin.password_hash):
                log(
                    db,
                    LEVEL_WARNING,
                    CATEGORY_STARTUP,
                    "管理员仍在使用弱密码，请尽快修改",
                    detail=f"用户名：{admin.username}",
                )
                print(
                    "\n警告：管理员账号仍在使用弱密码，请登录后台「账号与安全」立即修改。\n",
                    flush=True,
                )
                break
    except Exception:  # noqa: BLE001
        pass


@app.on_event("startup")
def _on_startup() -> None:
    """启动时初始化数据，记录服务启动并异步执行站点地址自检。"""
    init_seed()
    try:
        db = SessionLocal()
        try:
            ensure_theme_state(db)
            _warn_security_defaults(db)
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


# 受控媒体：原图与缩略图（路由内部按状态/分类密码/后台签名授权）
app.include_router(media.router)

# 认证与公开路由
app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(user.router)
app.include_router(images.router)
app.include_router(comments.router)
app.include_router(folders.router)
app.include_router(tags.router)
app.include_router(site.router)
app.include_router(theme_settings.router)
app.include_router(settings_router.router)
app.include_router(credential.router)

# 管理端路由
app.include_router(folders.admin_router)
app.include_router(tags.admin_router)
app.include_router(tokens.router)
app.include_router(review.router)
app.include_router(settings_router.admin_router)
app.include_router(site.admin_router)
app.include_router(theme_settings.admin_router)
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
