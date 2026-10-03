# -*- coding: utf-8 -*-
"""容器健康检查：请求 API 的 /api/health，成功退出码 0，失败为 1。"""
import os
import sys
import urllib.request

port = os.environ.get("API_PORT", "8080")
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
