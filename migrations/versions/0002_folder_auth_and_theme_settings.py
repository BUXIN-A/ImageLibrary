"""add folder auth fields, image fk cascade, indexes and theme settings

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24

- folders 增加 password_hash / auth_version
- images.uploaded_by 外键改为 ON DELETE SET NULL（SQLite 重建表，保留数据与索引）
- 新增性能索引
- 文件夹扁平化（parent_id 置空、path 重建、顶级重名追加后缀）
- 设置表写入 active_theme / theme_config / theme_presets，删除旧主题键
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------- 默认设置值 ----------
DEFAULT_ACTIVE_THEME = "base"

DEFAULT_THEME_CONFIG = {
    "base": {
        "default_preset": "light",
    },
    "nav": {
        "default_preset": "light",
        "stats": {
            "folder_images": True,
            "total_images": True,
            "total_views": True,
            "total_comments": True,
            "total_downloads": True,
        },
    },
}

DEFAULT_THEME_PRESETS = {
    "base": [
        {"id": "light", "name": "明亮", "file": "light.css"},
        {"id": "dark", "name": "暗夜", "file": "dark.css"},
    ],
    "nav": [
        {"id": "light", "name": "亮色", "file": "light.css"},
        {"id": "dark", "name": "暗色", "file": "dark.css"},
    ],
}

REMOVED_SETTING_KEYS = ("default_theme", "enabled_themes")


def _json(value) -> str:
    """以紧凑格式序列化为 JSON 字符串（保留中文）。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _index_names(bind, table: str) -> set[str]:
    """返回指定表已存在的索引名集合。"""
    return {item["name"] for item in sa.inspect(bind).get_indexes(table)}


def _column_names(bind, table: str) -> set[str]:
    """返回指定表已存在的列名集合（表不存在时返回空集合）。"""
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {item["name"] for item in inspector.get_columns(table)}


def _drop_leftover_tmp_tables(bind) -> None:
    """清理上一次迁移失败残留的 ``_alembic_tmp_*`` 临时表（仅 SQLite）。"""
    if bind.dialect.name != "sqlite":
        return
    rows = bind.execute(
        sa.text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_alembic_tmp_%'"
        )
    ).fetchall()
    for (name,) in rows:
        bind.execute(sa.text(f'DROP TABLE IF EXISTS "{name}"'))


def _uploaded_by_ondelete(bind) -> str:
    """读取 ``images.uploaded_by`` 外键当前的 ondelete 行为（表或外键缺失时返回空串）。"""
    inspector = sa.inspect(bind)
    if "images" not in inspector.get_table_names():
        return ""
    for fk in inspector.get_foreign_keys("images"):
        if fk.get("constrained_columns") == ["uploaded_by"]:
            options = fk.get("options") or {}
            return str(options.get("ondelete") or "").upper()
    return ""


def _create_index_if_missing(bind, table: str, name: str, columns: list[str]) -> None:
    """若索引不存在则创建（表缺失时跳过，保证迁移幂等）。"""
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return
    if name in {item["name"] for item in inspector.get_indexes(table)}:
        return
    op.create_index(name, table, columns, unique=False)


