"""
remain.py - 剩余游戏登记和查询插件

功能：
1. 使用 remain 指令登记剩余的游戏份数
2. 使用 remain 指令查询游戏的当前领取情况
3. 指令格式：
   - remain 游戏ID/URL 份数 （登记或更新份数）
   - remain 游戏ID/URL （查询当前领取情况）
4. 示例：
   - remain 730 5 （登记CS:GO 5份）
   - remain https://store.steampowered.com/app/730 5 （通过URL登记CS:GO 5份）
   - remain 730 （查询CS:GO当前领取情况）
   - remain https://store.steampowered.com/app/730 （通过URL查询当前领取情况）

表格字段：
- gameId: 游戏ID（Steam AppID）
- gameName: 游戏名称（通过Steam API自动获取）
- totalCount: 总份数（通过指令参数设置）
- getedCount: 已领取份数（初始为0）
"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import re

from . import noco_config as cfg
from . import noco_utils as utils
from plugins.steam_utils import extract_steam_id, get_game_info

remain = on_command("remain", aliases={"remain"}, priority=10, block=True)


@remain.handle()
async def handle_function(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    arg_text = args.extract_plain_text().strip()

    # ── 无参数：列出所有可领取的游戏 ──
    if not arg_text:
        url = cfg.url_with_filter(
            cfg.REMAIN_TABLE_ID, "(canBeClaimed,gt,0)", sort="created_at"
        )
        try:
            data = utils.get_records(url)
            if "error" in data:
                await remain.finish(f"查询出错: {data['error']}")
            games = data.get("list", [])
            if not games:
                await remain.finish("当前没有可领取的游戏")
            lines = []
            for g in games:
                c = int(g.get("canBeClaimed", 0))
                lines.append(f"《{g.get('gameName', '未知游戏')}》剩余{c}个")
            await remain.finish("\r\n".join(lines))
        except Exception as e:
            await remain.finish(f"查询可领取游戏时出错: {str(e)}")

    # ── 有参数：解析 ──
    parts = arg_text.split()
    game_id = extract_steam_id(parts[0])
    if not game_id and re.match(r"^\d+$", parts[0]):
        game_id = parts[0]
    if not game_id:
        await remain.finish("未检测到有效的游戏ID，请提供Steam游戏ID或Steam商店链接")

    # 查询现有记录
    query_url = cfg.url_with_filter(cfg.REMAIN_TABLE_ID, f"(gameId,eq,{game_id})")
    existing = utils.get_record(query_url)

    # ── 仅查询 ──
    if len(parts) == 1:
        if "id" in existing:
            remaining = existing["totalCount"] - existing["getedCount"]
            await remain.finish(
                f"游戏《{existing['gameName']}》(ID: {game_id}) 当前领取情况：\n"
                f"总份数: {existing['totalCount']}\n"
                f"已领取份数: {existing['getedCount']}\n"
                f"剩余可领取: {remaining}\n"
                f"记录ID: {existing['id']}"
            )
        else:
            info = get_game_info(game_id)
            name = info.get("game_name") or f"ID: {game_id}"
            await remain.finish(f"游戏《{name}》(ID: {game_id}) 尚未登记剩余份数")

    # ── 登记/更新 ──
    elif len(parts) >= 2:
        try:
            count = int(parts[1])
            if count <= 0:
                await remain.finish("份数必须大于0")
        except ValueError:
            await remain.finish("份数必须是整数")

        info = get_game_info(game_id)
        if "error" in info:
            await remain.finish(f"游戏{game_id}数据获取出错：{info['error']}")
        if not info["game_name"]:
            await remain.finish(f"无法获取游戏{game_id}的名称，请检查游戏ID是否正确")

        url = cfg.table_url(cfg.REMAIN_TABLE_ID)

        if "id" in existing:
            new_total = count
            can_be_claimed = new_total - existing["getedCount"]
            payload = {
                "id": existing["id"],
                "gameId": game_id,
                "gameName": info["game_name"],
                "totalCount": new_total,
                "getedCount": existing["getedCount"],
                "canBeClaimed": can_be_claimed,
            }
            result = utils.update_record(url, payload)
            if "id" in result:
                await remain.finish(
                    f"游戏《{info['game_name']}》(ID: {game_id}) 的剩余份数已更新\n"
                    f"原总份数: {existing['totalCount']}\n"
                    f"现总份数: {new_total}\n"
                    f"已领取份数: {existing['getedCount']}\n"
                    f"剩余可领取: {new_total - existing['getedCount']}"
                )
            else:
                await remain.finish("更新记录失败，请检查网络或配置")
        else:
            payload = {
                "gameId": game_id,
                "gameName": info["game_name"],
                "totalCount": count,
                "getedCount": 0,
                "canBeClaimed": count,
            }
            result = utils.create_record(url, payload)
            if "id" in result:
                await remain.finish(
                    f"游戏《{info['game_name']}》(ID: {game_id}) 已成功登记\n"
                    f"总份数: {count}\n"
                    f"已领取份数: 0\n"
                    f"剩余可领取: {count}\n"
                    f"记录ID: {result['id']}"
                )
            else:
                await remain.finish("创建记录失败，请检查网络或配置")
    else:
        await remain.finish(
            "请输入游戏ID/URL和份数，格式：remain 游戏ID/URL 份数\n"
            "或输入游戏ID/URL查询当前领取情况"
        )