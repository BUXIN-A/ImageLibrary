# -*- coding: utf-8 -*-
"""导出服务：把多张图片的原图打包为 ZIP 临时文件。"""
import os
import re
import tempfile
import zipfile
from pathlib import Path

from backend.app.config import settings

# ZIP 内条目名长度上限（保留扩展名）
_MAX_ARCNAME_LEN = 180
# 控制字符、文件系统非法字符与连续点
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_ILLEGAL_RE = re.compile(r'[<>:"|?*]')
_DOT_RUN_RE = re.compile(r"\.{2,}")
_SAFE_EXT_RE = re.compile(r"^\.[A-Za-z0-9]{1,10}$")


def cleanup_file(path: str) -> None:
    """删除临时文件（供 BackgroundTask 调用），忽略异常。"""
    try:
        os.remove(path)
    except OSError:
        pass


def _truncate(name: str, suffix: str) -> str:
    """按上限截断名称并保留扩展名。"""
    if len(name) <= _MAX_ARCNAME_LEN:
        return name
    keep = _MAX_ARCNAME_LEN - len(suffix)
    if keep <= 0:
        return name[:_MAX_ARCNAME_LEN]
    stem = name[:keep].rstrip(". ")
    if not stem:
        stem = "file"
    return f"{stem}{suffix}"


def _normalize_arcname(raw: str, image_id: int, fallback_ext: str = "") -> str:
    """把原始文件名转换为安全的 ZIP 内条目名（不含路径分隔符与危险段）。

    - ``\\`` 统一为 ``/`` 后只取最后一段，规避 ``../``、``..\\``、绝对路径与盘符；
    - 去除控制字符与文件系统非法字符，并压缩连续点；
    - 空名或非法名回退为 ``image_<id><ext>``。
    """
    text = _CONTROL_RE.sub("", (raw or "").replace("\\", "/"))
    base = text.split("/")[-1].strip()
    base = _ILLEGAL_RE.sub("_", base)
    base = base.lstrip("./").strip()
    base = _DOT_RUN_RE.sub(".", base)
    base = base.strip(". ")

    suffix = Path(base).suffix
    if suffix and not _SAFE_EXT_RE.match(suffix):
        suffix = ""
    if not suffix and _SAFE_EXT_RE.match(fallback_ext or ""):
        suffix = fallback_ext

    stem = base[: len(base) - len(suffix)] if suffix and base.endswith(suffix) else base
    stem = stem.strip(". ")
    if not stem or stem in (".", ".."):
        stem = f"image_{image_id}"
    return _truncate(f"{stem}{suffix}", suffix)


def _unique_arcname(arcname: str, image_id: int, used_names: set[str]) -> str:
    """保证 ZIP 内条目名唯一：重名时追加 ``{id}_`` 前缀或序号。"""
    if arcname.lower() not in used_names:
        used_names.add(arcname.lower())
        return arcname

    suffix = Path(arcname).suffix
    stem = arcname[: len(arcname) - len(suffix)] if suffix else arcname
    candidate = _truncate(f"{image_id}_{arcname}", suffix)
    counter = 2
    while candidate.lower() in used_names:
        candidate = _truncate(f"{image_id}_{counter}_{stem}{suffix}", suffix)
        counter += 1
    used_names.add(candidate.lower())
    return candidate


def build_zip_file(images: list, prefix: str = "images") -> str:
    """把给定图片的原图打包进临时 ZIP 文件并返回其路径。

    ZIP 内条目名统一经过安全化处理（禁止路径穿越），重名时自动追加序号；
    调用方负责用 ``FileResponse`` 返回并在 ``BackgroundTask`` 中删除该临时文件。
    """
    fd, zip_path = tempfile.mkstemp(suffix=".zip", prefix=f"{prefix}_")
    os.close(fd)

    used_names: set[str] = set()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for image in images:
            src = settings.UPLOAD_DIR / image.filename
            if not src.exists():
                continue
            fallback_ext = Path(image.filename or "").suffix
            arcname = _normalize_arcname(
                image.original_name or "", image.id, fallback_ext
            )
            arcname = _unique_arcname(arcname, image.id, used_names)
            zf.write(src, arcname=arcname)
    return zip_path
