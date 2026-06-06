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

编辑 `.env`，至少需要配置 QQ 机器人凭证。详见下方 [配置](#配置)。

### 运行

```bash
nb run
```

## 配置

所有配置通过 `.env` 文件设置（已 gitignore）。参考 `.env.example`。

### 必需

| 变量 | 说明 |
|------|------|
| `QQ_BOTS` | QQ 机器人凭证（BOT_APP_ID / BOT_TOKEN / BOT_SECRET），在 [QQ 开放平台](https://q.qq.com/) 创建应用获取 |
| `COMMAND_START` | 指令前缀，默认 `["#"]` |

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
| `STEAM_COOKIE` | Steam 登录 Cookie（wish 功能需要） |
| `CURATOR_ID` | Steam 鉴赏家 ID（unreported 功能需要） |

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

运行中的异常自动写入 `logs/error.log`（项目根目录），同时打印到控制台。

- 轮转：5MB × 3 份
- 格式：`[时间] [ERROR] [来源] 错误描述`

## 项目结构

```
foxMeido/
├── .env.example          # 配置模板
├── pyproject.toml        # NoneBot 项目配置
├── logs/                 # 错误日志（自动创建）
└── plugins/
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
    └── noco/
        ├── __init__.py
        ├── noco_config.py       # 配置中心
        ├── noco_utils.py        # 共享工具函数
        ├── error_logger.py      # 错误日志模块
        ├── playwright_utils.py  # 共享 Playwright 工具
        ├── bind.py / get.py / wish.py / ...
        └── README.md            # NocoDB 子模块文档
```