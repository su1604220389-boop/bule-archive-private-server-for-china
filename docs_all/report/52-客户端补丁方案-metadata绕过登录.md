# 52 · 客户端补丁方案：能不能靠改 `global-metadata.dat` 绕过登录

> 输入（只读）：`work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`
> （38,426,024 B，sha256 `2352cb570a4652cc76574b9eb87a2941cf906237ff1f1a80454ab1b5634b47e6`；
> 与 `bapatch\global-metadata_patched.dat.origbackup` 同一份，即**未打任何补丁的原文件**）
> 时间：2026-11-14
> 性质：**纯本地离线静态分析 + 脚本**。未连手机、未连服务器、未改任何线上文件。
> 脚本：`report\_tmp\md52\{probe52,hdr66,regkey,dump52}.py`、`scripts\md_scan.py`（子代理产出）、
> **交付工具 `bapatch\patch_metadata_bypass.py`**

---

## 0. 一页结论

**四条路，两条死、一条空、一条活着但绕不过登录。**

| # | 任务给的路径 | 判定 | 一句话理由 |
|---|---|---|---|
| 2 | **改方法体**（把某方法改成 `return` 常量） | ❌ **结构性不可能** | il2cpp 的 metadata **里根本没有方法体**。C# 的 IL 在构建期被翻成 C++ 再编成 `libil2cpp.so` 的 ARM64 指令；`global-metadata.dat` 只存反射元数据。`Il2CppMethodDefinition` 的字段里没有任何 body offset / IL offset。见 §2 |
| 3 | **参考 Shittim 的 `ClientMetadataPatchService.cs`** | ❌ **给不出答案** | 已从上游源码逐字核对：它只做两件事 —— **三段定长 RSA 公钥 PEM 等长覆写** + **region label 改名**。8 个 patcher 里没有任何一个"跳过登录"。"跳过登录"在 Shittim 里是**服务端开关** `BypassAuthentication`，不是客户端补丁。见 §3 |
| 1 | **改字符串字面量** | ⚠️ **机制可行，但绕不过登录** | 三条硬理由见 §4。最关键的一条：**客户端的协议 token 是运行时算的**（26 字符 token 在 256 个 key 下 **0 命中**，见 §6.3）⇒ 改协议名会同时改变"发出去的 token"和"期望回显的 token"，两侧同步漂移，**不产生任何新的可达状态** |
| 4 | **找登录相关关键字符串** | ✅ **做完了** | 全部真实偏移见 §6.2。**结论是"这些字面量里没有一个是判定开关"** |

**但这一轮不是白跑。** 撞了五份报告的"metadata 头部混淆 ⇒ 表读不到"那堵墙，**这一轮拆掉了**：

> **`global-metadata.dat` 的 header 就是整块 XOR `0x66`。**
> 解开后 **28/28 个区段严格单调、首尾相接、末段正好收在文件末尾附近**（§5）。
> 于是 `typeDefinitions` / `methods` / `parameters` / `fields` / `images` / `assemblies`
> 这些**此前被判定"读不到"的表，offset 全部可读**。
> 同时顺带**直接证实**了 `report\30` 的猜测：RSA 公钥三段确实落在
> `fieldAndParameterDefaultValueData` 区段里（§5.4）。

**所以这条线的正确用法不是"绕过登录"，而是"当客户端侧的独立变量"** —— §8 给了三个真正值得打的补丁，其中 **P-1 能一次性回答 `report\50` §8.0 里那个"E0 阳性有两种读法"的分歧**，而且**不需要动服务端**。

---

## 1. 先把"哪份是原始文件"钉死

| 文件 | 大小 | sha256 | 是什么 |
|---|---|---|---|
| `work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat` | 38,426,024 | `2352cb57…` | **原始**（从 APK 里取的） |
| `bapatch\global-metadata_patched.dat.origbackup` | 38,426,024 | `2352cb57…` | **与上面同一份**（`patch_metadata_key.py` 自己留的备份） |
| `bapatch\global-metadata_patched.dat` | 38,426,024 | `f0a30008…` | 已换过网关 RSA 公钥（差异 **337 B / 0.0009%**），**不是原始** |

本报告**全部偏移以原始文件（`2352cb57…`）为准**。
`report\39` §开头已注明：patched 版字符串区与原始逐字节相同，所以**字符串类偏移对两者通用**；
但 §5 的 header 区段表在 patched 版上同样成立（那边没改 header）。

---

## 2. 【硬结论 A】metadata 里没有方法体 —— 路径 2 结构性不可能

这一条本项目此前已经碰到过三次（`report\47:188`、`report\48:51`、`report\48` 附录 B.2），
但一直是以"取不到 `methodPointer`"的说法出现。这里把它讲成**架构事实**，免得再有人试：

### 2.1 il2cpp 与 Mono 的根本差别

| | Mono | **il2cpp** |
|---|---|---|
| 托管代码存在哪 | `.dll` 里的 IL 字节码 | **不存**。构建期 IL → C++ → **原生 ARM64 指令**，落在 `libil2cpp.so` 的 `.text` |
| `global-metadata.dat` 存什么 | — | **只存反射元数据**：类型/方法/字段/参数的**名字与索引**、字符串字面量、默认值、属性数据、metadata usage 表 |

本包的直接旁证：
- `report\01:227`：`assets/bin/Data/Managed/` 下**只有** `Metadata/global-metadata.dat`，**没有 `Assembly-CSharp.dll`**。
- `report\03:407`：Il2CppDumper 的输出是"**仅签名+地址，无函数体**"。
- `report\02`：`libil2cpp.so` 270,927,056 B，含 **3,461,254 条 `BL` 指令**（那是方法体）；
  metadata 只有 38.4 MB，全是数据。

### 2.2 `Il2CppMethodDefinition` 的表结构里没有"body offset"

```c
// il2cpp / Unity 2020.2+
struct Il2CppMethodDefinition {
    StringIndex          nameIndex;              // 方法名
    TypeDefinitionIndex  declaringType;          // 声明类型
    TypeIndex            returnType;             // 返回类型
    ParameterIndex       parameterStart;         // 参数表起点
    GenericContainerIndex genericContainerIndex;
    uint32_t             token;                  // metadata token
    uint16_t             flags;
    uint16_t             iflags;
    uint16_t             slot;
    uint16_t             parameterCount;
};   // 共 32 字节
```

