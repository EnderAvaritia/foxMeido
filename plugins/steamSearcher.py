import httpx
import urllib3
from lxml import html

from nonebot import require

# from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.rule import to_me

from plugins.noco.noco_config import get_http_proxy
from plugins.playwright_utils import take_app_screenshot
from plugins.error_logger import log_error
from plugins.message_reaction import reaction_cleanup
from plugins.steam_utils import get_game_info, get_popular_tags

require("nonebot_plugin_apscheduler")
from nonebot_plugin_alconna import Alconna, Args, Match, UniMessage, on_alconna  # noqa: E402

# 通过代理访问 HTTPS 时，不验证 SSL 证书
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


steam_searcher = on_alconna(
    Alconna("搜索steam游戏", Args["name?", str]["number?", int]),
    rule=None, # 如果不想每次都@的话
    aliases={"find"},
    priority=10,
    block=True,
)


@steam_searcher.handle()
async def handle_function(bot, event, name: Match[str]):
    cleanup = await reaction_cleanup(bot, event)
    steam_searcher.set_path_arg("_reaction_cleanup", cleanup)
    if name.available:
        # 如果参数已经提供，直接处理
        steam_searcher.set_path_arg("name", name.result)
        # await get_message(name.result)
    else:
        # 如果没有提供参数，进入got_path流程
        steam_searcher.set_path_arg("name", None)


@steam_searcher.got_path("name", prompt="请输入要搜索的游戏名称")
async def send_message(name: str):
    cleanup = steam_searcher.get_path_arg("_reaction_cleanup", None)
    print(name)
    if name and name.strip():  # 更严格的空值检查
        await get_message(name, cleanup)
    else:
        print("no_match")
        await steam_searcher.send("oh!NO!")

async def get_message(name, cleanup=None):
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
    
    proxy_url = get_http_proxy()

    url = (
        "https://store.steampowered.com/search/?term="
        + name
        + "&supportedlang=schinese%2Cenglish%2Ctchinese%2Cjapanese"
    )
    print(url)

    client_kwargs = {}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
        client_kwargs["verify"] = False
    async with httpx.AsyncClient(**client_kwargs) as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            print("请求失败")
            if cleanup: await cleanup()
            await steam_searcher.finish("请求失败", at_sender=False)

        print("请求成功")
        content = response.text

    tree = html.fromstring(content)

    # with open("temphtml.html", 'wb') as file:
        # file.write(html.tostring(tree, pretty_print=True, encoding='utf-8'))#打印网页，测试用

    # 获取前5个游戏条目
    items = tree.xpath('//a[@data-gpnav="item"]')
    if not items or len(items) == 0:
        if cleanup: await cleanup()
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
    cleanup = steam_searcher.get_path_arg("_reaction_cleanup", None)
    game_links = steam_searcher.get_path_arg("game_links", [])
    if number == 0:
        if cleanup: await cleanup()
        await steam_searcher.finish("已退出")
    elif not game_links or number < 1 or number > len(game_links):
        await steam_searcher.reject("无效的选择，请重试", at_sender=False)
        return
    link = game_links[number - 1]
    # 从 URL 如 https://store.steampowered.com/app/12345/ 中提取 appid
    parts = link.split("/")
    try:
        appid_idx = parts.index("app")
        appid = parts[appid_idx + 1]
    except (ValueError, IndexError):
        if cleanup: await cleanup()
        await steam_searcher.finish("无效的链接", at_sender=False)
        return

    # 获取游戏详细信息（与 steamFinderAuto 格式一致）
    gameInfo = get_game_info(appid)
    if "error" in gameInfo:
        if cleanup: await cleanup()
        await steam_searcher.finish(f"游戏{appid}数据获取出错，请反馈", at_sender=False)
    tags_result = get_popular_tags(appid)

    # 格式化价格
    if gameInfo.get("currency"):
        discount = 100 - (gameInfo["final"] / gameInfo["initial"] * 100)
        price_format = (
            f'原价：{gameInfo["initial"]}{gameInfo["currency"]}'
            f'\n现价：{gameInfo["final"]}{gameInfo["currency"]}'
            f'\n折扣：-{discount:.0f}%'
        )
    else:
        price_format = ""

    # 条件构建输出行，缺失信息不输出对应行
    lines = []
    if gameInfo.get("game_name"):
        lines.append(f'游戏名：{gameInfo["game_name"]}')
    if gameInfo.get("genres"):
        lines.append(f'类型：{gameInfo["genres"]}')
    if tags_result.get("tags"):
        lines.append(f'热门标签：{", ".join(tags_result["tags"][:12])}')
    if gameInfo.get("supported_languages"):
        lines.append(f'支持语言：{gameInfo["supported_languages"]}')
    if gameInfo.get("release_date"):
        lines.append(f'发售日期：{gameInfo["release_date"]}')
    if gameInfo.get("publisher"):
        lines.append(f'发行商：{gameInfo["publisher"]}')
    if price_format:
        lines.append(price_format)
    lines.append(f'Steam商店页链接：https://store.steampowered.com/app/{appid}')
    info_text = '\n'.join(lines)

    screenshot_bytes = await take_app_screenshot(appid)
    if screenshot_bytes:
        pic = UniMessage.image(raw=screenshot_bytes)
        if cleanup: await cleanup()
        await steam_searcher.finish(message=info_text + "\n" + pic, at_sender=False)
    else:
        if cleanup: await cleanup()
        await steam_searcher.finish(message=info_text, at_sender=False)
