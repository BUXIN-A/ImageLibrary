# -*- coding: utf-8 -*-
"""命令行工具：通过 ``python run.py <命令>`` 调用。

当前支持：

- ``clear-site-address``：清空后台已配置的全部站点地址（API / 后台专属 / 前台），
  恢复为按 ``PUBLIC_HOST`` 或访问主机自动推断。用于填错地址导致后台无法访问时的救援。
"""
from backend.app.database import SessionLocal
from backend.app.notify_service import CATEGORY_SITE, LEVEL_INFO, log
from backend.app.seed import init_seed
from backend.app.site_monitor import clear_site_addresses


def clear_site_address_command() -> int:
    """清空站点地址命令实现。"""
    # 确保数据目录/数据表/默认设置就绪
    init_seed()

    db = SessionLocal()
    try:
        cleared = clear_site_addresses(db)
        if not cleared:
            print("未配置任何站点地址，无需清空。")
            return 0
        detail = "；".join(f"{label}: {value}" for label, value in cleared)
        log(
            db,
            LEVEL_INFO,
            CATEGORY_SITE,
            "通过命令行清空站点地址",
            detail=detail,
        )
        print("已清空以下站点地址（恢复自动推断）：")
        for label, value in cleared:
            print(f"  - {label}: {value}")
        return 0
    finally:
        db.close()


# 命令名 -> 处理函数
COMMANDS = {
    "clear-site-address": clear_site_address_command,
    "clear-site": clear_site_address_command,
}


def run(argv: list[str]) -> int:
    """按命令行参数执行命令，返回进程退出码。"""
    if not argv:
        return 0
    name = argv[0]
    if name in ("-h", "--help", "help"):
        print("可用命令：")
        print("  clear-site-address  清空已配置的站点地址（API / 后台专属 / 前台）")
        return 0
    handler = COMMANDS.get(name)
    if handler is None:
        print(f"未知命令：{name}")
        print("可用命令：clear-site-address（使用 python run.py help 查看帮助）")
        return 1
    return handler()
