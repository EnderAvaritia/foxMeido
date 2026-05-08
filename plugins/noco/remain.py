"""
remain.py - 剩余游戏登记和查询插件

功能：
1. 使用 remain 指令登记剩余的游戏份数
2. 使用 remain 指令查询游戏的当前领取情况
3. 指令格式：
   - remain 游戏ID/URL 份数 （登记或更新份数）
   - remain 游戏ID/URL （查询当前领取情况）
4. 示例：
   - remain 730 5 （登记CS:GO 5份）
   - remain https://store.steampowered.com/app/730 5 （通过URL登记CS:GO 5份）
   - remain 730 （查询CS:GO当前领取情况）
   - remain https://store.steampowered.com/app/730 （通过URL查询当前领取情况）

表格字段：
- gameId: 游戏ID（Steam AppID）
- gameName: 游戏名称（通过Steam API自动获取）
- totalCount: 总份数（通过指令参数设置）
- getedCount: 已领取份数（初始为0）

使用前需要配置：
1. 将 remainTableId 替换为实际的remain表格ID
2. 将 token 替换为实际的NocoDB token
3. 确保已创建remain表格（参考createTables.sql）

注意：
- 如果游戏已存在记录，会累加份数
- 如果游戏不存在记录，会创建新记录
- 游戏名称通过Steam API自动获取
- 支持从Steam商店URL中自动提取游戏ID
- 查询功能不需要游戏名称，即使Steam API不可用也能查询
"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

import datetime
import requests
import json
import re

# 代理配置（如果需要）
proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

# NocoDB配置
nocoUrl = "https://127.0.0.1:52533/api/v2/tables"

remainTableId = "tableId"  # TODO: 需要替换为实际的remain表格ID（从NocoDB中获取）

token = "token"  # TODO: 需要替换为实际的token（从NocoDB中获取）
headers = {"xc-token": token}

# remain指令
remain = on_command("remain", aliases={"remain"}, priority=10, block=True)

def getRecord(url):
    """获取记录"""
    response = requests.get(url, headers=headers)
    # response = requests.get(url, headers=headers, verify=False)
    
    json_string = response.text
    data = json.loads(json_string)
    
    if data['list'] == []:
        return ""
    else:
        return data['list'][0]  # 返回第一条记录

def createRecord(url, gameId, gameName, totalCount, getedCount=0):
    """创建剩余游戏记录"""
    payload = {
        "gameId": gameId,
        "gameName": gameName,
        "totalCount": totalCount,
        "getedCount": getedCount
    }
    
    headers = {
        'Content-Type': "application/json",
        'xc-token': token
    }
    
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    # response = requests.post(url, data=json.dumps(payload), headers=headers, verify=False)
    
    json_string = response.text
    data = json.loads(json_string)
    
    return data

def updateRecord(url, gameId, gameName, totalCount, getedCount, recordId):
    """更新剩余游戏记录"""
    payload = {
        "id": recordId,
        "gameId": gameId,
        "gameName": gameName,
        "totalCount": totalCount,
        "getedCount": getedCount
    }
    
    headers = {
        'Content-Type': "application/json",
        'xc-token': token
    }
    
    response = requests.patch(url, data=json.dumps(payload), headers=headers)
    # response = requests.patch(url, data=json.dumps(payload), headers=headers, verify=False)
    
    json_string = response.text
    data = json.loads(json_string)
    
    return data

def getGameInfo(appid: int):
    """
    根据Steam AppID，通过Steam Web API获取游戏的名称。
    参照steamFinderAuto.py中的getGameInfo函数

    Args:
        appid (int): Steam游戏的AppID。

    Returns:
        dict: 包含游戏名称的字典。
              例如：{"game_name": "Half-Life 2"}
              如果获取失败，会包含 "error" 键。
    """
    game_name = None
    errors = []

    # 通过Steam Web API 获取游戏名称
    api_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese"
    print(f"正在请求API接口: {api_url}")

    try:
        response = requests.get(api_url, proxies=proxies)
        response.raise_for_status()  # 检查HTTP状态码，如果不是200则抛出异常

        data = response.json()
        app_data = data.get(str(appid))  # API响应中AppID是字符串键

        if app_data and app_data.get('success'):
            details = app_data.get('data')
            if details:
                # 获取游戏名称
                game_name = details.get('name')
                if game_name:
                    print(f"获取到游戏名称: {game_name}")
                else:
                    errors.append(f"API返回数据中未找到'name'信息 (AppID: {appid})")
                    print(errors[-1])
            else:
                errors.append(f"API返回数据中未找到'data'详情 (AppID: {appid})")
                print(errors[-1])
        else:
            errors.append(f"API返回成功状态为false或数据为空 (AppID: {appid})。可能AppID不存在或不可用。")
            print(errors[-1])

    except requests.exceptions.RequestException as e:
        errors.append(f"请求API接口时发生网络错误或HTTP错误: {e}")
        print(errors[-1])
    except json.JSONDecodeError as e:
        errors.append(f"解析API响应JSON时发生错误: {e}")
        print(errors[-1])
    except Exception as e:
        errors.append(f"处理API响应时发生未知错误: {e}")
        print(errors[-1])

    result = {
        "game_name": game_name
    }
    if errors:
        result["error"] = "; ".join(errors)
    
    return result

@remain.handle()
async def handle_function(event: MessageEvent, args: Message = CommandArg()):
    """处理remain指令"""
    # 解析参数
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await remain.finish("请输入游戏ID/URL和份数，格式：remain 游戏ID/URL 份数\n或输入游戏ID/URL查询当前领取情况")
    
    # 分割参数
    parts = arg_text.split()
    
    # 提取游戏ID（支持纯数字ID或URL）
    game_input = parts[0]
    
    # 尝试从URL中提取游戏ID（类似wish.py中的处理方式）
    game_id_match = re.findall(r"(?<=app/)(\d+)|(\d{5,11})", game_input)
    
    if game_id_match:
        # 清除元组中的空结果
        game_id = tuple(item for item in game_id_match[0] if item)[0]
    else:
        # 如果不是URL，检查是否是纯数字
        if re.match(r'^\d+$', game_input):
            game_id = game_input
        else:
            await remain.finish("未检测到有效的游戏ID，请提供Steam游戏ID或Steam商店链接")
    
    # 检查是否已存在该游戏的记录
    tableFilter = f"where=(gameId,eq,{game_id})"
    remainTableUrl = f"{nocoUrl}/{remainTableId}/records?{tableFilter}"
    existing_record = getRecord(remainTableUrl)
    
    if len(parts) == 1:
        # 只有一个参数：查询当前领取情况
        if "id" in existing_record:
            # 游戏已登记，显示当前状态
            remaining = existing_record["totalCount"] - existing_record["getedCount"]
            await remain.finish(
                f"游戏《{existing_record['gameName']}》(ID: {game_id}) 当前领取情况：\n"
                f"总份数: {existing_record['totalCount']}\n"
                f"已领取份数: {existing_record['getedCount']}\n"
                f"剩余可领取: {remaining}\n"
                f"记录ID: {existing_record['id']}"
            )
        else:
            # 游戏未登记
            # 获取游戏信息用于显示名称
            game_info = getGameInfo(game_id)
            if "error" in game_info:
                game_name = f"ID: {game_id}"
            else:
                game_name = game_info.get("game_name", f"ID: {game_id}")
            
            await remain.finish(f"游戏《{game_name}》(ID: {game_id}) 尚未登记剩余份数")
    
    elif len(parts) >= 2:
        # 两个参数：登记或更新份数
        try:
            count = int(parts[1])
            if count <= 0:
                await remain.finish("份数必须大于0")
        except ValueError:
            await remain.finish("份数必须是整数")
        
        # 获取游戏信息
        game_info = getGameInfo(game_id)
        
        if "error" in game_info:
            await remain.finish(f"游戏{game_id}数据获取出错：{game_info['error']}")
        
        if not game_info["game_name"]:
            await remain.finish(f"无法获取游戏{game_id}的名称，请检查游戏ID是否正确")
        
        if "id" in existing_record:
            # 更新现有记录
            remainTableUrl = f"{nocoUrl}/{remainTableId}/records"
            # new_total_count = existing_record["totalCount"] + count
            new_total_count = count
            update_result = updateRecord(
                remainTableUrl, 
                game_id, 
                game_info["game_name"], 
                new_total_count, 
                existing_record["getedCount"], 
                existing_record["id"]
            )
            
            if "id" in update_result:
                await remain.finish(
                    f"游戏《{game_info['game_name']}》(ID: {game_id}) 的剩余份数已更新\n"
                    f"原总份数: {existing_record['totalCount']}\n"
                    # f"新增份数: {count}\n"
                    f"现总份数: {new_total_count}\n"
                    f"已领取份数: {existing_record['getedCount']}\n"
                    f"剩余可领取: {new_total_count - existing_record['getedCount']}"
                )
            else:
                await remain.finish("更新记录失败，请检查网络或配置")
        else:
            # 创建新记录
            remainTableUrl = f"{nocoUrl}/{remainTableId}/records"
            create_result = createRecord(
                remainTableUrl, 
                game_id, 
                game_info["game_name"], 
                count, 
                0  # 初始已领取份数为0
            )
            
            if "id" in create_result:
                await remain.finish(
                    f"游戏《{game_info['game_name']}》(ID: {game_id}) 已成功登记\n"
                    f"总份数: {count}\n"
                    f"已领取份数: 0\n"
                    f"剩余可领取: {count}\n"
                    f"记录ID: {create_result['id']}"
                )
            else:
                await remain.finish("创建记录失败，请检查网络或配置")
    else:
        await remain.finish("请输入游戏ID/URL和份数，格式：remain 游戏ID/URL 份数\n或输入游戏ID/URL查询当前领取情况")