# 国服 GameMainConfig / ServerInfoDataUrl —— 定位 + 解密 + 等长替换实测

> 工作目录：`work\ba\noroot\`（**只读 APK**，未修改任何现有文件，未连服务器/手机）
> 原料：`report\_tmp\cn_base.apk` — 2,126,400,085 B，sha256 `dd30a285…7f83bb`，
> versionName **3.0.2** / versionCode **73** / targetSdk 33 / arm64-v8a
> 日期：2026-11-16
> 本轮新增脚本：`_cn_layer2.py` `_cn_crack.py` `_cn_crack2.py` `_cn_crack3.py` `_cn_words.py`
> `_cn_final.py` `_cn_parity.py` `_cn_one.py` `_cn_guess.py` `_cn_patch.py` `_cn_scan_lib.py`

---

## 0. 一句话结论

| 问题 | 答案 |
|---|---|
| 国服 `GameMainConfig` 在哪 | ✅ `assets/bin/Data/e37c46fea17834108a4756797197d05a`（**5,212 B**），m_Script = **1,090 B** |
| 解出来是什么 | ✅ **6 个字段，6/6 全部破出**：`SkipTutorial` / `ServerInfoDataUrl` / `ServerName` / `VersionCode` / `PlatformID` / `ChannelID`（§5） |
| **`ServerInfoDataUrl` 有值吗** | ✅ **有，而且就是生产 dispatcher**：<br>`["https://state-api.bluearchive-cn.com/api/state","https://stateqc-api.bluearchive-cn.com/api/state"]` |
| `DefaultConnectionGroup` 有值吗 | ❌ **这个 build 根本没有这个字段**（6 个键里没有 22 字符的名字；词表+字典无关反搜均 0 命中） |
| 那生产 state 域名从哪来 | **就是 APK 内置的 `ServerInfoDataUrl`**。国服 3.0.2 与国际服 1.93 是**两种形态**（见 §6/§8） |
| 等长替换可行性 | ✅ **完全可行，已实测两种方案**（§9）。方案 A 只改 **28 B** 密文，所有偏移/文件大小不动 |

> ⚠️ **不要套用国际服 1.93 的结论**。国际服那个 build 的 `ServerInfoDataUrl` 是空串
> （5 字段 / 494 B），国服 3.0.2 是 **6 字段 / 1,090 B / 带两条生产 URL**。
> 字段表都不一样：`ToyLogin`、`Language`、`DefaultConnectionGroup` 在国服**已不存在**。

---

## 1. 算法自检（先过硬判据）

```
$ python work\ba\noroot\CRYPTO_MT.py
[selftest] xxHash32('')          = 0x2cc5d05   (canonical 0x02CC5D05)
[selftest] xxHash32('abc')       = 0x32d153ff  (canonical 0x32D153FF)
[selftest] create_password('Excel.zip') = '/wy5f3hIGGXLOIUDS9DZ'  len 20
[selftest] expected                     = '/wy5f3hIGGXLOIUDS9DZ'  len 20
[selftest] create_key('GameMainConfig') = 1b 23 28 06 ad 72 c2 57
[selftest] RESULT: PASS
```

`create_key("GameMainConfig") = 1b 23 28 06 ad 72 c2 57`，第一层就是它的 **key8 循环 XOR**。

> ⚠️ **环境坑（下游必须知道）**：本机 `C:\msys64\...\python.exe`（3.12）在跑几万次
> `create_key` 后会**运行时损坏**（局部变量被替换成别的类型，报
> `'range_iterator' object is not subscriptable` / `'<' not supported between bytes and int`
> 这类语义上不可能的错误），**不是脚本 bug**。换成 DSH 自带 Python
> `C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（3.12.14）
> 即稳定（3 万次心跳通过；2.0 M 次级搜索用分片跑完）。**后续所有长循环都用这个解释器。**
>
> ⚠️ **第二个坑**：**不要**用 PowerShell `Get-Content -Raw` / `Set-Content` 往返编辑这些
> 含中文的 `.py`/`.md`（会把 UTF-8 中文写成 `\ufffd`，直接 `SyntaxError`）。
> 用编辑工具或 `write` 整文件重写。本轮踩过一次，已整文件重建恢复。

