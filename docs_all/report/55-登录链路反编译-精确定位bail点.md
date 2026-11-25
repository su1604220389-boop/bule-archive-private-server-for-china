# 55 · 登录链路反编译 — 精确定位 bail 点

> 时间：2026-11-14 05:0x–05:4x
> 性质：**纯静态**。未动手机、未动服务器配置、未连任何在线服务。
> 输入（只读）：
> `work\ba\audit\ba-work\x\lib\arm64-v8a\libil2cpp.so`（270,927,056 B，sha256 `5ac1cbe0…`，与 `ba-apk\` 副本同尺寸）
> `work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`（38,426,024 B）
> 工具：IG5/Ghidra headless（AARCH64，586,438 函数，**部分分析**）、自写离线解析器 `report\_tmp\meta\h*.py`、capstone 5.0.7
> 结论等级：**[确证]** 有可复跑输出；**[推断·强]** 结构证据充分；**[推断·弱]** 仅命名/形态证据

---

## 0. 一页结论

1. **「`global-metadata.dat` 表头被混淆 ⇒ `methodPointer` 拿不到」这条历史死结论，本轮作废。**
   头**只是 `XOR 0x66`**，表体**每 64 KB 固定把 `[0x1000,0x5000)` 这段 `XOR 0x66`**。解掉后 31 对 (offset,count) 严格首尾相接，`typeDefinitions`/`methods`/`images` 全部可解析。**[确证]**

2. **`0x0013F654` 那批"已知符号"是 metadata 文件偏移，不是代码地址。** **[确证]**
   （`LoginTask 0x0013F654` = 名字堆里 `"LoginTask"` 10 个字节的文件偏移 = `0xEC9C8 + StringIndex 339084`）
   **补丁组若按这些值去 `.text` 打补丁，一定是空打或打坏 metadata。**

3. **代码地址全部拿到了，并且用数量关系闭合验证过。** **[确证]**
   `BlueArchive.dll` 的 `Il2CppCodeGenModule` = `0xf90e080`，`methodPointerCount = 154,173`，
   `methodPointers = 0xfed01c0`；而 metadata 里 image0（20,410 个类型）的 `Σ method_count = 154,173`——**两边完全相等**。
   ⇒ `addr(methodIndex) = reloc[0xfed01c0 + methodIndex*8]`。
   - `HandleAccountAuthResponseMessage`(m20272, token `0x06004F31`) = **`0x008A3440`**
   - `OnLoginFinish`(m20273) = `0x008A36C0`　`ErrorAccountAuth`(m20276) = `0x008A42BC`　`OnLoginFail`(m20282) = `0x008A489C`

4. **★ 但 `HandleAccountAuthResponseMessage` 的机器码在磁盘上是被 ACE 编码的（不是可读 ARM64）。** **[确证]**
   同一函数在 `libil2cpp.so` 文件里 16 字节 = `9c 76 ca 59 61 a3 b1 f0 bd ef 89 30 c1 d5 69 87`，capstone 0 条指令。
   **整个 `HttpGameSession` 类（`Equals`/`GetHashCode`/`WaitForRequest`/`get_State`）也在编码页里。** **[确证]**
   ⇒ **离线给这个 handler 本体打字节补丁是不可能的**；唯一可行的补丁是改**重定位 addend**（data 段，见 §7.2），把该方法指针重定向到代码洞。

5. **`ParseProtocol` 是明文，已反汇编：它返回 `int`。** **[确证]**
   `0x00873A8844`（`NetworkService.ParseProtocol(string) -> int32`）。结尾是
   `cmp klass; b.ne → InvalidCastException` → `ldr w0,[x0]`（拆箱取 int32）。
   ⇒ **协议分发是按整型协议号（`Account_Auth` = 1002），不是按协议名。**
   **这直接修正 `report\50` 的 H1（"应回显 26 字符 token"）——分发根本不看字符串 token。**

6. **最关键判断：我们的响应在"被认领给待完成会话"这一步被静默丢弃，`HandleAccountAuthResponseMessage` 从未被调用。**
   置信度 **[推断·强]**（bail 点在 `HttpGameSession`/会话匹配层，而那一层整类在编码页，静态到不了）。

7. **补丁组现在可以动手的那一处**：`.rela.dyn` 文件偏移 **`0x1DF00F8`** 的 8 字节 addend（现值 `0x008A3440`），
   改成代码洞 `0xF2C2410`，就能把 `HandleAccountAuthResponseMessage` 整体劫持到明文可写的洞里。见 §7.2。

---

## 1. 方法学突破：metadata 其实可以完整解析

### 1.1 头 = 前 0x100 字节整体 `XOR 0x66`

```
raw   : 94 43 72 12 18 4b 9e ec | 66 67 66 66 a6 62 65 66 a6 63 65 66 …
^0x66 : （magic/version 仍伪）   | 00 01 00 00 c0 04 03 00 c0 05 03 00 …
                                  stringLiteralOffset=0x100 / count=0x304C0
