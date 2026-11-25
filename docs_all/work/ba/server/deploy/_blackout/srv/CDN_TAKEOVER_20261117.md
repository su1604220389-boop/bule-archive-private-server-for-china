# CDN 接管 —— 阶段 A 执行记录（**停在 A2，未进入 B**）

- 执行者：srv-ops
- 时间：2026-11-17 21:09–21:11（北京时间 UTC+8）
- 依据 Lead 的纪律：**「A 阶段任何一步不理想就停，宁可今晚不做」**
- **未改任何 nginx 配置、未 reload、未进入 B 阶段**

---

## 结论

**A1 成功（备份就绪）。A2/A3 失败：真实 CDN 上取不到 `catalog_Remote.json` / `.hash` / `.zip` —— 三个 static 域名、多个路径变体全部返回 `404 NoSuchKey`。A4 目录已建但为空。⇒ 按纪律停在这里，B 阶段（改成"先到我们"）不应该做。**

---

## A1 备份（✅ 完成）

```
BACKUP_DIR=/root/ba_nginx_backup_20261117_210952
e1f6818276f2bf361f3fd93810cd2e583513711688e584e033c58fc6617464e0  ba_mitm.conf
82112af23d7c4945aa4d0110e615cae38ff9d321e0ee765ab0aa23c1dcfdf961  ba_sni.conf
ad0e7c63028a00db7c01bc5bb83e1e2c6cfb7a414acc641fddf0fac1c02ea281  nginx.conf
（SHA256SUMS 已写入该目录）
```
**回滚一行（随时可用）**
```bash
D=/root/ba_nginx_backup_20261117_210952
cp -a $D/ba_sni.conf /www/server/panel/vhost/nginx/tcp/ba_sni.conf && \
cp -a $D/ba_mitm.conf /www/server/panel/vhost/nginx/ba_mitm.conf && \
nginx -t && nginx -s reload && echo ROLLED_BACK
```

## A2 出站取 catalog（❌ 失败）

```
static.bluearchive-cn.com     → 123.148.116.78
  /prodm39/catalog_Remote.json   http=404 size=402 time=0.177  ct=application/xml
  /prodm39/catalog_Remote.hash   http=404 size=402
  /prodm39/catalog_Remote.zip    http=404 size=401
static-qc.bluearchive-cn.com  → 123.148.116.78   三条同样 404
static-hs.bluearchive-cn.com  → 140.249.103.169  三条同样 404
```
**CDN 本身是通的**（证明不是网络问题）：
```
/prodm39/AssetBundles/Android/AddressbleAssetInfo.txt  http=200 size=6,553,315 (6.5 MB) ct=text/plain
```
**404 的原文（OSS 风格）**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Error>
  <Code>NoSuchKey</Code>
  <Message>The specified key does not exist.</Message>
  <RequestId>6AFC5221F30B8932312F3EBB</RequestId>
```
**⇒ 路径不存在，不是被墙、不是证书问题。**

## A2b 追加的路径变体（全部 404）

```
/prodm39/Catalog_Remote.json              404
/prodm39/catalog_remote.json              404
/prodm39/Android/catalog_Remote.json      404
/prodm39/Android/catalog_Remote.hash      404
/prodm39/Android/Catalog_Remote.json      404
/prodm39/prodm39/catalog_Remote.json      404
/com.nexon.bluearchive/53c8e5c4ff484d23/catalog_Remote.json             404
/com.nexon.bluearchive/53c8e5c4ff484d23/Android/catalog_Remote.json     404
/prodm39/version.txt                      404
/prodm39/Android/version.txt              404
/prodm39/                                 404
```
**⇒ `catalog_Remote.*` 不在 `static*.bluearchive-cn.com` 的任何常规路径上。**

## A2c 顺带把 6.5 MB 的 `AddressbleAssetInfo.txt` 拉下来看了（这是**能拿到**的那份）

结构（原文头几行）：
```
MXBundle : MXContentUpdate
MXBundle : InBuildGroup
	[Assets/_MX/AddressableAsset/InBuild/RawData/sensitivewords.txt][20901e55ff003bc4486200078524e633][rawdata/sensitivewords]
	[Assets/_MX/AddressableAsset/InBuild/Audio/...][ef42e7f53a953f84cb8f3bc3fdee3cfb][audio/...]
