"""
noco_config.py - NocoDB 配置中心

所有 NocoDB 相关的常量统一从环境变量读取。
可配置在 .env 文件中（已 gitignore），无需逐个修改脚本。

通用工具（_read_dotenv / get_proxies / get_http_proxy）已移至
``plugins.env_utils``，此处仅重新导出。

可用环境变量及默认值：
  NOCO_URL             - NocoDB API 地址 (https://127.0.0.1:52533/api/v2/tables)
  NOCO_TOKEN           - NocoDB API Token (必填)
  NOCO_ACCOUNT_TABLE   - account 表格 ID (必填)
  NOCO_RECORD_TABLE    - record 表格 ID (必填)
  NOCO_REMAIN_TABLE    - remain 表格 ID (必填)
  NOCO_WISHLIST_TABLE  - wishlist 表格 ID (必填)
  NOCO_VERIFY_SSL      - 是否验证 SSL (true/false, 默认 false)
                          ⚠ 国内自建 NocoDB 多为自签名证书，默认 false。
                            如果使用公共 CA 证书的 HTTPS，可设为 true。
  HTTP_PROXY           - HTTP 代理地址（默认空 = 不使用代理）
  HTTPS_PROXY          - HTTPS 代理地址（默认空 = 跟随 HTTP_PROXY）
  STEAM_COOKIE         - Steam 登录 Cookie（wish 用）
  CURATOR_ID           - Steam 鉴赏家 ID（curator_monitor / unreported 用）
"""

from __future__ import annotations

import os
from typing import Any

from plugins.env_utils import _read_dotenv, get_http_proxy, get_proxies, _env_bool


# 项目根目录：此文件位于 plugins/noco/，往上级 3 层
_PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
print(f"[CONFIG] 项目根目录: {_PROJECT_ROOT}")
print(f"[CONFIG] .env 路径: {os.path.join(_PROJECT_ROOT, '.env')}")
print(f"[CONFIG] .env 是否存在: {os.path.isfile(os.path.join(_PROJECT_ROOT, '.env'))}")


# ── NocoDB 连接 ─────────────────────────────────────────────
NOCO_URL: str = _read_dotenv("NOCO_URL") or "https://127.0.0.1:52533/api/v2/tables"
NOCO_TOKEN: str = _read_dotenv("NOCO_TOKEN") or ""

# ── 表格 ID（每个表格一个变量，查询时自行拼接 URL） ────────
ACCOUNT_TABLE_ID: str = _read_dotenv("NOCO_ACCOUNT_TABLE") or ""
RECORD_TABLE_ID: str = _read_dotenv("NOCO_RECORD_TABLE") or ""
REMAIN_TABLE_ID: str = _read_dotenv("NOCO_REMAIN_TABLE") or ""
WISHLIST_TABLE_ID: str = _read_dotenv("NOCO_WISHLIST_TABLE") or ""

# ── 功能开关 ────────────────────────────────────────────
CHECK_REMAIN: bool = _env_bool("NOCO_CHECK_REMAIN", "true")

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


# ── 便捷函数 ─────────────────────────────────────────────────
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
