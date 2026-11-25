# Shittim-Server `ClientMetadataPatchService` 研究

> 目标：搞清楚上游私服（`Neoexm/Shittim-Server`，Steam/PC 版）到底怎么补丁 `global-metadata.dat`，以及这套做法对**国服 3.0.2（header 被混淆，magic `0x12724394`）**是否适用。
> 性质：纯源码阅读 + 本工程既有取证结果交叉引用，**未对任何设备/服务端执行任何操作**。
> 结论摘要见 §3；逐条问答见 §4；适用性判断见 §5。

---

## 0. 取证方式与可信度

| 项 | 值 | 说明 |
|---|---|---|
| 仓库 | `https://github.com/Neoexm/Shittim-Server` | 公开，465★，`private:false`，`default_branch: main`（**不是 master**，`trees/master` 返回 404） |
| 路径 | `Shittim-Server/Services/ClientMetadataPatchService.cs` | GitHub contents API 实测存在，`size: 18931` |
| 上游 blob sha | `10bfa36a88dd4ad2ae62281b626ca169ea847e70` | GitHub API 返回的 `sha` 即 git blob sha1 |
| 本地副本 | `report\_tmp\shittim\src\Shittim-Server__Services__ClientMetadataPatchService.cs`，18,931 B | 本工程上一轮抓取 |
| 本地文件自算 git blob sha1 | `10bfa36a88dd4ad2ae62281b626ca169ea847e70` | **与上游逐字节相同**（sha1 diff 级证明，不是"看起来像"） |
| 同族文件校验 | `ClientRegionLabelPatchService` 11859 B / `3ccc84e3…`；`ClientInfaceConfigPatchService` 11925 B / `dd2b536e…` | 本地副本与上游 `Services/` 目录清单里的 `size`+`sha` 同样一致 |
| `ClientStoreUrlPatchService` | 未存本地副本，直接读 GitHub contents API 的 base64 `content` 并解码 | 一手；本文引用的代码即解码结果 |

**为什么用 blob sha 而不是 raw 抓取**：`raw.githubusercontent.com` 在本机 `web_fetch` 直连失败（`TypeError: fetch failed`），而 `api.github.com` 可用。git blob sha1 = `sha1("blob <len>\0" + <content>)`，本地算出与上游 `sha` 字段完全一致 ⇒ 本地这份就是 `main` 分支当前的原文，未做任何改动。所以下面的"原文"是**上游真实内容**，不是我复述的。

试过但不可用的 URL（记录在案）：
- `https://api.github.com/repos/Neoexm/Shittim-Server/git/trees/master?recursive=1` → **404**（分支是 `main`）
- `https://raw.githubusercontent.com/Neoexm/Shittim-Server/main/Shittim-Server/Services/ClientMetadataPatchService.cs` → **fetch failed**（本机网络层，非 404）
- `https://api.github.com/repos/Neoexm/Shittim-Server/contents/...` → **200，可用**

---

## 1. 文件原文（`ClientMetadataPatchService.cs`，434 行，逐字节等同上游 `main`）

