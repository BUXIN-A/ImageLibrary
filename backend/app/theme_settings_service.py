# -*- coding: utf-8 -*-
"""主题设置服务：基础/导航两套主题、预设 CSS 文件与主题配置。

主题体系：
- ``frontend/themes/<theme_id>/`` 存放自包含主题（theme.json + HTML/CSS/JS）；
- ``data/theme-presets/<theme_id>/<preset_id>.css`` 存放配色预设；
- 设置表 ``active_theme`` / ``theme_config`` / ``theme_presets`` 保存状态。

本模块只负责状态与文件读写，路由见 :mod:`backend.app.routers.theme_settings`。
"""
import json
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models import Comment, Folder, Image
from backend.app.seed import get_setting, set_setting

# ---------------- 主题常量 ----------------
THEME_IDS: tuple[str, ...] = ("base", "nav")
THEME_NAMES: dict[str, str] = {"base": "基础", "nav": "导航"}
THEME_DESCRIPTIONS: dict[str, str] = {
    "base": "经典图库首页，沿用简洁的网格布局",
    "nav": "以导航入口为首页，提供分类与统计面板",
}
THEME_VERSION = "2.0.1"

DEFAULT_PRESET_ID = "light"

# 导航主题首页统计开关（默认全部开启）
DEFAULT_NAV_STATS: dict[str, bool] = {
    "folder_images": True,
    "total_images": True,
    "total_views": True,
    "total_comments": True,
    "total_downloads": True,
}

# 默认主题配置（与迁移 0002 写入的结构保持一致）
DEFAULT_THEME_CONFIG: dict[str, dict] = {
    "base": {"default_preset": "light"},
    "nav": {
        "default_preset": "light",
        "stats": dict(DEFAULT_NAV_STATS),
    },
}

# 默认预设（每套主题至少保留一个）
DEFAULT_THEME_PRESETS: dict[str, list[dict]] = {
    "base": [
        {"id": "light", "name": "明亮", "builtin": True},
        {"id": "dark", "name": "暗夜", "builtin": True},
    ],
    "nav": [
        {"id": "light", "name": "亮色", "builtin": True},
        {"id": "dark", "name": "暗色", "builtin": True},
    ],
}

# 预设 id 规则（同时用于防路径穿越）
PRESET_ID_RE = re.compile(r"^[a-z0-9_-]{2,32}$")
# 单个预设 CSS 文件大小上限
MAX_PRESET_BYTES = 256 * 1024
# 预设名称长度上限
MAX_PRESET_NAME_LEN = 64

# ---------------- 默认预设 CSS 变量 ----------------
# 17 个现有变量，选择器为 :root[data-preset="<id>"]
_LIGHT_VARS: dict[str, str] = {
    "--color-bg": "#fbfbfa",
    "--color-surface": "#ffffff",
    "--color-surface-2": "#f1f1ef",
    "--color-text": "#37352f",
    "--color-text-muted": "#787774",
    "--color-primary": "#2383e2",
    "--color-primary-contrast": "#ffffff",
    "--color-border": "rgba(55, 53, 47, 0.09)",
    "--color-danger": "#eb5757",
    "--color-success": "#0f7b6c",
    "--color-warning": "#cb912f",
    "--shadow-sm": "0 1px 2px rgba(15, 15, 15, 0.04)",
    "--shadow-md": "0 4px 14px rgba(15, 15, 15, 0.1)",
    "--radius-sm": "4px",
    "--radius-md": "6px",
    "--radius-lg": "10px",
    "--font-sans": (
        'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", '
        '"PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif'
    ),
}

_DARK_VARS: dict[str, str] = {
    "--color-bg": "#191919",
    "--color-surface": "#202020",
    "--color-surface-2": "#2a2a2a",
    "--color-text": "#e9e9e7",
    "--color-text-muted": "#9b9b9b",
    "--color-primary": "#529cca",
    "--color-primary-contrast": "#ffffff",
    "--color-border": "rgba(255, 255, 255, 0.094)",
    "--color-danger": "#ff7369",
    "--color-success": "#4dab9a",
    "--color-warning": "#ffdc49",
    "--shadow-sm": "0 1px 2px rgba(0, 0, 0, 0.3)",
    "--shadow-md": "0 4px 14px rgba(0, 0, 0, 0.45)",
    "--radius-sm": "4px",
    "--radius-md": "6px",
    "--radius-lg": "10px",
    "--font-sans": (
        'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", '
        '"PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif'
    ),
}


