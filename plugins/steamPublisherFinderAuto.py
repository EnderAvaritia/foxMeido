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
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from nonebot import on_startswith

from noco.noco_config import PROXIES
from noco.playwright_utils import create_browser_page
from noco.error_logger import log_error

browser = None
page = None


async def init_playwright():
    global browser, page
    if browser is None:
        browser, page = await create_browser_page(viewport_size={"width": 800, "height": 19200})


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
            pic = MessageSegment.image(f"base64://{base64.b64encode(pic_data).decode()}")
            return title + pic


async def fetch_title(url: str) -> str:
    try:
        response = requests.get(url, proxies=PROXIES)
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
    try:
        await init_playwright()
    except Exception as e:
        log_error("steamPublisherFinderAuto.take_screenshot", f"Playwright 初始化异常: {e}")
        return None
    print("new_browser")
    if not page:
        log_error("steamPublisherFinderAuto.take_screenshot", "Playwright初始化失败")
        return None
    try:
        await page.goto(url)
    except Exception as e:
        log_error("steamPublisherFinderAuto.take_screenshot", f"页面跳转失败: {e}")
        return None
    print("page_goto")
    try:
        title = await page.title()
        if title == "Welcome to Steam":
            log_error("steamPublisherFinderAuto.take_screenshot", f"页面跳转至Welcome to Steam，URL可能无效: {url}")
            return None
        
        if await page.query_selector('//a[@id="view_product_page_btn"]'):
            print("view_product_page_btn")
            await page.click('//select[@name="ageYear"]')
            await page.select_option('//select[@name="ageYear"]', '1900')
            await page.click('//a[@id="view_product_page_btn"]')
    except Exception as e:
        log_error("steamPublisherFinderAuto.take_screenshot", f"页面处理异常: {e}")
        return None
    
    print("screenshot_bytes")
    try:
        screenshot_bytes = await page.locator('xpath=//div[@id="RecommendationsRows"]').screenshot()
    except PlaywrightTimeout:
        log_error("steamPublisherFinderAuto.take_screenshot", "截图超时，30秒内元素未出现")
        screenshot_bytes = None
    except PlaywrightError as e:
        msg = e.message if hasattr(e, 'message') else str(e)
        log_error("steamPublisherFinderAuto.take_screenshot", f"页面打开失败: {msg}")
        screenshot_bytes = None

    return screenshot_bytes
