# P0 抽卡概率可配置化 —— C# 侧部署与验证

- 时间：2026-11-19 02:46–02:47（Asia/Shanghai）｜ 执行：srv-ops
- 产物：`_build_p0rates/Shittim-Server.dll` + `Data/gacha_rates.defaults.json`
- **最终判定：部署成功 · 全部验证通过 · KEEP（保留新版本）**

## 1. 新旧对比

| 文件 | 改前 | 改后 |
|---|---|---|
| `/www/wwwroot/ba_srv/Shittim-Server.dll` | `160c3e15…` / 2,688,000 B | **`c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa` / 2,727,424 B** |
| `/www/wwwroot/ba_srv/Data/gacha_rates.defaults.json` | **不存在** | **新增**，`59bbf27d738daa74f0693e53f8074ecefd469bdbaf5b5282aadf4d1d9e9b2aad` / 312 B |

- 本地构建件与上传件 sha256/字节数**逐项校验一致**；线上基线核对为 `160c3e15…` 后才替换。
- **只替换这一个 DLL + 新增这一个 json**；其它 68 个 DLL 未动（未整目录覆盖）。
- 部署前确认 `Data/gacha_rates.defaults.json`、`Data/gacha_rates.json`、`/www/wwwroot/gacha_config.json` **三者均不存在**。

## 2. 备份 + 回滚

```
备份目录：/root/P0RATES_20261119_024640/
   Shittim-Server.dll   （改前 160c3e15… / 2,688,000 B）
   BEFORE.txt           （sha256 + 字节数）
   ROLLBACK.sh
```

**ROLLBACK.sh 完整路径：**
```
/root/P0RATES_20261119_024640/ROLLBACK.sh
```
逻辑：还原旧 DLL → 删除 `Data/gacha_rates.defaults.json`、`Data/gacha_rates.json`、`Data/gacha_rates.backup.*.json`
→ `systemctl restart ba-shittim` → 轮询 5000/5100 ≤30s → 打印恢复后 sha256。

## 3. 重启

```
systemctl restart ba-shittim ｜ 5000/5100 同时就绪 **6,147 ms** ｜ 新 pid 2,803,354 ｜ active
```

## 4. 验证 ①：启动日志（`[GachaRates] boot`）

```
2026-11-19 02:46:42.212 [INF] [GachaRates] boot: override file absent, defaults=/www/wwwroot/ba_srv/Data/gacha_rates.defaults.json, isDefault=true
2026-11-19 02:46:42.216 [INF] [GachaRates] boot Normal: upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185
2026-11-19 02:46:42.216 [INF] [GachaRates] boot Pickup: upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185
2026-11-19 02:46:42.217 [INF] [GachaRates] boot Limited: upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185
2026-11-19 02:46:42.217 [INF] [GachaRates] boot Fes: upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185
```
（tmux 控制台同样打印，大小写为 `isDefault=True`。）

## 5. 验证 ②：`GET /api/admin/gacha/rates`

```
HTTP 200
响应前 200 字符：
{"ok":true,"rates":{"Normal":{"ssrThreshold":30,"srRate":185},
 "Pickup":{"upSsrRate":7,"ssrThreshold":23,"srRate":185},
 "Limited":{"upSsrRate":7,"ssrThreshold":23,"srRate":185},
 "Fes":{"upSsrRate":7,"fes…

字段级：
  ok                    = True
  isDefault             = True          ✅
  legacyOverrideActive  = False         ✅
  overrideFileExists    = False
  version=1 ｜ updatedAt=null ｜ warnings=[] ｜ lastError=null ｜ sourceIp=127.0.0.1

rates：
  Normal  {"ssrThreshold": 30, "srRate": 185}                       ✅
  Pickup  {"upSsrRate": 7, "ssrThreshold": 23, "srRate": 185}       ✅
  Limited {"upSsrRate": 7, "ssrThreshold": 23, "srRate": 185}       ✅
  Fes     {"upSsrRate": 7, "fesSsrRate": 9, "ssrThreshold": 44, "srRate": 185}  ✅
```
响应完整键集合（20 个）：
```
ok, rates, defaults, isDefault, version, updatedAt, filePath, defaultsFilePath,
overrideFileExists, overrideFileValid, lastError, warnings, legacyOverrideActive,
legacyOverridePath, groupMapping, backupFile, changed, resetScope, overrideFileDeleted, sourceIp
```

## 6. 验证 ③：热加载（关键，不改实际出率）