class PresetConflictError(ValueError):
    """预设已存在（路由映射为 409）。"""


# ---------------- 路径 ----------------
def presets_root() -> Path:
    """预设 CSS 根目录：``data/theme-presets``。"""
    return settings.DATA_DIR / "theme-presets"


def themes_root() -> Path:
    """主题目录根：``frontend/themes``。"""
    return settings.BASE_DIR / "frontend" / "themes"


def ensure_dirs() -> None:
    """确保预设目录与主题目录存在（主题包本身由 Task 7 创建）。"""
    for theme_id in THEME_IDS:
        (presets_root() / theme_id).mkdir(parents=True, exist_ok=True)
    themes_root().mkdir(parents=True, exist_ok=True)


# ---------------- 校验 ----------------
def require_theme(theme_id: str) -> str:
    """校验主题 id，非法时抛 ValueError（中文原因）。"""
    value = (theme_id or "").strip()
    if value not in THEME_IDS:
        raise ValueError("主题不存在")
    return value


def validate_preset_id(preset_id: str) -> str:
    """校验预设 id（同时防止路径穿越）。"""
    value = (preset_id or "").strip()
    if not PRESET_ID_RE.match(value):
        raise ValueError("预设 ID 只能由 2-32 位小写字母、数字、下划线或连字符组成")
    return value


def preset_css_path(theme_id: str, preset_id: str) -> Path:
    """返回预设 CSS 文件路径；非法 id 抛 ValueError。"""
    theme = require_theme(theme_id)
    preset = validate_preset_id(preset_id)
    return presets_root() / theme / f"{preset}.css"


def preview_path(theme_id: str) -> Optional[Path]:
    """返回主题预览图路径；主题非法或文件缺失时返回 None。"""
    if theme_id not in THEME_IDS:
        return None
    path = themes_root() / theme_id / "preview.png"
    return path if path.is_file() else None


# ---------------- 默认 CSS ----------------
def _vars_for(preset_id: str) -> dict[str, str]:
    """按预设 id 选择默认变量（未知 id 回退明亮配色）。"""
    return dict(_DARK_VARS if preset_id == "dark" else _LIGHT_VARS)


def render_default_preset_css(theme_id: str, preset_id: str) -> str:
    """生成内置默认预设 CSS（含 ``[data-preset="<id>"]`` 选择器）。"""
    theme_name = THEME_NAMES.get(theme_id, theme_id)
    lines = [
        f"/* {theme_name}主题 · 预设 {preset_id}（内置默认） */",
        f':root[data-preset="{preset_id}"] {{',
    ]
    for key, value in _vars_for(preset_id).items():
        lines.append(f"  {key}: {value};")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------- JSON 读写 ----------------