```
`sanity = 0x12724394`、`version = 0xEC9E4B18` 是**仅有的两个伪字段**（就是为了挡 `0xFAB11BAF` 检查）。

### 1.2 31 对 (offset,count) 严格相接 **[确证]**

| pair | 表 | offset | count(B) | 判据 |
|---|---|---|---|---|
| 00 | stringLiteral | `0x00000100` | `0x000304C0` | end = 下一对 |
| 01 | stringLiteralData | `0x000305C0` | `0x000BC408` | |
| 02 | **string（名字堆）** | `0x000EC9C8` | `0x006C7C88` | **明文（key=0）** |
| 05 | **methods** | `0x008B2C14` | `0x009085BC` | `/36 = **263,095**` 整数 |
| 19 | **typeDefinitions** | `0x01F02148` | `0x002F2358` | `/88 = 35,116`（尾 56 B 填充） |
| 20 | **images** | `0x021F44A0` | `0x00001018` | `/40 = **103** 个 assembly |

判据不是猜偏移，而是每对的 `offset+count` **严格等于**下一对的 `offset`（唯一例外 pair08 前 4 B 对齐填充）。

### 1.3 表体：`XOR 0x66`，但每 64 KB 只有 `[0x1000,0x5000)` 这一段 **[确证]**

逐记录判 key（`h19_keymap.py`）在 `typeDefinitions` 区观察到周期性翻转：
`0x…5008 → 0x00`、`0x…1030 → 0x66`、`0x…5020 → 0x00`、`0x…1048 → 0x66` …

```
key(off) = 0x66   当 (off & 0xFFFF) ∈ [0x1000, 0x5000)
         = 0x00   否则
```
**这与 `report\17:484` 说的 `libil2cpp.so` "每 64 KB 约 12 KB 是 ACE 编码块"是同一套保护**，只是 metadata 这边是 16 KB。
解掉后：`typeDefinitions[0] = <Module>`（token `0x02000001`）、`methods[0] = get_value`（token `0x06000001`）。**[确证]**

> 细节：`typeDefinitions` 区里有 2,789 处相邻记录 token 互换（记录级重排），
> 但**方法号↔方法名↔declaringType 三者自洽**（`declaringType=3156` 与 `methodStart=20225 + 72` 区间闭合），不影响结论。

### 1.4 被本轮推翻/纠正的历史条目

| 历史说法 | 实际 |
|---|---|
| `report\47:186-194`、`report\48:49-53`「无函数体、`methodPointer` 拿不到」 | **本轮拿到了**（§2.4） |
| `report\34`「12 种 stride×phase 扫 methods 表 0 命中」 | 因为没解码；解码后 `/36` 一次命中 |
| lead 的"已知符号 `0x0013F654` …" | 是 metadata **文件偏移**，不是代码地址 |
| `report\50` H1「分发按 26 字符 token 匹配」 | **分发按 int 协议号**；`ParseProtocol` 返回 int（§4） |

---

## 2. 精确坐标

### 2.1 类型

| 名字 | type index | token | 方法区间 |
|---|---|---|---|
| `LoginTask` | **3156** | `0x02000C3E` | `[20225, 20297)` = 72 |
| `NetworkService` | 9965 | `0x020026EC` | `[65805, 65811)` = 6（**0 字段**） |
| `GameSessionManager` | 9970 | `0x020026F0` | `[65815, 65848)` = 33 |
| `HttpGameMessage` | 9977 | `0x020026FA` | `[65943, 65970)` = 27 |
| `HttpGameSession` | 9981 | `0x020026FC` | `[65975, 66011)` = 36 |

### 2.2 地址映射的闭合验证 **[确证]**

```
image0 (BlueArchive.dll, typeStart=0, typeCount=20410)
   Σ method_count            = 154,173
Il2CppCodeGenModule @0xf90e080
   +0x00 moduleName          = NULL（所以按名字扫不到它，这也是前几轮卡住的原因）
   +0x08 methodPointerCount  = 154,173   ← 与上式完全相等
   +0x10 methodPointers      = 0xfed01c0
⇒ addr(m) = RELA_ADDEND(0xfed01c0 + m*8)      （.rela.dyn 里 R_AARCH64_RELATIVE 的 addend）
```

其余 39 个模块也都解出来了（`BlueArchive.FirstPass.dll` / `BestHTTP.dll`(17,831) / `criware.dll` / `UnityEngine.UI.dll` …），
但 `BlueArchive.dll` 的 `moduleName` 是 NULL，只能靠"count 相等"认出来。

### 2.3 `LoginTask` 72 个方法（名字 + **地址** + token）