**没有 `bodyOffset`、没有 `ilOffset`、没有 `rva`。** 方法体地址在
`libil2cpp.so` 的 `Il2CppCodeRegistration → Il2CppCodeGenModule → methodPointers[]` 里，
**是二进制里的一张指针表，不是 metadata 的字段**。

⇒ **"把一个方法改成 `return` 常量"在 metadata 上无法表达。** 这需要改 `libil2cpp.so`：
要么在**明文页**里改机器码（`.text` 有 26.2% 页被 ACE 编码，见 `report\17:484`），
要么改 `MethodInfo::methodPointer`（data 段）指向代码洞。
那属于"改 libil2cpp"这条线（`DEADENDS` D-19～D-29 已把大部分死法踩完），**不是 metadata 补丁**。

> **一句话**：任务里的路径 2 不是"难"，是**这个文件里没有那个东西**。

---

## 3. 【硬结论 B】Shittim 的 metadata 补丁不绕登录 —— 路径 3 给不出答案

已按任务要求去 GitHub 读了 `Neoexm/Shittim-Server` 的 `Services/ClientMetadataPatchService.cs`
（含同族 `ClientRegionLabelPatchService` / `ClientStoreUrlPatchService` / `ClientInfaceConfigPatchService`），
并用 git blob sha1 核对过抓到的是上游逐字节原文。完整研究落盘在
`report\_tmp\shittim_metadata_patch_研究.md`（963 行，含 434 行原文）。

### 3.1 它到底改什么

| 项 | 内容 |
|---|---|
| **改什么** | ① 三段**定长 ASCII 的 RSA 公钥 PEM**，原地**等长覆写**；② `region label`（`ServerRegion` 枚举成员名 + 独立字面量） |
| **在哪** | 源码注释自称载体是 `fieldAndParameterDefaultValueData`（**不是** `stringLiteralData`） |
| **怎么定位** | **全文件 AOB 内容扫描**（`TryLocateUnique`），要求**唯一命中**；找不到或歧义 ⇒ **一个字节都不写**（fail-safe） |
| **依赖标准 header 吗** | **不依赖**。全文 `BitConverter` **0 次**、`0xFAB11BAF` **0 次**、无任何 header 解析 ⇒ **我们的 `magic=0x12724394` 对它零影响** |
| **校验机制** | 不是 verify 而是 fail-safe + **边车文件** `{path}.shittim_patch.json` 存每段 offset + 原始/补丁 base64；关开关时**先比对"当前字节==补丁值"才回写原始值**，不等则拒绝。**无全文件 checksum、无写后重读校验** |
| **只碰 metadata 吗** | 是。该方法体**0 次**出现，纯字符串/字节覆写 |

### 3.2 它是不是"让客户端跳过登录"

**不是。** 8 个 patcher 全表（`Configuration/ConfigType/ServerConfig.cs`）：

```
AutoPatchClientMetadata        -> global-metadata.dat: RSA key + region label
AutoPatchClientSteamOffline    -> GameAssembly.dll（默认关）
AutoPatchClientGamescaleIas    -> gamescale.core.dll（登录端点）
AutoPatchClientInfaceConfig    -> inface 配置文件
AutoManageGrap64               -> 插件目录
AutoPatchClientBanners         -> ExcelDB.db 卡池行
AutoPatchClientStoreUrl        -> 商店 URL（唯一一个"真的改 URL"的）
RegionDisplayText              -> 标题页地区名
```

**没有任何一项是"跳过登录"。** 换公钥的目的是"让私服自己的私钥能解开 `50001` 握手"，
**不是**让客户端不校验登录。Shittim 里"跳过登录"是**服务端**的 `BypassAuthentication`（`Config.json`）。

### 3.3 那它对我们还有什么用？—— 两条方法论 + 一个交叉验证

1. **可复用（已内置进我们的工具）**：AOB 内容定位 + 唯一命中 + fail-safe；边车文件 + 双向比对回滚。
2. **可复用（已内置）**：**等长硬约束**。上游注释里那句"a PEM of any other length cannot go into them without shifting the section and every offset past it"就是铁律。
3. **交叉验证（意外收获）**：上游注释说上一代 key 的切分是 `150/150/150`，
   正好 = 我们国服实测的 `150/150/151` 去掉尾部换行 ⇒ **两侧同源，同一套机制**。
   国服实测三段：`0x0178CC60`(150) / `0x012D5F88`(150) / `0x0178CBA0`(151)，共 451 B，RSA-2048。
4. **不必移植这份 C#**：`bapatch\patch_metadata_key.py` 已经是同思路的**超集**
   （DER 结构验证 + 8 条硬断言 + 写后重读）。

> **一句话**：路径 3 的答案是"它没有绕登录的姿势，只有打补丁的姿势"。它教的**方法**我们已经在用；它**不能**回答我们的卡点。

---

## 4. 【硬结论 C】为什么"改字符串"改不出登录绕过

三条理由，一条比一条硬。

### 4.1 卡点的性质是"会话认领"，不是"某个判断判输"

`report\48` §0/§7 定死的机制：

```
LoginTask 协程
  └─ yield return HttpGameSession.WaitForRequest(...)   ← <WaitForRequest>d__59 @0x0021A802
       └─ 等 IsFinished == true                          ← @0x0021A583 / get_IsFinished
            └─ 只有 ResponseHandler / NetworkErrorHandler 被调用才置位
                 └─ 而 handler 是按"响应属于哪个 pending 会话"查出来的
                      └─ 查不到 ⇒ 两个回调都不调 ⇒ IsFinished 永不置位 ⇒ 协程永久挂起
```

字符串补丁能改的只有**比较的一方**（某个字面量）。而这里缺的是
**"这一包属于哪次请求"这个 key** —— 它在 `GameSessionManager` 的
`sessionQueue`/`sessionSet`（`0x21A0E1`/`0x21A0EE`）里，是**运行期对象**，
**不是 metadata 里的任何字面量**。改字符串碰不到它。

### 4.2 `LoginState` 没有"进行中"，也没有可被字面量影响的状态转移

`0x0013FDD3` 处实测：`LoginState\0Finished\0Failed\0`（只有两个成员）。
状态转移发生在代码里；**枚举成员名不参与任何比较**（C# 枚举比较的是值）。
把 `Finished` 改名成 `Failed` 不会让状态机前进或后退一格。

