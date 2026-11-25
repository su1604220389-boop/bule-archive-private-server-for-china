# 卡池清单收敛到 5 个（GachaRecruitBanners.cn.json）部署记录

- 时间：2026-11-19 00:17–00:20（Asia/Shanghai）
- 执行：srv-ops ｜ 服务器：root@<SERVER_IP>
- 结论：**PASS**。客户端实际收到的 `Shop_GachaRecruitList`（协议 **10006**）现在返回 **5 条**，Id 与目标逐一对齐；
  文件 480 B / sha256 与期望完全一致；DLL 未变；服务 active、5000/5100 均在听。

## 1. 改动（只动一个数据文件）

| 项 | 内容 |
|---|---|
| 文件 | `/www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json` |
| 改前 | **40,739 B**，529 条，sha256 `3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77` |
| 改后 | **480 B**，5 条，sha256 `ed3a3d867517f90b4cac97cfc4d39045bed38f8c36fa80ac280324708da54834` |
| 方式 | 上传 `.new` → 校验字节数 + sha256 → `mv -f` 替换（未直接覆盖） |
| 生效 | `systemctl restart ba-shittim`（该文件启动时加载），5000 端口 **6,169 ms** 就绪，新 pid 2784057 |

内容（`indent=2`，结尾一个 LF 换行，尾字节实测 `]\n`）：
```json
[
  { "Id": 5004660,  "From": "2026-11-12T14:00:00", "To": "2026-11-26T13:59:59" },
  { "Id": 7000001,  "From": "2025-08-14T14:00:00", "To": "2099-12-31T03:59:59" },
  { "Id": 8000004,  "From": "2026-09-24T14:00:00", "To": "2027-06-10T13:59:59" },
  { "Id": 90000000, "From": "2026-07-16T10:00:00", "To": "2099-12-31T03:59:59" },
  { "Id": 99999999, "From": "2024-08-01T14:00:00", "To": "2099-12-31T03:59:59" }
]
```

## 2. 验收①：文件
```
$ ls -l /www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json
-rw-r--r-- 1 root root 480 Nov 19 00:17 …/GachaRecruitBanners.cn.json
$ sha256sum 同上
ed3a3d867517f90b4cac97cfc4d39045bed38f8c36fa80ac280324708da54834
$ python3 -c 'json.load(...)' → entries = 5 [5004660, 7000001, 8000004, 90000000, 99999999]
```

## 3. 验收②：**客户端真正拿到的列表 = 5**（这条与原计划的接口不同，见 §4）

`GachaRecruitBanners.cn.json` 的消费方是 `ShopHandler.GachaRecruitList`（DLL 里
`BuildRecruitBanners` + 字符串 `GachaRecruitBanners.cn.json`），协议号 **10006**，
客户端路径 `POST /api/shop/gacharecruitlist`（经桥 9097 转发到 Shittim 5000）。

探测结果（`/tmp/924_gacha_final_verify.py`，真实 CN 信封请求）：
```
POST /api/shop/gacharecruitlist  (protocol=Shop_GachaRecruitList num=10006)
  HTTP 200  1472 B
  outer.protocol = 'Shop_GachaRecruitList'
  inner.keys = ['Protocol','ShopRecruits','ShopFreeRecruitHistoryDBs','ServerTimeTicks','ServerNotification','RequestId']
  **ShopRecruits 条数 = 5**
    {"Id":5004660,  "SalesStartDate":"2026-11-12T14:00:00", "SalesEndDate":"2026-11-26T13:59:59"}
    {"Id":7000001,  "SalesStartDate":"2025-08-14T14:00:00", "SalesEndDate":"2099-12-31T03:59:59"}
    {"Id":8000004,  "SalesStartDate":"2026-09-24T14:00:00", "SalesEndDate":"2027-06-10T13:59:59"}
    {"Id":90000000, "SalesStartDate":"2026-07-16T10:00:00", "SalesEndDate":"2099-12-31T03:59:59"}
    {"Id":99999999, "SalesStartDate":"2024-08-01T14:00:00", "SalesEndDate":"2099-12-31T03:59:59"}
  Id 集合与期望一致 = True ｜ 多余 = ∅ ｜ 缺失 = ∅
```
⇒ 时间字段在响应里叫 `SalesStartDate` / `SalesEndDate`（**逐字保留了原 From/To 的值，未被改动**）。

## 4. ⚠ 与原验收项不符的地方（务必知会）

原任务写「`curl /api/admin/gacha/banners` → 长度必须是 5」。**实测该接口返回 717 条**，与本次文件无关：

```
$ curl -H "X-Admin-Key: <Config.json/ServerConfiguration/AdminApiKey>" \
       http://127.0.0.1:5000/api/admin/gacha/banners
HTTP 200  159,477 B   → 717 条
条目形状 = {"id":90070000,"displayOrder":1,"bannerPath":"uis/00_images/banner/Event_Banner_70000",
            "saleFrom":"2022-09-06 04:00:00","saleTo":"2024-07-23 10:59:59","isNewbie":true,…}
```

原因：`/api/admin/gacha/banners` 是**管理端视图**（读 ExcelDB 的 `GachaRecruitBannerExcels` + 手工 patch），
**不经过** `BuildRecruitBanners`；而客户端卡池列表走的是协议 10006 的 `ShopRecruits`。
所以「长度 5」只能在**客户端协议**上验证 —— 见 §3，已实测 5 条。
（AdminApiKey 未在报告里明文，来源：`/www/wwwroot/ba_srv/Config/Config.json` → `ServerConfiguration.AdminApiKey`）

## 5. 验收③④：DLL 与服务
```
$ sha256sum /www/wwwroot/ba_srv/Shittim-Server.dll
2a98a2b36280784e9ff0323fa4ab54c5adaab949e4b1c23e729f80d675ea7e8d   （改前改后一致）

$ systemctl is-active ba-shittim → active
$ ss -lntp | grep -E ':(5000|5100)\b'
LISTEN 0 512 0.0.0.0:5000 … users:(("dotnet",pid=2784057,fd=343))
LISTEN 0 512 0.0.0.0:5100 … users:(("dotnet",pid=2784057,fd=344))
```

## 6. 回滚

```
备份目录：/root/GACHACLEAN5_20261119_001751/
   GachaRecruitBanners.cn.json        （改前 40,739 B / 3ac8385d…）
   BEFORE.sha256 / AFTER.sha256
   ROLLBACK.sh
```

一键回滚：
```bash
bash /root/GACHACLEAN5_20261119_001751/ROLLBACK.sh
```
手工回滚：
```bash
cp -a /root/GACHACLEAN5_20261119_001751/GachaRecruitBanners.cn.json \
      /www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json
systemctl restart ba-shittim
for i in $(seq 1 30); do ss -lnt | grep -q ':5000' && { echo "5000_UP ${i}s"; break; }; sleep 1; done
```

## 7. 未触碰
`shittim.sqlite3` / `BlueArchive.db`（含 ExcelDB）｜`Shittim-Server.dll`｜`ExcelDB.db`｜nginx｜桥 9097（未重启）。

## 8. 观察（不在本次范围，供后续）
- Shittim 启动日志有 `[WRN] Client banner auto-patch enabled but client ExcelDB.db was not found ()`
  —— 这是「自动给**客户端** ExcelDB 打补丁」的开关，与本次服务端下发无关；如后续要改客户端图表需另配路径。
- 收起的 524 个卡池里若有**已在进行中**的复刻活动（如 5004670 美咲泳装），收敛后客户端不再展示该页签；
  这是用户明确选择的取舍（宁可少不可错）。
