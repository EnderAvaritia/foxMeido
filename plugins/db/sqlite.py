"""
db/sqlite.py - SQLite 后端指令（SqliteBackend）

实现 plugins/db/base.py 的 DatabaseBackend 抽象接口：
  get_record(table, where=None, sort="")       -> dict | "" | {"error": ...}
  get_records(table, where=None, sort="")      -> {"list": [...], "pageInfo": {"totalRows": n}} | {"error": ...}
  create_record(table, payload)                -> 新建记录 dict（含 "id"）| {"error": ...}
  update_record(table, record_id, payload)     -> 更新后的记录 dict（含 "id"）| {"error": ...}

where 格式：[(field, op, value), ...]，op ∈ {"eq", "gt", "ne"}
  - value 为 None 时：eq → IS NULL，ne → IS NOT NULL
  - 条件之间为 AND 关系

表结构与 plugins/db/noco/createTables.sql 完全一致（含系统列），
不加唯一约束，行为与 NocoDB 后端对齐。首次使用时自动建表。

用法（通过抽象层获取实例）：
  from plugins.db import get_backend
  backend = get_backend()          # DB_BACKEND=sqlite 时返回 SqliteBackend 实例
  rec = backend.get_record("account", [("account", "eq", "123456")])
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any

from .base import DatabaseBackend
from .config import SQLITE_PATH
from plugins.error_logger import log_error


# ── 表结构（源自 createTables.sql，含 NocoDB 系统列） ─────────────
TABLE_SCHEMAS: dict[str, list[str]] = {
    "account": [
        "id", "created_at", "updated_at", "created_by", "updated_by",
        "nc_order", "steamId", "account", "nickname",
    ],
    "records": [
        "id", "created_at", "updated_at", "created_by", "updated_by",
        "nc_order", "gameId", "gameName", "userId", "userName", "Link",
        "submitTime", "getTime", "report", "publisher", "steamId",
    ],
    "remain": [
        "id", "created_at", "updated_at", "created_by", "updated_by",
        "nc_order", "gameId", "gameName", "totalCount", "getedCount",
        "canBeClaimed",
    ],
    "wishlist": [
        "id", "created_at", "updated_at", "created_by", "updated_by",
        "nc_order", "gameId", "gameName", "userId", "userName", "Link",
        "submitTime", "publisher", "releaseDate", "steamId",
    ],
}

TABLE_DDL: dict[str, str] = {
    "account": """
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY,
            created_at DATETIME, updated_at DATETIME,
            created_by VARCHAR(255), updated_by VARCHAR(255),
            nc_order REAL,
            steamId INTEGER, account VARCHAR(255), nickname VARCHAR(255)
        )
    """,
    "records": """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY,
            created_at DATETIME, updated_at DATETIME,
            created_by VARCHAR(255), updated_by VARCHAR(255),
            nc_order REAL,
            gameId INTEGER, gameName VARCHAR(255),
            userId INTEGER, userName VARCHAR(255), Link VARCHAR(255),
            submitTime DATE, getTime DATE,
            report BOOLEAN DEFAULT '0',
            publisher VARCHAR(255), steamId INTEGER
        )
    """,
    "remain": """
        CREATE TABLE IF NOT EXISTS remain (
            id INTEGER PRIMARY KEY,
            created_at DATETIME, updated_at DATETIME,
            created_by VARCHAR(255), updated_by VARCHAR(255),
            nc_order REAL,
            gameId INTEGER, gameName VARCHAR(255),
            totalCount INTEGER, getedCount INTEGER, canBeClaimed INTEGER
        )
    """,
    "wishlist": """
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY,
            created_at DATETIME, updated_at DATETIME,
            created_by VARCHAR(255), updated_by VARCHAR(255),
            nc_order REAL,
            gameId VARCHAR(255), gameName VARCHAR(255),
            userId VARCHAR(255), userName VARCHAR(255), Link VARCHAR(255),
            submitTime VARCHAR(255), publisher VARCHAR(255),
            releaseDate VARCHAR(255), steamId INTEGER
        )
    """,
}

# where 支持的操作符
_OPS: tuple[str, ...] = ("eq", "gt", "ne")


def _get_conn() -> sqlite3.Connection:
    """获取 SQLite 连接（每次调用新建，WAL 模式）。"""
    parent = os.path.dirname(SQLITE_PATH)
    os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """确保 4 张表存在（CREATE TABLE IF NOT EXISTS）。"""
    for ddl in TABLE_DDL.values():
        conn.execute(ddl)
    conn.commit()


def _validate_table(table: str) -> None:
    if table not in TABLE_SCHEMAS:
        raise ValueError(f"未知表: {table!r}，可用表: {list(TABLE_SCHEMAS)}")


def _validate_column(table: str, field: str) -> None:
    if field not in TABLE_SCHEMAS[table]:
        raise ValueError(f"表 {table!r} 无字段 {field!r}")


def _build_where_clause(
    table: str, where: list[tuple[str, str, Any]] | None
) -> tuple[str, list[Any]]:
    """把结构化 where 编译为 SQL 条件。返回 (sql, params)。"""
    if not where:
        return "", []
    clauses: list[str] = []
    params: list[Any] = []
    for field, op, value in where:
        _validate_column(table, field)
        if op not in _OPS:
            raise ValueError(f"不支持的操作符: {op!r}，可选: {_OPS}")
        if op == "eq":
            if value is None:
                clauses.append(f'"{field}" IS NULL')
            else:
                clauses.append(f'"{field}" = ?')
                params.append(value)
        elif op == "ne":
            if value is None:
                clauses.append(f'"{field}" IS NOT NULL')
            else:
                clauses.append(f'"{field}" <> ?')
                params.append(value)
        elif op == "gt":
            if value is None:
                raise ValueError("gt 操作符不支持 NULL 值")
            clauses.append(f'"{field}" > ?')
            params.append(value)
    return " AND ".join(clauses), params


def _build_sort_clause(table: str, sort: str) -> str:
    if not sort:
        return ""
    _validate_column(table, sort)
    return f' ORDER BY "{sort}"'


def _filter_payload(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    """只保留表中存在的字段，避免未知键导致 SQL 错误。"""
    valid = TABLE_SCHEMAS[table]
    return {k: v for k, v in payload.items() if k in valid}


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


# ── 公共接口（SqliteBackend 指令） ─────────────────────────────

class SqliteBackend(DatabaseBackend):
    """SQLite 后端指令：实现 DatabaseBackend 抽象接口。"""

    name = "sqlite"

    def get_record(
        self,
        table: str,
        where: list[tuple[str, str, Any]] | None = None,
        sort: str = "",
    ) -> dict[str, Any] | str:
        """查询单条记录。空结果返回空字符串，失败返回 {"error": ...}。"""
        try:
            _validate_table(table)
            where_sql, params = _build_where_clause(table, where)
            sort_sql = _build_sort_clause(table, sort)
            conn = _get_conn()
            try:
                sql = f'SELECT * FROM "{table}"'
                if where_sql:
                    sql += f" WHERE {where_sql}"
                sql += sort_sql
                row = conn.execute(sql, params).fetchone()
                result = _row_to_dict(row)
                return result if result is not None else ""
            finally:
                conn.close()
        except Exception as e:
            log_error("db.sqlite.get_record", f"查询失败: {e}")
            return {"error": f"查询失败: {e}"}

    def get_records(
        self,
        table: str,
        where: list[tuple[str, str, Any]] | None = None,
        sort: str = "",
    ) -> dict[str, Any]:
        """通用查询记录列表，返回 {"list": [...], "pageInfo": {"totalRows": n}}。"""
        try:
            _validate_table(table)
            where_sql, params = _build_where_clause(table, where)
            sort_sql = _build_sort_clause(table, sort)
            conn = _get_conn()
            try:
                sql = f'SELECT * FROM "{table}"'
                if where_sql:
                    sql += f" WHERE {where_sql}"
                sql += sort_sql
                rows = conn.execute(sql, params).fetchall()
                records = [dict(r) for r in rows]
                return {"list": records, "pageInfo": {"totalRows": len(records)}}
            finally:
                conn.close()
        except Exception as e:
            log_error("db.sqlite.get_records", f"查询失败: {e}")
            return {"error": f"查询失败: {e}"}

    def create_record(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        """在指定表创建一条记录，返回含 "id" 的记录。失败返回 {"error": ...}。"""
        try:
            _validate_table(table)
            data = _filter_payload(table, payload)
            if not data:
                raise ValueError("payload 中没有有效字段")
            conn = _get_conn()
            try:
                fields = list(data.keys())
                placeholders = ", ".join("?" for _ in fields)
                sql = (
                    f'INSERT INTO "{table}" ({", ".join(fields)}) '
                    f"VALUES ({placeholders})"
                )
                cur = conn.execute(sql, list(data.values()))
                conn.commit()
                new_id = cur.lastrowid
                row = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?', (new_id,)).fetchone()
                result = _row_to_dict(row) or {"id": new_id, **data}
                return result
            finally:
                conn.close()
        except Exception as e:
            log_error("db.sqlite.create_record", f"创建失败: {e}")
            return {"error": f"创建失败: {e}"}

    def update_record(
        self, table: str, record_id: int, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """更新指定 id 的记录，返回更新后的记录（含 "id"）。失败返回 {"error": ...}。"""
        try:
            _validate_table(table)
            data = _filter_payload(table, payload)
            if not data:
                raise ValueError("payload 中没有有效字段")
            conn = _get_conn()
            try:
                sets = ", ".join(f'"{k}" = ?' for k in data)
                sql = f'UPDATE "{table}" SET {sets} WHERE id = ?'
                cur = conn.execute(sql, list(data.values()) + [record_id])
                conn.commit()
                if cur.rowcount == 0:
                    return {"error": "记录不存在"}
                row = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?', (record_id,)).fetchone()
                result = _row_to_dict(row)
                if result is None:
                    return {"error": "记录不存在"}
                return result
            finally:
                conn.close()
        except Exception as e:
            log_error("db.sqlite.update_record", f"更新失败: {e}")
            return {"error": f"更新失败: {e}"}
