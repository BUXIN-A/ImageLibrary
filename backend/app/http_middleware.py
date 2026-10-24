# -*- coding: utf-8 -*-
"""HTTP 中间件：选择性 GZip 与请求体大小限制。

- :class:`SelectiveGZipMiddleware`：对媒体/下载/Range 请求跳过压缩，
  避免破坏 ``206`` 的 ``Content-Range`` 语义与浪费 CPU。
- :class:`BodySizeLimitMiddleware`：在解析 multipart 之前按 ``Content-Length``
  快速拒绝超大请求，并在流式读取时累计字节数兜底。
"""
import json
from typing import Iterable, Optional

from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# 默认不做压缩的路径前缀/后缀
DEFAULT_EXCLUDED_PREFIXES = ("/media/", "/thumbnails/")
DEFAULT_EXCLUDED_SUFFIXES = ("/download",)


class SelectiveGZipMiddleware:
    """仅对非媒体请求启用 GZip 的中间件。

    ``Range`` 请求（含视频拖动）与媒体文件本身不压缩：
    压缩后 Starlette 会移除 ``Content-Length``，且与 ``Content-Range`` 冲突。
    """

    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        excluded_prefixes: Iterable[str] = DEFAULT_EXCLUDED_PREFIXES,
        excluded_suffixes: Iterable[str] = DEFAULT_EXCLUDED_SUFFIXES,
    ) -> None:
        self.app = app
        self._gzip = GZipMiddleware(app, minimum_size=minimum_size)
        self._prefixes = tuple(excluded_prefixes)
        self._suffixes = tuple(excluded_suffixes)

    def _should_skip(self, scope: Scope) -> bool:
        """媒体路径或携带 Range 的请求跳过压缩。"""
        path = scope.get("path", "") or ""
        if any(path.startswith(prefix) for prefix in self._prefixes):
            return True
        if any(path.endswith(suffix) for suffix in self._suffixes):
            return True
        headers = dict(scope.get("headers") or [])
        return b"range" in headers

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or self._should_skip(scope):
            await self.app(scope, receive, send)
            return
        await self._gzip(scope, receive, send)


class _BodyTooLarge(Exception):
    """请求体超过上限时抛出的内部异常。"""


class BodySizeLimitMiddleware:
    """限制单个 HTTP 请求体大小（默认 512 MB）。

    ``Content-Length`` 存在时在读取前直接拒绝；分块传输则在读取过程中累计，
    超过上限时若响应尚未开始，返回 ``413`` JSON。
    """

    def __init__(self, app: ASGIApp, max_bytes: Optional[int] = None) -> None:
        self.app = app
        self.max_bytes = int(max_bytes or 0)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self.max_bytes:
            await _send_413(send, self.max_bytes)
            return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            """累计请求体字节数，超限时中断本次请求处理。"""
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body") or b""
                received += len(body)
                if received > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message: Message) -> None:
            """记录响应是否已开始，避免重复发送响应。"""
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await _send_413(send, self.max_bytes)


async def _send_413(send: Send, max_bytes: int) -> None:
    """发送统一的 413 响应。"""
    body = json.dumps(
        {"detail": f"请求体过大（上限 {max_bytes} 字节）"}, ensure_ascii=False
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
