"""
report.py - 更新record表中指定游戏的report字段

功能：
1. 使用 report 指令更新指定游戏的report字段为1
2. 指令格式：report 游戏ID 或 report Steam链接
3. 示例：
   - report 730 （将CS:GO的所有记录标记为已报告）
   - report 570 （将Dota 2的所有记录标记为已报告）
   - report https://store.steampowered.com/app/730/ （从Steam链接提取游戏ID并标记为已报告）

工作原理：
1. 从输入中提取游戏ID（支持纯数字ID和Steam链接）
2. 查询record表中指定gameId且report为0的记录
3. 将查询到的所有记录的report字段更新为1
4. 输出更新结果统计
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

report = on_command("report", aliases={"report"}, priority=10, block=True)


def batch_update_records(records: list) -> tuple[int, int, list[str]]:
    """批量更新多条记录的report字段"""
    success = 0
    failed = 0
    details: list[str] = []
    url = cfg.table_url(cfg.RECORD_TABLE_ID)
    for r in records:
        rid = r.get("id")
        name = r.get("userName", "未知用户")
        game = r.get("gameName", "未知游戏")
        result = utils.update_record(url, {"id": rid, "report": 1})
        if "error" in result:
            failed += 1
            details.append(f"{name} - {game}: 更新失败 ({result['error']})")
        else:
            success += 1
            details.append(f"{name} - {game}: 已标记为已报告")
    return success, failed, details


@report.handle()
async def handle_function(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await report.finish(
            "请输入游戏ID或Steam链接，格式：report 游戏ID"
        )

    game_id = extract_steam_id(arg_text)
    if not game_id and arg_text.isdigit():
        game_id = arg_text
    if not game_id:
        await report.finish("无法识别游戏ID，请提供纯数字ID或Steam商店链接")

    await report.send(f"正在查询游戏ID为 {game_id} 的未报告记录...")

    url = cfg.url_with_filter(
        cfg.RECORD_TABLE_ID, f"(gameId,eq,{game_id})~and(report,eq,0)"
    )
    records_data = utils.get_records(url)

    if "error" in records_data:
        await report.finish(f"查询失败: {records_data['error']}")
    if "list" not in records_data or not records_data["list"]:
        await report.finish(f"游戏ID {game_id} 没有找到未报告（report=0）的记录")

    records = records_data["list"]
    game_name = records[0].get("gameName", f"ID: {game_id}")

    await report.send(f"找到 {len(records)} 条未报告记录，游戏：{game_name}")
    await report.send("开始更新report字段为1...")

    success, failed, details = batch_update_records(records)
    lines = [
        f"游戏《{game_name}》(ID: {game_id}) 报告状态更新完成：",
        f"总记录数: {len(records)}",
        f"成功更新: {success}",
        f"更新失败: {failed}",
        "",
        "详细信息：",
    ]
    lines.extend(details)
    await report.finish("\r\n".join(lines))