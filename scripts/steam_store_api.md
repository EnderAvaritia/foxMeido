# Steam Store API 参考

机器人内部通过 Steam 非官方 API `store.steampowered.com/api/appdetails` 获取游戏信息。

## 端点

```
GET https://store.steampowered.com/api/appdetails
```

## 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `appids` | 是 | Steam App ID，多个用逗号分隔（如 `730,570`）。多 appid 时必须加 `&filters=price_overview`，否则返回 400 |
| `cc` | 否 | **国家/地区码**（ISO 3166-1），控制返回的货币和区域定价。如 `cn` → CNY、`us` → USD、`jp` → JPY、`hk` → HKD |
| `l` | 否 | **语言**，控制本地化文本。如 `schinese`（简体中文）、`english`、`japanese` |
| `filters` | 否 | 过滤返回字段，CSV 格式。如 `price_overview`（仅价格）、`basic`（基础信息） |

## 返回示例

```json
{
  "838350": {
    "success": true,
    "data": {
      "price_overview": {
        "currency": "CNY",
        "initial": 10800,
        "final": 10800,
        "discount_percent": 0,
        "final_formatted": "¥ 108.00"
      }
    }
  }
}
```

> 价格单位为**分**（cents），即 `10800` = ¥108.00。

## 注意事项

1. **Cookie 会覆盖 `cc` 参数**：在浏览器中直接访问时，`store.steampowered.com` 的已有 Cookie（如 `steamCountry`、`steamCurrency`）**优先级高于 `cc` 参数**。如果你登录了美区账号且当前窗口有对应 Cookie，即使加上 `&cc=cn` 仍可能返回 USD。解决方案：
   - **服务端调用**（推荐）：后端代码发请求，不带 Cookie
   - **隐私/无痕窗口**：无已有 Cookie，`cc` 正常生效
   - **fetch 时禁用凭据**：`fetch(url, { credentials: 'omit' })`

2. 本机器人的 `get_game_info()` 会自动读取 `.env` 中的 `STEAM_CC` 配置并附加到请求中，服务端调用不受浏览器 Cookie 影响。

3. **锁区降级**：如果设置了 `STEAM_CC` 但目标区返回 `success: false`（游戏在该区不可用），会自动降级到不带 `cc` 参数重新请求，确保能正常显示游戏信息。

4. **IP 地理围栏**：极少数区域（俄罗斯等）可能会基于出口 IP 覆盖 `cc` 参数，需配合对应区域的代理。

5. **速率限制**：约 200 请求 / 5 分钟 / IP，超出返回 429。

6. **非官方 API**：此为 Valve 内部接口，无稳定性保证，可能随时变更。

## 常用 `cc` 与货币对照

| cc | 货币 | 区域 |
|----|------|------|
| `us` | USD ($) | 美国 |
| `cn` | CNY (¥) | 中国 |
| `tw` | TWD (NT$) | 台湾 |
| `hk` | HKD (HK$) | 香港 |
| `jp` | JPY (¥) | 日本 |
| `kr` | KRW (₩) | 韩国 |
| `ru` | RUB (₽) | 俄罗斯 |
| `gb` | GBP (£) | 英国 |
| `de` / `fr` / `it` / `es` | EUR (€) | 欧洲 |
