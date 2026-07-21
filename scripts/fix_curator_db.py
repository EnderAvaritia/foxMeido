"""修复 curator DB：将所有因迁移错误被标为今天 first_seen_at 的记录重置。

在你跑 bot 的机器上执行：
    python scripts/fix_curator_db.py
"""
import sqlite3
import os
import sys
from datetime import datetime, timezone, timedelta

# 找项目根目录（脚本在 scripts/ 下）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "db", "curator_state.db")

if not os.path.isfile(DB_PATH):
    print(f"❌ 数据库不存在: {DB_PATH}")
    sys.exit(1)

CST = timezone(timedelta(hours=8))
today = datetime.now(CST).strftime("%Y-%m-%d")

conn = sqlite3.connect(DB_PATH)

# 查看受影响记录数
before = conn.execute(
    "SELECT count(*) FROM seen_games WHERE date(first_seen_at) = ?", (today,),
).fetchone()[0]
print(f"当前 first_seen_at 是 {today} 的记录: {before} 条")

if before == 0:
    print("✅ 无需修复")
    conn.close()
    sys.exit(0)

# 重置为过去时间（今天新入库的游戏也会被重置，但已在"新增"中通知过，可接受）
n = conn.execute(
    "UPDATE seen_games SET first_seen_at = '2000-01-01 00:00:00' "
    "WHERE date(first_seen_at) = ?",
    (today,),
).rowcount
conn.commit()
conn.close()
print(f"已重置 {n} 条记录为 2000-01-01")
print("下次运行 pending 时，今日新到游戏将只显示真正今天入库的。")
