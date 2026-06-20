from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import datetime
import requests
import json

from . import noco_config as cfg
from . import noco_utils as utils
from plugins.steam_utils import extract_steam_id, get_game_info
from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

wish = on_command("wish", aliases={"wish"}, priority=10, block=True)


def add_to_wishlist(appid: str | int, cookie: str) -> bool:
    """将指定 appid 的游戏加入 Steam 愿望单"""
    url = "https://store.steampowered.com/api/addtowishlist"
    payload = {"appid": str(appid)}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.5",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://store.steampowered.com",
        "Sec-GPC": "1",
        "Referer": "https://store.steampowered.com/app/4013460/_/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Cookie": cookie.strip(),
    }

    response = requests.post(url, data=payload, headers=headers, proxies=cfg.PROXIES)
    try:
        data = response.json()
    except ValueError:
        return False
    return "wishlistCount" in data


@wish.handle()
async def handle_function(bot, event):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    userId = event.user_id
    nickname = event.sender.nickname

    goodId = extract_steam_id(str(event.message).strip())
    if not goodId:
        await wish.finish("你确定这是商品的id？")

    gameInfo = get_game_info(goodId)

    if cfg.WISH_ADD_TO_STEAM and cfg.STEAM_COOKIE:
        result = add_to_wishlist(goodId, cfg.STEAM_COOKIE)
        print(f"愿望单添加{'成功' if result else '失败'}")
    if "error" in gameInfo:
        await wish.finish(f"游戏{goodId}数据获取出错，请反馈")

    accountUrl = cfg.url_with_filter(cfg.ACCOUNT_TABLE_ID, f"(account,eq,{userId})")
    accountRecord = utils.get_record(accountUrl)
    if "id" not in accountRecord:
        await wish.finish(f"请id为{userId}的\n{nickname}先使用bind指令进行登记")

    wishlistUrl = cfg.url_with_filter(
        cfg.WISHLIST_TABLE_ID, f"(gameId,eq,{goodId})~and(userId,eq,{userId})"
    )
    wishlistRecord = utils.get_record(wishlistUrl)

    if "id" in wishlistRecord:
        updatePayload = {
            "id": wishlistRecord["id"],
            "gameId": goodId,
            "gameName": gameInfo["game_name"],
            "releaseDate": gameInfo["release_date"],
        }
        updated = utils.update_record(cfg.table_url(cfg.WISHLIST_TABLE_ID), updatePayload)
        if wishlistRecord["id"] == updated["id"]:
            await wish.finish(
                f'id为{goodId}的游戏\n《{gameInfo["game_name"]}》\n'
                f'已经在{wishlistRecord["submitTime"]}被你许过愿了'
            )
    else:
        dayTime = datetime.date.today().strftime("%Y-%m-%d")
        link = f"https://store.steampowered.com/app/{goodId}"
        createPayload = {
            "gameId": goodId,
            "gameName": gameInfo["game_name"],
            "userId": accountRecord["account"],
            "userName": accountRecord["nickname"],
            "steamId": accountRecord["steamId"],
            "Link": link,
            "submitTime": dayTime,
            "publisher": gameInfo["publisher"],
            "releaseDate": gameInfo["release_date"],
        }
        recordResult = utils.create_record(cfg.table_url(cfg.WISHLIST_TABLE_ID), createPayload)
        if "id" not in recordResult:
            await wish.finish(f"登记阶段出现未知错误，请反馈")
        else:
            await wish.finish(
                f'id为{userId}的用户{nickname}\n'
                f'对id为{goodId}的游戏《{gameInfo["game_name"]}》\n'
                f'成功登记为第{recordResult["id"]}个许愿\n'
                f'预计发行日期为：{gameInfo["release_date"]}'
            )
