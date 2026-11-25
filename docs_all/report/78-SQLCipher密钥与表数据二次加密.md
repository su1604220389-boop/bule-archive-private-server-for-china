# 78 · SQLCipher 密钥与表数据二次加密

> 目标：拿到国服《蔚蓝档案》`ExcelDB.db` 的 SQLCipher 密钥，或确定它从哪来。
> 约束：全程只读本地文件，未连手机、未连服务器、未碰 `libtprt.so`。
> 材料：`report/_tmp/shittim/`（Shittim-Server 源码快照）、`work/ba/audit/`（客户端 APK 解包 + 既往实测记录）、`report/03`、`report/09`、`report/56`。

---

## §0 一句话结论

**密钥拿到了，而且是可复现的字面量，不是猜的：**

```
ef0aaca06f34b4a4be3172a75a3ea565e815f9ece35b1fb12b7a166ba0807bc4
```

- 形式：**64 个 hex 字符 → 32 字节 raw key**（AES-256，SQLCipher 4.x），配套一条商业 License。
- 出处：Shittim-Server 上游源码 `Configuration/ConfigType/ServerConfig.cs:58` 的**类字段默认值**；可被环境变量 `SHITTIM_EXCELDB_SQLCIPHER_KEY` 覆盖；运行时通过 `Queuing_GetCryptoKeys` / `Queuing_GetAuthTicket` 的 `EncryptedSqlCipherKey` 下发给客户端。
- **已被真实库验证过**：`report/09-服务器盘点.md:390` 的实机日志 `[ExcelTableService] ExcelDB SQLCipher key validated (912 schema entries).` —— 那把 key 打开了从**官方 CDN**（`ba.dn.nexoncdn.co.kr`）下来的 **311,083,008 B** 的 `ExcelDB.db`，读出 912 个 schema 条目。这条是本报告最硬的一条证据：说明这把 key **就是官方原键**，不是私服作者自造的。

**但有两件事必须先纠正：**

1. **`ExcelDB.db` 与 `Excel.zip` 是两个并列的 CDN 文件，不是"两层锁"。** 密钥属于 SQLCipher 那条线（`/Preload/TableBundles/ExcelDB.db`），zip 口令属于 flatbuffer 那条线（`/Preload/TableBundles/Excel.zip` → 62 个 `.bytes`）。zip 里**没有** `ExcelDB.db`。详见 §5。
2. **国服大概率根本没有这个 SQLCipher 单文件。** 客户端实测拿到的 4 个 SQLite 分片是**明文**（`ba-data-layer.md:8-12`）。所以"国服 `ExcelDB.db` 的 SQLCipher 密钥"这个问题本身，在证据上大概率**不成立**——需要的是"表数据在哪"，不是"钥匙"。

---

## §1 Shittim 源码里所有相关片段

> 说明：`report/_tmp/shittim/raw/*.json` 是 GitHub Contents API 的 base64 包装，`_decode6.py` 已解到 `report/_tmp/shittim/src/`。下面引用的是解码后的原文（行号对应 `src/` 下的文件）。

### 1.1 密钥与 License 的字面量 —— `Shittim-Server__Configuration__ConfigType__ServerConfig.cs:57-59`

```csharp
public string AdminApiKey { get; set; } = "";
public string ExcelDbSqlCipherKey { get; set; } = "ef0aaca06f34b4a4be3172a75a3ea565e815f9ece35b1fb12b7a166ba0807bc4";
public string ExcelDbSqlCipherLicense { get; set; } = "OmNpZDowMDFWSjAwMDAwY3pzaVlZQVE6cGxhdGZvcm06MjY6ZXhwaXJlOm5ldmVyOnZlcnNpb246MTpsaWJ2ZXI6NC4xMC4wOmhtYWM6ODQ1Y2JkMzQ0MDc3YjIxNmRlYTgyOWI3OTIyMzQzZDNlMGJlMjMzYWM=";
```

>`Config.cs:76` 定义 `ConfigPath = ConfigDirectory/Config.json`，`Config.cs:88` ——**文件不存在时直接 `Save()` 写默认值**。也就是说：**服务器上第一次跑起来，这把 key 就已经明文落在 `Config/Config.json` 里了**。这是"从哪来"的第二个现成来源（不需要源码）。

### 1.2 密钥的规范化链 —— `Shittim-Server__Core__NetworkProtocol__Handlers__QueuingHandler.cs:128-149`

```csharp
private static byte[] GetSqlCipherKeyBytes()
{
    var key = Environment.GetEnvironmentVariable("SHITTIM_EXCELDB_SQLCIPHER_KEY");
    if (string.IsNullOrWhiteSpace(key))
        key = Config.Instance.ServerConfiguration.ExcelDbSqlCipherKey;

    key = (key ?? "").Trim();

    if (key.StartsWith("x'", StringComparison.OrdinalIgnoreCase) && key.EndsWith("'"))
        key = key[2..^1];

    if (key.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        key = key[2..];

    if (TryHexKey(key, out var hexKey))
        return hexKey;

    if (TryBase64Key(key, out var base64Key))
        return base64Key;

    return Encoding.UTF8.GetBytes(key);
}
```

