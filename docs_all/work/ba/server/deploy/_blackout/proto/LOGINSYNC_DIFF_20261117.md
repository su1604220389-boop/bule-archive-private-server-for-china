# LOGINSYNC_DIFF_20261117 — 我方 vs 官方 `Account_LoginSync` 逐字段对比

> 时间：2026-11-17 19:45–20:1x
> 素材：① 服务器 `/root/ba_watch/blackout_lo.pcap0`（827 KB，1189 包，379.2 s，2026-11-17 19:39 那轮，已 scp 到本目录）
> ② `report\_tmp\最全的一个.har`（官方 CN 抓包，2026-11-15 20:30:54 那条 `Account_LoginSync`）
> 方法：本地 Python 解 pcap → 重组 TCP → 拆 HTTP → 按固定 IV 解密。**只读，未安装任何软件，未改任何现有文件。**
> 产物（同目录）：`_ours_loginsync_37060.json`、`_official_loginsync.json`、`_ours_auth_37040.json`、`_official_auth.json`

> ## ⚠️ 2026-11-17 20:xx 更正：§0 的 **D1 / D2 已撤回**
>
> **撤回原因（lead 转述 srv-ops 复核）**：19:42:10 的 `Account_Auth` 原始报文（**Shittim wire dump**）里，
> `AccountDB` 只有 **9 个键**，`RepresentCharacterServerId = 9`（指向真实角色 `UniqueId 13003`），
> `1100001` 在该报文出现 **0 次**；`LobbyMode = 0` 且被 `DefaultValueHandling.Ignore` 省略 —— **与官方一致，不是缺陷**。
>
> **但本次复核同时确认了一件事**（见 §9.0）：9097（桥接明文出口）上抓到的**客户端侧字节**是另一份
> （22 个 AccountDB 字段、`RepresentCharacterServerId=1100001`、`LobbyMode=1`）。
> ⇒ 两个观测**各自可复现**，指向**不同环节**（Shittim 上游 vs 桥接出口）。
> **D1/D2 作为"根因假设"撤回**；但"客户端到底收到哪一份"仍需 srv-ops 用 bridge 日志确认，见 §9.0。
> **本文件 §0–§7 的其他结论（尤其 LoginSync 35/35 完全对齐）不受影响。**

---

## 0. 结论（先说，含"不是 LoginSync"的部分）

1. **`Account_LoginSync` 本身不缺任何字段。**
   两份响应都是 **35 个顶层 key**，逐层比对**结构差异 0 条**（键名/嵌套/类型全一致），
   差异只出现在**值**上（账号 id、等级、列表长度）。⇒ **黑屏不是 LoginSync 缺字段造成的。**

2. **真正的缺陷在 `Account_Auth` 的 `AccountDB` 里**——而它正是客户端缓存、重建大厅时用的那份账号数据：

| # | 缺陷 | 我们 | 官方 | 与大厅渲染的关系 |
|---|---|---|---|---|
| **D1** | **`RepresentCharacterServerId` 指向一个不存在的角色** | `1100001` | `3002866` | **最可疑**。我们 `CharacterListResponse.CharacterDBs` 只有 `210001/210002/210003/210004` 四个角色，**`1100001` 在整个 LoginSync 里出现 0 次**；官方的 `3002866` 在官方 LoginSync 里出现 **7 次**。大厅要按这个 id 实例化代表角色 → 查不到 → 黑屏 |
| **D2** | **`LobbyMode` 值不同** | `1` | `0` | 高。`LobbyMode` 是 lead 说的"咬过三次"的字段，本次**没有被吞**（确实发出去了），但**值是 1**。若 1 = 回忆/特殊大厅，客户端会去加载内存大厅资源 |
| **D3** | **`RoleId` 整个缺失** | 无此键 | `10015354380`（= ServerId） | 中。客户端可能用 `RoleId` 而非 `ServerId` 做角色归属过滤 |
| **D4** | **`LinkRewardDateDate` 缺失、且我们写错成 `LinkRewardDate`** | `"LinkRewardDate": null` | `"LinkRewardDateDate": "0001-01-01T00:00:00"` | 低-中。**字段名不匹配**，客户端永远读不到 |
| **D5** | `OpenConditions` 缺失（顶层） | 无此键（我们发了 `StaticOpenConditions` + `Desc`） | `"OpenConditions": null` | 低（官方这份也是 null） |

