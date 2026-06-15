"""
unfinished.py - 输出record表中未完成的内容

功能：
1. 查询record表中submitTime为null的记录
2. 按userId排序
3. 按用户分组输出未完成的游戏
4. 输出格式：{username}未完成{gameName}：{getTime}
"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

from . import noco_config as cfg
from . import noco_utils as utils
from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

unfinished = on_command("unfinished", aliases={"unfinished"}, priority=10, block=True)


def format_unfinished_output(records_data: dict) -> str:
    """格式化未完成记录的输出"""
    if "error" in records_data:
        return f"获取记录失败: {records_data['error']}"
    if "list" not in records_data or not records_data["list"]:
        return "没有找到未完成的记录"

    records = records_data["list"]
    user_records: dict[str, list[dict]] = {}
    for r in records:
        name = r.get("userName", "未知用户")
        user_records.setdefault(name, [])
        user_records[name].append(r)

    lines: list[str] = []
    for user_name, games in user_records.items():
        lines.append(f"用户{user_name}未完成：")
        for g in games:
            lines.append(f"{g.get('gameName', '未知游戏')}：{g.get('getTime', '未知时间')}")
        lines.append("")

    total = records_data.get("pageInfo", {}).get("totalRows", len(records))
    lines.append(f"共找到 {total} 条未完成记录")
    return "\r\n".join(lines)


@unfinished.handle()
async def handle_function(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    await unfinished.send("正在查询未完成的记录...")

    url = cfg.url_with_filter(cfg.RECORD_TABLE_ID, "(submitTime,eq,null)", sort="userId")
    records_data = utils.get_records(url)
    output = format_unfinished_output(records_data)

    await unfinished.finish(output)