# 公益卡 / 付费卡 · PHP 侧实现报告

> 时间：2026-11-18 01:09（+08:00）
> 作用域：`work/ba/cardadmin_php/` + `cards` 表 ALTER 方案（**未执行**）
> 不碰：`sdkcard.py`（proto-analyst）、部署（srv-ops）、nginx/php.ini。
> 与 proto-analyst 已对齐：`last_used_at` = **epoch 秒整数**，SDK 只写 `cards.json`，PHP 反向合并。

---

## 0. 结论

| 交付 | 状态 |
|---|---|
| ALTER（幂等） | ✅ `_audit/alter_cards_cardtype.sql`（未执行，等 lead 批） |
| 新建页表单 + 联动 | ✅ 卡类型下拉 + 最大设备数；公益→置灰清零 |
| 编辑页 | ✅ kind **只读**，max_devices 可改、保存即生效 |
| 列表页「类型」列 | ✅ 公益/付费 + 「最多 N 台/不限」 |
| 同步链 | ✅ 导出 kind/max_devices/last_used_at（epoch），并反向合并 last_used_at |
| `php -l` | ✅ 25/25 产品文件通过（PHP 8.2.31） |
| 演练 | ✅ 3 类卡 + 遗留行 + last_used_at 反向合并，全部符合预期 |
| 部署 | ⏸ 未部署（清单见 §7） |
| 回滚 | `inc/helpers.php` / `inc/sync.php` 原件在 `_audit/FEATURE_CARDTYPE_orig/`；diff 见 `FEATURE_CARDTYPE_PHP.diff`（+179/−14）。两个页面为纯增量块，见 §2 行号 |

---

## 1. ALTER 语句（幂等，未执行）

文件：`work/ba/server/deploy/_audit/alter_cards_cardtype.sql`

```sql
-- kind
SET @has_kind := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cards' AND COLUMN_NAME='kind');
SET @sql := IF(@has_kind=0,
  'ALTER TABLE `cards` ADD COLUMN `kind` VARCHAR(8) NOT NULL DEFAULT ''paid''
     COMMENT ''free=公益 / paid=付费'' AFTER `bind_one`', 'DO 0');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- max_devices
SET @has_max := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cards' AND COLUMN_NAME='max_devices');
SET @sql := IF(@has_max=0,
  'ALTER TABLE `cards` ADD COLUMN `max_devices` INT NOT NULL DEFAULT 0
     COMMENT ''0=不限 / 1=一台 / N'' AFTER `kind`', 'DO 0');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- last_used_at
SET @has_lu := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cards' AND COLUMN_NAME='last_used_at');
SET @sql := IF(@has_lu=0,
  'ALTER TABLE `cards` ADD COLUMN `last_used_at` DATETIME NULL DEFAULT NULL
     COMMENT ''最近一次使用（导出为 epoch 秒）'' AFTER `max_devices`', 'DO 0');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- 迁移（只在 kind 首次新增时跑一次）
SET @sql := IF(@has_kind=0,
  'UPDATE `cards` SET `kind`=''paid'',
      `max_devices` = CASE WHEN `bind_one`=1 THEN 1 ELSE 0 END,
      `last_used_at` = NULL', 'DO 0');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- 索引（幂等）
SET @has_idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='cards' AND INDEX_NAME='idx_cards_kind');
SET @sql := IF(@has_idx=0, 'ALTER TABLE `cards` ADD KEY `idx_cards_kind` (`kind`)', 'DO 0');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;
```

**幂等要点**
- 三个 `ADD COLUMN` 都由 `information_schema` 判存在；
- 迁移用 `@has_kind`（**加列之前**的快照）：第一次跑 `=0` → 执行迁移；第二次跑 `=1` → `DO 0`，**不会覆盖后来改过的 kind / max_devices**；
- 索引同理；重复执行全程无报错。

**迁移规则**（与 lead 一致）：`kind='paid'`、`max_devices = bind_one ? 1 : 0`、`last_used_at = NULL`（导出为 0）。

---

## 2. 表单字段与联动

### 2.1 新建卡密（`pages/cards_new.php`）

