"""
probe.py - 检测record表中的link是否有效

功能：
1. 查询record表中submitTime为null的记录
2. 对每个记录的link进行请求
3. 检查响应标题是否包含"评测"或"Review"
4. 如果成功，更新submitTime为当前日期
5. 输出完成检测的用户和游戏列表

输出格式：
{userName}完成了：
{gameName}
{gameName}
...
"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import datetime
import requests
import json
import re
import time

from . import noco_config as cfg
from . import noco_utils as utils

probe = on_command("probe", aliases={"probe"}, priority=10, block=True)


def check_link_valid(link: str) -> tuple[bool, str]:
    """检查链接是否有效，标题是否包含'评测'或'Review'"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(
            link, headers=headers, timeout=10, proxies=cfg.PROXIES, verify=cfg.VERIFY_SSL
        )
        response.raise_for_status()
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL
        )
        if title_match:
            title = title_match.group(1).strip()
            if "评测" in title or "Review" in title:
                return True, title
            return False, title
        return False, "未找到标题标签"
    except Exception as e:
        return False, str(e)


def format_output(completed_records: list) -> str:
    """格式化输出结果"""
    if not completed_records:
        return "本次检测没有发现新的完成记录"
    user_records: dict[str, list] = {}
    for r in completed_records:
        name = r.get("userName", "未知用户")
        user_records.setdefault(name, [])
        user_records[name].append(r)
    lines: list[str] = []
    for user_name, records in user_records.items():
        lines.append(f"{user_name}完成了：")
        for r in records:
            lines.append(r.get("gameName", "未知游戏"))
            lines.append(r.get("Link", "未知链接"))
        lines.append("")
    return "\r\n".join(lines)


@probe.handle()
async def handle_function(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    await probe.send("开始检测record表中的link有效性...")

    url = cfg.url_with_filter(cfg.RECORD_TABLE_ID, "(submitTime,eq,null)", sort="userId")
    records_data = utils.get_records(url)

    if "error" in records_data:
        await probe.finish(f"获取记录失败: {records_data['error']}")
    if "list" not in records_data or not records_data["list"]:
        await probe.finish("没有找到submitTime为null的记录")

    records = records_data["list"]
    page_info = records_data.get("pageInfo", {})
    total_rows = page_info.get("totalRows", len(records))
    await probe.send(f"找到 {total_rows} 条需要检测的记录（本次处理 {len(records)} 条）")

    completed_records = []
    checked_count = 0
    success_count = 0

    for record in records:
        checked_count += 1
        link = record.get("Link")
        if not link:
            continue

        is_valid, _ = check_link_valid(link)
        if is_valid:
            today = datetime.date.today().strftime("%Y-%m-%d")
            payload = {"id": record["id"], "submitTime": today}
            result = utils.update_record(cfg.table_url(cfg.RECORD_TABLE_ID), payload)
            if "error" not in result:
                success_count += 1
                completed_records.append(record)
        time.sleep(1)

    output = format_output(completed_records)
    stats = f"\r\n\r\n检测完成！\r\n共检测 {checked_count} 条记录\r\n成功更新 {success_count} 条记录"
    await probe.finish(output + stats)