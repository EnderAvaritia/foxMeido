"""
Steam 鉴赏家待处理副本监控 - NoneBot2 插件

定时抓取鉴赏家后台 pending 页面，检测新增的游戏副本邀请，
通过 QQ 群消息推送通知（可选同时推送 ntfy）。

用法：
  pending              — 手动触发检查，结果发到当前群
  pending test         — 发送测试推送

配置（.env）：
  CURATOR_COOKIE        — Steam 鉴赏家后台 Cookie（与商店页面 cookie 不同）
  CURATOR_ID             — 鉴赏家 ID
  CURATOR_NAME           — 鉴赏家名称（可选，默认 "鉴赏家"）
  CURATOR_ENABLED       — 是否启用每日定时检查（默认 false）
  CURATOR_NOTIFY_GROUP   — 每日定时推送的目标群号（可选）
  CURATOR_NOTIFY_USER    — 每日定时推送的目标 QQ 号（可选，与 GROUP 可同时设置）
  CURATOR_CHECK_TIME     — 每日定时检查时间，格式 HH:MM（默认 09:00）
  CURATOR_NTFY_TOPIC     — ntfy topic（可选，设了则额外推送到 ntfy）
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from nonebot import require, get_bot, on_startswith
from nonebot.plugin import on_command
from nonebot.log import logger
from nonebot.exception import FinishedException

from plugins.noco.noco_config import get_proxies
from plugins.message_reaction import reaction_cleanup
from plugins.playwright_utils import ensure_browser, create_context

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler  # noqa: E402


# ── 常量 ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "db" / "curator_state.db"
CST = timezone(timedelta(hours=8))

# ── 自定义异常 ──────────────────────────────────────────────────
class CookieExpiredError(Exception):
    """CURATOR_COOKIE / CURATOR_COOKIE_FILE 已过期，需要重新获取。"""
    pass


# ── 默认 ──────────────────────────────────────────────────────────
curator_cmd = on_startswith("pending", ignorecase=False, priority=20, block=True)


# ── 数据结构 ──────────────────────────────────────────────────────
@dataclass
class PendingGame:
    app_id: str
    name: str
    copies: int
    expiration: str


@dataclass
class CheckResult:
    total_pending: int
    games: list[PendingGame]
    new_games: list[PendingGame]
    updated_games: list[PendingGame]
    today_games: list[PendingGame] | None = None
    error: str | None = None


# ── 配置读取 ──────────────────────────────────────────────────────
_CURATOR_NAME_CACHE: str | None = None


def _read_dotenv(key: str) -> str:
    """从 os.environ 或 .env 文件读配置（使用 noco_config 的读取方式）。"""
    from plugins.noco.noco_config import _read_dotenv as _noco_read
    return _noco_read(key)


def _resolve_curator_name(curator_id: str) -> str:
    """获取鉴赏家显示名称：优先 CURATOR_NAME，未设则从 Steam 页面自动抓取。"""
    global _CURATOR_NAME_CACHE
    if _CURATOR_NAME_CACHE is not None:
        return _CURATOR_NAME_CACHE

    env_name = _read_dotenv("CURATOR_NAME")
    if env_name:
        _CURATOR_NAME_CACHE = env_name
        return env_name

    # 自动探测：访问 curator 页面，从 HTML 或重定向 URL 提取名字
    try:
        from urllib.parse import unquote
        proxies = get_proxies()
        url = f"https://store.steampowered.com/curator/{curator_id}/"
        resp = requests.get(
            url, proxies=proxies, timeout=10,
            allow_redirects=True,
            verify=not bool(proxies),
        )

        # 方式一：从 HTML 中取 <a href="/curator/{id}-...">显示名</a>
        # 注意同一个 href 可能对应多个 a 标签（响应式菜单），找第一个有文字的
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=re.compile(rf"/curator/{curator_id}-")):
            text = a.get_text(strip=True)
            if text:
                _CURATOR_NAME_CACHE = text
                logger.info("鉴赏家名字自动探测（HTML）: %s", text)
                return text

        # 方式二：从重定向 URL 提取
        m = re.search(r"/curator/\d+-(.+?)(?:/|$)", resp.url)
        if m:
            name = unquote(m.group(1))
            _CURATOR_NAME_CACHE = name
            logger.info("鉴赏家名字自动探测（URL）: %s", name)
            return name
    except Exception as e:
        logger.warning("鉴赏家名字自动探测失败: %s", e)

    _CURATOR_NAME_CACHE = "鉴赏家"
    return _CURATOR_NAME_CACHE


def get_config() -> dict[str, Any]:
    """读取插件所需的所有配置项。"""
    cookie = _read_dotenv("CURATOR_COOKIE")
    cookie_file = _read_dotenv("CURATOR_COOKIE_FILE")
    curator_id = _read_dotenv("CURATOR_ID")
    curator_name = _resolve_curator_name(curator_id)
    notify_group = _read_dotenv("CURATOR_NOTIFY_GROUP")
    notify_user = _read_dotenv("CURATOR_NOTIFY_USER")
    check_time = _read_dotenv("CURATOR_CHECK_TIME") or "09:00"
    ntfy_topic = _read_dotenv("CURATOR_NTFY_TOPIC")
    enabled = _read_dotenv("CURATOR_ENABLED") in ("true", "1", "yes")

    return {
        "cookie": cookie,
        "cookie_file": cookie_file,
        "curator_id": curator_id,
        "curator_name": curator_name,
        "notify_group": notify_group,
        "notify_user": notify_user,
        "check_time": check_time,
        "ntfy_topic": ntfy_topic,
        "enabled": enabled,
    }


def is_configured() -> bool:
    """检查配置是否足以运行（CURATOR_COOKIE_FILE 或 CURATOR_COOKIE 任一 + CURATOR_ID）。"""
    cfg = get_config()
    has_auth = bool(cfg["cookie_file"]) or bool(cfg["cookie"])
    return has_auth and bool(cfg["curator_id"])


# ── Cookie 解析 ──────────────────────────────────────────────────
def parse_cookie(cookie_str: str) -> dict[str, str]:
    """将 'key=value; key=value' 格式的 Cookie 字符串解析为 dict。"""
    result: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            key, _, val = part.partition("=")
            key = key.strip()
            val = val.strip()
            if key:
                result[key] = val
    return result


# ── SQLite 状态管理 ──────────────────────────────────────────────
def _get_db() -> sqlite3.Connection:
    """获取 SQLite 连接（线程安全：每个连接独立）。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db() -> None:
    """确保数据库和表存在。"""
    conn = _get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_games (
                app_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                copies INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                first_seen_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        # 兼容旧表：补 first_seen_at 列
        try:
            conn.execute("ALTER TABLE seen_games ADD COLUMN first_seen_at TEXT")
            conn.execute("UPDATE seen_games SET first_seen_at = updated_at WHERE first_seen_at IS NULL")
        except sqlite3.OperationalError:
            pass  # 列已存在
        conn.commit()
    finally:
        conn.close()


def load_seen_games() -> dict[str, dict[str, Any]]:
    """从 SQLite 加载已见游戏。{app_id: {name, copies}}"""
    conn = _get_db()
    try:
        rows = conn.execute("SELECT app_id, name, copies FROM seen_games").fetchall()
        return {row[0]: {"name": row[1], "copies": row[2]} for row in rows}
    finally:
        conn.close()


def load_today_ids() -> set[str]:
    """从 SQLite 加载今天首次入库的游戏 app_id 集合。"""
    conn = _get_db()
    try:
        today = datetime.now(CST).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT app_id FROM seen_games WHERE date(first_seen_at) = ?",
            (today,),
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def save_seen_games(games: list[PendingGame]) -> None:
    """将当前游戏列表写入 SQLite。首次入库记录 first_seen_at，后续仅更新名称和副本数。"""
    conn = _get_db()
    try:
        now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
        for g in games:
            conn.execute("""
                INSERT INTO seen_games (app_id, name, copies, first_seen_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(app_id) DO UPDATE SET
                    name=excluded.name,
                    copies=excluded.copies,
                    updated_at=excluded.updated_at
            """, (g.app_id, g.name, g.copies, now, now))
        conn.commit()
    finally:
        conn.close()


# ── 中文数字解析 ────────────────────────────────────────────────
_CHINESE_DIGITS = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


def _parse_copies(text: str) -> int:
    """从 '您收到了 X 个副本' 中提取数量。"""
    m = re.search(r"收到了\s*(\d+)\s*个副本", text)
    if m:
        return int(m.group(1))
    m = re.search(r"收到了\s*(一|二|两|三|四|五|六|七|八|九|零)\s*个副本", text)
    if m:
        return _CHINESE_DIGITS.get(m.group(1), 0)
    return 0


# ── Steam 页面抓取 ────────────────────────────────────────────────
def build_url(curator_id: str, curator_name: str) -> str:
    """构造 pending 页面 AJAX URL（只用 ID，名字仅作 fallback）。"""
    return (f"https://store.steampowered.com/curator/"
            f"{curator_id}/admin/pending?ajax=1")


async def fetch_pending_html(curator_id: str, curator_name: str,
                              cookie_str: str, cookie_file: str) -> str:
    """
    抓取 pending 页面，返回 HTML 文本。

    优先使用 Playwright + CURATOR_COOKIE_FILE（更稳定，session 维持更久）。
    降级使用 requests + CURATOR_COOKIE（旧方式，静态 Cookie）。
    """
    url = build_url(curator_id, curator_name)

    if cookie_file:
        return await _fetch_pending_with_playwright(url, cookie_file)
    else:
        return _fetch_pending_with_requests(url, cookie_str)


# ── Playwright 路径 ──────────────────────────────────────────────
_LOGIN_TITLES = {"sign in", "login", "welcome to steam"}


async def _fetch_pending_with_playwright(url: str, cookie_file: str) -> str:
    """通过 Playwright 加载 pending 页面，自动使用 cookie 文件维持登录态。"""
    if not await ensure_browser():
        raise RuntimeError("浏览器启动失败")

    context = await create_context(cookie_file=cookie_file)
    if context is None:
        raise RuntimeError("创建浏览器上下文失败")

    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # 过期检测：检查页面标题是否为登录页
        title = await page.title()
        title_lower = title.strip().lower()
        for keyword in _LOGIN_TITLES:
            if keyword in title_lower:
                raise CookieExpiredError(
                    "CURATOR_COOKIE_FILE 已过期（检测到登录页），"
                    "请重新运行 python scripts/get_curator_cookies.py")

        # 额外检测：URL 是否被重定向到登录页
        current_url = page.url
        if "login" in current_url.lower():
            raise CookieExpiredError(
                "CURATOR_COOKIE_FILE 已过期（被重定向到登录页），"
                "请重新运行 python scripts/get_curator_cookies.py")

        html = await page.content()
        return html

    except CookieExpiredError:
        raise
    except Exception as e:
        logger.error(f"Playwright 抓取 pending 页面失败: {e}")
        raise RuntimeError(f"Playwright 抓取 pending 页面失败: {e}") from e
    finally:
        await context.close()


# ── requests 降级路径 ────────────────────────────────────────────
def _fetch_pending_with_requests(url: str, cookie_str: str) -> str:
    """通过 requests 加载 pending 页面（旧方式，使用静态 Cookie）。"""
    proxies = get_proxies()
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) "
                       "Gecko/20100101 Firefox/150.0"),
        "Accept": "text/html, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": url.replace("?ajax=1", ""),
        "Cookie": cookie_str,
    }

    resp = requests.get(url, headers=headers, proxies=proxies, timeout=30,
                        verify=not bool(proxies))
    resp.raise_for_status()

    # 过期检测：检查响应是否包含登录页特征
    text_lower = resp.text.lower()
    if _is_login_page(text_lower):
        raise CookieExpiredError(
            "CURATOR_COOKIE 已过期（检测到登录页），"
            "建议改用 CURATOR_COOKIE_FILE 配合 Playwright 获取方式，"
            "或重新从浏览器复制 CURATOR_COOKIE")

    return resp.text


