# ITEMDB_OFFICIAL_VS_OURS — 官方 / 我们 的 ItemDB 与 ItemListResponse 逐字段比对

> 只读离线比对。未改任何源码、未部署、未重启、未改库。
> 素材：
> - 官方 `Item_List`(4000) 响应：`report\_tmp\official_decoded_201\03_4000_api_item_list.response.json`
> - 官方 LoginSync：`report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json`
> - 我们线上 LoginSync（22:43:25 那次）：`/www/wwwroot/ba_srv/logs/wire-2026-11-18.txt`（只读取）
> - 服务端 DTO：`work\ba\srv_src\Schale\MX\NetworkProtocol\NetworkProtocol.cs`、`...\MX\GameLogic\DBModel\DBModel.cs`

---

## 1. 官方 `ItemDB` 字段集合（134 条取并集）

| 字段 | 类型 | 出现率 | 备注 |
|---|---|---|---|
| `Type` | int | **134/134 = 100%** | 全为 `4` |
| `ServerId` | int | **134/134 = 100%** | 8 位量级（24345539 …） |
| `UniqueId` | int | **134/134 = 100%** | 道具 Excel Id |
| `StackCount` | int | **134/134 = 100%** | |
| `IsNew` | bool | **134/134 = 100%** | 绝大多数 `false` |

**没有 `ExpiryDate`**（134 条里 0 次）。过期道具走的是 `ExpiryItemDBs` 这个**独立列表**（官方 4000 响应里 `ExpiryItemDBs: []`，0 条）。

> 结论：官方 `ItemDB` **只有 5 个字段**，其中 `IsNew` 是**必有**字段。

---

## 2. 我们发出的 `ItemDB`（LoginSync 内嵌，21 条）

从 22:43:25 的 LoginSync `packet` 解出（二次 `json.loads`）：

```
字段统计: {'Type': 21, 'ServerId': 21, 'UniqueId': 21, 'StackCount': 21}
首 3 条: [{"Type":4,"ServerId":23,"UniqueId":2,"StackCount":5},
          {"Type":4,"ServerId":24,"UniqueId":3,"StackCount":18},
          {"Type":4,"ServerId":25,"UniqueId":11,"StackCount":414}]
Type 分布: {4: 21}
```

### 缺字段清单

| 缺失字段 | 官方出现率 | 原因 |
|---|---|---|
| **`IsNew`** | 100% | **DTO 根本没这个属性** —— `ItemDB : ConsumableItemBaseDB`（`DBModel.cs:1487`），基类（`DBModel.cs:818`）只有 `Key / ServerId / UniqueId / StackCount / CanConsume`。**不是** `DefaultValueHandling.Ignore` 吞掉的 |

### 我们多出来的字段（序列化时被忽略）

- `CanConsume`（bool，默认 false → 被 ignore）
- `Key`（`ParcelKeyPair?`，null → 被 ignore）
- `ParcelInfos`（override，null → 被 ignore）

⇒ 净效果就是我们只发 4 个字段，**比官方少 `IsNew`**。

---

## 3. `ItemListResponse` 的形状对比

服务端 DTO（`NetworkProtocol.cs:4470`）：
```csharp
public class ItemListResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Item_List; }   // 4000
    public List<ItemDB>? ItemDBs { get; set; }
    public List<ItemDB>? ExpiryItemDBs { get; set; }
}
```

| 项 | 官方 | 我们 |
|---|---|---|
| 独立 `Item_List`(4000) 响应 | 有：`Protocol + SessionKey + ServerTimeTicks + ServerNotification + RequestId + ItemDBs(134) + ExpiryItemDBs([])` | 客户端**从不发 4000**（11-17/11-18 日志 `"Protocol":4000` 精确匹配 **0 次**） |
| LoginSync 内嵌 `ItemListResponse` | **`{}`（空对象，一个字段都没有）** | **内嵌完整响应**：`{"Protocol":4000,"ItemDBs":[21条...],"ExpiryItemDBs":[]}` |
| 字段集合 | Protocol / ItemDBs / ExpiryItemDBs | 同（一致） |

**关键事实**：官方把道具放在**独立的 4000 响应**里，LoginSync 里只留一个 `{}` 占位；
我们把 21 条直接塞进 LoginSync，而客户端**从不主动发 4000** ⇒ 客户端的道具来源只能是 LoginSync 内嵌的那份。

