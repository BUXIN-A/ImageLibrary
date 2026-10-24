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


def _drop_leftover_batch_tables() -> None:
    """清理上一次迁移失败残留的 ``_alembic_tmp_*`` 临时表（仅 SQLite）。"""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE '_alembic_tmp_%'"
            )
        ).fetchall()
        for (name,) in rows:
            conn.execute(text(f'DROP TABLE IF EXISTS "{name}"'))


def _create_missing_tables() -> None:
    """为旧库补齐缺失的表（只创建不存在的表，不修改已有表结构）。

    早期版本的数据库可能缺少后来新增的表（如 ``comments``、``notifications``），
    直接 stamp 基线再升级会因缺表失败，因此先按当前模型补建缺失表。
    """
    from backend.app import models  # noqa: F401 - 导入以注册所有模型

    Base.metadata.create_all(bind=engine, checkfirst=True)


def run_migrations() -> None:
    """执行数据库迁移到最新 revision。

    - 空库：直接 upgrade 到 head（创建全部表与默认数据）。
    - 已有业务表但无 alembic_version 的旧库：清理迁移残留 -> 补建缺失表
      -> stamp 基线 -> upgrade。
    - 已有 alembic_version 的库：清理残留临时表并补建缺失表后 upgrade
      （兼容此前迁移失败/异常中断留下的半成品库）。
    - 迁移失败会抛出异常，阻止服务带病启动。
    """
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = _alembic_config()

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    has_version_table, current_revision = _current_revision()

    if has_version_table and current_revision is not None:
        # 已纳入 Alembic 管理：清理失败残留并补齐意外缺失的表（幂等）
        _drop_leftover_batch_tables()
        _create_missing_tables()
    elif tables & _BUSINESS_TABLES:
        # 旧库（无版本记录）：结构视为基线，先补齐缺失表再打基线标记
        _drop_leftover_batch_tables()
        _create_missing_tables()
        command.stamp(config, BASE_REVISION)

    command.upgrade(config, "head")


def init_db() -> None:
    """兼容旧调用：执行 Alembic 迁移（不再使用 create_all 建表）。"""
    run_migrations()
