# 客户端拦截证据（招募 / 总力战 / 竞技场）

> 只读取证。未改客户端、未改服务端、未重启任何东西。
> 证据源：`global-metadata.dat`（解混淆副本 `report\_tmp\patch\md_deob.bin`）、
> `work\ba\audit\ba-work\x\lib\arm64-v8a\libil2cpp.so`（原厂 il2cpp，方法指针表 `ba_ptrs.bin`）、
> `work\ba\data\ExcelDB.db`（本地化表）、`work\ba\srv_live\20261118_2210\wire-2026-11-18.txt.gz`（明文协议日志）。
> 标注：**【已证实】**= 有地址/偏移/原文；**【推测】**= 有间接证据但未闭环；**【找不到】**= 明确没拿到。

---

## A. 招募：`ShopRecruits` 在哪、按钮读什么

### A1 结论
**【已证实】** `ShopRecruits` 是 `MX.NetworkProtocol.ShopGachaRecruitListResponse`（type[**11553**]）的第一个字段，
类型 `List<ShopRecruitDB>`（typeIdx **22823**），**字段偏移 `+0x50`**。
**【推测】** 客户端 UI 判断"能不能抽"读的就是这个列表（列表 null/空 ⇒ 没有可售卡池 ⇒ 不发 `Shop_BuyGacha*`）；
**但我没能在 UI 层闭环**，原因见 A4。

### A2 证据：DTO 与偏移（实测反汇编）
```
ShopGachaRecruitListResponse  type[11553]  MX.NetworkProtocol  fields=2
    <ShopRecruits>k__BackingField              typeIdx=22823   ← List<ShopRecruitDB>
    <ShopFreeRecruitHistoryDBs>k__BackingField typeIdx=22811

get_ShopRecruits @0x0E860884:  ldr x0, [x0, #0x50] ; ret      ← 偏移 +0x50（PLAIN）
set_ShopRecruits @0x0E86088C:  str x1, [x0, #0x50]!
```
```
ShopRecruitDB  type[12143]  MX.GameLogic.DBModel  fields=4
    <Id>k__BackingField            typeIdx=50531   (long)
    <SalesStartDate>k__BackingField typeIdx=42727  (DateTime)
    <SalesEndDate>k__BackingField   typeIdx=42727  (DateTime)
    <UpdateDate>k__BackingField     typeIdx=42727  (DateTime)
```
**⇒ `ShopRecruitDB` 只有 4 个字段：id + 三个日期。卡池内容（角色/概率）不在服务端响应里。**

> 注意：`ShopRecruitDB` 的 4 个 getter（`0x0D775014`/`024`/`034`/`044`）**全部落在 ACE 密文块**（可解率 0.00），
> 所以只拿到了字段名与类型索引，**没拿到它的偏移**。

### A3 招募 UI 的全部本地化文案（实测，`work\ba\data\ExcelDB.db`）

表：`LocalizeDBSchema`（18,456 行）；按关键词过滤后命中 211 行。与"抽卡被拦"直接相关的原文：

| rowid | 原文 |
|---|---|
| 3193 | `免费次数` |
| 3513 | `是否继续进行1次招募` |
| 3514 | `招募1次` |
| 3515 | `招募10次` |
| 3516 | `是否继续进行10次招募` |
| 3517 | `是否使用[c][007eff]{0}[-][/c]个青辉石购买[c][007eff]{1}[-][/c]信用积分\n并进行免费招募` |
| 3525 | `招募成员` |
| **768** | **`招募所需的招募券不足`** |
| 3302 | `离{0}剩余{1}:{2}:{3}` |
| 3521 / 3522 / 3595 | `距离结束剩余[c][50caff]{0}[-][/c]` / `距离过期剩余[c][50caff]{0}[-][/c]` |
| 3596 | `是否进行免费新手冲刺招募` |
| **3263** | **`开放期间 : 请参考官方社群公告`** |
| **3264 / 3265** | **`距离开放剩余{0}天{1}小时` / `距离开放剩余{0}小时{1}分`** |

> **注意：没有找到"此卡池不在开放期间""无法招募"这类硬拦截文案。**
> 表里只有「开放期间 : 请参考官方社群公告」与「距离开放剩余…」——**说明卡池不在期时客户端是"显示倒计时"而不是"报错拦下"**。
> 另外 `LocalizeErrorDBSchema`（429 行）里也**没有**招募相关错误行（17 条命中全是无关的编队/等级文案）。

### A4 【找不到】UI 层的拦截点
招募相关 UI 类很多（`UIGacha` type[7698] 20 字段、`UIBasicGachaButton` type[7630] 21 字段、
`UIPopupGacha_RecruitShop` type[6167] 11 字段、`UIGachaInfo` type[7635] 10 字段），
但**没能定位到读 `ShopRecruits` 的那个方法**：
* 对 `get_ShopRecruits`（`0x0E860884`）做了全 section `BL/B` 扫描，**直接调用点 0 个**
  —— 说明读取发生在 **ACE 密文块**内，或被 IL2CPP 内联，静态扫不到。
