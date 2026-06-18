import re
import base64

import requests
from bs4 import BeautifulSoup
from nonebot import on_command
from nonebot.adapters import Message

from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
# # from nonebot.adapters.qq import MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import to_me

from nonebot import on_startswith

from plugins.noco.noco_config import get_proxies
from plugins.playwright_utils import take_publisher_screenshot
from plugins.noco.error_logger import log_error
from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id


steamPublishersAuto = on_startswith(("https://store.steampowered.com/publisher/"), ignorecase=False, priority=20, block=True)

@steamPublishersAuto.handle()
async def handle_function(bot, event):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    publisher = event.get_plaintext()
    await send_message(publisher)


async def send_message(publisher):
    publisher = re.findall(r"(?<=publisher/)(.*)", publisher)
    print(publisher)
    if publisher != [] and publisher != "":
        result = await get_message(publisher)
        if result:
            await steamPublishersAuto.send(message=result, at_sender=False)
    else:
        print("no_match")
        await steamPublishersAuto.send("你确定这是发行商的页面？")


async def get_message(publisher):
    print(publisher[0])
    # publisher[0] = tuple(item for item in publisher[0] if item)

    url = "https://store.steampowered.com/publisher/" + publisher[0]
    print(url)
    title = await fetch_title(url)
    print(title)

    if title == "Steam 搜索" or title == "Steam Search":
        return f"{publisher[0]}无效"
    elif title == "站点错误":
        return f"{publisher[0]}锁区看不见"
    else:
        pic_data = await take_publisher_screenshot(url)
        if pic_data:
            pic = MessageSegment.image(f"base64://{base64.b64encode(pic_data).decode()}")
            return title + pic


async def fetch_title(url: str) -> str:
    try:
        response = requests.get(url, proxies=get_proxies())
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        title_tag = soup.find("title")
        if title_tag:
            return f"{title_tag.get_text(strip=True)}"

        return "出现异常"
    except requests.exceptions.RequestException as e:
        return f"请求出错: {e}"