```
m20225 0x008A7DCF8 0x06004F02 CheckContinueCampaign          m20261 0x008A8217C 0x06004F26 ShowTTSDownLoadPopup
m20226 0x008A7E26C 0x06004F03 CheckContinueEventContent      m20262 0x008A822EC 0x06004F27 LoadCallNameLipSync
m20227 0x008A7E638 0x06004F04 CheckContinueStoryStrategy     m20263 0x008A823A0 0x06004F28 IsLoginStarted
m20228 0x008A7E8B0 0x06004F05 CheckContinueConquestBattle    m20264 0x008A823F0 0x06004F29 IsLoginFinished
m20229 0x008A7ECF8 0x06004F06 CheckContinueStoryMode         m20265 0x008A82440 0x06004F2A StartLoginWithAccountCheckYostar
m20230 0x008A7EF34 0x06004F07 ResetContinueStorySaveData     m20266 0x008A82694 0x06004F2B RetryLoginWithAccountCheckYostar
m20231 0x008A7F04C 0x06004F08 get_WaitingTicket              m20267 0x008A826DC 0x06004F2C SetAccountNickname
m20232 0x008A7F054 0x06004F09 set_WaitingTicket              m20268 0x008A82BCC 0x06004F2D SetAccountCallname
m20233 0x008A7F05C 0x06004F0A Initialize                     m20269 0x008A82CB4 0x06004F2E Close
m20234 0x008A7F580 0x06004F0B Release                        m20270 0x008A82F04 0x06004F2F CheckContinueWeekDungeon
m20235 0x008A7FAF0 0x06004F0C ErrorQueuingGetTicket          m20271 0x008A831BC 0x06004F30 CheckContinueSchoolDungeon
m20236 0x008A7FD6C 0x06004F0D HandleQueuingGetTicketResponseMessage
m20237 0x008A802C4 0x06004F0E ErrorAccountPassCheck          ★m20272 0x008A83440 0x06004F31 HandleAccountAuthResponseMessage
m20238 0x008A80394 0x06004F0F HandleAccountPassCheckResponseMessage
m20239 0x008A805F8 0x06004F10 ErrorAccountCheckYostar        m20273 0x008A836C0 0x06004F32 OnLoginFinish
m20240 0x008A806C8 0x06004F11 HandleAccountCheckYostarResponseMessage
m20241 0x008A8078C 0x06004F12 AccountAuthStart               m20274 0x008A8417C 0x06004F33 StartLoginWithAccountPassCheck
m20242 0x008A80C64 0x06004F13 ErrorAccountCreate             m20275 0x008A8258C 0x06004F34 StartLogin
m20243 0x008A80D34 0x06004F14 HandleAccountCreateResponseMessage
m20244 0x008A80ECC 0x06004F15 ErrorAccountNickname            m20276 0x008A842BC 0x06004F35 ErrorAccountAuth
m20245 0x008A81004 0x06004F16 HandleAccountNicknameResponseMessage
m20246 0x008A812BC 0x06004F17 ErrorAccountCallname            m20277 0x008A8438C 0x06004F36 SkipAccountCallname
m20247 0x008A813F4 0x06004F18 HandleSessionFinishedMessage   m20278 0x008A844AC 0x06004F37 onCreateStateEnd
m20248 0x008A81534 0x06004F19 ErrorContentSaveDiscard        m20279 0x008A84564 0x06004F38 HandleAccountCallnameResponseMessage
m20249 0x008A81708 0x06004F1A HandleContentSaveDiscardResponseMessage
m20250 0x008A81950 0x06004F1B RequestQueuingGetTicket         m20280 0x008A846AC 0x06004F39 RequestAccountPassCheck
m20251 0x008A81B10 0x06004F1C RequestQueuingGetTicketRetry    m20281 0x008A82014 0x06004F3A co_RelayPacketsProcess
m20252 0x008A8008C 0x06004F1D RequestAccountCheckYostar       m20282 0x008A8489C 0x06004F3B OnLoginFail
m20253 0x008A80458 0x06004F1E RequestAccountAuth            m20283 0x008A84A10 0x06004F3C co_SyncShopListTutorialGacha
m20254 0x008A81CB0 0x06004F1F RequestAccountCreate           m20284 0x008A84AD0 0x06004F3D CheckBeforehandGachaProceeding
m20255 0x008A81E50 0x06004F20 RequestAccountCallname         m20285 0x008A827C4 0x06004F3E RequestAccountNickname
m20256 0x008A80BA4 0x06004F21 StartRequestRelayPackets        m20286 0x008A84CC0 0x06004F3F .ctor
m20257 0x008A820BC 0x06004F22 co_SyncTutorialCompletionIds    m20287 0x008A84D20 0x06004F40 <AccountAuthStart>b__20_0
m20258 0x008A7DFBC 0x06004F23 RequestContentSaveDiscard      m20288 0x008A84DC4 0x06004F41 <AccountAuthStart>b__20_1
m20259 0x008A80A84 0x06004F24 ShowNicknamePopup              m20289 0x008A84E7C 0x06004F42 <HandleContentSaveDiscardResponseMessage>b__28_0
m20260 0x008A8119C 0x06004F25 ShowCallnamePopup               m20290 0x008A84E80 0x06004F43 <ShowTTSDownLoadPopup>b__40_0
                                                              m20291 0x008A84F14 0x06004F44 <ShowTTSDownLoadPopup>b__40_1
                                                              m20292 0x008A84F18 0x06004F45 <OnLoginFinish>g__CloseTitle|52_6
                                                              m20293 0x008A85048 0x06004F46 <SkipAccountCallname>b__56_0
                                                              m20294 0x008A850F4 0x06004F47 <SkipAccountCallname>g__TTSSaveAndRequestAccountAuth|56_1
                                                              m20295 0x008A85110 0x06004F48 <CheckBeforehandGachaProceeding>b__63_1
                                                              m20296 0x008A85270 0x06004F49 <CheckBeforehandGachaProceeding>b__63_2
```