def _is_login_page(html_lower: str) -> bool:
    """检测 HTML 是否属于 Steam 登录页面（而非正常 pending 页面）。"""
    # 登录页特征：title 或 URL 包含登录关键词
    for keyword in _LOGIN_TITLES:
        if keyword in html_lower:
            return True
    # 额外的: pending 页面包含 sessionid 在正常内容中，登录页没有
    if "login" in html_lower and "pending" not in html_lower:
        return True
    return False


# ── HTML 解析 ─────────────────────────────────────────────────────
def parse_pending_page(html: str) -> CheckResult:
    """解析 pending 页面 HTML，提取游戏列表和总数。"""
    soup = BeautifulSoup(html, "html.parser")
    games: list[PendingGame] = []

    # 待处理总数
    total_pending = 0
    pending_stat = soup.select_one(".pending_stat")
    if pending_stat:
        stat_text = pending_stat.get_text(strip=True)
        match = re.search(r"(\d+)", stat_text)
        if match:
            total_pending = int(match.group(1))

    # 解析每个游戏卡片
    offer_divs = soup.select("div[id^='app-ctn-']")
    for div in offer_divs:
        app_id = div["id"].replace("app-ctn-", "")

        name_el = div.select_one(".app_name")
        name = name_el.get_text(strip=True) if name_el else "未知"

        copies = 0
        name_ctn = div.select_one(".app_name_ctn")
        if name_ctn:
            full_text = name_ctn.get_text("\n", strip=True)
            copies = _parse_copies(full_text)

        expiration = ""
        if name_ctn:
            spans = name_ctn.find_all("span")
            for span in spans:
                text = span.get_text(strip=True)
                if "过期" in text or "expire" in text.lower():
                    expiration = text
                    break

        games.append(PendingGame(
            app_id=app_id, name=name, copies=copies, expiration=expiration,
        ))

    return CheckResult(total_pending=total_pending, games=games,
                       new_games=[], updated_games=[])


