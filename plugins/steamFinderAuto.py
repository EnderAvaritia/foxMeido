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
        # browser = await playwright.chromium.launch(headless=False)
        cookies: list = []
        context = await browser.new_context(proxy={"server": "http://127.0.0.1:7890"})
        await context.add_cookies(cookies=cookies)
        page = await context.new_page()


steamGoods = on_startswith(("https://store.steampowered.com/app/"), ignorecase=False, priority=20, block=True)


@steamGoods.handle()

async def handle_function(event):
    goodIds = event.get_plaintext()
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

    # url = "https://store.steampowered.com/app/" + goodId[0][0] +"/_/?l=schinese"
    # print(url)
    # title = await fetch_title(url)
    # print(title)

    # if title == "欢迎来到 Steam" or title == "Welcome to Steam":
        # return f"{goodId[0][0]}无效"
    # elif title == "站点错误":
        # return f"{goodId[0][0]}锁区看不见"
    # else:
        # pic_data = await take_screenshot(url)
        # if pic_data:
            # pic = MessageSegment.image(pic_data)
            # return title + pic
#旧的实现，已作废

    appid = goodId[0][0] 
    gameInfo = await getGameInfo(appid)
    if "error" in gameInfo:
        await steamGoods.finish(f"游戏{goodId}数据获取出错，请反馈")   
    pic_data = await take_screenshot(appid)
    
    #格式化价格
    if gameInfo["currency"]:
        price_format = f'\n原价：{str(gameInfo["initial"])+gameInfo["currency"]}\n现价：{str(gameInfo["final"])+gameInfo["currency"]}\n折扣：-{100-(gameInfo["final"]/gameInfo["initial"]*100)}%'
        print(price_format)
    else :
        price_format = ''
    
    if pic_data:
        pic = MessageSegment.image(pic_data)
    else:
        pic = '截图超时，请联系'
        
    return f'游戏名：{gameInfo["game_name"]}\n支持语言：{gameInfo["supported_languages"]}\n发售日期：{gameInfo["release_date"]}\n发行商：{gameInfo["publisher"]}{price_format}\nSteam商店页链接：https://store.steampowered.com/app/{appid}\n' + pic        

# async def fetch_title(url: str) -> str:
    # proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
    # try:
        # response = requests.get(url, proxies=proxies)
        # response.raise_for_status()

        # soup = BeautifulSoup(response.content, "html.parser")

        # title_tag = soup.find("title")
        # if title_tag:
            # return f"{title_tag.get_text(strip=True)}"

        # return "出现异常"
    # except requests.exceptions.RequestException as e:
        # return f"请求出错: {e}"
        
# 使用下方函数作为替代，现已作废

async def getGameInfo(appid: int):
    """
    根据Steam AppID，通过Steam Web API获取游戏的名称和厂商名。
    如果存在多个厂商名，将它们合并成一个用逗号和空格分隔的字符串。

    Args:
        appid (int): Steam游戏的AppID。

    Returns:
        dict: 包含游戏名称和厂商名的字典。
              例如：{"game_name": "Half-Life 2", "publisher": "Valve"}
              如果获取失败，会包含 "error" 键，并可能包含已获取的部分信息。
              例如：{"game_name": None, "publisher": None, "error": "API返回成功状态为false..."}
    """
    game_name = None
    publisher = None # 默认为None
    release_date = None
    errors = []

    # --- 通过Steam Web API 获取游戏名称和厂商名 ---
    api_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese"
    print(f"正在请求API接口: {api_url}")
    proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

    try:
        response = requests.get(api_url, proxies=proxies)
        response.raise_for_status()  # 检查HTTP状态码，如果不是200则抛出异常

        data = response.json()
        app_data = data.get(str(appid)) # API响应中AppID是字符串键

        if app_data and app_data.get('success'):
            details = app_data.get('data')
            if details:
                # 获取游戏名称
                game_name = details.get('name')
                if game_name:
                    print(f"获取到游戏名称: {game_name}")
                else:
                    errors.append(f"API返回数据中未找到'name'信息 (AppID: {appid})")
                    print(errors[-1])

                # 获取厂商名列表并合并
                publishers_list = details.get('publishers')
                if publishers_list:
                    # 将列表中的所有厂商名用逗号和空格连接起来
                    publisher = ", ".join(publishers_list)
                    print(f"获取到厂商名: {publisher}")
                else:
                    errors.append(f"API返回的厂商列表为空或未找到 (AppID: {appid})")
                    print(errors[-1])
                    
                # 获取发行日期并合并
                release_date = details.get('release_date').get('date')
                if release_date:
                    print(f"获取到发行日期: {release_date}")
                else:
                    errors.append(f"API返回的发行日期为空或未找到 (AppID: {appid})")
                    print(errors[-1])
                    
                # 获取语言并合并
                supported_languages = details.get('supported_languages')
                supported_languages = re.sub("<.*?>", "", supported_languages)
                supported_languages = supported_languages.replace('*', '').replace('具有完全音频支持的语言', '')
                if supported_languages:
                    print(f"获取到支持语言: {supported_languages}")
                else:
                    errors.append(f"API返回的发行日期为空或未找到 (AppID: {appid})")
                    print(errors[-1]) 

                # 获取价格
                try:
                    price = details.get('price_overview')
                    if price:
                        print(f"获取到价格: {price}")
                        initial = int(price.get('initial'))/100
                        final = int(price.get('final'))/100
                        currency = price.get('currency')
                        
                    else:
                        errors.append(f"API返回的价格为空或未找到 (AppID: {appid})")
                        print(errors.pop())
                        initial = 1
                        final = 1
                        currency = None
                
                except Exception as e:
                    errors.append(f"处理API响应时发生未知错误: {e}")
                    initial = 1
                    final = 1
                    currency = None
                    print(errors[-1])
                    
            else:
                errors.append(f"API返回数据中未找到'data'详情 (AppID: {appid})")
                print(errors[-1])
        else:
            errors.append(f"API返回成功状态为false或数据为空 (AppID: {appid})。可能AppID不存在或不可用。")
            print(errors[-1])

    except requests.exceptions.RequestException as e:
        errors.append(f"请求API接口时发生网络错误或HTTP错误: {e}")
        print(errors[-1])
    except json.JSONDecodeError as e:
        errors.append(f"解析API响应JSON时发生错误: {e}")
        print(errors[-1])
    except Exception as e:
        errors.append(f"处理API响应时发生未知错误: {e}")
        print(errors[-1])

    result = {
        "game_name": game_name,
        "publisher": publisher,
        "release_date":release_date,
        "supported_languages":supported_languages,
        "initial":initial,
        "final":final,
        "currency":currency
    }
    if errors:
        result["error"] = "; ".join(errors)
    
    return result

async def take_screenshot(appid: str):
    url = "https://store.steampowered.com/app/" + appid +"/_/?l=schinese"
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
        # screenshot_bytes = await page.locator('xpath=//div[@class="glance_ctn"]').screenshot()
        try:
            # 例如等待某个元素并截图
            screenshot_bytes = await page.locator('xpath=//div[@class="glance_ctn"]').screenshot()
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
