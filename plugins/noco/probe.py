"""
probe.py - 检测record表中的link是否有效

功能：
1. 查询record表中submitTime为null的记录
2. 对每个记录的link进行请求
3. 检查响应标题是否包含"评测"或"Review"
4. 如果成功，更新submitTime为当前日期
5. 输出完成检测的用户和游戏列表

输出格式：
{userName}完成了：
{gameName}
{gameName}
...

使用前需要配置：
1. 将recordTableId替换为实际的record表格ID
2. 将token替换为实际的NocoDB token
"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import datetime
import requests
import json
import re
import time

# NocoDB配置
nocoUrl = "https://127.0.0.1:52533/api/v2/tables"
recordTableId = "tableId"  # TODO: 需要替换为实际的record表格ID

token = "token"  # TODO: 需要替换为实际的token
headers = {"xc-token": token}

# 代理配置（如果需要）
proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

# probe指令
probe = on_command("probe", aliases={"probe"}, priority=10, block=True)

def get_records_with_null_submitTime():
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

def check_link_valid(link):
    """检查链接是否有效，标题是否包含'评测'或'Review'"""
    try:
        # 设置请求头，模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 发送请求
        response = requests.get(link, headers=headers, timeout=10, proxies=proxies, verify=False)
        response.raise_for_status()
        
        # 检查响应内容
        content = response.text
        
        # 检查标题是否包含"评测"或"Review"
        # 查找<title>标签
        title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            # 检查是否包含关键词
            if "评测" in title or "Review" in title:
                return True, title
            else:
                return False, title
        else:
            return False, "未找到标题标签"
                
    except requests.exceptions.RequestException as e:
        return False, f"请求失败: {e}"
    except Exception as e:
        return False, f"检查失败: {e}"

def update_record_submitTime(record_id):
    """更新记录的submitTime为当前日期"""
    current_date = datetime.date.today().strftime('%Y-%m-%d')
    
    update_url = f"{nocoUrl}/{recordTableId}/records"
    
    payload = {
        "id": record_id,
        "submitTime": current_date
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

def format_output(completed_records):
    """格式化输出结果"""
    if not completed_records:
        return "本次检测没有发现新的完成记录"
    
    # 按userName分组
    user_records = {}
    for record in completed_records:
        user_name = record.get("userName", "未知用户")
        game_name = record.get("gameName", "未知游戏")
        link = record.get("Link", "未知链接")
        
        if user_name not in user_records:
            user_records[user_name] = []
        
        user_records[user_name].append({
            "game_name": game_name,
            "link": link
        })
    
    # 构建输出
    output_lines = []
    for user_name, records in user_records.items():
        output_lines.append(f"{user_name}完成了：")
        for record_info in records:
            output_lines.append(f"{record_info['game_name']}")
            output_lines.append(f"{record_info['link']}")
        output_lines.append("")  # 空一行分隔不同用户
    
    return "\r\n".join(output_lines)

@probe.handle()
async def handle_function(event: MessageEvent, args: Message = CommandArg()):
    """处理probe指令"""
    # 获取参数（可选参数，如是否强制检测所有记录）
    arg_text = args.extract_plain_text().strip()
    force_check = arg_text.lower() == "force" if arg_text else False
    
    await probe.send("开始检测record表中的link有效性...")
    
    # 获取需要检测的记录
    records_data = get_records_with_null_submitTime()
    
    if "error" in records_data:
        await probe.finish(f"获取记录失败: {records_data['error']}")
    
    if "list" not in records_data or not records_data["list"]:
        await probe.finish("没有找到submitTime为null的记录")
    
    records = records_data["list"]
    total_records = len(records)
    page_info = records_data.get("pageInfo", {})
    total_rows = page_info.get("totalRows", total_records)
    
    await probe.send(f"找到 {total_rows} 条需要检测的记录（本次处理 {total_records} 条）")
    
    # 检测记录
    completed_records = []
    checked_count = 0
    success_count = 0
    
    for record in records:
        checked_count += 1
        
        record_id = record.get("id")
        link = record.get("Link")
        user_name = record.get("userName", "未知用户")
        game_name = record.get("gameName", "未知游戏")
        
        if not link:
            # 没有link的记录，静默跳过
            continue
        
        # 检查链接有效性
        is_valid, message = check_link_valid(link)
        
        if is_valid:
            # 更新submitTime
            update_result = update_record_submitTime(record_id)
            
            if "error" not in update_result:
                success_count += 1
                completed_records.append(record)
            # 检测成功但更新失败的情况，静默处理
        
        # 避免请求过于频繁
        time.sleep(1)
    
    # 格式化输出结果
    output = format_output(completed_records)
    
    # 添加统计信息
    stats = f"\r\n\r\n检测完成！\r\n共检测 {checked_count} 条记录\r\n成功更新 {success_count} 条记录"
    
    await probe.finish(output + stats)