# ── 变化检测 ──────────────────────────────────────────────────────
def detect_changes(
    games: list[PendingGame],
    seen: dict[str, dict[str, Any]],
    track_copies: bool = False,
) -> tuple[list[PendingGame], list[PendingGame]]:
    """与已见状态比对，返回 (新增的, 份数变化的)。"""
    new: list[PendingGame] = []
    updated: list[PendingGame] = []
    for game in games:
        entry = seen.get(game.app_id)
        if entry is None:
            new.append(game)
            continue
        if track_copies:
            prev = entry.get("copies", 0)
            if prev != game.copies:
                updated.append(game)
    return new, updated


# ── 执行检查 ──────────────────────────────────────────────────────
async def run_check() -> CheckResult:
    """执行一次完整的检查流程。"""
    cfg = get_config()
    html = await fetch_pending_html(
        cfg["curator_id"], cfg["curator_name"], cfg["cookie"], cfg["cookie_file"])
    result = parse_pending_page(html)

    seen = load_seen_games()
    result.new_games, result.updated_games = detect_changes(
        result.games, seen, track_copies=False)

    # 更新 SQLite 状态，然后读取入库总数
    save_seen_games(result.games)
    total_in_db = len(load_seen_games())

    # 有新增时，收集今天所有新到游戏（使用当前拉取的副本数量）
    if result.new_games:
        today_ids = load_today_ids()
        result.today_games = [g for g in result.games if g.app_id in today_ids]

    # 可选 ntfy 推送
    if result.new_games or result.updated_games:
        maybe_ntfy(result, cfg["curator_name"])

    if not result.games:
        logger.info(
            "鉴赏家检查完成: 待处理 {}, 游戏 {} 款, 新增 {}, 累计 {}\n探测结果为空",
            result.total_pending, len(result.games), len(result.new_games),
            total_in_db,
        )
    elif result.new_games:
        logger.info(
            "鉴赏家检查完成: 待处理 {}, 游戏 {} 款, 新增 {}, 累计 {}\n最新: {}",
            result.total_pending, len(result.games), len(result.new_games),
            total_in_db, result.new_games[0].name,
        )
    else:
        logger.info(
            "鉴赏家检查完成: 待处理 {}, 游戏 {} 款, 新增 {}, 累计 {}\n无新增",
            result.total_pending, len(result.games), len(result.new_games),
            total_in_db,
        )
    return result