解析顺序：`x'…'` → `0x…` → hex → base64 → UTF-8 原文。默认值 64 hex 走 `TryHexKey`（`QueuingHandler.cs:160-169`：偶数长度 + 全 hex 才成立）→ **32 字节 raw key**。

### 1.3 密钥怎么出门（下发给客户端）—— `QueuingHandler.cs:116-126`

```csharp
private static (string EncryptedKey, string EncryptedLicense) BuildSqlCipherResponse(string? clientKeyText, string? clientIvText)
{
    var (clientKey, clientIv) = GatewaySessionCryptoBuilder.DecodeClientCrypto(clientKeyText, clientIvText);
    var sqlCipherKey = Convert.ToBase64String(GetSqlCipherKeyBytes());
    var sqlCipherLicense = GetSqlCipherLicense();

    return (
        GatewaySessionCryptoBuilder.EncryptAesBase64(sqlCipherKey, clientKey, clientIv),
        GatewaySessionCryptoBuilder.EncryptAesBase64(sqlCipherLicense, clientKey, clientIv)
    );
}
```

挂载点：`GetCryptoKeys`（`Queuing_GetCryptoKeys`，`:27-35`）与 `GetAuthTicket`（`Queuing_GetAuthTicket`，`:82-91`），两条路径都会填 `response.EncryptedSqlCipherKey`。

加密方式 —— `Shittim-Server__Core__GatewaySessionCrypto.cs:150-156`：

```csharp
public static string EncryptAesBase64(string text, byte[] key, byte[] iv)
{
    // Stays CBC: this encrypts EncryptedKey/EncryptedIV and the SqlCipher asset-DB key, both of which the client decrypts with CBC, so another mode stalls it at "Unpacking game resources".
    var encrypted = HybridCryptor.EncryptTextAES(Encoding.UTF8.GetBytes(text), key, iv);
    return Convert.ToBase64String(encrypted);
}
```

⇒ **线上形状**：`EncryptedSqlCipherKey = base64( AES-CBC( base64(32 字节 raw key) ) )`，AES 的 key/IV 是客户端在请求里自带的 `ClientGeneratedKey` / `ClientGeneratedIV`。

对我们的 key 算一算（本地已算）：

| 形态 | 值 |
|---|---|
| hex（源码里的） | `ef0aaca06f34b4a4be3172a75a3ea565e815f9ece35b1fb12b7a166ba0807bc4` |
| 字节数 | 32 |
| `base64(raw 32B)`（AES 之前的明文） | `7wqsoG80tKS+MXKnWj6lZegV+ezjWx+xK3oWa6CAe8Q=` |
| SQLCipher PRAGMA 形式 | `PRAGMA key = "x'ef0a…bc4'";` |

### 1.4 License 解码（本地 base64 还原）

```
:cid:001VJ00000czsiYYAQ:platform:26:expire:never:version:1:libver:4.10.0:hmac:845cbd344077b216dea829b7922343d3e0be233ac
```

这是 **Zetetic SQLCipher 商业授权码**格式（`cid / platform / expire / version / libver / hmac`）。`libver:4.10.0` 与客户端 `libsqlcipher.so` 里的版本串 `4.10.0` 完全一致（见 §3.2）。⇒ 该 key 不是随便生成的字符串，它是**跟着一份商业版 SQLCipher 库走**的。

> 对我们的用途：**License 在离线解密时不需要**。它只控制商业版特性（如性能/只读密钥）。用社区版 `sqlcipher` CLI 或 `sqlcipher3` Python 包，只给 key 即可。

### 1.5 协议里的字段定义 —— `Schale__MX__NetworkProtocol__NetworkProtocol.cs:5832-5833 / 5857-5858`

```csharp
public string? EncryptedSqlCipherKey { get; set; }
public string? EncryptedSqlCipherLicense { get; set; }
```

只出现在 `QueuingGetCryptoKeysResponse` 与 `QueuingGetAuthTicketResponse` 两个类型里，没有第三个出口。⇒ **密钥只有一条下发通道**（排队/取票阶段），不走 `/api/state`，不走资源 CDN。

### 1.6 资源清单：`ExcelDB.db` 是独立下载件 —— `Shittim-Server__Configuration__ConfigResources.cs:28-32`

```csharp
var resources = new List<string>() {
    "/Preload/TableBundles/ExcelDB.db",
    "/Preload/TableBundles/Excel.zip",
    "/GameData/TableBundles/HexaMap.zip"
};
```

分发逻辑 —— 同文件 `:72-87`：