### 2.4 网络层关键方法的地址 + **明文/编码页判定** **[确证]**

判据：从函数入口连续能解出的 ARM64 指令条数（≥8 = 明文；≤2 = ACE 编码页，磁盘上不可读）。

| method | 名字 | 地址 | 指令 | 判定 |
|---|---|---|---|---|
| 65805 | `NetworkService.ParseProtocol` | `0x0073A8844` | 12 | **明文 ✔** |
| 65806 | `ParsePacketString` | `0x0073A89E4` | 12 | 明文 ✔ |
| 65809 | `ParseReceivedString` | `0x0073A8F54` | 12 | 明文 ✔ |
| 65957 | `HttpGameMessage.DecodeResponse` | `0x006E12534` | 12 | 明文 ✔ |
| 65958 | `DecryptOrReturnOriginal` | `0x006E12680` | 12 | 明文 ✔ |
| 65960 | `IsSpecificErrorJson` | `0x006E12828` | 12 | 明文 ✔ |
| 65966 | `get_Protocol` | `0x006E12E68` | 12 | 明文 ✔ |
| 65838 | `GameSessionManager.CreateSession` | `0x0073AA334` | 12 | 明文 ✔ |
| 65831 | `RemoveSession` | `0x0073A9748` | 12 | 明文 ✔ |
| 65824 | `get_SessionQueueCount` | `0x0073A92FC` | 12 | 明文 ✔ |
| 20241 | `LoginTask.AccountAuthStart` | `0x008A8078C` | 12 | 明文 ✔ |
| 20253 | `RequestAccountAuth` | `0x008A80458` | 12 | 明文 ✔ |
| 20264 | `IsLoginFinished` | `0x008A823F0` | 12 | 明文 ✔ |
| **20272** | **`HandleAccountAuthResponseMessage`** | **`0x008A3440`** | **0** | **ACE 编码 ✘** |
| 20273 | `OnLoginFinish` | `0x008A36C0` | 2 | 编码 ✘ |
| 20276 | `ErrorAccountAuth` | `0x008A42BC` | 0 | 编码 ✘ |
| 20282 | `OnLoginFail` | `0x008A489C` | 0 | 编码 ✘ |
| 66000 | `HttpGameSession.Equals` | `0x006E13E38` | 0 | 编码 ✘ |
| 66007 | `HttpGameSession.WaitForRequest` | `0x006E13594` | 0 | 编码 ✘ |
| 65981 | `HttpGameSession.get_State` | `0x006E13158` | 0 | 编码 ✘ |

> **这个表就是本轮最硬的工程情报**：登录卡死点所在的整条"会话匹配"链（`HttpGameSession` 全类）
> 与 `HandleAccountAuthResponseMessage` 本体**都在 ACE 编码块里**，离线反汇编拿不到；
> 而它前面那一层（解析、错误分支、建会话）**全是明文，可以随便看**。

---

## 3. 调用链图（本轮实证版）

```
BestHTTP 回调
   ▼
HttpGameMessage.DecodeResponse            0x006E12534  明文 ✔  （argc=3）
   ├─ DecryptOrReturnOriginal             0x006E12680  明文 ✔  （argc=3）  ← 加解密层（我们已复刻成功）
   │     └─(失败) HandleDecryptionError            （argc=1）
   ├─ IsSpecificErrorJson                 0x006E12828  明文 ✔  （argc=1）  ★ 错误信封专用分支
   │     └─(命中) → 全局错误 → 弹「认证服务器拒绝了请求」（**不经过任何 pending 会话**）
   ▼
NetworkService.ParseReceivedString        0x0073A8F54  明文 ✔
   ├─ ParseProtocol(this)                 0x0073A8844  明文 ✔  → **返回 int32**（协议号）
   └─ ParsePacketString(this)             0x0073A89E4  明文 ✔
   ▼
★★★ 会话认领（HttpGameSession 全类 = ACE 编码页，静态到此为止）
   GameSessionManager.CreateSession       0x0073AA334  明文 ✔
        └─ new HttpGameSession，然后把三个委托写到  +0x20 / +0x28 / +0x30
           （= ResponseHandler / NetworkErrorHandler / RequestHandler）
   HttpGameSession.Equals / GetHashCode / get_State   ✘ 编码页（但方法表证明它们存在且被重写）
   │
   ├─ 匹配成功 → ResponseHandler → IsFinished = true → 协程恢复 → m20272(0x008A3440)
   └─ 匹配失败 → **静默跳过**（无日志、无异常、无弹窗）→ IsFinished 恒 false
   ▼
HttpGameSession.WaitForRequest            ✘ 编码页
   └─ 永不完成 → LoginTask 协程永久挂起（report\48 §5 的 S1）
```

