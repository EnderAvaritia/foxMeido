"""
noco_utils.py - 通用工具函数

非 NocoDB 专属的通用工具，放在 plugins/ 层级供所有模块引用。

包含：
- get_game_info()    — 通过 Steam Web API 查询游戏信息
- extract_steam_id() — 从文本/URL 提取 Steam AppID
"""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from plugins.noco.noco_config import get_proxies
from plugins.error_logger import log_error


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
        response = requests.get(
            api_url,
            proxies=get_proxies(),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        app_data = data.get(str(appid))

        if app_data and app_data.get("success"):
            details = app_data.get("data")
            if details:
                game_name = details.get("name")
                if not game_name:
                    errors.append(
                        f"API返回数据中未找到'name'信息 (AppID: {appid})"
                    )

                publishers = details.get("publishers")
                if publishers:
                    publisher = ", ".join(publishers)
                else:
                    errors.append(
                        f"API返回的厂商列表为空 (AppID: {appid})"
                    )

                rd = details.get("release_date")
                if rd and rd.get("date"):
                    release_date = rd["date"]
                else:
                    errors.append(
                        f"API返回的发行日期为空 (AppID: {appid})"
                    )
            else:
                errors.append(
                    f"API返回数据中未找到'data'详情 (AppID: {appid})"
                )
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
    match = re.findall(r"(?<=app/)(\d+)|(\d{5,11})", text)
    if match:
        return tuple(item for item in match[0] if item)[0]
    return None
