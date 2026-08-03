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
import time

# 确保能在项目根目录执行
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
os.chdir(_PROJECT_ROOT)

OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "data", "cookies")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "curator_playwright.json")


def goto_curator(page, url: str, attempts: int = 3) -> bool:
    """
    导航到鉴赏家后台，处理 Playwright 的『导航被另一导航打断』竞态问题。

    Steam 登录后页面可能仍在重定向（如跳转 steamcommunity.com），此时
    page.goto 会因另一导航正在进行而抛异常（Navigation is interrupted）。
    这里通过重试 + 最终 URL 校验来保证最终落在目标页面。

    Args:
        page: Playwright sync Page 实例。
        url: 目标 URL（鉴赏家后台地址）。
        attempts: 最多尝试次数。

    Returns:
        True 表示成功（最终 URL 在目标页），False 表示失败（需用户手动处理）。
    """
    expected_prefix = url.split("?")[0].rstrip("/")
    for attempt in range(1, attempts + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            if attempt == attempts:
                print(f"[playwright] 自动跳转失败（{type(e).__name__}），"
                      f"当前页面: {page.url}")
                return False
            print(f"[playwright] 页面重定向打断了跳转，"
                  f"{2 * attempt} 秒后重试（第 {attempt + 1}/{attempts} 次）...")
            time.sleep(2 * attempt)
            continue

        # 跳转成功，但需校验最终是否落在目标页（可能被服务端重定向走）
        final_url = page.url.rstrip("/")
        if final_url.startswith(expected_prefix):
            return True

        print(f"[playwright] 跳转后落在其他页面: {final_url}")
        if attempt == attempts:
            return False
        time.sleep(2 * attempt)

    return False


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

        # 登录后页面可能仍在重定向（跳转 steamcommunity.com 等），
        # 先等网络安静，减少 goto 被其他导航打断的概率（等不到也属正常）
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        # ── 自动导航到鉴赏家后台 ──────────────────────────────────
        print(f"[playwright] 正在跳转到鉴赏家后台: {curator_url}")
        if not goto_curator(page, curator_url):
            print()
            print("[playwright] 自动跳转被页面重定向打断，请手动在浏览器中打开：")
            print(f"  {curator_url}")
            print("[playwright] 打开并确认页面正常后，按 Enter 继续 ...")
            input()
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
            if not goto_curator(page, curator_url):
                print("[playwright] 自动跳转失败，请手动在浏览器中打开目标页面后按 Enter 继续 ...")
                input()
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
