# ID 卡全占位取证：服务端只发了 22 个字段里的 4 个（2026-11-18 02:50）

## 0. 用户判断被证实：**是服务端**
用户原话：「从官方 CDN 拿的资源绝对不可能有问题，绝对是我们服务端的问题」—— 成立。
本地 Excel 表已排除（`ExcelDB.db` 160,534,528 B、sha 与 root 机一致、TableBundles 6,232 个文件齐）。

---

## 1. 屏幕上看到什么（`work\ba\noroot\freeze_20261118\idcard_screen.png`，read_image 亲看）
```
ID卡
  Lv. 72
  username                      ← 用户说的"US name 占位符"，字面就是 username
  [Schale's Teacher]
  好友码：AAAAAAAAAA
  赛季纪录：上次总力战 0 / 上次大决战 0 / 战术对抗赛 100,000 / 上次无限制决战 100,000
  自我介绍：TEXTTEXTTEXTTEXTTEXTTEXTTEXTTEXTTEXTTEX / TTEXTTEXTTEXTTEXT
  OFFICIAL ▮▮▮▮▮
```
**这一整套（`username` / `TEXTTEXT…` / `AAAAAAAAAA` / `Lv. 72` / `100,000`）是 prefab 里预置的出厂占位文本**，
不是服务端"给了默认值"，而是**服务端给的值没有覆盖上去**。

同一屏 CPU（PID 4053）：`UnityMain 19.3% + UnityGfxDeviceW 22.5%`，画面静态却在烧
⇒ 与之前"硬冻"同形态（主线程忙等），**不是等级页专属**。

---

## 2. 服务端缺陷：`FriendIdCardDB` 有 22 个字段，`GetIdCard` 只填 4 个

### 2.1 权威定义（`Schale\MX\GameLogic\DBModel\DBModel.cs:1388`）
```csharp
public class FriendIdCardDB {
    public int Level                    { get; set; }
    public string? FriendCode           { get; set; }
    public string? Comment              { get; set; }
    public DateTime LastConnectTime     { get; set; }
    public long RepresentCharacterUniqueId   { get; set; }
    public long RepresentCharacterCostumeId  { get; set; }
    public bool SearchPermission             { get; set; }
    public bool AutoAcceptFriendRequest      { get; set; }
    public long CardBackgroundId             { get; set; }
    public bool ShowAccountLevel             { get; set; }
    public bool ShowFriendCode               { get; set; }
    public bool ShowRaidRanking              { get; set; }
    public bool ShowArenaRanking             { get; set; }
    public bool ShowEliminateRaidRanking     { get; set; }
    public bool ShowMultiFloorRaidClearedDifficulty { get; set; }
    public Nullable<long> ArenaRanking               { get; set; }
    public Nullable<long> RaidRanking                { get; set; }
    public Nullable<int>  RaidTier                   { get; set; }
    public Nullable<long> EliminateRaidRanking       { get; set; }
    public Nullable<int>  EliminateRaidTier          { get; set; }
    public Nullable<int>  MultiFloorRaidClearedDifficulty { get; set; }
    public long EmblemId                    { get; set; }
}
```
**⇒ 没有昵称字段。**

### 2.2 实际只填了 4 个（`FriendHandler.cs:107-126`）
```csharp
var card = account.ContentInfo.IdCard;
card.Level = account.Level;
card.FriendCode = AccountHandler.BuildFriendCode(account.ServerId);
card.LastConnectTime = account.LastConnectTime;
if (card.RepresentCharacterUniqueId == 0)
    card.RepresentCharacterUniqueId = account.RepresentCharacterServerId;
response.FriendIdCardDB = card;
```
桥端明文实测（`_ba_state/last_direct_envelope_plain.txt`）：
```
protocol = Friend_GetIdCard
FriendIdCardDB: {"Level":90,"FriendCode":"RRYHEALT","LastConnectTime":"2026-11-17T20:34:53","RepresentCharacterUniqueId":9}
```
⇒ **只有 4 个键**（其余被序列化配置省略，客户端落到默认值）。

### 2.3 为什么是默认值
```
ContentInfoDB.cs:21   public FriendIdCardDB IdCard { get; set; } = new();
```
新号 ⇒ `ShowAccountLevel / ShowFriendCode / ShowRaidRanking / ShowArenaRanking /
     ShowEliminateRaidRanking / ShowMultiFloorRaidClearedDifficulty` **全 false**，
     `Comment=""`、`CardBackgroundId=0`、`EmblemId=0`、各 Ranking=null。
`SetIdCard` 只有用户**主动保存过**才会写这些，现网账号从未保存过。

**⇒ 客户端判定"该玩家未配置 ID 卡"⇒ 保留 prefab 出厂文本 ⇒ 用户看到的全是占位符。**

---

## 3. 三个"等级"不一致（部分已解释，部分存疑）
```
账号信息页：等级 111（带铅笔）  90（大号）+ 满条 + 「最大值」
ID 卡：    Lv. 72
```
- `90` = `AccountDB.Level`（真实值，注入已生效，明文可证）✅
- 进度条满 + 只显示「最大值」= `IsMaxLevelExp()` 为真，**90 很可能是该版本满级** ⇒ 按设计只显示"最大值"，**属正常**
- `111`：il2cpp 已证明 `AccountInfo`（28 字段）用**独立属性 setter** 填充，键序不可能错位；
  `+0x20`=Nickname、`+0x44`=Level 都与反汇编吻合 ⇒ **不是我们的键序问题**
  ⇒ 111 的来源**存疑**，待查（可能是别的响应写入，或 prefab 默认，或截图行归属需再确认）
