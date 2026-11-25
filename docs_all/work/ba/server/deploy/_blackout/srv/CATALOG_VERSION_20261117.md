# 招募界面 catalog 版本问题 —— 只读取证

- 执行者：srv-ops
- 时间：2026-11-17 21:05（北京时间 UTC+8）
- 现场（手机侧，Lead 提供）：`catalog_Remote.json` 81,410,257 B / `catalog_Remote.zip` 12,283,640 B 均为 **11-13 03:22**；`catalog_Remote.hash` 831a1ba7… 与 `manifest*.db` 为 **11-17 20:53**
- 症状：招募页「卡池名 DUMMY」「No LocalizeKey ×5」，角色立绘/日期/价格/按钮正常
- 本轮**未改任何东西**（无 nginx reload、无代码/配置/数据改动）

---

## 结论（三句）

1. **catalog 从「真实 CDN」拿，不是我们。** `static*.bluearchive-cn.com` 在 stream 层被强制透传；`tcp-access.log` 里 103 条 `sni=static*` 记录的上游**全是外部 IP**，我们的三个 `ba_static*.log` 自 **11-14 04:35** 起就没有新条目（那几条还是我当天用 curl 打的 404）。
2. **"hash 新、内容旧"是客户端自己的状态，不是我们喂错版本。** 我们**没有任何** catalog / ResourceVersion / CatalogHash 下发路径：桥的 90004 stub 里 `Banners: []`、`Notices: []`、`Events: []`，没有任何版本字段；Shittim 侧 `grep ResourceVersion|TableVersion|CatalogHash` = **0 命中**；`catalog_Remote.hash` 是客户端自己在 20:53 与 `manifest.db` 同分钟写下的。
3. **建议做法 = (c) 变体**：**先只补 Localize/文本 bundle，不要整包重拉 catalog**（理由见 §4：整包重拉要客户端删本地 catalog 并回官方 CDN，风险与代价都最高；而我们真正缺的只是文本）。

---

## ① 客户端下载资源打到谁 —— **真实 CDN**

```
grep 'sni=static' tcp-access.log | wc -l  = 103
最近 15 条（时间 / 上下行 / 时长 / 上游）：
20:00:03 sent=0      recv=517   dur=5.105    up=122.225.32.35:443
20:00:09 sent=6100   recv=767   dur=0.076    up=122.225.32.35:443
20:00:54 sent=6954   recv=853   dur=0.243    up=36.136.120.20:443
20:01:07 sent=6954   recv=853   dur=0.189    up=36.136.120.20:443
20:02:04 sent=8060   recv=1933  dur=123.808  up=122.225.32.35:443
20:45:35 sent=6952   recv=853   dur=0.169    up=123.148.116.78:443
20:52:58 sent=6100   recv=767   dur=0.235    up=122.225.32.35:443
20:53:08 sent=6100   recv=767   dur=0.075    up=122.225.32.35:443
20:55:02 sent=8060   recv=1933  dur=121.413  up=122.225.32.35:443
21:03:04 sent=6953   recv=853   dur=0.145    up=36.151.118.211:443
21:03:14 sent=6953   recv=853   dur=0.126    up=36.151.118.211:443
21:03:56 sent=8685   recv=1933  dur=49.804   up=36.151.118.211:443
21:04:02 sent=6100   recv=767   dur=0.187    up=122.225.32.35:443
21:04:12 sent=6100   recv=767   dur=0.092    up=122.225.32.35:443
21:04:15 sent=6100   recv=767   dur=0.072    up=122.225.32.35:443

上游 IP 汇总：39.175.108.47(15) / 122.225.32.35(15) / 101.68.219.169(14) / 36.150.72.84(12)
              183.131.185.35(12) / 223.111.119.35(8) / 122.228.115.35(6) / 112.25.92.35(4) …
```
**⇒ 全部是真实 CDN 节点，不是 `127.0.0.1:8443`。**

我们的 static vhost 日志（只是旁证）：
```
ba_static.log        2,132 B   mtime 2026-11-14 04:35:17   ← 之后 0 条
ba_static_mitm.log   0 B       mtime 2026-11-14 04:44:28
ba_static_status.log 0 B       mtime 2026-11-14 04:44:28
（里面那 3 条是 11-14 我用 curl 探 catalog_Remote.json / .hash / AddressbleAssetInfo.txt 得到的 404）
```

**注意一个事实（影响下一步判断）：客户端在 20:53–21:04 确实在跟 CDN 说话，且每次只传 6–8 KB 下行、0.1–0.2 秒就结束** —— 这不是"下载 12 MB zip"的体量，更像**校验/取 hash/取小 manifest 片段**。**真正的大文件（81 MB json / 12 MB zip）在 11-13 就已经在本地了，今天没有重下。**

---

## ② 我们自己有没有在服务 catalog —— **完全没有**

```
nginx conf 里 grep catalog|Addressable|manifest  →  无匹配
本地 Shittim Controllers/ 里 AddressablesController  →  缺失（上游有）
noroot_payloads/ 只有：state1.json (64 B)、state2.json (676 B)
5000 端口探路结果：
  /catalog_Remote.json            404 0
  /prodm39/catalog_Remote.json    404 0
  /AddressablesCatalog.json       404 0
  /api/addressables               404 0
  /manifest.db                    404 0
```
**⇒ 我们没在服务任何 catalog / manifest / bundle。**

---

## ③ `catalog_Remote.hash` 今天 20:53 是谁刷新的 —— **客户端自己**