```csharp
foreach (var filename in resourcesList)
{
    var downloadUrl = baseUrl + filename;
    var downloadFilePath = Path.Combine(DownloadDir, filename.Split('/').Last());
    await DownloadFile(downloadUrl, downloadFilePath);

    if (Path.GetExtension(downloadFilePath) == ".zip") ExtractExcels(downloadFilePath);
    else File.Copy(downloadFilePath, Path.Combine(DumpedDir, filename.Split('/').Last()));
}
```

⇒ `.zip` 走**解压**分支，其余**原样复制**。`ExcelDB.db` 走的是 `File.Copy`，从头到尾没有任何解密动作——它是被 SQLCipher 加密的**整文件**，钥匙在运行时由 §1.3 下发给客户端。

### 1.7 全目录检索结果

对 `report/_tmp/shittim/` 全量检索 `SQLCipher|ExcelDb|EXCELDB|sqlite3_key|PRAGMA key|password`：

| 命中位置 | 内容 |
|---|---|
| `ServerConfig.cs:34,58,59` | `ClientExcelDbPath` / `ExcelDbSqlCipherKey` / `ExcelDbSqlCipherLicense` |
| `QueuingHandler.cs:28,34,35,83,90,91,116-158` | 密钥读取 + AES 封装 + 下发 |
| `GameServer.cs:78-79` | `ExcelTableService.ValidateExcelDbKey();` 调用点 |
| `ConfigResources.cs:29,177-185` | `ExcelDB.db` 下载 / `TableService.DumpExcelDB(...)` |
| `GatewaySessionCrypto.cs:152` | 注释："…the SqlCipher asset-DB key… the client decrypts with CBC" |
| `NetworkProtocol.cs:5832,5833,5857,5858` | 两个 Response 的字段 |

**`PRAGMA key` / `sqlite3_key` 在源码里 0 命中** —— 说明 Shittim 打开 ExcelDB 走的是 .NET 侧的 SQLCipher provider（`Services/SqliteProvider.cs`，403 B，本地未下载），而不是手写 SQL。

---

## §2 `ValidateExcelDbKey()` 的实现与它揭示的约束

### 2.1 先说清楚：函数体本地**未见**

`Services/ExcelTableService.cs`（**20,874 B**）在 `raw/DIR__Shittim-Server__Services.json` 的目录清单里存在，但 `_dl.py` 的下载列表没有它，本地 `src/` 也没有 —— 所以**函数体源码中未见**。

同样缺失但相关的（都在 DIR 清单里、都没下载）：

| 文件 | 大小 | 与本任务的关系 |
|---|---|---|
| `Services/ExcelTableService.cs` | 20,874 | **`ValidateExcelDbKey()` 就在这里** |
| `Services/ClientExcelSchema.cs` | 19,520 | `*DBSchema` 的 C# 建表定义（重建表结构要它） |
| `Services/SqliteProvider.cs` | 403 | SQLCipher provider 注册（用哪个 bundle） |
| `Services/ClientExcelBannerPatchService.cs` | 8,831 | 直写 `ExcelDB.db` 卡池行 ⇒ 证明服务端能**写**这个加密库 |
| `Services/ClientExcelCharacterSyncService.cs` | 1,263 | 同上，角色行同步 |

`Schale.Crypto.TableService`（`CreatePassword` / `DumpExcels` / `DumpExcelDB`）在 `Schale/Crypto/` 下，我们从未枚举该目录，**连清单都没有**。

### 2.2 【重构】根据三个可观测点反推

可观测点：

1. **调用点** `GameServer.cs:75-79`：
   ```csharp
   Console.WriteLine("\n[Resource Manager] Checking Excel tables...");
   await ResourceService.LoadResources(Config.Instance.ServerConfiguration.UseCustomExcel);

   // Fail fast with a clear message if the ExcelDB SQLCipher key cannot decrypt the ExcelDB.db for this client version (the key rotates between some game updates).
   ExcelTableService.ValidateExcelDbKey();
   ```
   ⇒ 位置在"资源已下载/复制到 `Resources/Dumped/`"之后、"WebApplication 起来"之前。属于**启动期 fail-fast 闸门**。

2. **成功日志**（`report/09-服务器盘点.md:390`）：`[ExcelTableService] ExcelDB SQLCipher key validated (912 schema entries).`
   ⇒ 计数量词是 **schema entries**（不是 rows、不是 tables）。这个数字 912 与 311 MB 库的 `sqlite_master` 条目数（表+视图+索引）量级吻合；`ba-data-layer.md:9` 记国服那个 160 MB 分片是 398 张表，量级也一致。

3. **失败症状**（`work/ba/audit/ba-pitfalls.md:35`）：`ValidateExcelDbKey` 报 **`SQLITE_NOTADB`**。
   ⇒ 这是 SQLCipher 的**错误钥匙签名**：拿错 key（或对明文库强行 key）时，第一页 HMAC 校验失败，SQLite 报 "file is not a database"。

据此重构（**非原文**，标注 `【重构】`）：