3. **`LobbyMode` 和 `MemoryLobbyUniqueId` 都没有被 `DefaultValueHandling.Ignore` 吞掉**：
   `LobbyMode` 在响应里**存在且=1**；`MemoryLobbyUniqueId` **存在且=0**（与官方一致）。
   ⇒ 这一次不是"字段消失"，是"值不对"。

---

## 1. 解密脚本本体（可复跑）

```python
# -*- coding: utf-8 -*-
# deps: 仅标准库 + report\_tmp\mx_crypto\aes_pure.py（纯 Python AES）
import struct, json, base64, collections, sys, os
sys.path.insert(0, r"C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\mx_crypto")
import aes_pure

IV = b"JOSYdf8ys97uhFYS"

def unpad(b):
    n = b[-1] if b else 0
    return b[:-n] if 1 <= n <= 16 and b.endswith(bytes([n]) * n) else b

def decrypt_envelope(body_b64: str) -> dict:
    """base64( AES-256-CBC(ct, key=尾32B, IV=固定) + key32 ) -> {"protocol","packet","requestid"}"""
    raw = base64.b64decode(body_b64 + "=" * ((4 - len(body_b64) % 4) % 4))
    pt = unpad(aes_pure.cbc_decrypt(raw[-32:], IV, raw[:-32])).decode("utf-8")
    return json.loads(pt)

# ---------- 1) 解 pcap（lo，link-type EN10MB） ----------
def read_pcap(path):
    d = open(path, "rb").read()
    magic = struct.unpack("<I", d[:4])[0]
    assert magic == 0xA1B2C3D4, "只处理微秒精度的小端 pcap"
    off, flows = 24, collections.defaultdict(list)
    while off + 16 <= len(d):
        ts, tu, incl, orig = struct.unpack("<IIII", d[off:off+16]); off += 16
        pkt = d[off:off+incl]; off += incl
        if len(pkt) < 34: continue
        eth = pkt[14:]
        if eth[0] >> 4 != 4 or eth[9] != 6: continue          # 只取 IPv4/TCP
        ihl = (eth[0] & 0xF) * 4
        tot = struct.unpack(">H", eth[2:4])[0]
        ip = eth[ihl:tot]
        if len(ip) < 20: continue
        sp, dp = struct.unpack(">HH", ip[0:4])
        seq = struct.unpack(">I", ip[4:8])[0]
        doff = (ip[12] >> 4) * 4
        pl = ip[doff:]
        if pl: flows[(sp, dp)].append((seq, pl))
    return flows

def reassemble(segs):
    segs = sorted(segs); out = bytearray(); want = None
    for s, p in segs:
        if want is None: out += p; want = s + len(p)
        elif s >= want: out += p; want = s + len(p)
        elif s + len(p) > want: out += p[want-s:]; want = s + len(p)
    return bytes(out)

def parse_http(buf):
    res, i = [], 0
    while True:
        j = buf.find(b"HTTP/1.", i)
        if j < 0: break
        k = buf.find(b"\r\n\r\n", j)
        if k < 0: break
        head = buf[j:k].decode("latin-1"); cl = 0
        for line in head.split("\r\n"):
            if line.lower().startswith("content-length:"):
                cl = int(line.split(":")[1].strip())
        res.append((head.split("\r\n")[0], buf[k+4:k+4+cl])); i = k + 4 + cl
    return res

flows = read_pcap(r"...\blackout_lo.pcap0")
for (sp, dp), segs in flows.items():
    if sp != 9097: continue                      # 9097 = 桥接的明文 HTTP
    for status, body in parse_http(reassemble(segs)):
        if len(body) < 40: continue
        o = decrypt_envelope(body.decode("latin-1").strip())
        print(dp, o["protocol"], len(o["packet"]), o["requestid"])

# ---------- 2) 解 HAR（官方） ----------
es = json.load(open(r"...\最全的一个.har", encoding="utf-8"))["log"]["entries"]
for e in es:                                      # 按 URL 找 /api/account/loginsync
    if e["request"]["url"].endswith("/api/account/loginsync"):
        o = decrypt_envelope(e["response"]["content"]["text"].strip())
        official = json.loads(o["packet"])
```

**复跑要点**
- 9097 流里共 56 条响应，其中 `Account_LoginSync` 出现 **2 次**（同一份内容、两个不同 `requestid`，是两次重连）；
- 响应体 **122,968 B**，内层 `packet` 字符串 **82,676 字符**；
- 官方 HAR 那条：响应体 **246,808 B**，内层同为 35 键。

---

## 2. 顶层字段对比（35 vs 35，全部命中）

