# Steam 评测鉴赏家链接提取

扫描 Steam 用户的评测页面，提取评测内容中包含的鉴赏家（Curator）超链接，输出为 CSV。

## 用法

```bash
# 安装依赖
pip install -r requirements.txt

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

## 参数

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

## Cookie 来源（优先级）

1. `--cookie` 命令行参数
2. `STEAM_COOKIE` 环境变量
3. `cookie.txt` 文件（项目目录下）

## 代理来源（优先级）

1. `--proxy` 命令行参数
2. `HTTPS_PROXY` / `HTTP_PROXY` 环境变量

## 输出

自动生成 CSV，文件名格式：`{steam_id}_{起始日期}_{结束日期}.csv`

每条记录包含：游戏名、App ID、评测时间、评测链接、鉴赏家链接、鉴赏家名称、组评