```csharp
// 【重构】Services/ExcelTableService.cs
public static void ValidateExcelDbKey()
{
    var path = Path.Combine(Resources.DumpedDir, "ExcelDB.db");
    if (!File.Exists(path)) throw new InvalidOperationException($"ExcelDB.db missing: {path}");

    var key = Config.Instance.ServerConfiguration.ExcelDbSqlCipherKey;   // 可能同样有 env 覆盖
    try
    {
        using var conn = new SqliteConnection($"Data Source={path}");
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = $"PRAGMA key = \"x'{key}'\";";   // 或 PRAGMA key = '{key}'，取决于 provider
        cmd.ExecuteNonQuery();
        cmd.CommandText = "SELECT count(*) FROM sqlite_master;";   // ← 触发真正的 key 校验
        var n = Convert.ToInt64(cmd.ExecuteScalar());
        Console.WriteLine($"[ExcelTableService] ExcelDB SQLCipher key validated ({n} schema entries).");
    }
    catch (SqliteException ex)
    {
        throw new InvalidOperationException(
            $"ExcelDB SQLCipher key rejected for this client version ({ex.SqliteErrorCode}: {ex.Message}). " +
            $"Set SHITTIM_EXCELDB_SQLCIPHER_KEY to the key this client version expects.", ex);
    }
}
```

### 2.3 它揭示的四条硬约束

| # | 约束 | 依据 | 对我们的意义 |
|---|---|---|---|
| C1 | 库必须落在 **`Resources/Dumped/ExcelDB.db`** | `ConfigResources.cs:179` + `:85` 的 Copy 分支 | 换库 = 换个文件，不用改代码 |
| C2 | key 必须能通过 **`sqlite_master` 计数** | 日志里的 `912 schema entries` | 判定标准是"能不能读 schema"，不是"magic 对不对" |
| C3 | key 与"客户端版本"绑定，**会轮换** | `GameServer.cs:78` 注释原文 `the key rotates between some game updates` | 拿到的 key 有版本保质期；不是永久万能钥匙 |
| C4 | 错 key 与"库是明文"**症状相同**（都是 `SQLITE_NOTADB`） | `ba-pitfalls.md:35` | **这是个陷阱**：看到 NOTADB 不能立刻断定"key 错"，也可能是"这库压根没加密" |

C4 是本次调研最重要的一条操作性结论 —— 既往把 `SQLITE_NOTADB` 一律解读成"key 不对"，实际上国服那种**明文库**被 key 一下同样是 NOTADB。

---

## §3 密钥来源判断（含证据强度）

### 3.1 判定表

| 命题 | 判定 | 强度 | 依据 |
|---|---|---|---|
| key 是源码里的固定字面量 | ✅ | **确证** | `ServerConfig.cs:58` 原文 |
| key 可被环境变量覆盖 | ✅ | **确证** | `QueuingHandler.cs:130` |
| key 会下发给客户端 | ✅ | **确证** | `QueuingHandler.cs:119-125`；`NetworkProtocol.cs:5832` |
| 这把 key 是**官方原键**（不是私服自造） | ✅ | **强推断** | 它解开了从 `ba.dn.nexoncdn.co.kr` 下的官方 311 MB 库，读出 912 schema 条目（`report/09:390`）；私服作者若要自造，就得同时重加密全网官方库，无动机 |
| key **不在客户端**里，必须联网取 | ✅ | **强推断** | ① 每版轮换（C3）→ 硬编码在 APK 里会立刻失效；② 既往把 dex / libil2cpp / libunity / global-metadata / assets / 6227 个 TableBundles 全扫过，网关域名 0 命中（`ba-pitfalls.md:130`），同法扫 key 亦无（本报告 §3.2 复核） |
| 国服与国际服**共用**同一 key | ❓ | **弱/未知** | 无任何一手证据；国服连这个文件都不一定有（§3.3） |
| 国服需要这把 key | ❌ | **反证** | 国服下发的是明文 SQLite 分片（`ba-data-layer.md:9`） |

### 3.2 客户端侧复核（本次新做）

对 `work/ba/audit/ba-apk/` 做了三件事，结论都指向"key 不在客户端，且客户端确实会用 SQLCipher 库"：

**(a) ELF `DT_NEEDED`（脚本 [`scripts/elf_needed.py`](../scripts/elf_needed.py)，纯本地解析）**

| 库 | DT_NEEDED |
|---|---|
| `libil2cpp.so` | `liblog, libm, libdl, libc, libstdc++, libtprt` |
| `libunity.so` | `libmain, libandroid, liblog, libz, libEGL, libm, libdl, libc, libstdc++, libtprt` |
| `libsqlcipher.so` | `libdl, liblog, libc, libm` |

⇒ **没有任何 Unity 库静态依赖 `libsqlcipher.so`**；`libsqlcipher.so` 也没有 `DT_NEEDED` 别的 SQLite。所以它只能在运行时被 `dlopen`。

