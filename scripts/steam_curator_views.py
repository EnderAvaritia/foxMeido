#!/usr/bin/env python3
"""Steam 鉴赏家评测浏览量脚本：通过访问鉴赏家推荐的游戏页面来提升浏览量。

用法示例:
  python steam_curator_views.py --clan-id 45519015 --name "无趣评测" --cookie "<steam cookie>"
  python steam_curator_views.py --clan-id 45519015 --name "无趣评测" --cookie "<cookie>" \\
      --proxy http://127.0.0.1:10279 --count 500 --threads 4 --log views.log
"""

import argparse
import logging
import random
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple

import requests
from bs4 import BeautifulSoup
from lxml import html

# ── 常量 ──────────────────────────────────────────────────────────────────

STEAM_MAIN_URL = "https://store.steampowered.com/"
STEAM_APP_BASE_URL = "https://store.steampowered.com/app/"
STEAM_CURATOR_URL = (
    "https://store.steampowered.com/curator/{clan_id}-{name_slug}/"
    "ajaxgetfilteredrecommendations/"
)
STEAM_CURATOR_URL_NO_NAME = (
    "https://store.steampowered.com/curator/{clan_id}/ajaxgetfilteredrecommendations/"
)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Accept": "text/javascript, text/html, application/xml, text/xml, */*",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "X-Requested-With": "XMLHttpRequest",
    "X-Prototype-Version": "1.7",
    "DNT": "1",
    "Sec-GPC": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

REQUEST_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_WAIT_MIN = 8.0
DEFAULT_WAIT_MAX = 16.0

_local = threading.local()


# ── 工具函数 ──────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Steam 鉴赏家评测浏览量脚本：访问鉴赏家推荐的游戏页面以提升浏览量",
    )
    parser.add_argument(
        "--clan-id",
        required=True,
        help="鉴赏家组的 ID（clan ID，纯数字，如 45519015）",
    )
    parser.add_argument(
        "--name",
        default="",
        help="鉴赏家组的名称（用于拼接 URL，可留空）",
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="Steam Cookie 字符串（必填，用于以登录身份访问）",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="代理地址，如 http://127.0.0.1:10279",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=835,
        help="每次拉取的组评数量（默认 835）",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="同时执行的线程数（默认 1）",
    )
    parser.add_argument(
        "--wait-min",
        type=float,
        default=DEFAULT_WAIT_MIN,
        help=f"每次访问之间的最小等待秒数（默认 {DEFAULT_WAIT_MIN}）",
    )
    parser.add_argument(
        "--wait-max",
        type=float,
        default=DEFAULT_WAIT_MAX,
        help=f"每次访问之间的最大等待秒数（默认 {DEFAULT_WAIT_MAX}）",
    )
    parser.add_argument(
        "--start-appid",
        default=None,
        help="从指定的 App ID 开始（留空则从头开始）",
    )
    parser.add_argument(
        "--log",
        default=None,
        metavar="FILE",
        help="日志文件路径（不传则仅输出到控制台）",
    )
    return parser.parse_args()


def setup_logging(log_file: Optional[str]) -> logging.Logger:
    """配置日志：输出到控制台，可选同时写入文件。"""
    logger = logging.getLogger("steam_curator_views")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    return logger


def encode_curator_name(name: str) -> str:
    """将组名编码为 Steam 鉴赏家 URL 中的 slug 格式。

    Steam 对非 ASCII 字节使用 "^%^25XX" 转义：先对名称做 URL 编码，
    再把每个 "%" 替换为 "^%^25"。
    """
    quoted = urllib.parse.quote(name, safe="")
    return quoted.replace("%", "^%^25")


def build_curator_url(clan_id: str, name: str) -> str:
    """根据组 ID 与组名构造鉴赏家推荐列表的 ajax 地址。"""
    if name:
        slug = urllib.parse.quote(encode_curator_name(name), safe="")
        return STEAM_CURATOR_URL.format(clan_id=clan_id, name_slug=slug)
    return STEAM_CURATOR_URL_NO_NAME.format(clan_id=clan_id)


def make_session(headers: dict, proxies: Optional[dict]) -> requests.Session:
    session = requests.Session()
    session.headers.update(headers)
    if proxies:
        session.proxies.update(proxies)
    return session


def fetch_url_with_retry(
    session: requests.Session,
    url: str,
    method: str = "GET",
    params: Optional[dict] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    is_initial_list: bool = False,
    logger: Optional[logging.Logger] = None,
) -> requests.Response:
    """带重试的请求封装，失败时指数等待后重试。"""
    logger = logger or logging.getLogger("steam_curator_views")
    target = "推荐列表" if is_initial_list else "游戏页面"
    for retries in range(1, max_retries + 1):
        try:
            if method == "GET":
                response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            else:
                response = session.post(url, data=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.warning("网络错误: %s", e)
            logger.warning("URL: %s", url)
            if retries < max_retries:
                wait_time = random.uniform(5, 15)
                logger.warning("尝试获取%s失败，等待 %.2f 秒后重试 (%d/%d)...",
                               target, wait_time, retries, max_retries)
                time.sleep(wait_time)
    logger.error("重试 %d 次后获取%s失败。", max_retries, target)
    raise


def visit_app_page(
    app_id: str,
    clan_id: str,
    headers: dict,
    proxies: Optional[dict],
    wait_min: float,
    wait_max: float,
    logger: logging.Logger,
) -> Optional[str]:
    """访问单个游戏页面以产生浏览量，返回游戏标题（未找到则为 None）。"""
    session = getattr(_local, "session", None)
    if session is None:
        session = make_session(headers, proxies)
        _local.session = session
    game_url = f"{STEAM_APP_BASE_URL}{app_id}/?curator_clanid={clan_id}"
    try:
        response = fetch_url_with_retry(session, game_url, logger=logger)
        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else None
        if not title:
            logger.warning("App ID %s: 未找到游戏标题。", app_id)
        return title
    except requests.exceptions.RequestException:
        logger.error("获取 App ID %s 的详细信息失败，跳过此项。", app_id)
        return None
    finally:
        time.sleep(random.uniform(wait_min, wait_max))


# ── 主流程 ────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    logger = setup_logging(args.log)

    if not args.cookie:
        logger.error("缺少 --cookie 参数，无法以登录身份访问 Steam。")
        sys.exit(1)

    headers = dict(DEFAULT_HEADERS)
    headers["Cookie"] = args.cookie
    proxies = {"http": args.proxy, "https": args.proxy} if args.proxy else None

    # 0. 尝试获取登录用户 ID（仅确认登录状态，失败不中断）
    try:
        logger.info("--------------------------")
        logger.info("尝试获取 Steam 用户 ID...")
        resp = requests.get(STEAM_MAIN_URL, headers=headers, proxies=proxies,
                            timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        tree = html.fromstring(resp.content)
        button = tree.xpath('//button[@id="account_pulldown"]')
        if button:
            logger.info("当前登录用户 ID: %s", button[0].text_content().strip())
        else:
            logger.warning("未找到用户 ID，可能未登录或页面结构已改变。")
    except requests.exceptions.RequestException as e:
        logger.warning("获取 Steam 主页失败，无法确认登录状态: %s", e)
    except Exception as e:
        logger.warning("解析用户 ID 失败: %s", e)

    # 1. 拉取组评推荐列表
    logger.info("--------------------------")
    logger.info("开始获取鉴赏家推荐列表...")
    curator_url = build_curator_url(args.clan_id, args.name)
    params = {
        "query": "",
        "start": "0",
        "count": str(args.count),
        "dynamic_data": "",
        "tagids": "",
        "sort": "recent",
        "app_types": "",
        "curations": "",
        "reset": "false",
    }
    response = fetch_url_with_retry(
        make_session(headers, proxies), curator_url, params=params,
        is_initial_list=True, logger=logger,
    )
    soup = BeautifulSoup(response.text, "html.parser")
    for _ in range(2):
        outer = soup.find("div")
        if outer:
            outer.unwrap()
    links = soup.find_all("a", attrs={"data-ds-appid": True})
    if not links:
        logger.error("未找到任何游戏推荐链接。请检查 URL 或 HTML 结构。")
        sys.exit(1)

    app_ids = [link["data-ds-appid"].replace('\\"', "") for link in links]
    logger.info("共获取到 %d 条组评。", len(app_ids))

    # 2. 定位起始 App ID
    start_index = 0
    if args.start_appid:
        try:
            start_index = app_ids.index(args.start_appid)
            logger.info("从 App ID %s 开始执行。", args.start_appid)
        except ValueError:
            logger.warning("未找到指定的 App ID %s，将从头开始执行。", args.start_appid)

    # 3. 并发访问游戏页面以产生浏览量
    total = len(app_ids) - start_index
    logger.info("开始处理 %d 个游戏页面（线程数: %d）...", total, max(1, args.threads))

    successful = 0
    last_processed: Tuple[str, str] = ("", "")
    try:
        with ThreadPoolExecutor(max_workers=max(1, args.threads)) as executor:
            futures = {
                executor.submit(
                    visit_app_page, app_id, args.clan_id, headers, proxies,
                    args.wait_min, args.wait_max, logger,
                ): app_id
                for app_id in app_ids[start_index:]
            }
            for future in as_completed(futures):
                app_id = futures[future]
                last_processed = (
                    app_id,
                    f"{STEAM_APP_BASE_URL}{app_id}/?curator_clanid={args.clan_id}",
                )
                try:
                    title = future.result()
                except Exception as e:
                    logger.error("获取 App ID %s 的详细信息失败，跳过此项。错误: %s",
                                 app_id, e)
                    continue
                if title:
                    successful += 1
                    logger.info("App ID %s - %s", app_id, title)
    except KeyboardInterrupt:
        logger.warning("脚本被用户中断。")

    # 4. 汇总
    logger.info("--------------------------")
    logger.info("脚本停止。")
    if last_processed[0]:
        logger.info("最后处理的项目信息: App ID %s, URL %s",
                    last_processed[0], last_processed[1])
    else:
        logger.info("未处理任何项目。")
    logger.info("成功获取游戏标题的次数: %d", successful)
    logger.info("--------------------------")


if __name__ == "__main__":
    main()