### 6.1 `POST /api/admin/gacha/rates`（把 GET 到的 rates 原样回填）
```
HTTP 200
字段：ok=true ｜ isDefault=**true** ｜ changed=**[]** ｜ overrideFileExists=**true**
      overrideFileDeleted=false ｜ updatedAt=2026-11-18T18:47:11.2262332Z ｜ lastError=null ｜ warnings=[]
文件变化：Data/ 下 **新增 `gacha_rates.json`**（覆盖配置文件被写出）
```
> ⚠ **与预期不同**：因为回填的值**与默认值完全相同**，接口把 `isDefault` 判为 **true**、`changed=[]`（空数组）。
> 即 `isDefault` 的语义是「当前速率 == 默认速率」，**不是**「是否存在覆盖文件」。
> `overrideFileExists=true` 才反映覆盖文件已生成 —— **热加载链路本身已验证成功**（文件被写出 + 读取生效）。

### 6.2 POST 之后再 GET（值不变）
```
HTTP 200 ｜ ok=true ｜ isDefault=true ｜ overrideFileExists=true ｜ updatedAt 同上
rates 与 POST 前完全相同 = **True**
  Normal {"ssrThreshold":30,"srRate":185}
  Pickup {"upSsrRate":7,"ssrThreshold":23,"srRate":185}
  Fes    {"upSsrRate":7,"fesSsrRate":9,"ssrThreshold":44,"srRate":185}
⇒ **实际出率零变化** ✅
```

### 6.3 `POST /api/admin/gacha/rates/reset` `{"scope":"all"}`
```
HTTP 200
字段：ok=true ｜ isDefault=true ｜ resetScope="all" ｜ overrideFileDeleted=**true** ｜ overrideFileExists=false
      changed=["all groups -> defaults (Normal{upSsrRate=0, fesSsrRate=0, ssrThreshold=30, srRate=185}
               Pickup{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185}
               Limited{upSsrRate=7, fesSsrRate=0, ssrThreshold=23, srRate=185}
               Fes{upSsrRate=7, fesSsrRate=9, ssrThreshold=44, srRate=185})"]
      backupFile="/www/wwwroot/ba_srv/Data/gacha_rates.backup.20261119_024711_231.json"
```
**reset 后 GET**：`HTTP 200 ｜ ok=true ｜ isDefault=true ｜ overrideFileExists=false ｜ updatedAt=null` ✅

### 6.4 测试产生的文件（当前 Data/ 下）
```
gacha_rates.defaults.json                        312 B  （本次部署的产品）
gacha_rates.backup.20261119_024700_114.json      399 B  （第一次 POST 时生成）
gacha_rates.backup.20261119_024711_231.json      399 B  （reset 时生成）
gacha_rates.json                                 —— 已被 reset 删除（overrideFileDeleted=true）
```
> 这两个 `backup.*.json` 是 API 自己写的；`ROLLBACK.sh` 会一并清理。需要我现在删掉它们的话请示下。

## 7. 验证 ④：回归

```
Account_Auth(1002)：HTTP 200 ｜ 含 SessionKey ｜ 无 ErrorCode
LoginSync(1019)   ：HTTP 200 ｜ **587,104 B** ｜ ShopRecruits = **529 条**
Mail_Check(7001)  ：HTTP 200 ｜ ServerNotification = 8
90004             ：HTTP 200 ｜ 14,060 B ｜ 顶层键 = [Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, **Data**]
                    Banners=7 ｜ Notices=6 ｜ Events=14 ｜ GachaProbabilityDisplay=12  ✅
```

## 8. 验证 ⑤：日志

```
02:46:40 之后 Exception / NullReference / [ERR] / Error Response 行数 = **0**
log.txt 尾部：正常 200 记录（LoginSync 200 / 1,728 ms、Mail_Check 200）
```

## 9. 验证 ⑥：旧覆盖通道

```
ls /www/wwwroot/gacha_config.json → **No such file or directory**（仍不存在）✅
```

## 10. 结论与备注

1. 三个 API 全部 200，`ok:true`；默认速率与要求逐项一致；热加载写文件成功（`gacha_rates.json` 生成后被 reset 删除）。
2. **唯一与预期不同的一点**：POST 相同值时 `isDefault` 返回 `true`（而非 false）、`changed=[]`；
   说明该字段语义 =「当前值 == 默认值」，覆盖文件是否存在看 `overrideFileExists`。
   若要验证「isDefault 变 false」，需要 POST **与默认不同**的值（会改变实际出率，故本次未做）。
3. `legacyOverrideActive` 全程 `false`，`/www/wwwroot/gacha_config.json` 始终不存在 ⇒ 新旧两条通道不冲突。
4. 回滚点齐备：`/root/P0RATES_20261119_024640/ROLLBACK.sh`；另有全量备份 `/root/PRE_P0_20261119_023546`。