**(b) `libil2cpp.so` 里的字符串块**（偏移 `0x2677468`，原文相邻）

```
...read_all_pcm_data_from_memory . sqlcipher . sqlite3_open_v2 . sqlite3_shutdown . UnityEngine.SpriteMask::get_backSortingOrder()...
```

`sqlcipher` 这个词**只出现这一次**，且紧贴 `sqlite3_open_v2` / `sqlite3_shutdown` 等入口名。这正是 il2cpp 里 `[DllImport("sqlcipher")]` 的形态（P/Invoke 库名 + 一串入口名放在同一元数据块）。**【推断·中】** 游戏的 C# SQLite 层把 `libsqlcipher.so` 当后端。

> ⚠️ 关键推论：**这不能反推"库文件是加密的"**。SQLCipher 在未调用 `sqlite3_key` 时对**明文** SQLite 完全透明——一个明文的 `ExcelDB.db` 用 SQLCipher 库照样能开。所以"APK 里有 libsqlcipher.so ⇒ 表是 SQLCipher 加密的"这一步是**不成立的跳跃**，也是本报告要纠正的第二个前提。

**(c) `libsqlcipher.so` 是什么**

strings 里是 `net/zetetic/database/sqlcipher/*` + `register_android_database_SQLiteConnection` + `SQLiteNotADatabaseException`，版本串 `4.10.0`（SQLCipher 核）、`3.0.17`（android-database-sqlcipher）、`3.50.4`（SQLite）。⇒ 它是 **SQLCipher-for-Android 的 JNI 封装**，既能给 Java 用（`classes2.dex` 里确有 69 处 `net/zetetic` 引用），也能给 il2cpp 通过 C API 用。

### 3.3 国服的数据形态（一手实测，已有记录）

`work/ba/audit/ba-data-layer.md`：

| 项 | 实测 |
|---|---|
| 客户端 `files/TableBundles/` | 6,231 文件 / 433 MB |
| 其中真正的 SQLite | **仅 4 个**：7.5 / 8.5 / 19 / 160 MB |
| 160 MB 那个（`6993339912994747134_824ce3a8…`） | **明文**（`SQLite format 3`），**398 张表**，全是 `*DBSchema`（剧情/本地化/字幕） |
| 玩法数值表（`CharacterDBSchema` / `ItemDBSchema`） | **不在客户端任何下载资源里**（TableBundles 无、9 GB AssetBundles grep 无、APK 内无） |

⇒ 国服是**明文分片 + 缺玩法表**，不是"一个 SQLCipher 大库"。

### 3.4 结论：密钥从哪来

**排序（从"最可能"到"最不可能"）：**

1. **固定常量（已确认就是这一条）** — 服务端侧的版本常量，跟客户端版本走，通过排队协议下发。国服若要复刻，key 只能是"国服官方那一把"，而它**只能从国服官方服务的 `Queuing_GetCryptoKeys`/`GetAuthTicket` 响应里取**，不可能从 APK 推导出来。
2. **网络下发** — 已经确认这就是它的**唯一**传输方式（§1.5），只是它下发的是**已经确定的常量**，不是"派生"。
3. **从客户端派生**（assets / GameMainConfig / 签名）— **排除**。理由：① 轮换机制要求它跟着服务端走；② 客户端扫描无命中（轮换的 key 不可能藏在客户端）；③ `GameMainConfig` 那套派生（`CreateKey('GameMainConfig')`）产出的东西是**资源地址**，不是 DB 钥匙（`report/56:967-995`）。

### 3.5 验证方法（可执行）

| # | 验什么 | 怎么做 | 期望 |
|---|---|---|---|
| V1 | key 对国际服库有效 | 服务器上：`sqlcipher Resources/Dumped/ExcelDB.db` → `PRAGMA key = "x'ef0a…bc4'";` → `SELECT count(*) FROM sqlite_master;` | **912**（与 `report/09:390` 对齐） |
| V2 | 国服那个库到底加没加密 | `head -c 16 <国服ExcelDB.db> \| xxd` | 明文 ⇒ `53 51 4c 69 74 65 20 66 6f 72 6d 61 74 20 33 00`（`SQLite format 3`）；加密 ⇒ 随机 16 字节（国际服实测是 `c4d7dbb3ac7115d4…`，`report/09:176`） |
| V3 | 线上字段是不是这把 key | 抓一次 `Queuing_GetCryptoKeys` 响应，用请求里的 `ClientGeneratedKey/IV` 做 AES-CBC 解密 `EncryptedSqlCipherKey`，再 base64 解一次 | 应等于 `7wqsoG80tKS+MXKnWj6lZegV+ezjWx+xK3oWa6CAe8Q=` |
| V4 | 国服是否同键 | 若有国服的 SQLCipher 库，用同一 key 试 `sqlite_master` | 出 912 附近 ⇒ 同键；`SQLITE_NOTADB` ⇒ 不同键或库是明文 |

