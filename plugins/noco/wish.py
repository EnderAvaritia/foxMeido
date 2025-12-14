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
accountTableId = "tableId"

token = "token"
headers = {"xc-token": token}

tableFilter = f"where=(account,eq,353662379)"

# url = f"{nocoUrl}/{tableId}/records?{tableFilter}"

#cookie用cookie editor导出的hander string就行
cookie = ""

# wish = on_command("wish", rule=to_me(), aliases={"wish"}, priority=10, block=True)
wish = on_command("wish", aliases={"wish"}, priority=10, block=True)

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
        
def createRecord (url, gameId, gameName, userId, userName, steamid, link, dayTime, publisher, releaseDate):
    payload = {
    "gameId": gameId,
    "gameName": gameName,
    "userId": userId,
    "userName": userName,
    "steamId": steamid,
    "Link": link,
    "submitTime": dayTime,
    "publisher": publisher,
    "releaseDate": releaseDate
    }
    
    headers = {
    'Content-Type': "application/json",
    'xc-token': token
    }
    
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    # response = requests.post(url, data=json.dumps(payload), headers=headers, verify=False)

    # print(response.text)
    
    json_string = response.text
    data = json.loads(json_string)
    
    return data
    
def updateRecord (url, gameId, gameName, releaseDate, recordId):
    payload = {
    "id": recordId,
    "gameId": gameId,
    "gameName": gameName,
    "releaseDate": releaseDate
    }
    
    headers = {
    'Content-Type': "application/json",
    'xc-token': token
    }
    
    # response = requests.post(url, data=json.dumps(payload), headers=headers)
    response = requests.patch(url, data=json.dumps(payload), headers=headers, verify=False)

    # print(response.text)
    
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
    release_date = None
    errors = []

    # --- 通过Steam Web API 获取游戏名称和厂商名 ---
    api_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese"
    print(f"正在请求API接口: {api_url}")
    proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}


    try:
        response = requests.get(api_url, proxies=proxies)
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
                    
                # 获取发行日期并合并
                release_date = details.get('release_date').get('date')
                if release_date:
                    print(f"获取到发行日期: {release_date}")
                else:
                    errors.append(f"API返回的发行日期为空或未找到 (AppID: {appid})")
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
        "publisher": publisher,
        "release_date":release_date
    }
    if errors:
        result["error"] = "; ".join(errors)
    
    return result

def addToWishlist(appid: str | int, cookie: str) -> str:
    """
    将指定 appid 的游戏加入 Steam 愿望单
    :param appid: 游戏 ID
    :param cookie: 登录后的 Cookie 字符串
    :return: 接口返回的原始文本
    """
    url = "https://store.steampowered.com/api/addtowishlist"
    payload = {"appid": str(appid)}
    headers = {"Cookie": cookie.strip()}

    response = requests.post(url, data=payload, headers=headers)
    try:
        data = response.json()
    except ValueError:
        return False

    # 只要 wishlistCount 字段存在即认为接口正常执行
    return "wishlistCount" in data
    
@wish.handle()
async def handle_function(event):
    
    userId = event.user_id
    # userId = event.author.id
    
    nickname = event.sender.nickname
    
    goodId = str(event.message).strip()
    goodId = re.findall(r"(?<=app/)(\d+)|(\d{5,11})", goodId)
    if not goodId:
        await wish.send("你确定这是商品的id？")
    goodId = tuple(item for item in goodId[0] if item)[0]
    gameInfo = getGameInfo(goodId)
    if "error" in gameInfo:
        await wish.finish(f"游戏{goodId}数据获取出错，请反馈")
    # 获取游戏对应信息
    
    tableFilter = f"where=(account,eq,{userId})"
    accountTableUrl = f"{nocoUrl}/{accountTableId}/records?{tableFilter}"
    accountRecord = getRecord(accountTableUrl)
    if "id" not in accountRecord:
        await wish.finish(f"请id为{userId}的\n{nickname}先使用bind指令进行登记")
    # 获取账号对应信息
    
    tableFilter = f"where=(gameId,eq,{goodId})"
    wishlistTableUrl = f"{nocoUrl}/{wishlistTableId}/records?{tableFilter}"
    wishlistRecord = getRecord(wishlistTableUrl)
    
    if "id" in wishlistRecord:
        
         link = f'https://store.steampowered.com/app/{goodId}'
        
         wishlistTableUrl = f"{nocoUrl}/{wishlistTableId}/records"
        
         updateWishlistRecord = updateRecord (wishlistTableUrl, goodId,  gameInfo["game_name"], gameInfo["release_date"], wishlistRecord['id'])
         # 借用许愿来更新条目
         if wishlistRecord['id'] == updateWishlistRecord['id']:
            await wish.finish(f'id为{goodId}的游戏\n《{gameInfo["game_name"]}》\n已经被{wishlistRecord["userName"]}许过愿了\n下次早点来吧')
    else:
        if cookie:
            addToWishlistResult = addToWishlist(goodId,cookie)
            if addToWishlistResult:
                print("愿望单添加成功")
            else:
                print("愿望单添加失败")
            
            
        dayTime = datetime.date.today().strftime('%Y-%m-%d')

        link = f'https://store.steampowered.com/app/{goodId}'
        
        wishlistTableUrl = f"{nocoUrl}/{wishlistTableId}/records"
    
        recordResult = createRecord (wishlistTableUrl, goodId, gameInfo["game_name"], accountRecord["account"], accountRecord["nickname"], accountRecord["steamId"], link, dayTime, gameInfo["publisher"],gameInfo["release_date"])

        if "id" not in recordResult:
            await wish.finish(f"登记阶段出现未知错误，请反馈")
        else:
             await wish.finish(f'id为{userId}的用户{nickname}\n对id为{goodId}的游戏《{gameInfo["game_name"]}》\n成功登记为第{recordResult["id"]}个许愿\n预计发行日期为：{gameInfo["release_date"]}')
