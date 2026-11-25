# 封禁弹窗打通 —— 现象 / 根因 / 修法 / 回滚

> 状态：**已打通（真机验证 2026-11-18 21:29）**
> 文档分工：本文是"怎么修、怎么回滚"的作战记录；技术订正细节见
> `work\ba\noroot\SYNC_RESOURCE_ERROR_20261118.md`（已同步订正）。
> 本文件只读记录，不含可执行改动。

---

## 1. 现象

**一句话：`Account_Auth` 返回 `Protocol:-1` + `ErrorCode:1025` 时，客户端不弹官方封禁窗，只弹通用失败提示。**

| 项 | 值 |
|---|---|
| 请求 | `Account_Auth` |
| 响应 | 364 字节，`outer{protocol:"Error", packet, requestid}` + `inner{Protocol:-1, ServerTimeTicks, RequestId, ErrorCode:1025, AccountBanErrorPacket{BanReason:"永久"}}` |
| 客户端表现 | 弹 **「同步资源信息时发生错误」+「将返回标题画面」** 的通用兜底（表内原文：`rowid=293 / Key=3944054940`；用户口语转述为"时失败"），**不弹**官方封禁窗 |
| 抓包/日志 | 确认 364 字节**完整、正确**地送达客户端 |

---

## 2. 根因

**一句话：根因是 `ErrorCode` 填错了 —— 1025 是 `AccountLoginError`，不是封禁码；本地化表里没有 1025 这一行，于是走兜底文案。**

### 2.1 错误码对照（真机实测，全表）

| `ErrorCode` | 枚举名 / 出处 | 客户端表现 | 判定 |
|---|---|---|---|
| **1025** | `AccountLoginError`（`ProtocolData.cs:720`） | 表里**没有这一行** ⇒ 兜底「同步资源信息时发生错误」+「将返回标题画面」 | ❌ **证伪**：不是封禁码 |
| **3** | `InvalidSession`（`:654`） | 弹 **「无效的会话。」** | ✅ **验证通道**：证明 `ErrorCode → LocalizeErrorDBSchema` 通路是通的 |
| **27000** | **`AccountBanned`**（**:979**） | 弹 **官方封禁窗「账号已被禁止使用，/ 如有任何问题请咨询客服！/ 封禁周期至：」** | ✅ **成功** |

### 2.2 数据库侧交叉验证

`work\ba\data\ExcelDB.db` → **`LocalizeErrorDBSchema`（429 行，`Key` / `Bytes`）**，
**按枚举顺序存放**，与 `ProtocolData.cs` 逐行对齐（编号口径 = **rowid**）：

```
rowid=167  Key=2211462200  「无法找到保存信息」                      ↔ ContentSaveDBNotFound = 26000（:977）
rowid=168  Key=1749817446  「账号已被禁止使用\n如有任何问题请咨询客服\n封禁周期至」 ↔ ★ AccountBanned = 27000（:979）
rowid=169 起                正好对上 28000 ServerNowLoadingProhibitedWord 起的 6 个成员
```

**⇒ 26000/27000 与表行严格对齐，说明"枚举顺序 = 表行顺序"这个对齐方法是可靠的。**

### 2.3 被否证的三个假设（写下来防止回流）

1. ❌ **"包形状不对 / 回错了接口"** —— 包形状从头到尾没变过，协议名 `Error`/值 `-1` 本来就是对的。
2. ❌ **"`Protocol:-1` 解不出类型"** —— 真机证明能正常解析（此前静态推断错误，已在订正文档中作废）。
3. ❌ **"`LocalizeErrorDBSchema.Key` 是文案/枚举名的 hash"** ——
   `crc32 / adler32 / fnv1a / fnv1 / fnv1a64 / djb2 / sdbm / java / murmur3 / md5 / sha1` **全试过，0 命中**。
   **`Key` 就是个不透明整数，不要试图反推。**

---

## 3. 修法

**一句话：把 `ErrorCode` 改成 `27000`，日期串**只挂 `BanReason`** —— 不要挂 `Reason`。**

### 3.1 客户端弹窗链路（真机验证）

```
桥 → outer{ "protocol":"Error", "packet":<inner>, "requestid":<echo> }
      inner{ "Protocol": -1, "ServerTimeTicks": ..., "RequestId": ..., "ErrorCode": <N>, ... }
                                  ↓
              客户端按 inner.Protocol(-1) 选错误 DTO（可正常解析）
                                  ↓
              按 inner.ErrorCode = N 查 LocalizeErrorDBSchema
                                  ↓
      ┌ 命中 → 弹该行文案
      └ 未命中（如 1025）→ 弹「<当前阶段>时发生错误。将返回标题画面。」
```