**V2 优先做。** 它是 5 秒钟就能做完的一步，能直接终结"国服到底要不要 key"这个问题；V1/V3/V4 都需要服务端或抓包，成本高一个数量级。

---

## §4 替代路线与代价

按"多久能玩上"排序。**代价栏里的"能玩影响"是本项目真正关心的。**

### R1 · 直接用国际服全量库（成本 0，已通）

现状：`Resources/Dumped/ExcelDB.db` 就是 311 MB 国际服库 + 已知 key + `912 schema entries`（`report/09:390`）。**机制 100% 通**，缺的只是国服内容（`report/13:54` 的定性："缺的是国服内容不是机制"）。

- 代价：0
- 能玩影响：可玩国际服版本的活动/角色/数值；国服特有天梯、国服和谐、国服活动全缺。

### R2 · 明文分片合并 + 绕开 key（半通，已有产物）

把国服 4 个明文分片合成一个 `ExcelDB.db`（`/root/bapatch/merge_excel.py`，产物 `ExcelDB_full.db`：**13 张表 / 52 MB**，含 `Student/Enemy/Ground` 技能表），然后**不要**给它上 key。

拦路石就是 C4：`ValidateExcelDbKey()` 会无条件 `PRAGMA key` 一下明文库 → `SQLITE_NOTADB` → 进程起不来。
现有绕法（我们自己的补丁）：`SHITTIM_SKIP_EXCEL=1`（`report/04:91`）。
**但跳过校验 ≠ 能用**：`ExcelTableService` 的 provider 若仍硬编码 `PRAGMA key`，后面读表一样挂。需要确认 `SqliteProvider.cs` 的行为（本地缺失），或干脆把 key 设成空串并在服务端配置里留空。

- 代价：低（半天）
- 能玩影响：剧情/技能/本地化可用；**玩法数值表（角色成长、掉落、商店、抽卡概率）全缺**，大厅数据灌入会失败（`ba-data-layer.md:16`）。

### R3 · 自洽三角：换客户端库 + 服务端发我们自己的 key（推荐正路）

关键洞察：**客户端只是"拿服务端给的 key 去开本地库"**，而这两个东西**都在我们手里**：

```
        ① 我们把库推进客户端数据目录（明文，或按我们自己的 key 加密）
客户端 ──② 服务端在 Queuing_GetCryptoKeys 里下发对应的 key（或空 key）──> 打开成功
```

- ① 客户端库路径由 `ClientExcelDbPath`（`ServerConfig.cs:34`）+ `AutoPatchClientBanners` 体系管理，说明"改客户端 ExcelDB.db"这条路上游作者本来就在用（`ClientExcelBannerPatchService` 直写卡池行）。
- ② `SHITTIM_EXCELDB_SQLCIPHER_KEY` 随便设。
- **不必知道官方国服 key**——因为我们同时可以改客户端的库。

- 代价：中（要摸清客户端库的落盘路径与写入时机；国服路径可能不是 `ClientExcelDbPath` 默认值）
- 能玩影响：与 R1/R2 同，取决于塞进去的是什么库；**但这是唯一能"用国服数据 + 不依赖官方 key"的组合**。
- 风险：客户端可能校验库的完整性/版本号（未验证）。

### R4 · 老版本明文 Android `ExcelDB.db`

2024 年国际服 Android 的 `TableBundles/ExcelDB.db` 是**明文**（`ba-data-layer.md:30` 引 52pojie 实证）。

- 代价：低（找包）
- 能玩影响：全量表结构对得上（老版本），缺 2025-2026 的新表/新列；`ba-pitfalls.md:36` 已记 flatbuffer 版本必须对齐（65 vs 67 槽位），SQL 表同样有版本漂移风险。

### R5 · 运行时 dump（**与硬约束冲突**）

客户端已经用 key 把库打开在内存里，理论上可以：
- hook `sqlite3_key` 抓参数（`libsqlcipher.so` 导出符号 + `libil2cpp` 运行时 dlopen ⇒ 可 hook）——但 ACE 会记账（`ba-pitfalls.md:59-70`）；
- 或 dump 解密后的页（客户端临时目录 / page cache）。

- 代价：高（需上机，违反本次硬约束；且 R3 已经用更便宜的方式解决了同一问题）
- 能玩影响：真值，但性价比最低。

### R6 · 从 flatbuffer `.bytes` 反向建库

`Excel.zip` 解出来的 62 个 `.bytes` 是**明文 flatbuffer**（口令 zip 解完 + `TableEncryptionService.XOR` 剥掉后），表结构可从 `global-metadata.dat` 的 C# 类定义推。

- 代价：周级
- 能玩影响：数据是"客户端那份"，仍缺玩法表（因为客户端压根没有）。

### R7 · 不用真值、用推算

- 代价：0
- 能玩影响：**能启动、能进大厅、界面能显示**，但数值全错——抽卡池空/角色属性错/关卡打不过/商店价格乱。作为"验证链路"可以，作为"能玩"不可接受。