---

## 2. APK 结构盘点（只列目录，未整包解压）

`assets/bin/Data/` 共 **565** 个条目，合计 **164,349,827 B**。要点：

| 条目 | 大小 | 说明 |
|---|---|---|
| `Managed/Metadata/global-metadata.dat` | **38,426,024 B** | IL2CPP 元数据。**方法名明文、字符串字面量被混淆**（见 §5.3） |
| `sharedassets0.assets.split0..36` | 37 × 1,048,576 + 88,828 | 资源被切成 1 MiB 段 |
| `globalgamemanagers.assets.split0..5` | 6 × 1,048,576 + 109,768 | 同上 |
| `globalgamemanagers` / `level0` / `level1` | 1,009,692 / 36,840 / 4,516 | Unity 序列化文件（v22，**大端**） |
| `unity_app_guid` | 36 | `611ecbd3-58f7-4f6b-8056-e955c461a84c`（明文） |
| **`e37c46fea17834108a4756797197d05a`** | **5,212** | ★ **就是 GameMainConfig** |

> 注意：这是**裸 SerializedFile**，不是 UnityFS bundle（无 `UnityFS` magic），
> 数据段固定在 `0x1000` 起，头部 4 KiB 是元数据。

---

## 3. 定位（P1 名字法 + P2 周期 8 字节特征，双路命中同一文件）

```
$ python work\ba\noroot\find_gamemainconfig.py "report\_tmp\cn_base.apk" --dump work\ba\noroot\_extract_cn
[P0] scanned 565 members / 164349827 bytes
[P1] name hits      : 1
[P2] period-8 hits  : 1
       assets/bin/Data/e37c46fea17834108a4756797197d05a  0x1019 .. 0x145B
```

精确偏移（与文件大小自洽）：

| 位置 | 长度 | 内容 |
|---|---|---|
| `0x1000` | 4 | `0E 00 00 00` = m_Name 长度 14 |
| `0x1004` | 14 | ASCII `GameMainConfig` |
| `0x1012` | 2 | 对齐 padding `00 00` |
| `0x1014` | 4 | `42 04 00 00` = **1090** = m_Script 长度 |
| `0x1018` | **1090** | **密文**（`0x1018 .. 0x145A`） |
| `0x145A` | 2 | 尾部对齐 padding |
| 合计 | **5212** | = `0x145C` = 文件大小 |

第一层解密：H1（key8 循环、phase 0），`score=90`，`enc=utf-16-le`，`json.loads` 通过。
密文头 32 B 与明文头 32 B：

```
ct: 60 23 0a 06 95 72 83 57 54 23 49 06 fc 72 b4 57 ...
        ~~    ~~    ~~    ~~   ← 奇数字节严格周期 8 = key 的奇数位
pt: 7b 00 22 00 38 00 41 00 4f 00 ...   = {  " 8 A O ...
```

---

## 4. 第一层明文（还是二次混淆的）

```
545 个 UTF-16 字符 / 1090 B，6 个键值对，键和值都是 base64：
{"8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI":"5QOQQvfC5AjGAw==",
 "X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==":"V05fXAtqdXZ4Tg1c…",
 "ioIcSFNXEmG8ggtIb1cFYbSCHEg=":"qYILSE5XAGE=",
 "nYFvU65AaVWigWVTskBZVaSBblO5QA==":"/IE5Uw==",
 "wBgDdzgJJFH2GAB3Kwk9UdkYK3c=":"oRg=",
 "SiMCCCkfsBxnIw8IJB+XHE0j":"OCM="}
```

