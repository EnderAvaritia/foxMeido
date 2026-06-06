"""
noco_config.py - NocoDB 配置中心

所有 NocoDB 相关的常量统一从环境变量读取。
可配置在 .env 文件中（已 gitignore），无需逐个修改脚本。

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
  CURATOR_ID           - Steam 鉴赏家 ID（unreported 用）
"""

from __future__ import annotations

import os
from typing import Any


def _env_bool(key: str, default: str) -> bool:
    return os.getenv(key, default).strip().lower() in ("true", "1", "yes")


# ── NocoDB 连接 ─────────────────────────────────────────────
NOCO_URL: str = os.getenv("NOCO_URL", "https://127.0.0.1:52533/api/v2/tables")
NOCO_TOKEN: str = os.getenv("NOCO_TOKEN", "")

# ── 表格 ID（每个表格一个变量，查询时自行拼接 URL） ────────
ACCOUNT_TABLE_ID: str = os.getenv("NOCO_ACCOUNT_TABLE", "")
RECORD_TABLE_ID: str = os.getenv("NOCO_RECORD_TABLE", "")
REMAIN_TABLE_ID: str = os.getenv("NOCO_REMAIN_TABLE", "")
WISHLIST_TABLE_ID: str = os.getenv("NOCO_WISHLIST_TABLE", "")

# ── 请求通用配置 ─────────────────────────────────────────────
HEADERS: dict[str, str] = {"xc-token": NOCO_TOKEN}
VERIFY_SSL: bool = _env_bool("NOCO_VERIFY_SSL", "false")

# ── 代理（懒加载函数）────────────────────────────────────────
# 注意：os.getenv() 在模块导入时执行，但 python-dotenv 可能尚未加载 .env。
# 使用 get_proxies() / get_http_proxy() 在调用时实时读取，确保值正确。


def get_http_proxy() -> str:
    """获取 HTTP 代理地址（Playwright 用）。每次调用时从环境变量读取。"""
    http_proxy = os.getenv("HTTP_PROXY", "")
    https_proxy = os.getenv("HTTPS_PROXY", "")
    # 同步：如果只设了一个，另一个沿用同一值
    if http_proxy and not https_proxy:
        https_proxy = http_proxy
    elif https_proxy and not http_proxy:
        http_proxy = https_proxy
    return http_proxy


def get_proxies() -> dict[str, str]:
    """获取代理配置字典（requests 用）。每次调用时从环境变量读取。"""
    http_proxy = os.getenv("HTTP_PROXY", "")
    https_proxy = os.getenv("HTTPS_PROXY", "")
    if http_proxy and not https_proxy:
        https_proxy = http_proxy
    elif https_proxy and not http_proxy:
        http_proxy = https_proxy
    proxies: dict[str, str] = {}
    if http_proxy:
        proxies["http"] = http_proxy
        proxies["https"] = https_proxy
    return proxies


# ── 模块级常量（兼容旧代码，但优先使用上面的函数）───────────
# 注意：这些在模块导入时求值，如果 dotenv 尚未加载则可能为空。
HTTP_PROXY: str = os.getenv("HTTP_PROXY", "")
HTTPS_PROXY: str = os.getenv("HTTPS_PROXY", "")
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
STEAM_COOKIE: str = os.getenv("STEAM_COOKIE", "")
CURATOR_ID: int = int(os.getenv("CURATOR_ID", "0"))


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
