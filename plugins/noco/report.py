"""
report.py - 更新record表中指定游戏的report字段

功能：
1. 使用 report 指令更新指定游戏的report字段为1
2. 指令格式：report 游戏ID 或 report Steam链接
3. 示例：
   - report 730 （将CS:GO的所有记录标记为已报告）
   - report 570 （将Dota 2的所有记录标记为已报告）
   - report https://store.steampowered.com/app/730/ （从Steam链接提取游戏ID并标记为已报告）
   - report https://store.steampowered.com/app/570 （从Steam链接提取游戏ID并标记为已报告）

工作原理：
1. 从输入中提取游戏ID（支持纯数字ID和Steam链接）
2. 查询record表中指定gameId且report为0的记录
3. 将查询到的所有记录的report字段更新为1
4. 输出更新结果统计

使用前需要配置：
1. 将recordTableId替换为实际的record表格ID
2. 将token替换为实际的NocoDB token
3. 确保已创建records表格（参考createTables.sql）

注意：
- 只更新report为0的记录，避免重复更新
- 支持批量更新同一游戏的所有未报告记录
- 输出更新成功的记录数量和详细信息
- 支持从Steam商店链接自动提取游戏ID
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

# report指令
report = on_command("report", aliases={"report"}, priority=10, block=True)

def get_unreported_records_by_game(game_id):
    """
    获取指定游戏ID且report为0的记录
    
    Args:
        game_id: 游戏ID
        
    Returns:
        dict: 包含记录列表的响应数据，或包含错误信息的字典
    """
    # 构建查询参数：where=(gameId,eq,{gameId})~and(report,eq,0)
    table_filter = f"where=(gameId,eq,{game_id})~and(report,eq,0)"
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

def update_record_report(record_id):
    """
    更新单条记录的report字段为1
    
    Args:
        record_id: 记录ID
        
    Returns:
        dict: 更新结果，包含更新后的记录信息或错误信息
    """
    update_url = f"{nocoUrl}/{recordTableId}/records"
    
    payload = {
        "id": record_id,
        "report": 1
    }
    
    headers = {
        'Content-Type': "application/json",
        'xc-token': token
    }
    
    try:
        response = requests.patch(update_url, data=json.dumps(payload), headers=headers, verify=False)
        response.raise_for_status()
        
        json_string = response.text
        data = json.loads(json_string)
        
        return data
    except requests.exceptions.RequestException as e:
        return {"error": f"更新失败: {e}"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        return {"error": f"未知错误: {e}"}

def batch_update_records(records):
    """
    批量更新多条记录的report字段
    
    Args:
        records: 记录列表
        
    Returns:
        tuple: (成功数量, 失败数量, 详细信息列表)
    """
    success_count = 0
    fail_count = 0
    details = []
    
    for record in records:
        record_id = record.get("id")
        user_name = record.get("userName", "未知用户")
        game_name = record.get("gameName", "未知游戏")
        
        # 更新记录
        update_result = update_record_report(record_id)
        
        if "error" in update_result:
            fail_count += 1
            details.append(f"❌ {user_name} - {game_name}: 更新失败 ({update_result['error']})")
        else:
            success_count += 1
            details.append(f"✅ {user_name} - {game_name}: 已标记为已报告")
    
    return success_count, fail_count, details

def extract_game_id_from_input(input_text):
    """
    从输入中提取游戏ID，支持以下格式：
    1. 纯数字ID：730, 570
    2. Steam链接：https://store.steampowered.com/app/730/
    3. Steam链接：https://store.steampowered.com/app/730
    4. Steam链接：store.steampowered.com/app/730/
    
    Args:
        input_text: 用户输入
        
    Returns:
        str: 提取到的游戏ID，如果提取失败返回None
    """
    # 如果是纯数字，直接返回
    if input_text.isdigit():
        return input_text
    
    # 尝试从Steam链接中提取游戏ID
    # 匹配模式：app/后面跟着数字
    pattern = r"(?<=app/)(\d+)|(\d{5,11})"
    matches = re.findall(pattern, input_text)
    
    if matches:
        # re.findall返回元组列表，需要提取非空的部分
        for match in matches:
            # match是元组，如 ('730', '') 或 ('', '730')
            for item in match:
                if item:  # 找到非空的部分
                    return item
    
    return None

@report.handle()
async def handle_function(event: MessageEvent, args: Message = CommandArg()):
    """处理report指令"""
    # 解析参数
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await report.finish("请输入游戏ID或Steam链接，格式：report 游戏ID 或 report https://store.steampowered.com/app/730/")
    
    # 提取游戏ID
    game_id = extract_game_id_from_input(arg_text)
    
    if not game_id:
        await report.finish("无法识别游戏ID，请提供纯数字ID或Steam商店链接")
    
    await report.send(f"正在查询游戏ID为 {game_id} 的未报告记录...")
    
    # 获取未报告记录
    records_data = get_unreported_records_by_game(game_id)
    
    if "error" in records_data:
        await report.finish(f"查询失败: {records_data['error']}")
    
    if "list" not in records_data or not records_data["list"]:
        await report.finish(f"游戏ID {game_id} 没有找到未报告（report=0）的记录")
    
    records = records_data["list"]
    total_records = len(records)
    
    # 获取游戏名称（从第一条记录中获取）
    game_name = records[0].get("gameName", f"ID: {game_id}")
    
    await report.send(f"找到 {total_records} 条未报告记录，游戏：{game_name}")
    await report.send("开始更新report字段为1...")
    
    # 批量更新记录
    success_count, fail_count, details = batch_update_records(records)
    
    # 构建输出
    output_lines = []
    output_lines.append(f"游戏《{game_name}》(ID: {game_id}) 报告状态更新完成：")
    output_lines.append(f"总记录数: {total_records}")
    output_lines.append(f"成功更新: {success_count}")
    output_lines.append(f"更新失败: {fail_count}")
    output_lines.append("")
    output_lines.append("详细信息：")
    output_lines.extend(details)
    
    await report.finish("\r\n".join(output_lines))