| 位置 | 字段 | 说明 |
|---|---|---|
| `:300` 单卡表单 | `<select name="kind">` | `paid`（默认）/ `free` |
| `:308` 单卡表单 | `<input type="number" name="max_devices" min=0 max=9999 value=0>` | 0=不限 |
| `:374/:382` 批量表单 | 同上两个字段 | 批量同样生效 |
| `:235` | 文案块 | 「卡类型怎么选？」两行解释 |
| `:408-420` | JS 联动 | `kind=free` → `max_devices.disabled=true` 且 `value=0`；切回 paid 恢复可编辑 |

服务端兜底（不依赖 JS）：`card_kind_norm()` + `card_max_devices_norm('free',…)→0`。
落库：单卡 `:66`、批量 `:171` 的 INSERT 都带 `kind, max_devices`；`bind_one` 由 `max_devices` 派生。

### 2.2 编辑已有卡（`pages/cards.php`）

| 位置 | 字段 | 说明 |
|---|---|---|
| `:483` | 卡类型 | **只读文本**（`card_kind_label()`），不可改 |
| `:486` | hidden `kind` | 仅回传原值，服务端忽略 POST 里的 kind（`:206-208` 取数据库值） |
| `:489` | `max_devices` | 可改；公益卡自动 disabled；保存即写库 |
| `:213` | UPDATE | `... max_devices = ? ...`（ALTER 前自动走旧 SQL） |
| `:555` | 列表表头 | 新增「类型」列 |
| `:600-606` | 列表单元格 | 公益/付费徽标 + `card_devices_text()`（最多 N 台/不限） |

**为什么 kind 只读**：改 kind 会让 `publisherId = md5(card)[:8]` 派生结果变化 → 该卡下所有设备账号失联且不可逆。UI 层面直接不可点（比弹窗更稳）。

**生效时间**：`max_devices` 保存后写 MySQL；客户端读取的是 `cards.json`，所以 **≤60 秒**（cron 每分钟）或到「仪表盘 → 立即同步」立刻推送。

---

## 3. 同步链路（`inc/sync.php`）

### 3.1 导出字段

`sync_make_payload()`（`:236-275`）每张卡输出：

```php
array(
  'devices'      => [...],
  'expire'       => 0,
  'bind_one'     => ($maxd === 1),      // legacy，仅派生
  'kind'         => 'free'|'paid',
  'max_devices'  => 0|1|N,
  'last_used_at' => <epoch 秒>,          // sdkcard 要的数值（不是 DATETIME 字符串）
)
```

- `kind`：`free` 之外一律 `paid`（与 SDK 默认一致）；
- `max_devices`：`free` 强制 0；缺列时按 `bind_one` 兼容；
- `last_used_at`：MySQL DATETIME → `strtotime()` → epoch 秒，NULL → 0。

### 3.2 反向合并 last_used_at（proto-analyst 的硬要求）

- sdkcard 登录/quick-login 成功后写 `cards.json` 的 `last_used_at = time.time()`（epoch）；
- cron 每轮先读旧 `cards.json`，对每张卡取 `max(MySQL, JSON)`：
  - JSON 更新 → 收集 `pending_last_used = [[id, ts], …]`（`:262-263`）；
  - 在 `sync_build()` 里回写 MySQL（`:341-357`）：
    `UPDATE cards SET last_used_at = ? WHERE id = ? AND (last_used_at IS NULL OR last_used_at < ?)`
    —— **只前进不后退**，并发下也不会被旧值覆盖；
  - 导出的 `last_used_at` 用合并后的值，因此 cron 不会把 SDK 刚写的值冲回 0。

### 3.3 兼容与容错

- `sync_cards_has_type_cols()`（`:140-158`）：`information_schema` 一次性探测三列；
  - ALTER 前：SELECT 不带新列，导出按 `bind_one` 降级（**新 PHP 可以先于 ALTER 上线，不炸 cron**）；
  - ALTER 后：自动带三列。
- `devices` 合并逻辑不变（只补不删），`kind/max_devices` 以 MySQL 为准，**不会被 json 旧值覆盖**。
- `sync_import_orphans()`（`:583-614`）：从 `cards.json` 恢复孤儿卡时，若三列存在则一并写回 `kind/max_devices/last_used_at`。

### 3.4 同步频率