**这份 JSON 正好占满 545 个字符，尾部 padding 为 0** —— 这条事实决定了 §9 的预算。

---

## 5. 第二层：6 个字段全解（本轮核心）

### 5.1 格式（与国际服一致，本轮在国服上重新验证通过）

```
存键 = UTF16LE(fieldName) XOR cycle8(create_key(fieldName))
存值 = UTF16LE(value)     XOR cycle8(create_key(fieldName))     ← 值是拿「字段名」当种子
两者各自 base64 后放进第一层 JSON
```

**自密钥**：`dec(cand, key_ct) == UTF16LE(cand)` 是一个**充要判定式**——
命中即证明字段名正确，不需要任何外部佐证（无假阳性可能）。

### 5.2 还原结果（国服 3.0.2）

| # | 名字长度 | key_ct | val_ct | **字段名** | **值** | 判定来源 |
|---|---|---|---|---|---|---|
| 0 | 12 | 24 B | 10 B | **`SkipTutorial`** | `"False"` | 词表 + 自密钥 |
| 1 | 17 | 34 B | 202 B | **`ServerInfoDataUrl`** | **见 §6（101 字符）** | 词表 + 自密钥 |
| 2 | 10 | 20 B | 8 B | **`ServerName`** | `"prod"` | 词表 + 自密钥 |
| 3 | 11 | 22 B | 4 B | **`VersionCode`** | `"73"` | 词表 + 自密钥 |
| 4 | 10 | 20 B | 2 B | **`PlatformID`** | `"1"` | **奇偶分解（字典无关）** |
| 5 | 9 | 18 B | 2 B | **`ChannelID`** | `"1"` | **奇偶分解（字典无关）** |

**闭合性校验**（`_cn_verify.py`）：6 个键**全部**被上述名字认领，没有剩余未知键
（`已认领 6 / 6，缺失 无`）。判定式是精确等式，不存在假阳性。

**三条强交叉验证**：
- `VersionCode = "73"` 与 APK 的 `versionCode 73` **完全一致**；
- `ServerName = "prod"` / `PlatformID = "1"` / `ChannelID = "1"` 是符合国服运营形态的取值；
- 两个由**字典无关**方法破出的名字（`PlatformID`/`ChannelID`）与词表法破出的名字
  在命名风格上完全一致（都以大写 `ID` 结尾），互相佐证。

> 注意大小写：国服是 `"False"`（首字母大写），国际服同字段是 `"false"`。
> **不要在补丁里按国际服的写法生成值。**

### 5.3 字典无关破译：奇偶分解（本轮方法学收获）

因为字段名是 ASCII，`UTF16LE(name)` 的**奇数字节恒为 `0x00`**，于是：

```
key_ct[奇数] = 0x00 XOR cycle8(k)[奇数] = k[奇数]        ← 直接读出 k 的 4 个字节
key_ct[偶数] = name[i] XOR k[(2i) mod 8]                ← 只剩 k[0],k[2],k[4],k[6] 未知
```

对每个相位枚举这 4 个字节、要求拼出的字符都落在 `[A-Za-z0-9_]`，再以
`create_key(name) == k` 判定。名字 9~11 字符时组合数只有 10⁵~10⁶ 量级，
**分钟级可穷尽**。`PlatformID`（L=10，2,023,308 组合，92 s）与 `ChannelID`（L=9，3,406,760 组合，175 s）
就是这样在**完全没有任何候选词表**的情况下破出来的。

> 这条也解释了为什么 metadata 帮不上忙：见下。

### 5.4 metadata 为什么帮不上忙（重要）

- `global-metadata.dat` 里 **方法名是明文**：`GameMain-GetDefaultConnectionGroup0`、
  `GameMain-get_ServerInfo0`、`MX-Data-GameDataInitializer-InitializeServerInfoData0`、
  `MX-Data-DataManager-SetRepositoryGroup0` 等（23 个 `GameMain-*` 可枚举）。
