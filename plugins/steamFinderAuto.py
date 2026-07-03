import re
import base64

from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

from nonebot import on_startswith

from plugins.playwright_utils import take_app_screenshot
from plugins.message_reaction import reaction_cleanup
from plugins.steam_utils import get_game_info


steamGoods = on_startswith(("https://store.steampowered.com/app/"), ignorecase=False, priority=20, block=True)

@steamGoods.handle()

async def handle_function(bot, event):
    cleanup = await reaction_cleanup(bot, event)
    try:
        goodIds = event.get_plaintext()
        goodIds = goodIds.split()
        for goodId in goodIds:
            await send_message(goodId)
    finally:
        if cleanup: await cleanup()


async def send_message(goodId):
    goodId = re.findall(r"(?<=app/)(\d+)|(\d{5,11})", goodId)
    print(goodId)
    if goodId != [] and goodId != "":
        result = await get_message(goodId)
        if result:
            await steamGoods.send(message=result, at_sender=False)
    else:
        print("no_match")
        await steamGoods.send("你确定这是商品的id？")


async def get_message(goodId):
    goodId[0] = tuple(item for item in goodId[0] if item)
    # 清除元组中的空结果

    # print(goodId)
    # print(type(goodId[0]))
    # print(goodId[0])

    # url = "https://store.steampowered.com/app/" + goodId[0][0] +"/_/?l=schinese"
    # print(url)
    # title = await fetch_title(url)
    # print(title)

    # if title == "欢迎来到 Steam" or title == "Welcome to Steam":
        # return f"{goodId[0][0]}无效"
    # elif title == "站点错误":
        # return f"{goodId[0][0]}锁区看不见"
    # else:
        # pic_data = await take_screenshot(url)
        # if pic_data:
            # pic = MessageSegment.image(pic_data)
            # return title + pic
#旧的实现，已作废

    appid = goodId[0][0] 
    gameInfo = get_game_info(appid)
    if "error" in gameInfo:
        await steamGoods.finish(f"游戏{goodId}数据获取出错，请反馈")   
    pic_data = await take_app_screenshot(appid)
    
    #格式化价格
    if gameInfo["currency"]:
        price_format = (
            f'\n原价：{str(gameInfo["initial"]) + gameInfo["currency"]}'
            f'\n现价：{str(gameInfo["final"]) + gameInfo["currency"]}'
            f'\n折扣：-{100 - (gameInfo["final"] / gameInfo["initial"] * 100):.0f}%'
        )
        print(price_format)
    else :
        price_format = ''
    
    if pic_data:
        pic = MessageSegment.image(f"base64://{base64.b64encode(pic_data).decode()}")
    else:
        pic = '截图超时，请联系'
        
    return f'游戏名：{gameInfo["game_name"]}\n支持语言：{gameInfo["supported_languages"]}\n发售日期：{gameInfo["release_date"]}\n发行商：{gameInfo["publisher"]}{price_format}\nSteam商店页链接：https://store.steampowered.com/app/{appid}\n' + pic        

# async def fetch_title(url: str) -> str:
    # proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
    # try:
        # response = requests.get(url, proxies=proxies)
        # response.raise_for_status()

        # soup = BeautifulSoup(response.content, "html.parser")

        # title_tag = soup.find("title")
        # if title_tag:
            # return f"{title_tag.get_text(strip=True)}"

        # return "出现异常"
    # except requests.exceptions.RequestException as e:
        # return f"请求出错: {e}"
        
# 使用下方函数作为替代，现已作废

# getGameInfo 已移至 plugins/steam_utils.py（get_game_info）
