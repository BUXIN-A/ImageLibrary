# -*- coding: utf-8 -*-
"""导出服务：把多张图片的原图打包为 ZIP 临时文件。"""
import os
import tempfile
import zipfile

from backend.app.config import settings


def cleanup_file(path: str) -> None:
    """删除临时文件（供 BackgroundTask 调用），忽略异常。"""
    try:
        os.remove(path)
    except OSError:
        pass


def build_zip_file(images: list, prefix: str = "images") -> str:
    """把给定图片的原图打包进临时 ZIP 文件并返回其路径。

    文件重名时以 ``{id}_{filename}`` 命名以避免冲突；
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
            arcname = image.original_name or image.filename
            if arcname in used_names:
                arcname = f"{image.id}_{image.original_name or image.filename}"
            used_names.add(arcname)
            zf.write(src, arcname=arcname)
    return zip_path
