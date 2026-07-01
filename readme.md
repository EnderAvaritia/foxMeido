# foxMeido

基于 [NoneBot2](https://nonebot.dev/) 的 QQ 机器人，主要功能是查询 Steam 相关数据。

## 快速开始

### 安装依赖

```bash
pip install requests beautifulsoup4 playwright httpx lxml
playwright install chromium

# NoneBot 插件
nb plugin install nonebot-plugin-alconna
nb plugin install nonebot_plugin_apscheduler
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env`，配置 NapCat 连接信息。详见下方 [配置](#配置)。

### 运行

```bash
nb run
```

## 配置

所有配置通过 `.env` 文件设置（已 gitignore）。参考 `.env.example`。

### 必需（NapCat / OneBot V11）

通过 WebSocket 连接 [NapCat](https://github.com/NapNeko/NapCatQQ)（或其他 OneBot V11 实现），无需 QQ 开放平台凭证。

| 变量 | 说明 |
|------|------|
| `DRIVER` | NoneBot 驱动，必须包含 `~websockets` 以支持 ws 连接 |
| `ONEBOT_WS_URLS` | NapCat WebSocket 地址，格式 `["ws://ip:port"]` |
| `ONEBOT_API_ROOTS` | NapCat HTTP API 地址，格式 `{"bot_qq": "http://ip:port/"}` |
| `HOST` | 监听地址，默认 `127.0.0.1` |
| `PORT` | 监听端口 |
| `COMMAND_START` | 指令前缀，默认 `[""]`（无前缀） |

`.env` 示例：

```env
DRIVER=~httpx+~websockets
ONEBOT_API_ROOTS={"2326291391": "http://127.0.0.1:26657/"}
ONEBOT_WS_URLS=["ws://192.168.10.14:26657"]
HOST=127.0.0.1
PORT=26657
COMMAND_START=[""] 
```

### NocoDB（可选）

登记游戏领取记录的后端数据库。自行部署 [nocodb/nocodb](https://github.com/nocodb/nocodb)。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NOCO_URL` | `https://127.0.0.1:52533/api/v2/tables` | NocoDB API 地址 |
| `NOCO_TOKEN` | — | API Token（必填） |
| `NOCO_ACCOUNT_TABLE` | — | account 表格 ID |
| `NOCO_RECORD_TABLE` | — | record 表格 ID |
| `NOCO_REMAIN_TABLE` | — | remain 表格 ID |
| `NOCO_WISHLIST_TABLE` | — | wishlist 表格 ID |
| `NOCO_VERIFY_SSL` | `false` | 是否验证 SSL（国内自建通常用自签名证书，默认关闭） |

### 代理（可选）

国内访问 Steam / iflow 需要代理转发。只设 `HTTP_PROXY` 即可，`HTTPS_PROXY` 自动同步。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HTTP_PROXY` | — | 代理地址，如 `http://127.0.0.1:7890`。不设则不走代理 |
| `HTTPS_PROXY` | — | 跟随 `HTTP_PROXY`，通常无需单独设置 |

### Steam（可选）

| 变量 | 说明 |
|------|------|
| `STEAM_COOKIE` | Steam **商店页面** Cookie，`wish` 功能需要。从浏览器访问 store.steampowered.com → F12 → 复制请求头 `Cookie:` 整行。格式：`sessionid=xxx; steamLogin=xxx; ...` |
| `CURATOR_ID` | Steam 鉴赏家 ID（unreported 功能需要） |

### Playwright（可选）

Playwright 用于 Steam 页面截图（`steamGoods`、`pub` 等命令）。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PLAYWRIGHT_HEADLESS` | `true` | 无头模式。设为 `false` 可在调试时看到浏览器窗口 |
| `PLAYWRIGHT_COOKIE_FILE` | — | Playwright 格式的 Cookie 文件路径（JSON），用于登录态截图。参考 `data/cookies/steam_playwright.json.example` |

**获取 Playwright Cookie：**

```bash
python scripts/get_steam_cookies.py
```

弹出浏览器 → 手动登录 Steam → 回车 → cookie 自动写入 `data/cookies/steam_playwright.json`。然后在 `.env` 中添加：

```env
PLAYWRIGHT_COOKIE_FILE=data/cookies/steam_playwright.json
```

> Playwright 的 cookie 格式与 `STEAM_COOKIE`（requests 用）不通用，需要单独的文件。`STEAM_COOKIE` 用于 wish 命令，`PLAYWRIGHT_COOKIE_FILE` 用于截图功能。

### 鉴赏家副本监控（可选）

监控 Steam 鉴赏家后台的待处理游戏副本邀请，有新副本到达时通过 QQ 群消息（和/或 ntfy）推送通知。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CURATOR_COOKIE` | — | Steam **鉴赏家后台** Cookie（与商店 cookie 不同），必须包含 `sessionid` 和 `steamLoginSecure`。从浏览器访问 `store.steampowered.com/curator/{id}/admin` → F12 → 复制请求头 `Cookie:` |
| `CURATOR_ENABLED` | `false` | 是否启用每日定时检查 |
| `CURATOR_NAME` | `鉴赏家` | 鉴赏家显示名称 |
| `CURATOR_NOTIFY_GROUP` | — | 每日定时推送的目标群号 |
| `CURATOR_CHECK_TIME` | `09:00` | 每日定时检查时间 |
| `CURATOR_NTFY_TOPIC` | — | ntfy topic，设了则额外推送到手机 |

**命令：**

| 命令 | 说明 |
|------|------|
| `pending` | 手动触发一次检查，结果发送到当前群 |
| `pending test` | 发送测试推送（QQ 消息 + ntfy 如有配置） |

**日志输出：**

每次检查在后台输出一条日志，三种情况：

```
鉴赏家检查完成: 待处理 5, 游戏 7 款, 新增 2, 累计 7
最新: 霍格沃茨之遗             ← 有新增时
```

```
鉴赏家检查完成: 待处理 3, 游戏 3 款, 新增 0, 累计 7
无新增                          ← 有游戏但无变化
```

```
鉴赏家检查完成: 待处理 0, 游戏 0 款, 新增 0, 累计 7
探测结果为空                     ← Cookie 过期或页面抓取失败
```

`累计` 为 SQLite 中累积的唯一游戏总数（不会回缩）。出现**探测结果为空**请检查 `CURATOR_COOKIE` 是否过期。

### 消息表情回复（可选）

收到消息后立即添加 QQ 表情回应（如 ✅），类似 frontier 的 `send_group_message_reaction` 模式。仅 NapCat/OneBot V11 支持，不支持时自动忽略。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MESSAGE_REACTION_ENABLED` | `false` | 是否启用表情回复 |
| `MESSAGE_REACTION_FACE_ID` | `32` | QQ 表情 ID，详见常见 ID 表 |
| `MESSAGE_REACTION_AUTO_REMOVE` | `false` | 处理结束后是否自动撤回表情 |

**常见 QQ 表情 ID：**

| ID | 视觉 | 推荐场景 |
|----|------|---------|
| `32` | ✅ 对勾 | 安全通过 |
| `26` | ❌ 叉 | 拒绝/不通过 |
| `212` | 🤔 思考 | 处理中 |
| `351` | 👍 强 | 赞同/完成 |
| `324` | 👌 好的 | 收到/等待 |
| `319` | 🎉 庆祝 | 任务完成 |
| `0` | 😲 惊讶 | — |
| `14` | 🙂 微笑 | — |
| `13` | 😁 呲牙 | — |
| `67` | ❤️ 爱心 | — |
| `107` | ⭕ OK | — |
| `105` | 👍 爱你 | — |
| `101` | 🙏 抱拳 | — |
| `74` | 💩 便便 | — |

### 崩溃推送 ntfy（可选）

`log_crash()` 调用时会额外推送 ntfy 通知。可自建 ntfy 服务器。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CRASH_NTFY_SERVER` | `https://ntfy.sh` | ntfy 服务器地址 |
| `CRASH_NTFY_TOPIC` | — | ntfy topic，不设则不推送 |

### 自动拉取仓库更新（可选）

定时或手动执行 `git pull`，检测到新提交后自动重启机器人以加载新代码。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GIT_AUTO_PULL_ENABLED` | `false` | 是否启用自动检查 |
| `GIT_AUTO_PULL_INTERVAL` | `30` | 间隔模式：每 N 分钟检查一次 |
| `GIT_AUTO_PULL_TIME` | `06:00` | 定时模式：每天检查时间 |
| `GIT_AUTO_PULL_SCHEDULE_TYPE` | `both` | 调度类型：`cron` / `interval` / `both` |
| `GIT_AUTO_PULL_NOTIFY_GROUP` | — | 拉取结果通知的目标群号（可选） |
| `GIT_AUTO_PULL_REMOTE` | `origin` | 远程仓库名或 URL（如 `origin` 或 `https://github.com/user/repo.git`） |
| `GIT_AUTO_PULL_GIT_PATH` | `git` | git 可执行文件路径（绝对路径或仅文件名） |
| `GIT_AUTO_PULL_RESTART_CMD` | — | 自定义重启命令（如 `systemctl restart foxmeido`；不设则用 `os.execv` 原地替换） |
| `GIT_AUTO_PULL_BRANCH` | — | 目标分支（留空自动检测当前分支）

## 命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `id <appid/url>` | `steam` `查商店` `steamGoods` | 查询游戏详情（名称、厂商、发行日期、价格、截图） |
| `pub <publisher>` | `steamPublishers` | 查询发行商页面截图 |
| `find <关键字>` | `搜索steam游戏` | 交互式搜索 Steam 游戏 |
| `cs [最低价] [日销量]` | — | CS2 挂刀行情表 |
| `dota [最低价] [日销量]` | — | Dota2 挂刀行情表 |
| `pending` | — | 鉴赏家副本监控，手动触发检查 |
| `update` / `pull` | — | 手动触发 git pull，检测到更新后自动重启机器人 |
| `update force` | — | 强制拉取（丢弃本地未提交更改）后重启 |
| `help` | — | 显示帮助 |

Steam 商店链接会自动触发查询（如发送 `https://store.steampowered.com/app/3251240`）。

## 错误日志

运行中的异常自动写入 `logs/` 目录，每次错误一个时间戳文件。

- 文件格式：`error_<时间戳>.log` 或 `crash_<时间戳>.log`
- 内容：`[时间] [来源] 描述` + 异常堆栈

## 项目结构

```
foxMeido/
├── .env.example          # 配置模板
├── pyproject.toml        # NoneBot 项目配置
├── scripts/              # 工具脚本
│   └── get_steam_cookies.py  # 获取 Playwright 格式的 Steam cookie
├── data/                 # 运行时数据（gitignore）
│   ├── cookies/          #   Playwright cookie 文件
│   │   └── steam_playwright.json.example  #   cookie 格式模板
│   └── db/               #   SQLite 数据库文件
├── logs/                 # 错误日志（自动创建，gitignore）
└── plugins/
    ├── steam_utils.py    # Steam 通用工具
    ├── cs.py             # CS2 挂刀行情
    ├── curator_monitor.py# Steam 鉴赏家副本监控
    ├── dota.py           # Dota2 挂刀行情
    ├── finder.py         # 通用页面截图
    ├── help.py           # 帮助命令
    ├── ping.py           # 心跳测试
    ├── steamFinder.py    # Steam 游戏详情查询
    ├── steamFinderAuto.py# Steam 链接自动触发查询
    ├── steamPublisherFinder.py    # 发行商页面查询
    ├── steamPublisherFinderAuto.py# 发行商链接自动触发
    ├── steamSearcher.py  # Steam 游戏搜索
    ├── playwright_utils.py # 共享 Playwright 工具
    ├── auto_pull.py        # 自动拉取仓库更新（定时 + 手动命令）
    ├── message_reaction.py # 表情回复模块（核心函数 + 自动钩子）
    ├── error_logger.py     # 错误日志模块（全模块共用）
    └── noco/
        ├── __init__.py
        ├── noco_config.py       # 配置中心
        ├── noco_utils.py        # NocoDB 工具函数
        ├── bind.py / get.py / wish.py / ...
        └── README.md            # NocoDB 子模块文档
```