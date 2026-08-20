# plugins/db/noco 说明

## 目录结构

```
plugins/db/
├── __init__.py       # 统一数据库访问层（对外接口，按 DB_BACKEND 分发）
├── config.py         # 配置中心（原 noco_config.py，含 DB_BACKEND / SQLITE_PATH）
├── sqlite.py         # SQLite 后端实现（结构化 where → SQL）
├── noco_backend.py   # NocoDB 后端实现（结构化 where → NocoDB 语法）
└── noco/             # 命令插件（本目录）
    ├── bind.py / get.py / wish.py / remain.py / probe.py
    ├── report.py / unfinished.py / unreported.py / queryWishlist.py
    ├── calendar.py
    └── createTables.sql   # 4 张表的结构参考（sqlite 后端自动建表同源）
```

## 统一接口

所有命令插件都通过 `plugins.db` 的统一接口访问数据，不再直接操作 NocoDB API：

```python
from plugins.db import get_record, get_records, create_record, update_record
from plugins.db import config as cfg

# where: [(field, op, value), ...]，op ∈ {eq, gt, ne}，value=None 表示 NULL 判断
rec = get_record("account", [("account", "eq", "123456")])
rows = get_records("remain", [("canBeClaimed", "gt", 0)], sort="created_at")
rec = create_record("wishlist", {...})
rec = update_record("records", 42, {"report": 1})
```

逻辑表名：`account` / `records` / `remain` / `wishlist`。
返回约定保持不变：查询为空返回 `""`，失败返回 `{"error": ...}`，列表返回 `{"list": [...], "pageInfo": {"totalRows": n}}`。

## 后端切换（.env）

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `DB_BACKEND` | 后端选择：`sqlite` / `noco` | 智能默认（检测到 `NOCO_TOKEN` → `noco`，否则 `sqlite`） |
| `SQLITE_PATH` | sqlite 数据库文件路径 | `data/db/foxmeido.db` |
| `NOCO_URL` | NocoDB API 地址 | `https://127.0.0.1:52533/api/v2/tables` |
| `NOCO_TOKEN` | API Token | `""` |
| `NOCO_ACCOUNT_TABLE` / `NOCO_RECORD_TABLE` / `NOCO_REMAIN_TABLE` / `NOCO_WISHLIST_TABLE` | 表格 ID（仅 noco 后端） | `""` |
| `NOCO_VERIFY_SSL` | 是否验证 SSL | `false` |
| `NOCO_CHECK_REMAIN` | `get` 指令是否检查 remain 剩余份数 | `true` |
| `HTTP_PROXY` / `HTTPS_PROXY` | 代理（calendar / wish / probe 用） | `""` |
| `STEAM_COOKIE` / `STEAM_CC` | Steam 配置（wish / steam_utils 用） | `""` |
| `CURATOR_ID` | 鉴赏家 ID（unreported 用） | `0` |

## 后端迁移

```bash
python scripts/migrate_db.py --from noco --to sqlite   # NocoDB → SQLite
python scripts/migrate_db.py --from sqlite --to noco   # SQLite → NocoDB
```
