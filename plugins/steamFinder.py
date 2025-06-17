import re

import requests
from bs4 import BeautifulSoup
from nonebot import on_command
from nonebot.adapters import Message

# from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.adapters.qq import MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import to_me
from playwright.async_api import async_playwright

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


steamGoods = on_command("steamGoods", rule=to_me(), aliases={"steam", "查商店", "id"}, priority=10, block=True)


@steamGoods.handle()
async def handle_function(args: Message = CommandArg()):
    goodIds = args.extract_plain_text()
    goodIds = goodIds.split()
    for goodId in goodIds:
        await send_message(goodId)


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

    url = "https://store.steampowered.com/app/" + goodId[0][0] +"/_/?l=schinese"
    print(url)
    title = await fetch_title(url)
    print(title)

    if title == "欢迎来到 Steam" or title == "Welcome to Steam":
        return f"{goodId[0][0]}无效"
    elif title == "站点错误":
        return f"{goodId[0][0]}锁区看不见"
    else:
        pic_data = await take_screenshot(url)
        if pic_data:
            pic = MessageSegment.file_image(pic_data)
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
        screenshot_bytes = await page.locator('xpath=//div[@class="glance_ctn"]').screenshot()

        # print(type(screenshot_bytes))
        # base64_data = base64.b64encode(screenshot_bytes).decode("utf-8")
        return screenshot_bytes
    else:
        print("Playwright初始化失败")
