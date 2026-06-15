"""
message_reaction.py - 消息表情回复自动钩子

收到群消息后自动添加表情回复（如 ✅）。
核心逻辑委托给 reaction_utils，此文件只负责注册消息事件。

配置（.env）：
    MESSAGE_REACTION_ENABLED  - 是否启用（默认 false）
    MESSAGE_REACTION_FACE_ID  - QQ 表情 ID（默认 32=✅）

手动调用（其他插件中）：
    from plugins.reaction_utils import send_reaction, remove_reaction
    await send_reaction(bot, group_id=..., message_id=..., face_id="351")
"""

from nonebot import on_message

from plugins.reaction_utils import (
    extract_group_id,
    extract_message_id,
    get_reaction_config,
    send_reaction,
)

# priority=1 先于所有命令处理器（priority=10）运行
# block=False 不阻止消息继续传递到下层处理器
reaction_handler = on_message(priority=1, block=False)


@reaction_handler.handle()
async def handle_message_reaction(bot, event):
    """收到群消息后立即添加表情回复。"""
    enabled, face_id = get_reaction_config()
    if not enabled:
        return

    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id is None or message_id is None:
        return

    await send_reaction(bot, group_id=group_id, message_id=message_id, face_id=face_id)