| 项 | 我们 | 官方 |
|---|---|---|
| 顶层 key 数 | **35** | **35** |
| 官方有、我们无 | **0** | — |
| 我们有、官方无 | **0** | — |
| 深层结构差异（键名/嵌套/类型） | **0 条** | **0 条** |

共有 35 键：
`Protocol` `SessionKey` `ServerTimeTicks` `ServerNotification` `RequestId` `CafeGetInfoResponse`
`AccountCurrencySyncResponse` `CharacterListResponse` `EquipmentItemListResponse` `CharacterGearListResponse`
`ItemListResponse` `EchelonListResponse` `MemoryLobbyListResponse` `CampaignListResponse` `ArenaLoginResponse`
`RaidLoginResponse` `CraftInfoListResponse` `ClanLoginResponse` `MomoTalkOutLineResponse` `ScenarioListResponse`
`ShopGachaRecruitListResponse` `TimeAttackDungeonLoginResponse` `BillingPurchaseListByYostarResponse`
`EventContentPermanentListResponse` `AttachmentEmblemListResponse` `AttachmentGetResponse`
`ContentSweepMultiSweepPresetListResponse` `EliminateRaidLoginResponse` `StickerListResponse` `FriendCount`
`FriendCode` `MultiFloorRaidSyncResponse` `MultiFloorRaidLoginResponse` `PickupFirstGetHistoryDBs` `AccountLevelRewardIds`

**只有值不同**（均已核对，属账号进度差异，非缺陷）：

| 路径 | 我们 | 官方 |
|---|---|---|
| `CharacterListResponse.CharacterDBs` | 4 条 | 46 条 |
| `ScenarioListResponse.ScenarioHistoryDBs` | 0 | 191 |
| `EchelonListResponse.EchelonDBs` | 1 | 8 |
| `EquipmentItemListResponse.EquipmentDBs` | 0 | 84 |
| `CampaignListResponse.StageHistoryDBs` | 0 | 90 |
| `EventContentPermanentListResponse.PermanentDBs` | 0 | 22 |
| `MomoTalkOutLineResponse.MomoTalkOutLineDBs` | 0 | 1 |
| `AccountLevelRewardIds` / `PickupFirstGetHistoryDBs` | `[]` | 各 1 条 |
| `FriendCode` | `EsnjNyf` | `slmv4wc` |

> ⚠️ `MomoTalkOutLineDBs` 为空时，官方每条元素里的 `CharacterId` 键在我们这边**不存在**——
> 这是"空列表"的必然结果，**不是缺字段**（我们的空列表里根本没有元素可比）。

---

## 3. `LobbyMode` / `MemoryLobbyUniqueId` 单独判定（lead 点名）

| 字段 | 在我们响应里存在吗 | 值 | 官方 | 判定 |
|---|---|---|---|---|
| `LobbyMode` | **存在**（在 `Account_Auth.AccountDB` 里） | **1** | **0** | **值不对**，不是被吞 |
| `MemoryLobbyUniqueId` | **存在**（同上） | `0` | `0` | 一致 ✅ |
| `MemoryLobbyDBs` | **存在**（`LoginSync.MemoryLobbyListResponse`） | 1 条，`MemoryLobbyUniqueId=13010` | 1 条，`13010` | 一致 ✅ |

**重要澄清**：`LobbyMode` / `MemoryLobbyUniqueId` **不在 `Account_LoginSync` 里**，它们在
**`Account_Auth` 的 `AccountDB`** 里。所以"LoginSync 对比"这一层永远看不到它们——
黑屏要查的是 Auth 那份。

---

## 4. 真正的差异：`Account_Auth` 的 `AccountDB`（22 vs 23 字段）

