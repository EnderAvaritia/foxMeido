from nonebot.rule import to_me
from nonebot.plugin import on_command

ping = on_command("ping", rule=to_me())

@ping.handle()
async def handle_function(bot, event):
    await ping.finish("咕咕咕")