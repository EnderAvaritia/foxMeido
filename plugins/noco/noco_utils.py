"""
noco_utils.py - NocoDB 通用工具函数

集中存放多个脚本中重复出现的 NocoDB 操作和 Steam API 调用。
"""

from __future__ import annotations

import json
from typing import Any

import requests

from .noco_config import get_proxies, request_kwargs, post_kwargs
from .error_logger import log_error

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


# ── Steam API ────────────────────────────────────────────────


def get_game_info(appid: int | str) -> dict[str, Any]:
    """
    通过 Steam Web API 获取游戏名称、厂商名和发行日期。

    Args:
        appid: Steam AppID。

    Returns:
        dict: 包含 game_name、publisher、release_date 的字典，
              出错时含 error 键。
    """
    game_name: str | None = None
    publisher: str | None = None
    release_date: str | None = None
    errors: list[str] = []

    api_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese"

    try:
        response = requests.get(api_url, proxies=get_proxies(), timeout=10)
        response.raise_for_status()
        data = response.json()
        app_data = data.get(str(appid))

        if app_data and app_data.get("success"):
            details = app_data.get("data")
            if details:
                game_name = details.get("name")
                if not game_name:
                    errors.append(f"API返回数据中未找到'name'信息 (AppID: {appid})")

                publishers = details.get("publishers")
                if publishers:
                    publisher = ", ".join(publishers)
                else:
                    errors.append(f"API返回的厂商列表为空 (AppID: {appid})")

                rd = details.get("release_date")
                if rd and rd.get("date"):
                    release_date = rd["date"]
                else:
                    errors.append(f"API返回的发行日期为空 (AppID: {appid})")
            else:
                errors.append(f"API返回数据中未找到'data'详情 (AppID: {appid})")
        else:
            errors.append(
                f"API返回成功状态为false或数据为空 (AppID: {appid})。"
                "可能AppID不存在或不可用。"
            )
    except requests.exceptions.RequestException as e:
        errors.append(f"请求API接口时发生网络错误或HTTP错误: {e}")
        log_error("noco_utils.get_game_info", f"请求API异常: {e}")
    except json.JSONDecodeError as e:
        errors.append(f"解析API响应JSON时发生错误: {e}")
        log_error("noco_utils.get_game_info", f"JSON解析异常: {e}")
    except Exception as e:
        errors.append(f"处理API响应时发生未知错误: {e}")
        log_error("noco_utils.get_game_info", f"未知异常: {e}")

    result: dict[str, Any] = {
        "game_name": game_name,
        "publisher": publisher,
        "release_date": release_date,
    }
    if errors:
        result["error"] = "; ".join(errors)
    return result


def extract_steam_id(text: str) -> str | None:
    """
    从文本中提取 Steam AppID。

    支持：
    - 纯数字（5-11 位）
    - Steam 商店 URL (store.steampowered.com/app/数字)

    Returns:
        匹配到的第一个 AppID 字符串，未找到返回 None。
    """
    import re
    match = re.findall(r"(?<=app/)(\d+)|(\d{5,11})", text)
    if match:
        return tuple(item for item in match[0] if item)[0]
    return None
