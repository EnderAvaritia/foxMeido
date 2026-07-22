import re
import base64

from nonebot import on_command
from nonebot.adapters import Message

# from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
try:
    from nonebot.adapters.qq import MessageSegment
except ImportError:
    from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.params import CommandArg

from plugins.playwright_utils import take_app_screenshot
from plugins.message_reaction import reaction_cleanup
from plugins.steam_utils import get_game_info, get_popular_tags


steamGoods = on_command("steamGoods", aliases={"steam", "查商店", "id"}, priority=10, block=True)


@steamGoods.handle()

async def handle_function(bot, event, args: Message = CommandArg()):
    cleanup = await reaction_cleanup(bot, event)
    try:
        goodIds = args.extract_plain_text()
        goodIds = goodIds.split()
        for goodId in goodIds:
            if not (goodId.startswith("https://store.steampowered.com/app/") or goodId.isdigit()):
                continue
            await send_message(goodId)
    finally:
        if cleanup: await cleanup()


async def send_message(goodId):
    original_input = goodId
    path_match = re.search(r"app/(.+)", original_input)
    display_input = path_match.group(1) if path_match else original_input
    goodId = re.findall(r"(?<=app/)(\d+)|(\d{5,11})", goodId)
    print(goodId)
    if goodId != [] and goodId != "":
        result = await get_message(goodId)
        if result:
            await steamGoods.send(message=result, at_sender=False)
    else:
        print("no_match")
        await steamGoods.send(f"你确定\"{display_input}\"是商品的id？")


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
    tags_result = get_popular_tags(appid)
    pic_data = await take_app_screenshot(appid)
    
    # 格式化价格
    if gameInfo.get("currency"):
        discount = 100 - (gameInfo["final"] / gameInfo["initial"] * 100)
        price_format = (
            f'\n原价：{gameInfo["initial"]}{gameInfo["currency"]}'
            f'\n现价：{gameInfo["final"]}{gameInfo["currency"]}'
            f'\n折扣：-{discount:.0f}%'
        )
    else:
        price_format = ""
    
    if pic_data:
        pic = MessageSegment.image(f"base64://{base64.b64encode(pic_data).decode()}")
    else:
        pic = '截图超时，请联系'
    
    # 条件构建输出行，缺失信息不输出对应行
    lines = []
    if gameInfo.get("game_name"):
        lines.append(f'游戏名：{gameInfo["game_name"]}')
    if gameInfo.get("genres"):
        lines.append(f'类型：{gameInfo["genres"]}')
    if tags_result.get("tags"):
        lines.append(f'热门标签：{", ".join(tags_result["tags"][:12])}')
    if gameInfo.get("supported_languages"):
        lines.append(f'支持语言：{gameInfo["supported_languages"]}')
    if gameInfo.get("release_date"):
        lines.append(f'发售日期：{gameInfo["release_date"]}')
    if gameInfo.get("publisher"):
        lines.append(f'发行商：{gameInfo["publisher"]}')
    if price_format:
        lines.append(price_format.lstrip("\n"))
    lines.append(f'Steam商店页链接：https://store.steampowered.com/app/{appid}')
    return '\n'.join(lines) + '\n' + pic        

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
