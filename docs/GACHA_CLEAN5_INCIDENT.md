# 事故记录：卡池清单 529→5 导致登录失败（已回滚）

时间：2026-11-19 00:17 – 00:23
状态：**已回滚，链路恢复正常**；根因代码待修

---

## 1. 发生了什么

按方案 (a)「只保留客户端能完整渲染的 5 个卡池」，把
`/www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json` 从 **529 条（40,739 B / `3ac8385d…`）**
改成 **5 条（480 B / `ed3a3d86…`）**，重启服务。

用户随后登录，客户端弹出 **「同步账号信息时发生错误」**，并进入 2 秒一轮的重试死循环。

## 2. 因果链（有堆栈，不是推测）

```
卡池清单 529 → 5
   ↓
POST /api/shop/list  (Shop_List, protocol 10002)
   ↓
ShopManager.GetShopList(context, account, shopExcel, reqCategoryList)
   ↓ NullReferenceException（第一帧就在这里）
{"Protocol":-1,"ErrorCode":500}
   ↓
客户端把这次同步判为失败 → 弹「同步账号信息时发生错误」→ 重新认证 → 再同步 → 再失败
```

### 关键堆栈（原文）

```
2026-11-19 00:19:28.322 +08:00 [ERR] Error invoking handler for protocol "Shop_List"
System.NullReferenceException: Object reference not set to an instance of an object.
   at Shittim_Server.Services.ShopManager.GetShopList(SchaleDataContext context, AccountDBServer account, List`1 shopExcel, List`1 reqCategoryList)
   at Shittim_Server.Core.NetworkProtocol.Handlers.ShopHandler.List(SchaleDataContext db, ShopListRequest request, ShopListResponse response)
   at Shittim_Server.Core.ProtocolHandlerRegistry.InvokeHandler(Protocol protocol, RequestPacket request)
2026-11-19 00:19:28.324 [INF] Error Response: {"Protocol":-1,"ErrorCode":500,"ServerTimeTicks":639306443680000000}
```

### 登录重试循环（原文）

```
00:22:18 Account_Auth        200
00:22:18 Account_LoginSync   200
00:22:19 Item_List           200
00:22:20 Account_Auth  ❌ UnauthorizedAccessException: Session key required
          Error Response: {"Protocol":-1,"ErrorCode":3}
00:22:22 Account_Auth  ❌ 同上
```

## 3. 前后对比（srv-ops 复核）

| 指标 | clean5 期间（00:17:52–00:23:01） | 回滚后（00:23:01 起） |
|---|---|---|
| `Shop_List` NullReferenceException | **2 次**（00:19:28.322 / .341） | **0** |
| `Session key required` | 2 次（00:22:20 / 00:22:22） | **0** |
| `ErrorCode:3` | 2 条 | **0** |
| 卡池文件 | 5 条 / `ed3a3d86…` | **529 条 / `3ac8385d…`** |

`Shop_List` NRE **首次出现时间 = 00:19:28.322**，落在 clean5 生效窗口内；回滚后未再出现。

## 4. 重要澄清：不是「卡池变少」本身的问题

`00:20:02` 那一次登录，服务端**已经是 5 条卡池**，客户端完整走完
`CheckNexon → Auth → LoginSync → Item_List → GetTutorial → Mission ×4 → … → Friend_Check → Billing`，**是成功的**。

所以「5 条 → 登录必崩」不成立。真正的问题是 **`ShopManager.GetShopList` 里有一个隐藏的空指针**，
任何把卡池清单砍到它没预料到的规模/内容时都会被触发。**在修掉这个空指针之前，任何卡池筛选方案都走不通。**

## 5. 已排除的噪声

`00:19:15` 前后的一批 `Protocol "10017"…"10030" / "90010" doesn't have corresponding type registered`
是 srv-ops 当晚扫协议号造成的，与本次故障无关，回滚后一条都没有。

## 6. 我的执行失误（必须记下来）

- **跳过了单变量**：应该先只留 1 个卡池（`7000001`）验证，却一次性上了 5 个。
- **没有先确认登录**：改完直接让用户去点招募，没有先跑一遍"登录是否正常"的检查。
- 违背了用户红线「不要乱改以前的东西，任何改动都可能破坏当前已跑通的部分」。

**后续规矩**：
1. 任何卡池/表相关改动，**先单变量（1 个）**，可秒回滚
2. **改完先验登录**，登录正常才谈界面表现
3. 修 `GetShopList` 空指针是**前置条件**，没修之前不碰卡池清单

## 7. 回滚

```
备份目录：/root/GACHACLEAN5_20261119_001751/
一键回滚：bash /root/GACHACLEAN5_20261119_001751/ROLLBACK.sh
```

回滚后状态（已确认）：卡池 `3ac8385d…`（529 条）、`ba-shittim` active、5000/5100 在听、
`Shop_List` NRE = 0、`Session key required` = 0。

## 8. 下一步

1. **修 `ShopManager.GetShopList` 的空指针**（已派代码子 agent，产出 `SHOPLIST_NRE_FIX.md`）
2. 修复编译产物经 **srv-ops** 部署（先备份、给回滚、单变量）
3. 部署后**先验登录**，再讨论是否做「只留 1 个卡池」的单变量实验
