"""
获取 Playwright 格式的 Steam cookie，保存到 data/cookies/steam_playwright.json。

使用方式：
    python scripts/get_steam_cookies.py

流程：
    1. 弹出 Chromium 浏览器窗口，导航到 store.steampowered.com
    2. 手动登录 Steam（如有需要）
    3. 登录完成后在终端按 Enter 继续
    4. 脚本自动保存 cookie 到 data/cookies/steam_playwright.json
    5. 在 .env 中设置 PLAYWRIGHT_COOKIE_FILE=data/cookies/steam_playwright.json

注意：
    - 需要已安装 playwright：pip install playwright && playwright install chromium
    - cookie 包含 steamLoginSecure（登录态），请勿泄露此文件
    - data/cookies/ 已在 .gitignore 中，不会提交到仓库
"""

import json
import os
import sys

# 确保能在项目根目录执行
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
os.chdir(_PROJECT_ROOT)

OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "data", "cookies")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "steam_playwright.json")


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误：未安装 playwright。请运行：")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("Steam Playwright Cookie 获取工具")
    print("=" * 60)
    print()
    print("1. 即将打开浏览器窗口，请登录 store.steampowered.com")
    print("2. 登录完成后，回到此终端按 Enter 继续")
    print("3. 脚本会自动保存 cookie 到 data/cookies/steam_playwright.json")
    print()
    print("按 Enter 打开浏览器...")
    input()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("[playwright] 正在导航到 store.steampowered.com ...")
        page.goto("https://store.steampowered.com/")
        print("[playwright] 页面已加载，请在浏览器中完成登录。")
        print("[playwright] 登录完成后，回到此终端按 Enter 保存 cookie ...")
        input()

        cookies = context.cookies()
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] 已保存 {len(cookies)} 个 cookie 到 {OUTPUT_FILE}")
        print()
        print("下一步：在 .env 中添加以下配置：")
        print(f'  PLAYWRIGHT_COOKIE_FILE=data/cookies/steam_playwright.json')
        print()
        print("验证：重启 bot 后查看日志，应有 '[playwright] 已加载 N 个 cookie' 输出。")

        browser.close()


if __name__ == "__main__":
    main()
