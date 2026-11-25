# 里程碑：完整游戏链路打通（2026-11-17 19:30）

> 从「点登录就弹窗」到「进门 → 打仗 → 结算 → 回大厅」全链路可玩。
> 本文记录：**七个卡点的根因与修法、验证证据、遗留问题、可回滚点。**

---

## 一、最终状态

```
✅ 登录 / 存档持久化
✅ 教程跳过（不再重播）
✅ 进大厅 / 大厅交互
✅ 任务列表 / 编队 / 关卡进度显示
✅ 进入关卡 → 战斗 → 结算 → 回大厅   ← 今晚打通
❌ 战术地图玩法（6001/6003 那条路仍坏）
❌ 桃信 MomoTalk（数据 0 行，Shittim 未实现）
❌ 指导任务 GuideMission（8006 恒返回空，整条链路未实现）
```

---

## 二、七个卡点

### 1. `invalidprotocol` 弹窗

**根因（两层）**
- `cn_wrap_mode=a_proto_int` 让 `_cn_enc_b64`（`account_auth_probe.py:1588`）把**所有**走 `_cn_envelope` 的响应替换成 `Account_Auth(1002)` 的包
- `protocol_names.txt` 是垃圾表（159 行 Redis/IRC 错误码），导致协议名解析成 `"Unknown"`

**修法**
- FIX-1：补路径表 + 协议号表，兜底用请求路径机械转换
- FIX-3：relay 两条路径的信封构造器从 `_cn_envelope` 换成 `_cn_send_envelope`

**验证**
```json
改前 1005: {"protocol":"Account_Auth","packet":"{\"Protocol\":1002,...}"}
改后 1005: {"protocol":"Account_GetTutorial","packet":"{\"Protocol\":1005,\"TutorialIds\":[1,2]}"}
```

### 2. 教程每次从头开始

**根因**：桥的桩 `simple-1005` 恒返回 `TutorialIds: []`（`SIMPLE_TUTORIAL_IDS = ()`，`account_auth_probe.py:1984-1986`），与库里的真值脱钩。

**修法**：FIX-2，把 1005 移出 `RL2_HANDLED`（`L3286`），改走 relay → Shittim 真读 `AccountTutorials` 表。

### 3. 存档"不保存"

**真相**：存档一直是好的！客户端发 `[1]` → `[1,2]`，库里正是 `[1,2]`。
**问题**在客户端**读回来的是桩的 `[]`** → 以为一步没做 → 重播教程 → 每次重演。

**修法**：同 FIX-2。

### 4. 卡在「幽香记忆大厅」

**根因**：客户端与 Shittim **协议编号错位**。
```
客户端: Account_LoginSync = 1017
Shittim: Account_LoginSync = 1019，1017 = Account_DismissRepurchasablePopup
```
桥按数字透传 → 1017 打到错误 handler → 回空包 → 200 但内容无关。

**修法**：FIX-6，**建 token 权威反查表**——从 Shittim `Protocol` 枚举抽 501 个名字，逐个算 `b32md5(name)` 建表；客户端发的 token 一查就知道真名。优先级：① token 反查 → ② 原有手写表 → ③ 路径/编号表 → ④ 路径机械转换（会打标记）。
开关：`/www/wwwroot/bapatch/cn_nametoken.txt`

**验证**：`b32md5('Campaign_EnterMainStage') = 6CSZXRZ3CJRG5UW5JTKVFERYW4` = 客户端实际 token。

> 同一机制还修正了 `Campaign_Entermainstage`（错）→ `Campaign_EnterMainStage`（对），那一次是"点入场卡死"的直接原因——**数据全对，只是名字大小写错了一个字母，客户端就静默丢弃**。

### 5. 教程教程记录处于"半截"状态

**根因**：`AccountTutorials` 僵在 `[1,2]` —— 客户端读到"1、2 做完了" → 从第 3 步继续 → 第 3 步需要桃信/大厅数据 → 数据是空的 → 卡死。

**修法**：删掉那一行。`AccountHandler.cs:628-631` 语义：**无记录时返回 `1..27`（全部已完成）** ⇒ 整段教程被跳过。

**产品含义**：建号时 Shittim **不会**创建 `AccountTutorials` 行，所以**新号天然跳过全部 27 步教程**。

### 6. 战斗场景加载黑屏（`Location.z` 被吞）

**根因**：`HexLocation2D`（`Schale\MX\Campaign\Campaign.cs:68-73`）的 `x/y/z` 三个 `int` **没有任何序列化特性**，走网关全局的 `DefaultValueHandling.Ignore` ⇒ `z=0` 被整个吞掉 ⇒ 单位落在六边形格子外。