### 4.3 协议 token 是运行时算的 ⇒ 改协议名自相抵消（决定性，见 §6.3）

如果 token 是**预计算字面量**，改字面量就能改客户端发出去的协议 —— 那是真 bypass。
**实测不是**：三个 token 在 256 个单字节 key 下**全部 0 命中**，
且 `ToBase32String`@`0x1552E9`、`Base32`@`0x1552B5` 明文可读。
⇒ token 只能在运行时由协议名算出：

```
token = BASE32( MD5( UTF-16LE( 协议名 ) ) )
```

于是改协议名 ⇒ 请求 token 变、期望回显 token 也变 ⇒ **两边一起漂，等于没改**。
它唯一的剩余价值是当**探针**（看请求里的 token 是否随之变化），但**这个问题 §6.3 已经答了**，
所以这条探针也一并作废 —— **省下一次点击**。

### 4.4 顺手排除：把"认证失败"文案改成空串

`DEADENDS` D-44/D-46 已经证明：**"无弹窗" ≠ "成功"，而是"静默停住"**。
把失败文案改空，只会把**可见的失败**变成**不可见的失败**，一个字节都不会往前走。
更糟：它会毁掉 `btn_px` 像素判据（`_tmp\chkcard.py`）这个**唯一的现场观测通道**。

> **结论**：路径 1 **不能**绕过登录。它不是"没找到正确的字面量"，而是**这一类改动的作用域到不了卡点**。

---

## 5. 【本轮最大副产品】header 解开了：整块 XOR `0x66`

这一节是**计划外收获**，但它推翻了本项目五份报告反复引用的一条"墙"。单独列出来，因为它对**所有**后续静态工作都有用。

### 5.1 怎么发现的

原始 header 前 0x80 字节，注意到 **每个 int32 的高字节几乎都是 `0x66`**：

```
00000000  94 43 72 12 18 4b 9e ec | 66 67 66 66 | a6 62 65 66 | a6 63 65 66 | ...
                                  ^^^^^^^^^^^^ ^^^^^^^^^^^^ ^^^^^^^^^^^^
```

按 `^0x66` 试解：

```
raw[0x08:0x0c] = 66 67 66 66  -> ^0x66 -> 00 01 00 00 = 256
raw[0x0c:0x10] = a6 62 65 66  -> ^0x66 -> c0 04 03 00 = 197,824
raw[0x10:0x14] = a6 63 65 66  -> ^0x66 -> c0 05 03 00 = 198,080
                                        256 + 197,824 = 198,080   ← 结构恒等式
```

这不是巧合。**判据是整条链**，不是单点：

### 5.2 硬判据：28/28 区段单调、不重叠、首尾相接

| 判据 | 结果 |
|---|---|
| offset 落在 `[0x60, filesize)` | **28/28 ok** |
| `offset[i+1] == offset[i] + count[i]`（首尾相接，无空洞） | **28/28 ok** |
| 区段单调不回溯 | **28/28 ok** |
| 末段 `exportedTypeDefinitions` 结束于 `0x24A3664` | 文件末尾 `0x24A55A8`，尾部仅 8,004 B 未归属（对齐/尾巴） |
| 绝大多数 offset 16 字节对齐 | 是 |

**256 个单字节 key 里只有 `0x66` 能让这四条同时成立。** 这不是拟合，是唯一解。

### 5.3 解出来的完整区段表（这就是本项目此前拿不到的东西）

| 区段 | offset | count(B) | 尾部 | 备注 |
|---|---|---|---|---|
| `stringLiteral` | `0x00000100` | 197,824 | `0x000305C0` | = **24,728 条 × 8 B** |
| `stringLiteralData` | `0x000305C0` | 771,080 | `0x000EC9C8` | 字面量数据 |
| **`string`** | `0x000EC9C8` | 7,109,768 | `0x007B4650` | 标识符堆，**明文 key `0x00`** |
| `events` | `0x007B4650` | 14,520 | `0x007B7F08` | |
| `properties` | `0x007B7F08` | 1,027,340 | `0x008B2C14` | |
| `methods` | `0x008B2C14` | 9,471,420 | `0x011BB1D0` | |
| `parameterDefaultValues` | `0x011BB1D0` | 130,848 | `0x011DB0F0` | |
| `fieldDefaultValues` | `0x011DB0F0` | 983,268 | `0x012CB1D4` | |
| **`fieldAndParameterDefaultValueData`** | `0x012CB1D8` | 5,446,792 | `0x017FCE60` | **RSA PEM 三段全在这里** |
| `fieldMarshaledSizes` | `0x017FCE60` | 127,164 | `0x0181BF1C` | |
| `parameters` | `0x0181BF1C` | 3,126,900 | `0x01B17590` | |
| `fields` | `0x01B17590` | 2,303,880 | `0x01D49D18` | |
| `genericParameters` | `0x01D49D18` | 116,464 | `0x01D66408` | |
| `genericParameterConstraints` | `0x01D66408` | 7,048 | `0x01D67F90` | |
| `genericContainers` | `0x01D67F90` | 57,360 | `0x01D75FA0` | |
| `typeDefinitions` | `0x01D75FA0` | 56,580 | `0x01D83CA4` | |
| `images` | `0x01D83CA4` | 55,640 | `0x01D915FC` | |
| `assemblies` | `0x01D915FC` | 1,279,708 | `0x01EC9CD8` | |
| `metadataUsageLists` | `0x01EC9CD8` | 230,512 | `0x01F02148` | |
| `metadataUsagePairs` | `0x01F02148` | 3,089,240 | `0x021F44A0` | |
| `fieldRefs` | `0x021F44A0` | 4,120 | `0x021F54B8` | |
| `referencedAssemblies` | `0x021F54B8` | 6,592 | `0x021F6E78` | |
| `attributeData` | `0x021F6E78` | 27,960 | `0x021FDBB0` | |
| `attributeDataRange` | `0x021FDBB0` | 2,328 | `0x021FE4C8` | |
| `unresolvedVirtualCallParameterTypes` | `0x021FE4C8` | 1,616,208 | `0x02388E18` | |
| `unresolvedVirtualCallParameterRanges` | `0x02388E18` | 887,000 | `0x024616F0` | |
| `windowsRuntimeTypeNames` | `0x024616F0` | 148,124 | `0x0248598C` | |
| `exportedTypeDefinitions` | `0x0248598C` | 122,072 | `0x024A3664` | |