def _load_json(raw: Optional[str]):
    """解析设置中的 JSON 字符串；缺失或损坏返回 None。"""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _dump(value) -> str:
    """以紧凑格式序列化 JSON（保留中文）。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _default_preset_ids(theme_id: str) -> set[str]:
    """某主题内置默认预设 id 集合。"""
    return {item["id"] for item in DEFAULT_THEME_PRESETS[theme_id]}


def _normalize_config(raw) -> dict:
    """把任意 theme_config 规范化为 base/nav 结构并补齐缺失项。"""
    source = raw if isinstance(raw, dict) else {}
    result: dict[str, dict] = {}
    for theme_id in THEME_IDS:
        defaults = DEFAULT_THEME_CONFIG[theme_id]
        node = source.get(theme_id)
        node = node if isinstance(node, dict) else {}

        preset = node.get("default_preset")
        preset = str(preset).strip() if preset is not None else ""
        if not preset:
            preset = defaults["default_preset"]

        entry: dict = {"default_preset": preset}
        if theme_id == "nav":
            stats_raw = node.get("stats")
            stats_raw = stats_raw if isinstance(stats_raw, dict) else {}
            stats: dict[str, bool] = {}
            for key, default in defaults["stats"].items():
                value = stats_raw.get(key, default)
                try:
                    stats[key] = _coerce_bool(value)
                except ValueError:
                    stats[key] = bool(default)
            entry["stats"] = stats
        result[theme_id] = entry
    return result


def _normalize_presets(raw) -> dict[str, list[dict]]:
    """把任意 theme_presets 规范化为 base/nav 列表并剔除非法项。"""
    source = raw if isinstance(raw, dict) else {}
    result: dict[str, list[dict]] = {}
    for theme_id in THEME_IDS:
        builtin_ids = _default_preset_ids(theme_id)
        entries = source.get(theme_id)
        cleaned: list[dict] = []
        seen: set[str] = set()
        if isinstance(entries, list):
            for item in entries:
                if not isinstance(item, dict):
                    continue
                preset_id = str(item.get("id") or "").strip()
                if not PRESET_ID_RE.match(preset_id) or preset_id in seen:
                    continue
                name = str(item.get("name") or "").strip() or preset_id
                seen.add(preset_id)
                cleaned.append(
                    {
                        "id": preset_id,
                        "name": name[:MAX_PRESET_NAME_LEN],
                        "builtin": bool(item.get("builtin")) or preset_id in builtin_ids,
                    }
                )
        if not cleaned:
            cleaned = [dict(item) for item in DEFAULT_THEME_PRESETS[theme_id]]
        result[theme_id] = cleaned
    return result


def get_active_theme(db: Session) -> str:
    """读取当前启用主题；非法或缺失时回退 base（不写库）。"""
    raw = (get_setting(db, "active_theme") or "").strip()
    return raw if raw in THEME_IDS else "base"


def _config_from_db(db: Session) -> dict:
    """读取并规范化 theme_config（只读，不写库）。"""
    return _normalize_config(_load_json(get_setting(db, "theme_config")))


def _presets_from_db(db: Session) -> dict[str, list[dict]]:
    """读取并规范化 theme_presets（只读，不写库）。"""
    return _normalize_presets(_load_json(get_setting(db, "theme_presets")))


# ---------------- 状态初始化 ----------------
def ensure_theme_state(db: Session) -> None:
    """确保主题状态完整：合法 active_theme、配置/预设元数据、预设 CSS 文件。

    幂等，可重复调用；仅在内容发生变化时写库，已存在的预设文件不覆盖。
    """
    ensure_dirs()

    active = (get_setting(db, "active_theme") or "").strip()
    if active not in THEME_IDS:
        set_setting(db, "active_theme", "base")

    raw_config = _load_json(get_setting(db, "theme_config"))
    config = _normalize_config(raw_config)

    raw_presets = _load_json(get_setting(db, "theme_presets"))
    presets = _normalize_presets(raw_presets)

    for theme_id in THEME_IDS:
        for entry in presets[theme_id]:
            path = presets_root() / theme_id / f"{entry['id']}.css"
            if not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    render_default_preset_css(theme_id, entry["id"]),
                    encoding="utf-8",
                )
        ids = [entry["id"] for entry in presets[theme_id]]
        if config[theme_id]["default_preset"] not in ids:
            config[theme_id]["default_preset"] = ids[0]

    if config != raw_config:
        set_setting(db, "theme_config", _dump(config))
    if presets != raw_presets:
        set_setting(db, "theme_presets", _dump(presets))


# ---------------- 主题 / 预设查询 ----------------
def _read_theme_meta(theme_id: str) -> dict:
    """读取主题元信息；theme.json 缺失或损坏时使用内置默认。"""
    meta = {
        "id": theme_id,
        "name": THEME_NAMES[theme_id],
        "description": THEME_DESCRIPTIONS[theme_id],
        "version": THEME_VERSION,
    }
    path = themes_root() / theme_id / "theme.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data = None
        if isinstance(data, dict):
            for key in ("name", "description", "version"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    meta[key] = value.strip()
    return meta


def list_themes(db: Optional[Session] = None) -> list[dict]:
    """列出 base/nav 两套主题；传入 db 时附带 active 标记。"""
    active = get_active_theme(db) if db is not None else None
    themes: list[dict] = []
    for theme_id in THEME_IDS:
        meta = _read_theme_meta(theme_id)
        meta["has_preview"] = preview_path(theme_id) is not None
        if active is not None:
            meta["active"] = theme_id == active
        themes.append(meta)
    return themes


def list_presets(db: Session, theme_id: str) -> list[dict]:
    """列出某主题的全部预设（含 builtin/default 标记）。"""
    theme = require_theme(theme_id)
    config = _config_from_db(db)
    default_id = config[theme]["default_preset"]
    return [
        {**entry, "default": entry["id"] == default_id}
        for entry in _presets_from_db(db)[theme]
    ]


def get_preset(db: Session, theme_id: str, preset_id: str) -> Optional[dict]:
    """读取单个预设；不存在或 id 非法返回 None。"""
    theme = require_theme(theme_id)
    try:
        preset = validate_preset_id(preset_id)
    except ValueError:
        return None
    for entry in list_presets(db, theme):
        if entry["id"] == preset:
            return entry
    return None


# ---------------- 预设增删改 ----------------
def save_preset(
    db: Session,
    theme_id: str,
    preset_id: str,
    name: Optional[str],
    css_bytes: bytes,
) -> dict:
    """新增预设：校验主题/id/大小/编码/选择器后落盘并更新元数据。"""
    theme = require_theme(theme_id)
    preset = validate_preset_id(preset_id)

    raw = bytes(css_bytes or b"")
    if not raw.strip():
        raise ValueError("预设 CSS 内容为空")
    if len(raw) > MAX_PRESET_BYTES:
        raise ValueError("预设文件不能超过 256KB")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("预设 CSS 必须为 UTF-8 编码")

    marker = f'[data-preset="{preset}"]'
    if marker not in text:
        raise ValueError(f"预设 CSS 必须包含选择器 {marker}")

    presets = _presets_from_db(db)
    if any(entry["id"] == preset for entry in presets[theme]):
        raise PresetConflictError("预设 ID 已存在")

    display_name = (name or "").strip() or preset
    display_name = display_name[:MAX_PRESET_NAME_LEN]

    path = presets_root() / theme / f"{preset}.css"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)

    presets[theme].append({"id": preset, "name": display_name, "builtin": False})
    set_setting(db, "theme_presets", _dump(presets))
    return {"id": preset, "name": display_name, "builtin": False}


def delete_preset(db: Session, theme_id: str, preset_id: str) -> list[dict]:
    """删除预设；删除最后一个预设时抛 ValueError，删除默认预设时自动切换默认。"""
    theme = require_theme(theme_id)
    preset = validate_preset_id(preset_id)

    presets = _presets_from_db(db)
    entries = presets[theme]
    if not any(entry["id"] == preset for entry in entries):
        raise ValueError("预设不存在")
    if len(entries) <= 1:
        raise ValueError("每个主题至少保留一个预设，无法删除最后一个预设")

    remaining = [entry for entry in entries if entry["id"] != preset]
    presets[theme] = remaining

    path = presets_root() / theme / f"{preset}.css"
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        # 文件删除失败不应阻断元数据清理
        pass

    config = _config_from_db(db)
    if config[theme]["default_preset"] == preset:
        config[theme]["default_preset"] = remaining[0]["id"]
        set_setting(db, "theme_config", _dump(config))

    set_setting(db, "theme_presets", _dump(presets))
    return list_presets(db, theme)


def set_default_preset(db: Session, theme_id: str, preset_id: str) -> dict:
    """把某预设设为该主题的默认预设。"""
    theme = require_theme(theme_id)
    preset = validate_preset_id(preset_id)

    presets = _presets_from_db(db)
    if not any(entry["id"] == preset for entry in presets[theme]):
        raise ValueError("预设不存在")

    config = _config_from_db(db)
    config[theme]["default_preset"] = preset
    set_setting(db, "theme_config", _dump(config))
    return config[theme]


def set_active_theme(db: Session, theme_id: str) -> str:
    """切换启用主题（仅 base/nav），并清理静态服务缓存。"""
    theme = require_theme(theme_id)
    set_setting(db, "active_theme", theme)
    _invalidate_static_cache()
    return theme


def _invalidate_static_cache() -> None:
    """通知静态服务刷新 active_theme 缓存（延迟导入避免循环依赖）。"""
    try:
        from backend.app.static_server import invalidate_active_theme_cache

        invalidate_active_theme_cache()
    except Exception:  # noqa: BLE001 - 缓存清理失败不影响主流程
        pass


def update_theme_config(
    db: Session,
    theme_id: str,
    default_preset: Optional[str] = None,
    stats: Optional[dict] = None,
) -> dict:
    """更新主题配置：默认预设；导航主题额外支持统计开关。"""
    theme = require_theme(theme_id)
    config = _config_from_db(db)

    if default_preset is not None:
        preset = validate_preset_id(default_preset)
        presets = _presets_from_db(db)
        if not any(entry["id"] == preset for entry in presets[theme]):
            raise ValueError("预设不存在")
        config[theme]["default_preset"] = preset

    if stats is not None:
        if theme != "nav":
            raise ValueError("仅导航主题支持统计配置")
        if not isinstance(stats, dict):
            raise ValueError("统计配置格式不正确")
        merged = dict(config["nav"]["stats"])
        for key in DEFAULT_NAV_STATS:
            if key in stats:
                merged[key] = _coerce_bool(stats[key])
        config["nav"]["stats"] = merged

    set_setting(db, "theme_config", _dump(config))
    return config[theme]


def _coerce_bool(value) -> bool:
    """把 JSON 中的布尔值/常见字符串转换为 bool；无法识别时抛 ValueError。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError("统计配置必须为布尔值")


