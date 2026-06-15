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
| `STEAM_COOKIE` | Steam 登录 Cookie，`wish` 功能需要。从浏览器 F12 → 网络请求 → 请求头中复制 `Cookie:` 整行。格式：`sessionid=xxx; steamLogin=xxx; steamLoginSecure=xxx; ...` |
| `CURATOR_ID` | Steam 鉴赏家 ID（unreported 功能需要） |

### 消息表情回复（可选）

收到消息后立即添加 QQ 表情回应（如 ✅），类似 frontier 的 `send_group_message_reaction` 模式。仅 NapCat/OneBot V11 支持，不支持时自动忽略。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MESSAGE_REACTION_ENABLED` | `false` | 是否启用表情回复 |
| `MESSAGE_REACTION_FACE_ID` | `32` | QQ 表情 ID。常用：`32`=✅ `212`=🤔 `26`=❌ `351`=👍 |

## 命令

| 命令 | 别名 | 说明 |
|------|------|------|
| `id <appid/url>` | `steam` `查商店` `steamGoods` | 查询游戏详情（名称、厂商、发行日期、价格、截图） |
| `pub <publisher>` | `steamPublishers` | 查询发行商页面截图 |
| `find <关键字>` | `搜索steam游戏` | 交互式搜索 Steam 游戏 |
| `cs [最低价] [日销量]` | — | CS2 挂刀行情表 |
| `dota [最低价] [日销量]` | — | Dota2 挂刀行情表 |
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
├── logs/                 # 错误日志（自动创建）
└── plugins/
    ├── steam_utils.py    # Steam 通用工具
    ├── cs.py             # CS2 挂刀行情
    ├── dota.py           # Dota2 挂刀行情
    ├── finder.py         # 通用页面截图
    ├── help.py           # 帮助命令
    ├── ping.py           # 心跳测试
    ├── steamFinder.py    # Steam 游戏详情查询
    ├── steamFinderAuto.py# Steam 链接自动触发查询
    ├── steamPublisherFinder.py    # 发行商页面查询
    ├── steamPublisherFinderAuto.py# 发行商链接自动触发
    ├── steamSearcher.py  # Steam 游戏搜索
    ├── reaction_utils.py   # 表情回复工具模块（send_reaction 核心函数）
    ├── message_reaction.py # 表情回复自动钩子（基于 reaction_utils）
    └── noco/
        ├── __init__.py
        ├── noco_config.py       # 配置中心
        ├── noco_utils.py        # NocoDB 工具函数
        ├── error_logger.py      # 错误日志模块
        ├── playwright_utils.py  # 共享 Playwright 工具
        ├── bind.py / get.py / wish.py / ...
        └── README.md            # NocoDB 子模块文档
```