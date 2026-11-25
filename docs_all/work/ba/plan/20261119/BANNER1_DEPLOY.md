# 卡池清单切 1 条实验（BANNER1）——部署与验证

- 时间：2026-11-19 01:39–01:41（Asia/Shanghai）｜ 执行：srv-ops
- 目的：判定「招募界面的页签是否由我们下发的卡池清单决定」——把 529 条压成 1 条 `5004670`
- 结论：**已切换成 1 条卡池；10006 实测返回 1 条（Id=5004670），LoginSync 内嵌子包同样 1 条，登录链路正常。**

## 1. 真实路径（先确认，非猜测）

```
systemctl cat ba-shittim →
  WorkingDirectory=/www/wwwroot/ba_srv
  ExecStart=/usr/bin/tmux new-session -d -s shittim … "/root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2"
find /www/wwwroot -name 'GachaRecruitBanners.cn.json' →
  /www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json    （唯一一处）
```

## 2. 改前 / 改后

| | 改前 | 改后 |
|---|---|---|
| 字节数 | 40,739 | **98** |
| 条目数 | 529 | **1** |
| sha256 | `3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77` | **`7fbe8645d1b036beb7224e4af38f4d4f9bbaedb5c490ae53352fc58b56e11c9a`** |
| 写入方式 | — | `cat > *.new` → `python3 -c json.load` 校验 → `mv -f` |

新文件内容（schema 与要求一致，仅 `Id / From / To`）：
```json
[
  {
    "Id": 5004670,
    "From": "2026-11-12T14:00:00",
    "To": "2026-11-26T13:59:59"
  }
]
```
`json.load` 校验：`entries = 1 [{'Id': 5004670, 'From': '2026-11-12T14:00:00', 'To': '2026-11-26T13:59:59'}]`

## 3. 重启与端口轮询

```
systemctl restart ba-shittim
轮询（5000 与 5100 同时就绪才算过）→ **5000/5100_UP 耗时 6,141 ms**
新 pid = 2794452 ｜ systemctl is-active ba-shittim → active
```

## 4. 验证①：协议 10006（Shop_GachaRecruitList）

```
HTTP 200 ｜ raw = 388 B ｜ outer.protocol = 'Shop_GachaRecruitList'
前 100 字节：
b'{"protocol":"Shop_GachaRecruitList","packet":"{\\"Protocol\\":10006,\\"ShopRecruits\\":[{\\"Id\\":5004670,'

inner.keys = ['Protocol', 'ShopRecruits', 'ShopFreeRecruitHistoryDBs', 'ServerTimeTicks', 'ServerNotification']
**ShopRecruits 条数 = 1**
  {"Id": 5004670, "SalesStartDate": "2026-11-12T14:00:00", "SalesEndDate": "2026-11-26T13:59:59", "UpdateDate": "0001-01-01T00:00:00"}
结论：**PASS（1 条且 Id=5004670）**
```

## 5. 验证②：登录链路（LoginSync）

```
（说明：Shittim 侧 LoginSync 的协议号是 1019；CN 客户端的 1017 由桥 relay1017 映射成 1019，之前我用 1017 打到的是
  Account_DismissRepurchasablePopup，属正常现象。）

POST Protocol=1019 + SyncProtocols(25 项，含 10006)
HTTP 200 ｜ raw = **511,798 B** ｜ outer.protocol = 'Account_LoginSync'
inner.keys 数 = 32
子包 ShopGachaRecruitListResponse 键 = ['Protocol', 'ShopRecruits', 'ShopFreeRecruitHistoryDBs']
**ShopRecruits 条数 = 1**
  首条 = {"Id": 5004670, "SalesStartDate": "2026-11-12T14:00:00", "SalesEndDate": "2026-11-26T13:59:59", "UpdateDate": "0001-01-01T00:00:00"}
⇒ 登录链路 200、大小正常（比 529 条时的 ~585–728 KB 小，符合"少 528 条"的预期）
```

### 5.1 实验结论：**阴性（否定证据）** —— 2026-11-19 01:43 记录

**用户真机反馈（在下发只有 1 条 `5004670` 的状态下）：**
```
看到的是「新手冲刺一 / 新手冲刺二 / 3★自选招募 / 一堆 DUMMY」
⇒ 页签数量没有变成 1，反而多了一个
```
**结论：招募界面的页签不是由 `ShopRecruits`（`GachaRecruitBanners.cn.json` → LoginSync 子包 / 10006）驱动的。**
（本清单只影响"每个页签内的卡池内容/时间"，不决定页签集合。）

**回滚执行（`/root/BANNER1_20261119_013953/ROLLBACK.sh`，exit=0）：**
```
restored sha256: 3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77
5000/5100_UP after 7s
```

**回滚后校验值（2026-11-19 01:43:15）：**
| 项 | 实测 |
|---|---|
| 文件 | `-rw-r--r-- 1 root root 40739 Nov 18 22:24 /www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json` |
| sha256 | `3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77` ✅（与改前一致） |
| 条目数 | **529** ✅ |
| ba-shittim | `active`，新 pid **2795210**，5000/5100 均在听 |
| 10006 实测 | HTTP 200 ｜ **74,314 B** ｜ **ShopRecruits = 529** ｜ 首条 `{"Id":5000000,"SalesStartDate":"2023-08-03T05:00:00",…}` |
| LoginSync(1019) 实测 | HTTP 200 ｜ **585,725 B** ｜ 子包 `ShopRecruits = 529` ✅ |

**注意（需知道）**：`ROLLBACK.sh` 用的是 `mv -f`，所以
`/root/BANNER1_20261119_013953/GachaRecruitBanners.cn.json` **已被移回原位、备份目录里不再有该文件**；
目录里仍保留 `BEFORE.sha256`（记录改前 sha256 `3ac8385d…`）与 `ROLLBACK.sh`。
文件本体已在线上恢复，sha256 与改前完全一致，无需再从备份目录取。

## 6. 备份与回滚

```
备份目录：/root/BANNER1_20261119_013953/
   GachaRecruitBanners.cn.json（原 40,739 B / 3ac8385d…）
   BEFORE.sha256
   ROLLBACK.sh
```

**ROLLBACK.sh 完整路径：**
```
/root/BANNER1_20261119_013953/ROLLBACK.sh
```
其逻辑：`mv -f` 备份文件回原位 → `systemctl restart ba-shittim` → 轮询 5000 与 5100 最多 30 秒 → 打印恢复后的 sha256。

## 7. 未触碰

代码 / DLL（`63ca8f34…`）/ `ClientItemIds.txt` / `shittim.sqlite3` / nginx / 桥 9097 —— **全部未动**。

## 8. 给真机测试的预期

- 客户端重新登录（或强杀重进）后，招募页应只看到 **1 个页签**（若页面数量确实由本清单驱动）。
- 若仍然是 3 个页签 → **说明页签来源不是这份清单**（可能是客户端本地 Excel 或别的服务端字段），本次实验即为否定证据。
