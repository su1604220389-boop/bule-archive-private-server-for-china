# `/api/state` 缺少 AddressablesCatalogUrlRoots —— 只读取证

- 执行者：srv-ops
- 时间：2026-11-17 21:16–21:17（北京时间 UTC+8）
- 纪律：**只读**。未改 `state1.json`、未改 nginx、未 reload、未动桥/DLL/DB

---

## 结论一行

**官方 `/api/state` 里**有** `AddressablesCatalogUrlRoots`（3 条 static 根）+ `ResourceVersion/TableVersion/MediaVersion/PatchVersion`；我们实际发给客户端的 `state1.json`（64 B）**一条都没有**；而 `state2.json`（676 B）**有**（就是官方样本）。**

---

## ① `state2.json` 全文（官方样本，676 B）

```json
{"CallbackUrl":"{\"order_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/order/notify\",\"survey_notify\":\"http://gs-inter.bluearchive-cn.com:4000\",\"web_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/web/notify\",\"account_logout\":\"http://gs-inter.bluearchive-cn.com:4000/api/account/logout\"}","CustomerServiceUrl":"","AddressablesCatalogUrlRoots":["https://static.bluearchive-cn.com/prodm39","https://static-qc.bluearchive-cn.com/prodm39","https://static-hs.bluearchive-cn.com/prodm39"],"ResourceVersion":"202611051844","TableVersion":"202611051826","MediaVersion":"202611051836","PatchVersion":"202609291539","State":1,"Msg":"","IsOpenPreDownload":true}
```
**字段清单（10 个）**
```
CallbackUrl / CustomerServiceUrl / **AddressablesCatalogUrlRoots**(3 条) /
**ResourceVersion**=202611051844 / **TableVersion**=202611051826 / **MediaVersion**=202611051836 /
**PatchVersion**=202609291539 / State=1 / Msg="" / IsOpenPreDownload=true
```

## ② `state1.json` 全文（我们当前实际发的，64 B）

```json
{"Servers":["https://example.com/api/"],"State":1,"Msg":""}
```
**⇒ 没有 `AddressablesCatalogUrlRoots`、没有任何版本号、也没有 `CallbackUrl`。**

## ③ 服务器上其它同名文件（说明这条本来就有"完整版"）
```
/www/wwwroot/_ba_state/gw/api-state.json                          ← 676 B 完整版（同 state2）
/www/wwwroot/_ba_state/cn_real_capture/state_real.json            ← 676 B 完整版
/www/wwwroot/bapatch/state/gw/api-state.template.json             ← 模板：**字段更全**
/www/wwwroot/bapatch/state/gw/api-state.json                      ← 同上（模板态，版本号为空）
```
**模板版（`api-state.json`）的字段最全，包含：**
```
AddressablesCatalogUrlRoot / AddressablesCatalogUrlRoots / ApiUrls /
ResourceVersion / TableVersion / MediaVersion / PatchVersion /
AssetBundlesUrlRoots / BundlesCatalogUrls / BundlesHashUrls /
AddressCatalogUrls / AddressHashUrls / MediaUrlRoots / MediaManifestUrlRoots /
MediaManifestHashUrlRoots / TableManifestUrlRoots / TableManifestHashUrlRoots /
TableUrlRoots / PatchUrlRoots / PatchCatalogUrlRoots / CDNLineCount / Msg
```
**⇒ "完整 state" 的结构我们本地就有据可查；只是实际对外服务的是 64 B 那个降级文件。**

## ④ 客户端会去哪个地址拉 catalog（重要限制）

拿 `AddressablesCatalogUrlRoots` = `https://static.bluearchive-cn.com/prodm39`（等 3 条）去**真实 CDN** 实测（21:10 / 21:17 两次）：

```
/prodm39/catalog_Remote.json                      404 (NoSuchKey)
/prodm39/catalog_Remote.hash                      404
/prodm39/catalog_Remote.zip                       404
/prodm39/Android/catalog_Remote.json              404
/prodm39/AssetBundles/Android/catalog_Remote.json 404
/prodm39/202611051844/catalog_Remote.json         404
/prodm39/AssetBundles/Android/202611051844/catalog_Remote.json  404
/prodm39/catalog_Remote_202611051844.json         404
/prodm39/AssetBundles/Android/AddressbleAssetInfo.txt    **200 / 6,553,315 B**
```
**⇒ 结论：真实 CDN 上**确实**有 `prodm39` 这个根（bundle 清单能下 6.5 MB），**但 `catalog_Remote.*` 在任何常见路径上都 404。**