```
- **`grep -i catalog` = 0 命中**，`grep -i Remote` = 0 命中 ⇒ 这份清单里**没有 catalog 的 URL**，它只是 bundle 名称+md5+内部路径的清单。
- bundle 命名能看到 `Assets-_MX-EffectsFreezed-Texture-Text-_MXDependency-2023-05-30`、`...-UIGachaSSRCharText-...` 这类，**说明文本类资源确实是以 bundle 为单位分发的**（与"招募文案来自 bundle"一致），但**没有单独的 "Localize" bundle 名**（grep localize/text/lang 只匹配到 Texture-Text 这类）。

## A3 校验（未执行 —— 没有文件可校验）

```
/tmp/static*.json 全部是 402 B 的 OSS 404 XML，json.load 会直接失败；
因此 A3 的 `Localize` 校验无法进行（这一点本身就是"停"的理由）。
```

## A4 落盘（目录已建，内容为空）

```
/www/wwwroot/bapatch/cdn/prodm39/    (21:09 创建，**空目录**)
```

---

## 这意味着什么（我的判断，供你决策）

1. **原方案（我们接管 `catalog_Remote.*` 再回源）今晚做不了**：因为没有"真 catalog"可以放到 `/www/wwwroot/bapatch/cdn/prodm39/`。**B 阶段如果做了，客户端会从我们这里拿到 404 → 招募页会更坏。**
2. **"catalog 从哪来"这个前提本身要修正**：客户端本地那份 81 MB `catalog_Remote.json` 不是从 `static*/prodm39/` 下的这个路径拿的。可能来源：
   - 客户端内置（APK 内 `assets/` 或首个版本包）；
   - 或者由 **另一个域名/路径** 提供（我们没探到）；
   - 或者由 **更新流程**（`Management_Data` / `ServerNotification` 里的更新标志 → 客户端走另一条更新链路）下发地址。
3. **要钉死它，最省事的取证不在服务器侧**：手机侧抓一次"打开招募界面 / 更新检查"期间的 HTTP 请求（HttpCanary 或 logcat 里 UnityWebRequest 的 URL），就能看到它到底请求了哪个 URL。**这一条我已经无能为力（服务器侧看不到，因为那些请求要么没发、要么走的是我们无日志的路径）。**

## 建议的下一步（都不动配置）

- **(i) 先要一条手机侧的 URL 证据**（最有效）：打开招募界面时抓包，看有没有对 `catalog_Remote.json` 的请求、host 和 path 是什么。有这条我就能精确接管。
- **(ii) 若抓不到**：说明客户端根本没请求 catalog（用本地那份），那"接管 CDN"这条路**对文案没帮助**，应回到(c) 只补 Localize bundle，或走 APK 内资源替换。
- **(iii) 备选（风险中）**：把 `static*` 先**不接管**，而是**只加一个旁路**（`ba_mitm.conf` 里 static server 块加 `location /prodm39/` 的 404 拦截并落日志），先**观测**客户端到底请求哪些 static 路径 —— 纯观测、不影响现有透传（因为 static 目前根本不进我们 vhost）。**这个要改配置，等你点头。**

## 本轮改动清单
```
新增：/root/ba_nginx_backup_20261117_210952/（3 个备份 + SHA256SUMS）
新增：/www/wwwroot/bapatch/cdn/prodm39/（**空目录**）
新增：/tmp/aai.txt（6.5 MB，官方 bundle 清单，仅取证用）
未改：nginx 任何 .conf、未 reload、未改桥/DLL/DB、未动手机侧
```