```csharp
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using BlueArchiveAPI.Configuration;

namespace Shittim_Server.Services
{
    public class ClientMetadataPatchService : IHostedService
    {
        // The key is three separate string literals in the metadata rather than one run, and the split lands wherever the build's literal packing put it: 272/272/255 for the RSA-4096 key, and 150/150/150 for the RSA-2048 one it replaced.
        private static readonly int[] ChunkLengths = [272, 272, 255];
        private const int ChunkCount = 3;

        // The official Nexon gateway RSA-4096 public key, exactly as it is embedded inside the client's global-metadata.dat.
        // The client RSA-encrypts the 50001 gateway handshake with this key, so swapping in the private server's own key is what lets the gateway decode the handshake. Ours has to be 4096-bit as well: the chunks are fixed-size holes in fieldAndParameterDefaultValueData, and a PEM of any other length cannot go into them without shifting the section and every offset past it.
        //
        // The three byte runs are located by content (an AOB scan) rather than by fixed file offsets: the offsets move every time the client is rebuilt, and build 439170 shifted all three by +0x49B0.
        // Writing at a stale offset corrupts whatever IL2CPP metadata now lives there and hangs the client at "Unpacking game resources". A scan also fails safe: a chunk that cannot be found means no write at all.
        private const string OfficialGatewayPublicKeyPem =
            "-----BEGIN PUBLIC KEY-----\n" +
            "MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAz1oODtVINPQsTIbFDiL2\n" +
            "IIj3YqDGxZ1WqJWfJrpo7ZqdnSIMXaVqVyM07Zguc9wczPrluDNowheP8NXe8uTR\n" +
            "prO7jpF9bOcrrit9Xyxf57NA5rIMqOj6/XgWzzptvvt3oUrOQJRTvEjusQCX79Ds\n" +
            "fhhbPRfdPzZUOPYa49MM385Z05ndNiTB9/yhxP5+5zm7TS3f6/o1Ntw9yXoRYmgR\n" +
            "8+JYGL6TpqtZHkqPTp6kIJrnsLyT1wRteh3oQKJaze0CM0DUUzFiqieRE8c8JAoV\n" +
            "jk/yRQUqVMoKbdpINYlWhF+GFE/ccSpqQymepHxfR0alspynqJwJgODCeHtwuno5\n" +
            "HEOwdbA8NanLVnE9qlvdeNkbODdt/XTHKOaXx+SUMHezUY0rEXp8WMim0i9IQTGa\n" +
            "YWeW25RjXIZswKdg0gLRJXYZXUgF3nVcqr0hi4kv1pgrFPsjI7yIThxLY0UfomkR\n" +
            "oe6sSBBtQUDI85s+1pZRcl8xygxOxMfFSk5RB3EntFmcf/AKaLYQbXN9RxgrvqRS\n" +
            "9koBBEnnrIN0zXDBioZUDOWVBeBZwAydpPGKu2mkqu3BI/Al92noEHc6fmkG5+Qm\n" +
            "b237xSh1DFbbQO6lxg4ABdsqgvZskYS+7BcQPjs1z2zftrnesFkqD7BhbqXUBuDY\n" +
            "D80B8Be5I483qSSy8DsW458CAwEAAQ==\n" +
            "-----END PUBLIC KEY-----";

        private static readonly JsonSerializerOptions JsonOptions = new()
        {
            WriteIndented = true
        };

        private readonly ILogger<ClientMetadataPatchService> logger;
        private MetadataPatchState patchState;
        private string metadataPath;

        public ClientMetadataPatchService(ILogger<ClientMetadataPatchService> logger)
        {
            this.logger = logger;
        }

        public Task StartAsync(CancellationToken cancellationToken)
        {
            try
            {
                metadataPath = GetMetadataPath();

                if (!IsEnabled())
                {
                    // Turning the patch off is how someone goes back to the official client, so it has to mean putting the key back rather than merely not patching again. A global-metadata.dat left carrying our gateway key hangs the client on "Unpacking game resources" with nothing on screen to say why, and the usual guess is to verify the files through Steam.
                    RestoreMetadata();
                    logger.LogInformation("Client metadata auto-patch disabled");
                    return Task.CompletedTask;
                }

                if (string.IsNullOrWhiteSpace(metadataPath))
                {
                    logger.LogWarning("Client metadata auto-patch is enabled, but no metadata path was configured");
                    return Task.CompletedTask;
                }

                if (!File.Exists(metadataPath))
                {
                    logger.LogWarning("Client metadata file not found: {MetadataPath}", metadataPath);
                    return Task.CompletedTask;
                }

                var publicKey = GetGatewayPublicKey();
                if (string.IsNullOrWhiteSpace(publicKey))
                {
                    logger.LogWarning("Client metadata auto-patch is enabled, but no gateway public key was found");
                    return Task.CompletedTask;
                }

                var officialChunks = BuildKeyChunks(OfficialGatewayPublicKeyPem, "official gateway public key");
                var targetChunks = BuildKeyChunks(publicKey, "gateway public key");
                patchState = PatchMetadata(metadataPath, officialChunks, targetChunks);
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Failed to patch client metadata");
            }

            return Task.CompletedTask;
        }

        public Task StopAsync(CancellationToken cancellationToken)
        {
            try
            {
                RestoreMetadata();
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Failed to restore client metadata");
            }

            return Task.CompletedTask;
        }

        private MetadataPatchState PatchMetadata(string path, byte[][] officialChunks, byte[][] targetChunks)
        {
            var statePath = GetStatePath(path);
            var fileBytes = File.ReadAllBytes(path);

            // Resolve where each key chunk currently lives by scanning for its bytes: a chunk is either still the official key (needs patching) or already ours (patched on an earlier run).
            // If neither turns up, abort without writing rather than corrupt the file.
            var offsets = new long[ChunkCount];
            var alreadyPatched = true;
            for (var i = 0; i < ChunkCount; i++)
            {
                if (TryLocateUnique(fileBytes, officialChunks[i], out var officialOffset))
                {
                    offsets[i] = officialOffset;
                    alreadyPatched = false;
                }
                else if (TryLocateUnique(fileBytes, targetChunks[i], out var patchedOffset))
                {
                    offsets[i] = patchedOffset;
                }
                else
                {
                    logger.LogWarning(
                        "Gateway public key chunk {Index} was not found in client metadata. The client build " +
                        "may have changed how the key is stored; leaving {MetadataPath} unchanged to avoid " +
                        "corrupting it.", i, path);
                    return null;
                }
            }

            if (alreadyPatched)
            {
                // The official key is a known constant, so the original bytes stay recoverable regardless of any stale sidecar left by an older client build.
                var state = CreateState(offsets, officialChunks, targetChunks);
                SaveState(statePath, state);
                logger.LogInformation("Client metadata already patched: {MetadataPath}", path);
                return state;
            }

            using (var stream = File.Open(path, FileMode.Open, FileAccess.ReadWrite, FileShare.Read))
            {
                WriteChunks(stream, offsets, targetChunks);
            }

            var patchState = CreateState(offsets, officialChunks, targetChunks);
            SaveState(statePath, patchState);

            logger.LogInformation("Patched client metadata gateway key at 0x{O0:X}, 0x{O1:X}, 0x{O2:X}: {MetadataPath}",
                offsets[0], offsets[1], offsets[2], path);
            return patchState;
        }

        private void RestoreMetadata()
        {
            var path = metadataPath ?? patchState?.MetadataPath;
            if (string.IsNullOrWhiteSpace(path))
                return;

            var statePath = GetStatePath(path);
            var state = patchState ?? LoadState(statePath);
            if (state == null)
                return;

            if (!File.Exists(path))
            {
                logger.LogWarning("Client metadata file disappeared before restore: {MetadataPath}", path);
                return;
            }

            var offsets = state.Chunks.Select(c => c.Offset).ToArray();
            var patchedChunks = state.Chunks.Select(c => Convert.FromBase64String(c.Patched)).ToArray();
            var originalChunks = state.Chunks.Select(c => Convert.FromBase64String(c.Original)).ToArray();

            using var stream = File.Open(path, FileMode.Open, FileAccess.ReadWrite, FileShare.Read);
            var currentChunks = ReadChunks(stream, offsets);

            if (!ChunksEqual(currentChunks, patchedChunks))
            {
                logger.LogWarning("Client metadata did not match the active patch state. Leaving it unchanged: {MetadataPath}", path);
                return;
            }

            WriteChunks(stream, offsets, originalChunks);

            if (File.Exists(statePath))
                File.Delete(statePath);

            logger.LogInformation("Restored client metadata: {MetadataPath}", path);
        }

        // Splits a PEM public key at the lengths the client stores its own in. Newlines are normalized to '\n' and any trailing newline trimmed so the byte layout is identical to the metadata's embedded copy.
        private static byte[][] BuildKeyChunks(string publicKey, string label)
        {
            var normalized = publicKey
                .Replace("\r\n", "\n")
                .Replace("\r", "\n")
                .TrimEnd('\n');

            var publicKeyBytes = Encoding.ASCII.GetBytes(normalized);
            if (publicKeyBytes.Length != ChunkLengths.Sum())
                throw new InvalidOperationException($"The {label} must be {ChunkLengths.Sum()} ASCII bytes after newline normalization, got {publicKeyBytes.Length}");

            var chunks = new byte[ChunkCount][];
            var at = 0;
            for (var i = 0; i < ChunkCount; i++)
            {
                chunks[i] = publicKeyBytes.Skip(at).Take(ChunkLengths[i]).ToArray();
                at += ChunkLengths[i];
            }

            return chunks;
        }

        // Finds the single occurrence of pattern in data. Returns false if absent or ambiguous (found more than once) so the caller can fail safe instead of patching the wrong location.
        private static bool TryLocateUnique(byte[] data, byte[] pattern, out long offset)
        {
            offset = -1;
            var span = data.AsSpan();
            var start = 0;
            while (start <= data.Length - pattern.Length)
            {
                var index = span[start..].IndexOf(pattern);
                if (index < 0)
                    break;

                var absolute = start + index;
                if (offset >= 0)
                {
                    // More than one match: cannot safely choose one.
                    offset = -1;
                    return false;
                }

                offset = absolute;
                start = absolute + 1;
            }

            return offset >= 0;
        }

        private static byte[][] ReadChunks(FileStream stream, long[] offsets)
        {
            var chunks = new byte[offsets.Length][];

            for (var i = 0; i < offsets.Length; i++)
            {
                chunks[i] = new byte[ChunkLengths[i]];
                stream.Position = offsets[i];

                var read = stream.Read(chunks[i], 0, ChunkLengths[i]);
                if (read != ChunkLengths[i])
                    throw new IOException($"Could not read metadata patch chunk at 0x{offsets[i]:X}");
            }

            return chunks;
        }

        private static void WriteChunks(FileStream stream, long[] offsets, byte[][] chunks)
        {
            if (chunks.Length != offsets.Length)
                throw new InvalidOperationException("Invalid metadata patch chunk count");

            for (var i = 0; i < offsets.Length; i++)
            {
                if (chunks[i].Length != ChunkLengths[i])
                    throw new InvalidOperationException("Invalid metadata patch chunk length");

                stream.Position = offsets[i];
                stream.Write(chunks[i], 0, chunks[i].Length);
            }

            stream.Flush(true);
        }

        private static MetadataPatchState CreateState(long[] offsets, byte[][] originalChunks, byte[][] patchedChunks)
        {
            return new MetadataPatchState
            {
                MetadataPath = "",
                Chunks = Enumerable.Range(0, offsets.Length)
                    .Select(index => new MetadataPatchChunk
                    {
                        Offset = offsets[index],
                        Original = Convert.ToBase64String(originalChunks[index]),
                        Patched = Convert.ToBase64String(patchedChunks[index])
                    })
                    .ToList()
            };
        }

        private static bool ChunksEqual(byte[][] left, byte[][] right)
        {
            return left.Length == right.Length && left.Zip(right).All(pair => pair.First.SequenceEqual(pair.Second));
        }

        private static string GetStatePath(string path)
        {
            return $"{path}.shittim_patch.json";
        }

        private static MetadataPatchState LoadState(string statePath)
        {
            if (!File.Exists(statePath))
                return null;

            return JsonSerializer.Deserialize<MetadataPatchState>(File.ReadAllText(statePath));
        }

        private void SaveState(string statePath, MetadataPatchState state)
        {
            state.MetadataPath = metadataPath ?? state.MetadataPath;
            File.WriteAllText(statePath, JsonSerializer.Serialize(state, JsonOptions));
        }

        private static bool IsEnabled()
        {
            var env = Environment.GetEnvironmentVariable("SHITTIM_AUTO_PATCH_METADATA");
            if (!string.IsNullOrWhiteSpace(env) && bool.TryParse(env, out var enabled))
                return enabled;

            var config = Config.Instance.ServerConfiguration;
            return config.EnableGateway && config.AutoPatchClientMetadata;
        }

        internal static string GetMetadataPath()
        {
            var configuredPath = Environment.GetEnvironmentVariable("SHITTIM_CLIENT_METADATA_PATH");
            if (string.IsNullOrWhiteSpace(configuredPath))
                configuredPath = Config.Instance.ServerConfiguration.ClientMetadataPath;

            if (!string.IsNullOrWhiteSpace(configuredPath))
                return ResolvePath(configuredPath);

            // Any Steam library can hold the install.
            return SteamGameLocator.FindGameFile(Path.Combine("BlueArchive_Data", "il2cpp_data", "Metadata", "global-metadata.dat"));
        }

        private static string GetGatewayPublicKey()
        {
            var publicKey = Environment.GetEnvironmentVariable("SHITTIM_GATEWAY_RSA_PUBLIC_KEY");
            if (!string.IsNullOrWhiteSpace(publicKey))
                return publicKey;

            if (!string.IsNullOrWhiteSpace(Config.Instance.ServerConfiguration.GatewayRsaPublicKeyPem))
                return Config.Instance.ServerConfiguration.GatewayRsaPublicKeyPem;

            var publicKeyPath = Environment.GetEnvironmentVariable("SHITTIM_GATEWAY_RSA_PUBLIC_KEY_PATH");
            if (string.IsNullOrWhiteSpace(publicKeyPath))
                publicKeyPath = Config.Instance.ServerConfiguration.GatewayRsaPublicKeyPath;

            var publicKeyCandidates = new List<string>();

            if (!string.IsNullOrWhiteSpace(publicKeyPath))
                publicKeyCandidates.Add(ResolvePath(publicKeyPath));

            var privateKeyPath = Config.Instance.ServerConfiguration.GatewayRsaPrivateKeyPath;
            if (!string.IsNullOrWhiteSpace(privateKeyPath))
            {
                var privateKeyDirectory = Path.GetDirectoryName(ResolvePath(privateKeyPath));
                if (!string.IsNullOrWhiteSpace(privateKeyDirectory))
                    publicKeyCandidates.Add(Path.Combine(privateKeyDirectory, "GatewayPublicKey.pem"));
            }

            publicKeyCandidates.Add(Path.Combine(Config.ConfigDirectory, "GatewayPublicKey.pem"));

            foreach (var candidate in publicKeyCandidates.Distinct(StringComparer.OrdinalIgnoreCase))
            {
                if (File.Exists(candidate))
                    return File.ReadAllText(candidate);
            }

            var privateKey = GetGatewayPrivateKey();
            if (string.IsNullOrWhiteSpace(privateKey))
                return "";

            using var rsa = RSA.Create();
            rsa.ImportFromPem(privateKey);
            return rsa.ExportSubjectPublicKeyInfoPem();
        }

        private static string GetGatewayPrivateKey()
        {
            var privateKey = Environment.GetEnvironmentVariable("SHITTIM_GATEWAY_RSA_PRIVATE_KEY");
            if (!string.IsNullOrWhiteSpace(privateKey))
                return privateKey;

            var privateKeyPath = Environment.GetEnvironmentVariable("SHITTIM_GATEWAY_RSA_PRIVATE_KEY_PATH");
            if (string.IsNullOrWhiteSpace(privateKeyPath))
                privateKeyPath = Config.Instance.ServerConfiguration.GatewayRsaPrivateKeyPath;

            if (!string.IsNullOrWhiteSpace(privateKeyPath))
            {
                privateKeyPath = ResolvePath(privateKeyPath);
                if (File.Exists(privateKeyPath))
                    return File.ReadAllText(privateKeyPath);
            }

            var defaultPrivateKeyPath = Path.Combine(Config.ConfigDirectory, "GatewayPrivateKey.pem");
            if (File.Exists(defaultPrivateKeyPath))
                return File.ReadAllText(defaultPrivateKeyPath);

            return Config.Instance.ServerConfiguration.GatewayRsaPrivateKeyPem;
        }

        private static string ResolvePath(string path)
        {
            if (Path.IsPathRooted(path))
                return path;

            var basePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, path);
            return File.Exists(basePath) ? basePath : Path.GetFullPath(path);
        }

        private sealed class MetadataPatchState
        {
            public string MetadataPath { get; set; } = "";
            public List<MetadataPatchChunk> Chunks { get; set; } = [];
        }

        private sealed class MetadataPatchChunk
        {
            public long Offset { get; set; }
            public string Original { get; set; } = "";
            public string Patched { get; set; } = "";
        }
    }
}
```

