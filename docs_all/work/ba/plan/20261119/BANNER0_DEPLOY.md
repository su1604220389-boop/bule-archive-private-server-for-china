# BANNER0 实验：把卡池清单改成空数组（结果：**前提不成立，已回滚**）

- 时间：2026-11-19 01:56–01:57（Asia/Shanghai）｜ 执行：srv-ops
- 目的：验证「我们下发的 529 条卡池数据本身是否在干扰客户端」——原计划让 `ShopRecruits` 变成 **0 条**
- **结论：把 JSON 改成 `[]` 之后，服务端并没有下发 0 条，而是回落到它自带的 Excel 数据，下发了 714 条（Id 段 9005xxxx）。**
  即"服务端不下发卡池清单"这个状态，**无法通过清空这个文件达成** ⇒ 实验前提不成立，**已立即回滚到 529 条**。

## 1. 文件变更

| | 内容 | 字节 | sha256 |
|---|---|---|---|
| 改前 | 529 条 | 40,739 | `3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77` |
| 改后 | `[]` | **3** | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| 回滚后 | 529 条 | 40,739 | `3ac8385d…`（与改前一致）✅ |

写入方式：`printf '[]\n' > *.new` → `json.load` 校验（entries = 0）→ `sha256sum` → `mv -f`。

## 2. 重启

```
systemctl restart ba-shittim ｜ 5000/5100 同时就绪 **8,151 ms** ｜ 新 pid 2798049 ｜ active
（服务端未报错、未启动失败）
```

## 3. 验收实际值（与预期不符，这是关键发现）

**① 协议 10006（改后）**
```
HTTP 200 ｜ raw = 101,012 B ｜ outer.protocol = 'Shop_GachaRecruitList'
前 100 字节：b'{"protocol":"Shop_GachaRecruitList","packet":"{\\"Protocol\\":10006,\\"ShopRecruits\\":[{\\"Id\\":90050002'
inner.keys = ['Protocol','ShopRecruits','ShopFreeRecruitHistoryDBs','ServerTimeTicks','SessionKey','AccountId']
**ShopRecruits 条数 = 714**（预期 0）
  前 3 条 = {"Id":90050002,"SalesStartDate":"2021-11-09T00:00:00","SalesEndDate":"2021-11-16T12:00:00"}
           {"Id":90050003,…,"SalesStartDate":"2021-11-09T00:00:00",…}
           {"Id":90050004,…,"SalesStartDate":"2021-11-16T12:30:00",…}
```

**② LoginSync（1019）**
```
HTTP 200 ｜ raw = 613,429 B（体积正常）｜ outer = 'Account_LoginSync' ｜ inner 键数 33
内嵌子包 ShopGachaRecruitListResponse.ShopRecruits = **714**
首条 = {"Id":90050002,"SalesStartDate":"2021-11-09T00:00:00","SalesEndDate":"2021-11-16T12:00:00"}
```

**③ 日志**
```
01:56 之后 Exception / NullReference / Error Response / [ERR] → 0 条
log.txt 尾部全是正常的 200 记录（含真实客户端 LoginSync 200 / 1,738 ms）
```

## 4. 这个结果说明什么（重要）

1. `Data/GachaRecruitBanners.cn.json` 是**覆盖/补充表**，不是唯一来源：
   - 文件有 529 条 → 响应 529 条；
   - 文件有 1 条 → 响应 1 条（BANNER1 实验）；
   - 文件为 `[]` → 响应 **714 条**（回落到服务端自带 Excel 数据，Id 段 900500xx，2021 年档期）。
2. 所以"**服务端不下发任何卡池清单**"这一状态，**在本版本代码里不可达**（除非改代码）。
   这也意味着：**BANNER1（只发 1 条）实验里"页签没变"的结论依然成立**，
   但 BANNER0 想验证的"完全不下发"没法用改数据的方式做。
3. 714 条本身是**服务端 Excel 里的历史档期**（2021 年），不是我们 529 条；如果让客户端拿这份数据，页签数量/内容会再变一次（未验证）。

## 5. 处理决定与回滚

- 因为「0 条」这个实验前提不成立，且线上不应停留在未获批准的新状态（714 条），**已立即执行回滚**。
- 回滚结果：
```
restored sha256: 3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77
5000/5100_UP after 6s
文件 = 40,739 B / 529 条 ｜ ba-shittim active（pid 2798358）｜ 5000/5100 均在听
```

## 6. 回滚脚本路径

```
/root/BANNER0_20261119_015658/ROLLBACK.sh
```
备份目录内容：`GachaRecruitBanners.cn.json`（已被 mv 回原位，故目录内只剩）、`BEFORE.sha256`、`ROLLBACK.sh`。

## 7. 未触碰

代码 / DLL（`160c3e15…`）/ `ClientItemIds.txt` / 数据库 / nginx / 桥（`da07749d…`）—— 全部未动。

## 8. 给后续的可选实验（需另行下令）

- 若想验证"完全不下发"，必须**改代码**（让 `ShopGachaRecruitListResponse.ShopRecruits` 直接空数组且不回落到 Excel）。
- 或者：保留 529 条/1 条/714 条三态，直接让真机看页签差异（714 条未经真机验证）。
