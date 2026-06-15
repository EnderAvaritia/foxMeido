"""
unreported.py - 输出record表中report为0的项目

功能：
1. 查询record表中report为0的记录
2. 按gameId排序
3. 按游戏分组输出用户
4. 输出格式：{gameName}:\r\n{userName}\r\n{userName}\r\n
"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import re

from . import noco_config as cfg
from . import noco_utils as utils
from plugins.steam_utils import extract_steam_id
from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

unreported = on_command("unreported", aliases={"unreported"}, priority=10, block=True)


def format_unreported_output(records_data: dict) -> str:
    """格式化未报告记录的输出"""
    if "error" in records_data:
        return f"获取记录失败: {records_data['error']}"
    if "list" not in records_data or not records_data["list"]:
        return "没有找到report为0的记录"

    records = records_data["list"]
    game_records: dict[str, list] = {}
    for r in records:
        name = r.get("gameName", "未知游戏")
        game_records.setdefault(name, [])
        game_records[name].append(r)

    lines: list[str] = []
    for game_name, recs in game_records.items():
        lines.append(f"{game_name}:")
        gid = recs[0].get("gameId", "")
        lines.append(
            f"https://store.steampowered.com/app/{gid}/?curator_clanid={cfg.CURATOR_ID}"
        )
        for r in recs:
            lines.append(r.get("userName", "未知用户"))
            lines.append(
                "未完成" if r.get("submitTime") is None else r.get("Link", "未知链接")
            )
        lines.append("")

    total = records_data.get("pageInfo", {}).get("totalRows", len(records))
    lines.append(f"共找到 {total} 条未报告记录")
    return "\r\n".join(lines)


@unreported.handle()
async def handle_function(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    arg_text = args.extract_plain_text().strip()
    game_id = None

    if arg_text:
        game_id = extract_steam_id(arg_text)
        if not game_id and re.match(r"^\d+$", arg_text):
            game_id = arg_text
        if not game_id:
            await unreported.finish("请输入有效的游戏ID或Steam商店链接")

    if game_id:
        await unreported.send(f"正在查询游戏ID {game_id} 的未报告（report=0）记录...")
    else:
        await unreported.send("正在查询所有未报告（report=0）的记录...")

    where = f"(report,eq,0)"
    if game_id:
        where += f"~and(gameId,eq,{game_id})"
    url = cfg.url_with_filter(cfg.RECORD_TABLE_ID, where, sort="gameId")

    records_data = utils.get_records(url)
    output = format_unreported_output(records_data)
    await unreported.finish(output)