# -*- coding: utf-8 -*-
"""一键启动脚本：同时拉起 API、前台静态站与后台静态站三个服务。"""
import sys
import threading
from pathlib import Path

import uvicorn

# 将项目根目录加入 sys.path，确保可作为脚本直接运行
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.main import app as api_app  # noqa: E402
from backend.app.static_server import create_static_app  # noqa: E402


def _serve(app, host: str, port: int) -> None:
    """在子线程中运行给定的 ASGI 应用。"""
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _print_banner() -> None:
    """打印三个服务的访问地址横幅。"""
    host = settings.HOST
    print("=" * 56)
    print("  ImageLibrary 已启动")
    print(f"  API      : http://{host}:{settings.API_PORT}")
    print(f"  前台站点 : http://{host}:{settings.FRONTEND_PORT}")
    print(f"  管理后台 : http://{host}:{settings.ADMIN_PORT}")
    print("  按 Ctrl+C 停止全部服务")
    print("=" * 56)


def main() -> None:
    """启动三个服务：前台/后台静态站运行于守护线程，API 运行于主线程。"""
    frontend_app = create_static_app(str(ROOT / "frontend"), site_routes=True)
    admin_app = create_static_app(str(ROOT / "admin"), admin_config=True)

    threading.Thread(
        target=_serve,
        args=(frontend_app, settings.HOST, settings.FRONTEND_PORT),
        daemon=True,
    ).start()
    threading.Thread(
        target=_serve,
        args=(admin_app, settings.HOST, settings.ADMIN_PORT),
        daemon=True,
    ).start()

    _print_banner()
    try:
        uvicorn.run(api_app, host=settings.HOST, port=settings.API_PORT)
    except KeyboardInterrupt:
        print("已停止")


if __name__ == "__main__":
    # 支持以命令行方式执行管理命令，如：python run.py clear-site-address
    from backend.app import cli

    if sys.argv[1:]:
        sys.exit(cli.run(sys.argv[1:]))
    main()