# ---------------- 公共 payload ----------------
def public_theme_payload(db: Session) -> dict:
    """公开主题配置：当前主题、主题列表、各主题预设与配置。"""
    config = _config_from_db(db)
    presets = _presets_from_db(db)
    active = get_active_theme(db)
    return {
        "active_theme": active,
        "themes": [
            {
                "id": meta["id"],
                "name": meta["name"],
                "description": meta["description"],
                "version": meta["version"],
            }
            for meta in list_themes()
        ],
        "presets": {
            theme_id: [
                {"id": entry["id"], "name": entry["name"]}
                for entry in presets[theme_id]
            ]
            for theme_id in THEME_IDS
        },
        "config": config,
    }


def nav_stats(db: Session) -> dict:
    """导航主题首页统计（公开口径：排除加密分类，避免泄露受保护内容）。

    - ``folders[].image_count``：加密分类为 ``None``（前端显示「—」）；
    - 总图片/浏览/下载/评论：仅统计不属于加密分类的已通过未删除内容。
    """
    locked_ids = select(Folder.id).where(Folder.password_hash.isnot(None))
    visible_scope = (
        Image.status == "approved",
        Image.is_deleted.is_(False),
        or_(Image.folder_id.is_(None), Image.folder_id.notin_(locked_ids)),
    )

    counts = dict(
        db.query(Image.folder_id, func.count(Image.id))
        .filter(
            Image.status == "approved",
            Image.is_deleted.is_(False),
            Image.folder_id.isnot(None),
        )
        .group_by(Image.folder_id)
        .all()
    )
    folders = db.query(Folder).order_by(Folder.sort_order, Folder.name).all()
    folder_items = []
    for folder in folders:
        locked = bool(folder.password_hash)
        folder_items.append(
            {
                "id": folder.id,
                "name": folder.name,
                "image_count": None if locked else int(counts.get(folder.id, 0)),
                "has_password": locked,
            }
        )

    total_images = db.query(func.count(Image.id)).filter(*visible_scope).scalar() or 0
    total_views = (
        db.query(func.coalesce(func.sum(Image.views), 0))
        .filter(*visible_scope)
        .scalar()
        or 0
    )
    total_downloads = (
        db.query(func.coalesce(func.sum(Image.downloads), 0))
        .filter(*visible_scope)
        .scalar()
        or 0
    )
    total_comments = (
        db.query(func.count(Comment.id))
        .join(Image, Comment.image_id == Image.id)
        .filter(Comment.status == "visible", *visible_scope)
        .scalar()
        or 0
    )

    return {
        "folder_count": len(folder_items),
        "folders": folder_items,
        "total_images": int(total_images),
        "total_views": int(total_views),
        "total_comments": int(total_comments),
        "total_downloads": int(total_downloads),
    }