作者在 `Campaign.cs:65-67` 和 `HexaMapService.cs:87` 两处注释里都写明了：
> "z is load-bearing. … drop it on either side and every enemy lands off-lattice, the client can't build the strategy map."

同文件的 `SimpleVector3`（`Rotate` 用）有三个 `Include` 特性所以没事，`HexLocation2D` 漏了。

**修法**：给 `x/y/z` 三个属性各加 `[JsonProperty(DefaultValueHandling = Include)]`。

**⚠ 踩过的坑**：`HexLocation2D` 编译进 **`Schale.dll`**（Schale 项目），不是 `Shittim-Server.dll`。第一次只部署了后者，响应字节数一个都没变（1452 / 1900 → 1452 / 1900），白忙一轮。第二次部署 `Schale.dll` 后才生效（1452 → 1472）。

**验证**：`{"x":-1,"y":1}` → `{"x":-1,"y":1,"z":0}`，响应 +20 B。

### 7. 战术地图路径卡死 → 绕过

**现象**：`6001 EnterMainStage` → `5000 Echelon_List` → `5001 Echelon_Save` → `6003 DeployEchelon` → **客户端再也不发包**。黑屏转圈，无异常、无 ANR、无 D 状态线程、网络 10 秒零增长、15 分钟零新文件。

**排查结论**
- 服务端全 200、数据齐全、`Location` 三轴、零 ERR
- 客户端 native 栈：网络线程卡在 `poll()`；simpleperf 显示 CPU 96% 只是 Unity 渲染主循环（56% UnityMain），**不是业务死算**
- 客户端 DTO（`work/ba/proto/dto_schema_full_v2.json`）逐字段对比：`CampaignMainStageSaveDB` 29 字段、`HexaUnit` 22 字段；我们恒不发的字段里，**只有 `HexaUnit.Id = -1`（回传客户端的 -1）和 `SkillCardHand`（从未赋值）值得怀疑**
- **`ContentType` 曾被我误判为根因（说 Excel 里是 6）—— 复核后是 1，与主线关一致，我的解码把关号 `1011301` 看成了 `1011101`，该结论作废**

**绕过方案（已验证有效）**
用 GM 命令 `/unlockall campaign`（**注意前缀是 `/` 不是 `!`**）把 416 关标记为三星通关：
```
CampaignStageHistories: 0 行 → 416 行
Campaign_List 响应: 492 B → 205,164 B
```
客户端看到"已通关" ⇒ 改走 `6020 EnterMainStageStrategySkip` → `6021 MainStageStrategySkipResult`（Shittim 完整实现 + 官方抓包验证过的路径）⇒ **通了**。

**遗留**：完整战术地图玩法（6001/6003）仍然坏，玩家看不到六边形格子部署。

---

## 三、关键参考数据

### 官方 HAR 抓包（`report\_tmp\最全的一个.har`，201 条）
只包含跳过路径，**没有** `entermainstage`(6001) / `deployechelon`(6003)。

| 协议 | 官方 HAR | 我们（修复后） |
|---|---|---|
| `/account/loginsync` | 246,808 B | 122,968 B（**桥桩**） |
| `/mission/list` | 268,396 B | 3,500 B（**桥桩**） |
| `/campaign/list` | 44,672 B | 205,164 B（已填 416 关） |
| `/item/list` | 16,088 B | 640 B（**桥桩**） |
| `/academy/getinfo` | 17,560 B | 1,772 B（**桥桩**） |
| `/management/data` | 14,124 B | 2,092 B（**桥桩**） |
| `/mission/guidemissionseasonlist` | 160,216 B | **两个空数组** |
| `/account/auth` | 5,056 B | 3,520 B |
| `/campaign/entermainstagestrategyskip` | 2,072 B | 2,816 B |
| `/campaign/mainstagestrategyskipresult` | 10,284 B | 3,328 B |

**⇒ 桥的桩严重偏小（差 10~77 倍）。这是"能返回 200 但内容残废"的系统性问题。**

### 客户端 DTO 定义（权威）
`work/ba/proto/dto_schema_full_v2.json`（从 `global-metadata.dat` 提取）
- `CampaignMainStageSaveDB`: `:20477`（29 字段，`inherits: ContentSaveDB`）
- `ContentSaveDB`: `:35122`
- `HexaUnit`: `:62055`（22 字段）
- `CampaignDeployEchelonResponse`: `:18974`、`CampaignEnterMainStageResponse`: `:19299`