| 字段 | 我们 | 官方 | 判定 |
|---|---|---|---|
| `ServerId` | `10000000001` | `10015354380` | 账号不同，正常 |
| **`RoleId`** | **缺失** | `10015354380` | **D3 官方有我们无** |
| `Nickname` | `老师0002` | `111` | 正常 |
| `CallName` | `老师` | `""` | 正常 |
| `DevId` | `1013178778` | `1013178778` | 一致 |
| `State` | `1` | `3` | 值不同（语义未知） |
| `Level` / `Exp` | `1` / `0` | `32` / `174` | 进度差异 |
| `Comment` | `""` | `""` | 一致 |
| **`LobbyMode`** | **`1`** | **`0`** | **D2 重点** |
| **`RepresentCharacterServerId`** | **`1100001`** | **`3002866`** | **D1 最重点（见 §5）** |
| `MemoryLobbyUniqueId` | `0` | `0` | 一致 |
| `LastConnectTime` | `2026-11-17T19:39:26.xxx` | `2026-11-16T04:30:54.556129837` | 格式一致 |
| `BirthDay` | `1970-01-01T00:00:00` | `0001-01-01T00:00:00` | 值不同（1970 像哨兵值） |
| `CallNameUpdateTime` | `2026-11-16T06:05:08.xxx` | `0001-01-01T00:00:00` | 值不同 |
| `PublisherAccountId` | `1013178778` | `0` | 值不同 |
| `RetentionDays` | `1` | `0` | 值不同 |
| `CreateDate` | `2026-11-16T06:05:08` | `2026-06-06T11:44:27.139` | 正常 |
| `UnReadMailCount` | `0` | `0` | 一致 |
| `VIPLevel` | `0` | `0` | 一致 |
| **`LinkRewardDate`** | 有，`null` | **无此键** | **D4 字段名错** |
| **`LinkRewardDateDate`** | **缺失** | `0001-01-01T00:00:00` | **D4 官方有我们无** |
| `Location` | `""` | `浙江省` | 展示用 |
| `LastReturningDate` | `null` | `2026-11-11T04:00:00` | 值不同 |

**顶层另有 3 处键名差异（Auth 响应本体）**：

| 键 | 我们 | 官方 |
|---|---|---|
| `OpenConditions` | **无** | 有（值 `null`） |
| `StaticOpenConditions` | 有（dict 55 项） | **无** |
| `Desc` | 有（`""`） | **无** |

> `StaticOpenConditions` / `Desc` 是"多发"（未知键被 Newtonsoft 忽略，无害）；
> `OpenConditions` 是"少发"（官方这份也是 `null`，影响小）。

---

## 5. D1 的证据：代表角色 id 在我们的角色表里**不存在**

| 检查 | 我们 | 官方 |
|---|---|---|
| `AccountDB.RepresentCharacterServerId` | **`1100001`** | `3002866` |
| `CharacterDBs` 里实际存在的 `ServerId` | `210001, 210002, 210003, 210004` | `3002866, 3002867, …`（46 个） |
| 代表角色 id 是否在角色表里 | **False** ❌ | **True** ✅ |
| 该 id 在整份 LoginSync 里出现次数 | **0** | **7**（角色表 / Echelon 主槽位等） |

⇒ **客户端要在大厅实例化一个"不复存在的角色"。** 这比任何值差异都更像"渲染全黑"的直接原因：
模型/立绘加载失败 → 加载协程挂在 `yield` → 屏幕保持黑、进程不死、点屏仍有动画（正是 lead 描述的现象）。

**为什么"第一次进大厅正常、返回必黑"（推断，中）**：
首次进入时客户端可能用默认展示角色/未读缓存；重建大厅时才去读缓存里的 `AccountDB`
（`Report\47`/`Report\48` 已证明 AccountDB 是客户端保存的账号主体）。这条与观测吻合，但没有动态证据。

---

## 6. 结论只写能证的

**能证的**：
1. `Account_LoginSync` 结构 35/35 完全对齐，**不缺字段**（逐层 0 差异）。
2. `LobbyMode`、`MemoryLobbyUniqueId` **都没有被 `DefaultValueHandling.Ignore` 吞掉**；
   `LobbyMode` 我们发的是 **1**，官方是 **0**。
3. 我们 `AccountDB` 少 **2** 个官方字段：`RoleId`、`LinkRewardDateDate`；且 `LinkRewardDate` 是**错名**。
4. 我们 `RepresentCharacterServerId=1100001` **不在**我们自己的 `CharacterDBs`（只有 210001–210004）里；
   官方代表角色在其角色表里存在。

**不能证的（需要 X）**：
- `LobbyMode=1` 的确切语义：需要客户端侧枚举或官方抓包里出现 `LobbyMode≠0` 的样本（本 HAR 只有 0）。
- 「代表角色不存在 → 黑屏」的因果：需要一次单变量实验（见 §7），或 logcat 里有资源加载异常。
- 首次进入为何正常：需要动态 hook / 两次进入的日志对比。

---

## 7. 建议的最小实验（一次只改一个变量）