- `Lv. 72`：几乎肯定是 prefab 默认（整卡未刷新）

---

## 4. 修法（方向已定，方案待出）
```
C# 侧：GetIdCard 补全 DTO
  · 检测"从未保存过"（CardBackgroundId==0 或类似判据）→ 填一套合理默认
  · 或者：建号时初始化 IdCard 并落库
代价：需要重新构建 Shittim-Server.dll + **重启 ba-shittim**（唯一需要重启游戏服的操作）
现状：DLL 79fc88e5 已构建未部署；本次改动会叠加进去
```
已派 shittim-analyst 出方案（A 读取时补默认 / B 写库初始化），**不许部署**。

## 5. 待确认
```
① FriendIdCardDB 没有昵称字段 ⇒ ID 卡名字位客户端到底读哪个字段？（已派 il2cpp-analyst）
   a) MXAccount.AccountInfo.Nickname   b) 客户端 DTO 与服务端不一致   c) 纯 prefab 静态文本
② Show*=false 时客户端是「显示占位」还是「整块隐藏」？这决定补 Show* 能否修好那几格
③ 账号页那个 111 的真实来源
```

---

## 6. ★ 真根因（2026-11-18 03:00 定位，代码级）

### 6.1 `Friend_List` 从不返回玩家自己的 ID 卡
`Shittim-Server\Core\NetworkProtocol\Handlers\FriendHandler.cs:39-52`
```csharp
[ProtocolHandler(Protocol.Friend_List)]
public async Task<FriendListResponse> List(db, request, response)
{
    var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);
    response.FriendDBs = [];
    response.SentRequestFriendDBs = [];
    response.ReceivedRequestFriendDBs = [];
    return response;                    // ★ FriendIdCardDB / IdCardBackgroundDBs 从未赋值
}
```
`Schale\MX\NetworkProtocol\NetworkProtocol.cs:4253-4262`
```csharp
public class FriendListResponse : ResponsePacket
{
    public FriendIdCardDB? FriendIdCardDB { get; set; }              // ★ 玩家自己的卡，第一个字段
    public IdCardBackgroundDB[]? IdCardBackgroundDBs { get; set; }   // ★ 也从未赋值
    ...
}
```

### 6.2 客户端为什么因此整卡不刷新（反汇编实测）
```
UIIdCardObject.SetMyIdCard() @0x0A02B060
  0x0A02B1A8  bl  get_MyIdCardClone        ; MXAccount.FriendInfoObject
  0x0A02B1AC  cbz x0, 0xA02B770            ; ★ null → 整个函数直接 return
  0x0A02B288  ldr x8,[x0,#0x18]            ; MXAccount.AccountInfo
  0x0A02B294  ldr x1,[x8,#0x20]            ; 名字 ← AccountInfo.Nickname（不受 Show* 保护）
```
⇒ `Friend_List` 回的是 null ⇒ `MyIdCardClone` = null ⇒ `SetMyIdCard()` 第一行就返回
⇒ **整张卡保留 prefab 出厂文本**（`username` / `Lv.72` / `AAAAAAAAAA` / `100,000` / `TEXTTEXT…`）
⇒ 也解释了为什么 `userName` 那格不受 `Show*` 保护却仍是占位

### 6.3 用户实验佐证（决定性）
```
用户操作：点「编辑ID卡」→ 随便改 → 保存 → 加载一会儿 → 再进入
结果：**毫无变化，与原来完全一样**
解释：SetIdCard 写进了库，但读出来走的是 Friend_List（空）⇒ 画面不可能变
```

### 6.4 `Show*=false` 的行为（反汇编实测，5~6 个开关全覆盖）
```
0x0A02B2DC  ldrb [x20,#0x50] → ShowAccountLevel
0x0A02B364  ldrb [x20,#0x51] → ShowFriendCode
0x0A02B390  ldrb [x20,#0x52] → ShowRaidRanking
0x0A02B518  ldrb [x20,#0x53] → ShowArenaRanking
0x0A02B450  ldrb [x20,#0x54] → ShowEliminateRaidRanking
决定性一行 0x0A02B38C: csel x8, x27, x9, eq → ldr x1,[x8] → bl set_text
⇒ false 走的是"写静态占位文本"，与 true 共用同一个 set_text，**全程没有 SetActive(false)**
⇒ 补 true + 真实值能修好被 Show* 保护的格子；修不了 userName（它不读 FriendIdCardDB）
```

### 6.5 修法（补丁已成型，未应用未构建）
```
改动 1  FriendHandler.List 补两行：
          response.FriendIdCardDB      = BuildMyIdCard(account);
          response.IdCardBackgroundDBs = db.GetAccountIdCardBackgrounds(...).ToMapList(_mapper).ToArray();
        并把 GetIdCard 里那 5 行抽成 private static BuildMyIdCard()，两处共用
改动 2  SetIdCard 补漏掉的 ShowMultiFloorRaidClearedDifficulty（请求 DTO 有，赋值漏了）
改动 3  新账号默认值 —— **不猜**，取用户保存后落库的那套值做初始化基准
```
**⚠ 改动 1 单独上线会把"占位卡"变成"空卡"**（未保存过的号 `Show*` 全 false、`Comment=null`、`CardBackgroundId=0）
⇒ **改动 1 必须与改动 3 一起上**，否则观感未必更好。