---

## 2. 同族文件、接口、DI 注册、调用点

### 2.1 DI 注册（启动即执行）

`Shittim-Server/CLI/GameServer.cs:99-108`（`builder.Services.AddHostedService<...>()`）：

```csharp
builder.Services.AddHostedService<ClientMetadataPatchService>();
builder.Services.AddHostedService<ClientSteamOfflinePatchService>();
builder.Services.AddHostedService<ClientGrap64ManagementService>();
builder.Services.AddHostedService<ClientInfaceConfigPatchService>();
builder.Services.AddHostedService<ClientNativeIasPatchService>();
builder.Services.AddHostedService<ClientExcelBannerPatchService>();
builder.Services.AddHostedService<ClientExcelCharacterSyncService>();
builder.Services.AddHostedService<ClientCatalogPatchService>();
builder.Services.AddHostedService<ClientRegionLabelPatchService>();
builder.Services.AddHostedService<ClientStoreUrlPatchService>();
```

- 没有自定义接口，直接实现 `IHostedService`：`StartAsync` 打补丁，`StopAsync` 还原。
- 它**不是** HTTP 中间件、不是 Controller、不在请求路径上 —— 是"服务端启动时顺手改客户端文件"的旁路服务。
- 同族 10 个 patcher 都挂在这一个列表里，`ClientMetadataPatchService` 是**第一个**，且被另外两个 patcher 当成公共工具类用：
  - `ClientRegionLabelPatchService.cs:63` → `var path = ClientMetadataPatchService.GetMetadataPath();`
  - `ClientStoreUrlPatchService.cs` → `var path = ClientMetadataPatchService.GetMetadataPath();`（同一句）
  - 即 `internal static string GetMetadataPath()` 是**事实上的公共 API**（`internal`，同程序集可见）。

