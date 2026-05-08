"""
unfinished.py - 输出record表中未完成的内容

功能：
1. 查询record表中submitTime为null的记录
2. 按userId排序
3. 按用户分组输出未完成的游戏
4. 输出格式：{username}未完成{gameName}：{getTime}

使用前需要配置：
1. 将recordTableId替换为实际的record表格ID
2. 将token替换为实际的NocoDB token
"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import requests
import json

# NocoDB配置
nocoUrl = "https://127.0.0.1:52533/api/v2/tables"
recordTableId = "tableId"  # TODO: 需要替换为实际的record表格ID

token = "token"  # TODO: 需要替换为实际的token
headers = {"xc-token": token}

# unfinished指令
unfinished = on_command("unfinished", aliases={"unfinished"}, priority=10, block=True)

def get_unfinished_records():
    """获取submitTime为null的记录"""
    # 构建查询参数：where=(submitTime,eq,null)&sort=userId
    table_filter = "where=(submitTime,eq,null)&sort=userId"
    record_table_url = f"{nocoUrl}/{recordTableId}/records?{table_filter}"
    
    try:
        response = requests.get(record_table_url, headers=headers, verify=False)
        response.raise_for_status()
        
        json_string = response.text
        data = json.loads(json_string)
        
        return data
    except requests.exceptions.RequestException as e:
        return {"error": f"请求失败: {e}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        return {"error": f"未知错误: {e}"}

def format_unfinished_output(records_data):
    """格式化未完成记录的输出"""
    if "error" in records_data:
        return f"获取记录失败: {records_data['error']}"
    
    if "list" not in records_data or not records_data["list"]:
        return "没有找到未完成的记录"
    
    records = records_data["list"]
    
    # 按userName分组
    user_records = {}
    for record in records:
        user_name = record.get("userName", "未知用户")
        game_name = record.get("gameName", "未知游戏")
        get_time = record.get("getTime", "未知时间")
        
        if user_name not in user_records:
            user_records[user_name] = []
        
        user_records[user_name].append({
            "gameName": game_name,
            "getTime": get_time
        })
    
    # 构建输出
    output_lines = []
    for user_name, games in user_records.items():
        # 输出用户标题
        output_lines.append(f"用户{user_name}未完成：")
        # 输出该用户的每个游戏
        for game_info in games:
            output_lines.append(f"{game_info['gameName']}：{game_info['getTime']}")
        # 添加空行分隔不同用户
        output_lines.append("")
    
    # 添加统计信息
    page_info = records_data.get("pageInfo", {})
    total_rows = page_info.get("totalRows", len(records))
    output_lines.append(f"共找到 {total_rows} 条未完成记录")
    
    return "\r\n".join(output_lines)

@unfinished.handle()
async def handle_function(event: MessageEvent, args: Message = CommandArg()):
    """处理unfinished指令"""
    # 获取参数（可选参数，如是否显示所有记录）
    arg_text = args.extract_plain_text().strip()
    show_all = arg_text.lower() == "all" if arg_text else False
    
    await unfinished.send("正在查询未完成的记录...")
    
    # 获取未完成的记录
    records_data = get_unfinished_records()
    
    # 格式化输出
    output = format_unfinished_output(records_data)
    
    await unfinished.finish(output)