# ── ntfy 推送（可选）─────────────────────────────────────────────
def send_ntfy(title: str, message: str, topic: str) -> bool:
    """通过 ntfy.sh 发送推送通知。返回是否成功。"""
    payload = {
        "topic": topic,
        "title": title,
        "message": message,
        "tags": ["steam", "new"],
        "priority": 4,
    }
    headers = {"Content-Type": "application/json"}
    proxies = get_proxies()
    try:
        resp = requests.post(
            "https://ntfy.sh",
            data=json.dumps(payload),
            headers=headers,
            proxies=proxies,
            timeout=15,
            verify=not bool(proxies),
        )
        resp.raise_for_status()
        logger.info("ntfy 推送成功: %s", title)
        return True
    except requests.RequestException as e:
        logger.error("ntfy 推送失败: %s", e)
        return False


def maybe_ntfy(result: CheckResult, curator_name: str) -> None:
    """如果有 ntfy topic 配置，推送变化通知。"""
    topic = get_config().get("ntfy_topic", "")
    if not topic:
        return
    lines: list[str] = []
    for g in result.new_games:
        lines.append(f"[新增] {g.name} - {g.copies} 个副本")
    for g in result.updated_games:
        lines.append(f"[更新] {g.name} - {g.copies} 个副本")
    if not lines:
        return

    body = "\n".join(lines)
    if len(body.encode("utf-8")) > 1800:
        body = "\n".join(lines[:5])
        rest = len(lines) - 5
        if rest > 0:
            body += f"\n... 及其他 {rest} 款游戏"

    send_ntfy(
        title=f"{curator_name} 待处理副本更新",
        message=body,
        topic=topic,
    )