### 2.2 配置面（`ServerConfig`）

`Shittim-Server/Configuration/ConfigType/ServerConfig.cs:5,13-17,20-21`：

```csharp
public Version GameVersion { get; set; } = new("1.90.439170");
public bool EnableGateway { get; set; } = true;
public string GatewayRsaPrivateKeyPem { get; set; } = "";
public string GatewayRsaPrivateKeyPath { get; set; } = "";
public string GatewayRsaPublicKeyPem { get; set; } = "";
public string GatewayRsaPublicKeyPath { get; set; } = "";
public bool AutoPatchClientMetadata { get; set; } = true;   // ← 默认开
public string ClientMetadataPath { get; set; } = "";
```

`GameVersion` 默认 `1.90.439170` 与代码注释里"build 439170 让三段整体挪了 +0x49B0"是同一次构建，可互证。

### 2.3 同族另外两个"改 metadata"的 patcher（关键对照）

这两个**才是**依赖标准 header 的，必须和 `ClientMetadataPatchService` 区分开。

**(a) `ClientStoreUrlPatchService.cs` —— 改 `stringLiteral` 记录本身：**

```csharp
var literals = BitConverter.ToInt32(bytes, 8);      // stringLiteralOffset
var literalsSize = BitConverter.ToInt32(bytes, 12);
var data = BitConverter.ToInt32(bytes, 16);          // stringLiteralDataOffset
var dataSize = BitConverter.ToInt32(bytes, 20);
...
stream.Position = data + index;                      // 改字面量数据
stream.Write(wanted, 0, wanted.Length);
stream.Position = record;                            // 改 8 字节记录里的 length
stream.Write(BitConverter.GetBytes(wanted.Length), 0, 4);
```

常量原文：

```csharp
private const string StockUrl = "https://store.steampowered.com/api/appdetails?appids={0}";
private const string LocalUrl = "http://127.0.0.1:5000/api/appdetails?appids={0}";
```

**(b) `ClientRegionLabelPatchService.cs:69-76,254-257` —— 改 `ServerRegion` 枚举成员名（名字表）+ 字面量记录：**

```csharp
var literalOffset = BitConverter.ToInt32(bytes, 8);
var literalSize   = BitConverter.ToInt32(bytes, 12);
var literalData   = BitConverter.ToInt32(bytes, 16);
var literalDataSize = BitConverter.ToInt32(bytes, 20);
var stringOffset  = BitConverter.ToInt32(bytes, 24);   // 名字表
var stringSize    = BitConverter.ToInt32(bytes, 28);
var fieldsOffset  = BitConverter.ToInt32(bytes, 96);   // fieldDefinitions
var fieldsSize    = BitConverter.ToInt32(bytes, 100);
...
for (var i = 8; i < 8 + 31 * 8; i += 8)               // 遍历 header 里 31 个 (offset,size) 对
    end = Math.Max(end, BitConverter.ToInt32(bytes, i) + BitConverter.ToInt32(bytes, i + 4));
```

常量原文：`FieldRecordSize = 12`、`LiteralRecordSize = 8`、`RoutedRegionField = 3`、`StockRegionName = "asia"`、`ServerRegionFields = { "value__", "kr", "tw", "asia", "na", "global" }`。

> **这两个 patcher 是"按 header 里的 u32 读区段起点"的**（偏移 8/12/16/20/24/28/96/100 都是 `Il2CppGlobalMetadataHeader` 的标准字段位置），且**不校验 magic/version**。这才是"依赖标准 header"的部分；`ClientMetadataPatchService` 不是。

### 2.4 官方文档的说法（`docs/docs/server/client-patching.md`）

| Patcher | File | What it changes |
| --- | --- | --- |
| Metadata | `global-metadata.dat` | **the server's RSA public key, in three 150-byte chunks**, and the region label |
| Gamescale IAS | `gamescale.core.dll` | the login endpoint |
| Inface config | the inface config file | endpoint configuration |
| Steam offline | `GameAssembly.dll` | off by default; lets the client hand out an external ticket with Steam offline |
| grap64 | the plugin directory | plugin management |
| Banners | the client's `ExcelDB.db` | recruitment banner rows |
| Region label | `global-metadata.dat` | the title-screen region name |
| Store URL | the client's store lookup | points it at this server so the shop currency check answers with no route out |

注意：**文档写"three 150-byte chunks"，代码写 `[272,272,255]`** —— 文档停留在 RSA-2048 那一代（见 §4.1 的注释原文"150/150/150 for the RSA-2048 one it replaced"），代码已经换成 4096 位。**这个"文档滞后"对我们反而是好消息**：150/150/150 正是国服的切分（§4）。

### 2.5 客户端 URL 重定向在哪？（回答"是不是靠 metadata 连私服"）

**不在 metadata。** `docs/docs/server/client-patching.md` 开头：

> The retail client talks to Nexon. Getting it to talk to loopback instead means editing the installed files, which the server does at startup as a set of hosted services.

而 `README.md:25`：

> It handles the whole setup: downloads the server, installs the .NET 10 SDK and **mitmproxy if they're missing, and trusts the proxy's CA certificate**.

即 **URL 重定向在代理层（mitmproxy）+ 服务端下发的 server_config**，与 metadata 无关。服务端侧把连接组 URL 指向本机：

`Configuration/Config.cs:196-197,235-244`：

```csharp
var apiUrl = GetApiUrl();
var gatewayUrl = GetGatewayUrl();
...
private static string GetApiUrl()     => $"http://{...HostAddress}:{...HostPort}/api/";
private static string GetGatewayUrl() => ...EnableGateway ? $"http://{...HostAddress}:{...GatewayPort}/api/" : "";
```

`Config.cs:201`（region 名与连接组名的耦合，也是"三处必须同名"的来源）：

```csharp
// co_SetupServerData looks the override group up by the region name the client is carrying,
// and ClientRegionLabelPatchService has renamed that region to whatever the label says.
```

---

## 3. 一页结论（先看这个）

