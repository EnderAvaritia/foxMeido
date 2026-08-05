# Steam 脚本集

`scripts/` 目录下的 Steam 相关工具脚本集合。

| 脚本 | 用途 |
|------|------|
| [steam_curator_views.py](#steam_curator_viewspy--鉴赏家评测浏览量) | 刷鉴赏家评测浏览量 |
| [steam_reviews.py](#steam_reviewspy--评测鉴赏家链接提取) | 提取用户评测中的鉴赏家链接，输出 CSV |
| [get_curator_cookies.py](#get_curator_cookiespy--获取鉴赏家后台-cookie) | 获取鉴赏家后台 Cookie（Playwright） |
| [get_steam_cookies.py](#get_steam_cookiespy--获取-steam-商店-cookie) | 获取 Steam 商店 Cookie（Playwright） |
| [fix_curator_db.py](#fix_curator_dbpy--修复鉴赏家数据库) | 修复鉴赏家数据库 |
| [Steam Store API 参考](#steam-store-api-参考) | 非官方 API `appdetails` 文档 |

## 安装

所有脚本共用同一份依赖：

```bash
pip install -r requirements.txt
```

> `get_curator_cookies.py` 和 `get_steam_cookies.py` 还需要 playwright：
> `pip install playwright && playwright install chromium`

---

## steam_curator_views.py — 鉴赏家评测浏览量

通过访问鉴赏家（Curator）推荐的游戏页面来提升组评浏览量：先拉取鉴赏家的推荐列表，再逐个访问每个推荐游戏的页面（带 `curator_clanid` 参数），模拟真实浏览行为。

### 用法

```bash
# 基本用法（--name 不传时自动从鉴赏家主页获取组名）
python steam_curator_views.py --clan-id 45519015 --cookie "<cookie>"

# 显式指定组名 + 代理 + 并发 + 限制数量 + 保存日志
python steam_curator_views.py --clan-id 45519015 --name "无趣评测" --cookie "<cookie>" \
    --proxy http://127.0.0.1:7890 --count 500 --threads 4 --log views.log

# 从断点继续
python steam_curator_views.py --clan-id 45519015 --cookie "<cookie>" \
    --start-appid 4209160
```

### 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `--clan-id` | 是 | 鉴赏家组的 ID（clan ID，纯数字，如 `45519015`） |
| `--name` | 否 | 鉴赏家组的名称（用于拼接 URL；留空则自动从鉴赏家主页获取） |
| `--cookie` | 是 | Steam Cookie 字符串（用于以登录身份访问） |
| `--proxy` | 否 | 代理地址，如 `http://127.0.0.1:7890` |
| `--count` | 否 | 每次拉取的组评数量（默认 `835`） |
| `--threads` | 否 | 同时执行的线程数（默认 `1`） |
| `--wait-min` | 否 | 每次访问之间的最小等待秒数（默认 `8`） |
| `--wait-max` | 否 | 每次访问之间的最大等待秒数（默认 `16`） |
| `--start-appid` | 否 | 从指定的 App ID 开始（断点续跑） |
| `--log FILE` | 否 | 日志文件路径（UTF-8 写入，不传则仅输出到控制台） |

### 工作原理

1. 若未传 `--name`，先访问 `store.steampowered.com/curator/{clan_id}/` 获取组名
2. 访问 Steam 主页确认登录状态（失败不中断）
3. 请求 `store.steampowered.com/curator/{clan_id}-{name}/ajaxgetfilteredrecommendations/` 拉取推荐列表，解析出全部 App ID
4. 使用线程池（`--threads`）并发访问每个游戏的详情页 `https://store.steampowered.com/app/{appid}/?curator_clanid={clan_id}` 以产生浏览量
5. 每个请求之间随机等待 `--wait-min` ~ `--wait-max` 秒，网络失败自动重试 3 次

> Steam 对鉴赏家组名采用 `^%^25XX` 转义（非 ASCII 字节），脚本会自动将 `--name` 编码为 URL 中的 slug 格式。

---

## steam_reviews.py — 评测鉴赏家链接提取

扫描 Steam 用户的评测页面，提取评测内容中包含的鉴赏家（Curator）超链接，输出为 CSV。

### 用法

```bash
# 基本用法
python steam_reviews.py EnderAvaritia

# 指定日期范围
python steam_reviews.py EnderAvaritia --since 2026-05-01 --until 2026-05-31

# 仅起始日期（到今日）
python steam_reviews.py EnderAvaritia --since 2026-05-01

# 仅结束日期
python steam_reviews.py EnderAvaritia --until 2025-12-31

# 带 Cookie + 代理
python steam_reviews.py EnderAvaritia --since 2026-01-01 --cookie "sessionid=xxx" --proxy http://127.0.0.1:7890
```

### 参数

| 参数 | 说明 |
|---|---|
| `steam_id` | Steam 自定义 URL、SteamID64 或完整 URL（如 `https://steamcommunity.com/id/xxx/recommended/`） |
| `--since` | 起始日期 YYYY-MM-DD，只抓此日期之后的评测 |
| `--until` | 结束日期 YYYY-MM-DD，只抓此日期之前的评测（含当日） |
| `--cookie` | Steam Cookie 字符串 |
| `--cookie-file FILE` | Cookie 文件路径（默认项目目录下的 cookie.txt） |
| `--proxy` | 代理地址，如 `http://127.0.0.1:7890` |
| `--list FILE` | 批量模式：文本文件，每行一个 Steam URL/ID |

### 批量模式

准备一个文本文件，每行一个 Steam 用户：

```
EnderAvaritia
https://steamcommunity.com/id/2802897529/recommended/
76561198836530221
```

```bash
python steam_reviews.py --list users.txt --since 2026-01-01 --cookie "..." --proxy http://127.0.0.1:7890
```

所有用户的结果写入同一个 CSV 文件 `batch_YYYY-MM-DD.csv`。

### Cookie 来源（优先级）

1. `--cookie` 命令行参数
2. `STEAM_COOKIE` 环境变量
3. `cookie.txt` 文件（项目目录下）

### 代理来源（优先级）

1. `--proxy` 命令行参数
2. `HTTPS_PROXY` / `HTTP_PROXY` 环境变量

### 输出

自动生成 CSV，文件名格式：`{steam_id}_{起始日期}_{结束日期}.csv`

每条记录包含：游戏名、App ID、评测时间、评测链接、鉴赏家链接、鉴赏家名称、组评

---

## get_curator_cookies.py — 获取鉴赏家后台 Cookie

获取 Playwright 格式的 Steam 鉴赏家后台 Cookie，保存到 `data/cookies/curator_playwright.json`。

> 鉴赏家后台 Cookie 与商店页面 Cookie 不同，需单独获取。

### 用法

```bash
python scripts/get_curator_cookies.py
```

### 流程

1. 输入鉴赏家 ID（CURATOR_ID，纯数字）
2. 输入鉴赏家名称（可选，用于 URL，直接回车跳过）
3. 弹出 Chromium 浏览器窗口，导航到 `store.steampowered.com`
4. 手动登录 Steam（如有需要）
5. 登录完成后，脚本自动跳转到鉴赏家后台页面（`curator/{id}/admin`），含重定向竞态处理
6. 确认后台页面正常加载后，回到终端按 Enter
7. 脚本自动保存 cookie 到 `data/cookies/curator_playwright.json`
8. 在 `.env` 中设置 `CURATOR_COOKIE_FILE` 和 `CURATOR_ID`（若填了名称还设置 `CURATOR_NAME`）

### 注意

- 需要已安装 playwright：`pip install playwright && playwright install chromium`
- cookie 包含 `steamLoginSecure`（登录态），请勿泄露此文件
- `data/cookies/` 已在 `.gitignore` 中，不会提交到仓库

---

## get_steam_cookies.py — 获取 Steam 商店 Cookie

获取 Playwright 格式的 Steam Cookie，保存到 `data/cookies/steam_playwright.json`。

### 用法

```bash
python scripts/get_steam_cookies.py
```

### 流程

1. 弹出 Chromium 浏览器窗口，导航到 `store.steampowered.com`
2. 手动登录 Steam（如有需要）
3. 登录完成后在终端按 Enter 继续
4. 脚本自动保存 cookie 到 `data/cookies/steam_playwright.json`
5. 在 `.env` 中设置 `PLAYWRIGHT_COOKIE_FILE=data/cookies/steam_playwright.json`

### 注意

- 需要已安装 playwright：`pip install playwright && playwright install chromium`
- cookie 包含 `steamLoginSecure`（登录态），请勿泄露此文件
- `data/cookies/` 已在 `.gitignore` 中，不会提交到仓库

---

## fix_curator_db.py — 修复鉴赏家数据库

修复 curator DB：将所有因迁移错误被标为今天 `first_seen_at` 的记录重置为 `2000-01-01`，避免误报今日新入库游戏。

> 在你跑 bot 的机器上执行（数据库在 `data/db/curator_state.db`）。

### 用法

```bash
python scripts/fix_curator_db.py
```

### 行为

- 检查 `first_seen_at` 为今天的记录数，为 0 则提示"无需修复"并退出
- 否则重置这些记录为 `2000-01-01 00:00:00`
- 下次运行 pending 时，今日新到游戏将只显示真正今天入库的

---

# Steam Store API 参考

机器人内部通过 Steam 非官方 API `store.steampowered.com/api/appdetails` 获取游戏信息。

## 端点

```
GET https://store.steampowered.com/api/appdetails
```

## 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `appids` | 是 | Steam App ID，多个用逗号分隔（如 `730,570`）。多 appid 时必须加 `&filters=price_overview`，否则返回 400 |
| `cc` | 否 | **国家/地区码**（ISO 3166-1），控制返回的货币和区域定价。如 `cn` → CNY、`us` → USD、`jp` → JPY、`hk` → HKD |
| `l` | 否 | **语言**，控制本地化文本。如 `schinese`（简体中文）、`english`、`japanese` |
| `filters` | 否 | 过滤返回字段，CSV 格式。如 `price_overview`（仅价格）、`basic`（基础信息） |

## 返回示例

```json
{
  "838350": {
    "success": true,
    "data": {
      "price_overview": {
        "currency": "CNY",
        "initial": 10800,
        "final": 10800,
        "discount_percent": 0,
        "final_formatted": "¥ 108.00"
      }
    }
  }
}
```

> 价格单位为**分**（cents），即 `10800` = ¥108.00。

## 注意事项

1. **Cookie 会覆盖 `cc` 参数**：在浏览器中直接访问时，`store.steampowered.com` 的已有 Cookie（如 `steamCountry`、`steamCurrency`）**优先级高于 `cc` 参数**。如果你登录了美区账号且当前窗口有对应 Cookie，即使加上 `&cc=cn` 仍可能返回 USD。解决方案：
   - **服务端调用**（推荐）：后端代码发请求，不带 Cookie
   - **隐私/无痕窗口**：无已有 Cookie，`cc` 正常生效
   - **fetch 时禁用凭据**：`fetch(url, { credentials: 'omit' })`

2. 本机器人的 `get_game_info()` 会自动读取 `.env` 中的 `STEAM_CC` 配置并附加到请求中，服务端调用不受浏览器 Cookie 影响。

3. **锁区降级**：如果设置了 `STEAM_CC` 但目标区返回 `success: false`（游戏在该区不可用），会自动降级到不带 `cc` 参数重新请求，确保能正常显示游戏信息。

4. **IP 地理围栏**：极少数区域（俄罗斯等）可能会基于出口 IP 覆盖 `cc` 参数，需配合对应区域的代理。

5. **速率限制**：约 200 请求 / 5 分钟 / IP，超出返回 429。

6. **非官方 API**：此为 Valve 内部接口，无稳定性保证，可能随时变更。

## 常用 `cc` 与货币对照

| cc | 货币 | 区域 |
|----|------|------|
| `us` | USD ($) | 美国 |
| `cn` | CNY (¥) | 中国 |
| `tw` | TWD (NT$) | 台湾 |
| `hk` | HKD (HK$) | 香港 |
| `jp` | JPY (¥) | 日本 |
| `kr` | KRW (₩) | 韩国 |
| `ru` | RUB (₽) | 俄罗斯 |
| `gb` | GBP (£) | 英国 |
| `de` / `fr` / `it` / `es` | EUR (€) | 欧洲 |
