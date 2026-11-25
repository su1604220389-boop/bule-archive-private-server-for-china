# GameMainConfig / ServerInfoDataUrl —— 定位 + 解密报告

> 工作目录：`work\ba\noroot\`（只读 APK，未改任何现有文件，未连服务器/手机）
> 产出：`CRYPTO_MT.py`、`find_gamemainconfig.py`、本文件
> 日期：2026-11-16

---

## 0. 一句话结论

| 项目 | 结果 |
|---|---|
| 算法自检 `create_password("Excel.zip")` | ✅ **PASS** = `"/wy5f3hIGGXLOIUDS9DZ"`（20 字符） |
| `GameMainConfig` 定位 | ✅ **找到了**（在**国际服** APK 里；**国服 APK 本地没有**，见 §6） |
| 解密 | ✅ 一次成功，`create_key("GameMainConfig")` 逐字节 XOR |
| `ServerInfoDataUrl` 的真实值 | ⚠️ **空字符串 `""`** —— 这个 build 的 APK 里**根本没有地址** |
| 等长替换是否可行 | ⚠️ 前提不成立（没东西可替换）；但**整段 JSON 重写**方案可行且更宽松，见 §7 |

**关键反直觉发现**：`GameMainConfig` 的明文 JSON **本身还是混淆的**（键和值都是二次加密的），
而且解开之后 `ServerInfoDataUrl` 在 1.93 这个 build 上是**空串**。
看雪那篇写的"914 B、直接可见 `ServerInfoDataUrl`"是**老版本/日服**的形态，2026 年的新 build 已经改了。

---

## 1. 算法自检（硬判据，先过这一关）

公式来源：`report\56:1013-1097`。实现：`CRYPTO_MT.py`。

```
seed      = xxHash32(UTF8(name), seed=0)
mt        = MT19937(seed)
mt.Next() = (genrand_int32() >> 1) & 0x7FFFFFFF     # 注意 >>1
NextBytes(n): 每 4 字节调一次 Next()，struct.pack('<I') 小端
create_key(name)          = NextBytes(8)
create_password(name, 20) = b64encode(NextBytes(15))
```

实测：

```
xxHash32('')          = 0x02CC5D05   (canonical ✓)
xxHash32('abc')       = 0x32D153FF   (canonical ✓)
create_password('Excel.zip') = '/wy5f3hIGGXLOIUDS9DZ'    len 20
期望                          = '/wy5f3hIGGXLOIUDS9DZ'    len 20   => PASS
```

> 注：任务书里写的 `/wy5f3hIGGpXLOIUDS9DZ` 是 21 字符、多了一个 `p`，是转录笔误。
> `report\56:1022` 与 `:1096` 两处都是 20 字符的 `...IGGX...`，实测以 20 字符为准。

**顺手得到一个强证据**（这条直接决定了解密方式）：

```
create_key("GameMainConfig") = 1b 23 28 06 ad 72 c2 57
                                 ↑    ↑    ↑    ↑
                                 23   06   72   57      <- 第 1/3/5/7 字节
```

`report\56:985` 观察到的密文奇数字节周期 `23 06 72 57 23 06 72 57 …`
**正是这把 key 的奇数字节**。⇒ 说明 `GameMainConfig` 用的是
**固定 8 字节 key 循环 XOR**（`create_key` 的 8 字节反复用），
**不是** `xor_bytes()` 那种连续 MT keystream。两者只在前 8 字节相同，之后会分叉。
扫描器把两种都试（H1/H2/H3），实际命中 **H1 = key8 循环、phase 0**。

---

## 2. 定位结果（精确偏移）

**容器文件**（在 APK zip 里的路径）：

```
assets/bin/Data/61376b4dc1d7943a1a6556439d2df761        4616 B
```

整份 APK 里 `GameMainConfig` 这个 ASCII 名**只出现这一次**（另一处是 `global-metadata.dat` 的字符串表）。

文件内部结构（该 build 是 **大端** SerializedFile，metadata 占 `0x0..0xFFF`，data 从 `0x1000` 起，只有一个对象）：

| 位置 | 长度 | 内容 |
|---|---|---|
| `0x1000` | 4 | `0E 00 00 00` = `m_Name` 长度 14 |
| `0x1004` | 14 | ASCII `GameMainConfig` |
| `0x1012` | 2 | 对齐 padding `00 00` |
| `0x1014` | 4 | `EE 01 00 00` = **494** = `m_Script` 长度 |
| `0x1018` | **494** | **密文**（`0x1018 .. 0x1205`，末字节在 `0x1206` 之前） |
| `0x1206` | 2 | 对齐 padding |
| 合计 | 4616 | = `0x1208` = file_size |

密文开头 32 字节：

```
60 23 0a 06 95 72 83 57 54 23 49 06 fc 72 b4 57
57 23 6b 06 98 72 b5 57 71 23 1b 06 ec 72 f6 57
        ~~    ~~    ~~    ~~   ← 奇数字节：23 06 72 57 严格周期 8
