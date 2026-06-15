from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
# from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
try:
    from nonebot.adapters.qq import MessageSegment
except ImportError:
    from nonebot.adapters.onebot.v11 import MessageSegment

import base64
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from plugins.noco.noco_config import get_proxies, get_http_proxy
from plugins.noco.error_logger import log_error
from plugins.reaction_utils import send_reaction, extract_group_id, extract_message_id

finder = on_command("finder", rule=to_me(), aliases={"finder"}, priority=10, block=True)

@finder.handle()
async def handle_function(bot, event, args: Message = CommandArg()):
    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id)
    # goodId = args.extract_plain_text()
    # goodIdList = goodId.split()
    # message = "\n".join(goodIdList)
    # await finder.send(message,at_sender=False)
    
    url = args.extract_plain_text()
    print(url)
    title = await fetch_title(url)
    # await finder.send(title)
    print(title)
    # pic_base64 = await take_screenshot(url)
    # print ("pic_base64")
    # pic = MessageSegment.image(f'base64://{pic_base64}')
    # await finder.send(pic)
    # pic = MessageSegment.file_image(take_screenshot(url))
    
    pic_data = await take_screenshot(url)
    pic = MessageSegment.image(f"base64://{base64.b64encode(pic_data).decode()}")
    print(type(pic_data))
    print(type(pic))
    await finder.send(pic)
    
async def fetch_title(url: str) -> str:
    try:
        # 发送HTTP GET请求
        response = requests.get(url, proxies=get_proxies())
        response.raise_for_status()
        print(response.status_code)

        # 解析网页内容
        soup = BeautifulSoup(response.content, 'html.parser')

        # 提取<title>标签内容
        title_tag = soup.find('title')
        if title_tag:
            return f"网页标题: {title_tag.string.strip()}"

        return "出现异常"
    except requests.exceptions.RequestException as e:
        return f"请求出错: {e}"
        
async def take_screenshot(url: str):
    async with async_playwright() as p:
        print("p")
        try:
            ctx_kwargs = {}
            proxy = get_http_proxy()
            if proxy:
                ctx_kwargs["proxy"] = {"server": proxy}
            
            browser = await p.chromium.launch(headless=False, slow_mo=1000)
            context = await browser.new_context(**ctx_kwargs)
            page = await context.new_page()
            print("new")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print("goto")

            print("screenshot_bytes")
            screenshot_bytes = await page.screenshot()
            
            print(type(screenshot_bytes))
            
            await browser.close()
            
            return screenshot_bytes
        except Exception as e:
            log_error("finder.take_screenshot", f"截图异常: {e}")
            return None