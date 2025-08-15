# foxMeido

## How to start

1. generate project using `nb create` .
2. install plugins using `nb plugin install` .
3. run your bot using `nb run` .

## Documentation

See [Docs](https://nonebot.dev/)

## 用法

主要作用是查询与steam相关的内容

help显示帮助

使用id查找steam游戏，后面可接游戏id或者url，如：id 3251240

使用cs或者dota获取挂刀详情表，可带参数，依次是最低价格和日销量，如：dota 5 100

使用find查找steam游戏，交互式搜索，如：find 夫妻

使用pub查找发行商页面，如：pub publisher/MangoParty(前面的前缀自行补全)

## 如果显示缺少库

Linux:`source .venv\Scripts\activate`/ Windows:`.venv\Scripts\activate.bat`

`nb plugin install nonebot-plugin-alconna`

`nb plugin install nonebot_plugin_apscheduler`

`pip install requests beautifulsoup4 playwright httpx lxml`

## 需要配合其他软件使用的功能

### 需要配合[nocodb](https://github.com/nocodb/nocodb)使用（wip）

用于方便登记谁领了什么游戏