### 横向对照

| 路线 | 需要国服 SQLCipher key | 得到玩法表 | 工时 | 合规 |
|---|---|---|---|---|
| R1 | ❌（用国际服 key） | ✅（国际服内容） | 0 | ✅ |
| R2 | ❌ | ❌ | 0.5 d | ✅ |
| **R3** | ❌（自定） | ✅（取决于塞什么库） | 1–2 d | ✅ |
| R4 | ❌ | ✅（老版本） | 0.5 d | ✅ |
| R5 | ✅ | ✅ | 2 d+ | ❌ 需上机 |
| R6 | ❌ | ❌ | 5 d+ | ✅ |

---

## §5 「zip 口令」与「SQLCipher」到底是什么关系

### 5.1 结论（一句话）

**并列的两条独立链路，不是同一文件的两层锁。**

```
/Preload/TableBundles/ExcelDB.db  ──(原样复制)──> Resources/Dumped/ExcelDB.db
                                                     └─ SQLCipher 加解密；钥匙 = ExcelDbSqlCipherKey（32B raw key，排队协议下发）

/Preload/TableBundles/Excel.zip   ──(口令解压)──> Resources/Dumped/Excel/*.bytes  (62 个)
                                                     ├─ 口令 = Base64(CreatePassword("Excel.zip"))
                                                     └─ 每个 .bytes 内部还有 TableEncryptionService.XOR 一层
```

**`ExcelDB.db` 从来不在 `Excel.zip` 里。** 两把"锁"各自锁各自的文件。

### 5.2 代码证据（4 条，`ConfigResources.cs`）

| 行 | 原文/行为 | 说明 |
|---|---|---|
| `:29-30` | 资源清单里 `ExcelDB.db` 与 `Excel.zip` **并列两项** | 两个独立下载 URL |
| `:84-85` | `if (Path.GetExtension(...) == ".zip") ExtractExcels(...); else File.Copy(...)` | `.db` 走 **Copy**，与解压无关 |
| `:165-171` | `ExtractExcels`：`zip.Password = Convert.ToBase64String(TableService.CreatePassword(Path.GetFileName(filePath)))` → `ExtractAll(Dumped/Excel/)` | zip 线只产出 `.bytes` |
| `:177-185` | `excelDbPath = Path.Combine(excelDbDir, "ExcelDB.db")` → `TableService.DumpExcelDB(excelDbPath, …)` | SQLCipher 线直接读下载目录里的那个文件 |

### 5.3 运行证据（一条实机清单，`report/09-服务器盘点.md:176-178`）

```
Resources/Dumped/ExcelDB.db   311,083,008 B   头部 c4d7dbb3ac7115d4…（不是 SQLite format 3）= SQLCipher 加密
Resources/Dumped/Excel/*.bytes   62 个         mtime 全是 Jul 31 15:50（来自 zip）
```

**两样东西同时存在、来源不同、互不包含。** 这是最直接的反证：如果 `ExcelDB.db` 是 zip 里解出来的，它就会落在 `Dumped/Excel/` 里，而不是 `Dumped/` 根下；而 `Dumped/` 根下那份是 `.db` 非 `.zip` 走 `File.Copy` 的结果。

### 5.4 第三层 XOR 属于 zip 那条线，与 SQLCipher 无派生关系

`report/56:1001-1024` 记的看雪链条是：

| 层 | 机制 | 作用对象 | 钥匙材料 |
|---|---|---|---|
| L1 | SharpZipLib 带口令 zip | `Excel.zip` | `Base64(CreatePassword(bundleName, 20))`，15 B MT 随机数 → base64 |
| L2 | `TableEncryptionService.XOR(name, bytes)` | zip 里的每个 `.bytes` | 表名派生的 MT 流 |

这两层**都只作用于 `Excel.zip` → `.bytes` 这条线**。`ExcelDB.db` 那条线只有 SQLCipher 一层，而它的钥匙是 32 字节 raw AES key（`ef0a…`），**与 `CreatePassword` 的 MT/xxHash32 输出没有任何数学关系**——一个是 `MT.NextBytes(15)` 的 base64（20 字符口令），一个是固定的 32 字节密钥。把两者混为一谈会导致无谓的派生尝试。

> 补充（`report/56:1016-1018`）：`CreatePassword` 的细节是 `seed = xxHash32(UTF8(name))` → `MT(seed)` → `NextBytes(15)` → `Base64` = 20 字符；`Next()` 是 `(genrand_int32() >> 1) & 0x7FFFFFFF`，`NextBytes` 每 4 字节调一次、小端写入。这条只对 zip 口令有效。

### 5.5 给后续文档的命名约定（避免再混）

以后不要再说"表包有两层加密"。请按这三件事分开命名：

