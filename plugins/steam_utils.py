"""
steam_utils.py - Steam 通用工具函数

包含：
- get_game_info()     — 通过 Steam Web API 查询游戏信息（名称、厂商、日期、语言、类型、价格）
- get_popular_tags()  — 从商店页面提取热门用户自定义标签
- extract_steam_id()  — 从文本/URL 提取 Steam AppID
"""

from __future__ import annotations

import json
import re
from typing import Any

import urllib3

import requests

from bs4 import BeautifulSoup

from plugins.env_utils import get_proxies
from plugins.db.config import STEAM_COOKIE, STEAM_CC
from plugins.error_logger import log_error

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _fetch_app_data(appid: int | str, cc: str = "") -> dict[str, Any] | None:
    """请求 Steam API，返回 app_data dict 或 None（success=false）。"""
    cc_param = f"&cc={cc}" if cc else ""
    api_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese{cc_param}"
    request_kwargs: dict[str, Any] = {
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        },
        "timeout": 15,
    }
    proxy_cfg = get_proxies()
    if proxy_cfg:
        request_kwargs["proxies"] = proxy_cfg
        request_kwargs["verify"] = False
    response = requests.get(api_url, **request_kwargs)
    print(f"[Steam API] {api_url}")
    response.raise_for_status()
    data = response.json()
    app_data = data.get(str(appid))
    if app_data and app_data.get("success"):
        return app_data.get("data")
    return None