**逐层 bail 候选：**

| 层 | 地址/依据 | 判定条件 | 本轮结论 |
|---|---|---|---|
| L0 解密 | `0x006E12680` | AES/key 不符 | **已排除**（服务端加密复刻成功、canary 命中 7 次） |
| L1 错误分支 | `0x006E12828` | 响应体是 `{"protocol":"Error",…}` | **已排除**（我们发的不是 Error；且命中会弹窗） |
| **L2 协议号解析** | **`0x0073A8844`** | **`Protocol` 字段不是 int32** | **★候选**（见 §4） |
| L3 认领 | `HttpGameSession`（编码页） | 会话匹配不上 | **★主判**（见 §5） |
| L4 处理器内 | `0x008A3440`（编码页） | 内部早退 | 次可能；且与"不发第二条请求"矛盾（见 §5.3） |
| L5 等待 | `WaitForRequest` | — | **是现象不是原因** |

---

## 4. `ParseProtocol` 反汇编（明文，第 4 问的直接证词）

### 4.1 函数尾部（决定返回值的地方）—— `0x0073A89A4–0x0073A89E4` **[确证]**

```asm
0x073a89a4  adrp x8, #0xfa49000
0x073a89a8  ldr  x8, [x8, #0xc30]        ; 取某个静态类型对象
0x073a89ac  ldr  x9, [x0]                ; x0 = 解析出来的对象 → *(x0) = Il2CppClass*
0x073a89b0  ldr  x1, [x8]                ; 期望类型的实例
0x073a89b4  ldr  x8, [x9, #0x40]         ; 实际 klass
0x073a89b8  ldr  x9, [x1, #0x40]         ; 期望 klass
0x073a89bc  cmp  x8, x9
0x073a89c0  b.ne #0x73a89e0              ; ★ klass 不符 → 跳到 0x73a89e0
0x073a89c4  bl   #0x63c73b8              ; 拆箱（unbox / 取值）
0x073a89c8  ldr  w0, [x0]                ; ★★ 返回 int32（32 位读！）
0x073a89cc  ldp  x19, x30, [sp, #0x20]   ; 恢复现场
0x073a89d0  ldp  x21, x20, [sp, #0x10]
0x073a89d4  ldr  x22, [sp], #0x30
0x073a89d8  ret
0x073a89dc  bl   #0x63c73d0              ; ★ 抛异常（空引用/解析失败）
0x073a89e0  bl   #0x63c7768              ; ★ 抛 InvalidCastException
```

**读出三件事** **[确证]**：
1. **返回值是 `int32`**（`ldr w0,[x0]`，不是 `ldr x0`）⇒ 它解析出来的是**协议号**，`Account_Auth` = **1002**；
2. 有一处**类型检查** `cmp klass / b.ne` ⇒ 若 JSON 里的 `Protocol` 不是 `int`（比如是字符串 `"Account_Auth"`），
   走 `b.ne → 0x73a89e0 → bl 0x63c7768` **抛 `InvalidCastException`**；
3. 解析失败/为空走 `0x73a89dc → bl 0x63c73d0` **抛异常**。

**⇒ 第 4 问答案（前半）：分发表的"键"是整型协议号，不是协议名。**
`report\50` 的 H1（"把 `protocol` 回显成 26 字符 base32 token"）**方向错了** —— 客户端根本不拿字符串 token 去匹配。

### 4.2 函数头部（类型初始化 + 唯一正常的成功路径）—— `0x0073A88B0–0x0073A8924`

```asm
0x073a88b0  mov  w0, #0xf02f               ; 61487 = metadata usage 索引
0x073a88b4  mov  x1, xzr
0x073a88b8  bl   #0x8f1c120                ; il2cpp codegen 元数据初始化判定
0x073a88bc  tbz  w0, #0, #0x73a88e8        ; 已初始化 → 走主路径
0x073a88c0  mov  w0, #0xf02f
0x073a88c4  mov  x1, xzr
0x073a88c8  bl   #0x8f1c0a4
0x073a88cc  cbz  x0, #0x73a89dc            ; ★ 拿不到 → 抛
0x073a88d0  mov  x1, x19                   ; x19 = 入参（响应字符串）
0x073a88e4  b    #0x94e196c                ; 尾调用（迭代器/泛型共享桩）
0x073a88e8  mov  x0, x19                   ; ↓ 主路径：解析入参
0x073a88ec  mov  x1, xzr
0x073a88f0  bl   #0x6dba840                ; 「字符串 → 对象」第 1 跳
0x073a88f4  cbz  x0, #0x73a89dc            ; ★ 解析失败 → 抛
0x073a88f8  … 取静态 → 0x6dbaed4 → 0x6dc5d04 → 0xa604e48 → 0x9d93a9c（取字段/转换链）
0x073a89a0  cbz  x0, #0x73a89dc            ; ★ 字段取不到 → 抛
```
⇒ **`ParseProtocol` 只有 3 条 bail 分支，全部是"抛异常"，全部指向 `0x73a89dc` 或 `0x73a89e0`。**
它**没有**任何 `return 0/return null` 的静默分支 ⇒ 解析层不可能"静默"丢弃，只能是"抛了被上层 catch"。

