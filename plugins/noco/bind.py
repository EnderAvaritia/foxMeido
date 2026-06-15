from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import re

from . import noco_config as cfg
from . import noco_utils as utils
from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

bind = on_command("bind", aliases={"bind"}, priority=10, block=True)


@bind.handle()
async def handle_function(bot, event):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    userId = str(event.user_id)
    nickname = event.sender.nickname

    url = cfg.url_with_filter(cfg.ACCOUNT_TABLE_ID, f"(account,eq,{userId})")
    record = utils.get_record(url)

    message_text = str(event.get_message())
    steamid = re.findall(
        r"(?<=steamcommunity.com/profiles/)(\d+)|(\d{15,20})", message_text
    )

    if not steamid:
        await bind.finish("未检测到有效的Steam ID，需要的是那个16位左右的那个。")

    steamid = tuple(item for item in steamid[0] if item)[0]

    url = cfg.table_url(cfg.ACCOUNT_TABLE_ID)
    if "id" not in record:
        payload = {"account": userId, "steamId": steamid, "nickname": nickname}
        result = utils.create_record(url, payload)
        await bind.finish(
            f"{nickname}用户的id：{userId}\n{steamid}\n已被登记为第{result['id']}个结果"
        )
    else:
        payload = {
            "id": record["id"],
            "account": userId,
            "steamId": steamid,
            "nickname": nickname,
        }
        result = utils.update_record(url, payload)
        if record["id"] == result["id"]:
            await bind.finish(f"{nickname}用户的id：{userId}\n{steamid}已被更新")
        else:
            await bind.finish(f"出现错误，请反馈")

