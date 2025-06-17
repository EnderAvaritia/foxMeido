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
        # browser = await playwright.chromium.launch(headless=False, slow_mo=1000)
        
        cookies: list = []
        context = await browser.new_context(proxy={"server": "http://127.0.0.1:7890"})
        await context.add_cookies(cookies=cookies)
        page = await context.new_page()


steamSearcher = on_command("steamSearcher", rule=to_me(), aliases={"find"}, priority=10, block=True)


@steamSearcher.handle()
async def handle_function(args: Message = CommandArg()):
    name = args.extract_plain_text()
    await send_message(name)


async def send_message(name):
    print(name)
    if name != [] and name != "":
        await get_message(name)
        
    else:
        print("no_match")
        await steamSearcher.send("oh!NO!")


async def get_message(name):
    url = "https://store.steampowered.com/search/?term=" + name +"&supportedlang=schinese%2Cenglish%2Ctchinese%2Cjapanese"
    print(url)

    pic1_data,pic2_data = await take_search_screenshot(url)
    if pic1_data:
        if pic2_data:
            pic1 = MessageSegment.file_image(pic1_data)
            pic2 = MessageSegment.file_image(pic2_data)
            await steamSearcher.send(message=pic1, at_sender=False)
            await steamSearcher.send(message=pic2, at_sender=False)

    else:        
        pic1 = MessageSegment.file_image(pic1_data)
        await steamSearcher.send(message=pic1, at_sender=False)

async def take_search_screenshot(url: str):
    print("start_screenshot")
    await init_playwright()
    print("new_browser")
    if page:
        await page.goto(url)
        print("page_goto")

        print("screenshot_bytes")
        element =await page.query_selector('//div[@id="search_result_container"]')
        element_text = await element.text_content()
        element_text = element_text.strip()
        
        if "0 个匹配的搜索结果。" != element_text:
            screenshot_search_bytes = await page.locator('xpath=//div[@id="search_result_container"]').screenshot()
            # await page.click('//div[@class="col search_capsule"][1]')
            number=1
            await page.click(f'//a[@data-gpnav="item"][{number}]')
            if await page.query_selector('//a[@id="view_product_page_btn"]'):
                print("view_product_page_btn")
                await page.click('//select[@name="ageYear"]')
                await page.select_option('//select[@name="ageYear"]', '1900')
                await page.click('//a[@id="view_product_page_btn"]')
            print("screenshot_bytes")
            screenshot_bytes = await page.locator('xpath=//div[@class="glance_ctn"]').screenshot()
            return screenshot_search_bytes,screenshot_bytes
        else:
            print("无结果")
            await steamSearcher.finish("什么都找不到呢", at_sender=False)
            exit
    else:
        print("Playwright初始化失败")
        return
     