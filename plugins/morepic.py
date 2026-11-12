"""
morepic.py - 发送游戏全部截图缩略图

用法：morepic <游戏ID/商店链接>
从 Steam Web API 的 appdetails.data.screenshots 中取全部截图，仅发送 path_thumbnail。
"""

import asyncio

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg

from plugins.steam_utils import extract_steam_id, get_game_screenshots
from plugins.message_reaction import reaction_cleanup
from plugins.protocol import image, send, text


morepic = on_command("morepic", aliases={"更多截图"}, priority=10, block=True)


@morepic.handle()
async def handle_function(bot, event, args: Message = CommandArg()):
    cleanup = await reaction_cleanup(bot, event)
    try:
        args_str = args.extract_plain_text().strip()
        appid = extract_steam_id(args_str)
        if not appid:
            await send(f"你确定\"{args_str}\"是游戏的id？", matcher=morepic, finish=True)

        screenshots = await asyncio.to_thread(get_game_screenshots, appid)
        if not screenshots:
            await send(f"游戏{appid}未获取到截图，请反馈", matcher=morepic, finish=True)

        msg = text("")
        for i, url in enumerate(screenshots):
            if i > 0:
                msg += text("\n")
            msg += image(url=url)
        await send(msg, matcher=morepic)
    finally:
        if cleanup:
            await cleanup()
