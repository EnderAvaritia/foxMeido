from nonebot.rule import to_me
from nonebot.plugin import on_command
from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

ping = on_command("ping", rule=to_me())

@ping.handle()
async def handle_function(bot, event):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    await ping.finish("咕咕咕")