# plugins/noco 重构说明

## 改了什么

### 问题

原来每个脚本（bind.py / get.py / wish.py / remain.py / probe.py / report.py / unfinished.py / unreported.py / queryWishlist.py）里都硬编码了 NocoDB 的连接信息：

```python
nocoUrl = "https://127.0.0.1:52533/api/v2/tables"
accountTableId = "tableId"   # placeholder
token = "token"              # placeholder
proxies = {"http": "...", "https": "..."}
```

改配置要改 9 个文件，很麻烦。而且 `getGameInfo()` 函数在 `get.py`、`remain.py`、`wish.py` 里各有几乎一样的实现，一份改动要同步三处。

### 方案

新增两个共享模块，所有脚本改为从它们导入：

```
plugins/noco/
├── __init__.py         # 包标记
├── noco_config.py      # 配置中心（从环境变量读取）
├── noco_utils.py       # 工具函数（get_record / get_game_info 等）
├── bind.py             # ↓ 以下脚本都改成了 from . import noco_config / noco_utils
├── calendar.py
├── get.py
├── ...
```

---

## noco_config.py — 配置中心

所有常量通过**环境变量**读取，默认值可以在 `.env` 文件中覆盖（`.env` 已在 `.gitignore` 中，不会提交到仓库）。

### 完整配置项

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `NOCO_URL` | NocoDB API 地址 | `https://127.0.0.1:52533/api/v2/tables` |
| `NOCO_TOKEN` | API Token | `""`（必填） |
| `NOCO_ACCOUNT_TABLE` | account 表格 ID | `""`（必填） |
| `NOCO_RECORD_TABLE` | records 表格 ID | `""`（必填） |
| `NOCO_REMAIN_TABLE` | remain 表格 ID | `""`（必填） |
| `NOCO_WISHLIST_TABLE` | wishlist 表格 ID | `""`（必填） |
| `NOCO_VERIFY_SSL` | 是否验证 SSL | `false` |
| `HTTP_PROXY` | HTTP 代理 | `http://127.0.0.1:7890` |
| `HTTPS_PROXY` | HTTPS 代理 | `http://127.0.0.1:7890` |
| `STEAM_COOKIE` | Steam 登录 Cookie（wish 用） | `""` |
| `CURATOR_ID` | Steam 鉴赏家 ID（unreported 用） | `0` |

### 示例 .env 配置

```env
# ── NocoDB ──
NOCO_TOKEN=your_nocodb_token_here
NOCO_ACCOUNT_TABLE=mtab_xxxxx
NOCO_RECORD_TABLE=mtab_xxxxx
NOCO_REMAIN_TABLE=mtab_xxxxx
NOCO_WISHLIST_TABLE=mtab_xxxxx

# ── 代理（可选，默认使用 7890） ──
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890

# ── Steam（可选） ──
STEAM_COOKIE=your_steam_cookie
CURATOR_ID=12345
```

### 辅助函数

config 还提供了几个便捷函数：

- `cfg.table_url(table_id)` → 拼接完整 API URL（`{NOCO_URL}/{table_id}/records`）
- `cfg.url_with_filter(table_id, where, sort="")` → 拼接带过滤条件的查询 URL
- `cfg.request_kwargs()` / `cfg.post_kwargs()` → 返回共用的 requests 参数字典（含 headers、verify 等）

---

## noco_utils.py — 工具函数

消除了原来散落在各文件中的重复代码：

### 公共函数

| 函数 | 说明 | 原重复位置 |
|---|---|---|
| `get_record(url)` | 查询单条记录（list ≤ 1 场景） | bind / get / remain / wish |
| `get_records(url)` | 通用查询，返回完整响应 | probe / report / unfinished / unreported / queryWishlist |
| `create_record(url, payload)` | 创建记录 | bind / get / remain / wish |
| `update_record(url, payload)` | PATCH 更新记录 | bind / get / remain / wish / report / probe |
| `get_game_info(appid)` | 通过 Steam API 获取游戏名称 + 厂商 + 发行日期 | **get.py / remain.py / wish.py（3 份合并为 1 份）** |
| `extract_steam_id(text)` | 从文本/URL 提取 Steam AppID | 分散在各脚本中的重复 re.findall 逻辑 |

---

## 改动的文件一览

| 文件 | 删减行数 | 主要变化 |
|---|---|---|
| `bind.py` | -70 行 | 移除硬编码常量、getRecord / createRecord / updateRecord |
| `get.py` | -130 行 | 同上 + 移除 getGameInfo（用 utils 的） |
| `wish.py` | -135 行 | 同上 + 移除 getGameInfo |
| `remain.py` | -200 行 | 同上 |
| `probe.py` | -100 行 | 移除 NocoDB 常量和重复的 requests 逻辑 |
| `report.py` | -120 行 | 同上 |
| `unfinished.py` | -55 行 | 同上 |
| `unreported.py` | -65 行 | 同上 |
| `queryWishlist.py` | -55 行 | 同上 |
| `calendar.py` | 1 行 | 代理地址改从 cfg 读取 |
| `noco_config.py` | **新增** | 配置中心 |
| `noco_utils.py` | **新增** | 工具函数 |
| `__init__.py` | **新增** | 包标记 |

总删除了约 **1443 行**，新增了 **674 行**。

---

## 修复的小问题

- **calendar.py** 中 `from playwright.async_api import Error as PWError` 导入别名和 catch 块用的 `PlaywrightError` 不一致，现已统一
- **wish.py** 中如果 `goodId` 未匹配到，原来 `await wish.send(...)` 后继续执行会报错，改为 `await wish.finish(...)`

---

## 后续可优化的方向

1. **plugins/ 下其他文件** — `steamFinder.py`、`steamFinderAuto.py`、`steamPublisherFinder.py` 等也有类似的 Steam API 调用，可以和 `noco_utils.get_game_info` 合并
2. **类型提示** — 现有脚本大量使用 `dict[str, Any]` 而非具体类型，后续可以为 NocoDB 返回数据定义 TypedDict 或数据类
3. **HTTP 会话复用** — 目前每次请求创建新连接，可以用 `requests.Session()` 做连接复用
4. **错误处理** — `get_record` 返回 `dict | str` 的 union 类型，调用方需要手动检查，后续可以改用异常或更严格的返回类型
