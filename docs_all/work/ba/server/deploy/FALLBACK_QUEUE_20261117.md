# 降级清单：还有哪些协议在用假响应

抓取时间：2026-11-17 01:24:57 ~ 01:24:58（用户首次进入游戏、新手教程期间）
数据来源：`srv-ops` 只读抓取 `/www/wwwroot/bapatch/logs/api_probe.out`

## 背景

客户端登录一次会连发 17 条请求。其中 12 条由正确的生成器服务，**5 条仍在走 `min+base` 假响应**。这 5 条就是接下来会静默卡住的地方。

## 全序列（17 条，一条不落）

```
01:23:39  /api/state                      req=0     200/0        gen_kind=None            （GET 探活，正常）
01:24:08  /api/networktime/sync           req=325   200/620      networktime-3            （srv-ops 自测）
01:24:57  /api/account/auth               req=1374  200/3520     gen_kind=None            （1002 专分支，正常）
01:24:57  /api/academy/getinfo            req=882   200/1772     academy-24000-v3         ✅
01:24:57  /api/account/loginsync          req=1138  200/122968   loginsync-1017-dynamic   ✅
01:24:57  /api/item/list                  req=882   200/640      simple-4000              ✅
01:24:57  /api/networktime/sync           req=882   200/600      networktime-3            ✅ ★本次打通
01:24:57  /api/contentsave/get            req=882   200/600      simple-26000             ✅
01:24:58  /api/management/data            req=882   200/2092     management-90004         ✅
01:24:58  /api/account/gettutorial        req=882   200/512      simple-1005              ✅
01:24:58  /api/shop/listtutorialgacha     req=882   200/512      min+base                 ⚠️ 90011
01:24:58  /api/mission/list               req=906   200/536      min+base                 ⚠️ 8000  (1/3)
01:24:58  /api/mission/guidemissionseason req=882   200/512      min+base                 ⚠️ 8006
01:24:58  /api/mission/list               req=906   200/536      min+base                 ⚠️ 8000  (2/3)
01:24:58  /api/mission/list               req=926   200/536      min+base                 ⚠️ 8000  (3/3)
01:24:58  /api/minigame/missionlist       req=926   200/512      min+base                 ⚠️ 35003
01:24:58  /api/toast/list                 req=882   200/512      min+base                 ⚠️ 16000
```

`Traceback = 0`，`error/exception/p3_err = 0`。

**一条重要的更正**：`/api/management/data` 返回 `gen_kind=management-90004` / 2,092 B，说明 **90004 已经由真生成器服务**。这与早前"`patch_90004` 已上传但未 apply"的记录不符 —— **以日志为准，那条记录作废**。

## 待补清单（按紧急度）

| # | gen | 路径 | 现状 | 次数 | 官方体量 | 可用材料 | 状态 |
|---|---|---|---|---|---|---|---|
| **1** | **8000** | `/api/mission/list` | 536 B `min+base` | **3 次**（被反复请求，最急） | **268,396 B** | `patch_8000.py` 42,964 B / sha `045c28d9…` 已在服务器、已双端校验 | **未 apply** |
| 2 | 8006 | `/api/mission/guidemissionseasonlist` | 512 B `min+base` | 1 | — | 本地有 `gen8006` | 待做 |
| 3 | 90011 | `/api/shop/listtutorialgacha` | 512 B `min+base` | 1 | — | 无生成器 | 待做 |
| 4 | 35003 | `/api/minigame/missionlist` | 512 B `min+base` | 1 | — | 本地有 `dto_extra/proto35003_minigame_mission.json` 与 `empty_builder` 骨架 | 待做 |
| 5 | 16000 | `/api/toast/list` | 512 B `min+base` | 1 | — | `empty_builder` 已覆盖（42 断言全过，**未部署**） | 待做 |

## 为什么 8000 是第一优先

一次登录里被**连发 3 次**（req 906 / 906 / 926 B，仍在递增 —— 客户端在变化入参重试），全部拿回 536 B 空构造。官方同一接口回 **268,396 B**。这是任务/剧情系统的入口，教程推进到任务界面时几乎必然卡住。

## 上线代价：必须重启

这些补丁都改 `account_auth_probe.py`，**必须重启 bridge 才生效**（pid 2569402）。重启会把在线客户端踢下线。

⇒ **策略：不在用户在线游玩时重启。** 等他撞墙、退出游戏后，一次性把所有要打的补丁批量打上，只重启一次。

## 打完每个补丁后的验收口径

- **不要看字节数**（同一协议不同会话字节数会变，见 `P3_ACCEPTANCE.md` §2 第 9 条）
- 看 **`gen_kind` 变了没**（`min+base` → `<真生成器名>`）
- 看 **7 键/应有键是否齐备**、关键数值是否非 0
- 看 **`Traceback = 0`** 且该协议之后客户端**继续发下一个请求**