> 核实备注：表里与"同步资源"对应的那行原文是 `rowid=293 / Key=3944054940` =
> 「同步资源信息时发生错误」+「\n将返回标题画面」。渲染文案以该行为准，链路口径不变。

### 3.2 字段：**只挂 `BanReason`**，不要挂 `Reason`

**一句话：`ErrorCode=27000` 时客户端仍然会读 `BanReason` 并拼在「封禁周期至：」后面（真机 21:29 验证），所以不需要 `Reason`。**

| 类型 | 字段 | 依据 |
|---|---|---|
| `ErrorPacket`（type[10777]） | `<Reason>` / `<ErrorCode>` | metadata 字段表 |
| `AccountBanErrorPacket`（type[10780]） | **`<BanReason>` ← 客户端实际读的就是这个** | metadata 字段表；**有 `get_ErrorCode` ⇒ 继承 `ErrorPacket`** |

**⇒ 终版只下发 `BanReason`。**
早前那版曾把同值日期串**同时**挂到 `BanReason` 与 `Reason`，实测后**撤掉** ——
多挂一个同值 `Reason` 有被客户端**拼接两遍**的风险，而 `BanReason` 单挂已能让日期正常显示。

### 3.3 桥侧改动清单

| # | 改动 | 说明 |
|---|---|---|
| 1 | **`CN_BANREPLY_CODE = 1025` → `27000`** | **唯一的实质差异**：把 `AccountLoginError` 换成 `AccountBanned` |
| 2 | 附带的注释 + 留档常量 `CN_BANREPLY_CODE_LEGACY = 1025` | 非功能性，仅留档 |
| 3 | 目标文件 | `account_auth_probe.py`（部署路径 `/www/wwwroot/bapatch/tools/account_auth_probe.py`） |
| 4 | **终版 md5 / 大小** | **`af1bc9a5517a6150546abf0b4a0ce57f`** / **222,486 B**（落盘前请 `md5sum` 复核） |

> **相对线上基线 `fa0d95b0`，终版差异只有一处**：`CN_BANREPLY_CODE` 的取值（外加注释与留档常量）。
> **不新增 `Reason` 字段**；`BanReason` 沿用原有下发方式。
> 其余部分**不动**：`outer.protocol` 保持 `"Error"`，`inner.Protocol` 保持 `-1`，`requestid` 保持回显。

---

## 4. 验证

**一句话：看 `ErrorCode` 与屏幕文案是否一对一对上。**

| 步骤 | 期望 |
|---|---|
| 1 | 用 `ErrorCode=3` 打一发 → 应弹「无效的会话。」（证明通路通） |
| 2 | 用 `ErrorCode=27000` + **只带 `BanReason`** 的包打一发 → 应弹官方封禁窗，且「封禁周期至：」后面**有日期** |
| 3 | 再打一发 `ErrorCode=1025` → 应回到通用兜底（对照组，说明 1025 确实不是封禁码） |

---

## 5. 回滚

**整文件回滚（推荐，一次到位）：**

```bash
cp -a /root/BANFINAL_*/account_auth_probe.py /www/wwwroot/bapatch/tools/account_auth_probe.py
# 然后重启桥/服务进程
```

**开关级回滚（不换文件，只关掉封禁应答分支）：**

```bash
rm /www/wwwroot/bapatch/cn_banreply.txt
# 然后重启桥/服务进程
```

> 两者都做也没关系；开关级回滚更快，整文件回滚更彻底。回滚后预期恢复"1025 → 通用兜底"的旧行为。

---

## 6. 以后不要再踩（清单）

1. **别再假设 `1025 = AccountLoginError` 能当封禁码用** —— 它是登录错误，本地化表里没有对应行，只会落到兜底文案。
   **封禁码是 `27000 = AccountBanned`。**
2. **别再假设 `Protocol:-1` 解不出类型** —— 已被真机否证。错误信息的 DTO 选型不受 `-1` 影响，
   真正决定弹窗的是 `ErrorCode`。
3. **别再假设 `LocalizeErrorDBSchema.Key` 是文案的 hash** —— 11 种哈希全试过 0 命中，它就是整数。
   要定位"哪个码配哪句话"，用**枚举顺序 ↔ 表行顺序**对齐，并用 `ProtocolData.cs` 的行号交叉验证。
4. **找 UI 文案先查 `work\ba\data\ExcelDB.db` 的 `Localize*` 表**，不要只扫 APK/metadata/so
   —— 文案是运行时数据表，不在包里（这条是上一轮 0 命中的真正原因）。
5. **涉及"会不会走某分支"的结论必须真机验证**，不能只靠 ARM 指令语义推演
   （`TypeConversion` 那次就是这么错的）。
