# -*- coding: utf-8 -*-
"""Alembic 迁移环境。

数据库 URL 统一从 ``backend.app.config.settings.DB_PATH`` 生成，
因此支持通过环境变量 ``DB_PATH`` 指向临时库或其他位置；
不依赖 alembic.ini 中写死的绝对路径，也不依赖当前工作目录。
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# 项目根目录：migrations/env.py -> parents[0]=migrations、[1]=项目根
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app import models  # noqa: E402,F401 - 导入模型以注册到 Base.metadata
from backend.app.config import settings  # noqa: E402
from backend.app.database import Base  # noqa: E402

config = context.config

# 读取 alembic.ini 的日志配置；disable_existing_loggers=False 避免关闭应用日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# 模型元数据（autogenerate / upgrade 对比目标）
target_metadata = Base.metadata

# 数据库 URL：始终以 settings.DB_PATH 为准
DB_PATH = Path(settings.DB_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH}"


def run_migrations_offline() -> None:
    """离线模式：仅生成 SQL，不实际连接数据库。"""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接 SQLite 并执行迁移（batch 模式重建表）。"""
    connectable = create_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args={"check_same_thread": False},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