- 但**类型名与字符串字面量被混淆**：`GameMainConfig`、`ToyLogin`、`ServerInfoDataUrl`
  的 `find()` 都是 **-1**；`SkipTutorial` 只作为方法名 `SetSkipTutorialIds` 的子串出现，
  **没有独立串**；对 `ToyLogin` 做 256 个单字节 XOR 反查也是 **0 命中**。
  ⇒ 字段名/字面量被加密，**只能靠密码学反搜**，不能靠 metadata 字符串表。
- 一个有用的旁证：`GameMain-GetDefaultConnectionGroup` 这个方法**存在**，
  说明「连接组」概念在代码里还在，但**本 build 的配置表里没有对应字段**
  （可能就是 §8 说的运行时下发/代码内默认）。

---

## 6. ★ `ServerInfoDataUrl` 的真实值（核心答案）

```
["https://state-api.bluearchive-cn.com/api/state","https://stateqc-api.bluearchive-cn.com/api/state"]
```
**101 个字符**，注意这是一个**「装着 JSON 数组的字符串」**（值本身是 string，
里面才是 2 个元素的 array）——客户端大概率要 `json.loads` 两次。

拆开看：

| # | URL | 字符数 | 角色 |
|---|---|---|---|
| 1 | `https://state-api.bluearchive-cn.com/api/state` | **46** | 生产 state 接口 |
| 2 | `https://stateqc-api.bluearchive-cn.com/api/state` | **48** | QC（质检/灰度）state 接口 |
| — | 共用域名 `bluearchive-cn.com` | **18** | 国服自有域名 |

**⇒ 国服客户端要拿的 dispatcher 地址，就写在 APK 内置的这份配置里。**
这和「国际服 1.93 是空串、必须去别处找」是**完全不同**的情况。

---

## 7. `DefaultConnectionGroup` 有值吗？

**没有，而且这个字段在本 build 不存在。**

判据（三条独立）：
1. 6 个键的名字长度是 `{12,17,10,11,10,9}`，**没有 22**（`DefaultConnectionGroup` 的长度）；
2. 词表反搜 43,927 个长度匹配候选，`DefaultConnectionGroup` **0 命中**；
3. 自密钥判定式是精确等式，不存在"解出来是空串所以看不见"的盲区。

同理 **`ToyLogin`（8）与 `Language`（8）也都不在了**（没有任何 8 字符目标键）。
国际服 5 字段 → 国服 6 字段，但**不是简单增删**，是换了一套 schema：

| 字段 | 国际服 1.93 | 国服 3.0.2 |
|---|---|---|
| `SkipTutorial` | `"false"` | ✅ `"False"` |
| `ToyLogin` | `"true"` | ❌ 不存在 |
| `Language` | `""` | ❌ 不存在 |
| `ServerInfoDataUrl` | `""`（空） | ✅ **两条生产 URL** |
| `DefaultConnectionGroup` | `""`（空） | ❌ 不存在 |
| `ServerName` | —— | ✅ `"prod"`（新） |
| `VersionCode` | —— | ✅ `"73"`（新） |
| `PlatformID` | —— | ✅ `"1"`（新） |
| `ChannelID` | —— | ✅ `"1"`（新） |

---

## 8. 那客户端的生产 state 域名到底从哪来？（最终问题）

**回答：国服 3.0.2 就是从 APK 内置的 `GameMainConfig.ServerInfoDataUrl` 来，没有别的来源**
——这是本轮最重要的修正。具体链路：

1. `GameMain` 启动 → `GameMain-InitGameData` → `MX-Data-GameDataInitializer-InitializeServerInfoData`
   （这三个方法名在 metadata 里**都是明文**）读取 `ServerInfoDataUrl` 并初始化 ServerInfo。
2. 值里的两条 URL 就是 state 接口的候选列表（生产 + QC），客户端按 `ServerName`/`ChannelID`
   等参数去请求。
