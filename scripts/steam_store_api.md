# Steam Store API 参考

`store.steampowered.com/api/appdetails` 是 Steam 商店前端使用的非官方但长期稳定的端点，
免鉴权，社区工具（SteamDB、IsThereAnyDeal 等）长期依赖。foxMeido 的 `steam_utils.py` 与
`price` 命令（多区域比价）均基于此端点。

## 请求

```text
GET https://store.steampowered.com/api/appdetails
    ?appids={appid}[,{appid}...]   # 必填，支持逗号分隔多 AppID（同一货币区一次取回）
    &cc={country_code}             # 可选，ISO 3166-1 alpha-2，如 us/cn/jp/tr
    &l={language}                  # 可选，如 schinese / english
    &filters={field}[,{field}...]  # 可选，只返回指定字段，如 price_overview,basic
```

- **`cc` 决定 `price_overview` 的货币与区域定价**。不带则按出口 IP 自动决定。
- 建议匿名请求也带 Cookie 绕过成人内容的年龄门，否则部分 18+ 游戏不返回价格：
  `Cookie: birthtime=1; lastagecheckage=1; wants_mature_content=1`
- 国内访问需走代理（本项目统一用 `plugins/env_utils.get_proxies()`）。
- 附带登录态 Cookie（`STEAM_COOKIE`）时货币可能受账户区域干扰，查多区价格请勿携带。

## 返回结构

```json
{
  "1091500": {
    "success": true,
    "data": {
      "name": "Cyberpunk 2077",
      "is_free": false,
      "price_overview": {
        "currency": "CNY",
        "initial": 29800,
        "final": 14900,
        "discount_percent": 50,
        "initial_formatted": "¥ 298.00",
        "final_formatted": "¥ 149.00"
      }
    }
  }
}
```

注意：

- 金额单位为**分**（cents），除以 100 才是主单位。
- **免费游戏没有 `price_overview`**（`is_free=true`）。
- 该区未上架 / 锁区 / 不可购买时：`success=false` 或 `price_overview` 缺失。
- **低价区对国外 IP 隐身**：TR（土耳其）/ AR（阿根廷）需本区账户与 IP 才返回本币价；
  RU 已停止本币定价。用 `cc=tr` 等从非本区 IP 查询大概率拿不到价格，属正常现象。
- 同一游戏不同区返回的货币/价格不同，多区比价 = 循环 `cc`（见 `price` 命令）。

## 频率限制

社区实测约 **200 请求 / 5 分钟 / IP** 的软限制。按需单次查询（一个游戏 × 十几个区域 ≈ 十余个请求）
远低于限制；全库批量扫描需要缓存、降速与代理轮换，不要在 QQ 群请求路径里做。

## 常用区域与货币对照

| 区域 (cc) | 货币 | 区域 (cc) | 货币 |
|---|---|---|---|
| cn | CNY 人民币 | gb | GBP 英镑 |
| us | USD 美元 | de / fr / es / it | EUR 欧元 |
| jp | JPY 日元 | br | BRL 雷亚尔 |
| kr | KRW 韩元 | au | AUD 澳元 |
| hk | HKD 港币 | ca | CAD 加元 |
| tw | TWD 新台币 | ru | RUB 卢布（已停本币定价） |
| sg | SGD 新加坡元 | tr | TRY 里拉（IP 受限） |
| ua | UAH 格里夫纳 | ar | ARS 比索（IP 受限） |
| in | INR 卢比 | pl | PLN 兹罗提 |
| kz | KZT 坚戈 | vn | VND 越南盾 |

## 本仓库使用点

- `plugins/steam_utils.py`：`get_game_info`（详情+单区价格，全量请求）、
  `get_multi_region_prices`（多区并发，每区仅 `filters=price_overview` 只取价格，
  元数据单独一次 `filters=basic`/全量兜底）
- `plugins/price.py`：`price` / `比价` 命令
- 汇率换算基准为人民币（CNY）：`https://open.er-api.com/v6/latest/CNY`（每日更新，免费）
