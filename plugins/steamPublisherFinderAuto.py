import re

import requests
from bs4 import BeautifulSoup
from nonebot import on_command
from nonebot.adapters import Message

from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
# # from nonebot.adapters.qq import MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import to_me
from playwright.async_api import async_playwright

from nonebot import on_startswith

browser = None
page = None


async def init_playwright():
    global browser, page
    if browser is None:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        cookies: list = []
        context = await browser.new_context(proxy={"server": "http://127.0.0.1:7890"})
        await context.add_cookies(cookies=cookies)
        page = await context.new_page()
        await page.set_viewport_size(({"width": 800, "height": 19200}))


steamPublishersAuto = on_startswith(("https://store.steampowered.com/publisher/"), ignorecase=False, priority=20, block=True)


@steamPublishersAuto.handle()
async def handle_function(event):
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
        pic_data = await take_screenshot(url)
        if pic_data:
            pic = MessageSegment.image(pic_data)
            return title + pic


async def fetch_title(url: str) -> str:
    proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
    try:
        response = requests.get(url, proxies=proxies)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        title_tag = soup.find("title")
        if title_tag:
            return f"{title_tag.get_text(strip=True)}"

        return "出现异常"
    except requests.exceptions.RequestException as e:
        return f"请求出错: {e}"


async def take_screenshot(url: str):
    print("start_screenshot")
    await init_playwright()
    print("new_browser")
    if page:
        await page.goto(url)
        print("page_goto")
        title = page.title()
        if await title == "Welcome to Steam":
            print("没这玩意，跳转了")
            return
        
        if await page.query_selector('//a[@id="view_product_page_btn"]'):
            print("view_product_page_btn")
            await page.click('//select[@name="ageYear"]')
            await page.select_option('//select[@name="ageYear"]', '1900')
            await page.click('//a[@id="view_product_page_btn"]')
        
        print("screenshot_bytes")
        screenshot_bytes = await page.locator('xpath=//div[@id="RecommendationsRows"]').screenshot()

        # print(type(screenshot_bytes))
        # base64_data = base64.b64encode(screenshot_bytes).decode("utf-8")
        return screenshot_bytes
    else:
        print("Playwright初始化失败")
