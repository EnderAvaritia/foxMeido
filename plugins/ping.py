from nonebot.rule import to_me
from nonebot.plugin import on_command
from plugins.message_reaction import reaction_cleanup
from plugins.protocol import finish

ping = on_command("ping", rule=to_me())

@ping.handle()
async def handle_function(bot, event):
    cleanup = await reaction_cleanup(bot, event)
    if cleanup: await cleanup()
    await finish(ping, "咕咕咕")