---

## 四、当前版本基线

| 部件 | 大小 | sha256 |
|---|---|---|
| `account_auth_probe.py` | — | `2475f231f196b4770a59e2376c6fda02fc8d29cdbca880a12d12603ffc400047`（FIX-1/2/3/6） |
| `cn_inner27.py` | — | `7793882d40231f588045862ee8b80f3c1f89e3202d2fda1d7f345150f3257208`（141 行） |
| `Shittim-Server.dll` | 2,669,568 B | `db4659340b1bca71f2d91f51de16352cac3428e54cfc5087e5f396fc1cfa24fc`（会话补丁 + 新构建） |
| `Schale.dll` | 5,392,384 B | `6745ee5f3a35b6c3b650f9a29e91c094eb8b06c77b4934447618a5432e35e98f`（含 `Location.z` 修复） |
| 服务 | — | `ba-shittim` active，dotnet pid 2619640，端口 6667/5000/5100 |

### 数据库状态
```
AccountTutorials        = 空表（新号也天然为空 → 跳过教程）
MemoryLobbies           = [(2, 13010)]        ← 手工插的幽香大厅
CampaignStageHistories  = 416 行（/unlockall campaign，全三星）
CampaignMainStageSaves  = 7 行（含 1 行脏数据 ServerId=2 StageUniqueId=0）
MomoTalkOutLines/Choices = 0 行
```

---

## 五、回滚点

```
# 数据库
/tmp/shittim.sqlite3.pre-stageclear.192220   sha 1134bd23a612a2d9e72839d92ba29fc221b8bda50bf162d41c97f83f04cad5e5

# Schale.dll（Locaton.z 修复之前）
/www/wwwroot/ba_srv/Schale.dll.pre-hexfix.191607      = 269c009a…（旧版）
cp -a 该文件 Schale.dll && systemctl restart ba-shittim

# Shittim-Server.dll（本轮构建之前，含会话补丁）
/www/wwwroot/ba_srv/Shittim-Server.dll.pre-hexfix.190912  = 01f5b906…
# 更原始（不含会话补丁，尽量别用）
/www/wwwroot/ba_srv/Shittim-Server.dll.orig.20261117-025444 = 2a97a922…

# 桥（FIX-6 之前）
account_auth_probe.py.fix6pre.190003   = 128c6ba9…

# 开关（不用改代码，秒回滚）
echo 0 > /www/wwwroot/bapatch/cn_nametoken.txt
```

---

## 六、待办（按优先级）

1. **把"跳过教程 + 关卡已通关 + 幽香大厅"做成建号种子** —— 否则每个新玩家踩同样的坑
2. **桥的桩全部退役，改为转发 Shittim** —— `1017 loginsync` / `4000 item/list` / `24000 academy` / `90004 management` / `26000 contentsave` / `90011` 目前是假数据，官方比自己小 10~77 倍
3. **实现 GuideMission（指导任务）** —— 8006 恒空；需要赛季表 + 建号播种 + handler + 进度推进，共 4 处
4. **实现 MomoTalk** —— 当前 0 行；幽香大厅的官方获取路径依赖它
5. **修 `MomoTalkHandler.cs:202-203`** 的 `amount == 0` 丢奖励 bug（本地已构建 `84517933…`，**它缺会话补丁，不能部署**，需重新构建）
6. **修 `ConcentrateCampaignManager.cs:265`** 的 `HpInfos` 泄漏 `0` 键
7. **修战术地图路径（6001/6003）** —— 真正的根因还没找到；候选：`HexaUnit.Id = -1`、`SkillCardHand` 缺失
8. **修复 1017/1019 编号错位** —— FIX-5b 未完成（锚点不唯一中止）；现在 1017 仍走桥桩
9. 清理 `CampaignMainStageSaves` 里的脏数据（`ServerId=2`, `StageUniqueId=0`）
10. 满级存档发放（GM 命令：`/max all`、`/currency`、`/giveall`、`/unlockall campaign|story`）

---

## 七、今晚学到的两条方法论

1. **协议名必须用 token 哈希反查，不能靠路径机械转换。** 一个字母的大小写差异（`Entermainstage` vs `EnterMainStage`）会让客户端静默丢弃整个响应——不报错、不弹窗、就是"点了没反应"。
2. **`DefaultValueHandling.Ignore` 是系统性陷阱。** 零值字段被静默吞掉，已在 `LobbyMode` / `MemoryLobbyUniqueId` / `Location.z` 三处咬人。凡是"零值有意义"的字段都必须显式 `Include`。