复现：`python bapatch\patch_metadata_bypass.py --header --in <原始 metadata>`
（自带"28/28 单调"断言，不成立会返回非 0）。

### 5.4 顺带确证：RSA 公钥的载体就是 `fieldAndParameterDefaultValueData`

`report\30` §8 当时写着"**未证实**：精确说出这三块属于哪个 metadata 区段……标注为
「与 `fieldAndParameterDefaultValueData` 一致，未直接验证」"。

现在**直接验证了**：

```
fieldAndParameterDefaultValueData = [0x012CB1D8, 0x017FCE60)
  PEM 段 A @0x0178CC60  ∈ 区间  ✅
  PEM 段 M @0x012D5F88  ∈ 区间  ✅（靠近区间头）
  PEM 段 C @0x0178CBA0  ∈ 区间  ✅
```

`report\30` 的猜测**成立**。这条可以改成确证。

### 5.5 这推翻了什么（要同步改口的地方）

下面这些位置都写着"header 混淆 ⇒ 表读不到"，口径需要修正为
**"只有前 8 字节（sanity/version）不可用，其余 28 个区段的 offset/count 全部可读"**：

| 位置 | 原话 | 应改为 |
|---|---|---|
| `INDEX.md` §1.7 | "头部被改写……标准 Il2CppDumper 静态解析不可行" | 仍不可行（Dumper 第一步校验 magic），但**"表读不到"这个理由作废** |
| `report\47:130-134` / §5.1 | "`AccountAuthResponse` 各属性的 CLR 类型不可知（metadata 表头混淆）" | **可读**：`typeDefinitions`@`0x1D75FA0` + `fields`@`0x1B17590` + `parameters`@`0x181BF1C` 全部有 offset |
| `report\48` §2 / 附录 B.2 | "`typeDefinitions`/`typeSpecs` 的 offset 在文件头里，本包头被混淆，解析不了" | **不再成立**。这是"派静态任务问方法内部行为"以外的第二条路 |
| `report\34:344` | "头部加密导致 `fieldDefaultValues`/`typeDefinitions` 无法解析" | 同上 |
| `report\41:412` | "`typeIndex` 表读不到" | 同上 |

> ⚠️ **但仍有一条真墙**：`typeSpecs` 在 2020.2+ 的 header 布局里**不在**我们解出的 28 段中
> （我们解出的顺序是 …… `genericContainers` → `typeDefinitions`，中间没有
> `nestedTypes`/`interfaces`/`vtableMethods`/`interfaceOffsets` 这四段，且
> `genericContainers` 的尾部 `0x1D75FA0` **正好等于** `typeDefinitions` 的头部 ⇒ 这四段确实不存在）。
> 这说明本包的 header 是**较老布局**（或这四张表被合并）。`typeSpecs`（`typeSpecifications`）
> 同样不在其中 —— 所以"拿到字段的**完整 CLR 类型**"还需要额外一步
> （`typeDefinitions` 里只有 `byvalTypeIndex`，要回到 `Il2CppType` 表，而那张表在 `libil2cpp.so` 的
> `Il2CppMetadataRegistration` 里，不在 metadata）。
> 这一条**没有解决**，只是把边界从"整个 header"缩小到"`Il2CppType` 表在 so 里"。

### 5.6 还没解的部分（诚实标注）

| 项 | 状态 |
|---|---|
| 前 8 字节（`sanity` / `version`） | **未解**。256 个单字节 key 都不行：`^0x66` 后得 `0x741425F2` / `0x8AF82D7E`，都不是 `0xFAB11BAF` / 29。要么被单独改写，要么二次混淆。<br>**不影响功能**（loader 只用 magic 做校验，其余字段才是功能性的），但 `Il2CppDumper` 会因此拒绝 |
| `stringLiteral` 表（24,728 条 × 8 B） | **未解**。单字节 XOR 不行（最佳合法率 0.0028）。判据是 `(u32 len, i32 dataIdx)` 必须 dataIdx 单调、`idx+len ≤ 771,080` —— 试了全 256 key 全部不成立 ⇒ 该区段使用了比单字节 XOR 更强的混淆 |
| `stringLiteralData` 区段 | **逐条字面量各自一个 key**（不是区段统一 key）。所以"整区段找一个 key"这条路本身不成立，只能用 ×256 全扫按内容定位（这正是本项目一直以来的做法，也是本报告 §6 的做法） |
| `methods` / `typeDefinitions` 等二进制表的逐条解密 | **未做**。`methods` 区段在 `^0x66` 下能读出 `63 / 1 / 2191 / -1 ...` 形态的 `nameIndex`，说明**至少部分表是 `^0x66`**；但结构体大小与区段长度对不齐（`9,471,420` 不能被 0x20 整除），需要单独一轮 |

---

## 6. `global-metadata.dat` 的字符串全貌（任务路径 4 的答案）

### 6.1 key → 命中什么

| key | 命中数 | 解出什么 |
|---|---|---|
| **`0x00`** | **589** | **全部标识符**（`string` 堆，7.1 MB 明文）：`LoginState` `OnLoginFinish` `HandleAccountAuthResponseMessage` `Account_Auth` `Account_CheckYostar` `ResultState` `ErrorCode` `RelayPackets` `LoginTask` `CallbackUrl` `AddressablesCatalogUrlRoots` `IsGatewayBypassed` `ShowDefaultNetworkError` `HandleDecryptionError` `IsSpecificErrorJson` `PROTOCOL_HEAD_RESERVE` `FBENCRYPT_BLOCK_SIZE` `BEGIN PUBLIC KEY` |
| `0x66` | 121 | header 段表本身；`fieldAndParameterDefaultValueData` 里一小片；`JOSYdf8ys97uhFYS`@`0x12D172C` |
| `0xB5` | 3 | `http://test-ba.yostar.net:5210/api/state` @`0xC172B` / `0xC1756` / `0xC1781` |
| `0xFE` | 1 | `网络连接失败，请确认网络连接情况。` @`0x0EBD04` |
| `0xC7` | 1 | `请确认网络连接状态后重试。` @`0x0EBD3D` |
| `0x55` | 1 | `通知` @`0x0EBDAF` |
| `0xE9` | 1 | `JOSYdf8ys97uhFYS` @`0x07AA13` |

