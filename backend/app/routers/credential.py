# -*- coding: utf-8 -*-
"""凭证上传路由：凭上传 Token 提交图片（需审核），含按 IP 限流。"""
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.deps import client_ip, validate_upload_token
from backend.app.images_service import process_upload
from backend.app.models import Image, now
from backend.app.ratelimit import upload_limiter

router = APIRouter(prefix="/api/credential", tags=["credential"])


@router.get("/validate")
def validate_token(
    token: str = Query(""), db: Session = Depends(get_db)
) -> dict:
    """校验上传 Token 并返回剩余额度等信息。"""
    token_obj, reason = validate_upload_token(token, db)
    if token_obj is None:
        return {"valid": False, "reason": reason, "note": None, "remaining": None, "max_file_size": None}
    remaining = (
        None
        if token_obj.max_uploads is None
        else max(token_obj.max_uploads - token_obj.used_uploads, 0)
    )
    return {
        "valid": True,
        "reason": None,
        "note": token_obj.note,
        "remaining": remaining,
        "max_file_size": token_obj.max_file_size,
    }


@router.post("/upload")
async def credential_upload(
    request: Request,
    token: str = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """凭 Token 上传图片：先限流，再校验 Token，逐文件处理，状态为 pending。"""
    # 1) 按客户端 IP 限流
    ip = client_ip(request)
    if not upload_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="上传过于频繁，请稍后再试")

    # 2) 校验 Token
    token_obj, reason = validate_upload_token(token, db)
    if token_obj is None:
        raise HTTPException(status_code=400, detail=reason or "Token 无效")

    # 3) 逐文件处理
    results: list[dict] = []
    success = 0
    failed = 0
    for upload in files:
        # 单文件即会让上传数超额时中止
        if token_obj.max_uploads is not None and token_obj.used_uploads >= token_obj.max_uploads:
            results.append(
                {
                    "filename": upload.filename or "",
                    "ok": False,
                    "error": "Token 上传次数已用尽",
                }
            )
            failed += 1
            continue

        raw = await upload.read()
        original_name = upload.filename or ""
        try:
            info = process_upload(raw, original_name, max_size=token_obj.max_file_size)
            image = Image(
                filename=info["filename"],
                original_name=original_name,
                title=None,
                description=None,
                mime_type=info["mime_type"],
                size=info["size"],
                width=info["width"],
                height=info["height"],
                thumb_name=info["thumb_name"],
                folder_id=None,
                status="pending",
                exif=info["exif"],
                uploaded_by=token_obj.id,
            )
            db.add(image)
            token_obj.used_uploads += 1
            token_obj.last_used_at = now()
            db.commit()
            db.refresh(image)
            results.append({"filename": original_name, "ok": True, "error": None, "id": image.id})
            success += 1
        except ValueError as exc:
            db.rollback()
            results.append({"filename": original_name, "ok": False, "error": str(exc)})
            failed += 1
        except Exception:  # noqa: BLE001 - 单文件异常不影响其它文件
            db.rollback()
            results.append({"filename": original_name, "ok": False, "error": "处理失败"})
            failed += 1

    return {
        "results": results,
        "success": success,
        "failed": failed,
        "message": "已提交，等待管理员审核",
    }
