# Shop_List 空指针（NRE）修复部署记录

- 时间：2026-11-19 00:37–00:39（Asia/Shanghai）
- 执行：srv-ops ｜ 服务器：root@<SERVER_IP>
- 结论：**PASS**。无 `CategoryList` 的 `Shop_List` 从 `ErrorCode:500`（NRE）变为 **200 + `ShopInfos: []`**；
  正常 11 分类仍返回完整数据（8 分类 / 1900 条商品 / 205,826 B）；登录同步 200。

## 1. 根因（堆栈为证）

```
2026-11-19 00:19:28.322 [ERR] Error invoking handler for protocol "Shop_List"
System.NullReferenceException: Object reference not set to an instance of an object.
   at Shittim_Server.Services.ShopManager.GetShopList(SchaleDataContext context, AccountDBServer account, List`1 shopExcel, List`1 reqCategoryList)
   at Shittim_Server.Core.NetworkProtocol.Handlers.ShopHandler.List(SchaleDataContext db, ShopListRequest request, ShopListResponse response)
   at Shittim_Server.Core.ProtocolHandlerRegistry.InvokeHandler(Protocol protocol, RequestPacket request)
→ Error Response: {"Protocol":-1,"ErrorCode":500,…}
```
`ShopManager.GetShopList(...)` 在 `reqCategoryList`（请求未带 `CategoryList` 时为 null）上空引用。

## 2. 改动

| 项 | 内容 |
|---|---|
| 代码 | `Shittim-Server/Services/ShopManager.cs`，**+11 / −1**（仅加 null 保护，行为对带分类的请求不变） |
| 产物 | `work\ba\srv_src\_build_shoplistnre\Shittim-Server.dll` |
| `Schale.dll` | `b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858`（**与线上一致，未替换**） |

### DLL sha256 / 字节数

| | sha256 | 字节 | 时间 |
|---|---|---|---|
| 改前 | `2a98a2b36280784e9ff0323fa4ab54c5adaab949e4b1c23e729f80d675ea7e8d` | 2,680,320 | 11-18 23:01 |
| 改后 | `e90867e2b6c75efdb07ff3bc7ea53fb597e3904a588fbab0fb2212f1c50e632b` | 2,680,320 | 11-19 00:37 |

部署方式：`.new` 上传 → 校验 sha256 + 字节数 → `mv -f`；`systemctl restart ba-shittim`，
5000 就绪 **6,165 ms**（轮询），新 pid **2788820**，5100 随后 1 s 就绪。

## 3. 验收

### ① DLL
```
e90867e2b6c75efdb07ff3bc7ea53fb597e3904a588fbab0fb2212f1c50e632b  /www/wwwroot/ba_srv/Shittim-Server.dll
-rw-r--r-- 1 root root 2680320 Nov 19 00:37 /www/wwwroot/ba_srv/Shittim-Server.dll
```

### ② 根因复测：**故意不带 `CategoryList`** 的 `Shop_List`
（走真实网关：`ensure_session` 取到 AccountServerId=4 的会话 → `post_gateway` 发 `Protocol 10002`）
```
HTTP 200 ｜ raw=165 B ｜ outer.protocol='Shop_List'
inner.keys = ['Protocol','ShopInfos','ShopEligmaHistoryDBs','ServerTimeTicks','ServerNotification']
**ShopInfos 分类数 = 0** ｜ 商品条目合计 = 0
inner = {"Protocol":10002,"ShopInfos":[],"ShopEligmaHistoryDBs":[],"ServerTimeTicks":639306455230000000,"ServerNotification":8}
⇒ 修复前：{"Protocol":-1,"ErrorCode":500}；修复后：200 + 空数组  ✅
```

### ③ 正常路径回归：带 `[0,36,37,1,21,2,33,10,25,26,20]`
```
HTTP 200 ｜ raw=**205,826 B** ｜ outer.protocol='Shop_List'
ShopInfos 分类数 = **8** ｜ 商品条目合计 = **1,900**
前 300 字节 = {"Protocol": 10002, "ShopInfos": [{"ShopProductList": [{"ShopExcelId": 1000, "DisplayOrder": 10,
              "PurchaseCountLimit": 5, "ProductType": 1}, …], …}
（改前响应未保存，无法逐字节比对；数量级与结构正常，字段名与改前堆栈/线上一致）
```

### ④ `Account_LoginSync(1019)`
```
HTTP 200 ｜ raw=**585,078 B** ｜ outer.protocol='Account_LoginSync'
inner.keys = ['Protocol','CafeGetInfoResponse','AccountCurrencySyncResponse','CharacterListResponse',
              'EquipmentItemListResponse','CharacterGearListResponse','ItemListResponse','EchelonListResponse',
              'MemoryLobbyListResponse','CampaignListResponse', …]
（改前同量级约 59 万~78 万字节，本次 585 KB，正常）
```

### ⑤ 服务 / 端口
```
systemctl is-active ba-shittim → active
5000 → dotnet pid 2788820 ｜ 5100 → dotnet pid 2788820 ｜ 9097 → python3 pid 2787446
```

### ⑥ 未动项
```
GachaRecruitBanners.cn.json = 3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77（40,739 B / 529 条）✅
桥 account_auth_probe.py md5 = af1bc9a5517a6150546abf0b4a0ce57f（回滚后的版本，未动）✅
cn_4000.txt = 1（未动）✅
/root/shittim.sqlite3 未动 ｜ ExcelDB / nginx 未动
```

## 4. 回滚

```
备份目录：/root/SHOPLISTNRE_20261119_003753/
   Shittim-Server.dll（2a98a2b3…）
   BEFORE.sha256
   ROLLBACK.sh
```

一键回滚：
```bash
bash /root/SHOPLISTNRE_20261119_003753/ROLLBACK.sh
```
手工：
```bash
cp -a /root/SHOPLISTNRE_20261119_003753/Shittim-Server.dll /www/wwwroot/ba_srv/Shittim-Server.dll
systemctl restart ba-shittim
for i in $(seq 1 30); do ss -lnt | grep -q ':5000' && { echo "5000_UP ${i}s"; break; }; sleep 1; done
```

## 5. 备注

- 网关 `/api/gateway` 只接受 **multipart/form-data 的 `mx` 字段**（`cn_cipher.build_mx`），
  直接用 JSON 打会得到 500 `This request does not have a Content-Type header`（已实测），验证脚本已按正确形式重写。
- 验证用的会话来自桥的 `ensure_session(rec, 854071516)` → AccountServerId=4；
  `Config/sessions.json` 里的 `Token` 是管理端会话，**不能**当 `SessionKey.MxToken` 用（会返回 `ErrorCode:3`）。
- 本次**未**恢复 Item_List 转发（`cn_4000.txt` 仍为 1，桥仍是 `af1bc9a5`），按指示等出口过滤先上。
