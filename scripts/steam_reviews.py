#!/usr/bin/env python3
"""
steam_reviews.py - 提取 Steam 用户评测中的鉴赏家(Curator)链接

扫描指定 Steam 用户的评测页面，提取每条评测内容中包含的
鉴赏家超链接，输出为 CSV。

用法:
  python steam_reviews.py <steam_id> [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                         [--cookie "str"] [--proxy http://127.0.0.1:7890]

Cookie 来源优先级（高 → 低）:
  1. --cookie 命令行参数
  2. STEAM_COOKIE 环境变量
  3. cookie.txt 文件

Proxy 来源优先级（高 → 低）:
  1. --proxy 命令行参数
  2. HTTP_PROXY / HTTPS_PROXY 环境变量
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import re
import sys
import time
import random
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ── 常量 ──────────────────────────────────────────────────────────────────

STEAM_COMMUNITY = "https://steamcommunity.com"
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
    "Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]
REQUEST_DELAY = (1.0, 2.5)       # 翻页间隔（秒）
MAX_RETRIES = 3
PAGE_PARAM = "p"

DATE_PATTERNS = [
    # "发布于 2025 年 7 月 18 日。" (Chinese with year)
    re.compile(
        r"发布于\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    ),
    # "发布于 7 月 18 日。" (Chinese without year)
    re.compile(
        r"发布于\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    ),
    # "Posted: 1 Jan, 2024" / "Posted: 1 January 2024"
    re.compile(r"Posted:\s*(\d{1,2})\s+(\w+)[,\s]*(\d{4})", re.IGNORECASE),
    # "Posted: 1 Jan @ 3:00pm"
    re.compile(r"Posted:\s*(\d{1,2})\s+(\w+)[,\s]*(\d{4}).*", re.IGNORECASE),
]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


# ── 工具函数 ──────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="提取 Steam 用户评测中的鉴赏家(Curator)链接",
    )
    parser.add_argument(
        "steam_id",
        help="Steam 自定义 URL、SteamID64 或完整 URL（如 "
        "https://steamcommunity.com/id/xxx/recommended/）",
    )
    parser.add_argument(
        "--since",
        type=lambda s: datetime.date.fromisoformat(s),
        default=None,
        help="起始日期 YYYY-MM-DD，只抓此日期之后的评测",
    )
    parser.add_argument(
        "--until",
        type=lambda s: datetime.date.fromisoformat(s),
        default=None,
        help="结束日期 YYYY-MM-DD，只抓此日期之前的评测（含当日）",
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="Steam Cookie 字符串（优先级最高）",
    )
    parser.add_argument(
        "--cookie-file",
        default=None,
        metavar="FILE",
        help="Cookie 文件路径（默认项目目录下的 cookie.txt）",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="代理地址，如 http://127.0.0.1:7890 "
        "（也支持 HTTP_PROXY / HTTPS_PROXY 环境变量）",
    )
    parser.add_argument(
        "--list",
        default=None,
        metavar="FILE",
        help="批量模式：指定一个文本文件，每行一个 Steam URL/ID，依次处理",
    )
    return parser.parse_args()


def resolve_input(steam_input: str) -> tuple[str, str]:
    """解析输入为 (请求 URL, ID 部分)。

    支持:
      - 完整 URL:  直接使用，提取 ID 用于文件名
      - 纯 ID:     自动拼 URL
    """
    STEAM_COMMUNITY = "https://steamcommunity.com"
    url_match = re.match(
        r"(https?://steamcommunity\.com/(?:id|profiles)/[^/]+)",
        steam_input.strip(),
    )
    if url_match:
        # 输入是完整 URL — 直接使用
        fetch_url = url_match.group(1)
        id_match = re.search(r"/(id|profiles)/([^/]+)", fetch_url)
        id_part = id_match.group(2) if id_match else steam_input.strip()
        return fetch_url, id_part

    # 纯 ID
    if steam_input.isdigit() and len(steam_input) == 17:
        url_type = "profiles"
    else:
        url_type = "id"
    return f"{STEAM_COMMUNITY}/{url_type}/{steam_input}", steam_input


def load_cookie(cli_cookie: Optional[str], cookie_file_path: Optional[str] = None) -> Optional[str]:
    """按优先级获取 Cookie。返回 None 表示无 Cookie。

    优先级: --cookie 参数 > STEAM_COOKIE 环境变量 > --cookie-file > cookie.txt
    """
    if cli_cookie:
        return cli_cookie
    env_cookie = os.environ.get("STEAM_COOKIE")
    if env_cookie:
        return env_cookie
    # 自定义路径或默认路径
    paths = [Path(p) for p in ([cookie_file_path] if cookie_file_path else [])]
    paths.append(Path("cookie.txt"))
    for cf in paths:
        if cf.exists():
            return cf.read_text(encoding="utf-8").strip()
    return None


def load_proxy(cli_proxy: Optional[str]) -> Optional[dict[str, str]]:
    """按优先级获取代理配置。返回 None 表示不使用代理。"""
    proxy = cli_proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if not proxy:
        return None
    return {"http": proxy, "https": proxy}


def build_session(
    cookie_str: Optional[str],
    proxy: Optional[dict[str, str]],
) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    if cookie_str:
        session.headers.update({"Cookie": cookie_str})
    if proxy:
        session.proxies.update(proxy)
    return session


def parse_date(text: str) -> Optional[datetime.date]:
    """从评测日期文本中解析出日期。

    支持格式:
      - 发布于 2025 年 7 月 18 日。
      - 发布于 7 月 18 日。（无年份时使用当前年份）
      - Posted: 1 Jan, 2024
    """
    if not text:
        return None
    # 对 "发布于 7 月 17 日。最后编辑于 7 月 17 日。" 只取第一部分
    text = text.split("。")[0]

    for i, pat in enumerate(DATE_PATTERNS):
        m = pat.search(text)
        if not m:
            continue

        # 中文带年份: groups = (year, month, day)
        if i == 0:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return datetime.date(year, month, day)
            except ValueError:
                return None

        # 中文无年份: groups = (month, day)
        if i == 1:
            month, day = int(m.group(1)), int(m.group(2))
            today = datetime.date.today()
            year = today.year
            try:
                d = datetime.date(year, month, day)
            except ValueError:
                return None
            # 如果生成的日期在未来（最多容忍 7 天），回退到上一年
            if d > today + datetime.timedelta(days=7):
                d = datetime.date(year - 1, month, day)
            return d

        # 英文: groups = (day, month_str, year)
        day = int(m.group(1))
        month_str = m.group(2).strip().lower()[:3]
        year = int(m.group(3))
        month = MONTH_MAP.get(month_str)
        if month:
            try:
                return datetime.date(year, month, day)
            except ValueError:
                return None

    return None


def make_csv_filename(
    steam_id: str,
    since: Optional[datetime.date],
    until: Optional[datetime.date],
) -> str:
    today = datetime.date.today()
    s = since.isoformat() if since else today.isoformat()
    u = until.isoformat() if until else today.isoformat()
    return f"{steam_id}_{s}_{u}.csv"


# ── 页面抓取 ──────────────────────────────────────────────────────────────

def fetch_page(
    session: requests.Session,
    url: str,
    page: int,
) -> Optional[str]:
    """获取第 page 页的 HTML。失败返回 None。"""
    full_url = f"{url}?{PAGE_PARAM}={page}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(full_url, timeout=30)
            resp.raise_for_status()
            # 检查是否返回了有效的 Steam 页面（不是空/重定向）
            content = resp.text
            if len(content) < 500:
                print(
                    f"  [WARN] 第 {page} 页内容过短 ({len(content)} bytes)，"
                    f"可能已到尾页",
                    file=sys.stderr,
                )
                return None
            return content
        except requests.RequestException as exc:
            if attempt < MAX_RETRIES:
                wait = REQUEST_DELAY[1] * attempt
                print(
                    f"  [RETRY] 第 {page} 页请求失败 ({exc})，"
                    f"{wait:.0f}s 后重试 ({attempt}/{MAX_RETRIES})",
                    file=sys.stderr,
                )
                time.sleep(wait)
            else:
                print(
                    f"  [FAIL] 第 {page} 页请求失败: {exc}",
                    file=sys.stderr,
                )
                return None
    return None


# ── HTML 解析 ─────────────────────────────────────────────────────────────

def parse_reviews_from_html(
    html: str,
) -> list[dict]:
    """从 HTML 中解析出所有评测条目。

    每条返回:
        {
            "game_name": str,
            "app_id": Optional[str],
            "review_url": str,
            "date": Optional[datetime.date],
            "curators": [(url, text), ...]
        }
    """
    soup = BeautifulSoup(html, "lxml")
    reviews = []

    # 尝试多个可能的容器选择器（Steam 社区改版过）
    selectors = [
        "div.review_box",
        "div.profile_recommendation",
        "div.ReviewCard",
        "div.apphub_Card",
        "div.recommendation",
    ]

    review_cards = []
    for sel in selectors:
        review_cards = soup.select(sel)
        if review_cards:
            break

    if not review_cards:
        # 最后尝试：找包含 curator 链接的任意卡片状容器
        for card in soup.find_all("div", class_=re.compile(r"(review|recommend|card)", re.I)):
            if card.get_text(strip=True):
                review_cards.append(card)

    if not review_cards:
        print("  [WARN] 未找到评测卡片，页面结构可能已变更", file=sys.stderr)
        return []

    for card in review_cards:
        try:
            item = _parse_single_review(card)
            if item is not None:
                reviews.append(item)
        except Exception as exc:
            # 单条解析失败不中断
            print(
                f"  [WARN] 解析单条评测时出错: {exc}",
                file=sys.stderr,
            )
            continue

    return reviews


def _parse_single_review(card) -> Optional[dict]:
    """解析单条评测卡片。"""
    # ── 游戏名 ──
    game_name = _extract_game_name(card)
    if not game_name:
        return None

    # ── App ID ──
    app_id = _extract_app_id(card)

    # ── 评测链接 ──
    review_url = _extract_review_url(card)

    # ── 评测日期 ──
    date = _extract_date(card)

    # ── 鉴赏家链接 ──
    curators = _extract_curator_links(card)

    if not curators:
        return None  # 没有 curator 链接的评测跳过

    return {
        "game_name": game_name,
        "app_id": app_id,
        "review_url": review_url or "",
        "date": date,
        "curators": curators,
    }


def _extract_game_name(card) -> Optional[str]:
    """从卡片中提取游戏名称。"""
    # 尝试1: 评测内容中的 bb_h1（中文 Steam 常见格式）
    content_div = card.select_one("div.content")
    if content_div:
        h1 = content_div.select_one("div.bb_h1")
        if h1:
            text = h1.get_text(strip=True)
            if text:
                return text

    # 尝试2: 应用链接 + 文字
    name_selectors = [
        "div.review_box_header a",
        "a[href*='/app/']",
        "div.recommendation_header a",
        "div.apphub_Card_Title a",
        "h2 a", "h3 a", "h4 a",
    ]
    for sel in name_selectors:
        links = card.select(sel)
        for link in links:
            href = link.get("href", "")
            if "/app/" in href:
                text = link.get_text(strip=True)
                if text:
                    return text
                # 如果链接里只有图片，从图片 alt 取
                img = link.select_one("img")
                if img:
                    alt = img.get("alt", "") or img.get("title", "")
                    if alt:
                        return alt

    # 尝试3: 从 app 链接提取 appid → 后续可通过 API 获取名称
    # 但只记录 appid 不够友好，先作为备选
    app_link = card.select_one("a[href*='/app/']")
    if app_link:
        href = app_link.get("href", "")
        m = re.search(r"/app/(\d+)", href)
        if m:
            return f"App {m.group(1)}"

    # 尝试4: 找任何带 href 的标题类元素
    for tag in card.find_all(["a", "b", "strong", "span"]):
        cls = " ".join(tag.get("class", []))
        if "title" in cls.lower() or "name" in cls.lower():
            text = tag.get_text(strip=True)
            if text:
                return text

    # 尝试5: 第一个大号文字
    for tag in card.find_all(["h2", "h3", "h4"]):
        text = tag.get_text(strip=True)
        if text and len(text) < 100:
            return text

    return None


def _extract_app_id(card) -> Optional[str]:
    """从卡片中提取 Steam App ID。"""
    link = card.select_one("a[href*='/app/']")
    if not link:
        return None
    href = link.get("href", "")
    m = re.search(r"/app/(\d+)", href)
    return m.group(1) if m else None


def _extract_review_url(card) -> Optional[str]:
    """从卡片中提取评测链接。"""
    for sel in ["div.thumb a", "div.title a", "a[href*='/recommended/']"]:
        link = card.select_one(sel)
        if link:
            href = link.get("href", "")
            if "/recommended/" in href:
                return href.rstrip("/")
    return None


def _extract_all_dates(html: str) -> list[datetime.date]:
    """从整个页面 HTML 中提取所有评测的日期（不论是否有 curator 链接）。

    用于翻页终止判定：如果页面最新日期 < since，后面的只会更旧，可以停。
    """
    soup = BeautifulSoup(html, "lxml")
    dates = []
    for card in soup.select("div.review_box"):
        d = _extract_date(card)
        if d:
            dates.append(d)
    return dates


def _extract_date(card) -> Optional[datetime.date]:
    """从卡片中提取评测日期。"""
    date_selectors = [
        "div.review_box_date",
        "div.recommendation_date",
        "div.posted",
        "div.date",
        "span.date",
        "time",
        "*[class*='posted']",
        "*[class*='date']",
        "*[class*='time']",
    ]
    for sel in date_selectors:
        elems = card.select(sel) if sel else []
        for elem in elems:
            text = elem.get_text(strip=True)
            d = parse_date(text)
            if d:
                return d

    # 全文搜日期模式
    d = parse_date(card.get_text())
    return d


def _extract_curator_links(card) -> list[tuple[str, str]]:
    """从卡片中提取所有鉴赏家超链接。

    Returns:
        [(url, link_text), ...]
    """
    results = []
    for link in card.find_all("a", href=True):
        href = link["href"]
        if "store.steampowered.com/curator/" in href:
            # 规范化 URL
            url = href.split("?")[0].rstrip("/")
            text = link.get_text(strip=True) or ""
            results.append((url, text))
    return results


# ── 主流程 ──────────────────────────────────────────────────────────────

CSV_FIELDS = ["游戏名", "App ID", "评测时间", "评测链接", "鉴赏家链接", "鉴赏家名称"]


def process_user(
    session: requests.Session,
    writer: csv.DictWriter,
    csv_file,
    steam_input: str,
    since: Optional[datetime.date],
    until: Optional[datetime.date],
) -> int:
    """处理单个用户的评测，返回写入的记录数。"""
    fetch_url, id_part = resolve_input(steam_input)
    url = fetch_url
    if not url.endswith("/recommended"):
        url = url.rstrip("/") + "/recommended/"

    total_rows = 0
    page = 1
    stop_pagination = False

    print()
    print(f"════════════════════════════════════════════")
    print(f"  用户: {id_part}")
    print(f"  URL:  {url}")
    print(f"  日期: {since or '不限'} → {until or '不限'}")
    print(f"════════════════════════════════════════════")

    while not stop_pagination:
        print(f"  [PAGE] 第 {page} 页...", file=sys.stderr)

        html = fetch_page(session, url, page)
        if html is None:
            print(f"  [DONE] 第 {page} 页无数据", file=sys.stderr)
            break

        curator_reviews = parse_reviews_from_html(html)
        all_dates = _extract_all_dates(html)

        if not all_dates and not curator_reviews:
            print(f"  [DONE] 第 {page} 页无任何评测", file=sys.stderr)
            break

        # 日期终止判定
        if since and all_dates:
            max_date = max(all_dates)
            if max_date < since:
                print(
                    f"  [DONE] 最新评测 {max_date} 早于 {since}，停止",
                    file=sys.stderr,
                )
                stop_pagination = True

        for rev in curator_reviews:
            rev_date = rev["date"]
            if rev_date:
                if since and rev_date < since:
                    continue
                if until and rev_date > until:
                    continue

            for curator_url, curator_name in rev["curators"]:
                row = {
                    "游戏名": rev["game_name"],
                    "App ID": rev["app_id"] or "",
                    "评测时间": rev_date.isoformat() if rev_date else "",
                    "评测链接": rev["review_url"],
                    "鉴赏家链接": curator_url,
                    "鉴赏家名称": curator_name,
                }
                writer.writerow(row)
                csv_file.flush()
                total_rows += 1
                print(
                    f"  [{rev['game_name']}]({rev['app_id'] or '?'}) {rev_date or 'N/A'} "
                    f"→ {curator_name} ({curator_url})"
                )

        if not stop_pagination:
            page += 1
            delay = random.uniform(*REQUEST_DELAY)
            time.sleep(delay)

    print(f"  [DONE] {id_part}: 共 {total_rows} 条")
    return total_rows


def run() -> None:
    args = parse_args()
    cookie_str = load_cookie(args.cookie, args.cookie_file)
    proxy = load_proxy(args.proxy)
    session = build_session(cookie_str, proxy)

    if cookie_str:
        print("[INFO] 使用 Cookie 登录会话")
    else:
        print("[INFO] 未使用 Cookie（公开数据）")
    if proxy:
        print(f"[INFO] 使用代理: {proxy['https']}")

    since = args.since
    until = args.until

    # ── 收集所有输入 ──
    if args.list:
        with open(args.list, "r", encoding="utf-8") as f:
            inputs = [line.strip() for line in f if line.strip()]
        print(f"[INFO] 批量模式: 共 {len(inputs)} 个用户")
    else:
        inputs = [args.steam_id]

    # ── 一个 CSV，所有用户数据 ──
    if args.list:
        csv_name = f"batch_{datetime.date.today().isoformat()}.csv"
    else:
        _, id_part = resolve_input(args.steam_id)
        csv_name = make_csv_filename(id_part, since, until)

    csv_file = open(csv_name, "w", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    writer.writeheader()
    csv_file.flush()

    print(f"[INFO] 输出文件: {csv_name}")

    grand_total = 0
    for steam_input in inputs:
        grand_total += process_user(session, writer, csv_file, steam_input, since, until)

    csv_file.close()
    print()
    print(f"[DONE] 全部完成，共 {grand_total} 条记录，已保存至 {csv_name}")


# ── 入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run()
