# plugins/db 说明

数据库抽象层：sqlite / noco 双后端指令 + 统一访问接口。

## 目录结构

```
plugins/db/
├── __init__.py       # 抽象层：DatabaseBackend 接口 + get_backend() 工厂（按 DB_BACKEND 分发）
├── base.py           # DatabaseBackend 抽象基类（两个后端共用的接口定义）
├── config.py         # 配置中心（原 noco_config.py，含 DB_BACKEND / SQLITE_PATH）
├── sqlite.py         # SqliteBackend 指令（SQLite 后端：结构化 where → SQL）
├── noco_backend.py   # NocoBackend 指令（NocoDB 后端：结构化 where → NocoDB 语法）
└── createTables.sql  # 4 张表的结构参考（sqlite 后端自动建表同源）
```

> 命令插件（bind / get / wish / remain / probe / report / unfinished / unreported / queryWishlist / calendar）
> 已移出到 `plugins/` 根目录，与 cs / dota / help 等其他命令插件平级，
> 通过本抽象层的 `get_backend()` 访问数据库。

## 统一接口（抽象层）

sqlite 与 noco 各自实现为独立后端指令（`SqliteBackend` / `NocoBackend`），
都继承 `DatabaseBackend` 抽象基类。命令插件通过 `get_backend()` 获取当前配置的后端实例，
只依赖抽象接口，不感知具体后端：

```python
from plugins.db import get_backend
from plugins.db import config as cfg

backend = get_backend()  # DB_BACKEND=sqlite → SqliteBackend，DB_BACKEND=noco → NocoBackend

# where: [(field, op, value), ...]，op ∈ {eq, gt, ne}，value=None 表示 NULL 判断
rec = backend.get_record("account", [("account", "eq", "123456")])
rows = backend.get_records("remain", [("canBeClaimed", "gt", 0)], sort="created_at")
rec = backend.create_record("wishlist", {...})
rec = backend.update_record("records", 42, {"report": 1})
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
