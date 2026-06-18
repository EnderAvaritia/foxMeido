"""
playwright_utils.py - 共享 Playwright 工具

集中管理 Playwright 浏览器/页面创建逻辑，避免 5+ 个文件中重复 init_playwright。
各调用方自行管理模块级缓存，支持可选视口尺寸。

全局缓存 browser（浏览器进程），但每次截图创建新 page 以避免并发冲突。
"""

from __future__ import annotations

from playwright.async_api import async_playwright

from plugins.noco.noco_config import get_http_proxy
from plugins.noco.error_logger import log_error

# 全局浏览器实例（模块级缓存，只启动一次）
_playwright = None
_browser = None


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
        await context.add_cookies(cookies=[])
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
