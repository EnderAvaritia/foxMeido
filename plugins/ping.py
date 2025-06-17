from nonebot.rule import to_me
from nonebot.plugin import on_command

ping = on_command("ping", rule=to_me())

@ping.handle()
async def handle_function():
    await ping.finish("咕咕咕")