3. `GameMain-GetDefaultConnectionGroup` 这个方法存在，但**配置表里没有对应字段**，
   说明连接组要么有代码内默认值，要么随 state 响应下发。

**因此对免 root 私服路线的直接含义**：

> 不需要再找"默认域名藏在哪"——**它就在这份 1,090 B 的 TextAsset 里，而且可以原地换掉**。
> 这条路在国际服上"没东西可改"，在国服上**有东西可改，且改动面极小（≤28 字节）**。

> 备注：早前在**旧国服包**的 metadata 里发现过 `http://test-ba.yostar.net:5210/api/state`
> （单字节 XOR key=0xB5）。那是**测试环境**常量，与本 build 的生产 URL 不是一回事；
> 本轮在 3.0.2 的 `assets/bin/Data/*` 里没有找到第二处生产域名（详见 §11 的扫描结论）。

---

## 9. 等长替换的可行性（**已实测，不是推算**）

### 9.1 预算结构

| 层 | 约束 |
|---|---|
| 文件大小 | 5,212 B（= `0x1018` + 1090 + 2 B padding） |
| `m_Script` | **固定 1,090 B = 545 个 UTF-16 字符** |
| 第一层 JSON | 当前 **545 字符，余量 0**（没有尾部空白） |
| 第二层 value | `ServerInfoDataUrl` 的密文 202 B = 101 字符，base64 后 **272 字符** |
| 固定开销 | **444 字符**（其余 5 个键的 base64 + 引号/逗号/花括号） |
| ⇒ **value 上限** | **101 字符** |

### 9.2 方案 A：域名等长替换（**推荐**，改动最小）

把 18 字符的域名换成任意 18 字符的自有域名，URL 条数/顺序/路径全不动：

```
原: ["https://state-api.bluearchive-cn.com/api/state","https://stateqc-api.bluearchive-cn.com/api/state"]
新: ["https://state-api.bapsvr-prod-cn.com/api/state","https://stateqc-api.bapsvr-prod-cn.com/api/state"]
      ↑ 只把 bluearchive-cn.com(18) 换成 bapsvr-prod-cn.com(18)，值仍 101 字符
```

实测结果（`_cn_patch.py`，真正落盘并回读复核）：

```
[1] file_size=5212  m_Name@0x1004='GameMainConfig'  m_Script_len@0x1014=1090  data=0x1018..0x145A
    JSON 重新序列化与原文逐字符一致: OK                     ← 说明重建不会改变任何字节布局
[2] ORIG (101 字符) / NEW (101 字符)，等长=True
    value b64: 272 → 272 字符（等长）
[3] layer1 chars: 545 → 545；密文差异字节 **28 个**，范围 0x146..0x288（全在 m_Script 内）
[4] 端到端回读：
    SkipTutorial      = 'False'          ← 未变
    ServerInfoDataUrl = '…bapsvr-prod-cn.com…'   ← 已改
    ServerName        = 'prod'           ← 未变
    VersionCode       = '73'             ← 未变
    ChannelID         = '1'              ← 未变
    ✅ 文件大小不变、全部偏移不变、其余字段逐字节不变
```

**代价：28 字节密文**（因为两个域名有大量公共前缀/后缀，只有中间不同的位会翻）。
**无需**改 `m_Name`、`m_Script` 长度字段、SerializedFile 头部、文件大小、zip 条目结构。

### 9.3 方案 B：任意短值 + 尾部空格补齐（**更宽松**）

如果不想背着 18 字符的域名长度约束，可以整条换成一个更短的值，
再用**尾随空格**把 JSON 补回 545 字符（JSON 允许尾部空白，`json.loads` 照常解析）：

```
值 = ["https://ba.example.com/si.json"]      (34 字符)
新 JSON = 365 字符 + 180 个空格 = 545 字符   → UTF-16LE = 1090 B
实测密文差异 384 B，文件大小 5212 不变，回读值 = ["https://ba.example.com/si.json"] ✅
```