# ── 格式化消息 ────────────────────────────────────────────────────
def format_result(result: CheckResult, curator_name: str) -> str:
    """将检查结果格式化为 QQ 消息文本。"""
    lines: list[str] = []

    if result.new_games:
        lines.append(f"📦 {curator_name} 新增待处理副本：")
        for g in result.new_games:
            lines.append(f"  🆕 {g.name}（{g.copies} 个副本）")
        lines.append("")

        # 今天所有新到游戏（含本次新增，使用当前副本数）
        if result.today_games:
            lines.append(f"📋 {curator_name} 今日新到游戏：")
            for g in result.today_games:
                lines.append(f"  📅 {g.name}（{g.copies} 个副本）")
            lines.append("")

    if result.updated_games:
        lines.append(f"🔄 {curator_name} 副本数更新：")
        for g in result.updated_games:
            lines.append(f"  🔄 {g.name}（{g.copies} 个副本）")
        lines.append("")

    if not result.new_games and not result.updated_games:
        lines.append(f"✅ {curator_name} 无新增待处理副本")
    else:
        lines.append(f"💡 共 {result.total_pending} 款游戏待处理")

    return "\n".join(lines)


# ── 发送消息 ──────────────────────────────────────────────────────
async def send_to_group(group_id: str, message: str) -> None:
    """向指定 QQ 群发送消息。"""
    try:
        bot = get_bot()
        await bot.call_api("send_group_msg", group_id=int(group_id), message=message)
    except Exception as e:
        logger.error(f"发送群消息失败 (group={group_id}): {e}")


async def send_to_user(user_id: str, message: str) -> None:
    """向指定 QQ 用户发送私聊消息。"""
    try:
        bot = get_bot()
        await bot.call_api("send_private_msg", user_id=int(user_id), message=message)
    except Exception as e:
        logger.error(f"发送私聊消息失败 (user={user_id}): {e}")