### 4.3 这对我们的包意味着什么

| 我们外层/内层给什么 | `ParseProtocol` 行为 |
|---|---|
| 内层 `"Protocol": 1002`（int） | ✅ 正常返回 1002 → 进入认领 |
| 内层 `"Protocol": "Account_Auth"`（字符串） | ❌ `cmp klass → b.ne → InvalidCastException`（被 catch 后静默） |
| 内层完全没有 `Protocol` | ❌ `cbz x0 → 0x73a89dc` 抛（被 catch 后静默） |
| 外层 `"protocol": "Account_Auth"` | 若这个字符串被喂进 `ParseProtocol` ⇒ 同第 2 行 |

> `report\49` 已经把内层 `Protocol` 定成 `1002`(int)，所以**这一层现在应该是通的**；
> 若 srv-ops 实际没按 49 号上线（或又改回了字符串），这里就会**静默失败**。
> **这是一个 30 秒就能查的判据**：抓一次响应，确认内层 `"Protocol"` 是**裸数字**而不是引号包着的名字。

---

## 5. 最关键判断：被丢弃，还是进了处理器静默 return？

### 5.1 结论

> **在"会话认领"这一步被静默丢弃。`HandleAccountAuthResponseMessage`(`0x008A3440`) 从未被调用。**
> 置信度 **[推断·强]**（bail 点落在 `HttpGameSession` 整类，而该类在 ACE 编码页，静态不可读）

### 5.2 判据

| # | 判据 | 强度 |
|---|---|---|
| J1 | `NetworkService` **0 字段、6 个静态方法**（`ParseProtocol`/`ParsePacketString`/`ParseReceivedString`/`ShowDefaultNetworkError`/`GetIpAddress`/`.ctor`）⇒ 它只解析，**没有地方放分发表** | **[确证]** |
| J2 | `HttpGameSession` 与 `HttpGameMessage` **都重写 `Equals(1)`/`GetHashCode()`/`op_Equality(2)`/`op_Inequality(2)`** —— C# 里这是"要被当 `Dictionary` 键 / `HashSet` 元素"的专属指纹 | **[确证 指纹]** |
| J3 | `GameSessionManager.CreateSession`(`0x0073AA334`) 的实测行为：`new` 一个会话对象后，**只写三个委托字段**（`str x21,[x0,#0x20]!` / `str x20,[x0,#0x28]!` / `str x19,[x0,#0x30]!`，每处都跟 `bl 0x63c7260` 写屏障）⇒ 这就是 `ResponseHandler`/`NetworkErrorHandler`/`RequestHandler` 三件套 | **[确证]** |
| J4 | `HttpGameSession` 有 `get_SessionId`/`set_SessionId`、`get_State`/`set_State`、`SetSessionParameters(5)` ⇒ 会话有身份、有状态、要按身份被查找 | **[确证]** |
| J5 | 真服 Error 信封能弹窗，是因为 `IsSpecificErrorJson`(`0x006E12828`)**走全局分支、不需要匹配会话**；成功响应**必须**匹配会话。两者不是同一条路径 ⇒ 不能拿"Error 能弹窗"证明"我们的包被认领了" | **[确证 结构]** |

### 5.3 一条能**否掉"处理器静默 return"**的推理

若我们的包已被认领并进入 `HandleAccountAuthResponseMessage`，那么 `ResponseHandler` 就已经被调过
⇒ `IsFinished` 已置位 ⇒ `WaitForRequest` 已返回 ⇒ 协程已恢复（`report\48` 论证它是"yield 到条件为真"，不是死锁）。

协程一旦恢复，无论 handler 内部早退/异常/走错误分支，**必然有下一步动作**：
① 发下一条协议（`Account_CheckYostar` / `Account_Nickname` / `Queuing_*`，见 `report\42` 流程表）；
② 弹窗（`ErrorAccountAuth`→`OnLoginFail`，`0x008A42BC`→`0x008A489C`，或 `ShowDefaultNetworkError`）；
③ 至少写 `LoginState`（只有 `Finished`/`Failed` 两个值，`report\48:28`）。

