# -*- coding: utf-8 -*-
"""后台通知 / 服务日志写入工具。

统一封装通知的写入逻辑，供各路由、启动自检与命令行使用：

- ``log(db, ...)``：复用调用方已有的数据库会话（会提交，异常向外抛出）。
- ``record(...)``：自行创建会话写入，且**吞掉全部异常**，用于异常处理器、
  后台线程等无法保证会话可用的场景，避免日志写入失败影响主流程。
"""
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models import Notification

# 事件级别
LEVEL_INFO = "info"
LEVEL_WARNING = "warning"
LEVEL_ERROR = "error"
LEVELS = (LEVEL_INFO, LEVEL_WARNING, LEVEL_ERROR)

# 事件分类
CATEGORY_STARTUP = "startup"  # 服务启动
CATEGORY_SITE = "site"        # 站点地址检测与变更
CATEGORY_ERROR = "error"      # 服务端错误
CATEGORY_LOGIN = "login"      # 管理员登录
CATEGORY_VISIT = "visit"      # 用户访问记录
CATEGORIES = (
    CATEGORY_STARTUP,
    CATEGORY_SITE,
    CATEGORY_ERROR,
    CATEGORY_LOGIN,
    CATEGORY_VISIT,
)

CATEGORY_LABELS = {
    CATEGORY_STARTUP: "服务启动",
    CATEGORY_SITE: "站点地址",
    CATEGORY_ERROR: "服务端错误",
    CATEGORY_LOGIN: "管理员登录",
    CATEGORY_VISIT: "用户访问",
}
LEVEL_LABELS = {LEVEL_INFO: "信息", LEVEL_WARNING: "警告", LEVEL_ERROR: "错误"}


def _truncate(value: Optional[str], limit: int) -> Optional[str]:
    """按长度截断文本，避免超长内容撑爆存储。"""
    if value is None:
        return None
    return value if len(value) <= limit else value[:limit]


def log(
    db: Session,
    level: str,
    category: str,
    message: str,
    detail: Optional[str] = None,
    ip: Optional[str] = None,
) -> Notification:
    """使用给定会话写入一条通知并提交。"""
    item = Notification(
        level=level if level in LEVELS else LEVEL_INFO,
        category=category if category in CATEGORIES else CATEGORY_STARTUP,
        message=_truncate(message, 500) or "",
        detail=_truncate(detail, 4000),
        ip=_truncate(ip, 64),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def record(
    level: str,
    category: str,
    message: str,
    detail: Optional[str] = None,
    ip: Optional[str] = None,
) -> None:
    """自行创建会话写入通知；任何异常都被吞掉，不影响主流程。"""
    try:
        db: Session = SessionLocal()
        try:
            log(db, level, category, message, detail=detail, ip=ip)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - 日志写入失败不应影响业务
        pass
