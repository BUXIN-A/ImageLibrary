# -*- coding: utf-8 -*-
"""进程内滑动窗口限流器（线程安全，适配单进程部署）。"""
import threading
import time
from collections import defaultdict, deque
from typing import Optional

from backend.app.config import settings


class SlidingWindowLimiter:
    """基于滑动时间窗口的请求计数器。

    以 ``time.monotonic()`` 记录每次命中时间，窗口内命中次数达到阈值即拒绝。
    所有操作均在锁内完成，保证多线程（含 uvicorn 工作线程）下安全。
    """

    def __init__(
        self,
        window_seconds: Optional[int] = None,
        max_requests: Optional[int] = None,
    ) -> None:
        self.window_seconds = (
            window_seconds
            if window_seconds is not None
            else settings.RATE_LIMIT_WINDOW_SECONDS
        )
        self.max_requests = (
            max_requests
            if max_requests is not None
            else settings.RATE_LIMIT_MAX_REQUESTS
        )
        self._lock = threading.Lock()
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """判断 key（通常为客户端 IP）是否允许本次请求，并记录命中。"""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True


# 模块级单例：凭证上传限流
upload_limiter = SlidingWindowLimiter()