* **缺什么**：能解开 `0x0CCFxxxx` / `0x0E8xxxxx` 那批密文块的密钥，或运行期 hook `get_ShopRecruits`。

### A5 服务端该试的最小改动（无需客户端证据也能做）
既然 `ShopRecruitDB` 只有 `Id + 3 个日期`，且**客户端会拿 `Id` 去查本地 Excel（`ShopRecruitExcel`）**：
**把 `ShopRecruits` 从 `null` 改成一个非空数组，`Id` 用本地 Excel 里真实存在的招募 id，`SalesStartDate/EndDate` 覆盖当前时间。**
—— 这是 A 的唯一可执行结论（依据：字段形状实测 + `ShopRecruitExcel` 是客户端本地表，见前次报告）。

---

## B. 总力战：`RaidBattleDB.BIEchelon` 是什么

### B1 结论
**【已证实】`BIEchelon` 是 `string`（typeIdx 61196），字段偏移 `+0x40`，getter 是 `ldr x0,[x0,#0x40]; ret`。**
**【已证实】实测响应里它就是空字符串 `""`。**
**【推测】空串会让客户端解析出空的编队索引集合 → 战斗场景拿不到出战编队 → 拦截/重试。**

### B2 证据
```
RaidBattleDB  type[12101]  MX.GameLogic.DBModel  fields=10
    <ContentType>        typeIdx=41579    (enum)
    <RaidUniqueId>       typeIdx=50531    (long)     getter @0x0D77038C → ldr x0,[x0,#0x18]
    <RaidBossIndex>      typeIdx=50495    (int)
    <CurrentBossHP>      typeIdx=50531    (long)
    <CurrentBossGroggy>  typeIdx=50531    (long)
    <CurrentBossAIPhase> typeIdx=50531    (long)
    <BIEchelon>          typeIdx=61196    (★ string) getter @0x0D7703DC → ldr x0,[x0,#0x40] ; ret
    <IsClear>            typeIdx=37725    (bool)     getter @0x0D7703EC → ldrb w0,[x0,#0x48]
    <RaidMembers>        typeIdx=?
    <SubPartsHPs>        typeIdx=?
```
* **typeIdx 61196 = `string`** —— 与 `AccountDB.Nickname`、`AccountDB.CallName`、`FriendIdCardDB` 里那些字符串字段**同一个类型索引**，可交叉印证。
* 明文反汇编（实测）：
```
0x0D7703DC  ldr x0, [x0, #0x40]     ← BIEchelon
0x0D7703E0  ret
```
* 明文协议日志（实测，`wire-2026-11-18.txt.gz`）：
```
"RaidBattleDB":{"ContentType":10,"RaidUniqueId":8,"CurrentBossHP":50000000,
                "BIEchelon":"",                                  ← ★ 空串
                "RaidMembers":[{"AccountId":2,"AccountName":"111","CharacterId":9,
                                "DamageCollection":[]}], ...},
"AccountLevelWhenCreateDB":90}
```

### B3 【找不到】谁在解析它
对 `get_BIEchelon`（`0x0D7703DC`）做全 section `BL/B` 扫描：**直接调用点 0 个**。
`RaidBattleDB` 的**全部 20 个 getter 都无直接调用点**（`get_ContentType`、`get_RaidUniqueId`… 同样 0 个），
⇒ 调用方在 **ACE 密文块**，或被内联。
**缺什么**：解 `0x0CCF/0x0E86/0x0D77` 这几段密文；或运行期 hook `get_BIEchelon` 看调用栈。

### B4 一条可立即验证的服务端假设（【推测】中）
`BIEchelon` 是"出战编队 id 串"。**先试 `"1"`（单个编队号）**，若还不行试 `"1,2,3,4"`；
观察 83 次重发是否变成 1 次。**这条不需要客户端证据，一次实验就能定。**

> 同理：`ContentSaveDB` 里还有 `BIEchelon0..BIEchelon4`（type[11983]，typeIdx 全是 61196=string），
> **说明客户端对 BIEchelon 的用法是"字符串数组/逗号串"这一类**，不是数值。

---

## C. 竞技场：点"对战"前有哪些本地校验

### C1 结论
**【找不到】** `UIArena` 的本地校验逻辑**全部在 ACE 密文块**，静态无法给出判据。
**【已证实】** 三个关键事实：`UIArena` 39 个方法里 **34 个是密文**；`UIArenaUserInfo.selectButton` 存在；
实测三名对手的 `AccountServerId` **全是 4**、`PlayerRank=1`、`Rank=2`。