### 6.2 登录/协议相关字面量的真实偏移（全部 `key=0x00` 明文）

| 字符串 | 文件偏移 | 所属 |
|---|---|---|
| `LoginTask` | `0x0013F654` | LoginTask 类 |
| `HandleAccountAuthResponseMessage` | `0x0013FACF` | LoginTask 方法名 |
| `OnLoginFinish` | `0x0013FAF0` | LoginTask 方法名 |
| `SkipAccountCallname` | `0x0013FB54` | LoginTask 方法名 |
| `LoginState` | `0x0013FDD3` | 枚举（紧跟 `Finished`@`0x13FDDE` / `Failed`@`0x13FDE7`） |
| `WaitForRequest` | `0x0021A6D6` | `HttpGameSession` |
| `IsFinished` | `0x0021A587` | `HttpGameSession` |
| `IsSpecificErrorJson` | `0x0021A50F` | `HttpGameMessage` |
| `HandleDecryptionError` | `0x0021A4F9` | `HttpGameMessage` |
| `SessionStateChangedMessage` | `0x0021A02F` | `GameSessionManager` |
| `IsGatewayBypassed` | `0x00219EFE` | `GameSessionManager` |
| `ShowDefaultNetworkError` | `0x00219D3A` | `NetworkService` |
| `Account_Auth` | `0x0022D988` | **Protocol 枚举成员** |
| `Account_Auth2` | `0x0022DA5A` | Protocol 枚举成员（**注意：`Account_Auth` 是它的前缀，锚点必须带 `\0`**） |
| `Account_CheckYostar` | `0x0022DA24` | Protocol 枚举成员 |
| `Queuing_GetTicket` | `0x0022FC03` | Protocol 枚举成员 |
| `Queueing_GetAuthTicket` | **不存在** | ⚠️ 这个名字是本项目历史文档里编出来的，实际叫 `Queuing_GetTicket` |
| `PROTOCOL_HEAD_RESERVE` | `0x0025E39D` | `PacketCryptManager` |
| `FBENCRYPT_BLOCK_SIZE` | `0x00259C18` | `CryptAES` |
| `JOSYdf8ys97uhFYS`（IV） | `0x0007AA13`（key `0xE9`）/ `0x012D172C`（key `0x66`） | 字面量 |

协议枚举原文（`0x22D960` 附近，明文可读）：

```
...Account_Create / Account_Nickname / Account_Auth / Account_CurrencySync /
Account_SetRepresentCharacterAndComment / Account_GetTutorial / Account_SetTutorial /
Account_PassCheck / Account_VerifyForYostar / Account_CheckYostar / Account_CallName /
Account_BirthDay / Account_Auth2 / Account_LinkReward / Account_ReportXignCodeCheater...
```

### 6.3 ★ 决定性结论：协议 token 不是字面量（0 命中）

```
BASE32(MD5(UTF-16LE("Account_Auth")))        = AHTQLQI65FWJGGGK4KL5AEF57A   (26 字符)
BASE32(MD5(UTF-16LE("Account_CheckYostar"))) = PFJRUKK5IXXQR2XFFCMNXEIKXM   (26 字符)
BASE32(MD5(UTF-16LE("Queuing_GetTicket")))   = OZDJK2P2KZJ7GLQLOCAGCL6WXA
BASE32(MD5(UTF-16LE("Account_Nickname")))    = GVDSNCHUMIOS44NDTZM6ZPDDVQ
BASE32(MD5(UTF-16LE("Error")))               = QR7Z3TRUPDNW6BN4LPRZQUVTOU

×256 单字节 XOR 全扫：5 个协议名 × {ASCII, UTF-16LE} × 256 key = 2,560 次搜索
  ⇒ 全部 0 命中
宽松扫（`[A-Z2-7]{26,}` 全文件 × 256 key）：6,000+ 条命中，去掉重复字符噪声后
  没有一条等于上面任何一个 token ⇒ 不存在"预计算 token 表"
```

> ⚠️ **方法学补正（本轮踩过的一个坑，记下来免得复发）**：
> 第一版 `b32_nopad` 漏了"尾部不足 5 bit 的余数要左移补零再编一个字符"，
> 于是 16 字节 MD5 → 只出了 **25** 个字符（`…57` 少了尾巴 `A`）。
> 用**前缀**去扫其实仍会命中（前缀在字面量开头），所以"0 命中"的结论不受影响；
> 但**打印出来的 token 是错的**。已修 + 在 `patch_metadata_bypass.py` 里加了 import 期自检
> （`proto_token("Account_Auth")` 必须等于 `AHTQLQI65FWJGGGK4KL5AEF57A`，否则直接退出），
> 并用修正后的 26 字符重跑了上表。

**⇒ 客户端在运行时用 `ToBase32String(MD5(UTF-16LE(名字)))` 现算。**（`ToBase32String`@`0x1552E9` 明文存在）

这条的三重后果：
1. **改 token 字面量这条路不存在**（没有可改的东西）。
2. **改协议名会自相抵消**（请求 token 与期望回显 token 同步变）⇒ §4.3。
3. **`report\50` §5-E1（"外层 protocol 换成请求里那个 token"）的依据被削弱**：
   如果客户端也是现算，那它算出来的应该是同一个值 —— 那我们早就该成功了。
   **它没有。** 所以匹配**不是**"名字/p token 相等"这么简单，
   更可能是 §4.1 的"会话 key"另有其物。这条比"protocol 用名字还是 token"更根本。

### 6.4 明确不存在的字符串（避免再去找）

`SkipLogin`、`OfflineMode`、`CheatMode`、`DevLogin`、`认证失败`、`服务器处理请求失败`、
`2021.3.56f2`、`m_UnityVersion` —— 全部 0 命中。

> ⚠️ 注意「服务器处理请求失败。将返回标题画面。」是 `DEADENDS` D-44 的实测弹窗文案，
> 但它**不在 metadata**。与 `report\24:375` 的结论一致：**大部分 UI 文案走外部本地化表**
> （`LocalizeConfig.txt` + `TableBundles`），且**本地化表按 key 的 hash 索引**
> （上游文档原话："rows in the client's localization table are keyed by a hash of the
> localization key, so patching a row is how you change any UI string that never crosses the wire"）。
> 所以"**改 UI 文案**"这件事根本不该在 metadata 里做 —— 这是另一个文件的事。