**这意味着：把 `AddressablesCatalogUrlRoots` 补回 `state1.json`，只是把"去哪里拉"告诉客户端；客户端照着去拉 `catalog_Remote.json` 仍然会 404（除非它的真实请求路径与我们猜的不同）。**

---

## ⑤ 回答你的四问

**1. 官方 `/api/state` 里有没有 `AddressablesCatalogUrlRoots`？**
**有。** 值 =
```json
["https://static.bluearchive-cn.com/prodm39","https://static-qc.bluearchive-cn.com/prodm39","https://static-hs.bluearchive-cn.com/prodm39"]
```
**2. 我们的 `state1`/`state2` 里有没有？**
`state1.json`（实际对外）：**没有**（64 B，三个键）。
`state2.json`（官方样本，目前挂在 www 块、但因 server_name 冲突被 ignored）：**有**。

**3. 补进 `state1.json` 是否就能让客户端去官方 CDN 拉完整 catalog？**
**能"告诉它去哪"，但不保证"拉得到"** —— 因为：
- ✅ 字段补上后，客户端**会**去做资源版本检查（`ResourceVersion` 也一并补），并用 `AddressablesCatalogUrlRoots` 作为根；
- ❌ 但我们实测该根下的 `catalog_Remote.*` **全是 404**（见 ④）。客户端可能因此报"资源下载失败"或继续用旧缓存 —— **两种结果都必须实测**。
- ⚠ 还有一层：`ResourceVersion=202611051844` 是**官方 2026-11-05 的版本**；我们现在 `OverrideVersionId=53c8e5c4ff484d23`（老版本）。**版本号与 CDN 内容是否自洽，今晚无法确认**。

**4. 补进去之后客户端会去哪、我们要不要放行/代理？**
- 会去 `static.bluearchive-cn.com` / `static-qc` / `static-hs` 的 `/prodm39/...`；
- 这三条在 `ba_sni.conf` 里是**强制透传到真实 CDN**，**不需要我们放行或代理**（现状已通，`AddressbleAssetInfo.txt` 200 就是证明）；
- **⇒ 如果只补 state 字段，最好的情况是"客户端自己去 CDN 拉 → 拉到 → 招募恢复"，最坏是"拉 404 → 招募仍坏但日志里能看到它到底请求了哪条路径"** —— 后者其实是我们最需要的证据。

---

## ⑥ 我的建议（等你决定，我没动任何文件）

**第一步（低风险、可秒回滚）：只改 `state1.json`，补 4 个字段**
```json
{"Servers":["https://example.com/api/"],
 "AddressablesCatalogUrlRoots":["https://static.bluearchive-cn.com/prodm39",
                                "https://static-qc.bluearchive-cn.com/prodm39",
                                "https://static-hs.bluearchive-cn.com/prodm39"],
 "ResourceVersion":"202611051844","TableVersion":"202611051826",
 "MediaVersion":"202611051836","PatchVersion":"202609291539",
 "State":1,"Msg":"","IsOpenPreDownload":true}
```
- **为什么安全**：`state1.json` 是 `location = /api/state` 直接读的静态文件，**改它不用 reload、不用碰 nginx**；回滚 = `cp -a` 回备份（我会先备份并给 sha256）。
- **预期观测点**：
  1. 客户端启动后**是否**开始请求 `static*/prodm39/*`（`tcp-access.log` 里 `sni=static*` 会立刻变多，且字节量明显变大）；
  2. 若开始请求，**请求的 path 是什么** → `ba_static.log` 不进（因为透传），只能用 tcp 抓不到路径；**所以这条要靠手机侧抓包**；
  3. 招募页是否恢复。

**⚠ 一个必须提醒的风险**：`ResourceVersion` 一旦给了非空值，客户端**可能触发一次真实更新流程**（下载/校验大量资源）。如果 CDN 上那个版本的数据不完整，**可能让客户端进入"更新失败"状态**（比现在更糟）。**所以这一步最好在手机侧可回滚的前提下做**（备份 `files/` 整个目录，或至少 `catalog_Remote.*` + `manifest*.db`）。

**第二步（若第一步后 client 仍在拉 `catalog_Remote.json` 且 404）**：那时我们才需要 B 阶段"接管 catalog"，而且**前提变成**：由手机侧抓包给出**真实的 catalog 请求 URL**，我照着接管，不再靠猜路径。

---

## 本轮未改动
```
未改 state1.json / state2.json
未改 nginx / 未 reload
未改桥 / DLL / DB
未动手机侧
新增：仅本报告
```
