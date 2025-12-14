import re

import requests
from bs4 import BeautifulSoup
from nonebot import on_command
from nonebot.adapters import Message

from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
# from nonebot.adapters.qq import MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import to_me
from playwright.async_api import async_playwright
from playwright.async_api import Error as PWError
from playwright.async_api import TimeoutError as PlaywrightTimeout

								 

browser = None
page = None


async def init_playwright():
    global browser, page
    if browser is None:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
																	
        cookies: list = []
        #playwright的cookie严格区分站点
        context = await browser.new_context(proxy={"server": "http://127.0.0.1:7890"})
        await context.add_cookies(cookies=cookies)
        page = await context.new_page()
        # await page.set_viewport_size(({"width": 800, "height": 1920}))


calendar = on_command("calendar", rule=to_me(), aliases={"cale", "愿望单", "冤枉单","任务"}, priority=10, block=True)


@calendar.handle()

async def handle_function(args: Message = CommandArg()):
    pic_data = await take_screenshot()
        
    if pic_data:
        pic = MessageSegment.image(pic_data)
    else:
        pic = '截图超时，请联系'
    
    await calendar.send(message=pic, at_sender=False) 

async def take_screenshot():
    url = "https://store.steampowered.com/personalcalendar/"
    print("start_screenshot")
    await init_playwright()
    print("new_browser")
    if page:
        await page.goto(url)
        print("page_goto")
        
        print("screenshot_bytes")
        # screenshot_bytes = await page.locator('xpath=//div[@class="glance_ctn"]').screenshot()
        try:
            # 例如等待某个元素并截图
            screenshot_bytes = await page.locator('xpath=//div[@class="_1ogG0o0tuYDOljO3JVMG4j p6KFiyUG9MYjbErC0_SGJ Panel Focusable"]').screenshot()
        except PlaywrightTimeout:
            print("截图超时，30 秒内元素未出现")
            screenshot_bytes = None
        except PlaywrightError as e:
            print("页面打开失败:", e.message)
            screenshot_bytes = None

        # print(type(screenshot_bytes))
        # base64_data = base64.b64encode(screenshot_bytes).decode("utf-8")
        return screenshot_bytes
    else:
        print("Playwright初始化失败")
