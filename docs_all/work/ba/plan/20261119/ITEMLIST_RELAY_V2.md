# Item_List(4000) 转发恢复 —— ITEMLIST-4000 v2

- 时间：2026-11-19 00:49（Asia/Shanghai）
- 执行：srv-ops ｜ 服务器：root@<SERVER_IP>
- 结论：**PASS**。`POST /api/item/list` 经桥返回 **5,016 B / 53 件真实道具**（含 6400/6998/11000001，不含 90070000），
  `Account_LoginSync` 经桥 200 / 780,312 B。

## 1. 两个改动（必须一起回滚）

| # | 文件 | 改前 | 改后 |
|---|---|---|---|
| ① | `/www/wwwroot/bapatch/tools/account_auth_probe.py` | md5 `af1bc9a5517a6150546abf0b4a0ce57f`（222,486 B） | md5 **`da07749d63487ce28ce8d571853b037f`**（222,539 B） |
| ② | `/www/wwwroot/bapatch/tools/cn_4000.txt` | `1`（md5 `b026324c6904b2a9cb4b88d6d61c81d1`） | **`0`** |

改动点（与 v1 相同、单处、最小）：
```
5103: RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1017,   # FIX-2: 1005 已移出，改走转发
5104-                          24000, 26000, 90004,   # ITEMLIST-4000 v2: 4000 移出排除表，改走 relay2
5105-                          90011))   # BAPATCH-90011 v1: Shop_ListTutorialGacha (no Shittim enum/handler)
```
替换前校验：目标片段 `24000, 26000, 4000, 90004,` **出现次数 = 1**（不唯一则拒绝修改）；改后 `py_compile` 通过。

桥重启：kill 旧 pid 2787446 → `cd /www/wwwroot/bapatch/tools` + `umask 007` + `setsid nohup` 启动，
**9097 就绪 1,010 ms**，新 pid **2790794**，实例数 **1**。

## 2. 验收

### ① `RL2_HANDLED` 已不含 4000
```
5103:RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1017,   # FIX-2: 1005 已移出，改走转发
5104-                         24000, 26000, 90004,   # ITEMLIST-4000 v2: 4000 移出排除表，改走 relay2
5105-                         90011))   # BAPATCH-90011 v1: Shop_ListTutorialGacha (no Shittim enum/handler)
```

### ② `cn_4000.txt`
```
0
```

### ③ 桥进程 / 端口 / 实例
```
9097_UP 耗时 = 1,010 ms ｜ pid = 2790794 ｜ 实例数 = 1
LISTEN 127.0.0.1:9097
```

### ④ `/api/item/list` 经桥（真实数据）
```
POST http://127.0.0.1:9097/api/item/list
HTTP 200  **5,016 B**（不再是 620 B 桩）
outer.protocol = 'Item_List'
inner.keys = ['Protocol','ItemDBs','ExpiryItemDBs','ServerTimeTicks','ServerNotification','RequestId']
**ItemDBs 条数 = 53**
  UniqueId=6400      StackCount=100
  UniqueId=6998      StackCount=100
  UniqueId=11000001  StackCount=10
前 5 条 = [{"Type":4,"ServerId":23,"UniqueId":2,"StackCount":5},{"Type":4,"ServerId":24,"UniqueId":3,"StackCount":18},
           {"Type":4,"ServerId":25,"UniqueId":11,"StackCount":414},{"Type":4,"ServerId":26,"UniqueId":40000,"StackCount":55},
           {"Type":4,"ServerId":27,"UniqueId":7,"StackCount":20}]
结论：PASS（真数据）｜ 不含 90070000
（桥包 5,016 B ＞ 网关裸包 3,611 B，因为桥走的是 CN 信封 + 完整 inner 键集合）
```

### ⑤ `Account_LoginSync` 经桥
```
HTTP 200 ｜ **780,312 B** ｜ outer='Account_LoginSync'
（网关裸包 585,078 B；桥信封后 780,312 B，与历史经桥值 777,816 B 同量级）
```

### ⑥ 未动项实测
```
Shittim-Server.dll        = 63ca8f34694f65420c5dff4ec0822192386407162c9ca38d2b326c65d434789f  ✅
Resources/ClientItemIds.txt = 48af0fd945fbd2dfaca0afa022b9cafb7095514bfd578b85a09dca17bbeb5ac6  ✅
GachaRecruitBanners.cn.json = 3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77  ✅
Items 行数：AccountServerId=4 → **53** ｜ AccountServerId=2 → **32**  ✅
Items 里 UniqueId=90070000 行数 = **0**  ✅
```

## 3. 回滚（两处一起）

```
备份目录：/root/ITEMLIST2_20261119_004912/
   account_auth_probe.py（af1bc9a5…）
   cn_4000.txt（内容 1）
   BEFORE.md5
   ROLLBACK.sh   ← 恢复两个文件 + 重启桥（cd tools + umask 007 + 端口轮询）
```

一键回滚：
```bash
bash /root/ITEMLIST2_20261119_004912/ROLLBACK.sh
```
回滚后期望：桥 md5 = `af1bc9a5…`、`cn_4000.txt` = `1`、`/api/item/list` 回到 620 B 桩。

## 4. 备注

- 现在链路：客户端 → 桥 9097（relay2 转发 4000）→ Shittim 5000 → 出口过滤（ClientItemIds 1803）→ 桥 CN 信封 → 客户端。
  背包里若再出现客户端不认识的 id，会被过滤掉而不是让整包解析失败。
- 桥侧开关是**每请求现读**，`cn_4000.txt` 生效不需要再重启；但 `RL2_HANDLED` 属代码常量，改动后必须重启（本次已重启）。
- 卡池清单未动（仍 529 条 / `3ac8385d…`），等用户重登确认。
