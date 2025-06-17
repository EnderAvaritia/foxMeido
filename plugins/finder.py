from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
# from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.adapters.qq import MessageSegment

import base64
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

finder = on_command("finder", rule=to_me(), aliases={"finder"}, priority=10, block=True)

@finder.handle()
async def handle_function(args: Message = CommandArg()):
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
    pic = MessageSegment.file_image(pic_data)
    print(type(pic_data))
    print(type(pic))
    await finder.send(pic)
    
async def fetch_title(url: str) -> str:
    proxies = {
    "http": "http://127.0.0.1:7890", 
    "https": "http://127.0.0.1:7890"
    }
    try:
        # 发送HTTP GET请求
        response = requests.get(url, proxies=proxies)
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
        proxy = {
        "server": "http://127.0.0.1:7890"
        }
        
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context(proxy=proxy)
        page = await context.new_page()
        print("new")
        await page.goto(url)
        print("goto")

        print("screenshot_bytes")
        screenshot_bytes = await page.screenshot()
        
        print(type(screenshot_bytes))
        
        await browser.close()
        
        base64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
        return screenshot_bytes