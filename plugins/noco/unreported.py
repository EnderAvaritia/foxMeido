"""
unreported.py - 输出record表中report为0的项目

功能：
1. 查询record表中report为0的记录
2. 按gameId排序
3. 按游戏分组输出用户
4. 输出格式：{gameName}:\r\n{userName}\r\n{userName}\r\n

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

curatorId = 0

# unreported指令
unreported = on_command("unreported", aliases={"unreported"}, priority=10, block=True)

def get_unreported_records():
    """获取report为0的记录"""
    # 构建查询参数：where=(report,eq,0)&sort=gameId
    table_filter = "where=(report,eq,0)&sort=gameId"
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

def format_unreported_output(records_data):
    """格式化未报告记录的输出"""
    if "error" in records_data:
        return f"获取记录失败: {records_data['error']}"
    
    if "list" not in records_data or not records_data["list"]:
        return "没有找到report为0的记录"
    
    records = records_data["list"]
    
    # 按gameName分组
    game_records = {}
    for record in records:
        game_id = record.get("gameId", "未知游戏ID")
        game_name = record.get("gameName", "未知游戏")
        user_name = record.get("userName", "未知用户")
        link = record.get("Link", "未知链接")
        
        if game_name not in game_records:
            game_records[game_name] = []
        
        game_records[game_name].append({
            "game_id": game_id,
            "user_name": user_name,
            "link": link
        })
    
    # 构建输出
    output_lines = []
    for game_name, records in game_records.items():
        # 输出游戏标题
        output_lines.append(f"{game_name}:")
        # 输出该游戏的每个用户和链接
        for record_info in records:
            output_lines.append(f"https://store.steampowered.com/app/{record_info['game_id']}/?curator_clanid={curatorId}")
            output_lines.append(f"{record_info['user_name']}")
            output_lines.append(f"{record_info['link']}")
        output_lines.append("")  # 空一行分隔不同游戏
    
    # 添加统计信息
    page_info = records_data.get("pageInfo", {})
    total_rows = page_info.get("totalRows", len(records))
    output_lines.append(f"共找到 {total_rows} 条未报告记录")
    
    return "\r\n".join(output_lines)

@unreported.handle()
async def handle_function(event: MessageEvent, args: Message = CommandArg()):
    """处理unreported指令"""
    # 获取参数（可选参数，如是否显示所有记录）
    arg_text = args.extract_plain_text().strip()
    show_all = arg_text.lower() == "all" if arg_text else False
    
    await unreported.send("正在查询未报告（report=0）的记录...")
    
    # 获取未报告的记录
    records_data = get_unreported_records()
    
    # 格式化输出
    output = format_unreported_output(records_data)
    
    await unreported.finish(output)