---

## 4. `Item.Type` 取值

- 官方：**134/134 全为 `4`**。
- 我们：**21/21 全为 `4`**。
- 枚举：`work\ba\srv_src\Schale\FlatData\ParcelType.cs:14` → **`Item = 4`** ✅

⇒ **`Type=4` 是对的，无需修改。**

---

## 5. 官方 134 条的 `UniqueId` 分布（前 30）

```
2, 23, 16002, 26000, 10, 12, 13, 150041, 150004, 150005,
150006, 150008, 150009, 150010, 150011, 5997, 100008, 150000,
150001, 150002, 11, 20001000, 160, 4030, 161, 162, 220, 221, 222, 3030
```
- 覆盖：低级材料（2/10/11/12/13）、活动材料（150xxx）、货币类（160/161/162）、
  其它（5997、100008、20001000、4030、3030、220/221/222）。
- 我们 21 条里可见 `2/3/11…`，**属于同一号段**，只是数量少（账号进度不同）。
- **没有明显的招募券专属号**（BA 的招募券是 100xxx 段，官方样本里 `100008` 是唯一 100xxx，但无法仅凭 ID 断定是券）。

---

## 6. 结论与建议

### 6.1 「客户端读不到道具」最可能的差异

**排序（带证据强度）**
1. **【已证实】`ItemDB` 缺 `IsNew`**：官方 134/134 必带，我们 DTO 里根本没有这个属性。
   影响面：客户端会认为所有道具都"不是新获得"；如果它的道具列表项渲染依赖 `IsNew` 初始化内部字段，理论上可能影响显示，但**不足以解释"读不到"**。
2. **【已证实】LoginSync 里 `ItemListResponse` 的形态与官方不同**：官方 `{}`，我们内嵌 21 条完整响应，
   且**客户端从不发 4000** ⇒ 客户端的道具来源**只有** LoginSync 这一份，任何该结构的解析偏差都会直接表现为"背包空/读不到"。
3. **【推测-弱】`ServerId` 量级不同**：官方 8 位（24345539…），我们 23/24/25。若客户端用 `ServerId` 作唯一键/字典键，小值通常无碍；但若它按 `ServerId` 与其它表关联则可能对不上。

### 6.2 可执行建议（按优先级）

| # | 建议 | 文件/位置 | 强度 |
|---|---|---|---|
| **1** | 给 `ItemDB` 增加 `IsNew` 属性并让它参与序列化（官方 100% 带） | `work\ba\srv_src\Schale\MX\GameLogic\DBModel\DBModel.cs:1487`（`class ItemDB`）加 `public bool IsNew { get; set; }`，并在填充时置 `false`；若序列化器开了 `DefaultValueHandling.Ignore`，需加 `[JsonProperty(DefaultValueHandling = DefaultValueHandling.Include)]` | **已证实缺失** |
| **2** | 与官方对齐：LoginSync 里的 `ItemListResponse` 改为空对象 `{}`，改由客户端发 `Item_List`(4000) 取道具 | 找写入 LoginSync 的地方（`BuildItemListResponse` 之类） | **推测**（需真机确认客户端会自发 4000；若不会，则**不能**改，保持现状） |
| **3** | 若改 2 不成立，则保留内嵌，但把 21 条补齐到与官方一致的字段集（`IsNew` 必带），并核对 `ExpiryItemDBs` 是否为 `[]` | 同上 | **已证实**（字段集缺口是确定的） |

> ⚠️ 建议 2 存在"改了更糟"的风险：我们已证实客户端**从不发 4000**，一旦把 LoginSync 里的道具清空，客户端可能一个道具都拿不到。**必须先真机抓一次 4000 是否出现**，否则不要动。

### 6.3 未能证实、需要新证据的点

- 客户端对 `ItemListResponse` 内嵌在 LoginSync 里的处理是"整体替换"还是"增量合并"（需客户端代码/日志）。
- `IsNew` 缺失是否真的导致显示异常（需真机对比：补上前后背包是否变化）。
- 官方 `Item_List` 的 `ServerId` 是否必须与服务器账号 ID 空间一致。
