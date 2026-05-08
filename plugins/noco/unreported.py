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
import re

# NocoDB配置
nocoUrl = "https://127.0.0.1:52533/api/v2/tables"
recordTableId = "tableId"  # TODO: 需要替换为实际的record表格ID

token = "token"  # TODO: 需要替换为实际的token
headers = {"xc-token": token}

curatorId = 0

# unreported指令
unreported = on_command("unreported", aliases={"unreported"}, priority=10, block=True)

def get_unreported_records_by_game_id(game_id=None):
    """获取report为0的记录，可指定gameId"""
    if game_id:
        # 如果指定了gameId，只查询该游戏的记录
        table_filter = f"where=(report,eq,0)~and(gameId,eq,{game_id})&sort=gameId"
    else:
        # 如果没有指定gameId，查询所有记录
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
        submit_time = record.get("submitTime")
        
        if game_name not in game_records:
            game_records[game_name] = []
        
        game_records[game_name].append({
            "game_id": game_id,
            "user_name": user_name,
            "link": link,
            "submit_time": submit_time
        })
    
    # 构建输出
    output_lines = []
    for game_name, records in game_records.items():
        # 输出游戏标题
        output_lines.append(f"{game_name}:")
        # 输出游戏商店链接（每个游戏只输出一次）
        if records:
            output_lines.append(f"https://store.steampowered.com/app/{records[0]['game_id']}/?curator_clanid={curatorId}")
        # 输出该游戏的每个用户和链接（或未完成状态）
        for record_info in records:
            output_lines.append(f"{record_info['user_name']}")
            # 检查submitTime是否为null
            if record_info['submit_time'] is None:
                output_lines.append("未完成")
            else:
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
    # 获取参数
    arg_text = args.extract_plain_text().strip()
    
    game_id = None
    if arg_text:
        # 尝试从输入中提取gameId
        # 支持直接输入数字ID或Steam链接
        game_id_match = re.findall(r"(?<=app/)(\d+)|(\d{5,11})", arg_text)
        
        if game_id_match:
            # 提取第一个匹配的非空组
            game_id = tuple(item for item in game_id_match[0] if item)[0]
        else:
            # 如果正则没匹配到，尝试直接使用输入内容作为gameId
            if re.match(r'^\d+$', arg_text):
                game_id = arg_text
            else:
                await unreported.finish("请输入有效的游戏ID或Steam商店链接")
    
    if game_id:
        await unreported.send(f"正在查询游戏ID {game_id} 的未报告（report=0）记录...")
    else:
        await unreported.send("正在查询所有未报告（report=0）的记录...")
    
    # 获取未报告的记录
    records_data = get_unreported_records_by_game_id(game_id)
    
    # 格式化输出
    output = format_unreported_output(records_data)
    
    await unreported.finish(output)