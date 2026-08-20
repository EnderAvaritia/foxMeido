"""plugins/db - 统一数据库访问层

按 DB_BACKEND（sqlite | noco）分发到对应后端，对外暴露一致的结构化接口：

  get_record(table, where=None, sort="")   - 查询单条记录
  get_records(table, where=None, sort="")  - 查询记录列表
  create_record(table, payload)            - 新建记录
  update_record(table, record_id, payload) - 更新记录

table 为逻辑表名：account / records / remain / wishlist。
where 为 [(field, op, value), ...]，op ∈ {"eq", "gt", "ne"}，value=None 表示 NULL 判断。

示例：
  from plugins.db import get_record, create_record
  rec = get_record("account", [("account", "eq", "123456")])
"""

from . import config
from .config import BACKEND, SQLITE_PATH

if BACKEND == "sqlite":
    from .sqlite import (
        create_record,
        get_record,
        get_records,
        update_record,
    )
else:
    from .noco_backend import (
        create_record,
        get_record,
        get_records,
        update_record,
    )

__all__ = [
    "BACKEND",
    "SQLITE_PATH",
    "config",
    "get_record",
    "get_records",
    "create_record",
    "update_record",
]
