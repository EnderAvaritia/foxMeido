"""
playwright_utils.py - 共享 Playwright 工具

集中管理 Playwright 浏览器/页面创建逻辑，避免 5+ 个文件中重复 init_playwright。
各调用方自行管理模块级缓存，支持可选视口尺寸。
"""

from __future__ import annotations

from playwright.async_api import async_playwright

from .noco_config import get_http_proxy
from .error_logger import log_error


async def create_browser_page(
    viewport_size: dict | None = None,
) -> tuple:
    """
    创建 Playwright 浏览器和页面实例。

    使用 noco_config 中的代理配置（HTTP_PROXY）创建上下文。
    调用方应自行缓存 browser/page 以实现复用。

    Args:
        viewport_size: 可选视口尺寸，例如 {"width": 800, "height": 19200}。

    Returns:
        (browser, page) 元组。失败时返回 (None, None)。
    """
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        # 仅当配置了代理时才传递 proxy 参数
        ctx_kwargs = {}
    proxy = get_http_proxy()
    if proxy:
        ctx_kwargs["proxy"] = {"server": proxy}
        context = await browser.new_context(**ctx_kwargs)
        await context.add_cookies(cookies=[])
        page = await context.new_page()
        if viewport_size:
            await page.set_viewport_size(viewport_size)
        return browser, page
    except Exception as e:
        log_error("create_browser_page", f"Playwright 初始化失败: {e}")
        return None, None
