from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
# from nonebot.adapters.qq import MessageSegment

import requests
import json
import re

nocoUrl = "https://127.0.0.1:52533/api/v2/tables"
tableId = "tableId"

token = "token"
headers = {"xc-token": token}

tableFilter = f"where=(account,eq,353662379)"

# url = f"{nocoUrl}/{tableId}/records?{tableFilter}"


# bind = on_command("bind", rule=to_me(), aliases={"bind"}, priority=10, block=True)
bind = on_command("bind", aliases={"bind"}, priority=10, block=True)

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
        
def createRecord (url, userId, steamid, nickname):
    payload = {
    "account": userId,
    "steamId": steamid,
    "nickname": nickname
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
    
    return data['id']

def updateRecord (url, userId, steamid, nickname, recordId):
    
    payload = {
    "id": recordId,
    "account": userId,
    "steamId": steamid,
    "nickname": nickname
    }
    headers = {
    'Content-Type': "application/json",
    'xc-token': token
    }
    
    response = requests.patch(url, data=json.dumps(payload), headers=headers)
    # response = requests.patch(url, data=json.dumps(payload), headers=headers, verify=False)

    # print(response.text)
    
    json_string = response.text
    data = json.loads(json_string)
    
    return data['id']

    
@bind.handle()
async def handle_function(event):
    
    userId = event.user_id
    # userId = event.author.id
    
    nickname = event.sender.nickname
    
    tableFilter = f"where=(account,eq,{userId})"
    url = f"{nocoUrl}/{tableId}/records?{tableFilter}"
    
    record = getRecord(url)
    # 获取是否存在已有的记录,返回是是一个包含id的数组
    
    # print(record)

    message_text = str(event.get_message())
    # https://steamcommunity.com/profiles/76561198836530221/
    steamid = re.findall(r"(?<=steamcommunity.com/profiles/)(\d+)|(\d{15,20})", message_text)
    # 获取steamid
    
    # print(steamid)
    steamid = tuple(item for item in steamid[0] if item)[0]
    # 清除元组中的空结果
    # print(steamid)
    
    if not steamid: 
    # 如果没有找到有效的steamid，提前结束
        await bind.finish("未检测到有效的Steam ID，请检查输入。")
    
    # await bind.send(f"{userId}:{steamid}")
    
    url = f"{nocoUrl}/{tableId}/records"
    if record == "":
        recordId = createRecord(url, userId, steamid, nickname)
        await bind.finish(f"{nickname}用户的id：{userId}\n{steamid}\n已被登记为第{recordId}个结果")
    else:
        recordId = updateRecord (url, userId, steamid, nickname, record['id'])
        if record['id'] == recordId:
            await bind.finish(f"{nickname}用户的id：{userId}\n{steamid}已被更新")
        else:
            await bind.finish(f"出现错误，请反馈")

