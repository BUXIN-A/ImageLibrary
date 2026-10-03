# -*- coding: utf-8 -*-
"""主题服务：内置主题枚举、自定义主题 ZIP 导入/导出/删除与文件路径解析。"""
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from backend.app.config import settings
from backend.app.themes import PRESET_THEMES

# 自定义主题 id 允许的字符与长度
_THEME_ID_RE = re.compile(r"^[a-z0-9_-]{2,32}$")
# ZIP 解压后允许的最大总字节数（防解压炸弹）
_MAX_ZIP_TOTAL = 5 * 1024 * 1024
# 允许出现在主题包中的扁平文件名
_ALLOWED_MEMBERS = {"theme.json", "theme.css", "preview.png"}

# 自定义主题根目录：data/themes/<id>/
_CUSTOM_THEMES_DIR = settings.DATA_DIR / "themes"


def _builtin_ids() -> set[str]:
    """全部内置主题 id 集合。"""
    return {item["id"] for item in PRESET_THEMES}


def _builtin_css_path(theme_id: str) -> Optional[Path]:
    """内置主题 CSS 路径：优先 frontend/themes，回退 admin/themes。"""
    for base in (settings.BASE_DIR / "frontend" / "themes", settings.BASE_DIR / "admin" / "themes"):
        path = base / f"{theme_id}.css"
        if path.exists():
            return path
    return None


def _builtin_preview_path(theme_id: str) -> Optional[Path]:
    """内置主题预览图路径（可选）。"""
    for base in (settings.BASE_DIR / "frontend" / "themes", settings.BASE_DIR / "admin" / "themes"):
        path = base / f"{theme_id}.png"
        if path.exists():
            return path
    return None


def theme_css_path(theme_id: str) -> Optional[Path]:
    """返回主题 CSS 文件路径；不存在返回 None。"""
    if theme_id in _builtin_ids():
        path = _builtin_css_path(theme_id)
        return path if path is not None and path.exists() else None
    path = _CUSTOM_THEMES_DIR / theme_id / "theme.css"
    return path if path.exists() else None


def theme_preview_path(theme_id: str) -> Optional[Path]:
    """返回主题预览图路径；不存在返回 None。"""
    if theme_id in _builtin_ids():
        return _builtin_preview_path(theme_id)
    path = _CUSTOM_THEMES_DIR / theme_id / "preview.png"
    return path if path.exists() else None


def _read_custom_meta(theme_dir: Path) -> Optional[dict]:
    """读取自定义主题的 theme.json，失败返回 None。"""
    meta_path = theme_dir / "theme.json"
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _theme_dict(theme_id: str, meta: dict, source: str, has_preview: bool) -> dict:
    """把主题元信息规范化为对外结构。"""
    return {
        "id": theme_id,
        "name": str(meta.get("name") or theme_id),
        "source": source,
        "author": str(meta.get("author") or ("内置" if source == "builtin" else "")),
        "version": str(meta.get("version") or ""),
        "description": str(meta.get("description") or ""),
        "has_preview": has_preview,
    }


def list_all_themes() -> list[dict]:
    """列出全部主题（内置在前，自定义在后）。"""
    themes: list[dict] = []
    for item in PRESET_THEMES:
        theme_id = item["id"]
        preview = _builtin_preview_path(theme_id)
        themes.append(
            _theme_dict(
                theme_id,
                {"name": item["name"], "author": "内置"},
                "builtin",
                preview is not None,
            )
        )

    if _CUSTOM_THEMES_DIR.exists():
        for theme_dir in sorted(_CUSTOM_THEMES_DIR.iterdir()):
            if not theme_dir.is_dir():
                continue
            meta = _read_custom_meta(theme_dir)
            if meta is None:
                continue
            themes.append(
                _theme_dict(
                    theme_dir.name,
                    meta,
                    "custom",
                    (theme_dir / "preview.png").exists(),
                )
            )
    return themes


