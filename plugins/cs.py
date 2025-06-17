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

cs = on_command("cs", rule=to_me(), aliases={"cs"}, priority=10, block=True)

@cs.handle()
async def handle_function(messages: Message = CommandArg()):
    
    messages = messages.extract_plain_text()
    messages = messages.split()
    messages = [str(item) for item in messages]
    
    if len(messages) > 2:
        messages = messages[:2]
    
    args = ["10","100"]
    args[:len(messages)] = messages

    pic_data = await take_screenshot(args)
    
    if pic_data:
        pic = MessageSegment.file_image(pic_data)
        await cs.send(pic)
    else:
        await cs.send("检查你发了什么")
    
async def take_screenshot(args: str):
    async with async_playwright() as p:
        
        print(args)
        
        proxy = {
        "server": "http://127.0.0.1:7890"
        }
                      
        browser = await p.chromium.launch(headless=True)
        # context = await browser.new_context(proxy=proxy)
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_viewport_size(({"width": 800, "height": 19200}))

        print("new")
        
        min_price = args[0]
        min_volume = args[1]
        
        url = f"https://www.iflow.work/?page_num=1&platforms=buff-igxe-uuyp-eco-c5&games=csgo&sort_by=sell&min_price={min_price}&max_price=5000&min_volume={min_volume}&max_latency=0&price_mode=buy"

        await page.goto(url)
        print("goto")

        print("screenshot_bytes")
        screenshot_bytes = await page.locator('xpath=//div[@class="ant-spin-container"]/div[@class="ant-row css-wfimbv"]').screenshot()
        
        print(type(screenshot_bytes))
        
        await browser.close()
        
        base64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
        return screenshot_bytes