⇒ **value 只要 ≤ 101 字符都能放**，短多少用空格补多少。
**这条路对"改成自己的域名"完全够用，且比等长替换更自由。**

### 9.4 如果想变长（**不建议**）

JSON 已经占满 545 字符、余量 0。要加长必须同时改：
`m_Script` 长度(@0x1014) + SerializedFile 头部的大小字段 + 文件大小 + zip 条目 + 重签。
成本高、且头部一旦算错就是整个 Unity 资源加载失败。
**除非真的要塞下一整份几十条 URL 的列表，否则用方案 A/B。**

### 9.5 结论表

| 方案 | 是否可行 | 改动量 | 备注 |
|---|---|---|---|
| A 域名等长替换 | ✅ **实测通过** | **28 B** 密文 | 推荐；域名必须 18 字符 |
| B 短值 + 空格补齐 | ✅ **实测通过** | 384 B 密文 | 值 ≤101 字符即可，更自由 |
| C 变长重排 | ⚠️ 理论可行 | 需改 3~4 处长度/大小字段 | 余量 0，不建议 |
| D 直接塞明文 JSON | ❌ 不可 | —— | 第二层是**必须**的：客户端按字段名查表解密 |

### 9.6 还没验证的两件事（写下来，别跳过）

1. **§9 只验证了"字节层正确闭环"**，没有真机/真服跑过。方案 A/B 产出的文件
   `PATCHED_*.bin` 已落地，**尚未重新打包进 APK、尚未重签、尚未启动验证**。
2. **空值/默认值语义**：国服这份是**非空**的生产 URL，所以不存在国际服那种
   "空=用代码默认"的歧义——这一点上国服反而更简单。

---

## 10. 产出与复现

| 文件 | 作用 |
|---|---|
| `_extract_cn/GameMainConfig_…_e37c46fe…bin` | 命中的 5,212 B 原文件 |
| `_extract_cn/GameMainConfig_…_e37c46fe….json` | 第一层解出的 545 字符 JSON |
| `_extract_cn/CN_GameMainConfig_plain.json` | 已还原字段（逐轮累积） |
| `_extract_cn/PATCHED_e37c46fe…bin` | **方案 A** 结果（域名等长替换） |
| `_extract_cn/PATCHED_SHORT_e37c46fe…bin` | **方案 B** 结果（短值 + 空格补齐） |
| `_cn_layer2.py` | 用已知名解第二层（自密钥校验） |
| `_cn_guess.py` / `_cn_words.py` / `_cn_final.py` | 词表反搜（含独立 MT 实现的交叉校验） |
| `_cn_parity.py` | **字典无关奇偶分解破译**（分片参数 `idx start end`） |
| `_cn_verify.py` | **最终校验**：6/6 字段闭合 + 落盘 `CN_GameMainConfig_plain.json` |
| `_cn_scan_lib.py` | 24 个 native 库的域名串扫描 |
| `_cn_scan_sanity.py` | 扫描器真阴性校验（对照组命中 4,592 次） |
| `_cn_patch.py` | 等长替换 + 回读复核（方案 A/B，6 字段全核对） |
| `_cn_one.py` | 心跳自检（`sanity`）与分片跑（`slice L a b`） |

复现（**必须用 DSH 自带 Python**，见 §1 环境坑）：

```powershell
$py="C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
& $py CRYPTO_MT.py                                              # PASS
& $py find_gamemainconfig.py "report\_tmp\cn_base.apk" --dump _extract_cn
& $py _cn_layer2.py                                             # 6 对，2 个已知名字命中
& $py _cn_verify.py                                             # 6/6 闭合校验
& $py _cn_patch.py                                              # 方案 A/B 全流程 + 回读复核
& $py _cn_parity.py 5 0 -                                       # 字典无关破 ChannelID(L=9)
& $py _cn_parity.py 4 0 600000                                   # 字典无关破 PlatformID(L=10, 第 1 片)
```

