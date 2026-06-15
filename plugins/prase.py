from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me

import re

from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

prase = on_command("prase", rule=to_me())

@prase.handle()
async def handle_function(bot, event, message: Message = CommandArg()):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    words = message.extract_plain_text()
    words = words.split()
    for word in words:
        word = re.findall(r'(?<=app/)(\d+)', word)
        if word != [] and word != "":
            print(word)
            await prase.send(message=word,at_sender=False)