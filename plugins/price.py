"""
price.py - 多区域价格比价命令

用法：
    price <游戏ID/商店链接>    例：price 1091500（别名：比价）

查询的区域列表由环境变量 PRICE_REGIONS 控制（逗号/空格分隔，可多个），
留空时使用默认集合（见 plugins/config.py DEFAULT_PRICE_REGIONS）。

输出按折合人民币升序排列，方便直接看出哪个区域最便宜。
结果在内存中缓存 15 分钟（价格随打折浮动，短时间不会变）。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg

from plugins.config import PRICE_REGIONS
from plugins.message_reaction import reaction_cleanup
from plugins.steam_utils import extract_steam_id, get_multi_region_prices

price_cmd = on_command("price", aliases={"比价"}, priority=10, block=True)

# 区域码 → 显示名（无 emoji，保持纯文本）
REGION_LABELS: dict[str, str] = {
    "cn": "中国", "us": "美国", "jp": "日本", "kr": "韩国",
    "hk": "中国香港", "tw": "中国台湾", "sg": "新加坡",
    "gb": "英国", "de": "德国", "fr": "法国", "es": "西班牙",
    "it": "意大利", "nl": "荷兰", "pl": "波兰", "se": "瑞典",
    "no": "挪威", "ch": "瑞士", "ru": "俄罗斯", "tr": "土耳其",
    "ar": "阿根廷", "br": "巴西", "mx": "墨西哥", "ca": "加拿大",
    "au": "澳大利亚", "nz": "新西兰",
    "in": "印度", "th": "泰国", "my": "马来西亚", "ph": "菲律宾",
    "id": "印度尼西亚", "vn": "越南",
    "ua": "乌克兰", "kz": "哈萨克斯坦",
    "sa": "沙特阿拉伯", "ae": "阿联酋", "il": "以色列",
    "cl": "智利", "co": "哥伦比亚", "pe": "秘鲁", "za": "南非",
    "cz": "捷克", "at": "奥地利", "be": "比利时", "pt": "葡萄牙",
}

# 内存缓存：{appid: (时间戳, 结果 dict)}，TTL 15 分钟
_CACHE_TTL = 15 * 60
_cache: dict[int, tuple[float, dict[str, Any]]] = {}


def _region_display(cc: str) -> str:
    """区域显示文本：已收录返回「US 美国」，未收录回退为大写区域码「RU」。"""
    label = REGION_LABELS.get(cc)
    return f"{cc.upper()} {label}" if label else cc.upper()


@price_cmd.handle()
async def handle_function(bot, event, args: Message = CommandArg()):
    cleanup = await reaction_cleanup(bot, event)
    raw = args.extract_plain_text().strip()
    if not raw:
        if cleanup:
            await cleanup()
        await price_cmd.finish("用法：price <游戏ID/商店链接>，例：price 1091500")
    appid = extract_steam_id(raw)
    if not appid:
        if cleanup:
            await cleanup()
        await price_cmd.finish(f"无法从「{raw}」识别游戏 ID，支持纯数字或 Steam 商店链接")

    try:
        data = await asyncio.to_thread(_query_with_cache, int(appid))
        if data is None:
            if cleanup:
                await cleanup()
            await price_cmd.finish(f"获取 AppID {appid} 的各区价格失败，请稍后重试或检查 PRICE_REGIONS")
        if data.get("error"):
            if cleanup:
                await cleanup()
            reason = data["error"]
            if data.get("name"):
                await price_cmd.finish(f"{data['name']}（AppID {appid}）：{reason}")
            await price_cmd.finish(f"AppID {appid}：{reason}")
        await price_cmd.send(message=_format_result(data), at_sender=False)
    finally:
        if cleanup:
            await cleanup()


def _query_with_cache(appid: int) -> dict[str, Any] | None:
    """带内存 TTL 缓存地查询多区价格。"""
    now = time.time()
    cached = _cache.get(appid)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]
    try:
        result = get_multi_region_prices(appid, PRICE_REGIONS)
    except Exception:
        result = None
    if result and result.get("rows"):
        _cache[appid] = (now, result)
    return result


def _cny_text(cny: float | None) -> str:
    """折合人民币文本；无汇率数据时返回空串（只显示原币）。"""
    if cny is None:
        return ""
    return f"≈¥{cny:,.2f}"


def _format_result(data: dict[str, Any]) -> str:
    """将多区价格结果格式化为纯文本（按折合人民币升序，无 emoji）。"""
    rows = [r for r in data.get("rows", []) if not r.get("error")]
    # 排序：免费(=0)/可换算的在前，汇率缺失的排最后
    rows.sort(key=lambda r: (r.get("cny") is None, r.get("cny") if r.get("cny") is not None else 0.0))

    name = data.get("name") or f"AppID {data.get('appid')}"
    lines = [f"{name}（AppID {data.get('appid')}）各区现价，按折合人民币升序"]

    for row in rows:
        cc = row["cc"]
        label = _region_display(cc)
        if row.get("is_free"):
            lines.append(f"{label}  免费")
            continue
        local = row.get("final_formatted") or f"{row['final']:.2f} {row['currency']}"
        # 人民币区：本地价即人民币，不再重复折算；外币区附折合人民币便于比较
        tail = "" if row.get("currency") == "CNY" else _cny_text(row.get("cny"))
        extra = ""
        if row.get("discount_percent"):
            original = row.get("initial_formatted") or f"{row['initial']:.2f}"
            extra = f"（-{row['discount_percent']}%，原价 {original}）"
        lines.append(f"{label}  {local} {tail} {extra}".rstrip())

    # 无价格区域分三类展示：锁区/下架、未上架/不可购买、网络异常
    if data.get("locked"):
        lines.append("锁区/下架：" + "、".join(_region_display(cc) for cc in data["locked"]))
    if data.get("unavailable"):
        lines.append("无价格（未上架/不可购买）："
                     + "、".join(_region_display(cc) for cc in data["unavailable"]))
    if data.get("failed"):
        lines.append("请求失败（网络异常，可稍后重试）："
                     + "、".join(_region_display(cc) for cc in data["failed"]))

    priced = [r for r in rows if not r.get("is_free") and r.get("cny") is not None]
    if len(priced) >= 1 and rows:
        cheapest = min(priced, key=lambda r: r["cny"])
        lines.append(
            f"最低：{_region_display(cheapest['cc'])} ¥{cheapest['cny']:,.2f}"
        )
    return "\n".join(lines)