**观测到的是三者全无 ⇒ 协程从未恢复 ⇒ `ResponseHandler` 从未被调用 ⇒ 包在认领阶段就被丢了。**

### 5.4 那"为什么没被认领"——候选按可能性排序

| # | 假设 | 依据 | 反证据 | 判定 |
|---|---|---|---|---|
| **H-A** | 会话按 **`Protocol` 整型号 + 某种会话标识**匹配；我们的响应里**缺会话标识**（真服三个外层键里我们唯一没有的 `requestid`） | `get_SessionId` 存在；`report\50` H2 | 客户端发请求时**没有**任何 requestid（`report\35` 明文 11 键里没有），服务端无从"回显"——除非它是客户端本地生成、回包时校验 | **[推断·强]** |
| **H-B** | 内层 `Protocol` 不是 int（或缺失）⇒ `ParseProtocol` 抛 | §4 的三条 bail 全是抛异常 | `report\49` 已定 `1002`(int) | **[推断·弱]**（但 30 秒可查，见 §4.3） |
| **H-C** | 会话匹配要求 `Encode`/`packet` 里的某段（如 `SessionId`）与服务端回包一致 | `SetSessionParameters(5)` 有 5 个参数 | 无 | **[推断·弱]** |

---

## 6. 给补丁组的建议

### 6.1 结论先行

- **不要按 `0x0013F654` 那批值去 `.text` 打补丁** —— 它们是 metadata 偏移，不是代码地址（§0.2）。
- **不要试图就地改 `HandleAccountAuthResponseMessage` 的机器码** —— 那 4 KB 在磁盘上是 ACE 编码的（§2.4）。
- **能打的地方只有两处**：`data` 段的重定位 addend（§7.2，唯一可行且干净），或**服务端信封**（§7.1，成本为零）。

### 6.2 最小修改（今天就能做，零成本）

按 §4.3 / §5.4，**先做这两个二值判据**，再决定要不要动二进制：

1. **查内层 `Protocol` 的类型**：必须是**裸数字 `1002`**，不能是 `"Account_Auth"`、不能缺。
   （判据：抓一次响应体，`grep -o '"Protocol":[^,]*'` 看到的是 `1002` 而不是带引号的名字。）
2. **补 `requestid` 并**回显**客户端发来的 26 字符 `protocol` 值**（H-A）：
   虽然 `ParseProtocol` 返回 int 说明**分发不看字符串**，但会话匹配可能还看 `SessionId`/`requestid`。
   做法：把请求 multipart 三个字段里的 `protocol` **原样**塞进响应的外层，并加一个 GUID 的 `requestid`。

**对照实验（同一轮，二选一就能定性）**：
- A 组：内层 `Protocol: 1002`（int）+ 外层 `protocol` 原样回显 + `requestid` 随机 GUID；
- B 组：与 A 组完全相同，但外层 `protocol` 填一个**明显错误**的值。
- 若 A 推进、B 不推进 ⇒ 外层字段参与匹配，问题定性闭合；
- 若 A、B 都不推进 ⇒ 匹配键既不是外层 `protocol` 也不是 `requestid`，转 §5.4 的 H-C。

### 6.3 若一定要在客户端二进制上下手：**唯一干净的落点**（已算出精确坐标）

因为 handler 本体不可改，正确做法是**改方法指针的重定位 addend**，把它整体劫持到**明文可写的代码洞**：

| 项 | 值 | 说明 |
|---|---|---|
| 目标方法 | `HandleAccountAuthResponseMessage`，methodIndex **20272** | §2.3 |
| 槽 vaddr | `0xFEF7B40` = `0xfed01c0 + 20272*8` | `methodPointers[20272]` |
| 槽在文件里的内容 | `00 00 00 00 00 00 00 00`（运行时由 loader 填） | 所以**改槽没用，要改 addend** |
| `.rela.dyn` 条目 | 文件偏移 **`0x1DF00E8`**（`r_offset=0xFEF7B40`, `type=1027 R_AARCH64_RELATIVE`） | |
| **★ addend 字段** | **文件偏移 `0x1DF00F8`，8 字节，现值 `40 34 8a 08 00 00 00 00` = `0x008A3440`** | **改这 8 字节** |
| 建议改成 | `0x00F2C2410`（代码洞，3056 B，`work/ba/bapatch/PROBE_README.md` 已实测可用） | 洞里前 32 B 全 0，可直接写 |

**为什么这条路能过 ACE**：`.rela.dyn` 是 `rodata`/数据页，不属于 `report\17:484` 那 739 个 ACE 编码的 `.text` 页；
且加载器在 `RELRO` 阶段会把这个 addend 写进 GOT 型槽 —— 与 `report\17:503` 说的"改 `MethodInfo::methodPointer`（data 段）"是同一手法。

**回滚**：把那 8 字节写回 `40 34 8a 08 00 00 00 00` 即可；建议补丁脚本先做 `expectedBytes` 校验再写（`work/ba/bapatch` 的既有风格）。

