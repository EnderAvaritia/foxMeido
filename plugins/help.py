from nonebot.rule import to_me
from nonebot.plugin import on_command
from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

help = on_command("help", rule=to_me())

@help.handle()
async def handle_function(bot, event):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    text = (
        "📖 可用命令\n\n"
        "id <游戏ID或商店链接>\n"
        "  查游戏详情（名称、厂商、发行日期、价格、截图）\n"
        "  例：id 3251240\n\n"
        "pub <发行商名称>\n"
        "  查发行商页面截图\n"
        "  例：pub publisher/MangoParty\n\n"
        "find <关键字>\n"
        "  搜索 Steam 游戏，选编号看详情\n"
        "  例：find 夫妻\n\n"
        "cs [最低价] [日销量]\n"
        "  CS2 挂刀行情表，可带参数\n"
        "  例：cs 5 100\n\n"
        "dota [最低价] [日销量]\n"
        "  Dota2 挂刀行情表\n"
        "  例：dota 5 100\n\n"
        "💡 直接发 Steam 商店链接也会自动查详情"
    )
    await help.finish(text)