# -*- coding: utf-8 -*-
"""受控媒体路由：原图 `/media/{filename}` 与缩略图 `/thumbnails/{filename}`。

访问规则由 :mod:`backend.app.media_service` 统一判定：
公开图片可直接访问；审核中/已拒绝/回收站图片需要后台签名令牌；
加密分类图片还需要该分类的解锁令牌。所有未授权情况统一返回 404。
"""
import hashlib
import os
from email.utils import formatdate
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.media_service import authorize_media
from backend.app.models import Image

router = APIRouter(tags=["media"])

_CHUNK_SIZE = 64 * 1024
_CACHE_PUBLIC = "public, max-age=300"
_CACHE_PRIVATE = "private, max-age=300"


def _not_found() -> HTTPException:
    """统一的 404，避免通过状态码泄露文件是否存在。"""
    return HTTPException(status_code=404, detail="文件不存在")


def _safe_filename(filename: str) -> bool:
    """文件名安全校验：拒绝路径分隔符、上跳与绝对路径。"""
    if not filename or filename in (".", ".."):
        return False
    if "\x00" in filename or "/" in filename or "\\" in filename:
        return False
    if ".." in filename:
        return False
    if os.path.isabs(filename):
        return False
    return Path(filename).name == filename


def _resolve_file(base: Path, filename: str) -> Optional[Path]:
    """把文件名解析到基准目录内，越界或不存在时返回 None。"""
    try:
        base_dir = base.resolve()
        path = (base_dir / filename).resolve()
    except OSError:
        return None
    if not path.is_relative_to(base_dir):
        return None
    if not path.is_file():
        return None
    return path


def _build_etag(kind: str, filename: str, stat: os.stat_result) -> str:
    """由类型、文件名、大小与纳秒级修改时间生成强 ETag。"""
    raw = f"{kind}:{filename}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
    return '"' + hashlib.sha256(raw).hexdigest()[:32] + '"'


def _etag_matches(header: Optional[str], etag: str) -> bool:
    """判断 If-None-Match 是否命中当前 ETag（支持弱比较与 *）。"""
    if not header:
        return False
    for item in header.split(","):
        candidate = item.strip()
        if not candidate:
            continue
        if candidate == "*":
            return True
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == etag:
            return True
    return False


def _parse_range(range_header: str, size: int) -> tuple[int, int]:
    """解析单段 Range（bytes=start-end / start- / -suffix），返回闭区间。

    语法非法或范围不可满足时抛出 ValueError，由调用方返回 416。
    """
    if not range_header.startswith("bytes="):
        raise ValueError("unsupported range unit")
    spec = range_header[len("bytes="):].strip()
    if not spec or "," in spec:
        raise ValueError("only single range supported")
    if "-" not in spec:
        raise ValueError("invalid range")

    start_text, end_text = spec.split("-", 1)
    start_text = start_text.strip()
    end_text = end_text.strip()

    if not start_text:
        # 后缀区间：bytes=-N 表示最后 N 个字节
        if not end_text.isdigit():
            raise ValueError("invalid suffix range")
        suffix = int(end_text)
        if suffix <= 0 or size <= 0:
            raise ValueError("unsatisfiable suffix range")
        start = max(0, size - suffix)
        return start, size - 1

    if not start_text.isdigit():
        raise ValueError("invalid range start")
    start = int(start_text)
    if not end_text:
        if start >= size:
            raise ValueError("range start out of bounds")
        return start, size - 1
    if not end_text.isdigit():
        raise ValueError("invalid range end")
    end = int(end_text)
    if start > end:
        raise ValueError("range start greater than end")
    if start >= size:
        raise ValueError("range start out of bounds")
    return start, min(end, size - 1)