---

## 7. 候选点总表（带偏移 / key / 预期 / 风险）

> 判据说明：**"能否绕过登录" 一列是本报告的核心输出**。
> 没有任何一行写 "✅ 能" —— 这是结论，不是遗漏。

| # | 候选 | 偏移 | key | 改成什么 | 预期效果 | 能绕过登录？ | 风险 |
|---|---|---|---|---|---|---|---|
| C1 | `LoginState.Finished` / `Failed` 成员名 | `0x13FDDE` / `0x13FDE7` | `0x00` | 任意等长 | **无**（枚举比较的是值，不是名） | ❌ | 低（但无收益） |
| C2 | `Account_Auth` 协议名 | `0x22D988` | `0x00` | 任意 12 字符 | 请求 token 与期望 token **同步**变化 | ❌ | 中（可能拼不出 token） |
| C3 | `Account_CheckYostar` 协议名 | `0x22DA24` | `0x00` | 任意 19 字符 | 无（handler 按枚举值绑定，改名不改 handler） | ❌ | 高 |
| C4 | `Error` 协议名 | 待精确定位（`Error` 命中多，需带 `\0` 锚） | `0x00` | 任意等长 | 客户端可能认不出错误包 | ❌ | 中（**可当探针，见 §8-P1**） |
| C5 | `ErrorCode` 键名 | `string` 堆，多处 | `0x00` | 任意等长 | `IsSpecificErrorJson` 可能失效 | ❌ | 中（**可当探针**） |
| C6 | `IsGatewayBypassed` | `0x219EFE` | `0x00` | 任意等长 | **无**（只是属性名；值在代码里 `new` 出来，不从 metadata 读） | ❌ | 低 |
| C7 | `http://test-ba.yostar.net:5210/api/state` ×3 | `0xC172B` / `0xC1756` / `0xC1781` | `0xB5` | 40 字符等长 URL | state 请求直奔我们（不依赖 DNAT） | ❌（但**去掉一层依赖**） | 低-中 |
| C8 | `JOSYdf8ys97uhFYS`（AES IV） | `0x7AA13` / `0x12D172C` | `0xE9` / `0x66` | 任意 16 字符 | 客户端解不开我们现有响应 | ❌ | **高（负收益）** |

**一句话**：C1~C6 全是"改一个名字"，名字不参与任何**判定**；
C7/C8 是"改一个数据"，改了只会让我们更难/更容易连上，与登录判定无关。

---

## 8. 真正值得打的三个补丁（不是绕过，是"给静默装观测"）

任务问的是"绕过登录"。答案是"绕不过"。但同一批工具能解决**当前真正的阻塞**：
`report\50` §8.0 那个分歧 —— **E0 弹「认证服务器拒绝了请求」的阳性，是"读法 A（全局错误扫描）"还是"读法 B（按内层 Protocol 路由）"？**
这个分歧决定后面 13 阶字段实验**要不要做**。目前只有服务端变量（R00）一种测法。**metadata 能提供第二种独立变量。**

### P-1（首选）★ 错误识别探针 —— 一次冷启动，分开读法 A / B

**设计原理**：如果错误识别是**内容扫描**（读法 A），它必然依赖某个**字面量键名**（`ErrorCode` / `Reason` / `IsSpecificErrorJson` 的比对串）。把这些键名在 metadata 里**等长改掉**，内容扫描就会**失效**；若错误识别是**按内层 `Protocol:-1` 路由**（读法 B），改键名**毫无影响**。

| 步骤 | 动作 |
|---|---|
| 1 | 打 C5：`ErrorCode` → 等长乱码（例如 `ErroxCode`）。**用本报告的工具，等长 + 唯一命中 + 边车回滚** |
| 2 | 冷启动 → 点一下 → 喂**真服错误包原文**（`{"Protocol":-1,"Reason":"sdk check failed,code: 100403","ErrorCode":1018}`），外层 `protocol` 保持 `"Account_Auth"` |
| 3 | 判读（二值，互斥） |

```
仍弹「认证服务器拒绝了请求」  ⇒ 读法 B（内层 Protocol 路由）
                              ⇒ report\50 §8 的 13 阶字段阶梯**有效**，可以开跑
弹窗消失 / 变成别的框        ⇒ 读法 A（内容扫描）
                              ⇒ E0 的阳性**不能**当作"分发到达 Account_Auth"的证据
                              ⇒ §8 阶梯失去前提，先回去做 H1（外层 protocol）
```

**为什么这条比 R00 好**：R00 改的是**服务端发送的内容**（`-1`→`1002`），
若客户端有"非法 Protocol 就静默"的分支，R00 的阴性会有两种解释；
P-1 改的是**客户端的比对基准**，阴性只有一种解释。
**两条一起做（R00 + P-1）就是 2×2 设计，能一次分开两个变量。**

**风险**：`ErrorCode` 同时是 `AccountCheckYostarResponse` 的字段名，
改掉会让该 DTO 的反序列化失效 —— 但我们在 P-1 里**不消费**那份 DTO，可接受。
**且 `--apply` 会先检查唯一性；若不唯一会拒绝，需先用 `--scan` 看命中数再定锚点。**

### P-2 把 `default_state_url` 的 3 处等长替换 —— 去掉 DNAT 依赖

```
现状: http://test-ba.yostar.net:5210/api/state      (40 字符, key 0xB5, 3 处)
可改: http://<我们的域名>/api/state                 （必须恰好 40 字符）
```

价值：这是**唯一**与游戏 API 有关的 URL 字面量（`report\11:156`）。
改成我们自己能解析的 40 字符域名后，`state` 请求**不再依赖 DNAT + SNI 分流**，
少一层"流量到底有没有到我们"的判读歧义（`DEADENDS` D-45 的整条证据链就卡在这上面）。
注意它原来就是 **`http` 不是 `https`** —— 少一层 TLS，风险更小。

### P-3（已作废，记录原因）协议名 oracle

原计划：改 `Account_Auth` → 看请求里的 token 变不变。
**§6.3 已经把这个问题的答案测出来了**（token 0 命中 ⇒ 一定是运行时算的）。
所以 P-3 **不必再花一次点击**。留在此处，是为了防止后来人重复设计这个实验。

