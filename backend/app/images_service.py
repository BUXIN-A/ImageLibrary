# -*- coding: utf-8 -*-
"""图片处理服务：文件名安全化、上传校验、缩略图生成、EXIF 提取与文件清理。"""
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from backend.app.config import settings


def safe_filename(original_name: str) -> str:
    """根据原始文件名生成安全的存储文件名。

    绝不使用用户提供的原始文件名作为路径，改用 uuid4 十六进制串；
    扩展名取小写，若不在白名单内则回退为 ".bin"。
    """
    ext = Path(original_name or "").suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        ext = ".bin"
    return f"{uuid.uuid4().hex}{ext}"


def _first_value(sources: list[dict], tag_ids: tuple[int, ...]):
    """按优先级从多个 EXIF 来源中读取第一个非空值。"""
    for tag_id in tag_ids:
        for source in sources:
            try:
                value = source.get(tag_id)
            except Exception:  # noqa: BLE001 - EXIF 解析异常一律忽略
                value = None
            if value is not None and value != "":
                return value
    return None


def extract_exif(img) -> Optional[dict]:
    """提取 EXIF 信息（全部字符串化，缺失字段跳过，且不含 GPS）。

    返回 dict；若无任何可用字段则返回 None。
    """
    try:
        exif = img.getexif()
    except Exception:  # noqa: BLE001 - 无 EXIF 或格式不支持
        return None
    if not exif:
        return None

    # Exif 子 IFD 中存放了 DateTimeOriginal / 光圈 / 快门等字段
    try:
        exif_ifd = exif.get_ifd(0x8769)
    except Exception:  # noqa: BLE001
        exif_ifd = {}
    sources = [exif, exif_ifd]

    # 字段 -> 候选 tag id（按优先级）
    field_tags: dict[str, tuple[int, ...]] = {
        "taken_at": (36867, 306),  # DateTimeOriginal / DateTime
        "camera_make": (271,),
        "camera_model": (272,),
        "lens": (42036,),
        "iso": (34855,),
        "f_number": (33437,),
        "exposure_time": (33434,),
        "focal_length": (37386,),
        "orientation": (274,),
    }

    result: dict[str, str] = {}
    for key, tags in field_tags.items():
        value = _first_value(sources, tags)
        if value is not None:
            result[key] = str(value)
    return result or None


def process_upload(
    raw: bytes, original_name: str, max_size: Optional[int] = None
) -> dict:
    """校验并处理上传的图片字节。

    校验大小、扩展名与真实内容类型（用 Pillow 实际打开验证），
    生成安全文件名与 JPEG 缩略图（按 EXIF 方向自动纠正），并提取 EXIF。

    校验失败时抛出 ``ValueError``（消息为中文）；成功返回包含元数据的 dict。
    """
    limit = settings.MAX_UPLOAD_SIZE if max_size is None else max_size
    if len(raw) > limit:
        raise ValueError("文件过大")

    ext = Path(original_name or "").suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValueError("不支持的图片格式")

    # 用 Pillow 实际打开以验证内容类型
    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except Exception:  # noqa: BLE001 - 无法识别为图片
        raise ValueError("不支持的图片格式")

    img_format = img.format
    mime_type = Image.MIME.get(img_format) if img_format else None
    if not mime_type or mime_type not in settings.ALLOWED_MIME_TYPES:
        raise ValueError("不支持的图片格式")

    width, height = img.size

    # 生成文件与缩略图文件名
    settings.ensure_dirs()
    filename = safe_filename(original_name)
    thumb_name = f"{Path(filename).stem}_thumb.jpg"

    # 原图：按原始字节写入
    (settings.UPLOAD_DIR / filename).write_bytes(raw)

    # 缩略图：纠正 EXIF 方向 -> 缩放到最长边 -> 统一存为 JPEG
    try:
        thumb = ImageOps.exif_transpose(img)
        if thumb.mode == "P":
            thumb = thumb.convert("RGBA")
        if thumb.mode in ("RGBA", "LA"):
            background = Image.new("RGB", thumb.size, (255, 255, 255))
            background.paste(thumb, mask=thumb.split()[-1])
            thumb = background
        elif thumb.mode != "RGB":
            thumb = thumb.convert("RGB")
        thumb.thumbnail((settings.THUMBNAIL_SIZE, settings.THUMBNAIL_SIZE))
        thumb.save(settings.THUMBNAIL_DIR / thumb_name, format="JPEG", quality=85)
    except Exception:  # noqa: BLE001 - 缩略图失败不阻断原图落库
        (settings.THUMBNAIL_DIR / thumb_name).write_bytes(b"")

    return {
        "filename": filename,
        "thumb_name": thumb_name,
        "width": width,
        "height": height,
        "size": len(raw),
        "mime_type": mime_type,
        "exif": extract_exif(img),
    }


def delete_files(image) -> None:
    """删除图片对应的原图与缩略图文件；文件不存在或删除异常时忽略。"""
    for directory in (settings.UPLOAD_DIR, settings.THUMBNAIL_DIR):
        name = image.filename if directory == settings.UPLOAD_DIR else image.thumb_name
        if not name:
            continue
        try:
            path = directory / name
            if path.exists():
                path.unlink()
        except Exception:  # noqa: BLE001 - 清理失败不影响主流程
            pass
