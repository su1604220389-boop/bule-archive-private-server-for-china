# 招募不可用 —— 真因定位：桥把 `Item_List`(4000) 换成了固定桩

2026-11-19 00:0x 定案。**纯服务端缺陷。**

## 1. 关键证据（nginx 访问日志，`/www/wwwlogs/example.com.log`）

```
22:38:09  POST /api/item/list        200  640   BestHTTP/2 v2.4.0
22:43:26  POST /api/item/list        200  640
22:57:44  POST /api/item/list        200  640
23:51:06  POST /api/item/list        200  640
```

**每次登录都请求，永远 640 字节。** 官方同一条响应 = **35,108 B / 134 件道具**
（`report\_tmp\official_decoded_201\03_4000_api_item_list.response.json`）。

## 2. 为什么 wire 日志里看不到这条

`/api/*` 由 nginx 转发到**桥** `127.0.0.1:9097`（`account_auth_probe.py`）；
只有桥把请求转给 Shittim(5000) `/api/gateway` 时，才会进 `wire-*.txt`。
桥自己把 `Item_List` 接住了 ⇒ **wire 里 0 条 `Item_List`**，之前据此得出的
「客户端不发 4000」是**错的**（那是被桥吞掉的假象）。

## 3. 桥里干这件事的代码

`/www/wwwroot/bapatch/tools/account_auth_probe.py`：

```python
SIMPLE_PROTOCOLS = (1005, 4000, 26000)   # 1005=Tutorial 4000=Item_List 26000=ContentSave
SIMPLE_SWITCH_FILES = {1005: 'cn_1005.txt', 4000: 'cn_4000.txt', 26000: 'cn_26000.txt'}
simple_wants(num) → num in SIMPLE_PROTOCOLS and simple_switch_on(num)
simple_build(4000) → 用 SIMPLE_INITIAL_ITEMS 合成固定道具表（不读数据库）
```

三个开关文件都在 `/www/wwwroot/bapatch/tools/`：`cn_4000.txt` / `cn_26000.txt` / `cn_1005.txt`，**当前都是开**。

⇒ **客户端拿到的背包是桥合成的固定桩，不是数据库里的真实道具。**

## 4. 因果链（一条原因解释全部现象）

```
客户端请求 /api/item/list
  → 桥合成固定桩（640 B，SIMPLE_INITIAL_ITEMS，无招募券）
  → 客户端认为背包里没有招募券
  → UIGacha.IsCanBuyGacha → 券不足 → ShowToast(本地化key缺失 → 显示 No LocalizeKey) + return false
  → 十连按钮永远点不动，且不发任何 Shop 请求（wire 里 0 条）
  → 按钮上那个「1,000」是算不出券数时的兜底值，所以每个池子都一样
```

同时解释了：**给数据库加多少券都没用**（`22:54 / 22:59` 两次加券后按钮完全不变），
因为这条链路根本不读数据库。

## 5. 已排除（都实测过，别再回头）

| 假设 | 结论 | 依据 |
|---|---|---|
| 客户端表过期 | 排除 | `5004670` 售期 2026-11-12~11-26，当前在区间内 |
| 服务端没发卡池 | 排除 | LoginSync 里 `ShopRecruits` 529 条 |
| 卡池 id 客户端没有 | 排除 | 客户端表 532 行 ⊇ 官方 529 |
| `IsLegacy` 闸门 | 排除 | 532 行全部无该字段 = false = 0，闸门放行 |
| 货币枚举/字段 | 排除 | 官方数字键与我们 `CurrencyTypes` 逐位吻合 |
| `GemPaid=0` | 排除 | 官方也是 0 |
| SQLCipher 密钥 | 排除 | 客户端从不请求 `Queuing` |
| 客户端时钟 | 排除 | 不请求 `NetworkTime_Sync`… **注意：其实请求了，但被桥接住** |
| CDN 表清单 | 排除 | 四个 URL 从服务器实测全部 200 |
| `/api/state` 内容 | 排除 | 与官方 676 B 逐字段一致 |
| `PickupSelectionGacha` 不保存选择 | **是真 bug，已修**，但不是本次根因 | `/root/PICKSEL_20261118_230108/` |

## 6. 修复方案（已派 srv-ops 执行）

**方案 A（首选）**：让 4000 走桥已有的 relay2 转发机制到 Shittim 真实 `/api/gateway`
1. 确认 `Item_List` 不在 `RL2_SKIP_NAMES` / `RL2_HANDLED` 排除名单
2. 建 `cn_relay_known.txt` = `1`
3. `cn_4000.txt` 改成 `0`（让 `simple_wants()` 不再接管）

**方案 B（仅当 A 牵连其它协议时）**：改 `SIMPLE_INITIAL_ITEMS` 加入招募券 —— 只是让客户端“看到”，抽完数量不会变，属临时绕过。

## 7. 附：`ItemDB` 字段对齐（proto-analyst 离线比对）

- 官方 `ItemDB` 5 字段 100% 出现：`Type / ServerId / UniqueId / StackCount / IsNew`，**无 ExpiryDate**
- 我们缺 **`IsNew`**，且是 **DTO 根本没这个属性**（`DBModel.cs:1487` `ItemDB : ConsumableItemBaseDB`，基类 `DBModel.cs:818` 只有 `Key/ServerId/UniqueId/StackCount/CanConsume`）
- `Type=4`（`ParcelType.Item`）官方与我们一致，正确
- `ItemListResponse` 类形状一致（`Protocol + ItemDBs + ExpiryItemDBs`）

详见 `work\ba\plan\20261118\ITEMDB_OFFICIAL_VS_OURS.md`。