### C2 证据
```
UIArena  type[4172]  fields=11  methods=39
  fields: ArenaClosedObject, OpponentListObject, backButton, refreshButton,
          accountInfo, opponentsInfo, seasonClosingLabel, seasonInfoButton,
          <DefenseFormationPopup>k__BackingField, _autoRefresh, waitForRefresh
  方法状态（实测可解率）：
    get_needStackUIs              0x0CCF4F04 ENC
    Awake                         0x0CCF530C ENC
    Co_Loading                    0x0CCF5664 ENC
    OnOpened                      0x0CCF5964 ENC
    TryOpenSeasonGuide            0x0CCF5F2C ENC
    Initialize                    0x0CCF622C ENC
    Refresh                       0x0CCF65D4 ENC
    FindOpponentIndex             0x0CCF6834 ENC      ← ★ 名字最可疑
    SetOpponentUsers              0x0CCF63F4 ENC
    ApplyArenaOpened              0x0CCF62C4 ENC
    ShowNeedToRefreshPopup        0x0CCF51EC ENC      ← ★ 可能是"需要刷新"拦截
    HandleArenaOpponentListResponseMessage 0x0CCF69A8 ENC
    HandleNeedToRefreshArenaOpponentsMessage 0x0CCF6B14 ENC
    OnClickRefresh                0x0CCF5BCC ENC
    只有 .ctor 与 5 个编译生成包装是 PLAIN
```

```
UIArenaUserInfo  type[4195]  fields=10  methods=15（全 PLAIN）
  fields: characterCard, rankIcon, levelLabel, nameLabel, rankLabel,
          selectButton, arenaSetting, emblemParcel,
          <ArenaUserDB>k__BackingField, hideMyCards
  OnClickThis @0x0B7BAAD8（PLAIN）前段实测：
      取单例 → 取到 UIArena 实例 → SetActive 判断 → UIArena.set_AutoRefresh(false)
      → 继续（后续段落未逐条读完）
```
**⇒ 点击对手的执行入口是明文的，但它要调用的 `UIArena` 校验方法全在密文里。**

### C3 实测数据（明文日志）
```
Arena_OpponentList: {"Protocol":22003,"PlayerRank":1,
  "OpponentUserDBs":[
     {"AccountServerId":4,"RepresentCharacterUniqueId":530,"NickName":"Your Defense",
      "Rank":2,"Level":1,"TeamSettingDB":{"EchelonType":4,"LeaderCharacterId":10065,...}}, ...]}
Arena_EnterLobby: 同样 OpponentUserDBs[0].AccountServerId = 4
```
**【推测，中】三个对手 `AccountServerId` 全相同（=4）**很可能踩中
`FindOpponentIndex`（密文）或 `SetOpponentUsers` 的去重/定位逻辑，导致点击后找不到目标而不发 22004。
**依据**：方法名 `FindOpponentIndex` 直指"按对手查找索引"；三个相同 id 会让该查找不唯一。
**但这只是推测**，无法给出代码级判据（方法体密文）。

### C4 建议的最小实验（一次就能定）
把三名对手的 `AccountServerId` 改成 **4 / 5 / 6**（互不相同，且都不等于玩家自己），
其余字段不变，再点一次对战：
* **若 22004 发出来了** ⇒ 就是"对手 id 重复"这个拦截，问题在服务端造数据；
* **若仍然不发** ⇒ 拦截点与 id 无关，需要继续挖 `UIArena`（或改配 `PlayerRank`/`Rank` 关系）。

---

## D. 附：本机资源位置（供后续复核）

| 资源 | 路径 |
|---|---|
| `global-metadata.dat`（原厂） | `work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`（38,426,024 B） |
| 解混淆副本 | `report\_tmp\patch\md_deob.bin` |
| 方法指针表 | `report\_tmp\patch\ba_ptrs.bin`（154,173 × u64） |
| il2cpp | `work\ba\audit\ba-work\x\lib\arm64-v8a\libil2cpp.so`（270,927,056 B） |
| 本地化表 | `work\ba\data\ExcelDB.db`（`Localize*` 7 张表） |
| 明文协议日志 | `work\ba\srv_live\20261118_2210\wire-2026-11-18.txt.gz` |

**没有 `dump.cs`**（本机不存在 Il2CppDumper 输出）；上述结论全部由 metadata 类型表 + il2cpp 反汇编直接得出。
本轮新增脚本：`report\_tmp\meta\s33_gate.py`、`s34_localize_ui.py`、`s35_xref.py`。

---

## E. 三条一句话总结

| # | 结论 | 等级 |
|---|---|---|
| A | `ShopRecruits` = `List<ShopRecruitDB>` @`+0x50`，元素只有 `Id+3 日期`；本地化表**没有**"无法招募"类硬拦截文案，只有"开放期间/倒计时" ⇒ 卡池为空时更像"列表空"而不是"报错"。UI 层读取点在**密文**，未闭环。 | 字段 **已证实** / 拦截点 **找不到** |
| B | `RaidBattleDB.BIEchelon` = **string** @`+0x40`，实测值为 `""`；`ContentSaveDB` 还有 `BIEchelon0..4` 同类型 ⇒ 客户端按"编队号串"使用。解析方在**密文**。 | 类型/偏移 **已证实** / 解析方 **找不到** |
| C | `UIArena` 39 方法中 34 个密文，`FindOpponentIndex`/`SetOpponentUsers` 都在密文 ⇒ 校验逻辑**静态拿不到**；实测三名对手 `AccountServerId` 全为 4，是**最可疑**的触发条件。 | 校验逻辑 **找不到** / 重复 id **已证实**（现象） |