1. **改的是"字符串数据"，不是方法体，也不是 header。** 具体是 metadata 文件里**三段定长 ASCII 文本（PEM 公钥）**的字节覆写，长度不变、区段不移动；代码注释自称这三段位于 `fieldAndParameterDefaultValueData`（const 字段默认值区）。**完全没有碰 `Il2CppCodeGenModule` / `codeRegistration` / 方法体** —— 那些本来也不在 metadata 里。
2. **定位方式 = 全文件 AOB 内容扫描 + 唯一匹配要求**，不用固定偏移、不用 hash 表、不读 header、不认 il2cpp 版本。
3. **校验 = fail-safe，不是 verify**：找不到或有歧义就**一个字节都不写**；写前把 `原始/补丁` 两段字节 + offset 存成 sidecar JSON；停机/关开关时**先比对当前字节等于补丁值才回滚**。**没有**全文件 checksum、**没有**写后重读校验。
4. **不依赖标准 header。** 全文 0 次读 `bytes[0..8]`，0 次校验 `0xFAB11BAF`。它对国服 `magic=0x12724394` **完全免疫**。
5. **既不是"连私服"也不是"跳过登录"**：它把客户端**用来 RSA 加密 50001 握手的公钥**换掉，让私服手里的私钥能解开握手。URL 重定向靠 mitmproxy，跳过登录靠服务端开关 `BypassAuthentication`。
6. 具体数字：`[272,272,255]` / `799` / `3` / `150,150,150`（上一代 RSA-2048）/ `+0x49B0`（build 439170 漂移）。

---

## 4. 逐条回答 6 个问题

### 4.1 它改的是 metadata 的什么字段/什么区段？

**改的是 metadata 文件里的三段"定长 ASCII 文本块"的字节内容 —— 字符串数据，不是方法体，不是 header，不是任何表。** 三段的载体，代码注释明确说是 `fieldAndParameterDefaultValueData`：

> `ClientMetadataPatchService.cs:15-18`
> ```
> // The official Nexon gateway RSA-4096 public key, exactly as it is embedded inside the client's global-metadata.dat.
> // The client RSA-encrypts the 50001 gateway handshake with this key, so swapping in the private server's own key is what lets the gateway decode the handshake. Ours has to be 4096-bit as well: the chunks are fixed-size holes in fieldAndParameterDefaultValueData, and a PEM of any other length cannot go into them without shifting the section and every offset past it.
> ```

以及"为什么是三段"：

> `:10-12`
> ```
> // The key is three separate string literals in the metadata rather than one run, and the split lands wherever the build's literal packing put it: 272/272/255 for the RSA-4096 key, and 150/150/150 for the RSA-2048 one it replaced.
> private static readonly int[] ChunkLengths = [272, 272, 255];
> private const int ChunkCount = 3;
> ```

对照你给的假设：

| 你的假设 | 实际 | 依据 |
|---|---|---|
| `stringLiteralData` 全局一块 + `stringLiteralTable` 索引 | **不是这样干的**。它没有读 `stringLiteralTable`，也不改记录里的 length/index；它直接把三段字节**原地等长覆写**。注释说是 `fieldAndParameterDefaultValueData`（const 字段默认值区），同族 `ClientStoreUrlPatchService` 才是走 `stringLiteralTable` 的 | 本文件 0 次 `BitConverter`、0 次读 header；StoreUrl patcher 才有 `BitConverter.ToInt32(bytes, 8..20)` |
| 方法体（method body） | **无关**。metadata 里根本没有函数体；本文件没打开过 `libil2cpp.so` / `GameAssembly.dll` | `GetMetadataPath()` 只返回 metadata 路径 |
| header 的 offset/table | **无关**。本文件从不解析 header | 见 §4.4 |

**旁证（我们自己的取证）**：国服 metadata 里那段 PEM **确实裂成三段、相隔 4.7 MB**（`report\30-网关RSA公钥定位与替换.md` §1：首段 `0x0178CC60`、中段 `0x012D5F88`、末段 `0x0178CBA0`）。`stringLiteralData` 是一个**连续区段**，一个 451 字节的字面量不可能裂成相隔 4.7 MB 的三段；而"三个 `const string` 字段的默认值"天然就是三个不连续的洞。**所以 Shittim 注释里的 `fieldAndParameterDefaultValueData` 与国服实际布局吻合，`stringLiteralData` 的假设不成立。**

### 4.2 它怎么定位目标？

**按内容 AOB 扫描，要求"全文件唯一命中"，否则放弃。** 不用 offset、不用 hash 表、不认版本。

> `:221-246`
> ```csharp
> // Finds the single occurrence of pattern in data. Returns false if absent or ambiguous (found more than once) so the caller can fail safe instead of patching the wrong location.
> private static bool TryLocateUnique(byte[] data, byte[] pattern, out long offset)
> {
>     offset = -1;
>     var span = data.AsSpan();
>     var start = 0;
>     while (start <= data.Length - pattern.Length)
>     {
>         var index = span[start..].IndexOf(pattern);
>         if (index < 0) break;
>         var absolute = start + index;
>         if (offset >= 0) { offset = -1; return false; }   // 第二处命中 ⇒ 视为歧义
>         offset = absolute;
>         start = absolute + 1;
>     }
>     return offset >= 0;
> }
> ```

扫描的 pattern 就是 PEM 的三段 ASCII 字节。调用点在 `PatchMetadata`：

> `:113-136`
> ```csharp
> // Resolve where each key chunk currently lives by scanning for its bytes: a chunk is either still the official key (needs patching) or already ours (patched on an earlier run).
> for (var i = 0; i < ChunkCount; i++)
> {
>     if (TryLocateUnique(fileBytes, officialChunks[i], out var officialOffset)) { offsets[i] = officialOffset; alreadyPatched = false; }
>     else if (TryLocateUnique(fileBytes, targetChunks[i], out var patchedOffset)) { offsets[i] = patchedOffset; }
>     else { /* 警告 + return null，不写盘 */ }
> }
> ```

为什么不用固定偏移，注释给了唯一一个具体数字：

> `:17`
> ```
> // The three byte runs are located by content (an AOB scan) rather than by fixed file offsets: the offsets move every time the client is rebuilt, and build 439170 shifted all three by +0x49B0.
> ```

**注意一个副作用**：它扫描的是"官方 PEM 的三段"或"我们的 PEM 的三段"。第一次打补丁时官方 key 在；打过之后官方 key 不在了，靠"我们的 key"命中来判定 `alreadyPatched`。**如果客户端升级后 key 变了（长度或内容），两个 pattern 都找不到 ⇒ 直接放弃，静默不写**（只留一条 warning）。

### 4.3 它怎么校验补丁成功？

**只有 fail-safe 和可回滚，没有真正的"成功校验"。** 逐项：

