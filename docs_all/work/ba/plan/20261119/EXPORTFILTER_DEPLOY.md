# BAPATCH-EXPORTFILTER v1 部署记录（出口道具过滤）

- 时间：2026-11-19 00:48（Asia/Shanghai）
- 执行：srv-ops ｜ 服务器：root@<SERVER_IP>
- 结论：**PASS，线上逐字节零变化**。过滤已启用（加载 1803 个客户端可解析 id），
  `/api/item/list`、`Account_LoginSync`、`Shop_List` 三条响应字节数与内容 hash **与部署前完全一致**。

## 1. 改动内容

| 文件 | 改前 | 改后 |
|---|---|---|
| `/www/wwwroot/ba_srv/Shittim-Server.dll` | `e90867e2…`（2,680,320 B，Shop_List NRE 修复版） | **`63ca8f34694f65420c5dff4ec0822192386407162c9ca38d2b326c65d434789f`（2,687,488 B）** |
| `/www/wwwroot/ba_srv/Resources/ClientItemIds.txt` | **不存在** | **`48af0fd945fbd2dfaca0afa022b9cafb7095514bfd578b85a09dca17bbeb5ac6`（12,659 B）** |
| `Schale.dll` | `b06f4609…` | **未替换**（与构建产物一致） |

`ClientItemIds.txt` 统计：总 1,831 行 = **28 行注释/空行 + 1,803 个 id**（与预期一致）。

部署方式：两个文件均 `.new` 上传 → 校验 sha256（+ DLL 字节数 2,687,488）→ `mv -f`；
`systemctl restart ba-shittim`，5000 就绪 **5,102 ms**（轮询），新 pid **2790312**，5100 随后 1 s 就绪。

## 2. 验收

### ① 线上文件
```
63ca8f34694f65420c5dff4ec0822192386407162c9ca38d2b326c65d434789f  /www/wwwroot/ba_srv/Shittim-Server.dll
48af0fd945fbd2dfaca0afa022b9cafb7095514bfd578b85a09dca17bbeb5ac6  /www/wwwroot/ba_srv/Resources/ClientItemIds.txt
-rw-r--r-- 1 root root   12659 Nov 19 00:48 /www/wwwroot/ba_srv/Resources/ClientItemIds.txt
-rw-r--r-- 1 root root 2687488 Nov 19 00:48 /www/wwwroot/ba_srv/Shittim-Server.dll
```

### ② 启动日志：过滤已启用（在 tmux 控制台，不在 log.txt）
```
[ClientItemFilter] loaded 1803 client item id(s) from /www/wwwroot/ba_srv/Resources/ClientItemIds.txt; item export filter is ON
```
```
grep -ic 'export filter disabled' logs/log.txt → 0  （**没有** disabled）
grep -inE 'ClientItemIds|export ?filter' logs/log.txt → 无命中
⇒ 说明：该行只打到 **tmux 控制台（stdout）**，不进 Serilog 的 log.txt。
   log.txt 仍是 29 行的标准启动段（Starting Game Server → Application started），无新增告警。
```

### ③ `/api/item/list` —— **与改前逐字节一致**
| | 改前（00:47） | 改后（00:48） |
|---|---|---|
| HTTP | 200 | 200 |
| **字节数** | **3,611** | **3,611** |
| `ItemDBs` 条数 | **53** | **53** |
| `ExpiryItemDBs` | 0 | 0 |
| ItemDBs 内容 sha256 | `b4cd257e2952060b58aa28745a115a549deb27e0bd1dd2ed12b199546e2e8325` | **同一值** |

（`3,611 B` 是**网关层**真实响应；桥的 `/api/item/list` 仍是 620 B 桩，因为 `cn_4000.txt` = 1 —— 按你的指示未恢复转发。）

### ④ `Account_LoginSync` —— 一致
```
改前 585,078 B ｜ 改后 585,078 B ｜ HTTP 200 ｜ protocol='Account_LoginSync'
```

### ⑤ `Shop_List`（11 分类）—— 一致
```
改前 205,826 B ｜ 改后 205,826 B ｜ HTTP 200
ShopInfos = 8 个分类 ｜ 商品条目 = 1,900
ShopInfos 内容 sha256 = dbda45b2bde5254e2f23f61795441ae450b54dab6049ca7f5e40d2141cb20155（改前后同值）
```

### ⑥ 服务 / 端口
```
systemctl is-active ba-shittim → active
5000 → dotnet pid 2790312 ｜ 5100 → dotnet pid 2790312 ｜ 9097 → python3 pid 2787446
```

### ⑦ 未动项实测
```
GachaRecruitBanners.cn.json = 3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77（40,739 B / 529 条）
桥 account_auth_probe.py md5 = af1bc9a5517a6150546abf0b4a0ce57f
cn_4000.txt = 1
/root/shittim.sqlite3、ExcelDB.db、nginx 均未触碰
```

## 3. 回滚

```
备份目录：/root/EXPORTFILTER_20261119_004819/
   Shittim-Server.dll（e90867e2… / 2,680,320 B）
   BEFORE.sha256
   ROLLBACK.sh   ← 恢复 DLL + 删除 Resources/ClientItemIds.txt + 重启 + 轮询
```

一键回滚：
```bash
bash /root/EXPORTFILTER_20261119_004819/ROLLBACK.sh
```

## 4. 备注

- 过滤规则：`ClientItemIds.txt` 列出客户端 `ItemDBSchema.Id` 全集（1803 个）；
  凡不在表内的 id 会在出口被扣掉 —— 覆盖 `Item_List`、
  `Account_LoginSync.ItemListResponse.ItemDBs/ExpiryItemDBs`、以及所有 `ParcelResultDB.ItemDBs`。
- 「零变化」符合预期：库里已经不存在非法 id（`90070000` 已于 00:32 删除），
  53 件道具全部在 1803 白名单内 ⇒ 输出与过滤前逐字节相同。
- 语义变化只在**出现脏 id 时**才可见：届时它会「消失」而不是「让客户端整包解析失败」。
- 本次**未**恢复 Item_List 转发（`cn_4000.txt` 仍为 1，桥仍是 `af1bc9a5`）。
