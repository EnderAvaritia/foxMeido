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
accountTableId = "tableId"
recordTableId = "tableId"
remainTableId = "tableId"

token = "token"
headers = {"xc-token": token}

tableFilter = f"where=(account,eq,353662379)"

# url = f"{nocoUrl}/{tableId}/records?{tableFilter}"

proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

# get = on_command("get", rule=to_me(), aliases={"get"}, priority=10, block=True)
get = on_command("get", aliases={"get"}, priority=10, block=True)

def getRecord(url):
    
    response = requests.get(url, headers=headers)
    # response = requests.get(url, headers=headers, verify=False)
    
    json_string = response.text
    data = json.loads(json_string)
    
    if data['list'] == []:
        return ""
    else:
        # return data['list'][0]['steamId']
        return data['list'][0] # 这东西还得要求一个id用于更新记录
        
def createRecord (url, gameId, gameName, userId, userName, steamid, link, dayTime, publisher):
    payload = {
    "gameId": gameId,
    "gameName": gameName,
    "userId": userId,
    "userName": userName,
    "steamId": steamid,
    "Link": link,
    "getTime": dayTime,
    "publisher": publisher
    }
    
    headers = {
    'Content-Type': "application/json",
    'xc-token': token
    }
    
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    # response = requests.post(url, data=json.dumps(payload), headers=headers, verify=False)

    print(f"创建记录响应: {response.text}")
    
    json_string = response.text
    data = json.loads(json_string)
    
    return data

def updateRecord (url, recordId, gameId, gameName, totalCount, getedCount, canBeClaimed):
    
    payload = {
    "id": recordId,
    "gameId": gameId,
    "gameName": gameName,
    "totalCount": totalCount,
    "getedCount": getedCount,
    "canBeClaimed": canBeClaimed
    }
    headers = {
    'Content-Type': "application/json",
    'xc-token': token
    }
    
    response = requests.patch(url, data=json.dumps(payload), headers=headers)
    # response = requests.patch(url, data=json.dumps(payload), headers=headers, verify=False)

    print(f"更新记录响应: {response.text}")
    
    json_string = response.text
    data = json.loads(json_string)
    
    return data
    
def getGameInfo(appid: int):
    """
    根据Steam AppID，通过Steam Web API获取游戏的名称和厂商名。
    如果存在多个厂商名，将它们合并成一个用逗号和空格分隔的字符串。

    Args:
        appid (int): Steam游戏的AppID。

    Returns:
        dict: 包含游戏名称和厂商名的字典。
              例如：{"game_name": "Half-Life 2", "publisher": "Valve"}
              如果获取失败，会包含 "error" 键，并可能包含已获取的部分信息。
              例如：{"game_name": None, "publisher": None, "error": "API返回成功状态为false..."}
    """
    game_name = None
    publisher = None # 默认为None
    errors = []

    # --- 通过Steam Web API 获取游戏名称和厂商名 ---
    api_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese"
    print(f"正在请求API接口: {api_url}")

    try:
        response = requests.get(api_url, proxies=proxies, timeout=10)
        response.raise_for_status()  # 检查HTTP状态码，如果不是200则抛出异常

        data = response.json()
        app_data = data.get(str(appid)) # API响应中AppID是字符串键

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

                # 获取厂商名列表并合并
                publishers_list = details.get('publishers')
                if publishers_list:
                    # 将列表中的所有厂商名用逗号和空格连接起来
                    publisher = ", ".join(publishers_list)
                    print(f"获取到厂商名: {publisher}")
                else:
                    errors.append(f"API返回的厂商列表为空或未找到 (AppID: {appid})")
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
        "game_name": game_name,
        "publisher": publisher
    }
    if errors:
        result["error"] = "; ".join(errors)
    
    return result

    
