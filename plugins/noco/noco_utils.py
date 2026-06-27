"""
noco_utils.py - NocoDB 通用工具函数

NocoDB 专用的数据库操作函数。
通用工具（get_game_info / extract_steam_id）已移至 plugins/noco_utils.py。
"""

from __future__ import annotations

import json
from typing import Any

import requests

from .noco_config import request_kwargs, post_kwargs
from plugins.error_logger import log_error


# ── 通用 NocoDB 操作 ───────────────────────────────────────


def get_record(url: str) -> dict[str, Any] | str:
    """
    查询单条记录。

    如果列表为空返回空字符串，否则返回第一条记录（字典）。
    失败时返回 {"error": ...}。
    注意：仅适用于查询结果 list ≤ 1 的场景。
    """
    try:
        kwargs = request_kwargs()
        kwargs.setdefault("verify", False)
        response = requests.get(url, **kwargs)
        response.raise_for_status()
        data = response.json()
        if data.get("list"):
            return data["list"][0]
        return ""
    except requests.exceptions.RequestException as e:
        log_error("noco_utils.get_record", f"请求失败: {e}")
        return {"error": f"请求失败: {e}"}
    except json.JSONDecodeError as e:
        log_error("noco_utils.get_record", f"JSON解析失败: {e}")
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        log_error("noco_utils.get_record", f"未知错误: {e}")
        return {"error": f"未知错误: {e}"}


def get_records(url: str) -> dict[str, Any]:
    """
    通用查询记录列表，返回完整响应字典。
    """
    kwargs = request_kwargs()
    kwargs.setdefault("verify", False)
    try:
        response = requests.get(url, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log_error("noco_utils.get_records", f"请求失败: {e}")
        return {"error": f"请求失败: {e}"}
    except json.JSONDecodeError as e:
        log_error("noco_utils.get_records", f"JSON解析失败: {e}")
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        log_error("noco_utils.get_records", f"未知错误: {e}")
        return {"error": f"未知错误: {e}"}


def create_record(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """在指定表格创建一条记录。失败时返回 {"error": ...}。"""
    try:
        kwargs = post_kwargs()
        kwargs.setdefault("verify", False)
        response = requests.post(url, data=json.dumps(payload), **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log_error("noco_utils.create_record", f"请求失败: {e}")
        return {"error": f"请求失败: {e}"}
    except json.JSONDecodeError as e:
        log_error("noco_utils.create_record", f"JSON解析失败: {e}")
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        log_error("noco_utils.create_record", f"未知错误: {e}")
        return {"error": f"未知错误: {e}"}


def update_record(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """更新指定表格中的一条记录（PATCH）。失败时返回 {"error": ...}。"""
    try:
        kwargs = post_kwargs()
        kwargs.setdefault("verify", False)
        response = requests.patch(url, data=json.dumps(payload), **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log_error("noco_utils.update_record", f"请求失败: {e}")
        return {"error": f"请求失败: {e}"}
    except json.JSONDecodeError as e:
        log_error("noco_utils.update_record", f"JSON解析失败: {e}")
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        log_error("noco_utils.update_record", f"未知错误: {e}")
        return {"error": f"未知错误: {e}"}
