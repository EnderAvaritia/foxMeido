import httpx
from lxml import html

from nonebot import require

# from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.rule import to_me
from playwright.async_api import async_playwright

require("nonebot_plugin_apscheduler")
from nonebot_plugin_alconna import Alconna, Args, Match, UniMessage, on_alconna  # noqa: E402

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


steam_searcher = on_alconna(
    Alconna("搜索steam游戏", Args["name?", str]["number?", int]),
    rule=to_me(),
    aliases={"find"},
    priority=10,
    block=True,
)


@steam_searcher.handle()
async def handle_function(name: Match[str]):
    if name.available:
        # 如果参数已经提供，直接处理
        steam_searcher.set_path_arg("name", name.result)
        # await get_message(name.result)
    else:
        # 如果没有提供参数，进入got_path流程
        steam_searcher.set_path_arg("name", None)


@steam_searcher.got_path("name", prompt="请输入要搜索的游戏名称")
async def send_message(name: str):
    print(name)
    if name and name.strip():  # 更严格的空值检查
        await get_message(name)
    else:
        print("no_match")
        await steam_searcher.send("oh!NO!")

async def get_message(name):
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        'Accept': "text/javascript, text/html, application/xml, text/xml, */*",
        'Accept-Encoding': "gzip, deflate, br, zstd",
        'Accept-Language': "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        'X-Requested-With': "XMLHttpRequest",
        'X-Prototype-Version': "1.7",
        'DNT': "1",
        'Sec-GPC': "1",
        'Sec-Fetch-Dest': "empty",
        'Sec-Fetch-Mode': "cors",
        'Sec-Fetch-Site': "same-origin",
        'Cookie': ""
    }
    #添加cookies
    
    proxy_url = "http://localhost:7890"

    url = (
        "https://store.steampowered.com/search/?term="
        + name
        + "&supportedlang=schinese%2Cenglish%2Ctchinese%2Cjapanese"
    )
    print(url)

    async with httpx.AsyncClient(proxy=proxy_url) as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            print("请求失败")
            await steam_searcher.finish("请求失败", at_sender=False)

        print("请求成功")
        content = response.text

    tree = html.fromstring(content)

    # with open("temphtml.html", 'wb') as file:
        # file.write(html.tostring(tree, pretty_print=True, encoding='utf-8'))#打印网页，测试用

    # 获取前5个游戏条目
    items = tree.xpath('//a[@data-gpnav="item"]')
    if not items or len(items) == 0:
        await steam_searcher.finish("什么都找不到呢", at_sender=False)
        return

    game_titles = []
    game_links = []
    for i, item in enumerate(items[:5], 1):
        title = item.xpath('.//span[@class="title"]/text()')
        text = title[0].strip() if title else f"未知游戏{i}"
        game_titles.append(f"{i}. {text}")
        href = item.get("href")
        game_links.append(href)

    # 发送游戏列表
    search_result = "搜索结果：\n" + "\n".join(game_titles)
    print(search_result)
    await steam_searcher.send(search_result, at_sender=False)
    # 存储链接到会话
    steam_searcher.set_path_arg("game_links", game_links)


@steam_searcher.got_path("number", prompt="请选择要查看的游戏编号,输入0退出")
async def get_choice(number: int):
    game_links = steam_searcher.get_path_arg("game_links", [])
    if number == 0:
        await steam_searcher.finish("已退出")
    elif not game_links or number < 1 or number > len(game_links):
        await steam_searcher.reject("无效的选择，请重试", at_sender=False)
        return
    link = game_links[number - 1]
    await init_playwright()
    if not page:
        await steam_searcher.finish("Playwright初始化失败", at_sender=False)
        return
    await page.goto(link)
    await page.wait_for_timeout(2000)
    # 处理年龄验证
    if await page.query_selector('//a[@id="view_product_page_btn"]'):
        await page.click('//select[@name="ageYear"]')
        await page.select_option('//select[@name="ageYear"]', "1900")
        await page.click('//a[@id="view_product_page_btn"]')
        await page.wait_for_timeout(2000)
    # 截图详情
    if await page.query_selector('xpath=//div[@class="glance_ctn"]'):
        screenshot_bytes = await page.locator('xpath=//div[@class="glance_ctn"]').screenshot()
        pic = UniMessage.image(raw=screenshot_bytes)
        await steam_searcher.finish(message=pic, at_sender=False)
    else:
        await steam_searcher.finish("未能获取详情页面", at_sender=False)
