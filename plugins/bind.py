from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg

import re

from plugins.db import get_backend
from plugins.message_reaction import reaction_cleanup
from plugins.protocol import nickname, plaintext, user_id

backend = get_backend()

bind = on_command("bind", aliases={"bind"}, priority=10, block=True)


@bind.handle()
async def handle_function(bot, event):
    cleanup = await reaction_cleanup(bot, event)
    userId = str(user_id(event))
    sender_name = nickname(event)

    record = backend.get_record("account", [("account", "eq", userId)])

    message_text = plaintext(event)
    steamid = re.findall(
        r"(?<=steamcommunity.com/profiles/)(\d+)|(\d{15,20})", message_text
    )

    if not steamid:
        if cleanup: await cleanup()
        await bind.finish("未检测到有效的Steam ID，需要的是那个16位左右的那个。")

    steamid = tuple(item for item in steamid[0] if item)[0]

    if "id" not in record:
        payload = {"account": userId, "steamId": steamid, "nickname": sender_name}
        result = backend.create_record("account", payload)
        if cleanup: await cleanup()
        await bind.finish(
            f"{sender_name}用户的id：{userId}\n{steamid}\n已被登记为第{result['id']}个结果"
        )
    else:
        payload = {
            "account": userId,
            "steamId": steamid,
            "nickname": sender_name,
        }
        result = backend.update_record("account", record["id"], payload)
        if record["id"] == result["id"]:
            if cleanup: await cleanup()
            await bind.finish(f"{sender_name}用户的id：{userId}\n{steamid}已被更新")
        else:
            if cleanup: await cleanup()
            await bind.finish(f"出现错误，请反馈")