---

## 9. 这条线真正的成本：三道**未验证**的闸门

前面所有分析都假设"补丁能被客户端加载"。这一节是**冷水**：这个前提在本项目里**从未验证过**。

### 闸门 1（最关键）：客户端到底从哪读 metadata —— **未知**

| 已知 | 出处 |
|---|---|
| APK 内是 `assets/bin/Data/Managed/Metadata/global-metadata.dat`（zip 条目，`extractNativeLibs=true` 但 `assets/` 不解压） | `report\30:336` |
| **设备外部存储里有一份 `il2cpp/Metadata/global-metadata.dat`** + `il2cpp/unity.ver = 611ecbd3-58f7-4b6d-8056-e955c461a84c` | `report\21:1116`（`persistentDataPath` 清单） |
| `libil2cpp.so` 里 `global-metadata.dat` 字符串**只有 1 处**（loader 的文件名），无法据此判断是 mmap 还是 read | `report\06:499`、`report\14:239` |

**这份 `il2cpp/` 目录是本路线唯一的低成本入口。** 它是可写的（`/storage/emulated/0/Android/data/<pkg>/files/`），
如果客户端真的从那里读，那么打补丁 = **一条 `cp`**，不需要重打包、不需要重签、不碰 ACE 的 APK 完整性面。

**一条命令就能验证**（不改任何东西，只读）：

```sh
# 1) 看两份是不是同一份、大小对不对
adb shell 'ls -l /storage/emulated/0/Android/data/com.RoamingStar.BlueArchive/files/il2cpp/Metadata/'
adb shell 'sha256sum /storage/emulated/0/Android/data/com.RoamingStar.BlueArchive/files/il2cpp/Metadata/global-metadata.dat'

# 2) 更硬的判据：进程运行时，看它有没有打开这个路径的 fd
adb shell 'ls -l /proc/$(pidof com.RoamingStar.BlueArchive)/fd 2>/dev/null | grep -i metadata'

# 3) 最硬：确认它是不是 mmap 了（maps 里会有 file-backed 行）
adb shell 'grep -i global-metadata /proc/$(pidof com.RoamingStar.BlueArchive)/maps'
```

> `report\11:282` 早写过同样的判据（"能看到一段 `…/global-metadata.dat` 且长度 ≥ 38 MB"），
> 但**从未真正跑过**。这是整条路线的第一个 5 分钟。

### 闸门 2：ACE 会不会因为 metadata 被改而杀进程 —— **未知，且从未实测**

| 库 | ACE 行为 | 证据 |
|---|---|---|
| `libunity.so` | **磁盘哈希钉死**（改 4 B → SIGBUS status=7） | `ba-pitfalls:50`、`DEADENDS` D-01 |
| `libil2cpp.so` | **不钉**（填充字节/代码洞/原位替换都活） | `ba-pitfalls:171`、`INDEX` A-31 |
| **`global-metadata.dat`** | **未知** | `report\30:386`、`INDEX` §4 仍是"尚未验证假设" |

我们的改动只有**几个字节**且**文件大小完全不变**，从"体积/布局"看不出破绽；
但若 ACE 对整文件做 CRC/SHA，一眼就抓。**这是纯实测题，没有静态答案。**
（`report\38:301` 里有一句"ACE 只钉 `libunity.so` 和 `global-metadata.dat`"，
但那是**转述**、无实验支撑，与 `INDEX` §4 的"未知"冲突 —— **不要采信它**。）

### 闸门 3：若必须在 APK 内改 —— 代价极高

`extractNativeLibs=true` 但 `assets/` 仍是 zip 条目 ⇒ 必须**重打包 + 重签 + 卸载重装**：

```
重打包 → 签名变 → 撞 ACE 的 sourceDir/签名完整性面（DEADENDS D-03/D-05 都死在这里）
      → 必须卸载重装 → 丢 /data/data（卡密登录态）+ 11 GB 资源要 mv 回来并 chown -R <新UID>:1078
      → 一次实验 = 半小时 + 一次 UID 变更风险
```

**对比**：P-1 只要"一次冷启动 + 一次点击"。所以**闸门 1 没确认之前，不要做任何需要重打包的补丁。**

---

## 10. 交付物

### 10.1 `bapatch\patch_metadata_bypass.py` —— 可执行的定点补丁工具

纯标准库（项目主机的 `python` 3.12 无 numpy，故**不依赖 numpy**）。

```bash
# 1) 解密并校验 header（28/28 单调断言，不过就返回非 0）
python bapatch\patch_metadata_bypass.py --header --in <原始 metadata>

# 2) 列出内置候选点 + 协议名→token 复算
python bapatch\patch_metadata_bypass.py --list

# 3) ×256 全 key 扫描（定位，40 个关键词）
python bapatch\patch_metadata_bypass.py --scan --in <原始 metadata>

# 4) 打补丁（等长，唯一命中，写前 8 条断言 + 写后 6 条复核）
python bapatch\patch_metadata_bypass.py --in <原始> --out <产物> \
       --apply 'proto_name_Account_Auth=Account_Auzh'

# 5) 复核 / 回滚（回滚前先比对当前字节==补丁值，不等则拒绝）
python bapatch\patch_metadata_bypass.py --verify   --in <产物>
python bapatch\patch_metadata_bypass.py --rollback --in <产物>
```

**设计要点（为什么长这样）**：

| 约束 | 实现 |
|---|---|
| **等长硬约束** | 长度不等直接 `REFUSING`。理由：`string` 堆是索引式、`stringLiteral` 表是 `(length, dataIndex)`，任何长度变化都会让后面所有索引失效 |
| **不按固定偏移定位** | 每个候选点用 **AOB ×256 单字节 XOR 现场重定位**，要求**唯一命中**；找不到/歧义 ⇒ 一个字节不写（fail-safe，抄上游 `TryLocateUnique`） |
| **处理前缀歧义** | `Account_Auth` 是 `Account_Auth2` 的前缀（`0x22D988` vs `0x22DA5A`）。候选可带 `terminator="\0"`：搜 `anchor+\0`、只替换 anchor |
| **处理多处相同串** | `default_state_url` 有 3 处同名。候选可带 `all=True`：要求三处同 key，全替换，并复核"旧值已全部消失" |
| **写前 8 条断言** | 锚点非空 / 新值非空 / 新旧不同 / 长度相等 / 纯可打印 ASCII / 偏移在文件内 / 不碰 header / 唯一命中 |
| **写后 6 条复核** | 大小不变 / 差异全在目标区间 / 差异字节数 / 逐处回读 == 新值 / 旧值已消失 / 重新定位 |
| **可回滚** | 边车 `<out>.bypass.json` 记录 offset/key/旧值/新值/两段 sha256/差异区间；`--rollback` **先验证当前字节等于补丁值**才回写旧值（否则拒绝，避免覆盖别人的改动） |
| **自动备份** | 写盘前 `copy2` 到 `<out>.origbackup` |