| 机制 | 有没有 | 原文 |
|---|---|---|
| 补丁失败即**不写** | ✅ | `:113-135` 任一 chunk 找不到 → `logger.LogWarning(...); return null;`（注释 `:18` `A scan also fails safe: a chunk that cannot be found means no write at all.`） |
| 备份 | ✅ 但是 **sidecar 元数据备份**，不是文件副本 | `:303-306` `GetStatePath` → `$"{path}.shittim_patch.json"`；`:282-296` 记录每段 `Offset` + `Original`(base64) + `Patched`(base64) |
| 回滚 | ✅ | `StopAsync` → `RestoreMetadata()`；`:184-188` **先比对**当前字节 == patched 才回滚，否则 `"Client metadata did not match the active patch state. Leaving it unchanged"` 并放弃 |
| 关开关即还原 | ✅ | `:55-61` `if (!IsEnabled()) { RestoreMetadata(); ... }`，注释说明"关掉开关 = 回到官方客户端，必须把 key 写回去，否则客户端卡 Unpacking" |
| 长度断言 | ✅ | `:207-208` `if (publicKeyBytes.Length != ChunkLengths.Sum()) throw new InvalidOperationException($"The {label} must be {ChunkLengths.Sum()} ASCII bytes after newline normalization, got {publicKeyBytes.Length}");` |
| 写前 chunk 数量/长度断言 | ✅ | `:267-273` `"Invalid metadata patch chunk count"` / `"Invalid metadata patch chunk length"` |
| 读不满报错 | ✅ | `:257-259` `throw new IOException($"Could not read metadata patch chunk at 0x{offsets[i]:X}")` |
| **全文件 checksum / 写后重读校验 / 断言客户端能启动** | ❌ **完全没有** | 全文无 hashing（`using System.Security.Cryptography` 只为 `RSA`），写后不重读、不比对 |
| 幂等 | ✅ | `:138-145` 已打过也重建 sidecar（理由：官方 key 是已知常量，原始字节永远可恢复） |

一句话：**它是"宁可不动，也绝不错写"，而不是"写完证明对了"。** 唯一的验收标准是日志里那行 offset：

> `:155-156`
> ```csharp
> logger.LogInformation("Patched client metadata gateway key at 0x{O0:X}, 0x{O1:X}, 0x{O2:X}: {MetadataPath}", offsets[0], offsets[1], offsets[2], path);
> ```

### 4.4 是否依赖"metadata header 未加密"？——**不依赖。**（关键）

**`ClientMetadataPatchService` 全文 0 次读取 header。** 证据：

- 全文唯一的 `File.ReadAllBytes(path)`（`:111`）之后，直接进 `TryLocateUnique` 全文件扫描，**中间没有一次 `BitConverter.ToInt32(bytes, 0..)`**；
- 全文没有 `0xFAB11BAF` / `sanity` / `version` 字样（grep 计数 0）；
- 没有 `Il2CppGlobalMetadataHeader` 之类结构体定义；
- 唯一与"格式"有关的检查是"这个 chunk 长度必须 799 字节且是 ASCII"，与 header 无关。

**因此它对我们 header 被混淆的国服 3.0.2 完全免疫**：magic 是 `0x12724394`、version 是 `0xEC9E4B18`、`stringLiteralOffset` 越界，这些它一个都不看。

**但是，同族的另外两个 patcher 依赖标准 header**（这是必须区分清楚的边界）：

| Patcher | 读 header 的字节位置 | 国服（header 被混淆）后果 |
|---|---|---|
| `ClientMetadataPatchService` | **无** | ✅ 有效 |
| `ClientStoreUrlPatchService` | `8/12/16/20`（stringLiteral offset/size、stringLiteralData offset/size） | ❌ 读到垃圾 offset → `bytes.AsSpan(data, ...)` 或 `File.Open` 定位异常/越界 → 被 `StartAsync` 的 `catch (Exception ex) { logger.LogError(...) }` 吞掉，**不写盘，静默无效** |
| `ClientRegionLabelPatchService` | 另有 `24/28`（名字表）、`96/100`（fieldDefinitions），并用 `8..8+31*8` 扫 31 个 (offset,size) 对求文件尾 | ❌ 同上（垃圾值 → 大概率 `ArgumentOutOfRangeException`，被 catch） |

国服 header 的实测事实（本工程既有取证，供对照）：

- `report\24-state接口schema反推.md:29`：`magic(LE) = 0x12724394   ← 不是标准 il2cpp magic 0xFAB11BAF`
- `report\DEADENDS.md:291`（D-34）：`magic 0x12724394（非 0xFAB11BAF）、version 0xEC9E4B18（无意义）、stringLiteralOffset 越界、全文件 0 处标准 sanity`
- `report\01-现状与已试方向.md:224`：`magic=0x12724394、version=0xEC9E4B18、第 3 个 u32 越界、标准 sanity 全文件 0 命中`

⇒ **"Shittim 的做法依赖标准 header" 这个前提是错的**（至少对 `ClientMetadataPatchService` 不成立）。它只依赖"那段 PEM 文本还在文件里、还是那三段、还是那些长度"。

### 4.5 改完是"让客户端连私服"还是"跳过登录判断"？

**都不是。它改的是"客户端用来加密握手的那把公钥"。**

目的（`:14-15` 原文）：

> ```
> // The client RSA-encrypts the 50001 gateway handshake with this key, so swapping in the private server's own key is what lets the gateway decode the handshake.
> ```

具体机制：客户端把 `Queuing_GetCryptoKeys`(50001) 的会话 key/IV 用**编译进 metadata 的 RSA 公钥**加密；服务端必须持有配对私钥才能解。所以：

- **不是替换 API URL 字符串**（URL 重定向由 mitmproxy + server_config 的 connection group 完成，见 §2.5）；
- **不是 disable 某个校验**（没有改任何 `if`、没有改 `ValidateCertificate`、没有改登录分支）；
- **不跳过登录**（`BypassAuthentication` 是服务端 `ServerConfig.cs:42` 的开关，与 metadata 无关）；
- 它做的是**密钥替换（key substitution）**，让加密通道的两端对上。

顺带说明"为什么不是改 URL"：客户端把网关 URL 从服务端下发的 `server_config` JSON 里读（`connection group`），metadata 里根本没有私服地址可改 —— `report\01-现状与已试方向.md:200` 也实测过"网关域名编译进 APK 静态产物：全量扫描 0 命中"。

### 4.6 代码里所有具体的 offset / magic / 字符串 / 断言（原样）

**offset 数字**

| 值 | 位置 | 含义 |
|---|---|---|
| `+0x49B0` | `:17` 注释 | build 439170 让三段整体漂移了这个量 |
| `0x{O0:X}, 0x{O1:X}, 0x{O2:X}` | `:155` | 运行时打印的三个 chunk 偏移（不是常量） |
| `0x{offsets[i]:X}` | `:259` | 读失败时的诊断串 |

> 注意：**没有任何硬编码的文件偏移**，也没有 magic 常量。`0xFAB11BAF` 全文不存在。

**长度/计数常量**

```csharp
private static readonly int[] ChunkLengths = [272, 272, 255];   // 和 = 799
private const int ChunkCount = 3;
```

（注释里另一组：`150/150/150 for the RSA-2048 one it replaced`。）

**官方公钥常量（4096 位，Nexon 网关公钥，`:19-33` 原样）**