| 顺序 | 改动 | 阳性（判据） | 若阴性说明 |
|---|---|---|---|
| **E1** | `Account_Auth.AccountDB.RepresentCharacterServerId` 改成 **`210001`**（角色表里真实存在的那一个） | 从子界面返回大厅**不再黑屏** | 代表角色不是主因，转 E2 |
| **E2** | `AccountDB.LobbyMode` 改成 **`0`** | 黑屏消失 | LobbyMode 不是主因，转 E3 |
| **E3** | 补 `RoleId`（= ServerId）+ 把 `LinkRewardDate` 改名成 `LinkRewardDateDate` | 黑屏消失 | 这两个都不是主因 |

> E1 优先，因为它是唯一一条"数据自相矛盾"的（id 指向不存在对象），而不是"值可能与官方不同"。
> 三条都可单独上线、单独回滚。

---

# 9. ContentSave / Item / Academy 桩对比（2026-11-17 20:xx 追加）

## 9.0 先交代核对：上一轮的 1100001 是哪来的

**复跑方式**：对 `blackout_lo.pcap0` 重新做 TCP 重组 → 拆 HTTP → 解密，只看 `lo:9097`（桥接明文出口）两个登录轮次。

| 轮次 | 客户端端口 | 外层 requestid | 顶层键 | `AccountDB` 字段数 | `RepresentCharacterServerId` | `LobbyMode` | `ServerId` |
|---|---|---|---|---|---|---|---|
| 19:39:26 | 37040 | `976b95b8-5e0d-4fb5-9657-755bf75682e6` | 33 | 22 | **1100001** | **1** | 10000000001 |
| 19:42:10 | 55008 | `1d206ec6-3064-4c34-8c4b-82ed85cf93be` | 33 | 22 | **1100001** | **1** | 10000000001 |

原始字节（可反查，非二手转述）：
```
9097->37040  body(3500B) 前 60: KuJ9ksKTL+jHE8/xdi2Kz8de2/PUuc2w/p5JVdoxmtFvFUWgwMFJm1F56A7p
9097->37040  body(3500B) 后 44: kcpiB2veF66yLH4xgS04Swc5nF2IOi9tCeI0HLYFeio=
9097->55008  body(3500B) 前 60: 7MQwXNgVIkQYNE1kAC7J8j8k7OcrDDr/2TKo3+fanuOaV9aZUjpzhkJ7Hfuk
9097->55008  body(3500B) 后 44: W+b9jWXmF96C8BhAOm8xrlUaXU3DVAKb4KMpecKplK4=
```

**核对结论（只陈述能证的部分）**
1. 这个 `1100001` **不是**从 HAR（官方）带过来的——官方那条是 `3002866`；也不是把别的响应串过来的——
   两层 `json.loads` 都自证 `Protocol=1002`、外层 `protocol=Account_Auth`、`packet` 长度 2226。
2. 它与 **Shittim wire dump（9 键 / 9）不同**，两者**同时成立**的唯一解释是：
   **bridge 在中间改写/自造了 `AccountDB`**（wire dump 记的是上游 Shittim，9097 记的是发出去的）。
   旁证：本仓库 `work\ba\server\account_service.py:904-906` 就是这个形状——
   `'LobbyMode': int(account.lobby_mode if ... else 1)`、`'RepresentCharacterServerId': int(... or 0)`，
   且在 `:1354` 的断言里出现 `[1100001, 1100002, 1100003]`。
3. **因此：D1/D2 撤回**（按 lead 指示），但**建议 srv-ops 用 bridge 日志按 `requestid=1d206ec6-...` 确认这一枪到底转发给了谁**：
   若 bridge 真的自造 `Account_Auth`，那它自造的 `AccountDB` 才是客户端实际用的那份。

---

## 9.1 `ContentSave_Get`（协议 26000）——**结论：完全一致，不是缺陷**

**官方**（HAR #142，body 640 B，packet 321 字符，逐字）：
```json
{"Protocol":26000,"SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"},"ServerTimeTicks":639304002556071764,"ServerNotification":0,"RequestId":"8fed57eb-2667-4db5-8562-e2eb1aa80ece","HasValidData":false,"ContentSaveDB":null,"EventContentChangeDB":null}
```

**我们**（pcap 9097→37102，body 600 B，packet 283 字符，逐字）：
```json
{"Protocol":26000,"SessionKey":{"AccountServerId":2,"MxToken":"a1386fce-e975-4b57-bcac-9e82e8b960bd"},"ServerTimeTicks":639305123666448440,"ServerNotification":0,"RequestId":"8c7bab48-1d0f-4625-bc53-73695f7c3166","HasValidData":false,"ContentSaveDB":null,"EventContentChangeDB":null}
```