def _images_table(ondelete_uploaded_by: Union[str, None]) -> sa.Table:
    """构造 images 表定义（用于 SQLite batch 重建）。

    参数控制 uploaded_by 外键的 ondelete 行为，其余列、约束与索引
    与 0001 基线保持一致。
    """
    return sa.Table(
        "images",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("thumb_name", sa.String(length=255), nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reject_reason", sa.String(length=255), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("downloads", sa.Integer(), nullable=False),
        sa.Column("share_token", sa.String(length=64), nullable=True),
        sa.Column("exif", sa.JSON(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["folder_id"], ["folders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["upload_tokens.id"], ondelete=ondelete_uploaded_by
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_images_created_at", "created_at"),
        sa.Index("ix_images_filename", "filename", unique=True),
        sa.Index("ix_images_is_deleted", "is_deleted"),
        sa.Index("ix_images_share_token", "share_token", unique=True),
        sa.Index("ix_images_status", "status"),
    )


def _rebuild_images(bind, ondelete_uploaded_by: Union[str, None]) -> None:
    """通过 batch 模式重建 images 表（SQLite 修改外键的唯一安全方式）。"""
    with op.batch_alter_table(
        "images",
        copy_from=_images_table(ondelete_uploaded_by),
        recreate="always",
    ):
        pass


def _flatten_folders(bind) -> None:
    """把所有文件夹提升为顶级并修复重名（幂等）。"""
    # 全部置为顶级：parent_id 为空，path 为 /{id}/
    bind.execute(
        sa.text(
            "UPDATE folders SET parent_id = NULL, path = '/' || CAST(id AS TEXT) || '/'"
        )
    )

    rows = bind.execute(sa.text("SELECT id, name FROM folders ORDER BY id")).fetchall()
    used: set[str] = set()
    for folder_id, name in rows:
        candidate = name if name else f"分类{folder_id}"
        if candidate in used:
            suffix = 2
            while f"{candidate} ({suffix})" in used:
                suffix += 1
            candidate = f"{candidate} ({suffix})"
        used.add(candidate)
        if candidate != name:
            bind.execute(
                sa.text("UPDATE folders SET name = :name WHERE id = :id"),
                {"name": candidate, "id": folder_id},
            )


def _migrate_settings(bind) -> None:
    """写入新主题设置键并删除旧键（仅补齐缺失项，幂等）。"""
    settings_table = sa.table(
        "settings",
        sa.column("key", sa.String(length=128)),
        sa.column("value", sa.Text()),
    )

    existing = {
        row[0] for row in bind.execute(sa.text("SELECT key FROM settings")).fetchall()
    }

    new_values = {
        "active_theme": DEFAULT_ACTIVE_THEME,
        "theme_config": _json(DEFAULT_THEME_CONFIG),
        "theme_presets": _json(DEFAULT_THEME_PRESETS),
    }
    for key, value in new_values.items():
        if key not in existing:
            bind.execute(settings_table.insert().values(key=key, value=value))

    for key in REMOVED_SETTING_KEYS:
        bind.execute(settings_table.delete().where(settings_table.c.key == key))


def upgrade() -> None:
    bind = op.get_bind()

    # 0) 清理上次失败残留的临时表，确保可以安全重试
    _drop_leftover_tmp_tables(bind)

    # 1) folders：分类密码相关字段（已存在时跳过，保证可重试）
    existing_columns = _column_names(bind, "folders")
    with op.batch_alter_table("folders", schema=None) as batch_op:
        if "password_hash" not in existing_columns:
            batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        if "auth_version" not in existing_columns:
            batch_op.add_column(
                sa.Column(
                    "auth_version",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )

    # 2) images：uploaded_by 外键改为 ON DELETE SET NULL（已是目标状态则跳过）
    if _uploaded_by_ondelete(bind) != "SET NULL":
        _rebuild_images(bind, ondelete_uploaded_by="SET NULL")

    # 3) 性能索引（不存在时创建）
    _create_index_if_missing(bind, "images", "ix_images_folder_id", ["folder_id"])
    _create_index_if_missing(bind, "images", "ix_images_thumb_name", ["thumb_name"])
    _create_index_if_missing(
        bind,
        "images",
        "ix_images_status_is_deleted_created_at",
        ["status", "is_deleted", "created_at"],
    )
    _create_index_if_missing(
        bind, "comments", "ix_comments_image_id_status", ["image_id", "status"]
    )

    # 4) 数据迁移：文件夹扁平化 + 设置键调整
    _flatten_folders(bind)
    _migrate_settings(bind)


def downgrade() -> None:
    bind = op.get_bind()

    # 恢复旧主题设置键，移除新键
    settings_table = sa.table(
        "settings",
        sa.column("key", sa.String(length=128)),
        sa.column("value", sa.Text()),
    )
    existing = {
        row[0] for row in bind.execute(sa.text("SELECT key FROM settings")).fetchall()
    }
    legacy_values = {
        "default_theme": "light",
        "enabled_themes": _json(
            ["light", "dark", "ocean", "forest", "sunset", "sakura"]
        ),
    }
    for key, value in legacy_values.items():
        if key not in existing:
            bind.execute(settings_table.insert().values(key=key, value=value))
    for key in ("active_theme", "theme_config", "theme_presets"):
        bind.execute(settings_table.delete().where(settings_table.c.key == key))

    # 删除新增索引
    for table, name in (
        ("images", "ix_images_folder_id"),
        ("images", "ix_images_thumb_name"),
        ("images", "ix_images_status_is_deleted_created_at"),
        ("comments", "ix_comments_image_id_status"),
    ):
        if name in _index_names(bind, table):
            op.drop_index(name, table_name=table)

    # images 外键恢复为无 ondelete
    _rebuild_images(bind, ondelete_uploaded_by=None)

    # 删除 folders 新增字段（batch 模式重建表）
    with op.batch_alter_table("folders", schema=None) as batch_op:
        batch_op.drop_column("auth_version")
        batch_op.drop_column("password_hash")