# ── 手动命令 ──────────────────────────────────────────────────────
@curator_cmd.handle()
async def handle_curator(bot, event):
    cleanup = await reaction_cleanup(bot, event)

    # 解析参数
    raw_msg = event.get_plaintext() if hasattr(event, "get_plaintext") else str(event)
    args = raw_msg.strip().split()
    is_test = len(args) > 1 and args[1] == "test"

    if not is_configured():
        if cleanup: await cleanup()
        await curator_cmd.finish("⚠️ 未配置 CURATOR_COOKIE_FILE 或 CURATOR_COOKIE，请先设置 .env")

    if is_test:
        cfg = get_config()
        # QQ 测试消息
        test_msg = (
            f"🧪 测试推送\n"
            f"鉴赏家: {cfg['curator_name']}\n"
            f"此消息表示推送配置正常"
        )
        await curator_cmd.send(test_msg, at_sender=False)

        # ntfy 测试（如果有配置）
        ntfy_topic = cfg.get("ntfy_topic", "")
        if ntfy_topic:
            ok = send_ntfy("🧪 测试推送", f"鉴赏家 {cfg['curator_name']} 测试消息", ntfy_topic)
            if cleanup: await cleanup()
            await curator_cmd.finish(
                f"ntfy 推送{'✅ 成功' if ok else '❌ 失败'}",
                at_sender=False,
            )
        else:
            if cleanup: await cleanup()
            await curator_cmd.finish("ntfy 未配置，仅发送了 QQ 消息", at_sender=False)

    # 执行检查（不再发"正在检查"，✅表情即为响应）
    try:
        result = await run_check()
        cfg = get_config()
        msg = format_result(result, cfg["curator_name"])
        if cleanup: await cleanup()
        await curator_cmd.finish(msg, at_sender=False)
    except CookieExpiredError as e:
        if cleanup: await cleanup()
        await curator_cmd.finish(f"❌ {e}", at_sender=False)
    except requests.RequestException as e:
        if cleanup: await cleanup()
        await curator_cmd.finish(f"❌ 网络请求失败: {e}", at_sender=False)
    except FinishedException:
        raise
    except Exception as e:
        logger.exception("检查异常")
        if cleanup: await cleanup()
        await curator_cmd.finish(f"❌ 检查异常: {e}", at_sender=False)


# ── 定时任务：每日推送 ────────────────────────────────────────────
def _parse_check_time(time_str: str) -> tuple[int, int]:
    """解析 'HH:MM' 格式的时间字符串。"""
    parts = time_str.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return hour, minute


async def scheduled_check():
    """定时任务：每日检查待处理副本并推送到指定群/用户。"""
    cfg = get_config()
    notify_group = cfg["notify_group"]
    notify_user = cfg["notify_user"]

    if not notify_group and not notify_user:
        logger.info("CURATOR_NOTIFY_GROUP 和 CURATOR_NOTIFY_USER 均未配置，跳过定时推送")
        return

    if not is_configured():
        logger.info("CURATOR_COOKIE 或 CURATOR_ID 未配置，跳过定时推送")
        return

    logger.info("定时检查：开始执行")
    try:
        result = await run_check()
        if not result.new_games and not result.updated_games:
            logger.info("无变化，跳过推送")
            return
        msg = format_result(result, cfg["curator_name"])
        if notify_group:
            await send_to_group(notify_group, msg)
        if notify_user:
            await send_to_user(notify_user, msg)
    except Exception as e:
        logger.exception(f"定时检查异常: {e}")
        err_msg = f"❌ 鉴赏家副本检查异常: {e}"
        if notify_group:
            await send_to_group(notify_group, err_msg)
        if notify_user:
            await send_to_user(notify_user, err_msg)


# ── 插件初始化 ────────────────────────────────────────────────────
_init_db()

# 注册定时任务（仅在启用时）
_cfg = get_config()
if _cfg["enabled"]:
    _hour, _minute = _parse_check_time(_cfg["check_time"])
    scheduler.add_job(
        scheduled_check,
        "cron",
        hour=_hour,
        minute=_minute,
        id="curator_daily_check",
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info(f"鉴赏家监控已注册，定时检查时间: {_cfg['check_time']}")
else:
    logger.info("鉴赏家监控未启用（CURATOR_ENABLED=false），仅支持手动 pending 命令")
