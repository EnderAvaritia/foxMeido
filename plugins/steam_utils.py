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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import urllib3

import requests

from bs4 import BeautifulSoup

from plugins.env_utils import get_proxies
from plugins.config import STEAM_COOKIE, STEAM_CC
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


def get_game_screenshots(appid: int | str) -> list[str]:
    """
    通过 Steam Web API 获取游戏全部截图缩略图（path_thumbnail）URL 列表。

    Args:
        appid: Steam AppID。

    Returns:
        list[str]: 截图缩略图 URL 列表，无截图或出错时返回空列表。
    """
    try:
        details = _fetch_app_data(appid)
        if not details:
            return []
        screenshots = details.get("screenshots") or []
        return [
            s.get("path_thumbnail")
            for s in screenshots
            if s.get("path_thumbnail")
        ]
    except Exception as e:
        log_error("steam_utils.get_game_screenshots", f"获取截图异常 (AppID: {appid}): {e}")
        return []


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


# ── 多区域价格比价（price 命令用）────────────────────────────────

# 匿名请求也附带这组 Cookie，绕过成人内容的年龄验证导致的价格缺失
_AGE_GATE_COOKIE = "birthtime=1; lastagecheckage=1; wants_mature_content=1"

# 汇率来源：open.er-api.com（免费，每日更新，基准 CNY）
_CNY_RATES_URL = "https://open.er-api.com/v6/latest/CNY"


def _fetch_region_price(
    appid: int | str, cc: str
) -> tuple[dict[str, Any] | None, str]:
    """
    请求指定区域（cc）的价格，只取 price_overview 字段，返回 (data, status)。

    用 filters=price_overview 把响应压到几百字节（不带 filter 是全量，往往数百 KB）。
    不做登录态，仅带年龄 Cookie —— 保证 cc 参数决定货币，
    不受 STEAM_COOKIE 账户所属区域干扰。

    返回 status 语义：
      "ok"     - 请求成功（data 含 price_overview，或空 dict：免费/该区无价）
      "locked" - success=false：该区锁区/下架/AppID 无效
      （网络/HTTP 异常由调用方捕获，归为 "error"）
    """
    api_url = (
        f"https://store.steampowered.com/api/appdetails?appids={appid}"
        f"&l=schinese&cc={cc}&filters=price_overview"
    )
    request_kwargs: dict[str, Any] = {
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36",
            "Cookie": _AGE_GATE_COOKIE,
        },
        "timeout": 15,
    }
    proxy_cfg = get_proxies()
    if proxy_cfg:
        request_kwargs["proxies"] = proxy_cfg
        request_kwargs["verify"] = False
    response = requests.get(api_url, **request_kwargs)
    response.raise_for_status()
    data = response.json()
    app_data = data.get(str(appid))
    if app_data and app_data.get("success"):
        return app_data.get("data"), "ok"
    return None, "locked"


def _fetch_meta(appid: int | str) -> dict[str, Any] | None:
    """
    获取游戏基础元数据（名称、是否免费），供比价结果展示与免费游戏判定。

    固定用 cc=us 请求：元数据不受"宿主出口区域"限制 —— 即使某游戏在机器人
    所在区域锁区，仍能拿到名称和 is_free，不会把锁区游戏误判成"无效 AppID"。

    优先用 filters=basic（响应较小）；若该响应不含 is_free 字段（无法确认
    免费），则回退一次全量请求（同样 cc=us），保证免费游戏不被误判。
    """
    api_url = (
        f"https://store.steampowered.com/api/appdetails?appids={appid}"
        f"&l=schinese&cc=us&filters=basic"
    )
    request_kwargs: dict[str, Any] = {
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36",
            "Cookie": _AGE_GATE_COOKIE,
        },
        "timeout": 15,
    }
    proxy_cfg = get_proxies()
    if proxy_cfg:
        request_kwargs["proxies"] = proxy_cfg
        request_kwargs["verify"] = False
    try:
        response = requests.get(api_url, **request_kwargs)
        response.raise_for_status()
        data = response.json()
        app_data = data.get(str(appid))
        if app_data and app_data.get("success"):
            meta = app_data.get("data") or {}
            if "is_free" in meta:
                return meta
            # basic 未返回 is_free → 用全量请求兜底，确保免费游戏识别正确
            return _fetch_app_data(appid, "us")
    except Exception as e:
        log_error("steam_utils._fetch_meta", f"获取游戏元数据异常 (AppID: {appid}): {e}")
        try:
            return _fetch_app_data(appid, "us")
        except Exception:
            return None
    return None


def _fetch_cny_rates() -> dict[str, float]:
    """
    拉取 1 CNY 可兑换的各币种汇率表（open.er-api，基准 CNY）。

    Returns:
        dict：{货币码: 每 1 CNY 可兑换的币种数量}；失败返回空 dict。
    """
    request_kwargs: dict[str, Any] = {
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        },
        "timeout": 10,
    }
    proxy_cfg = get_proxies()
    if proxy_cfg:
        request_kwargs["proxies"] = proxy_cfg
        request_kwargs["verify"] = False
    try:
        response = requests.get(_CNY_RATES_URL, **request_kwargs)
        response.raise_for_status()
        data = response.json()
        if data.get("result") == "success":
            return data.get("rates") or {}
    except Exception as e:
        log_error("steam_utils._fetch_cny_rates", f"获取汇率异常: {e}")
    return {}