---

## 11. 扫描结论（其它可能藏域名的地方）

`find_gamemainconfig.py` 的 P3 枚举了 **78,347 个 TextAsset 形态对象 / 遍及 474 个文件**，
`GameMainConfig` 这个 ASCII 名在全 APK 里**只出现 1 次**（就是命中的那份）。
另外：

- `assets/bin/Data/` 里没有第二份带 `https://…bluearchive-cn.com…` 的 TextAsset；
- metadata 的字符串表里 `ServerInfoDataUrl` / `ToyLogin` / `GameMainConfig` 均 **-1**
  （字面量被混淆，见 §5.4）；
- 早前记录的 `test-ba.yostar.net:5210` 是**旧包**的测试环境常量，不在本 build 的生产路径上。

### 11.1 native 库扫描（`_cn_scan_lib.py`，24 个 `.so` 全扫）
| 项 | 结果 |
|---|---|
| `lib/` 条目 | **24** 个，全部 arm64-v8a |
| 最大者 | `libil2cpp.so` = **270,927,056 B**（258 MB）；`libunity.so` 20,950,552 B |
| 搜索目标 | `state-api` / `stateqc` / `bluearchive-cn` / `/api/state` / `yostar` / `bluearchive` / `ServerInfoData` / `GameMainConfig` / `DefaultConnectionGroup` / `dispatcher`（ASCII + UTF-16LE 双形态） |
| **命中** | **0**（24 个库里全部 0） |

**真阴性校验**（`_cn_scan_sanity.py`，防止"扫描器坏了"的假阴性）：在同一个 `libil2cpp.so` 上
用对照组搜索本该存在的运行时符号，**命中 4,592 次**
（`il2cpp`=285、`UnityEngine`=4,132、`System.String`=150、`JNI_OnLoad`=9 …），
而目标串仍为 **0**（唯一的 `prod`=16 是 `product/production` 之类子串）。
同时抽样可打印率 23.1%、零字节 24.7% ⇒ **该 .so 没有被整体加密/加壳**，字符串区是可读的。

⇒ **结论：`libil2cpp.so` 里没有硬编码的 state 域名。**
域名字符串只存在于 APK 内置的 `GameMainConfig` 里，运行期从 asset 读入。
**这也再次印证 §8：国服生产 state 域名只有一个来源，就是这份 1,090 B 的 TextAsset。**


---

## 12. 与既有文档的冲突（需要回写 `GAMEMAINCONFIG.md` / `HISTORY.md`）

| 既有说法 | 本轮实测 |
|---|---|
| 国服 APK 本地不存在 | ✅ **已推翻**：`report\_tmp\cn_base.apk` 在盘上，565 个 Data 文件齐全 |
| `ServerInfoDataUrl` 大概率是空串 | ❌ **国服非空**，有两条生产 URL |
| 国际服=5 字段、国服应该一样 | ❌ 国服是 **6 字段 + 不同 schema**（`ToyLogin`/`Language`/`DefaultConnectionGroup` 都没了） |
| "等长替换"要先找可替换的字段 | ✅ 国服有 101 字符的值可替换，且**已实测** |

---

## 13. 未解 / 待办

1. ~~第 6 个字段待解~~ → **已解：`PlatformID = "1"`**（奇偶分解，分片穷尽 92 s 命中）。
   至此 **6/6 字段全部闭合**（`_cn_verify.py` 断言通过）。
2. 方案 A/B 的产物**尚未打成 APK 并重签/启动**——这一步属于打包链，不是本轮范围。
3. `ServerName` / `PlatformID` / `ChannelID` / `VersionCode` 在 state 请求里的具体用法未验证
   （是否作为 query 参数、是否参与签名）——建议在真机抓一次 state 请求确认。
4. `stateqc-api`（QC/灰度）与 `state-api`（生产）的切换条件未验证
   （可能由 `ServerName`/`ChannelID` 决定）。