def import_theme_zip(raw: bytes) -> dict:
    """导入自定义主题 ZIP 包，成功返回主题 dict，失败抛 ValueError（中文原因）。"""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            contents: dict[str, bytes] = {}
            total = 0
            for info in zf.infolist():
                name = info.filename
                # 防路径穿越：禁止目录项、绝对路径、.. 及不在白名单内的成员
                if name.endswith("/"):
                    raise ValueError("压缩包中不允许包含目录")
                if name not in _ALLOWED_MEMBERS:
                    raise ValueError(f"压缩包中包含不允许的文件：{name}")
                if name.startswith("/") or ".." in Path(name).parts or Path(name).is_absolute():
                    raise ValueError("压缩包中存在非法文件路径")
                total += info.file_size
                if total > _MAX_ZIP_TOTAL:
                    raise ValueError("压缩包解压后体积过大")
                contents[name] = zf.read(name)
    except zipfile.BadZipFile:
        raise ValueError("无效的 ZIP 文件")

    if "theme.json" not in contents:
        raise ValueError("缺少 theme.json")
    if "theme.css" not in contents:
        raise ValueError("缺少 theme.css")

    try:
        meta = json.loads(contents["theme.json"].decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ValueError("theme.json 不是合法的 JSON")
    if not isinstance(meta, dict):
        raise ValueError("theme.json 格式错误")

    theme_id = str(meta.get("id") or "").strip()
    name = str(meta.get("name") or "").strip()
    if not theme_id or not name:
        raise ValueError("theme.json 必须包含 id 与 name")
    if not _THEME_ID_RE.match(theme_id):
        raise ValueError("主题 id 只能由 2-32 位小写字母、数字、下划线或连字符组成")
    if theme_id in _builtin_ids():
        raise ValueError("主题 id 与内置主题冲突")
    if (_CUSTOM_THEMES_DIR / theme_id).exists():
        raise ValueError("该主题 id 已存在")

    css = contents["theme.css"].decode("utf-8", errors="ignore")
    marker = f'[data-theme="{theme_id}"]'
    if marker not in css:
        raise ValueError(f'theme.css 必须包含 {marker}')

    # 校验全部通过后才落盘，避免留下半成品
    _CUSTOM_THEMES_DIR.mkdir(parents=True, exist_ok=True)
    target = _CUSTOM_THEMES_DIR / theme_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "theme.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (target / "theme.css").write_text(css, encoding="utf-8")
    has_preview = "preview.png" in contents
    if has_preview:
        (target / "preview.png").write_bytes(contents["preview.png"])

    return _theme_dict(theme_id, meta, "custom", has_preview)


def delete_custom_theme(theme_id: str) -> None:
    """删除自定义主题；内置主题或不存在时抛 ValueError。"""
    if theme_id in _builtin_ids():
        raise ValueError("内置主题不可删除")
    target = _CUSTOM_THEMES_DIR / theme_id
    if not target.exists():
        raise ValueError("主题不存在")
    shutil.rmtree(target)


def export_theme_zip(theme_id: str) -> str:
    """把内置或自定义主题打包为临时 ZIP 文件并返回其路径；不存在抛 ValueError。"""
    if theme_id in _builtin_ids():
        builtin_name = next(
            (item["name"] for item in PRESET_THEMES if item["id"] == theme_id), theme_id
        )
        meta: dict = {"id": theme_id, "name": builtin_name, "author": "内置"}
        css_path = _builtin_css_path(theme_id)
        preview_path = _builtin_preview_path(theme_id)
    else:
        theme_dir = _CUSTOM_THEMES_DIR / theme_id
        meta = _read_custom_meta(theme_dir) or {}
        meta = {"id": theme_id, **meta}
        css_path = theme_dir / "theme.css"
        preview_path = theme_dir / "preview.png"

    if css_path is None or not css_path.exists():
        raise ValueError("主题不存在")

    fd, zip_path = tempfile.mkstemp(suffix=".zip", prefix=f"{theme_id}_theme_")
    os.close(fd)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("theme.json", json.dumps(meta, ensure_ascii=False, indent=2))
        zf.writestr("theme.css", css_path.read_text(encoding="utf-8"))
        if preview_path is not None and preview_path.exists():
            zf.write(preview_path, "preview.png")
    return zip_path