def _iter_file(path: Path, start: int, length: Optional[int]):
    """分块读取文件，避免大文件/视频整体载入内存。"""
    remaining = length
    with open(path, "rb") as handle:
        handle.seek(start)
        while remaining is None or remaining > 0:
            size = _CHUNK_SIZE if remaining is None else min(_CHUNK_SIZE, remaining)
            if size <= 0:
                break
            chunk = handle.read(size)
            if not chunk:
                break
            yield chunk
            if remaining is not None:
                remaining -= len(chunk)


def _serve(
    kind: str,
    filename: str,
    request: Request,
    db: Session,
    access: Optional[str],
    folder_token: Optional[str],
) -> Response:
    """公共处理逻辑：查找记录、授权、缓存协商与范围响应。"""
    if not _safe_filename(filename):
        raise _not_found()

    if kind == "thumb":
        image = db.query(Image).filter(Image.thumb_name == filename).first()
        base_dir = settings.THUMBNAIL_DIR
    else:
        image = db.query(Image).filter(Image.filename == filename).first()
        base_dir = settings.UPLOAD_DIR

    if image is None or not authorize_media(image, access, folder_token):
        raise _not_found()

    # 仅在确认图片记录存在后读取 MIME，避免在空记录上访问属性
    content_type = (
        "image/jpeg"
        if kind == "thumb"
        else (image.mime_type or "application/octet-stream")
    )

    path = _resolve_file(base_dir, filename)
    if path is None:
        raise _not_found()

    stat = path.stat()
    etag = _build_etag(kind, filename, stat)
    last_modified = formatdate(stat.st_mtime, usegmt=True)
    cache_control = _CACHE_PRIVATE if (access or folder_token) else _CACHE_PUBLIC
    common_headers = {
        "ETag": etag,
        "Last-Modified": last_modified,
        "Cache-Control": cache_control,
        "Accept-Ranges": "bytes",
    }

    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=common_headers)

    range_header = request.headers.get("range")
    if range_header:
        try:
            start, end = _parse_range(range_header, stat.st_size)
        except ValueError:
            return Response(
                status_code=416,
                headers={
                    **common_headers,
                    "Content-Range": f"bytes */{stat.st_size}",
                },
            )
        length = end - start + 1
        headers = {
            **common_headers,
            "Content-Range": f"bytes {start}-{end}/{stat.st_size}",
            "Content-Length": str(length),
        }
        if request.method == "HEAD":
            return Response(
                status_code=206, media_type=content_type, headers=headers
            )
        return StreamingResponse(
            _iter_file(path, start, length),
            status_code=206,
            media_type=content_type,
            headers=headers,
        )

    headers = {**common_headers, "Content-Length": str(stat.st_size)}
    if request.method == "HEAD":
        return Response(status_code=200, media_type=content_type, headers=headers)
    return StreamingResponse(
        _iter_file(path, 0, stat.st_size),
        media_type=content_type,
        headers=headers,
    )


@router.api_route("/media/{filename}", methods=["GET", "HEAD"], include_in_schema=False)
def get_media(
    filename: str,
    request: Request,
    access: Optional[str] = Query(None),
    folder_token: Optional[str] = Query(None),
    x_folder_token: Optional[str] = Header(None, alias="X-Folder-Token"),
    db: Session = Depends(get_db),
) -> Response:
    """返回受控原图（支持 ETag/304 与单段 Range）。"""
    return _serve(
        "media", filename, request, db, access, folder_token or x_folder_token
    )


@router.api_route(
    "/thumbnails/{filename}", methods=["GET", "HEAD"], include_in_schema=False
)
def get_thumbnail(
    filename: str,
    request: Request,
    access: Optional[str] = Query(None),
    folder_token: Optional[str] = Query(None),
    x_folder_token: Optional[str] = Header(None, alias="X-Folder-Token"),
    db: Session = Depends(get_db),
) -> Response:
    """返回受控缩略图（支持 ETag/304 与单段 Range）。"""
    return _serve(
        "thumb", filename, request, db, access, folder_token or x_folder_token
    )
