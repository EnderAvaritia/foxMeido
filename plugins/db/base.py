"""plugins/db/base.py - 数据库后端抽象接口

两个后端实现（SqliteBackend / NocoBackend）都必须实现此接口。
命令插件只依赖这里的抽象，通过 plugins.db.get_backend() 获取当前配置的后端实例，
不感知具体后端，从而支持在 sqlite / noco 之间自由切换。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DatabaseBackend(ABC):
    """数据库后端抽象接口。

    结构化查询约定（两个后端一致）：
      get_record(table, where, sort)    -> dict | "" | {"error": ...}
      get_records(table, where, sort)   -> {"list": [...], "pageInfo": {"totalRows": n}} | {"error": ...}
      create_record(table, payload)     -> 新建记录 dict（含 "id"）| {"error": ...}
      update_record(table, id, payload) -> 更新后的记录 dict（含 "id"）| {"error": ...}

    table 为逻辑表名：account / records / remain / wishlist。
    where 为 [(field, op, value), ...]，op ∈ {"eq", "gt", "ne"}，value=None 表示 NULL 判断。
    """

    #: 后端名称（sqlite / noco），用于日志与分支判断
    name: str = ""

    @abstractmethod
    def get_record(
        self,
        table: str,
        where: list[tuple[str, str, Any]] | None = None,
        sort: str = "",
    ) -> dict[str, Any] | str:
        """查询单条记录。空结果返回空字符串，失败返回 {"error": ...}。"""

    @abstractmethod
    def get_records(
        self,
        table: str,
        where: list[tuple[str, str, Any]] | None = None,
        sort: str = "",
    ) -> dict[str, Any]:
        """查询记录列表，返回 {"list": [...], "pageInfo": {"totalRows": n}}。失败返回 {"error": ...}。"""

    @abstractmethod
    def create_record(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        """在指定表新建一条记录，返回含 "id" 的记录。失败返回 {"error": ...}。"""

    @abstractmethod
    def update_record(
        self, table: str, record_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """更新指定 id 的记录，返回更新后的记录（含 "id"）。失败返回 {"error": ...}。"""