```

解密后（同一 32 字节）：

```
7b 00 22 00 38 00 41 00 4f 00 61 00 51 00 76 00 4c 00 43 00 35 00 77 00
 = { " 8 A O a Q v L C 5 w      -> UTF-16LE 的 JSON
```

**P2（字节特征法）独立复现**：完全不看名字、只按"奇数字节严格周期 8"扫，
在同一个文件里命中 lane `0x1019 .. 0x1207`（lane 起点 = blob 起点 `0x1018` + 1）。
⇒ 这条判据对**国服**同样可用，不依赖 `m_Name` 是否明文。

---

## 3. 解出来的完整明文（第一层）

```json
{"8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI":"xQOQQvfC5AjGAw==","YZMqL8DWxWpakyIv0Nbnag==":"QZM3L8zW7Go=","wL4EWsDv8QX5vgRaye/zBQ==":"","X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==":"","tSrfb7xhQRKEKtZvrmFjEp4q1G+0YUUSkirOb7NhTxKfKv1vqGFPEoQqym8=":""}
```

247 个 UTF-16 字符 / 494 字节，`json.loads` 直接通过。
**但这不是最终配置**——键和值本身还是加密的（第二层）。

---

## 4. 第二层：`GameMainConfig` 的键值混淆（本轮新解出来的）

一次 `ServerInfoDataUrl` 的巧合暴露了规律，随后用 `global-metadata.dat` 的候选字符串
反搜全部验证通过。格式（**已在 4/5 个键上验证，第 5 个手工验证**）：

```
存键:  key_stored   = UTF16LE(fieldName)   XOR  cycle8(create_key(fieldName))
存值:  value_stored = UTF16LE(value)       XOR  cycle8(create_key(fieldName))
                                      ↑ 注意值是拿「字段名」当种子，不是拿值自己
```

- `fieldName` 用自己当种子 ⇒ **自密钥**：不知道名字就解不开（客户端靠代码里写死的常量查表）。
- 值是拿**字段名**当种子 ⇒ 一旦知道名字，值就能直接解出来。
- `cycle8(k) = (k*2)[:n]`，和第一层同一个原语。

反搜脚本：`_schema_bruteforce.py`（候选 = metadata 里长度匹配的 ASCII 串；命中即 `enc_cycle(s) == 存键`）。

| # | 存键（UTF-16 字符数） | 反搜出的字段名 | 解密后的值 |
|---|---|---|---|
| 0 | 12 | **`SkipTutorial`** | `"false"` |
| 1 | 8  | **`ToyLogin`** | `"true"` |
| 2 | 8  | **`Language`** | `""` |
| 3 | 17 | **`ServerInfoDataUrl`** | **`""`** |
| 4 | 22 | **`DefaultConnectionGroup`** | `""` |

还原后的真实配置：

```json
{
  "SkipTutorial":           "false",
  "ToyLogin":               "true",
  "Language":               "",
  "ServerInfoDataUrl":      "",
  "DefaultConnectionGroup": ""
}
```

---

## 5. `ServerInfoDataUrl` 的真实值

> **`""`（空字符串）**

也就是说：**这个 build 的 APK 里没有写 dispatcher 地址**。
`report\56` 描述的那套"APK 内的 914 B TextAsset 里带着 URL"，
在 1.93.454564 这个 2026 年的 build 上**已经不成立**。

配套证据：
- 5 个字段里 3 个是空串，另外两个是布尔开关（`false` / `true`）——
  这看起来是一份**默认/空模版**，真正的 server info 是运行时从别处拿的。
- 该 build 里 `GameMainConfig` 只有 494 B，而看雪说的老版本是 914 B。
- `DefaultConnectionGroup` 也是空 ⇒ 连连接组都没在 APK 里指定。

**⇒ 对私服的意义：这条路在这个 build 世代上"没有东西可改"。**
要改地址得去别处（il2cpp 常量 / 登录后下发的 `ServerInfoDataUrl` / `catalog` 里），
不在 `GameMainConfig` 里。这条应当写进 `DEADENDS`。

---

## 6. ⚠️ 国服 APK 本地不存在（必须说清楚）

任务书里写的 `work\ba\audit\ba-apk\assets\` **并不存在**。实际盘点：

| 路径 | 是什么 | 有 `.assets` 吗 |
|---|---|---|
| `work\ba\audit\ba-apk\` | 只有 `lib/`、`jadx/`、`classes*.dex`、`slim.apk`(7.9 MB, 4 条目)、`zip_listing.txt` | ❌ |
| `work\ba\audit\ba-work\x\` | 从国服 APK 解出来的壳：`lib/`+2 dex+`assets/bin/Data/Managed/Metadata/global-metadata.dat` | ❌ 只有 metadata |
| `work\ba\audit\ba-work\zip_list.txt` | 国服 `base.apk` 的 `unzip -l` 全表（41,312 条目 / 2.46 GB 解压后，带**长度**） | 清单有，文件没有 |
| `_tmp\ba_apks\base.apk` + `Blue Archive_1.93.454564.apks` | **`com.nexon.bluearchive` 1.93.454564 = 国际服**（8 个 dex、`libNexonPlatformModules.so`） | ✅ 793 个 Data 文件 |

⇒ 本次用的是**国际服 base.apk**。国服只有目录清单，**字节不在盘上**，
所以"国服 `ServerInfoDataUrl` 是什么"这个问题**本地无法回答**（不是没找，是没有原料）。

顺带两条本次查明的事实，对后续有用：

1. **国服 `global-metadata.dat` 的字符串是「逐串单字节 XOR」的**。
   直接 `find(b"GameMainConfig")` / `find(b"ServerInfoDataUrl")` 都是 **-1**；
   但 `Language`(0xED0DE)、`ServerInfoData`(0x12A713) 能直接找到。`_urls_meta.txt` 里也印证了
   （`key=0xB5` → `http://test-ba.yostar.net:5210/api/state`）。
   ⇒ `report\59` 的"候选明文 × 256 key 反向搜"就是这个原因，方法是对的。
2. 31 个 `BA_backup\*.tar`（~9 GB 国服下载资源）里 `GameMainConfig` **0 命中**——
   它是 APK 内置资产，不在下载的 bundle 里，符合预期。

**要拿到国服的值，只需要给我国服 `base.apk`（或它那 565 个 `assets/bin/Data/*` 文件），一条命令：**

```powershell
python work\ba\noroot\find_gamemainconfig.py "<国服 base.apk 路径>" --dump _extract
```

扫描器已经把国服的两个坑都覆盖了：P2 按字节特征扫（不依赖名字明文），P1 按名字扫（名字在 `.assets` 里是明文的）。

---

## 7. 等长替换可行性评估

### 7.1 这个 build：没有东西可替换
`ServerInfoDataUrl` 是空串，值区 0 字节 ⇒ "等长替换"退化成"插入"，必然改变长度。

### 7.2 但**整段 JSON 重写**完全可行（推荐方案，比等长短替换更宽松）

`m_Script` 是一个**定长 494 B（247 个 UTF-16 字符）的密文块**，
里面装的就是整份 JSON。所以预算不是"某个字段多长"，而是：

> **整份 JSON 的 UTF-16 长度 ≤ 247 字符，然后用空格补齐到 247。**

JSON 允许尾部空白，所以补齐是合法的。这样做**所有偏移都不动**：

| 要改的东西 | 位置 | 是否需要改 |
|---|---|---|
| `m_Name` 长度 + 名字 | `0x1000..0x1011` | ❌ 不动 |
| `m_Script` 长度 u32 = 494 | `0x1014` | ❌ 不动（重写后仍是 494 B） |
| 密文本体 | `0x1018..0x1205`（494 B） | ✅ **只改这一段** |
| 文件大小 4616 | — | ❌ 不动 |
| 相邻对象 / 其他文件 | — | ❌ 不动（该文件只有 1 个对象） |

改写配方：

```python
new_json = '{"ServerInfoDataUrl":"https://你的域名/xxx.json"}'   # 或带上 SkipTutorial/ToyLogin
body = new_json.ljust(247)                      # 必须 <= 247 个字符
pt   = body.encode('utf-16-le')                 # 恰好 494 B
k8   = create_key("GameMainConfig")             # 1b 23 28 06 ad 72 c2 57
ct   = bytes(a ^ b for a, b in zip(pt, (k8 * 62)[:494]))
assert len(ct) == 494
asset[0x1018:0x1018+494] = ct                   # 原地写回
```

- 247 字符预算相当够用：`{"ServerInfoDataUrl":"https://ba.example.com/si.json"}` 才 54 字符，
  剩下 190 多字符可以留给 `SkipTutorial` / `ToyLogin` / `Language` / `DefaultConnectionGroup`。
- **能不能直接塞明文 JSON？** ⚠️ **不 —— 这一条要验证**。见 §7.3 风险项 1。

**已实测验证**（`_patchdemo.py`，在国际服那份 4616 B 文件上真跑了一遍）：

```
[1] round-trip (re-encrypt == original): True
[2] new json 54 chars, padded to 247, 494 B
[3] wrote ...PATCHDEMO.bin (4616 B, same size as original)
[4] read back: ServerInfoDataUrl = 'https://ba.example.com/si.json'  match=True
[5] name/length bytes untouched: True | file size equal: True
```

⇒ "改写 494 B 密文层、所有偏移不动、文件大小不变"这条**不是推算，是跑过的**。

### 7.3 两个必须先验证的风险（写下来，别跳过）

1. **第二层是不是"必须"的？**
   如果客户端拿到 `m_Script` 后还要再走一遍 `dict[Key("ServerInfoDataUrl")]` 查表，
   那我们就**不能**直接塞明文 JSON，必须按第二层格式**重新生成**：
   ```python
   k = "ServerInfoDataUrl"
   key_stored = xor(utf16le(k), cycle8(create_key(k)))          # 键
   val_stored = xor(utf16le(url), cycle8(create_key(k)))        # 值用字段名当种子
   new_json = '{"%s":"%s"}' % (b64(key_stored), b64(val_stored))
   ```
   这条**本轮没有验证**（因为国际服这个 build 的值是空的，没法做"A/B 对照"）。
   建议在国服上先用一条已知非空的字段（比如 `ToyLogin`）验证第二层是否真的被读——
   如果 `ToyLogin` 改成 `false` 能改变开局行为，说明第二层是真读取的，路线成立。

2. **空值语义**。`ServerInfoDataUrl=""` 是真的空，还是"空 = 用代码里的默认值"？
   如果客户端是 `if (empty) use default`，那**填上我们的 URL 反而可能不生效或被判坏**——
   更稳的做法是找到那个"默认值"在哪（大概率在 `libil2cpp.so` 的字符串常量里，
   国服那份 258 MB 的 `libil2cpp.so` 已经在盘上，可以静态搜 `yostar` / `bluearchive` / `.json`）。

### 7.4 结论

| 方案 | 可行性 | 备注 |
|---|---|---|
| 原地等长替换某个字段 | ⚠️ 本 build 无字段可换 | 值区 0 字节 |
| **原地重写整段 JSON（247 字符预算）** | ✅ **技术上可行**，偏移全不动 | 但要看 §7.3 的两条 |
| 改完重打包 + 重签 | ✅ 与本次改动面无关（只动 494 B 明文层） | E30/E38/E42 已证明改包能跑 |

---

## 8. 产出与复现

| 文件 | 作用 |
|---|---|
| `CRYPTO_MT.py` | `xxhash32` / `MT` / `create_key` / `create_password` / `xor_bytes`，`python CRYPTO_MT.py` 跑自检 |
| `find_gamemainconfig.py` | 扫描器：P1 名字法、P2 周期 8 字节特征法、P3 TextAsset 枚举；`--dump` 落地 |
| `_schema_bruteforce.py` | 第二层字段名反搜（metadata 候选串 × `enc_cycle` 比对） |
| `_probe_payload.py` / `_probe2.py` / `_probe3.py` | 第二层规律的推导/验证过程 |
| `_extract\GameMainConfig_*.bin` | 命中的 4616 B 原文件（国际服） |
| `_extract\GameMainConfig_*.json` | 第一层解出的 JSON |

复现（国际服）：

```
python CRYPTO_MT.py                                                  # PASS
python find_gamemainconfig.py "...\base.apk" --dump _extract          # P1 1 hit / P2 1 hit
python _schema_bruteforce.py "_extract\gm-global-metadata.dat"        # 4/5 字段名
```

---

## 9. 与既有文档的冲突（需要回写 `report\56` / `HISTORY.md`）

| 既有说法 | 本次实测 |
|---|---|
| `GameMainConfig` 914 B、明文可见 `ServerInfoDataUrl` | 494 B，且**明文 JSON 里的键值还是二次混淆的** |
| `ServerInfoDataUrl` 里有 dispatcher URL | 1.93.454564 上是 **空串** |
| 按 `create_key` 循环 XOR 解密 | ✅ 正确（并且从 key 的奇数字节反证了"循环 8 字节"而非连续 keystream） |
