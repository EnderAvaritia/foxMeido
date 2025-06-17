from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me

import re

prase = on_command("prase", rule=to_me())

@prase.handle()
async def handle_function(message: Message = CommandArg()):
    words = message.extract_plain_text()
    words = words.split()
    for word in words:
        word = re.findall(r'(?<=app/)(\d+)', word)
        if word != [] and word != "":
            print(word)
            await prase.send(message=word,at_sender=False)