"""
db/noco_backend.py - NocoDB 后端实现

结构化查询接口（与 sqlite 后端保持一致）：
  get_record(table, where=None, sort="")       -> dict | "" | {"error": ...}
  get_records(table, where=None, sort="")      -> {"list": [...], "pageInfo": {...}} | {"error": ...}
  create_record(table, payload)                -> 新建记录 dict（含 "id"）| {"error": ...}
  update_record(table, record_id, payload)     -> 更新后的记录 dict（含 "id"）| {"error": ...}

where 格式：[(field, op, value), ...]，op ∈ {"eq", "gt", "ne"}
  - value 为 None 时：eq → (field,eq,null)，ne → (field,ne,null)
  - 内部翻译为 NocoDB where 语法：(field,op,value)~and(...)

逻辑表名（account/records/remain/wishlist）在 config 中映射到 NOCO_*_TABLE。
"""

from __future__ import annotations

import json
from typing import Any

import requests

from .config import (
    request_kwargs,
    post_kwargs,
    table_url,
    url_with_filter,
    ACCOUNT_TABLE_ID,
    RECORD_TABLE_ID,
    REMAIN_TABLE_ID,
    WISHLIST_TABLE_ID,
)
from plugins.error_logger import log_error


# 逻辑表名 → NocoDB 表格 ID
_TABLE_IDS: dict[str, str] = {
    "account": ACCOUNT_TABLE_ID,
    "records": RECORD_TABLE_ID,
    "remain": REMAIN_TABLE_ID,
    "wishlist": WISHLIST_TABLE_ID,
}

# where 支持的操作符
_OPS: tuple[str, ...] = ("eq", "gt", "ne")


def _table_id(table: str) -> str:
    """逻辑表名 → NocoDB 表格 ID。"""
    if table not in _TABLE_IDS:
        raise ValueError(f"未知表: {table!r}，可用表: {list(_TABLE_IDS)}")
    return _TABLE_IDS[table]


def _build_where(where: list[tuple[str, str, Any]] | None) -> str:
    """结构化 where → NocoDB where 语法，如 (field,eq,val)~and(field,gt,val)。"""
    if not where:
        return ""
    parts: list[str] = []
    for field, op, value in where:
        if op not in _OPS:
            raise ValueError(f"不支持的操作符: {op!r}，可选: {_OPS}")
        if value is None:
            parts.append(f"({field},{op},null)")
        else:
            parts.append(f"({field},{op},{value})")
    return "~and".join(parts)


def _do_get(url: str) -> dict[str, Any] | list[Any] | str:
    """发起 GET 请求，统一错误处理。"""
    try:
        kwargs = request_kwargs()
        kwargs.setdefault("verify", False)
        response = requests.get(url, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log_error("db.noco_backend.get", f"请求失败: {e}")
        return {"error": f"请求失败: {e}"}
    except json.JSONDecodeError as e:
        log_error("db.noco_backend.get", f"JSON解析失败: {e}")
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        log_error("db.noco_backend.get", f"未知错误: {e}")
        return {"error": f"未知错误: {e}"}


def _do_write(url: str, payload: dict[str, Any], method: str) -> dict[str, Any]:
    """发起 POST/PATCH 请求，统一错误处理。"""
    try:
        kwargs = post_kwargs()
        kwargs.setdefault("verify", False)
        response = requests.request(method, url, data=json.dumps(payload), **kwargs)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"error": f"响应格式异常: {type(data).__name__}"}
    except requests.exceptions.RequestException as e:
        log_error(f"db.noco_backend.{method.lower()}", f"请求失败: {e}")
        return {"error": f"请求失败: {e}"}
    except json.JSONDecodeError as e:
        log_error(f"db.noco_backend.{method.lower()}", f"JSON解析失败: {e}")
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        log_error(f"db.noco_backend.{method.lower()}", f"未知错误: {e}")
        return {"error": f"未知错误: {e}"}


# ── 公共接口 ───────────────────────────────────────────────────

def get_record(
    table: str, where: list[tuple[str, str, Any]] | None = None, sort: str = ""
) -> dict[str, Any] | str:
    """查询单条记录。空结果返回空字符串，失败返回 {"error": ...}。"""
    try:
        table_id = _table_id(table)
        if not table_id:
            return {"error": f"表 {table} 未配置（缺少对应的 NOCO_*_TABLE）"}
        where_str = _build_where(where)
        url = url_with_filter(table_id, where_str, sort=sort)
        data = _do_get(url)
        if not isinstance(data, dict):
            return {"error": "响应格式异常"}
        if "error" in data:
            return data
        if data.get("list"):
            return data["list"][0]
        return ""
    except Exception as e:
        log_error("db.noco_backend.get_record", f"查询失败: {e}")
        return {"error": f"查询失败: {e}"}


def get_records(
    table: str, where: list[tuple[str, str, Any]] | None = None, sort: str = ""
) -> dict[str, Any]:
    """通用查询记录列表，返回完整响应字典（含 list / pageInfo）。"""
    try:
        table_id = _table_id(table)
        if not table_id:
            return {"error": f"表 {table} 未配置（缺少对应的 NOCO_*_TABLE）"}
        where_str = _build_where(where)
        url = url_with_filter(table_id, where_str, sort=sort)
        data = _do_get(url)
        if not isinstance(data, dict):
            return {"error": "响应格式异常"}
        return data
    except Exception as e:
        log_error("db.noco_backend.get_records", f"查询失败: {e}")
        return {"error": f"查询失败: {e}"}


def create_record(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    """在指定表格创建一条记录。失败时返回 {"error": ...}。"""
    try:
        table_id = _table_id(table)
        if not table_id:
            return {"error": f"表 {table} 未配置（缺少对应的 NOCO_*_TABLE）"}
        return _do_write(table_url(table_id), payload, "POST")
    except Exception as e:
        log_error("db.noco_backend.create_record", f"创建失败: {e}")
        return {"error": f"创建失败: {e}"}


def update_record(
    table: str, record_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    """更新指定表格中的一条记录（PATCH）。失败时返回 {"error": ...}。"""
    try:
        table_id = _table_id(table)
        if not table_id:
            return {"error": f"表 {table} 未配置（缺少对应的 NOCO_*_TABLE）"}
        body = {"id": record_id, **payload}
        return _do_write(table_url(table_id), body, "PATCH")
    except Exception as e:
        log_error("db.noco_backend.update_record", f"更新失败: {e}")
        return {"error": f"更新失败: {e}"}
