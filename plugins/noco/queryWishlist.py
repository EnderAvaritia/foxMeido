from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
# from nonebot.adapters.qq import MessageSegment

import datetime
import requests
import json
import re

nocoUrl = "https://127.0.0.1:52533/api/v2/tables"

wishlistTableId = "tableId"

token = "token"
headers = {"xc-token": token}

# queryWishlist = on_command("queryWishlist", rule=to_me(), aliases={"queryWishlist"}, priority=10, block=True)
queryWishlist = on_command("queryWishlist", aliases={"queryWishlist"}, priority=10, block=True)

def query_wishlist_by_gameid(game_id: str):
    """
    根据gameId查询wishlist表格
    :param game_id: 游戏ID
    :return: 查询结果JSON数据
    """
    # 构建查询参数
    table_filter = f"where=(gameId,eq,{game_id})&sort=submitTime"
    wishlist_table_url = f"{nocoUrl}/{wishlistTableId}/records?{table_filter}"
    
    try:
        response = requests.get(wishlist_table_url, headers=headers, verify=False)
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

def format_wishlist_response(data: dict) -> str:
    """
    格式化wishlist查询结果
    :param data: 查询结果JSON数据
    :return: 格式化后的字符串
    """
    if "error" in data:
        return f"查询失败: {data['error']}"
    
    if "list" not in data or not data["list"]:
        return "未找到相关许愿记录"
    
    # 获取游戏名称（从第一条记录中获取，因为查询的是同一个游戏）
    game_name = data["list"][0].get("gameName", "未知游戏")
    
    result_lines = []
    # 最开头加上《{gameName}》之后空一行
    result_lines.append(f"《{game_name}》")
    result_lines.append("")  # 空一行
    
    for index, item in enumerate(data["list"], start=1):
        # 格式化输出内容为“{userName}在{submitTime}第{index}个请求\r\n”
        # 注意：这里的index是list中的索引（从1开始），不是数据库中的id
        line = f"{item.get('userName', '未知用户')}在{item.get('submitTime', '未知时间')}第{index}个请求"
        result_lines.append(line)
    
    # 添加分隔线和统计信息
    page_info = data.get("pageInfo", {})
    total_rows = page_info.get("totalRows", 0)
    
    formatted_result = "\r\n".join(result_lines)
    formatted_result += f"\r\n\r\n共找到 {total_rows} 条记录"
    
    return formatted_result

@queryWishlist.handle()
async def handle_function(event: MessageEvent, args: Message = CommandArg()):
    """
    处理queryWishlist命令
    """
    # 获取用户输入的游戏ID
    input_text = args.extract_plain_text().strip()
    
    if not input_text:
        await queryWishlist.finish("请输入游戏ID，格式: queryWishlist [gameId]")
    
    # 提取游戏ID（支持直接输入数字或从URL中提取）
    game_id_match = re.findall(r"(?<=app/)(\d+)|(\d{5,11})", input_text)
    
    if game_id_match:
        # 提取第一个匹配的非空组
        game_id = tuple(item for item in game_id_match[0] if item)[0]
    else:
        # 如果正则没匹配到，尝试直接使用输入内容
        game_id = input_text
    
    # 查询wishlist
    query_result = query_wishlist_by_gameid(game_id)
    
    # 格式化输出
    formatted_output = format_wishlist_response(query_result)
    
    await queryWishlist.finish(formatted_output)