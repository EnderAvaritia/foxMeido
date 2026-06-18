from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import re

from . import noco_config as cfg
from . import noco_utils as utils
from plugins.steam_utils import extract_steam_id
from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

queryWishlist = on_command("queryWishlist", aliases={"queryWishlist","queryWish","qwish"}, priority=10, block=True)


def format_wishlist_response(data: dict) -> str:
    """格式化wishlist查询结果"""
    if "error" in data:
        return f"查询失败: {data['error']}"
    if "list" not in data or not data["list"]:
        return "未找到相关许愿记录"

    game_name = data["list"][0].get("gameName", "未知游戏")
    lines = [f"《{game_name}》", ""]
    for idx, item in enumerate(data["list"], start=1):
        lines.append(
            f"{item.get('userName', '未知用户')}在"
            f"{item.get('submitTime', '未知时间')}第{idx}个请求"
        )
    total = data.get("pageInfo", {}).get("totalRows", 0)
    lines.append(f"\r\n共找到 {total} 条记录")
    return "\r\n".join(lines)


@queryWishlist.handle()
async def handle_function(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    input_text = args.extract_plain_text().strip()
    if not input_text:
        await queryWishlist.finish("请输入游戏ID，格式: queryWishlist [gameId]")

    game_id = extract_steam_id(input_text) or input_text

    url = cfg.url_with_filter(cfg.WISHLIST_TABLE_ID, f"(gameId,eq,{game_id})", sort="submitTime")
    records_data = utils.get_records(url)
    output = format_wishlist_response(records_data)
    await queryWishlist.finish(output)