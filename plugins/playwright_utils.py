"""
playwright_utils.py - 共享 Playwright 工具

集中管理 Playwright 浏览器/页面创建逻辑，避免 5+ 个文件中重复 init_playwright。
各调用方自行管理模块级缓存，支持可选视口尺寸。

全局缓存 browser（浏览器进程），但每次截图创建新 page 以避免并发冲突。
"""

from __future__ import annotations

import json
import os

from playwright.async_api import async_playwright
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from plugins.noco.noco_config import get_http_proxy
from plugins.error_logger import log_error

# 全局浏览器实例（模块级缓存，只启动一次）
_playwright = None
_browser = None

# Playwright Cookie 文件路径（懒加载）
_cookie_file_path: str | None = None


def _get_cookie_file_path() -> str:
    """读取 PLAYWRIGHT_COOKIE_FILE（os.environ → .env 兜底）。"""
    global _cookie_file_path
    if _cookie_file_path is not None:
        return _cookie_file_path
    value = os.getenv("PLAYWRIGHT_COOKIE_FILE", "")
    if not value:
        # .env 兜底
        env_path = os.path.join(_project_root(), ".env")
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.startswith("PLAYWRIGHT_COOKIE_FILE="):
                            value = line[len("PLAYWRIGHT_COOKIE_FILE="):].strip().strip('"').strip("'")
                            break
            except OSError:
                pass
    _cookie_file_path = value
    return _cookie_file_path