def get_game_info(appid: int | str) -> dict[str, Any]:
    """
    通过 Steam Web API 获取游戏名称、厂商名、发行日期、支持语言、类型和价格信息。

    如果设置了 STEAM_CC 且目标区返回 success=false（锁区），
    自动降级到不带 cc 参数重新请求。

    Args:
        appid: Steam AppID。

    Returns:
        dict: 包含 game_name、publisher、release_date、supported_languages、
              genres、initial、final、currency 的字典，出错时含 error 键。
    """
    game_name: str | None = None
    publisher: str | None = None
    release_date: str | None = None
    supported_languages: str | None = None
    genres: str | None = None
    initial: float = 1
    final: float = 1
    currency: str | None = None
    errors: list[str] = []

    try:
        # 第一次请求：带 STEAM_CC（如果有的话）
        details = None
        if STEAM_CC:
            try:
                details = _fetch_app_data(appid, STEAM_CC)
            except Exception:
                log_error("steam_utils.get_game_info",
                           f"STEAM_CC={STEAM_CC} 请求异常 (AppID: {appid})，降级到默认区域")

        # 如果带 cc 失败（网络异常或锁区），且 STEAM_CC 有值，降级重试
        if details is None and STEAM_CC:
            log_error("steam_utils.get_game_info",
                       f"STEAM_CC={STEAM_CC} 目标区不可用 (AppID: {appid})，降级到默认区域")
            details = _fetch_app_data(appid)

        # STEAM_CC 未设置，直接请求（不带 cc）
        if details is None and not STEAM_CC:
            details = _fetch_app_data(appid)

        if details is not None:
            game_name = details.get("name")
            if not game_name:
                errors.append(
                    f"API返回数据中未找到'name'信息 (AppID: {appid})"
                )

            publishers = details.get("publishers")
            if publishers:
                publisher = ", ".join(publishers)

            rd = details.get("release_date")
            if rd and rd.get("date"):
                release_date = rd["date"]

            # 支持语言
            raw_lang = details.get("supported_languages")
            if raw_lang:
                supported_languages = re.sub(
                    "<.*?>", "", raw_lang
                ).replace("*", "").replace("具有完全音频支持的语言", "")

            # 类型（genres）
            raw_genres = details.get("genres")
            if raw_genres:
                genres = ", ".join(g.get("description", "") for g in raw_genres)

            # 价格信息
            try:
                price = details.get("price_overview")
                if price:
                    initial = int(price.get("initial", 0)) / 100
                    final = int(price.get("final", 0)) / 100
                    currency = price.get("currency")
                else:
                    initial = 1
                    final = 1
                    currency = None
            except Exception as e:
                log_error("steam_utils.get_game_info", f"价格异常 (AppID: {appid}): {e}")
                initial = 1
                final = 1
                currency = None
        else:
            errors.append(
                f"API返回成功状态为false或数据为空 (AppID: {appid})。"
                "可能AppID不存在或不可用。"
            )
    except requests.exceptions.RequestException as e:
        errors.append(f"请求API接口时发生网络错误或HTTP错误: {e}")
        log_error("steam_utils.get_game_info", f"请求API异常: {e}")
    except json.JSONDecodeError as e:
        errors.append(f"解析API响应JSON时发生错误: {e}")
        log_error("steam_utils.get_game_info", f"JSON解析异常: {e}")
    except Exception as e:
        errors.append(f"处理API响应时发生未知错误: {e}")
        log_error("steam_utils.get_game_info", f"未知异常: {e}")

    result: dict[str, Any] = {
        "game_name": game_name,
        "publisher": publisher,
        "release_date": release_date,
        "supported_languages": supported_languages,
        "genres": genres,
        "initial": initial,
        "final": final,
        "currency": currency,
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


def get_popular_tags(appid: int | str) -> dict[str, Any]:
    """
    从 Steam 商店页面提取"该产品的热门用户自定义标签"。

    优先从页面中 InitAppTagModal() 调用提取 JSON 数据（含 tagid、name、count），
    提取失败时退而求其次从 a.app_tag 元素获取纯文本标签名。

    Args:
        appid: Steam AppID。

    Returns:
        dict: 包含 tags（list[str]）的字典，出错时含 error 键。
    """
    tags: list[str] = []
    errors: list[str] = []

    url = f"https://store.steampowered.com/app/{appid}/"

    try:
        request_kwargs: dict[str, Any] = {
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
            },
            "timeout": 15,
        }
        if STEAM_COOKIE:
            request_kwargs["headers"]["Cookie"] = STEAM_COOKIE
        proxy_cfg = get_proxies()
        if proxy_cfg:
            request_kwargs["proxies"] = proxy_cfg
            request_kwargs["verify"] = False
        response = requests.get(url, **request_kwargs)
        response.raise_for_status()

        html = response.text

        # 方法 1：从 InitAppTagModal() 提取 JSON 数据
        tags = _extract_from_init_tag_modal(html, str(appid))

        if tags:
            return {"tags": tags}

        # 方法 2：退而求其次，从 a.app_tag 元素提取
        tags = _extract_from_app_tag_elements(html)

        if tags:
            return {"tags": tags}

        errors.append("页面中未找到标签数据，页面结构可能已变更")

    except requests.exceptions.RequestException as e:
        errors.append(f"请求商店页面时发生网络错误: {e}")
    except Exception as e:
        errors.append(f"提取标签时发生未知错误: {e}")

    return {"tags": tags, "error": "; ".join(errors) if errors else None}


def _extract_from_init_tag_modal(html: str, appid: str) -> list[str]:
    """
    从 InitAppTagModal(appid, ...) 调用中提取标签列表。

    页面中含有的调用示例：
        InitAppTagModal( 730,
            {"tagid":1662,"name":"Survival","count":283,"browseable":true},
            {"tagid":1659,"name":"Zombies","count":274,"browseable":true},
            ...
        )
    """
    start_tag = f"InitAppTagModal( {appid},"
    end_tag = "],"

    start = html.find(start_tag)
    if start == -1:
        return []

    start += len(start_tag)
    end = html.find(end_tag, start)
    if end == -1:
        return []

    raw = html[start:end] + "]"
    try:
        tag_objects = json.loads(raw)
        return [obj["name"] for obj in tag_objects if "name" in obj]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


def _extract_from_app_tag_elements(html: str) -> list[str]:
    """
    从 a.app_tag 元素中提取标签列表。

    页面中含有的元素示例：
        <a class="app_tag">Survival</a>
    """
    soup = BeautifulSoup(html, "html.parser")
    tag_elements = soup.select("a.app_tag")
    if not tag_elements:
        return []

    seen: set[str] = set()
    tags: list[str] = []
    for elem in tag_elements:
        name = elem.get_text(strip=True)
        if name and name not in seen:
            seen.add(name)
            tags.append(name)
    return tags
