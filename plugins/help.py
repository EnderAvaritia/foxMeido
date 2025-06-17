from nonebot.rule import to_me
from nonebot.plugin import on_command

help = on_command("help", rule=to_me())

@help.handle()
async def handle_function():
    text = '''
    命令使用/起始
    使用id查找steam游戏，后面可接游戏id或者url，如：id 3251240
    使用cs或者dota获取挂刀详情表，可带参数，依次是最低价格和日销量，如：dota 5 100
    使用find查找steam游戏，交互式搜索，如：find 夫妻
    使用pub查找发行商页面，如：pub publisher/MangoParty(前面的前缀自行补全)
    '''
    await help.finish(text)