```
-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAz1oODtVINPQsTIbFDiL2
IIj3YqDGxZ1WqJWfJrpo7ZqdnSIMXaVqVyM07Zguc9wczPrluDNowheP8NXe8uTR
prO7jpF9bOcrrit9Xyxf57NA5rIMqOj6/XgWzzptvvt3oUrOQJRTvEjusQCX79Ds
fhhbPRfdPzZUOPYa49MM385Z05ndNiTB9/yhxP5+5zm7TS3f6/o1Ntw9yXoRYmgR
8+JYGL6TpqtZHkqPTp6kIJrnsLyT1wRteh3oQKJaze0CM0DUUzFiqieRE8c8JAoV
jk/yRQUqVMoKbdpINYlWhF+GFE/ccSpqQymepHxfR0alspynqJwJgODCeHtwuno5
HEOwdbA8NanLVnE9qlvdeNkbODdt/XTHKOaXx+SUMHezUY0rEXp8WMim0i9IQTGa
YWeW25RjXIZswKdg0gLRJXYZXUgF3nVcqr0hi4kv1pgrFPsjI7yIThxLY0UfomkR
oe6sSBBtQUDI85s+1pZRcl8xygxOxMfFSk5RB3EntFmcf/AKaLYQbXN9RxgrvqRS
9koBBEnnrIN0zXDBioZUDOWVBeBZwAydpPGKu2mkqu3BI/Al92noEHc6fmkG5+Qm
b237xSh1DFbbQO6lxg4ABdsqgvZskYS+7BcQPjs1z2zftrnesFkqD7BhbqXUBuDY
D80B8Be5I483qSSy8DsW458CAwEAAQ==
-----END PUBLIC KEY-----
```

（代码里以 `"-----BEGIN PUBLIC KEY-----\n" + ... + "-----END PUBLIC KEY-----"` 拼接；`BuildKeyChunks` 会 `Replace("\r\n","\n").Replace("\r","\n").TrimEnd('\n')` 后要求恰好 799 字节。）

**路径 / 文件名 / 环境变量 / 配置键**

```csharp
// 默认路径（Steam 库定位）
Path.Combine("BlueArchive_Data", "il2cpp_data", "Metadata", "global-metadata.dat")   // :342
// sidecar
$"{path}.shittim_patch.json"                                                          // :305

// 环境变量
SHITTIM_AUTO_PATCH_METADATA            // bool，覆盖 IsEnabled
SHITTIM_CLIENT_METADATA_PATH           // 覆盖 ClientMetadataPath
SHITTIM_GATEWAY_RSA_PUBLIC_KEY         // 直接给 PEM 文本
SHITTIM_GATEWAY_RSA_PUBLIC_KEY_PATH
SHITTIM_GATEWAY_RSA_PRIVATE_KEY
SHITTIM_GATEWAY_RSA_PRIVATE_KEY_PATH

// 配置键（appsettings / ServerConfig）
ServerConfiguration.EnableGateway
ServerConfiguration.AutoPatchClientMetadata
ServerConfiguration.ClientMetadataPath
ServerConfiguration.GatewayRsaPublicKeyPem / Path
ServerConfiguration.GatewayRsaPrivateKeyPem / Path
// 默认 key 文件
Path.Combine(Config.ConfigDirectory, "GatewayPublicKey.pem")
Path.Combine(Config.ConfigDirectory, "GatewayPrivateKey.pem")
// 私钥同目录下的公钥
Path.Combine(privateKeyDirectory, "GatewayPublicKey.pem")
```

**全部断言 / 异常 / 日志串（原样）**

```csharp
$"The {label} must be {ChunkLengths.Sum()} ASCII bytes after newline normalization, got {publicKeyBytes.Length}"
"Invalid metadata patch chunk count"
"Invalid metadata patch chunk length"
$"Could not read metadata patch chunk at 0x{offsets[i]:X}"

"Client metadata auto-patch disabled"
"Client metadata auto-patch is enabled, but no metadata path was configured"
"Client metadata file not found: {MetadataPath}"
"Client metadata auto-patch is enabled, but no gateway public key was found"
"Gateway public key chunk {Index} was not found in client metadata. The client build may have changed how the key is stored; leaving {MetadataPath} unchanged to avoid corrupting it."
"Client metadata already patched: {MetadataPath}"
"Patched client metadata gateway key at 0x{O0:X}, 0x{O1:X}, 0x{O2:X}: {MetadataPath}"
"Client metadata did not match the active patch state. Leaving it unchanged: {MetadataPath}"
"Client metadata file disappeared before restore: {MetadataPath}"
"Restored client metadata: {MetadataPath}"
"Failed to patch client metadata"
"Failed to restore client metadata"
```

**注释里的关键英文字符串**

- `"Unpacking game resources"`（`:57`，写错 offset 的症状；`:18` 也提到）
- `fieldAndParameterDefaultValueData`（`:15`）
- `the chunk is three separate string literals`（`:10`）

---

## 5. 对我们（国服 3.0.2，header 被混淆）是否适用？——明确判断

### 5.1 结论

> **A. 方法论：完全适用。** "在 metadata 里 AOB 找 PEM 文本 → 三段定长原地覆写 → sidecar 记录原始字节以便回滚"这套做法**不碰 header**，国服 `magic=0x12724394` 对它没有影响。
>
> **B. 代码：不能直接照抄，要改 2 个常量。** 它把"官方 key 长度"硬编码成 `[272,272,255]`（799 B，RSA-4096），而国服是 `[150,150,151]`（451 B，RSA-2048）。两边错配时它会在第一个断言就抛出 `InvalidOperationException`（`must be <sum> ASCII bytes ... got <len>`）：拿 4096 位 PEM 配 CN 的 `[150,150,150]` → `800 != 450`；拿 CN 的 2048 位 PEM 配代码里的 `[272,272,255]` → `450 != 799`。
>
> **C. 我们其实已经有更好的实现。** `bapatch/patch_metadata_key.py` 做的事情与它同源，但多了 DER 结构验证 + 8 条硬断言（`report\30` §5.2-5.3）。**这条上游情报的价值在"确认思路"，不在"移植代码"。**

### 5.2 为什么"同构"——三段模型的直接对照

| 项 | Shittim（Steam 国际服，4096 位） | 国服 3.0.2（实测，`report\30`） |
|---|---|---|
| 段数 | 3 | **3** |
| 切分 | `272 / 272 / 255`（和 799） | **`150 / 150 / 151`（和 451）** |
| 段 A | AOB 扫出（build 439170 漂移后） | `0x0178CC60` |
| 段 M | AOB 扫出 | `0x012D5F88`（相距 4.7 MB） |
| 段 C | AOB 扫出（在 A 之前） | `0x0178CBA0`（**在 A 之前**，与 Shittim 描述一致） |
| 密钥位数 | RSA-4096 | **RSA-2048**（`e=65537`，SPKI DER 294 B，base64 392 字符） |
| PEM 规范化长度 | 799（去尾换行） | **451**（含尾换行）/ 450（去尾换行） |
| 载体 | `fieldAndParameterDefaultValueData` | 同样表现为 3 个不连续的定长洞（与 `stringLiteralData` 单连续区段矛盾） |

**关键的"同源"证据**：Shittim 注释自己说上一代是 `150/150/150`（和 450）= 国服的 `451 - 1`（去掉尾换行）。**这说明 Shittim 这套代码最初就是对着"RSA-2048、三段 150 字节"的客户端写的，而国服正好就是那个形态。** 换 4096 位是后来 Steam 版客户端升级导致的。

### 5.3 要改的具体参数（如果真要复用这份 C#）