- cron：`cron/sync_cards.php` 每分钟一次（宝塔计划任务实际配置为准）；
- 面板「立即同步」：`sync_run_from_web()` 可立刻推；
- **结论**：面板改完 `max_devices`，客户端 **≤60 秒**生效（或点立即同步立即生效）。

---

## 4. `php -l`

```text
LINT total=26 bad=0        # 25 个产品 PHP + 1 个临时测试脚本
```

（服务器 PHP 8.2.31，在 /tmp 副本上跑，未触碰站点。）

---

## 5. 演练结果（三条 + 两条边界）

在 /tmp 副本上直接 include `inc/sync.php` 调 `sync_make_payload()`（纯函数，不连库）：

| 用例 | 输入 | 输出 | 结果 |
|---|---|---|---|
| 公益卡 | `kind=free, max_devices=5, bind_one=1` | `kind=free, max_devices=0, bind_one=false` | ✅ 公益强制不限 |
| 付费·1 台 | `kind=paid, max_devices=1` | `kind=paid, max_devices=1, bind_one=true, last_used_at=<db epoch>` | ✅ |
| 付费·不限 | `kind=paid, max_devices=0` | `kind=paid, max_devices=0, bind_one=false` | ✅ |
| 遗留行（ALTER 前） | 只有 `bind_one=1`，无 kind/max | `kind=paid, max_devices=1` | ✅ 兼容 |
| 反向合并 | DB=1794931200，JSON=1794934800（更新） | 输出 1794934800，`pending=[[2,1794934800]]`，devices 保留 | ✅ |

另：`card_max_devices_norm('free',5)=0`、`card_max_devices_norm('paid',3)=3`、`card_bind_one_from_max(1)=1 / (5)=0`、`card_last_used_to_epoch(1763424000)=1763424000`（数字与字符串都认）。

**未做**：真实 MySQL 的 INSERT/UPDATE 端到端（需要先执行 ALTER）→ 见 §7 的 3 条验证。

---

## 6. 与 proto-analyst 的对齐结论

| 项 | 结论 |
|---|---|
| 字段 | `kind`(free/paid)、`max_devices`(int)、`last_used_at`(**epoch 秒**) |
| 写入点 | `last_used_at` 只由 SDK 写 `cards.json`；PHP 反向合并进 MySQL |
| bind_one | 保留但仅 legacy；导出 `= (max_devices===1)`，**不用它反推 max_devices** |
| 缺字段 | SDK 已容错（缺→paid/0/0）；PHP 导出始终给全 |
| 上线顺序 | **ALTER → PHP → SDK**（PHP 有降级，实际上 PHP 先于 ALTER 也不会炸） |

---

## 7. 给 srv-ops 的执行清单

> 前置：`mysqldump ba_cardadmin cards > /root/cards_before_cardtype_$(date +%Y%m%d).sql`

1. **ALTER**（只读确认后再执行）：
   ```bash
   mysql ba_cardadmin < /www/wwwroot/ba_cardadmin/_audit/alter_cards_cardtype.sql
   # 期望：3 个 SHOW COLUMNS 有输出；GROUP BY kind,max_devices 显示存量 = paid + (1|0)
   ```
2. **部署 4 个文件**（本功能）：
   ```
   inc/helpers.php  inc/sync.php  pages/cards_new.php  pages/cards.php
   ```
   （若上一批 F1–F4 还没部署，按 `FIX_PHP_20261118_0101.md` §10 的顺序一并做，`inc/auth.php` 仍要最先。）
3. **重载**：`/etc/init.d/php-fpm-82 reload`
4. **等同步**：≤60s，或面板「仪表盘 → 立即同步」
5. **验证 cards.json**：
   ```bash
   python3 - <<'PY'
   import json
   d=json.load(open('/www/wwwroot/ba_sdk/cards.json'))['cards']
   for k,v in list(d.items())[:5]:
       print(k, v.get('kind'), v.get('max_devices'), v.get('last_used_at'), v.get('bind_one'))
   PY
   ```
   期望：每张卡都有 `kind`（free/paid）、`max_devices`（int）、`last_used_at`（int），`bind_one == (max_devices==1)`。

### 部署后 3 条功能验收

