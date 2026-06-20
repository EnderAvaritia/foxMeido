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
   WISH_ADD_TO_STEAM    - /wish 时是否自动加入 Steam 愿望单（true/false, 默认 false）
   CURATOR_ID           - Steam 鉴赏家 ID（unreported 用）
"""

from __future__ import annotations

import os
import re
from typing import Any


def _env_bool(key: str, default: str) -> bool:
    return (_read_dotenv(key) or default).strip().lower() in ("true", "1", "yes")


# 项目根目录：此文件位于 plugins/noco/，往上级 3 层
_PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
print(f"[CONFIG] 项目根目录: {_PROJECT_ROOT}")
print(f"[CONFIG] .env 路径: {os.path.join(_PROJECT_ROOT, '.env')}")
print(f"[CONFIG] .env 是否存在: {os.path.isfile(os.path.join(_PROJECT_ROOT, '.env'))}")


def _read_dotenv(key: str) -> str:
    """
    从 .env 文件直接读取变量值（兜底方案）。

    当 python-dotenv 因文件中有非法格式（如混入 Python 代码）而解析失败时，
    os.getenv() 可能取不到值。此函数直接逐行扫描 .env 文件，
    匹配 ``KEY=VALUE`` 模式，不依赖 dotenv 库。

    支持行内注释：``KEY=VALUE  # comment`` 会返回 ``VALUE``。

    搜索顺序：
    1. ``.env.{ENVIRONMENT}``（如果设置了 ENVIRONMENT）
    2. ``.env``
    后者不覆盖前者。
    """
    # 先从 os.environ 取（正常情况）
    value = os.getenv(key, "")
    if value:
        return value.split("#")[0].strip()

    # 兜底：直接读 .env 文件
    env_name = os.getenv("ENVIRONMENT", "")
    candidates: list[str] = []
    if env_name:
        candidates.append(f".env.{env_name}")
    candidates.append(".env")

    for fname in candidates:
        fpath = os.path.join(_PROJECT_ROOT, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith("#"):
                        continue
                    m = re.match(r"export\s+", line)
                    if m:
                        line = line[m.end():]
                    m = re.match(rf'({re.escape(key)})\s*=\s*(.*)', line)
                    if m:
                        val = m.group(2).strip().strip('"').strip("'")
                        # 去掉行内注释
                        val = val.split("#")[0].strip()
                        if val:
                            return val
        except OSError:
            continue

    return os.getenv(key, "")


# ── NocoDB 连接 ─────────────────────────────────────────────
NOCO_URL: str = _read_dotenv("NOCO_URL") or "https://127.0.0.1:52533/api/v2/tables"
NOCO_TOKEN: str = _read_dotenv("NOCO_TOKEN") or ""

# ── 表格 ID（每个表格一个变量，查询时自行拼接 URL） ────────
ACCOUNT_TABLE_ID: str = _read_dotenv("NOCO_ACCOUNT_TABLE") or ""
RECORD_TABLE_ID: str = _read_dotenv("NOCO_RECORD_TABLE") or ""
REMAIN_TABLE_ID: str = _read_dotenv("NOCO_REMAIN_TABLE") or ""
WISHLIST_TABLE_ID: str = _read_dotenv("NOCO_WISHLIST_TABLE") or ""

print(f"[CONFIG] NOCO_URL={NOCO_URL!r}")
print(f"[CONFIG] ACCOUNT_TABLE_ID={ACCOUNT_TABLE_ID!r}")
print(f"[CONFIG] RECORD_TABLE_ID={RECORD_TABLE_ID!r}")
print(f"[CONFIG] REMAIN_TABLE_ID={REMAIN_TABLE_ID!r}")
print(f"[CONFIG] WISHLIST_TABLE_ID={WISHLIST_TABLE_ID!r}")

# ── 请求通用配置 ─────────────────────────────────────────────
HEADERS: dict[str, str] = {"xc-token": NOCO_TOKEN}
VERIFY_SSL: bool = _env_bool("NOCO_VERIFY_SSL", "false")

# ── 代理（懒加载函数）────────────────────────────────────────
# 注意：os.getenv() 在模块导入时执行，但 python-dotenv 可能尚未加载 .env。
# 使用 get_proxies() / get_http_proxy() 在调用时实时读取，确保值正确。


def get_http_proxy() -> str:
    """获取 HTTP 代理地址（Playwright 用）。每次调用时从环境变量读取。"""
    http_proxy = _read_dotenv("HTTP_PROXY")
    https_proxy = _read_dotenv("HTTPS_PROXY")
    # 同步：如果只设了一个，另一个沿用同一值
    if http_proxy and not https_proxy:
        https_proxy = http_proxy
    elif https_proxy and not http_proxy:
        http_proxy = https_proxy
    print(f"[PROXY] get_http_proxy() → {http_proxy!r}")
    return http_proxy


def get_proxies() -> dict[str, str]:
    """获取代理配置字典（requests 用）。每次调用时从环境变量读取。"""
    http_proxy = _read_dotenv("HTTP_PROXY")
    https_proxy = _read_dotenv("HTTPS_PROXY")
    if http_proxy and not https_proxy:
        https_proxy = http_proxy
    elif https_proxy and not http_proxy:
        http_proxy = https_proxy
    proxies: dict[str, str] = {}
    if http_proxy:
        proxies["http"] = http_proxy
        proxies["https"] = https_proxy
    print(f"[PROXY] get_proxies() → {proxies}")
    return proxies


# ── 模块级常量（兼容旧代码，但优先使用上面的函数）───────────
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
CURATOR_ID: int = int(_read_dotenv("CURATOR_ID") or "0")
# 是否在执行 /wish 时自动将游戏加入 Steam 愿望单（需要 STEAM_COOKIE）
WISH_ADD_TO_STEAM: bool = _env_bool("WISH_ADD_TO_STEAM", "false")


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
