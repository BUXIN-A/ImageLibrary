# -*- coding: utf-8 -*-
"""数据库引擎、会话与 ORM Base 定义。"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import settings

# SQLite 数据库连接；check_same_thread=False 允许跨线程使用同一连接
engine = create_engine(
    f"sqlite:///{settings.DB_PATH}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """SQLite 默认不强制外键约束，这里手动开启以支持 ondelete 行为。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 会话工厂
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db():
    """FastAPI 依赖：提供数据库会话，并在请求结束后关闭。"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """根据 ORM 模型创建全部数据表。"""
    # 导入模型以确保表结构已注册到 Base.metadata
    from backend.app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