| 名字 | 文件 | 加密 | 钥匙来源 |
|---|---|---|---|
| **A. 表库线** | `ExcelDB.db`（~311 MB 国际服） | SQLCipher 4（AES-256 + HMAC-SHA512） | `ExcelDbSqlCipherKey`，排队协议下发 |
| **B. 表包线** | `Excel.zip` → 62 × `.bytes` | SharpZipLib 口令 zip + 表内 XOR | `CreatePassword(bundleName)` |
| **C. 地图线** | `HexaMap.zip` | 同 B（口令 zip） | 同 B |

**A 和 B 是替代/并行的两套数据通道**（Shittim 两套都下载、两套都尝试用），不是先后两层。

---

## §6 复现清单（拿到库就能跑）

### 6.1 最小命令（CLI）

```bash
sqlcipher Resources/Dumped/ExcelDB.db
```
```sql
-- raw key 模式：64 hex 必须用 x'…' 包起来，否则会被当成口令走 PBKDF2（最常见失败原因）
PRAGMA key = "x'ef0aaca06f34b4a4be3172a75a3ea565e815f9ece35b1fb12b7a166ba0807bc4'";
SELECT count(*) FROM sqlite_master;        -- 期望 912
SELECT type,name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 20;
```
导出明文副本：
```sql
ATTACH DATABASE 'ExcelDB_plain.db' AS plaintext KEY '';
SELECT sqlcipher_export('plaintext');
DETACH DATABASE plaintext;
```

### 6.2 Python

```python
from sqlcipher3 import dbapi2 as sqlite3

KEY = "ef0aaca06f34b4a4be3172a75a3ea565e815f9ece35b1fb12b7a166ba0807bc4"
con = sqlite3.connect("ExcelDB.db")
con.execute(f"PRAGMA key = \"x'{KEY}'\"")
print(con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0])   # 912
print(con.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 10").fetchall())
```

### 6.3 如果 912 没出来（参数矩阵，按序试）

SQLCipher 4 默认：`page_size=4096, kdf_iter=256000, HMAC-SHA512, PBKDF2-HMAC-SHA512`。库版本 4.10.0（License 的 `libver` + `.so` 版本串一致），正常情况下上面对。若失败：

```sql
-- 1) 显式 v4 参数
PRAGMA key = "x'…'";
PRAGMA cipher_page_size = 4096;
PRAGMA cipher_hmac_algorithm = HMAC_SHA512;
PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;
SELECT count(*) FROM sqlite_master;

-- 2) v3 兼容（若客户端用了 cipher_compatibility=3）
PRAGMA cipher_compatibility = 3;   -- 必须在 key 之前
PRAGMA key = "x'…'";

-- 3) 反例排除：当成口令（PBKDF2）
PRAGMA key = 'ef0aaca06f34b4a4be3172a75a3ea565e815f9ece35b1fb12b7a166ba0807bc4';
```

`.so` 里出现 `cipher_default_plaintext_header_size`、`cipher_compatibility`、`MAX_DEFAULT_PAGE_SIZE=8192`、`sqlcipher_master` 表等符号 ⇒ 这是带商业扩展的定制构建；社区版对**读取**应当兼容，若遇 `plaintext_header_size` 相关的库才需要额外设 `PRAGMA cipher_plaintext_header_size = 32;`。

---

## §7 本次未做 / 不能做

| 项 | 原因 |
|---|---|
| 连服务器实测 V1 | 硬约束（不连服务器） |
| 连手机 dump / hook | 硬约束（不连手机） |
| 读 `libtprt.so` 内容 | 硬约束（不碰） |
| `ExcelTableService.cs` 原文 | 上游仓库该文件未在本快照下载（只在 DIR 清单里）。若需要原文，需补一次 GitHub 拉取（本次未做，按"只读本地"约束） |
| 验证国服库里到底有没有 SQLCipher 文件 | 国服 CDN 的 `/Preload/TableBundles/ExcelDB.db` 是否存在，需要一次 HEAD 请求；本次未做 |

---

## 附：一页速查

```
密钥（raw 32B hex）：ef0aaca06f34b4a4be3172a75a3ea565e815f9ece35b1fb12b7a166ba0807bc4
base64(32B)       ：7wqsoG80tKS+MXKnWj6lZegV+ezjWx+xK3oWa6CAe8Q=
License(b64)      ：OmNpZDowMDFWSjAwMDAwY3pzaVlZQVE6cGxhdGZvcm06MjY6…（解出 :cid:…:libver:4.10.0:hmac:…）
env 覆盖          ：SHITTIM_EXCELDB_SQLCIPHER_KEY / SHITTIM_EXCELDB_SQLCIPHER_LICENSE
落盘位置          ：<server>/Config/Config.json（首次启动自动写入明文）
下发通道          ：Queuing_GetCryptoKeys / Queuing_GetAuthTicket → EncryptedSqlCipherKey
本地库路径        ：Resources/Dumped/ExcelDB.db（311 MB，头部 c4d7dbb3…）
验证指纹          ：SELECT count(*) FROM sqlite_master → 912
```
