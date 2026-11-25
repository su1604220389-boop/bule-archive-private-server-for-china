# Item_List（4000）从合成桩改为真实数据（relay2 转发）

- 时间：2026-11-18 23:57（Asia/Shanghai）
- 执行：srv-ops ｜ 服务器：root@<SERVER_IP>
- 结论：**PASS**。`POST /api/item/list` 从 640 B 固定桩 → **2,988 B / 30 件真实道具**（含 6400/6998/11000001 招募券），
  登录链路 loginsync 响应体大小改前改后**完全一致（777,816 B）**。

## 1. 根因

桥 `account_auth_probe.py` 里 `SIMPLE_PROTOCOLS = (1005, 4000, 26000)`，`cn_4000.txt=1` 让
`simple_wants(4000)` 命中（分发顺序：simple hook 在 relay2 hook **之前**，见 `:3775` vs `:3804`），
于是用 `simple_build(4000)` + `SIMPLE_INITIAL_ITEMS = ((4, 2, 5, True),)` 合成**永远是 1 件道具**的桩，
响应固定 640 B，**完全不读数据库**。

同时 relay2 的排除表 `RL2_HANDLED` 里含 `4000`（`assert` 见 `:5103-5105`），即使开关打开也不会转发。

⇒ 数据库里给账号发的招募券（`Items.UniqueId=6400/6998/11000001`）客户端完全看不到；4000 从未进过 Shittim。

## 2. 改动（单变量，两处，均最小）

| # | 文件 | 改动 | 前 | 后 |
|---|------|------|----|----|
| ① | `/www/wwwroot/bapatch/tools/account_auth_probe.py` | `RL2_HANDLED` 去掉 `4000` | `24000, 26000, 4000, 90004,` | `24000, 26000, 90004,   # ITEMLIST-4000 v1: 4000 移出排除表，改走 relay2` |
| ② | `/www/wwwroot/bapatch/tools/cn_4000.txt` | 内容 `1` → `0` | `1` | `0` |

未改：nginx、证书、Shittim DLL、数据库结构、其它任何协议。

### sha256 前后对比

```
# ① 桥
BEFORE  ba322fae0ed621e768ab6238f2fb66d0c8c8a8d6f97106e995c60e374ee7e1f3  account_auth_probe.py
AFTER   f4b28ececd892cb1d7552ce4a80b3508a0ca003eb480a0089631e28fd4085f24  account_auth_probe.py
（注意：该文件随后又被另有改动覆盖，当前线上 md5 为 6b5a770171f0f0dfcb08249b2381a22c —— 见 §7 说明）

# ② 开关
BEFORE  4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865  cn_4000.txt   ('1')
AFTER   5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9  cn_4000.txt   ('0')

# 其余 26 个 cn_*.txt 全部未变（diff 只报上述两项）
```

## 3. 验收①：`/api/item/list` 真数据

工具：`/tmp/verify_itemlist.py`（不依赖客户端，按客户端格式现造 CN 请求：`[u32][gzip][iv|ct|key]`，fragment 373 B，
token = `base32(md5("Item_List" utf-16-le))` = `DGOYM2RERJJ7JIGHWVF7UZ5XPA`）

**改前（23:56:59，同脚本）**
```
HTTP 200  **620 B**
outer.protocol = 'Item_List'
inner.keys = ['Protocol','SessionKey','ServerTimeTicks','ServerNotification','RequestId','ItemDBs','ExpiryItemDBs']
ItemDBs 条数 = 1
  前 1 条 = {"Type":4,"ServerId":420001,"UniqueId":2,"StackCount":5,"IsNew":true}
  6400 / 6998 / 11000001 = **缺失**
结论：FAIL（仍是桩）
```

**改后（23:57:18）**
```
HTTP 200  **2988 B**
outer.protocol = 'Item_List'
inner.keys = ['Protocol','ItemDBs','ExpiryItemDBs','ServerTimeTicks','ServerNotification','RequestId']
ItemDBs 条数 = 30
  UniqueId=6400      StackCount=100
  UniqueId=6998      StackCount=100
  UniqueId=11000001  StackCount=10
  前 5 条 = [{"Type":4,"ServerId":23,"UniqueId":2,"StackCount":5},{"Type":4,"ServerId":24,"UniqueId":3,"StackCount":18},
             {"Type":4,"ServerId":25,"UniqueId":11,"StackCount":414},{"Type":4,"ServerId":26,"UniqueId":40000,"StackCount":55},
             {"Type":4,"ServerId":27,"UniqueId":7,"StackCount":20}]
结论：PASS（真数据）
```

