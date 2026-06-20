from nonebot import on_startswith
from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

help = on_startswith("help", ignorecase=False, priority=20, block=True)

@help.handle()
async def handle_function(bot, event):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    text = (
        "📖 可用命令\n\n"
        "━━━ Steam ━━━━━━━━━━━━━━━\n"
        "id <游戏ID/商店链接>\n"
        "  查游戏详情（steam / 查商店）\n"
        "  例：id 3251240\n\n"
        "pub <发行商名>\n"
        "  查发行商页面截图\n"
        "  例：pub MangoParty\n\n"
        "find <关键字>\n"
        "  搜索 Steam 游戏（搜索steam游戏）\n"
        "  例：find 夫妻\n\n"
        "pending\n"
        "  鉴赏家副本监控，手动检查\n\n"
        "━━━ 挂刀行情 ━━━━━━━━━━━━\n"
        "cs [最低价] [日销量]\n"
        "  CS2 挂刀行情表\n\n"
        "dota [最低价] [日销量]\n"
        "  Dota2 挂刀行情表\n\n"
        "━━━ 工具 ━━━━━━━━━━━━━━━━\n"
        "ping\n"
        "  心跳测试\n\n"
        "help\n"
        "  显示本帮助\n\n"
        "━━━ NocoDB ━━━━━━━━━━━━━━\n"
        "bind / get / remain / wish\n"
        "report / probe / unfinished / unreported\n"
        "queryWishlist / calendar\n"
        "  详情请自行探索\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 直接发 Steam 商店链接也会自动查详情"
    )
    await help.finish(text)
