"""
db/config.py - 数据库配置中心（统一访问层的配置）

后端选择（.env）：
  DB_BACKEND  - sqlite | noco
                - 显式设置则按设置取值（非法值回退 sqlite）
                - 未设置时智能默认：检测到 NOCO_TOKEN 已配置 → noco；否则 sqlite
  SQLITE_PATH - sqlite 数据库文件路径（默认 data/db/foxmeido.db）

noco 后端配置（仅 DB_BACKEND=noco 时生效）：
  NOCO_URL             - NocoDB API 地址 (https://127.0.0.1:52533/api/v2/tables)
  NOCO_TOKEN           - NocoDB API Token (必填)
  NOCO_ACCOUNT_TABLE   - account 表格 ID (必填)
  NOCO_RECORD_TABLE    - record 表格 ID (必填)
  NOCO_REMAIN_TABLE    - remain 表格 ID (必填)
  NOCO_WISHLIST_TABLE  - wishlist 表格 ID (必填)
  NOCO_VERIFY_SSL      - 是否验证 SSL (true/false, 默认 false)

通用配置（两个后端共用）：
  NOCO_CHECK_REMAIN    - get 指令是否检查 remain 表剩余副本数（默认 true）
  HTTP_PROXY           - HTTP 代理地址（默认空 = 不使用代理）
  HTTPS_PROXY          - HTTPS 代理地址（默认空 = 跟随 HTTP_PROXY）
  STEAM_COOKIE         - Steam 登录 Cookie（wish 用）
  STEAM_CC             - Steam 国家/地区码（steam_utils 用）
  CURATOR_ID           - Steam 鉴赏家 ID（curator_monitor / unreported 用）
"""

from __future__ import annotations

import os
from typing import Any

from plugins.env_utils import _read_dotenv, get_http_proxy, get_proxies, _env_bool


# 项目根目录：此文件位于 plugins/db/，往上级 2 层
_PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


# ── 后端选择 ────────────────────────────────────────────────────
_SUPPORTED_BACKENDS: tuple[str, ...] = ("sqlite", "noco")


def _resolve_backend() -> str:
    """解析 DB_BACKEND：显式设置优先，未设置时智能默认。"""
    raw = _read_dotenv("DB_BACKEND") or ""
    if raw:
        backend = raw.strip().lower()
        if backend in _SUPPORTED_BACKENDS:
            return backend
        print(f"[CONFIG] 警告: DB_BACKEND={raw!r} 非法，回退到 sqlite")
        return "sqlite"
    # 智能默认：已有 NocoDB 配置的老用户升级无感知
    if _read_dotenv("NOCO_TOKEN"):
        return "noco"
    return "sqlite"


BACKEND: str = _resolve_backend()

# ── sqlite 后端配置 ─────────────────────────────────────────────
SQLITE_PATH: str = (
    _read_dotenv("SQLITE_PATH")
    or os.path.join(_PROJECT_ROOT, "data", "db", "foxmeido.db")
)

# ── NocoDB 连接 ─────────────────────────────────────────────
NOCO_URL: str = _read_dotenv("NOCO_URL") or "https://127.0.0.1:52533/api/v2/tables"
NOCO_TOKEN: str = _read_dotenv("NOCO_TOKEN") or ""

# ── 表格 ID（仅 noco 后端使用） ─────────────────────────────
ACCOUNT_TABLE_ID: str = _read_dotenv("NOCO_ACCOUNT_TABLE") or ""
RECORD_TABLE_ID: str = _read_dotenv("NOCO_RECORD_TABLE") or ""
REMAIN_TABLE_ID: str = _read_dotenv("NOCO_REMAIN_TABLE") or ""
WISHLIST_TABLE_ID: str = _read_dotenv("NOCO_WISHLIST_TABLE") or ""

# ── 功能开关 ────────────────────────────────────────────
CHECK_REMAIN: bool = _env_bool("NOCO_CHECK_REMAIN", "true")

print(f"[CONFIG] DB_BACKEND={BACKEND!r}")
print(f"[CONFIG] SQLITE_PATH={SQLITE_PATH!r}")
print(f"[CONFIG] NOCO_URL={NOCO_URL!r}")
print(f"[CONFIG] ACCOUNT_TABLE_ID={ACCOUNT_TABLE_ID!r}")
print(f"[CONFIG] RECORD_TABLE_ID={RECORD_TABLE_ID!r}")
print(f"[CONFIG] REMAIN_TABLE_ID={REMAIN_TABLE_ID!r}")
print(f"[CONFIG] CHECK_REMAIN={CHECK_REMAIN!r}")
print(f"[CONFIG] WISHLIST_TABLE_ID={WISHLIST_TABLE_ID!r}")

# ── 请求通用配置 ─────────────────────────────────────────────
HEADERS: dict[str, str] = {"xc-token": NOCO_TOKEN}
VERIFY_SSL: bool = _env_bool("NOCO_VERIFY_SSL", "false")

# ── 模块级常量（兼容旧代码，但优先使用 env_utils 的函数）───
# 注意：这些在模块导入时求值，如果 dotenv 尚未加载则可能为空。
HTTP_PROXY: str = _read_dotenv("HTTP_PROXY") or ""
HTTPS_PROXY: str = _read_dotenv("HTTPS_PROXY") or ""
# 同步
if HTTP_PROXY and not HTTPS_PROXY:
    HTTPS_PROXY = HTTP_PROXY
elif HTTPS_PROXY and not HTTP_PROXY:
    HTTP_PROXY = HTTPS_PROXY

PROXIES: dict[str, str] = {}
if HTTP_PROXY:
    PROXIES["http"] = HTTP_PROXY
    PROXIES["https"] = HTTPS_PROXY

# ── Steam ────────────────────────────────────────────────────
STEAM_COOKIE: str = _read_dotenv("STEAM_COOKIE") or ""
STEAM_CC: str = _read_dotenv("STEAM_CC") or ""
CURATOR_ID: int = int(_read_dotenv("CURATOR_ID") or "0")


# ── 便捷函数（noco 后端与迁移脚本使用） ─────────────────────
def table_url(table_id: str) -> str:
    """拼接指定表格的完整 API URL。"""
    return f"{NOCO_URL}/{table_id}/records"


def url_with_filter(table_id: str, where: str, sort: str = "") -> str:
    """拼接带过滤条件的查询 URL。"""
    base = table_url(table_id)
    params = f"where={where}"
    if sort:
        params += f"&sort={sort}"
    return f"{base}?{params}"


def request_kwargs(extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    """返回共用的 requests 参数字典。"""
    kwargs: dict[str, Any] = {
        "headers": {**HEADERS, **(extra_headers or {})},
    }
    if not VERIFY_SSL:
        kwargs["verify"] = False
    return kwargs


def post_kwargs(extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    """返回 POST/PATCH 共用的参数字典（含 Content-Type）。"""
    return request_kwargs(
        extra_headers={"Content-Type": "application/json", **(extra_headers or {})}
    )
