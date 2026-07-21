"""修复 curator DB：将所有非今天新入库的游戏 first_seen_at 重置"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
db = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data" / "db" / "curator_state.db"
conn = sqlite3.connect(str(db))

today = datetime.now(CST).strftime("%Y-%m-%d")
# 先看有多少今天是 first_seen_at 的
rows = conn.execute(
    "SELECT app_id, name, first_seen_at FROM seen_games WHERE date(first_seen_at) = ?",
    (today,),
).fetchall()

print(f"当前 first_seen_at 是今天的记录: {len(rows)} 条")
for r in rows[:5]:
    print(f"  {r[0]} - {r[1]} - {r[2]}")
if len(rows) > 5:
    print(f"  ... 及另外 {len(rows)-5} 条")

# 重置为过去时间
n = conn.execute(
    "UPDATE seen_games SET first_seen_at = '2000-01-01 00:00:00' WHERE date(first_seen_at) = ?",
    (today,),
).rowcount
conn.commit()
conn.close()
print(f"\n已重置 {n} 条记录为 2000-01-01")
