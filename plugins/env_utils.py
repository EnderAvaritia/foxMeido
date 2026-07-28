"""
env_utils.py - 环境变量与网络代理工具

通用工具函数，不依赖任何业务模块。
从 .env 文件读取配置、获取代理设置等。
"""

from __future__ import annotations

import os
import re
from typing import Any


# 项目根目录：此文件位于 plugins/，往上级 1 层
_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


def _env_bool(key: str, default: str) -> bool:
    """读取布尔类型的环境变量。"""
    return (_read_dotenv(key) or default).strip().lower() in ("true", "1", "yes")


def get_http_proxy() -> str:
    """获取 HTTP 代理地址（Playwright 用）。每次调用时从环境变量读取。"""
    http_proxy = _read_dotenv("HTTP_PROXY")
    https_proxy = _read_dotenv("HTTPS_PROXY")
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