**注意事项**：
- 这个改动只影响 `LoginTask.HandleAccountAuthResponseMessage` 一个方法，**不会**影响其它任何协议；
- 但它**不能让 handler 被调用** —— handler 之所以没跑是因为**没被认领**。所以这条补丁只能用来**在洞里插入探针/强制推进**，
  例如在洞里实现"不管响应内容，直接调用 `LoginTask.OnLoginFinish`(`0x008A36C0`)"，用来**证明**卡点在认领层。
- 真正的"打通"仍然要回到 §6.2 的服务端信封对齐。

---

## 7. 未完成 / 下一步

**已闭合**：metadata 全解 → 类型/方法表 → 方法号 → 地址映射（用 `Σ method_count == 154,173` 闭合）→ 明文/编码页判定 → `ParseProtocol` 反汇编 → handler 的精确补丁坐标。

**未闭合（1 处）**：`HttpGameSession` 的 `Equals`/`WaitForRequest`/`get_State` 与 `HandleAccountAuthResponseMessage` 本体
**都在 ACE 编码页（磁盘不可读）**。要读它们，只有两条路：
1. **运行期**（手机）：等 ACE 解码完再 dump `/proc/<pid>/mem` 那几页 —— 但本轮硬约束是"不动手机"，未做；
2. **离线解码**：需要 ACE 的块解码算法。`report\17:484` 只测绘了编码块的位置（`work/ba/bapatch/encrypted_pages.txt`，183 区间），
   **算法本身尚未逆向**。这是目前唯一还有价值的静态缺口。

**复跑清单（全部只读，纯离线）：**

```powershell
$PY="C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd report\_tmp\meta
& $PY h1_header.py          # 头 XOR 0x66
& $PY h2_tables.py          # 31 对 (offset,count) 连续性
& $PY h19_keymap.py         # 每 64KB [0x1000,0x5000) 的 key 翻转
& $PY h20_global.py         # 全局解码 -> md_dec.bin
& $PY h11_methods.py        # 方法号 20272 / token 0x06004F31
& $PY h34_hgs.py            # 三个网络类的方法表
& $PY h12_so.py             # .rela.dyn（1,526,832 条 RELATIVE）
& $PY h38_bigmods.py        # 找 methodPointerCount=154173 的模块
& $PY h39_verify.py         # 验证 154173==154173 并列出 72 个地址
& $PY h40_pages.py          # 明文/编码页判定表
& $PY h42_rela_real.py      # handler 的 .rela.dyn addend 补丁坐标
& $PY show.py 0x73a8844 90  # capstone 反汇编 ParseProtocol
```

---

## 8. 置信度总表

| 结论 | 等级 |
|---|---|
| metadata 头 = `XOR 0x66`；表体每 64 KB 的 `[0x1000,0x5000)` = `XOR 0x66` | **[确证]** |
| 31 张表的 offset/count 布局（§1.2） | **[确证]** |
| `LoginTask` = type 3156，72 方法 `[20225,20297)` | **[确证]** |
| methodIndex ↔ 代码地址映射（`Σ=154173` 双侧相等） | **[确证]** |
| `HandleAccountAuthResponseMessage` = `0x008A3440` / `0x06004F31` / argc=1 / 同步 | **[确证]** |
| 该函数与 `HttpGameSession` 全类在 ACE 编码页（磁盘不可读） | **[确证]**（capstone 0 条指令） |
| `ParseProtocol` 返回 **int32**、有 `cmp klass / b.ne → InvalidCastException` | **[确证]** |
| 分发按**整型协议号**，不按协议名/token（推翻 `report\50` H1） | **[确证 汇编]** + **[推断·强 语义]** |
| `NetworkService` 6 静态方法、0 字段 ⇒ 无分发表 | **[确证]** |
| `CreateSession` 只写 3 个委托字段（+0x20/+0x28/+0x30） | **[确证]** |
| 分发 = 会话认领（session matching） | **[推断·强]** |
| **响应在认领阶段被丢弃，m20272 从未被调用** | **[推断·强]** |
| `WaitForRequest` 永不置位 = `ResponseHandler` 从未被调 | **[推断·强]** |
| 补丁坐标 `0x1DF00F8` → 代码洞 `0xF2C2410` 可行 | **[确证 结构]** / 实际过 ACE 未实机验证 **[推断·强]** |

---

## 9. 一句话给 lead

> **包的机器码和整个 `HttpGameSession` 都在 ACE 编码页里，离线读不到；但它的地址、token、补丁落点全算出来了。**
> **定性判断：没进处理器 —— 在"认领给待完成会话"那一步被静默丢了。**
> **分发用的是 int 协议号（1002），不是协议名，所以 `report\50` 那条"回显 26 字符 token"的假设方向不对。**
> 现在最便宜的一枪：确认内层 `Protocol` 是裸数字 `1002`，同时补 `requestid` + 回显外层 `protocol`，跑 A/B 对照。
