# -*- coding: utf-8 -*-
"""媒体处理服务：文件名安全化、上传校验、缩略图生成、EXIF 提取与文件清理。

支持两类媒体：
- 图片：用 Pillow 实际打开校验，生成 JPEG 缩略图并提取 EXIF；
- 视频：读取文件头做容器签名校验，不生成缩略图（由前端直接播放）。
"""
import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Optional

from PIL import Image, ImageOps

from backend.app.config import settings

# 流式写入分块大小（1 MB）
_CHUNK_SIZE = 1024 * 1024
# 视频容器签名校验所需的文件头长度（mp4 的 ftyp 位于 offset 4:8）
_VIDEO_HEADER_SIZE = 12

# 视频扩展名 -> MIME（用于落库与媒体路由 Content-Type）
_VIDEO_MIME_BY_EXT: dict[str, str] = {
    ".mp4": "video/mp4",
    ".m4v": "video/x-m4v",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".ogv": "video/ogg",
}


def _allowed_extensions() -> set[str]:
    """图片与视频扩展名并集。"""
    return set(settings.ALLOWED_IMAGE_EXTENSIONS) | set(settings.ALLOWED_VIDEO_EXTENSIONS)


def safe_filename(original_name: str) -> str:
    """根据原始文件名生成安全的存储文件名。

    绝不使用用户提供的原始文件名作为路径，改用 uuid4 十六进制串；
    扩展名取小写，若不在图片/视频白名单内则回退为 ".bin"。
    """
    ext = Path(original_name or "").suffix.lower()
    if ext not in _allowed_extensions():
        ext = ".bin"
    return f"{uuid.uuid4().hex}{ext}"


def _unlink(path: Path) -> None:
    """删除文件，不存在或删除失败时忽略。"""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _open_stream(upload_file) -> BinaryIO:
    """取得可同步读取的二进制流。

    FastAPI / Starlette 的 ``UploadFile`` 其 ``read`` 是协程，同步分块读取需
    回退到底层 ``.file``（SpooledTemporaryFile）；普通文件对象则原样使用。
    """
    stream = getattr(upload_file, "file", None)
    if stream is None or not hasattr(stream, "read"):
        stream = upload_file
    try:
        stream.seek(0)
    except (AttributeError, OSError, ValueError):
        pass
    return stream


def _write_stream_to_temp(stream: BinaryIO, temp_path: Path, limit: int) -> int:
    """按 1MB 分块把流写入临时文件，边写边计数，超限立即抛出 ``ValueError``。"""
    total = 0
    with open(temp_path, "wb") as handle:
        while True:
            chunk = stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            total += len(chunk)
            if total > limit:
                raise ValueError("文件过大")
            handle.write(chunk)
    return total


def _validate_video_header(path: Path, ext: str) -> None:
    """按扩展名校验视频容器签名；不匹配时抛出 ``ValueError``。"""
    with open(path, "rb") as handle:
        header = handle.read(_VIDEO_HEADER_SIZE)

    if ext in (".mp4", ".m4v", ".mov"):
        valid = len(header) >= 8 and header[4:8] == b"ftyp"
    elif ext == ".webm":
        valid = header[:4] == b"\x1aE\xdf\xa3"
    elif ext == ".ogv":
        valid = header[:4] == b"OggS"
    else:
        valid = False

    if not valid:
        raise ValueError("视频文件格式无效")


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


def _process_image_file(path: Path, filename: str, size: int) -> dict:
    """校验磁盘上的图片文件并生成缩略图，返回元数据。"""
    thumb_name = f"{Path(filename).stem}_thumb.jpg"
    thumb_path = settings.THUMBNAIL_DIR / thumb_name

    try:
        img = Image.open(path)
    except Exception:  # noqa: BLE001 - 无法识别为图片
        raise ValueError("不支持的图片格式")

    try:
        try:
            img.load()
        except Exception:  # noqa: BLE001 - 内容损坏
            raise ValueError("不支持的图片格式")

        img_format = img.format
        mime_type = Image.MIME.get(img_format) if img_format else None
        if not mime_type or mime_type not in settings.ALLOWED_IMAGE_MIME_TYPES:
            raise ValueError("不支持的图片格式")

        width, height = img.size

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
            thumb.save(thumb_path, format="JPEG", quality=85)
        except Exception:  # noqa: BLE001 - 缩略图失败不阻断原图落库
            thumb_path.write_bytes(b"")

        exif = extract_exif(img)
    except Exception:
        _unlink(thumb_path)
        raise
    finally:
        img.close()

    return {
        "filename": filename,
        "thumb_name": thumb_name,
        "width": width,
        "height": height,
        "size": size,
        "mime_type": mime_type,
        "exif": exif,
    }


def process_upload_stream(
    upload_file, original_name: str, max_size: Optional[int] = None
) -> dict:
    """流式校验并处理上传的图片或视频。

    ``upload_file`` 可为 FastAPI ``UploadFile`` 或任何带 ``read(size)`` 的文件对象。
    文件按 1MB 分块写入临时文件，超过大小上限立即中止；
    图片用 Pillow 校验并生成缩略图，视频校验容器签名后直接保存。

    校验失败或异常时删除临时文件与已写入的目标文件，并抛出 ``ValueError``
    （消息为中文）；成功返回包含元数据的 dict。
    """
    ext = Path(original_name or "").suffix.lower()
    image_exts = set(settings.ALLOWED_IMAGE_EXTENSIONS)
    video_exts = set(settings.ALLOWED_VIDEO_EXTENSIONS)
    if ext not in image_exts and ext not in video_exts:
        raise ValueError("不支持的图片或视频格式")

    is_video = ext in video_exts
    if max_size is None:
        limit = settings.MAX_VIDEO_UPLOAD_SIZE if is_video else settings.MAX_UPLOAD_SIZE
    else:
        limit = max_size

    settings.ensure_dirs()
    filename = safe_filename(original_name)
    target_path = settings.UPLOAD_DIR / filename
    temp_path = settings.UPLOAD_DIR / f".{uuid.uuid4().hex}.part"
    thumb_name = ""

    try:
        size = _write_stream_to_temp(_open_stream(upload_file), temp_path, limit)

        if is_video:
            _validate_video_header(temp_path, ext)
            info = {
                "filename": filename,
                "thumb_name": "",
                "width": 0,
                "height": 0,
                "size": size,
                "mime_type": _VIDEO_MIME_BY_EXT[ext],
                "exif": None,
            }
        else:
            info = _process_image_file(temp_path, filename, size)

        thumb_name = info["thumb_name"]
        os.replace(temp_path, target_path)
    except Exception:
        _unlink(temp_path)
        _unlink(target_path)
        if thumb_name:
            _unlink(settings.THUMBNAIL_DIR / thumb_name)
        raise

    return info


def process_upload(
    raw: bytes, original_name: str, max_size: Optional[int] = None
) -> dict:
    """兼容接口：接收整段字节，内部转为内存流调用 :func:`process_upload_stream`。"""
    return process_upload_stream(BytesIO(raw), original_name, max_size=max_size)


def delete_files(image) -> None:
    """删除媒体对应的原图与缩略图文件（无缩略图时跳过）；异常忽略。"""
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