**我们没有任何版本字段可下发：**
```
桥（account_auth_probe.py）90004 Management_Data stub 原文（L1784-1806）：
    obj = {"Protocol": 90004, "ServerTimeTicks": ..., "ServerNotification": 0,
           "MissionProgressDBs": [], "EventMissionProgressDBDict": {},
           "BattlePassMissionProgressDBDict": {},
           "StaticOpenConditions": {...},
           "Notices": [], "Events": [], "Issues": [], "Banners": [],
           "GachaProbabilityDisplay": False, "ContentLock": False,
           "GachaPeriodDisplay": False, "RaidPeriodDisplay": False, "GuidePopup": {}}
（Banners / Notices / Events 全是空数组；**没有任何 ResourceVersion / TableVersion / CatalogHash 字段**）

桥里 grep ResourceVersion|TableVersion|CatalogHash|catalog = 0 命中
Shittim 侧 grep ResourceVersion|TableVersion|CatalogHash = 0 命中
Management_Data 响应长度恒定 2,092 B（55 次请求，21:03–21:04 三次都是 2092）
```
**⇒ 结论：客户端那个 `831a1ba7…` 是它自己在更新 `manifest.db` 后**本地算出来**的；我们从没下发过任何 catalog 版本/hash，也就谈不上"喂错版本"。**

**那"内容旧"是怎么来的？** 与手机侧证据一致的最简解释：
- 11-13 那天下载了当时的 `catalog_Remote.json/zip`；
- 之后（含今天 20:53）客户端只是**重新校验/重建了 manifest 与 hash**，**没有重新下载 catalog 本体**（今天 static 会话全部 0.1–0.2 s / 6–8 KB，不够下 12 MB）；
- 于是"hash 是今天的、内容是 11-13 的"。**这是客户端的缓存/版本判定逻辑，不是我们的数据。**

---

## ④ 要让招募文案出现，正确做法

### (a) 让客户端重新完整拉一次 catalog + bundle
- **条件**：客户端必须**认为本地 catalog 过期**。它现在显然认为"不过期"（hash 已刷新但没重下）。强制手段只有三个：
  1. 删/改名手机 `files/catalog_Remote.*` 与 `manifest*.db`（需要手机 root 或 PRoot 文件访问）；
  2. 让服务端**下发一个更高的 ResourceVersion/TableVersion**（我们没有这条链路，要先做 (b) 的一部分）；
  3. 换一个 `VersionId`（我们 20:34 已把 `OverrideVersionId` 固定成 `53c8e5c4ff484d23`，改它会影响全服）。
- **会不会走官方 CDN**：会 —— `ResUrls` 指向 `static*.bluearchive-cn.com`，我们透传。
- **风险**：**高**。① 12 MB zip + 81 MB json 全量重下，流量与耗时都大；② 官方 CDN 上**未必还有 `prodm39/53c8e5c4…` 这个版本的完整 bundle**（我们版本号取自 `ba_version_cache.json`，`LastUpdatedUtc 2026-08-07`，很可能是老版本）；③ 一旦下到"版本对但内容更差"的包，招募/其他 UI 可能更糟；④ 无 root 环境下删文件这一步用户不一定做得到。

### (b) 我们在服务端发 catalog（自己当 CDN）
- **可行性**：技术上可以（补 `AddressablesController` + `Data/catalog` + nginx/vhost 路由；上游已有实现可抄），但**客户端 `ResUrls` 写死在 APK/`LocalizeConfig.txt` 里指向 `static*`**，而 `static*` 现在是**透传红线**。要让我们接管，必须改 `ba_sni.conf`（红线）**或**改客户端 ResUrls（要重打包 APK）——**两条都不是今晚能动的**。
- **工作量**：中-大（catalog 解析/切片/断点、CORS、hash 一致性）。
- **结论**：**不建议**，除非确定长期要脱离官方 CDN。

### (c) **推荐：只补 Localize 文本/横幅 bundle**
理由：用户实测的是**只有文本占位**（卡池名 DUMMY、No LocalizeKey ×5），立绘/日期/价格正常 ⇒ 缺的是 **Localize 相关 bundle**，不是整套 catalog。
- **最小动作**：让客户端**只重下 Localize 那几个 bundle**。手段：在客户端侧把 `catalog_Remote.hash`（或 `Localize` 条目的 hash）改掉 → 客户端会判定该条目变化并单独重下（走真实 CDN），**不用重下 81 MB catalog**。
- **前提（需要手机侧确认）**：`catalog_Remote.json` 里 Localize 相关 entry 的 `InternalId`/hash 字段结构（Addressables catalog 的 `m_LocatorId`/`m_BucketDataString`/entry hash）。**这条我无法从服务器侧确认，需要手机侧把 catalog JSON 的 header/前几 KB + grep `Localize` 的片段发来。**
- **风险**：低-中（只影响 Localize 条目）。

### 我建议的推进顺序（今晚不动手）
```
1) 手机侧把 catalog_Remote.json 前 ~4 KB（header/m_LocatorId）与 grep -o 'Localize[^,]*' 片段发来
2) 我据此判断：是"条目 hash 已变但客户端没下" 还是 "条目本身指向我们版本里不存在的旧地址"
3) 若是前者 -> 只改 Localize 条目 hash（客户端侧一个字节级改动或删对应 bundle 缓存），重下单个 bundle
4) 若后者 -> 才考虑 (a) 全量重拉，且先在手机侧备份 catalog/manifest
```

---

## 附：顺便记录的一个事实（与招募无关但重要）

`Management_Data(90004)` 的 `Banners` / `Notices` / `Events` **恒为空数组**（桥 stub 写死）。如果以后要让**活动横幅/公告**出现在大厅，这里必须补内容；**但它不影响招募文案**（文案来自客户端 Localize bundle）。

## 本轮未改动
```
未 reload / 未改 nginx
未改桥 / DLL / 数据库
未动手机侧任何东西
新增：仅本报告
```
