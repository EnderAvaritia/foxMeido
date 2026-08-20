"""数据库双向迁移工具：在 NocoDB 与 SQLite 之间迁移 foxMeido 数据。

在你跑 bot 的机器上执行（需要已安装 requests）：

    # NocoDB → SQLite（默认方向，推荐换 sqlite 后端时使用）
    python scripts/migrate_db.py --from noco --to sqlite

    # SQLite → NocoDB（回迁）
    python scripts/migrate_db.py --from sqlite --to noco

行为：
  - 遍历 4 张表：account / records / remain / wishlist
  - noco 侧按 limit/offset 翻页读取（现有 get_records 只读第一页，脚本内完整翻页）
  - noco → sqlite：保留原 id 与系统列（created_at 等），sqlite 表不存在则自动创建
  - sqlite → noco：noco 的 id 与系统列（nc_order 等）由 noco 自动生成，无法保留，脚本会提示
  - 迁移不影响 bot 正常运行

配置：从 .env 读取（NOCO_URL / NOCO_TOKEN / NOCO_*_TABLE / SQLITE_PATH / NOCO_VERIFY_SSL）。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

import requests

# 找项目根目录（脚本在 scripts/ 下），加入 sys.path 以便导入 plugins
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from plugins.env_utils import _read_dotenv  # noqa: E402
from plugins.db.sqlite import TABLE_SCHEMAS, TABLE_DDL  # noqa: E402

TABLES: list[str] = list(TABLE_SCHEMAS.keys())

# noco 自动管理、不可由客户端写入的字段
_NOCO_MANAGED_FIELDS = ("id", "nc_order", "created_at", "updated_at", "created_by", "updated_by")

_PAGE_SIZE = 100


# ── 配置 ──────────────────────────────────────────────────────────
def load_noco_config() -> dict[str, str]:
    """从 .env 读取 NocoDB 配置。"""
    return {
        "url": _read_dotenv("NOCO_URL") or "https://127.0.0.1:52533/api/v2/tables",
        "token": _read_dotenv("NOCO_TOKEN") or "",
        "tables": {
            "account": _read_dotenv("NOCO_ACCOUNT_TABLE") or "",
            "records": _read_dotenv("NOCO_RECORD_TABLE") or "",
            "remain": _read_dotenv("NOCO_REMAIN_TABLE") or "",
            "wishlist": _read_dotenv("NOCO_WISHLIST_TABLE") or "",
        },
        "verify_ssl": (_read_dotenv("NOCO_VERIFY_SSL") or "false").lower()
        in ("true", "1", "yes"),
    }


def load_sqlite_config() -> str:
    """从 .env 读取 SQLite 路径（默认 data/db/foxmeido.db）。"""
    return _read_dotenv("SQLITE_PATH") or os.path.join(
        _PROJECT_ROOT, "data", "db", "foxmeido.db"
    )


# ── NocoDB 侧 ────────────────────────────────────────────────────
def noco_request(method: str, url: str, cfg: dict, payload: dict | None = None) -> dict:
    """发 NocoDB API 请求，失败时抛异常。"""
    headers = {"xc-token": cfg["token"]}
    kwargs: dict = {"headers": headers}
    if not cfg["verify_ssl"]:
        kwargs["verify"] = False
    if payload is not None:
        kwargs["json"] = payload
    resp = requests.request(method, url, **kwargs)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"响应格式异常: {type(data).__name__}")
    if "error" in data:
        raise RuntimeError(str(data["error"]))
    return data


def fetch_noco_table(cfg: dict, table: str) -> list[dict]:
    """翻页读取 noco 指定表的全部记录。"""
    table_id = cfg["tables"][table]
    base = f"{cfg['url']}/{table_id}/records"
    rows: list[dict] = []
    offset = 0
    while True:
        url = f"{base}?limit={_PAGE_SIZE}&offset={offset}"
        data = noco_request("GET", url, cfg)
        page = data.get("list", [])
        rows.extend(page)
        if len(page) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return rows


# ── SQLite 侧 ────────────────────────────────────────────────────
def get_sqlite_conn(db_path: str) -> sqlite3.Connection:
    """连接 sqlite 并确保 4 张表存在。"""
    parent = os.path.dirname(db_path)
    os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    for ddl in TABLE_DDL.values():
        conn.execute(ddl)
    conn.commit()
    return conn


# ── 迁移方向 ─────────────────────────────────────────────────────
def migrate_noco_to_sqlite() -> None:
    """NocoDB → SQLite：保留 id 与系统列。"""
    cfg = load_noco_config()
    db_path = load_sqlite_config()
    if not cfg["token"]:
        print("❌ 未配置 NOCO_TOKEN，无法从 NocoDB 读取")
        sys.exit(1)
    print(f"源: NocoDB ({cfg['url']})")
    print(f"目标: SQLite ({db_path})")
    conn = get_sqlite_conn(db_path)
    try:
        for table in TABLES:
            if not cfg["tables"][table]:
                print(f"⚠️  跳过 {table}: 未配置 NOCO_{table.upper()}_TABLE")
                continue
            print(f"读取 {table} ...")
            rows = fetch_noco_table(cfg, table)
            cols = TABLE_SCHEMAS[table]
            if not rows:
                print(f"  {table}: 0 条，跳过")
                continue
            for row in rows:
                data = {k: row[k] for k in cols if k in row}
                placeholders = ", ".join("?" for _ in data)
                conn.execute(
                    f'INSERT OR REPLACE INTO "{table}" '
                    f'({", ".join(data.keys())}) VALUES ({placeholders})',
                    list(data.values()),
                )
            conn.commit()
            print(f"  ✅ {table}: 迁移 {len(rows)} 条（保留原 id 与系统列）")
    finally:
        conn.close()
    print("🎉 迁移完成：NocoDB → SQLite")


def migrate_sqlite_to_noco() -> None:
    """SQLite → NocoDB：id 与系统列由 noco 自动生成。"""
    cfg = load_noco_config()
    db_path = load_sqlite_config()
    if not cfg["token"]:
        print("❌ 未配置 NOCO_TOKEN，无法写入 NocoDB")
        sys.exit(1)
    if not os.path.isfile(db_path):
        print(f"❌ SQLite 数据库不存在: {db_path}")
        sys.exit(1)
    print(f"源: SQLite ({db_path})")
    print(f"目标: NocoDB ({cfg['url']})")
    conn = get_sqlite_conn(db_path)
    try:
        for table in TABLES:
            if not cfg["tables"][table]:
                print(f"⚠️  跳过 {table}: 未配置 NOCO_{table.upper()}_TABLE")
                continue
            base = f"{cfg['url']}/{cfg['tables'][table]}/records"
            rows = [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"').fetchall()]
            if not rows:
                print(f"  {table}: 0 条，跳过")
                continue
            count = 0
            for row in rows:
                payload = {k: v for k, v in row.items() if k not in _NOCO_MANAGED_FIELDS}
                noco_request("POST", base, cfg, payload)
                count += 1
            print(f"  ✅ {table}: 迁移 {count} 条（id 与系统列由 NocoDB 重新生成）")
    finally:
        conn.close()
    print("🎉 迁移完成：SQLite → NocoDB")
    print("⚠️ 注意：NocoDB 端的记录 id 已重新生成，不影响 bot 内部使用")


def main() -> None:
    parser = argparse.ArgumentParser(description="foxMeido 数据库双向迁移工具")
    parser.add_argument("--from", dest="src", choices=["noco", "sqlite"], required=True)
    parser.add_argument("--to", dest="dst", choices=["noco", "sqlite"], required=True)
    args = parser.parse_args()

    if args.src == args.dst:
        print("❌ 源和目标不能相同")
        sys.exit(1)
    if args.src == "noco" and args.dst == "sqlite":
        migrate_noco_to_sqlite()
    else:
        migrate_sqlite_to_noco()


if __name__ == "__main__":
    main()
