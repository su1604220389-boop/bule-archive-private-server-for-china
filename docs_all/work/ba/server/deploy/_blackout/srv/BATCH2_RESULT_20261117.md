# BATCH 2 执行记录（追加到 BATCH_DEPLOY_20261117.md 的批次 2 节）

执行者：srv-ops
时间：2026-11-17 20:29–20:36

---

## 结果一行

**批次 2 已部署：`Shittim-Server.dll` sha256 `59cf008196f19aadca7bd1502c113b3e53e88e3fd21b6201517f62efcc35dc06`、`Schale.dll` `c20095f50e06068a544611ee068bf2fdbdc7f60dd09c81c7ca9da97498a7ddf7`；1017 自测 200、`relay2_err=''`；字段名验证 **对**（`BillingPurchaseListByYostarResponse` / `MomoTalkOutLineResponse` / 无 `StaticOpenConditions`）；`MemoryLobbyDBs.AccountServerId` **本次未能验证（测试账号无记忆大厅行，列表为空）**。**

---

## 1. 源码改动（本地 `work\ba\srv_src`）

| # | 文件 | 改动 |
|---|---|---|
| 1 | `Schale\MX\GameLogic\DBModel\DBModel.cs` | `MemoryLobbyDB` 增 `public long AccountServerId { get; set; }` |
| 1 | `Schale\MappingProfiles\Mapping.cs` | `CreateMap<MemoryLobbyDBServer, MemoryLobbyDB>()` 增 `.ForMember(dest => dest.AccountServerId, src => src.AccountServerId)` |
| 2 | `Schale\MX\NetworkProtocol\NetworkProtocol.cs` | `AccountLoginSyncResponse.BillingPurchaseListByNexonResponse` → `BillingPurchaseListByYostarResponse` |
| 2 | `AccountHandler.cs` | `new BillingPurchaseListByNexonResponse` → `ByYostarResponse`；赋值行同步改名；**并删掉 ByYostar 上不存在的 4 个 Nexon-only 字段**（`GachaTicketItemIdList` / `ProductMonthlyIdInMailList` / `BattlePassIdInMailList` / `DailyRecordIdInMailList`），补 `PendingProductShopCashIds = []` |
| 3 | 同上两文件 + `Commands\AccountDataCommand.cs` | `MomotalkOutlineResponse` → `MomoTalkOutLineResponse` |
| 4 | `AccountHandler.cs` | 两处 `response.StaticOpenConditions = BuildOfficialStaticOpenConditions();` 删除（改为注释） |
| 5-M1 | `Services\ExcelTableService.cs` | 新增 `incomplete` 字典 + `catch (Exception ex) { incomplete[type]=0; }` + `public bool IsTableComplete<T>()` |
| 5-M2 | `AccountHandler.cs` | 幽灵角色清理整段包进 `if (_excelService.IsTableComplete<CharacterExcelT>()) { ... }` |

**编译期发现的事实（值得记）**：`BillingPurchaseListByYostarResponse` 与 `…ByNexonResponse` **字段集不同**（前者无 4 个 mail/ticket 列表、多 `PendingProductShopCashIds`），官方 HAR 里该子响应也只带 `CountList/OrderList/MonthlyProductList`。所以"改名"不能只改类型名，**必须同时裁字段**，否则 `CS0117`。

## 2. 构建产物

```
dotnet publish -c Release -o _build_batch2   （dotnet 10.0.301，多处 NU1903/AutoMapper 警告，无 error）
Schale.dll          5,392,896 B   c20095f50e06068a544611ee068bf2fdbdc7f60dd09c81c7ca9da97498a7ddf7
Shittim-Server.dll  2,670,080 B   59cf008196f19aadca7bd1502c113b3e53e88e3fd21b6201517f62efcc35dc06
```

## 3. 部署与备份