@get.handle()
async def handle_function(event: MessageEvent, args: Message = CommandArg()):
    
    # 获取参数并分割
    args_str = args.extract_plain_text().strip()
    params = args_str.split()
    
    # 根据参数数量决定使用哪个用户ID
    if len(params) == 2:
        # 两个参数：第一个是goodId，第二个是userId
        goodId_str = params[0]
        userId_str = params[1]
        
        # 尝试将userId转换为整数
        try:
            userId = int(userId_str)
        except ValueError:
            await get.finish(f"用户ID格式错误：{userId_str}")
            
        # 使用输入的userId，而不是event.user_id
        # 注意：这里需要获取对应用户的昵称，但event.sender.nickname是当前发送者的昵称
        # 对于这种情况，我们可能需要从数据库获取对应用户的昵称
        # 暂时先使用当前发送者的昵称，或者可以修改为从数据库查询
        nickname = event.sender.nickname
        
    elif len(params) == 1:
        # 一个参数：只有goodId，使用event.user_id
        goodId_str = params[0]
        userId = event.user_id
        nickname = event.sender.nickname
    else:
        await get.finish("参数错误！用法：\n1. get <商品ID> - 为自己登记\n2. get <商品ID> <用户ID> - 为指定用户登记")
    
    # 从goodId_str中提取数字ID
    goodId = re.findall(r"(?<=app/)(\d+)|(\d{5,11})", goodId_str)
    if not goodId:
        await get.finish("你确定这是商品的id？")
    goodId = tuple(item for item in goodId[0] if item)[0]
    gameInfo = getGameInfo(goodId)
    if "error" in gameInfo:
        await get.finish(f"游戏{goodId}数据获取出错，请反馈")
    # 获取游戏对应信息
    
    tableFilter = f"where=(gameId,eq,{goodId})"
    remainTableUrl = f"{nocoUrl}/{remainTableId}/records?{tableFilter}"
    remainGameRecord = getRecord(remainTableUrl)
    if "id" not in remainGameRecord:
        await get.finish(f'id为{goodId}的游戏\n《{gameInfo["game_name"]}》尚未收录\n请联系厂商')
    elif remainGameRecord["getedCount"] >= remainGameRecord["totalCount"]:
        await get.finish(f'id为{goodId}的游戏\n《{gameInfo["game_name"]}》已领取完毕\n无剩余')
    # 检查游戏剩余数量

    tableFilter = f"where=(account,eq,{userId})"
    accountTableUrl = f"{nocoUrl}/{accountTableId}/records?{tableFilter}"
    
    accountRecord = getRecord(accountTableUrl)
    if "id" not in accountRecord:
        # 当使用指定用户ID时，我们不知道该用户的昵称，所以只显示用户ID
        await get.finish(f"用户ID {userId} 尚未绑定，请先使用bind指令进行登记")
    # 获取账号对应信息

    # 检查用户是否已经登记过这个游戏
    tableFilter = f"where=(gameId,eq,{goodId})~and(userId,eq,{userId})"
    checkRecordUrl = f"{nocoUrl}/{recordTableId}/records?{tableFilter}"
    existingRecord = getRecord(checkRecordUrl)
    
    if "id" in existingRecord:
        await get.finish(f'用户ID {userId} (昵称: {accountRecord["nickname"]})\n已经登记过游戏ID {goodId}《{gameInfo["game_name"]}》\n登记ID: {existingRecord["id"]}')
    
    dayTime = datetime.date.today().strftime('%Y-%m-%d')

    link = f'https://steamcommunity.com/profiles/{accountRecord["steamId"]}/recommended/{goodId}'
    
    recordTableUrl = f"{nocoUrl}/{recordTableId}/records"
    
    recordResult = createRecord (recordTableUrl, goodId, gameInfo["game_name"], accountRecord["account"], accountRecord["nickname"], accountRecord["steamId"], link, dayTime, gameInfo["publisher"],)

    if "id" not in recordResult:
        await get.finish(f"登记阶段出现未知错误，请反馈")
    else:
        remainTableUrl = f"{nocoUrl}/{remainTableId}/records"
        canBeClaimed = remainGameRecord["totalCount"] - remainGameRecord["getedCount"] - 1
        remain = updateRecord (remainTableUrl, remainGameRecord["id"], goodId, gameInfo["game_name"], remainGameRecord["totalCount"], remainGameRecord["getedCount"] + 1, canBeClaimed)
        if "id" in remain :
            await get.finish(f'用户ID {userId} (昵称: {accountRecord["nickname"]})\n对游戏ID {goodId}《{gameInfo["game_name"]}》\n成功登记为第{recordResult["id"]}个结果\n游戏剩余{remainGameRecord["totalCount"] - remainGameRecord["getedCount"] - 1}个')