```csharp
// 1) 切分：国服 451 B，BuildKeyChunks 会 TrimEnd('\n') ⇒ 450 = 150+150+150
private static readonly int[] ChunkLengths = [150, 150, 150];

// 2) 官方 key 常量：换成国服那把 2048 位 PEM（report\30 §2 已抽出，451 B，
//    sha256 cf0297159db93aca7edbc1feaaff0ee71e2bc93b86abd7d2e97b5c0f10d268ea）
private const string OfficialGatewayPublicKeyPem = "<国服 2048 位 PEM，LF 折行 64 列>";
```

约束（少一条就写坏）：

- 替换用的 PEM **必须 RSA-2048**（4096 的 PEM 规范化后 800 B，比洞大 349 B，`BuildKeyChunks` 直接抛异常）；
- **必须 ASCII**（中文注释/CRLF 都会改长度），`Encoding.ASCII.GetBytes` 会把非 ASCII 变 `?`；
- **必须 64 列折行 + LF**（行宽不同 → 切点落点不同 → 即使总长对也会把 base64 打断成非法）；
- 写 450 字节、**留下文件里第 451 字节（尾 `\n`）不动** —— 因为 `TrimEnd('\n')` 已经把它去掉了，写回时恰好保持布局。

### 5.4 会失效的部分（必须知道的边界）

| 项 | 在国服上的状态 |
|---|---|
| `ClientMetadataPatchService`（换 RSA 公钥） | ✅ 机制可用（改常量后） |
| `ClientStoreUrlPatchService`（改 `stringLiteral` 记录） | ❌ 依赖 header `8/12/16/20`，国服读到垃圾 → 异常被吞，静默无效 |
| `ClientRegionLabelPatchService`（改 `ServerRegion` 枚举名） | ❌ 依赖 header `8..28/96/100`，同上 |
| `ClientInfaceConfigPatchService` | ⚠️ 与 metadata 无关（改 `nxinface.enconfig.json` + `Plugins/x86_64`），是 **PC 专属**，Android 无对应物 |
| `ClientSteamOfflinePatchService` / `Grap64` / `Banners` | ⚠️ PC 专属（`GameAssembly.dll` / 插件目录 / `ExcelDB.db`） |

### 5.5 还不能宣称的部分（诚实边界）

1. **"改了公钥就能连"没被证明。** Shittim 是 PC/Steam 版，登录走 50001 RSA 网关握手；国服 Android 走的是 **AiriSDK 明文 HTTPS + 自有信封混淆**（`report\03-上游情报.md:152`、`report\32`、`report\37`）。**国服是否真的用这把 PEM 做 50001 握手，仍需实测**（`report\27` / `report\28` 认为走，但那是源码/字符串推断）。
2. **ACE 是否校验 `global-metadata.dat`：未知。** 已知 `libunity.so` 被磁盘哈希钉死（改 4 字节即 SIGBUS），metadata 是否同类**未测**（`report\30` §6.2、`report\38:301`）。
3. **APK 重打包问题独立存在**：metadata 在 `assets/bin/Data/Managed/Metadata/` 里是 zip 条目，`extractNativeLibs=true` 但 `assets/` 仍是压缩条目，必须保持 STORED/DEFLATED 方式一致（`report\30` §7）。
4. Shittim 的 patcher 是**服务端进程直接改磁盘文件**；我们的场景是改 APK 内条目/推送到设备，**交付形态不同**，这块它没有可借鉴的。

### 5.6 一句话给决策

> **它证明了一件事：换 metadata 里的网关 RSA 公钥这条路上，"不需要解密 header"是成立的。** 国服 header 混淆只挡 `ClientStoreUrlPatchService` / `ClientRegionLabelPatchService` 那两条支线，挡不住换 key。我们 `bapatch/patch_metadata_key.py` 已经是同一思路的超集实现，**不需要移植这份 C#**；需要的是把 `[150,150,150]` 这个"上游确认过的切分"当作对 `report\30` 结论的独立交叉验证。

---

## 6. 引用 URL（全部）

**上游源码（一手）**

1. 仓库主页：https://github.com/Neoexm/Shittim-Server
2. 仓库元信息 API（`default_branch: main`）：https://api.github.com/repos/Neoexm/Shittim-Server
3. 目标文件 HTML：https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/Services/ClientMetadataPatchService.cs
4. 目标文件 contents API（`sha=10bfa36…`, `size=18931`）：https://api.github.com/repos/Neoexm/Shittim-Server/contents/Shittim-Server/Services/ClientMetadataPatchService.cs?ref=main
5. 目标文件 blob API：https://api.github.com/repos/Neoexm/Shittim-Server/git/blobs/10bfa36a88dd4ad2ae62281b626ca169ea847e70
6. `Services/` 目录清单：https://api.github.com/repos/Neoexm/Shittim-Server/contents/Shittim-Server/Services?ref=main
7. `ClientStoreUrlPatchService.cs`：https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/Services/ClientStoreUrlPatchService.cs
8. `ClientRegionLabelPatchService.cs`：https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/Services/ClientRegionLabelPatchService.cs
9. `ClientInfaceConfigPatchService.cs`：https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/Services/ClientInfaceConfigPatchService.cs
10. `CLI/GameServer.cs`（DI 注册）：https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/CLI/GameServer.cs
11. `Configuration/ConfigType/ServerConfig.cs`：https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/Configuration/ConfigType/ServerConfig.cs
12. `Configuration/Config.cs`（connection group / ApiUrl）：https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/Configuration/Config.cs
13. 官方文档 `docs/docs/server/client-patching.md`：https://github.com/Neoexm/Shittim-Server/blob/main/docs/docs/server/client-patching.md
14. `README.md`（mitmproxy 说明）：https://github.com/Neoexm/Shittim-Server/blob/main/README.md

**失败/不可用（记录在案）**

15. `https://api.github.com/repos/Neoexm/Shittim-Server/git/trees/master?recursive=1` → **HTTP 404**（分支是 `main`）
16. `https://raw.githubusercontent.com/Neoexm/Shittim-Server/master/Services/ClientMetadataPatchService.cs` → 路径/分支都不对（根目录没有 `Services/`）
17. `https://raw.githubusercontent.com/Neoexm/Shittim-Server/main/Shittim-Server/Services/ClientMetadataPatchService.cs` → **fetch failed**（本机网络，非 404）

**本工程内部引用**

18. `report\30-网关RSA公钥定位与替换.md`（国服 PEM 三段布局、451 B、sha256、AOB+DRE 断言）
19. `report\28-Shittim网关协议源码核对.md`（`global-metadata.dat` 里 PEM = 50001 握手公钥的定论）
20. `report\24-state接口schema反推.md:29`（magic `0x12724394` 实测）
21. `report\DEADENDS.md:288-291`（D-34：标准 Il2CppDumper 解析失败的四条硬证据）
22. `report\01-现状与已试方向.md:224`（header 混淆复现）
23. `report\03-上游情报.md:152`（手机版不改 metadata 的原因：AiriSDK 明文 HTTPS）
24. `report\_tmp\shittim\src\`（本地源码副本，本次已与上游 blob sha 核对一致）