| 键 | 我们 | 官方 | 判定 |
|---|---|---|---|
| `Protocol` | 26000 | 26000 | 一致 |
| `HasValidData` | **false** | **false** | 一致 |
| `ContentSaveDB` | **null** | **null** | 一致 |
| `EventContentChangeDB` | **null** | **null** | 一致 |
| `SessionKey` / `ServerTimeTicks` / `ServerNotification` / `RequestId` | 有（不同账号） | 有 | 一致 |

**⇒ 键数 8 vs 8，缺 0 个；语义逐字段相同。**
600 B vs 640 B 的 40 字节差**全部来自** `AccountServerId`（2 vs 10015354380）、`MxToken`（GUID 36 vs 64 字符）、
`RequestId`、`ServerTimeTicks` 这几个短字段，**不是内容缺失**。

> **对 lead 假设的结论**：`ContentSave_Get` 虽然是桥接桩（日志 `handled-26000`），
> 但它返回的正是官方在同一位置返回的东西（`HasValidData=false` + 两个 null）。
> **"大厅状态存在 ContentSave 里"这条在本抓包里不成立**——官方这个账号的 ContentSave 就是空的。

---

## 9.2 `Item_List`（4000，桩）

| 键 | 我们 | 官方 | 判定 |
|---|---|---|---|
| `Protocol` | 4000 | 4000 | 一致 |
| `ItemDBs` | **1 条** | **134 条** | 数量差（账号进度） |
| `ExpiryItemDBs` | 0 条 | 0 条 | 一致 |

首元素（逐字）：
```json
// 我们：{"Type": 4, "ServerId": 220001, "UniqueId": 2, "StackCount": 5, "IsNew": true}
// 官方：{"Type": 4, "ServerId": 24345539, "UniqueId": 2, "StackCount": 10, "IsNew": false}
```
**⇒ 键数 7 vs 7，缺 0 个；元素字段集合相同**（`Type/ServerId/UniqueId/StackCount/IsNew`）。差异只是"新号只有 1 件道具"。

---

## 9.3 `Academy_GetInfo`（24000，桩）

| 键 | 我们 | 官方 | 判定 |
|---|---|---|---|
| `AcademyDB` | dict(4) | dict(4) | 一致 |
| `AcademyLocationDBs` | **1 条** | **9 条** | 数量差（进度） |

首元素（逐字）：
```json
// 我们：{"AccountId": 10000000001, "LocationId": 1, "Rank": 1, "Exp": 0}
// 官方：{"AccountId": 10015354380, "LocationId": 1, "Rank": 2, "Exp": 0}
```
`AcademyDB` 内部均含 `AccountId / LastUpdate / ZoneVisitCharacterDBs / ...`（我们 4 键、官方 4 键）。
**⇒ 缺 0 个**，差异只是 `ZoneVisitCharacterDBs` 里的访问记录与 Location 数量。

---

## 9.4 三条桩的统一结论

| 接口 | 键数（我们/官方） | 缺 | 值差异 | 是否可能是黑屏原因 |
|---|---|---|---|---|
| `ContentSave_Get` (26000) | **8 / 8** | **0** | **无**（`HasValidData=false`、两个 null 逐字相同） | **否**（结构+语义完全一致） |
| `Item_List` (4000) | **7 / 7** | **0** | 1 vs 134 条 | 低（数量少，但客户端容忍空道具表） |
| `Academy_GetInfo` (24000) | **7 / 7** | **0** | 1 vs 9 个 location | 低（同上） |

**⇒ 三条桩都不存在"官方有、我们没有"的字段。** 黑屏原因不在这三个接口的结构上。
若仍怀疑是"数据太少"，那需要的是**种子数据补量**（角色/道具/剧情），而不是改响应格式。

---

## 9.5 没解的 / 解不出来的（诚实标注）

| 项 | 状态 |
|---|---|
| 8443（TLS 段）客户端实际收到的字节 | **未解**（TLS 加密，本次只解了 9097 明文段；9097→nginx 之后是否被再改写，**无证据**） |
| bridge 是否自造 `Account_Auth` | **未确认**（需要 bridge 代码或日志；本文只给了 9097 的字节事实与 `account_service.py` 的形状旁证） |
| `LobbyMode` 语义 | **未确认**（官方抓包只有 0；我们发 1 如果成立，语义仍未知） |
| 首次进大厅正常 / 返回必黑的机制 | **未确认**（需要动态观测） |