**与数据库一致（账号 ServerId=4）**
```
sqlite3 Items WHERE AccountServerId=4 → 30 行
  6400|100   6998|100   11000001|10
（响应里 30 条、三张券数量完全一致）
```

**桥日志（relay2 真正转发成功）**
```
23:56:59 /api/item/list | resp_len=640  | relay2_num=4000 | relay2_fallthrough=handled-4000   ← 改前：被排除表挡住
23:57:18 /api/item/list | resp_len=2988 | relay2_num=4000 | relay2_code=200 | relay2_resp_len=2096 ← 改后：Shittim 回包
```

## 4. 验收②：回归（改后 23:57:18-19）

```
/api/account/auth          Account_Auth         HTTP 200     3500 B
/api/account/loginsync     Account_LoginSync    HTTP 200   777816 B
/api/networktime/sync      NetworkTime_Sync     HTTP 200      620 B
/api/contentsave/get       ContentSave_Get      HTTP 200      620 B
回归结论：PASS
```

**loginsync 大小一致性（关键）**
```
改前真实客户端 22:38:09 → 749,528 B（首次登录，数据未满）
改前 22:43:24 → 777,024 B ｜ 22:57:43 → 777,196 B
改前 23:51:04 → **777,816 B**
改后 23:57:18 → **777,816 B**   ← 与改前最后一次完全一致
⇒ 登录链路未受影响
```

## 5. 回滚

```
备份目录：/root/BRIDGE_ITEMLIST_20261118_235716/
   account_auth_probe.py            （改前桥，sha256 ba322fae…）
   tools/cn_1005.txt  cn_26000.txt  cn_4000.txt（原值 '1'）
   bapatch/cn_*.txt                 （全部 26 个开关原值）
   BEFORE.sha256 / AFTER.sha256
   ROLLBACK.sh                      ← 一键回滚脚本
```

一键回滚（恢复文件 + 重启桥 + 端口轮询）：
```bash
bash /root/BRIDGE_ITEMLIST_20261118_235716/ROLLBACK.sh
```

手工回滚：
```bash
cp -a /root/BRIDGE_ITEMLIST_20261118_235716/account_auth_probe.py /www/wwwroot/bapatch/tools/account_auth_probe.py
cp -a /root/BRIDGE_ITEMLIST_20261118_235716/tools/cn_4000.txt    /www/wwwroot/bapatch/tools/cn_4000.txt
OLD=$(ss -lntp | grep 9097 | grep -oP 'pid=\K[0-9]+' | head -1); kill "$OLD"
for i in $(seq 1 20); do kill -0 "$OLD" 2>/dev/null || break; sleep 0.5; done
( umask 007; cd /www/wwwroot/bapatch/tools && setsid nohup python3 account_auth_probe.py >> bridge.restart.log 2>&1 & )
for i in $(seq 1 30); do ss -lnt | grep -q ':9097' && { echo "9097_UP ${i}s"; break; }; sleep 1; done
```
回滚后预期：`/api/item/list` 回到 640 B 桩、`cn_4000.txt`=1、`RL2_HANDLED` 含 4000。

## 6. 风险与注意

- `RL2_TIMEOUT = 8` 秒：4000 现在每个登录都会真打一次 Shittim（本地回环，实测 2,096 B 响应耗时 <20 ms）。
  若 Shittim 挂了，relay2 会 `gateway unreachable` 落回原路径（不 500），但客户端会看到桩包（640 B）——降级安全。
- `RL2_HANDLED` 里去掉了 4000，若 Shittim 侧 `Item_List` 处理器未来出问题，可直接回滚该文件恢复桩行为。
- `cn_1005.txt` / `cn_26000.txt` 仍为 1（1005/26000 仍走 simple 桩，本次未动）。
- 客户端侧下一次真实登录应看到 `/api/item/list` 由 640 B 变为约 3 KB（nginx 日志可验证）。

## 7. 后续（不在本次范围）

- 本文件此后又被「另有改动」覆盖（当前线上 md5 `6b5a770171f0f0dfcb08249b2381a22c`），
  本次 relaying 修复的 `RL2_HANDLED` 与 `cn_4000.txt=0` 仍然有效（改后验收数据即在该状态下取得）。
  若后续有新的桥版本，**必须把「4000 不在 RL2_HANDLED」与「cn_4000.txt=0」一起纳入版本基线**，否则会静默退回 640 B 桩。
