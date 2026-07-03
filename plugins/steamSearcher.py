import httpx
from lxml import html

from nonebot import require

from nonebot.rule import to_me

from plugins.noco.noco_config import get_http_proxy
from plugins.playwright_utils import take_app_screenshot
from plugins.error_logger import log_error
from plugins.message_reaction import reaction_cleanup
from plugins.steam_utils import get_game_info

require("nonebot_plugin_apscheduler")
from nonebot_plugin_alconna import Alconna, Args, Match, UniMessage, on_alconna  # noqa: E402


steam_searcher = on_alconna(
    Alconna("搜索steam游戏", Args["name?", str]),
    rule=None, # 如果不想每次都@的话
    aliases={"find"},
    priority=10,
    block=True,
)


@steam_searcher.handle()
async def handle_function(bot, event, name: Match[str]):
    # 检查是否从 pause() 恢复
    step = steam_searcher.get_path_arg("_step", "")

    if step == "awaiting_choice":
        # 用户刚回复了编号
        await handle_choice(event)
        return

    if step == "awaiting_keyword":
        # 用户刚回复了搜索关键词
        cleanup = steam_searcher.get_path_arg("cleanup")
        keyword = event.get_plaintext().strip()
        if not keyword:
            if cleanup: await cleanup()
            await steam_searcher.finish("oh!NO!")
        steam_searcher.set_path_arg("_step", "")  # 清除状态，让 do_search 重新设置
        await do_search(keyword, cleanup)
        return

    # 首次触发：从命令参数获取关键词
    cleanup = await reaction_cleanup(bot, event)
    keyword = name.result.strip() if name.available else ""

    if not keyword:
        steam_searcher.set_path_arg("cleanup", cleanup)
        steam_searcher.set_path_arg("_step", "awaiting_keyword")
        await steam_searcher.send("请输入要搜索的游戏名称", at_sender=False)
        await steam_searcher.pause(at_sender=False)
        return  # 不会到达这里

    await do_search(keyword, cleanup)


async def do_search(keyword: str, cleanup):
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

    proxy_url = get_http_proxy()

    url = (
        "https://store.steampowered.com/search/?term="
        + keyword
        + "&supportedlang=schinese%2Cenglish%2Ctchinese%2Cjapanese"
    )

    client_kwargs = {}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
    async with httpx.AsyncClient(**client_kwargs) as client:
        try:
            response = await client.get(url, headers=headers, timeout=30)
        except Exception as e:
            log_error("steamSearcher.do_search", f"请求Steam搜索页失败: {type(e).__name__}: {e}")
            if cleanup: await cleanup()
            await steam_searcher.finish("请求失败，请检查网络或代理配置", at_sender=False)
        if response.status_code != 200:
            if cleanup: await cleanup()
            await steam_searcher.finish("请求失败", at_sender=False)

    tree = html.fromstring(response.text)

    # 获取前5个游戏条目
    items = tree.xpath('//a[@data-gpnav="item"]')
    if not items or len(items) == 0:
        if cleanup: await cleanup()
        await steam_searcher.finish("什么都找不到呢", at_sender=False)

    game_titles = []
    game_links = []
    for i, item in enumerate(items[:5], 1):
        title = item.xpath('.//span[@class="title"]/text()')
        text = title[0].strip() if title else f"未知游戏{i}"
        game_titles.append(f"{i}. {text}")
        href = item.get("href")
        game_links.append(href)

    # 发送搜索结果
    search_result = "搜索结果：\n" + "\n".join(game_titles)
    await steam_searcher.send(search_result, at_sender=False)

    # 存储数据并等待用户选择编号
    steam_searcher.set_path_arg("game_links", game_links)
    steam_searcher.set_path_arg("cleanup", cleanup)
    steam_searcher.set_path_arg("_step", "awaiting_choice")
    await steam_searcher.send("请选择要查看的游戏编号,输入0退出", at_sender=False)
    await steam_searcher.pause(at_sender=False)


async def handle_choice(event):
    cleanup = steam_searcher.get_path_arg("cleanup", None)
    game_links = steam_searcher.get_path_arg("game_links", [])
    raw = event.get_plaintext().strip()

    try:
        number = int(raw)
    except ValueError:
        if cleanup: await cleanup()
        await steam_searcher.finish("请输入有效的数字", at_sender=False)

    if number == 0:
        if cleanup: await cleanup()
        await steam_searcher.finish("已退出")
    elif number < 1 or number > len(game_links):
        if cleanup: await cleanup()
        await steam_searcher.finish("无效的选择", at_sender=False)

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

    # 获取游戏详细信息并发送（与 steamFinderAuto 格式一致）
    gameInfo = get_game_info(appid)
    if "error" in gameInfo:
        if cleanup: await cleanup()
        await steam_searcher.finish(f"游戏{appid}数据获取出错，请反馈", at_sender=False)

    # 格式化价格
    if gameInfo["currency"]:
        price_format = (
            f'\n原价：{str(gameInfo["initial"]) + gameInfo["currency"]}'
            f'\n现价：{str(gameInfo["final"]) + gameInfo["currency"]}'
            f'\n折扣：-{100 - (gameInfo["final"] / gameInfo["initial"] * 100):.0f}%'
        )
    else:
        price_format = ""

    info_text = (
        f'游戏名：{gameInfo["game_name"]}'
        f'\n支持语言：{gameInfo["supported_languages"]}'
        f'\n发售日期：{gameInfo["release_date"]}'
        f'\n发行商：{gameInfo["publisher"]}'
        f'{price_format}'
        f'\nSteam商店页链接：https://store.steampowered.com/app/{appid}'
    )

    screenshot_bytes = await take_app_screenshot(appid)
    if screenshot_bytes:
        pic = UniMessage.image(raw=screenshot_bytes)
        if cleanup: await cleanup()
        await steam_searcher.finish(message=info_text + "\n" + pic, at_sender=False)
    else:
        if cleanup: await cleanup()
        await steam_searcher.finish(message=info_text, at_sender=False)