def get_multi_region_prices(
    appid: int | str, regions: list[str]
) -> dict[str, Any]:
    """
    并发查询同一游戏在多个区域的价格，并按汇率换算成人民币（CNY）便于比较。

    区域请求只取价格（filters=price_overview，约几百字节/区）；
    游戏名与是否免费通过一次元数据请求获得（filters=basic，cc=us 固定，
    不受宿主区域锁区影响；缺 is_free 时回退全量）。
    实际请求数 ≈ 区域数 + 1，限制并发 5，远低于 Steam 限流（约 200 请求/5 分钟/IP）。
    价格随打折浮动，由调用方决定是否缓存。

    Args:
        appid: Steam AppID。
        regions: 区域码列表（小写 cc，如 ["cn", "us", "jp"]）。

    Returns:
        dict：包含 name、rows（各区域价格，已折算 cny）、locked（锁区/下架区）、
        unavailable（未上架/不可购买区）、failed（网络异常区）。
        rows 元素键：cc / currency / is_free / final_formatted / initial_formatted
                     / discount_percent / final / initial / cny / cny_ok。
        全部区域无价格时返回 {"error": ...}（游戏存在则说明锁区/未上架，
        AppID 无效则说明获取失败）。
    """
    if not regions:
        return {"error": "未配置任何查询区域"}

    # 元数据仅请求一次（固定 cc=us，避免宿主区域锁区影响名称/免费判定），
    # 区域请求保持只取价格（filters=price_overview），避免每个区域都拉全量
    meta = _fetch_meta(appid)
    meta_free = bool(meta and meta.get("is_free"))
    name = meta.get("name") if meta else None

    def _fetch_one(cc: str) -> tuple[str, dict[str, Any] | None, str]:
        try:
            data, status = _fetch_region_price(appid, cc)
            return cc, data, status
        except Exception as e:
            log_error(
                "steam_utils.get_multi_region_prices",
                f"区域 {cc} 请求异常 (AppID: {appid}): {e}",
            )
            return cc, None, "error"

    rows: list[dict[str, Any]] = []
    locked: list[str] = []      # success=false → 该区锁区/下架
    unavailable: list[str] = []  # 成功但无价格，且非免费 → 未上架/不可购买
    failed: list[str] = []      # 网络/HTTP 异常（瞬时，可重试）
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_fetch_one, cc) for cc in regions]
        for future in as_completed(futures):
            cc, data, status = future.result()
            if status == "error":
                failed.append(cc)
                continue
            if status == "locked":
                locked.append(cc)
                continue

            price = (data or {}).get("price_overview")
            if not price:
                if meta_free:
                    # 游戏本身免费：该区无 price_overview 属正常，标记为免费
                    rows.append({
                        "cc": cc,
                        "currency": "FREE",
                        "is_free": True,
                        "final_formatted": "免费",
                        "initial_formatted": "",
                        "discount_percent": 0,
                        "final": 0.0,
                        "initial": 0.0,
                        "cny": 0.0,
                        "cny_ok": True,
                    })
                else:
                    # 非免费但无价格：该区未上架/不可购买
                    unavailable.append(cc)
                continue

            rows.append({
                "cc": cc,
                "currency": price.get("currency"),
                "is_free": False,
                "final_formatted": price.get("final_formatted") or "",
                "initial_formatted": price.get("initial_formatted") or "",
                "discount_percent": int(price.get("discount_percent") or 0),
                "final": int(price.get("final") or 0) / 100,
                "initial": int(price.get("initial") or 0) / 100,
                "cny": None,
                "cny_ok": False,
            })

    if not rows:
        if meta:
            # 元数据拿得到（游戏真实存在）→ 提示锁区/未上架，而非网络错误
            parts = []
            if locked:
                parts.append("锁区/下架：" + "、".join(locked))
            if unavailable:
                parts.append("未上架/不可购买：" + "、".join(unavailable))
            if failed:
                parts.append("请求失败：" + "、".join(failed))
            return {
                "name": name,
                "appid": appid,
                "rows": [],
                "locked": locked,
                "unavailable": unavailable,
                "failed": failed,
                "error": "该游戏在查询区域均不可购买（" + "；".join(parts) + "）",
            }
        return {
            "name": None,
            "appid": appid,
            "rows": [],
            "locked": locked,
            "unavailable": unavailable,
            "failed": failed,
            "error": "获取游戏信息失败（AppID 无效，或网络异常）",
        }

    # 折算人民币：1 CNY 可兑 X 外币 → 折合 CNY = final / rates[外币]
    currencies = {r["currency"] for r in rows if not r["is_free"]}
    rates = _fetch_cny_rates() if currencies else {}
    for row in rows:
        cur = row["currency"]
        if row["is_free"]:
            continue
        if cur == "CNY":
            row["cny"] = row["final"]
            row["cny_ok"] = True
            continue
        rate = rates.get(cur)
        if rate:
            row["cny"] = row["final"] / rate
            row["cny_ok"] = True

    return {
        "name": name,
        "appid": appid,
        "rows": rows,
        "locked": locked,
        "unavailable": unavailable,
        "failed": failed,
    }
