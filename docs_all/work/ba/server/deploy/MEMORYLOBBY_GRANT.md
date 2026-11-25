# 记忆大厅（MemoryLobby）发放 —— 精确参数

查证时间：2026-11-17 03:05。数据来源：本地客户端 ExcelDB `work\ba\data\ExcelDB.db`（398 张表，可直接读）。

---

## 结论

**记忆大厅 ID == 角色的 `UniqueId`。**

证据：
```
MemoryLobbyDBSchema (258 行，FlatBuffers)
  Id=10000  name=LobbyAru
  Id=10001  name=LobbyEimi
  Id=10002  name=LobbyHaruna
  ...
  Id=13010  name=LobbyYuuka      ← 幽香
  ...
  Id=1000501  LobbyHoshino_multi
  Id=1001001  LobbyShiroko_multi
```

对照账号 2 的角色：
```
Characters(AccountServerId=2): UniqueId = 13010, 16003, 13003, 26000
                                        ↑
                                  13010 就是幽香
```

⇒ **`LobbyYuuka` 的 ID `13010` 与幽香角色 `UniqueId` 完全相同。**

⇒ 用户从一开始就判断对了：**角色有，但记忆大厅没解锁。**

---

## 发放方式（正规通道，不写 SQL）

`ParcelType.MemoryLobby = 8`（`Schale/FlatData/ParcelType.cs:18`）

```
!mail 8 13010 1
       ↑  ↑     ↑
       │  │     └ 数量
       │  └────── MemoryLobbyUniqueId（幽香）
       └───────── ParcelType.MemoryLobby
```

链路：
```
MailCommand → 写 Mails 表（ParcelInfos 里 Type=8, Id=13010）
  → 客户端领邮件
  → ParcelHandler.cs:114  case ParcelType.MemoryLobby
  → ParcelResolver.UpdateMemoryLobby（ParcelResolver.cs:240-249）
  → 按 (AccountServerId, MemoryLobbyUniqueId) 幂等插入 MemoryLobbies 表
```

GM 控制台默认绑 `--id 2`（用户的号），**命令不需要指定账号**。

---

## 数据模型要点（别搞混）

| 表/字段 | 含义 |
|---|---|
| `MemoryLobbies`（表）| **拥有集合** —— 账号有哪些记忆大厅 |
| `Accounts.MemoryLobbyUniqueId` | **当前选中** —— 只改它改不出"拥有" |
| `MemoryLobbyHandler` 的四个 handler | **一个都不写** `MemoryLobbies`（List 只读、SetMain 只改 `Accounts.MemoryLobbyUniqueId`）|
| `ParcelType.MemoryLobby`（=8）| **唯一**能写 `MemoryLobbies` 的途径 |

---

## 完整 MemoryLobby 清单（258 条，按需查）

前 12 个（顺序与角色编号一致）：
```
10000 LobbyAru      10001 LobbyEimi      10002 LobbyHaruna   10003 LobbyHihumi
10004 LobbyHina     10005 LobbyHoshino   10006 LobbyIori     10007 LobbyMaki
10008 LobbyNeru     10009 LobbyIzumi     10010 LobbyShiroko  10011 LobbyShun
```
multi 版本（多人立绘）ID 是 7 位，如 `1000501 LobbyHoshino_multi`。

**查询方法（可复用）**：`MemoryLobbyDBSchema` 的 `Bytes` 是标准 FlatBuffers，字段布局：
```
f0 = Id（int，与表里的 Id 列相同）
f1 = 类型（int，观察到恒为 3）
f3 = Id（重复一份）
f4 = 名称字符串（如 "LobbyYuuka"）
f7 = 资源路径（如 "UIs/01_Common/08_Lobbyillust/Lobbyillust_Icon_Yuuka_01"）
```

---

## 待验证

- `!mail 8 13010 1` 发出后，客户端领邮件是否能正常解锁（需真客户端操作）
- 解锁后教程是否因此能继续（教程本来期望通过桃信拿到它 —— 用邮件发是否等效，**未验证**）
- 桃信那条链（`MomoTalkOutLines` / `MomoTalkChoices` 目前 0 行）是否需要另外补 —— **可能仍然需要**
