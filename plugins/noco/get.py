from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import datetime
import json
import re

from . import noco_config as cfg
from . import noco_utils as utils
from plugins.noco_utils import extract_steam_id, get_game_info

get = on_command("get", aliases={"get"}, priority=10, block=True)


@get.handle()
async def handle_function(event: MessageEvent, args: Message = CommandArg()):
    args_str = args.extract_plain_text().strip()
    params = args_str.split()

    if len(params) == 2:
        goodId_str = params[0]
        userId_str = params[1]
        try:
            userId = int(userId_str)
        except ValueError:
            await get.finish(f"用户ID格式错误：{userId_str}")
        nickname = event.sender.nickname
    elif len(params) == 1:
        goodId_str = params[0]
        userId = event.user_id
        nickname = event.sender.nickname
    else:
        await get.finish(
            "参数错误！用法：\n1. get <商品ID> - 为自己登记\n2. get <商品ID> <用户ID> - 为指定用户登记"
        )

    goodId = extract_steam_id(goodId_str)
    if not goodId:
        await get.finish("你确定这是商品的id？")
    gameInfo = get_game_info(goodId)
    if "error" in gameInfo:
        await get.finish(f"游戏{goodId}数据获取出错，请反馈")

    # 检查游戏剩余数量
    remainUrl = cfg.url_with_filter(cfg.REMAIN_TABLE_ID, f"(gameId,eq,{goodId})")
    remainGameRecord = utils.get_record(remainUrl)
    if "id" not in remainGameRecord:
        await get.finish(
            f'id为{goodId}的游戏\n《{gameInfo["game_name"]}》尚未收录\n请联系厂商'
        )
    elif remainGameRecord["getedCount"] >= remainGameRecord["totalCount"]:
        await get.finish(
            f'id为{goodId}的游戏\n《{gameInfo["game_name"]}》已领取完毕\n无剩余'
        )

    # 检查账号绑定
    accountUrl = cfg.url_with_filter(cfg.ACCOUNT_TABLE_ID, f"(account,eq,{userId})")
    accountRecord = utils.get_record(accountUrl)
    if "id" not in accountRecord:
        await get.finish(f"用户ID {userId} 尚未绑定，请先使用bind指令进行登记")

    # 检查是否已登记过该游戏
    checkUrl = cfg.url_with_filter(
        cfg.RECORD_TABLE_ID, f"(gameId,eq,{goodId})~and(userId,eq,{userId})"
    )
    existingRecord = utils.get_record(checkUrl)
    if "id" in existingRecord:
        await get.finish(
            f'用户ID {userId} (昵称: {accountRecord["nickname"]})\n'
            f'已经登记过游戏ID {goodId}《{gameInfo["game_name"]}》\n'
            f'登记ID: {existingRecord["id"]}'
        )

    dayTime = datetime.date.today().strftime("%Y-%m-%d")
    link = (
        f'https://steamcommunity.com/profiles/{accountRecord["steamId"]}/recommended/{goodId}'
    )

    # 创建登记记录
    recordPayload = {
        "gameId": goodId,
        "gameName": gameInfo["game_name"],
        "userId": accountRecord["account"],
        "userName": accountRecord["nickname"],
        "steamId": accountRecord["steamId"],
        "Link": link,
        "getTime": dayTime,
        "publisher": gameInfo["publisher"],
    }
    recordResult = utils.create_record(cfg.table_url(cfg.RECORD_TABLE_ID), recordPayload)
    if "id" not in recordResult:
        await get.finish(f"登记阶段出现未知错误，请反馈")

    # 更新 remain 表格
    canBeClaimed = remainGameRecord["totalCount"] - remainGameRecord["getedCount"] - 1
    remainPayload = {
        "id": remainGameRecord["id"],
        "gameId": goodId,
        "gameName": gameInfo["game_name"],
        "totalCount": remainGameRecord["totalCount"],
        "getedCount": remainGameRecord["getedCount"] + 1,
        "canBeClaimed": canBeClaimed,
    }
    remain = utils.update_record(cfg.table_url(cfg.REMAIN_TABLE_ID), remainPayload)
    if "id" in remain:
        await get.finish(
            f'用户ID {userId} (昵称: {accountRecord["nickname"]})\n'
            f'对游戏ID {goodId}《{gameInfo["game_name"]}》\n'
            f'成功登记为第{recordResult["id"]}个结果\n'
            f'游戏剩余{remainGameRecord["totalCount"] - remainGameRecord["getedCount"] - 1}个'
        )
