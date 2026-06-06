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

# ── 代理 ─────────────────────────────────────────────────────
# 不设置 HTTP_PROXY 即不使用代理。Playwright 只支持单 server 参数，
# 因此只读 HTTP_PROXY，HTTPS_PROXY 自动跟随。
_http_proxy: str = os.getenv("HTTP_PROXY", "")
_https_proxy: str = os.getenv("HTTPS_PROXY", "")

# 同步：如果只设了一个，另一个沿用同一值
if _http_proxy and not _https_proxy:
    _https_proxy = _http_proxy
elif _https_proxy and not _http_proxy:
    _http_proxy = _https_proxy

HTTP_PROXY: str = _http_proxy
HTTPS_PROXY: str = _https_proxy

# PROXIES 仅包含非空条目，传给 requests.get(proxies=PROXIES) 时自动生效/跳过
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
