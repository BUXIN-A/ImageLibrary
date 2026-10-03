# -*- coding: utf-8 -*-
"""站点地址解析。

API 站点地址与前台站点地址支持在后台「站点设置」中配置；未配置时按以下优先级自动推断：
后台配置 > PUBLIC_HOST 环境变量 > 访问请求的主机名（仅 API） > 配置文件默认值。
"""
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.seed import get_setting


def configured_api_base(db: Session) -> str:
    """后台配置的 API 站点地址；未配置返回空字符串。"""
    return (get_setting(db, "api_base_url", "") or "").strip()


def configured_frontend_base(db: Session) -> str:
    """后台配置的前台站点地址；未配置返回空字符串。"""
    return (get_setting(db, "frontend_base_url", "") or "").strip()


def effective_api_base(db: Session, request=None) -> str:
    """实际生效的 API 基地址（用于前端 config.js、OAuth 回调地址）。"""
    value = configured_api_base(db)
    if value:
        return value.rstrip("/")
    return settings.resolve_api_base(request)


def effective_frontend_base(db: Session) -> str:
    """实际生效的前台基地址（用于分享链接、sitemap、OAuth 回跳）。"""
    value = configured_frontend_base(db)
    if value:
        return value.rstrip("/")
    return settings.frontend_base_url()
