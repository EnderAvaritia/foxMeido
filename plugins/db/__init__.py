"""plugins/db - 数据库抽象层

数据库后端以"指令"形式独立实现，通过抽象接口统一对外：
  base.py          DatabaseBackend  抽象基类（接口定义）
  sqlite.py        SqliteBackend    sqlite 指令
  noco_backend.py  NocoBackend      noco 指令

命令插件通过 get_backend() 获取当前配置（DB_BACKEND）对应的后端实例，
只依赖 DatabaseBackend 抽象接口，不感知具体后端。

示例：
  from plugins.db import get_backend
  backend = get_backend()
  rec = backend.get_record("account", [("account", "eq", "123456")])

where 格式：[(field, op, value), ...]，op ∈ {"eq", "gt", "ne"}，value=None 表示 NULL 判断。
table 为逻辑表名：account / records / remain / wishlist。
"""

from . import config
from .base import DatabaseBackend
from .config import BACKEND, SQLITE_PATH

_backend: DatabaseBackend | None = None


def get_backend() -> DatabaseBackend:
    """按 DB_BACKEND 返回当前配置的后端实例（单例）。"""
    global _backend
    if _backend is None:
        if BACKEND == "noco":
            from .noco_backend import NocoBackend

            _backend = NocoBackend()
        else:
            from .sqlite import SqliteBackend

            _backend = SqliteBackend()
    return _backend


__all__ = [
    "BACKEND",
    "SQLITE_PATH",
    "DatabaseBackend",
    "config",
    "get_backend",
]
