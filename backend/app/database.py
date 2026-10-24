# -*- coding: utf-8 -*-
"""数据库引擎、会话、ORM Base 与 Alembic 迁移入口。"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import settings

# 项目根目录：backend/app/database.py -> parents[0]=app、[1]=backend、[2]=项目根
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
# 旧库（无 alembic_version）先落入的基线 revision
BASE_REVISION = "0001"
# 用于判断是否为已有业务库的表名
_BUSINESS_TABLES = {
    "admins",
    "upload_tokens",
    "folders",
    "tags",
    "image_tags",
    "images",
    "settings",
    "users",
    "notifications",
    "comments",
}

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


def _alembic_config() -> Config:
    """构造 Alembic 配置。

    脚本目录与数据库 URL 均使用绝对路径/配置生成，不依赖当前工作目录。
    """
    if not ALEMBIC_INI_PATH.exists():
        raise RuntimeError(f"未找到 Alembic 配置文件：{ALEMBIC_INI_PATH}")
    if not MIGRATIONS_DIR.is_dir():
        raise RuntimeError(f"未找到 Alembic 迁移目录：{MIGRATIONS_DIR}")

    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.DB_PATH}")
    return config


def _current_revision() -> tuple[bool, str | None]:
    """返回 (是否存在 alembic_version 表, 当前 revision)。"""
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        return False, None
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
    return True, (row[0] if row else None)


def run_migrations() -> None:
    """执行数据库迁移到最新 revision。

    - 空库：直接 upgrade 到 head（创建全部表与默认数据）。
    - 已有业务表的旧库（无 alembic_version）：先 stamp 基线，再 upgrade。
    - 迁移失败会抛出异常，阻止服务带病启动。
    """
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = _alembic_config()

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    has_version_table, current_revision = _current_revision()

    if (not has_version_table or current_revision is None) and tables & _BUSINESS_TABLES:
        # 旧库：结构等同于基线，先标记为 0001 再执行增量迁移
        command.stamp(config, BASE_REVISION)

    command.upgrade(config, "head")


def init_db() -> None:
    """兼容旧调用：执行 Alembic 迁移（不再使用 create_all 建表）。"""
    run_migrations()
