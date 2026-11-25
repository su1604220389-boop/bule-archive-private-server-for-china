# BAPATCH-ENVELOPE1 部署与自检（响应壳对齐官方）

- 时间：2026-11-19 01:53–01:54（Asia/Shanghai）｜ 执行：srv-ops
- 产物：`work\ba\srv_src\_build_envelope1\Shittim-Server.dll`
- 内容：① 每条响应回显 `SessionKey`；② `ServerNotification` 的"未读邮件"标记只盖在邮件类协议（7000–7004），不再每条都盖 8
- **最终判定：部署成功 · 自检全过 · KEEP（保留新版本）**

## 1. 路径确认（非猜测）

```
systemctl cat ba-shittim →
  WorkingDirectory=/www/wwwroot/ba_srv
  ExecStart=/usr/bin/tmux new-session -d -s shittim … "/root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2"
⇒ 线上加载路径 = /www/wwwroot/ba_srv/Shittim-Server.dll
```

## 2. 新旧 sha256 / 大小

| | sha256 | 字节 | 时间 |
|---|---|---|---|
| 改前 | `63ca8f34694f65420c5dff4ec0822192386407162c9ca38d2b326c65d434789f` | 2,687,488 | 11-19 00:48 |
| **改后** | **`160c3e159956ee8300b57a90af70bc8813cb03ce5aef48d3c36615631cf4bd16`** | **2,688,000** | 11-19 01:53 |

- 本地构建件核对：2,688,000 B / `160c3e15…` ✅（与要求一致）
- 部署方式：上传 `/tmp/Shittim-Server.dll.new` → 校验 sha256 + 字节数 + 线上基线 → `mv -f`
- `Schale.dll` 未替换：线上仍 `b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858` ✅

## 3. 备份与回滚

```
备份目录：/root/ENVELOPE1_20261119_015359/
   Shittim-Server.dll    ← 改前版本（63ca8f34… / 2,687,488 B）
   BEFORE.sha256
   ROLLBACK.sh           ← mv 备份回原位 → systemctl restart ba-shittim → 轮询 5000/5100 → 打印恢复后 sha256
```

**ROLLBACK.sh 完整路径：**
```
/root/ENVELOPE1_20261119_015359/ROLLBACK.sh
```

## 4. 重启

```
systemctl restart ba-shittim
轮询（5000 与 5100 同时就绪）→ **5000/5100_UP 耗时 7,151 ms**
新 pid = 2797354 ｜ systemctl is-active → active
```

## 5. 自检（部署后立即，脚本 `/tmp/972_envelope1_selfcheck.py`）

| 检查项 | 实测 | 判定 |
|---|---|---|
| ① `Account_Auth`(1002) | HTTP **200** ｜ **3,208 B** ｜ outer=`Account_Auth` ｜ `inner.Protocol=1002` ｜ 无 `ErrorCode` ｜ **含 `SessionKey` = True** | ✅ |
| ② `LoginSync`(1019) | HTTP **200** ｜ **587,036 B**（≥500 KB）｜ outer=`Account_LoginSync` ｜ `inner.Protocol=1019` ｜ inner 键数 33 | ✅ |
| ②-a `ShopRecruits` | **529 条** | ✅ |
| ②-b `SessionKey` 回显 | **True**，值 `{"AccountServerId":4,"MxToken":"d1507dc8-c93d-4a3b-90c8-9d45df94d84b"}` | ✅（新逻辑生效） |
| ②-c `ServerNotification` | **None**（LoginSync 不再盖 8） | ✅（符合本次改动意图） |
| ③ `Mail_Check`(7001) | HTTP 200 ｜ 250 B ｜ **ServerNotification = 8** | ✅（邮件类仍带未读标记） |
| ④ 日志异常 | `01:53` 之后 `Exception / NullReference / Error Response / [ERR]` → **0 条** | ✅ |
| **总判定** | **SELFCHECK = PASS（exit 0）** | **KEEP** |

## 6. 真实客户端流量（自检期间同时发生，佐证未破坏链路）

```
01:54:13  MomoTalk_MessageList(33001) -> 200
01:54:14  MomoTalk_Read(33002)        -> 200
01:54:15  Account_CheckNexon(1014)    -> 200
01:54:15  Account_Auth(1002)          -> 200（326 ms）
01:54:17  Account_LoginSync(1019)     -> 200（1,595 ms，All queries 1015 ms）
01:54:17  Mail_Check(7001)            -> 200
```

## 7. 未动项实测

```
Schale.dll                     = b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858  ✅
Data/GachaRecruitBanners.cn.json = 3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77  ✅（529 条）
Resources/ClientItemIds.txt    = 48af0fd945fbd2dfaca0afa022b9cafb7095514bfd578b85a09dca17bbeb5ac6  ✅
桥 account_auth_probe.py md5   = da07749d63487ce28ce8d571853b037f  ✅（ITEMLIST-4000 v2 版，未动）
nginx / 数据库：未触碰
```

## 8. 备注（供后续观察）

- 本次只改响应壳：`SessionKey` 现在每条响应都回显；`ServerNotification` 仅在邮件类协议（7000–7004）带未读标记。
- `LoginSync` 仍然**没有** `RequestId` 字段（本次未加，官方有）；如需继续对齐，可作为下一步单变量。
- 若真机出现异常，一键回滚：`bash /root/ENVELOPE1_20261119_015359/ROLLBACK.sh`