**已实测通过的路径**（本轮真跑过，输出见 §11）：

- ✅ header 解码（28/28）
- ✅ 歧义拒绝：`Account_Auth` 无 terminator → `REFUSING: 2 hits (0x22D988, 0x22DA5A)`
- ✅ terminator 消歧 → 定位到 `0x22D988 key=0x00`
- ✅ 等长违规拒绝：40 字符 URL 改成 38 字符 → `[FAIL] 长度完全相等`
- ✅ 多处替换：3 处 URL 全改，逐处回读 OK，"旧值已全部消失 True"
- ✅ IV 双命中拒绝（`0x7AA13^0xE9` / `0x12D172C^0x66`）

### 10.2 分析脚本（可复现）

| 脚本 | 作用 |
|---|---|
| `report\_tmp\md52\probe52.py` | header 探针 + token 字面量探针（`--only header` / `--only token`） |
| `report\_tmp\md52\hdr66.py` | header XOR `0x66` 的完整验证（A 全字段 / B 单调性 / C 字面量表 / D typeDefinitions / E 前 8 字节） |
| `report\_tmp\md52\regkey.py` | 逐区段暴力找 XOR key（**结论：只有 header 是统一 key，其余不是**） |
| `report\_tmp\md52\dump52.py` | 关键区段原始字节直出（用来一眼判断"是不是明文"） |
| `scripts\md_scan.py` | 子代理产出的全 key 扫描器（157 s，`--selftest` 6 项 PASS） |
| `report\_tmp\md52\token_probe.log` / `bypass_scan.log` | 上面两次全扫的原始输出 |

---

## 11. 诚实标注

| 声明 | 状态 |
|---|---|
| metadata 里没有方法体 | **确证**（架构 + `Il2CppMethodDefinition` 无 body 字段 + `report\47:188` + `01:227`） |
| Shittim 的 metadata patch 不含登录绕过 | **确证**（上游源码逐字核对 + 8 个 patcher 全表 + `ServerConfig.cs`） |
| header = XOR `0x66` | **确证**（28/28 区段单调 + 首尾相接 + 唯一 key） |
| RSA PEM 三段在 `fieldAndParameterDefaultValueData` 内 | **确证**（`0x178CC60/0x12D5F88/0x178CBA0` 全落在 `[0x12CB1D8, 0x17FCE60)`） |
| 协议 token 是运行时算的 | **确证**（3 个 token × ASCII/UTF-16LE × 256 key = 0 命中；宽松扫无 token 表） |
| `string` 标识符堆是明文 | **确证**（`key=0x00`，`BlueArchive\0BlueArchive.dll\0<Module>\0…` 逐字节可读） |
| `stringLiteral` 表（24,728 条）的混淆方式 | **未解**（单字节 XOR 全部不成立） |
| 前 8 字节 sanity/version | **未解**（不影响功能） |
| `methods`/`typeDefinitions` 等二进制表的逐条解密 | **未做**（`methods` 在 `^0x66` 下部分可读，但结构体大小与区段长度对不齐） |
| 客户端实际从哪读 metadata | **未验证**（§9 闸门 1，给出了 3 条判据命令） |
| ACE 是否校验 metadata | **未验证**（§9 闸门 2） |
| "改字符串能绕过登录" | **判定为否**。理由见 §4。**这不是"没试够"，是"作用域到不了"** |
| `typeSpecs` / `Il2CppType` 表 | **仍在 so 里，未解决**（§5.5 末尾） |
| 本轮是否动过手机/服务器 | **没有**。只读本地文件 + 写本地脚本/报告 |

---

## 12. 建议的下一步（按性价比排序）

| 序 | 动作 | 成本 | 收益 | 前置 |
|---|---|---|---|---|
| **1** | 跑 §9 闸门 1 的三条只读命令，确认 metadata 的读取路径 | **5 分钟，零风险，不耗点击** | 决定整条线"能不能用" | 无 |
| **2** | 若闸门 1 = 外部存储那份 ⇒ 直接 `cp` 打 **P-1（`ErrorCode` 探针）**，冷启动一次 | 10 分钟 + 1 次点击 | **一次分开 `report\50` 的读法 A/B**，决定 13 阶字段实验要不要做 | 1 |
| **3** | 并行做 `report\50` 的 **R00**（服务端变量），与 P-1 组成 2×2 | 1 次点击 | 同上，且两个变量互相独立 | 无 |
| **4** | 若 P-1 判为读法 B ⇒ 开跑 `report\50` §8 的字段阶梯（R01→R02→R03） | 3~4 次点击 | 定位"认证到底缺哪个字段" | 2 |
| **5** | 把 §5 的 header 结论回灌进 `INDEX` §1.7、`report\47` §5.1、`report\48` §2/B.2、`report\34:344`、`report\41:412` | 半小时 | 后续静态任务不再撞假墙 | 无 |
| **6** | 若未来要改 `libil2cpp` 里的方法体（真·绕过登录的唯一技术路径）⇒ 那是 `DEADENDS` D-19~D-29 的领域 | 大 | —— | 不在本报告范围 |

> **最后一句，写给自己和后来人**：
> `global-metadata.dat` 是**数据**文件，不是**代码**文件。任务里的"绕过登录判断"是一个**控制流**需求。
> 用数据文件去改控制流，只有两种可能：**改了某个被比较的常量**（本报告已穷举，没有），
> 或者**改了某个被查表的键**（那就是 §6.3，token 是算出来的，没有表）。
> 两条都不成立 ⇒ **这条路走不通，不是没找到路。**