| # | 操作 | 期望（页面 + SQL + json） |
|---|---|---|
| 1 | 新建「公益卡」，max_devices 自动置灰 | `cards.kind='free'`、`max_devices=0`；`cards.json` 同值 |
| 2 | 新建「付费卡」限 1 台 | `kind='paid'`、`max_devices=1`、`bind_one=1` |
| 3 | 编辑该付费卡改成不限（0）保存 | `max_devices=0`、`bind_one=0`；≤60s 后 `cards.json` 变 0 |

---

## 8. 风险与注意

### 8.0 三项确认（2026-11-18 01:12，只读核实，未改代码）

**① 时区换算**
- PHP 默认时区：`inc/db.php:87 @date_default_timezone_set(APP_TIMEZONE)`；`db.php:42` 默认 `Asia/Shanghai`；线上 `config.php:19 define('APP_TIMEZONE', 'Asia/Shanghai')`。
- 读：`inc/helpers.php:317-324`
  ```php
  $ts = strtotime($dt);        // $dt = MySQL DATETIME，按 Asia/Shanghai 解释
  return $ts === false ? 0 : (int)$ts;
  ```
  调用点 `inc/sync.php:230`：`$lu_db = ... dt_to_epoch($r['last_used_at'])`。
- 写：`inc/sync.php:345` `$ts = date('Y-m-d H:i:s', (int)$pl[1]);` → 绑定字符串到 `UPDATE ... last_used_at = ?`（`:347`）。
- MySQL：`@@global.time_zone=SYSTEM`、`@@session.time_zone=SYSTEM`；实测 `NOW()=2026-11-18 01:12:02` ↔ `UNIX_TIMESTAMP()=1794935522` 正好 +08:00。**两端同为 +0800**，且全程 DATETIME 字符串读写、**没有 FROM_UNIXTIME/UNIX_TIMESTAMP**，故无 8 小时偏移。

**② max_devices 非法值**
- 先 `post_int('max_devices', 0, 0, 9999)` 夹取，再 `card_max_devices_norm()`：
  - `"abc"` → `(int)` = 0；`-1` → 0；`1024` → 1024；`>9999` → 9999；`kind=free` → 强制 0。
- 策略：**非法值一律按 0（不限）**，不拒绝保存（与 SDK「缺省 0 / 非法按 0」一致）。

**③ kind 取值域**
- 当前 `card_kind_norm()`：`trim($v) === 'free' ? 'free' : 'paid'` —— **精确白名单**，`FREE`/`Free` 都会落到 `paid`；SDK 侧同样只认小写 `free`，两端一致。
- 注：尚未做显式 `strtolower()`；如需「大小写都接受」，解冻后加一行 `strtolower()` 即可（本次未改）。

**④ ALTER 额外注意**
- 体量：`cards` 1 行 / 0.09 MB，`card_devices` 2 行 / 0.05 MB（information_schema 估算）——DDL 本身毫秒级。
- 外键：`card_devices.fk_card_devices_card → cards`（1 个）。加列不动外键列，但 DDL 仍需短暂 MDL，建议避开长事务。
- 建议执行前：`SHOW PROCESSLIST` 确认无长事务；会话设 `SET lock_wait_timeout=10`，避免在 iowait 高时无限排队；`foreign_key_checks` 保持 1（默认）。
- 当前磁盘：`vda %util=100`、load 12.07 —— **确认应等 lead 通知再执行**。

---

## 9. 风险与注意（原）

1. **kind 不可改**：UI 只读；服务端也不接受 POST 覆盖（取数据库值）。要换类型只能新建卡。
2. **ALTER 失败半途**：脚本逐条判断存在性，重跑即续；迁移只在 `kind` 首次新增时执行一次。
3. **cron 覆盖**：`devices` 合并、`last_used_at` 取 max；`kind/max_devices` 以 MySQL 为准（面板写的值不会被 json 冲掉）。
4. **老客户端**：`bind_one` 仍导出，旧逻辑不受影响；SDK 新逻辑读 `max_devices`。
5. **导出 CSV**（`cards_export.php`）暂未加类型列——需求只要求列表页；需要的话下一批加。
6. **`cards_import.php`**（TXT/CSV 导入）未带 kind/max，默认 `paid/0`，符合迁移规则。