```
备份：/www/wwwroot/ba_srv/Shittim-Server.dll.pre-batch2.20261117_203256  (db465934…)
      /www/wwwroot/ba_srv/Schale.dll.pre-batch2.20261117_203256          (6745ee5f…)
部署后：Shittim-Server.dll 59cf0081…  /  Schale.dll c20095f5…
运行：tmux `shittim` → dotnet pid 2635890，5000/5100/6667 LISTEN
```
**一行回滚**
```bash
cp -a /www/wwwroot/ba_srv/Shittim-Server.dll.pre-batch2.20261117_203256 /www/wwwroot/ba_srv/Shittim-Server.dll
cp -a /www/wwwroot/ba_srv/Schale.dll.pre-batch2.20261117_203256          /www/wwwroot/ba_srv/Schale.dll
tmux kill-session -t shittim; tmux new-session -d -s shittim -x 220 -y 50 '/root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2'
```

## 4. 自测结果（20:34:53 / 20:35:19）

```
/api/account/loginsync → 200 / 13,912 B；relay2_used=True relay2_protocol=1019 gateway=Account_LoginSync
relay2_err=''  relay2_fallthrough=''  relay2_resp_len=10,284
inner keys = 32
  BillingPurchaseListByYostarResponse      ✅ 存在
  BillingPurchaseListByNexonResponse       ✅ 已消失
  MomoTalkOutLineResponse                  ✅ 存在
  MomotalkOutlineResponse                  ✅ 已消失
  StaticOpenConditions                     ✅ 已消失
  MemoryLobbyDBs count = **0**             ⚠️ 无法据此判断 AccountServerId
```

**`MemoryLobbyDBs` 为空的解释（不是代码错的证据）**：`MemoryLobbies` 表里只有 `(ServerId=1, AccountServerId=2, MemoryLobbyUniqueId=13010)` 一行，属于 **Shittim 账号 2**；而本轮合成请求命中的不是账号 2（`acct_server_id=10000000000`）。**要验证 `AccountServerId`，必须用账号 2 的真实会话跑一次 1017。** 该项标记为 **未验证**。

## 5. 部署过程事故（如实记录）

1. **`pkill -f 'dotnet .*Shittim-Server.dll'` 误杀 tmux**：tmux 命令行里也含该字符串 → tmux server 与子进程一起被杀，**服务中断约 40 秒**（20:32:5x–20:33:5x）。后续改用 `tmux kill-session -t shittim` + 精确 pid kill。
2. **重启后启动失败：`VersionLookupException: Failed to fetch version from PureAPK`**（`SslStream` 收到 EOF）。实测：从服务器 `https://www.pureapk.com/` = `000`（不可达），而 `api.github.com` / `baidu.com` 均 200 ⇒ **不是我们的配置问题，是外网可达性变化**。
   **处置**：把 `config/ba_version_cache.json` 里的值写进 `Config.json`：
   ```
   OverrideVersionId   = 53c8e5c4ff484d23
   OverrideCdnBaseUrl  = https://ba.dn.nexoncdn.co.kr/com.nexon.bluearchive/53c8e5c4ff484d23
   ```
   备份：`/root/ba_db_backup/Config.json.pre-override.20261117_203413`（sha256 `d747d2ec15ca93062e1683cf81668a86aec361e5718d47baa295d5c5d23e8c04`）
   回滚：`cp -a /root/ba_db_backup/Config.json.pre-override.20261117_203413 /www/wwwroot/ba_srv/Config/Config.json`
   **⇒ 这条配置改动是本轮唯一的"配置类"改动，且它是为了让服务能在 PureAPK 不可达时启动，不是功能改动。**
3. 期间还出现过一次 `System.UnauthorizedAccessException: User not found`（重启后旧会话失效），重新走一次 `Account_Auth` 后恢复，**不是批次 2 引入的**。

## 6. 数据完好性核对（部署后）

```
Characters 14 | CampaignStageHistories 416 | Items 2 | Currencies 2 | Echelons 5 | MemoryLobbies 1 | Mails 3
campaign rows acct2 = 416
日志无 "Removing N character rows" 记录
```
**⇒ M2 守卫上线后没有触发任何删除，账号 2 的 416 条通关记录与 4 个角色都在。**
