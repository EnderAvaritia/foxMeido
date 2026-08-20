from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import re

from plugins.db import get_record, create_record, update_record
from plugins.message_reaction import reaction_cleanup

bind = on_command("bind", aliases={"bind"}, priority=10, block=True)


@bind.handle()
async def handle_function(bot, event):
    cleanup = await reaction_cleanup(bot, event)
    userId = str(event.user_id)
    nickname = event.sender.nickname

    record = get_record("account", [("account", "eq", userId)])

    message_text = str(event.get_message())
    steamid = re.findall(
        r"(?<=steamcommunity.com/profiles/)(\d+)|(\d{15,20})", message_text
    )

    if not steamid:
        if cleanup: await cleanup()
        await bind.finish("未检测到有效的Steam ID，需要的是那个16位左右的那个。")

    steamid = tuple(item for item in steamid[0] if item)[0]

    if "id" not in record:
        payload = {"account": userId, "steamId": steamid, "nickname": nickname}
        result = create_record("account", payload)
        if cleanup: await cleanup()
        await bind.finish(
            f"{nickname}用户的id：{userId}\n{steamid}\n已被登记为第{result['id']}个结果"
        )
    else:
        payload = {
            "account": userId,
            "steamId": steamid,
            "nickname": nickname,
        }
        result = update_record("account", record["id"], payload)
        if record["id"] == result["id"]:
            if cleanup: await cleanup()
            await bind.finish(f"{nickname}用户的id：{userId}\n{steamid}已被更新")
        else:
            if cleanup: await cleanup()
            await bind.finish(f"出现错误，请反馈")