def _project_root() -> str:
    """获取项目根目录（此文件位于 plugins/ 下，往上级 1 层）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def load_cookie_file(context) -> None:
    """
    从 JSON 文件加载 Playwright cookie 到指定 context。

    JSON 格式为数组，每项需包含 name / value / domain / path，
    可选 httpOnly / secure / sameSite / expires。
    参考 cookies/steam_playwright.json.example。

    如果未配置 PLAYWRIGHT_COOKIE_FILE 或文件不存在，静默跳过。
    """
    cookie_file = _get_cookie_file_path()
    if not cookie_file:
        return
    fpath = os.path.join(_project_root(), cookie_file)
    if not os.path.isfile(fpath):
        log_error("load_cookie_file", f"Cookie 文件不存在: {fpath}")
        return
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if not isinstance(cookies, list):
            log_error("load_cookie_file", f"Cookie 文件格式错误：需要 JSON 数组，得到 {type(cookies).__name__}")
            return
        await context.add_cookies(cookies)
        print(f"[playwright] 已加载 {len(cookies)} 个 cookie")
    except json.JSONDecodeError as e:
        log_error("load_cookie_file", f"Cookie 文件 JSON 解析失败: {e}")
    except Exception as e:
        log_error("load_cookie_file", f"Cookie 加载异常: {e}")


async def ensure_browser():
    """确保浏览器已启动（全局缓存，多次调用只启动一次）。"""
    global _playwright, _browser
    if _browser is not None:
        return True
    try:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True)
        return True
    except Exception as e:
        log_error("ensure_browser", f"浏览器启动失败: {e}")
        return False


async def create_page(viewport_size: dict | None = None):
    """
    从全局浏览器创建一个新页面（含代理配置）。

    每次调用返回独立 page，用完请调用方关闭。
    并发安全 —— 各请求使用不同 page 实例。

    Args:
        viewport_size: 可选视口尺寸，例如 {"width": 800, "height": 19200}。

    Returns:
        page | None
    """
    if not await ensure_browser():
        return None
    try:
        ctx_kwargs = {}
        proxy = get_http_proxy()
        if proxy:
            ctx_kwargs["proxy"] = {"server": proxy}
        context = await _browser.new_context(**ctx_kwargs)
        await load_cookie_file(context)
        page = await context.new_page()
        if viewport_size:
            await page.set_viewport_size(viewport_size)
        return page
    except Exception as e:
        log_error("create_page", f"页面创建失败: {e}")
        return None


async def create_browser_page(
    viewport_size: dict | None = None,
) -> tuple:
    """
    创建 Playwright 浏览器和页面实例（旧接口，保留兼容）。

    建议新代码直接用 ensure_browser() + create_page()。

    Args:
        viewport_size: 可选视口尺寸，例如 {"width": 800, "height": 19200}。

    Returns:
        (browser, page) 元组。失败时返回 (None, None)。
    """
    try:
        if not await ensure_browser():
            return None, None
        page = await create_page(viewport_size)
        if page is None:
            return None, None
        return _browser, page
    except Exception as e:
        log_error("create_browser_page", f"初始化失败: {e}")
        return None, None


async def _navigate_with_age_gate(
    page,
    url: str,
    wait_after_nav: float = 0,
    wait_after_age_gate: float = 0,
) -> bool:
    """
    导航到 URL 并处理 Steam 年龄验证。

    Args:
        page: Playwright page 实例。
        url: 目标 URL。
        wait_after_nav: 导航后额外等待时间（秒），用于页面渲染。
        wait_after_age_gate: 年龄验证后额外等待时间（秒）。

    Returns:
        True 表示成功，False 表示页面不存在/跳转失败。
    """
    print(f"[screenshot] 开始导航: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        log_error("_navigate_with_age_gate", f"页面跳转失败: {url} {e}")
        return False

    print("[screenshot] 导航完成")
    if wait_after_nav:
        await page.wait_for_timeout(wait_after_nav)

    try:
        title = await page.title()
        print(f"[screenshot] 页面标题: {title}")
        if title == "Welcome to Steam":
            return False

        if await page.query_selector('//a[@id="view_product_page_btn"]'):
            print("[screenshot] 年龄验证")
            await page.click('//select[@name="ageYear"]')
            await page.select_option('//select[@name="ageYear"]', '1900')
            await page.click('//a[@id="view_product_page_btn"]')
            if wait_after_age_gate:
                await page.wait_for_timeout(wait_after_age_gate)
    except Exception as e:
        log_error("_navigate_with_age_gate", f"页面处理异常: {url} {e}")
        return False

    return True


async def _screenshot_element(page, xpath: str) -> bytes | None:
    """截取页面中指定 XPath 元素的截图。"""
    try:
        return await page.locator(f'xpath={xpath}').screenshot()
    except PlaywrightTimeout:
        log_error("_screenshot_element", f"截图超时: {xpath}")
        return None
    except PlaywrightError as e:
        msg = e.message if hasattr(e, 'message') else str(e)
        log_error("_screenshot_element", f"截图失败: {msg}")
        return None


async def take_app_screenshot(appid: str) -> bytes | None:
    """
    Steam 游戏详情页截图（glance_ctn 区域）。

    自动处理年龄验证，失败/不存在返回 None。
    并发安全 —— 每次调用创建独立 page。
    """
    print(f"[screenshot] take_app_screenshot: appid={appid}")
    url = f"https://store.steampowered.com/app/{appid}/_/?l=schinese"
    if not await ensure_browser():
        return None
    page = await create_page()
    if not page:
        return None
    try:
        if not await _navigate_with_age_gate(page, url):
            return None
        print("[screenshot] 开始截图 glance_ctn")
        return await _screenshot_element(page, '//div[@class="glance_ctn"]')
    finally:
        await page.context.close()
        print("[screenshot] 页面已关闭")


async def take_publisher_screenshot(url: str) -> bytes | None:
    """
    Steam 发行商页面截图（RecommendationsRows 区域）。

    自动处理年龄验证，失败/无效返回 None。
    并发安全 —— 每次调用创建独立 page。
    """
    if not await ensure_browser():
        return None
    page = await create_page(viewport_size={"width": 800, "height": 19200})
    if not page:
        return None
    try:
        if not await _navigate_with_age_gate(page, url):
            return None
        return await _screenshot_element(page, '//div[@id="RecommendationsRows"]')
    finally:
        await page.context.close()
