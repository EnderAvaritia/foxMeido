"""
获取 Playwright 格式的 Steam 鉴赏家后台 Cookie，保存到 data/cookies/curator_playwright.json。

鉴赏家后台 Cookie 与商店页面 Cookie 不同，需单独获取。

使用方式：
    python scripts/get_curator_cookies.py

流程：
    1. 输入鉴赏家 ID（CURATOR_ID）
    2. 弹出 Chromium 浏览器窗口，导航到 store.steampowered.com
    3. 手动登录 Steam（如有需要）
    4. 登录完成后，脚本自动跳转到鉴赏家后台页面
    5. 确认后台页面正常加载后，回到终端按 Enter 继续
    6. 脚本自动保存 cookie 到 data/cookies/curator_playwright.json
    7. 在 .env 中设置 CURATOR_COOKIE_FILE 和 CURATOR_ID

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
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "curator_playwright.json")


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("错误：未安装 playwright。请运行：")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("Steam 鉴赏家后台 Playwright Cookie 获取工具")
    print("=" * 60)
    print()

    # ── 询问 CURATOR_ID ──────────────────────────────────────────
    curator_id = input("请输入鉴赏家 ID（CURATOR_ID，纯数字，如 12345678）: ").strip()
    while not curator_id.isdigit():
        print("  鉴赏家 ID 为纯数字，请重新输入")
        curator_id = input("请输入鉴赏家 ID: ").strip()

    curator_name = input("请输入鉴赏家名称（可选，用于 URL，直接回车跳过）: ").strip()

    # 构建鉴赏家后台地址
    if curator_name:
        from urllib.parse import quote
        name_encoded = quote(curator_name)
        curator_url = f"https://store.steampowered.com/curator/{curator_id}-{name_encoded}/admin"
    else:
        curator_url = f"https://store.steampowered.com/curator/{curator_id}/admin"

    print()
    print("1. 即将打开浏览器窗口，请登录 store.steampowered.com")
    print("2. 登录完成后，脚本将自动跳转到鉴赏家后台页面")
    print("3. 确认页面（pending 选项卡）正常加载后，回到此终端按 Enter")
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
        print("[playwright] 登录完成后，按 Enter 自动跳转到鉴赏家后台 ...")
        input()

        # ── 自动导航到鉴赏家后台 ──────────────────────────────────
        print(f"[playwright] 正在跳转到鉴赏家后台: {curator_url}")
        page.goto(curator_url, wait_until="domcontentloaded", timeout=30000)
        title = page.title()
        print(f"[playwright] 页面标题: {title}")

        # 过期检测
        title_lower = title.strip().lower()
        sign_in_keywords = {"sign in", "login", "welcome to steam"}
        is_login = any(k in title_lower for k in sign_in_keywords)
        if is_login or "login" in page.url.lower():
            print()
            print("⚠️  检测到登录页面，请确认是否已成功登录 Steam。")
            print("   如果已经登录，按 Enter 继续保存 cookie。")
            print("   如果未登录，请在浏览器中完成登录后按 Enter。")
            input()
            # 再试一次导航
            page.goto(curator_url, wait_until="domcontentloaded", timeout=30000)
            print(f"[playwright] 页面标题: {page.title()}")

        print()
        print(f"[playwright] 已导航到鉴赏家后台。请确认页面加载正常，然后按 Enter 保存 cookie ...")
        input()

        cookies = context.cookies()
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] 已保存 {len(cookies)} 个 cookie 到 {OUTPUT_FILE}")
        print()
        print("下一步：在 .env 中添加以下配置：")
        print(f'  CURATOR_COOKIE_FILE=data/cookies/curator_playwright.json')
        print(f'  CURATOR_ID={curator_id}')
        if curator_name:
            print(f'  CURATOR_NAME={curator_name}')
        print()
        print("（如果之前有 CURATOR_COOKIE，建议删掉，让 Playwright 方式接管）")
        print()

        browser.close()


if __name__ == "__main__":
    main()
