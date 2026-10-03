# -*- coding: utf-8 -*-
"""站点地址可用性检测与清理。

启动时（由 ``site_check_on_startup`` 开关控制）检测后台已配置的站点地址：

- 提供 ``clear_site_addresses()`` 供命令行「清空站点地址」复用。

检测采用「折中」策略：**仅在明确失败时清空配置**，不确定的情况只记录告警：

- 明确失败（清空）：连上了但响应异常（HTTP 非 2xx、接口返回内容不对）、连接被拒绝/端口不通。
- 不确定（仅告警、不清空）：域名解析失败、连接超时、网络不可达等。
"""
import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.notify_service import CATEGORY_SITE, LEVEL_ERROR, LEVEL_INFO, LEVEL_WARNING, log
from backend.app.seed import get_bool_setting, get_setting, set_setting

# 单次探测超时（秒）
PROBE_TIMEOUT = 5.0
# 站点地址设置键 -> 显示名
ADDRESS_LABELS = {
    "api_base_url": "API 站点地址",
    "admin_api_base_url": "后台专属 API 站点地址",
    "frontend_base_url": "前台站点地址",
}
# 探测方式：API 类地址校验 /api/health，前台地址仅校验根路径可达
API_ADDRESS_KEYS = ("api_base_url", "admin_api_base_url")
FRONTEND_ADDRESS_KEYS = ("frontend_base_url",)


@dataclass
class ProbeResult:
    """探测结果。

    ``explicit`` 表示是否为「明确失败」（可据此清空配置）。
    """

    ok: bool
    explicit: bool
    detail: str


def _probe(url: str, expect_json: bool, timeout: float = PROBE_TIMEOUT) -> ProbeResult:
    """对给定 URL 发起 GET 探测，返回可用性判定。"""
    request = urllib.request.Request(
        url, headers={"User-Agent": "ImageLibrary-SiteCheck"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            status = resp.status
            body = resp.read(8192)
    except urllib.error.HTTPError as exc:
        # 有 HTTP 响应但状态码异常：明确失败
        return ProbeResult(False, True, f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ConnectionRefusedError):
            return ProbeResult(False, True, "连接被拒绝（端口未开放）")
        if isinstance(reason, socket.gaierror):
            return ProbeResult(False, False, "域名解析失败")
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return ProbeResult(False, False, "连接超时")
        return ProbeResult(False, False, f"网络不可达：{reason}")
    except (socket.timeout, TimeoutError):
        return ProbeResult(False, False, "连接超时")
    except OSError as exc:
        # 其它套接字错误：保守视为不确定
        return ProbeResult(False, False, f"网络错误：{exc}")

    if status < 200 or status >= 400:
        return ProbeResult(False, True, f"HTTP {status}")

    if expect_json:
        try:
            data = json.loads(body.decode("utf-8", "ignore"))
        except ValueError:
            return ProbeResult(False, True, "响应不是有效 JSON")
        if not isinstance(data, dict) or data.get("status") != "ok":
            return ProbeResult(False, True, "接口返回内容异常")

    return ProbeResult(True, False, "正常")


def probe_address(base_url: str, is_api: bool, timeout: float = PROBE_TIMEOUT) -> ProbeResult:
    """探测单个站点地址：API 类校验 ``/api/health``，其它校验根路径。"""
    base = (base_url or "").rstrip("/")
    if is_api:
        return _probe(base + "/api/health", expect_json=True, timeout=timeout)
    return _probe(base + "/", expect_json=False, timeout=timeout)


def clear_site_addresses(db: Session) -> list[tuple[str, str]]:
    """清空全部已配置的站点地址，返回被清空的 (显示名, 原值) 列表。"""
    cleared: list[tuple[str, str]] = []
    for key, label in ADDRESS_LABELS.items():
        value = (get_setting(db, key, "") or "").strip()
        if value:
            set_setting(db, key, "")
            cleared.append((label, value))
    return cleared


def check_site_addresses(db: Session, timeout: float = PROBE_TIMEOUT) -> list[dict]:
    """检测已配置的站点地址，按折中策略处理并写入通知。

    返回每项检测结果（含 key/label/value/ok/detail/cleared）。
    """
    results: list[dict] = []
    for key, label in ADDRESS_LABELS.items():
        value = (get_setting(db, key, "") or "").strip()
        if not value:
            continue

        is_api = key in API_ADDRESS_KEYS
        result = probe_address(value, is_api, timeout=timeout)
        cleared = False
        if not result.ok and result.explicit:
            # 明确失败：清空配置，回退自动推断
            set_setting(db, key, "")
            cleared = True
            log(
                db,
                LEVEL_ERROR,
                CATEGORY_SITE,
                f"{label}不可用，已清空并回退自动推断：{value}",
                detail=result.detail,
            )
        elif not result.ok:
            # 不确定：只告警，不清空
            log(
                db,
                LEVEL_WARNING,
                CATEGORY_SITE,
                f"{label}暂时无法确认可用（未清空）：{value}",
                detail=result.detail,
            )

        results.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "ok": result.ok,
                "explicit": result.explicit,
                "detail": result.detail,
                "cleared": cleared,
            }
        )

    if not results:
        log(db, LEVEL_INFO, CATEGORY_SITE, "未配置自定义站点地址，使用自动推断")
        return results

    if all(item["ok"] for item in results):
        summary = "；".join(f"{item['label']}={item['value']}" for item in results)
        log(db, LEVEL_INFO, CATEGORY_SITE, f"站点地址检测通过（{len(results)} 项）", detail=summary)

    return results


def run_startup_check(db: Optional[Session] = None) -> list[dict]:
    """启动自检入口：读取开关，必要时执行检测（异常不外抛）。"""
    from backend.app.database import SessionLocal

    own_session = db is None
    session: Session = db or SessionLocal()
    try:
        if not get_bool_setting(session, "site_check_on_startup", True):
            return []
        return check_site_addresses(session)
    finally:
        if own_session:
            session.close()
