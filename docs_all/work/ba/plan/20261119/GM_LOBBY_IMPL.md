# GM 面板「一键发放全部记忆大厅」实现报告

- 时间：2026-11-19（Asia/Shanghai）
- 执行者：本地实现 agent（**只写 PHP 到本地工作目录**）
- 范围：`inc/gm_lobby.php`（新增）+ `pages/items.php`（修改）
- 红线遵守：**未部署、未 SSH、未碰服务器、未改基准目录 `p0rates/`**；未引入任何新依赖；
  `inc/gacha.php`、`pages/gacha_rates.php` 一个字节没动（sha256 与基准一致，见 §1.2）。

> 相关文档：邮件接口**容量实测**的原始记录在 `plan/20261119/GM_LOBBY_MAIL_CAPACITY.md`
> （原本写在本文件名下，为避免覆盖 srv-ops 的实测数据，已原样另存一份，内容 sha256 一致）。
> 本文件只讲实现与部署。

---

## 0. 一句话结论

「发放全部记忆大厅」已实现并通过本地自测（**79 + 8 项检查全过**）：
258 个客户端大厅 id 硬编码在 `inc/gm_lobby.php`，按可配置的「每封包裹数」（默认 60）切成 N 封
`POST /api/admin/mail/send`，逐封发送、单封失败不中断、错误全收集，页面上每人一行显示
「邮件 / 包裹 / 失败原因」。`Type` 用字符串 `"MemoryLobby"`（实测唯一可用写法）。

---

## 1. 文件清单 + sha256

### 1.1 交付到站点根（`/www/wwwroot/ba_cardadmin`）的文件

| # | 相对站点根的路径 | 操作 | 字节 | sha256 |
|---|---|---|---|---|
| 1 | `inc/gm_lobby.php` | **新增** | 15579 | `7623fe9889eac4c26e1d8b45eaad7a21049f45c158288f7247b06cbdb74ec268` |
| 2 | `pages/items.php` | **覆盖** | 24248 | `25f7e2b3d29fec83fcc5abf57b121c2c733e491dd958d712f9693f4767dc0c26` |

行尾与基准一致：**LF（无 CRLF）、无 BOM、UTF-8**。除这两个文件外站点树**没有第三处改动**。

本地路径（工作副本 `work/ba/panel_work/gm_lobby/`）：

```
work/ba/panel_work/gm_lobby/inc/gm_lobby.php      ← 新增
work/ba/panel_work/gm_lobby/pages/items.php       ← 修改
```

### 1.2 未改动证明（红线：不许碰 gacha）

```
inc\gacha.php         baseline=1152FF4C5F16372F  copy=1152FF4C5F16372F   ← 一致
pages\gacha_rates.php baseline=105F151CD539322F  copy=105F151CD539322F   ← 一致
inc\ba.php            baseline=752F1637BDB86787  copy=752F1637BDB86787   ← 一致
```

整树比对（`p0rates/` → `gm_lobby/`）只有两条：`MODIFIED pages/items.php`、`ADDED inc/gm_lobby.php`。

### 1.3 不进站点的自测文件（**不要上传**）

```
work/ba/panel_work/gm_lobby_selftest/run.php           ← mock 自测（79 + 8 项）
work/ba/panel_work/gm_lobby_selftest/check_funcs.php   ← 被调函数是否都存在
work/ba/panel_work/gm_lobby_selftest/check_html.php    ← HTML 结构 vs 基准
```

---

## 2. `pages/items.php` 的 diff

`git diff --no-index p0rates/pages/items.php gm_lobby/pages/items.php` 原文（共 9 个 hunk，按 hunk 分段贴）：

```diff
diff --git a/p0rates/pages/items.php b/gm_lobby/pages/items.php
index 401fd87..bf4fe48 100644
--- a/p0rates/pages/items.php
+++ b/gm_lobby/pages/items.php
@@ -13,10 +13,17 @@ require_once __DIR__ . '/../inc/auth.php';
 require_once __DIR__ . '/../inc/sync.php';
 require_once __DIR__ . '/../inc/ba.php';
 require_once __DIR__ . '/../inc/players.php';
+require_once __DIR__ . '/../inc/gm_lobby.php';
 
 require_login();
 
-/** 一键快捷动作：key => [标题, 命令, 说明] */
+/**
+ * 一键快捷动作：key => [标题, 命令, 说明]
+ *
+ * 「发放全部记忆大厅」和其他 9 个不一样：它不走 GM 命令，而是走
+ * /api/admin/mail/send 发邮件（见 inc/gm_lobby.php），所以它的 [命令] 位留空，
+ * 由 quick 分支按 key 单独处理。
+ */
 function item_quick_actions()
 {
     return array(
```

```diff
@@ -29,6 +36,8 @@ function item_quick_actions()
         'unlock_school'   => array('解锁学院',        'unlockall schooldungeon',  '学院地下城全部解锁'),
         'unlock_mission'  => array('解锁任务',        'unlockall mission',        '任务全部解锁'),
         'battlepass'      => array('解锁通行证',      'unlockbattlepass',         '战斗通行证解锁'),
+        'give_memory_lobby' => array('发放全部记忆大厅', '',
+            '把客户端认识的 258 个记忆大厅做成邮件附件发给玩家（幂等，重复点只会多几封邮件）'),
     );
 }
 
```

```diff
@@ -80,6 +89,7 @@ if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_ME
     $okN   = 0;
     $failN = 0;
     $label = '';
+    $isLobby = false;
 
     if ($mode === 'quick') {
         $key   = post_q('quick', '');
```

```diff
@@ -88,16 +98,64 @@ if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_ME
             flash_set('未知的快捷动作', 'err');
             redirect_self();
         }
-        $label = $acts[$key][0];
-        $cmd   = $acts[$key][1];
-        foreach ($ids as $sid) {
-            $r = ba_command($sid, $cmd);
-            $out = ($r['ok'] && isset($r['data']['output'])) ? (string)$r['data']['output'] : '';
-            $rows[] = array('sid' => $sid, 'ok' => (bool)$r['ok'],
-                            'msg' => $r['ok'] ? (str_limit($out !== '' ? $out : '已执行', 60)) : $r['error']);
-            $r['ok'] ? $okN++ : $failN++;
+
+        /* ── 发放全部记忆大厅：走邮件接口，不走 GM 命令 ──────────────────────
+         * 动作本身不破坏数据，但量大（每人 N 封），所以和 gacha 的 reset_all 一样
+         * 要求二次确认：浏览器 confirm + confirm_all=1 + 服务端一次性令牌
+         * （令牌就是表单里那个 action_token_field('items')，上方 action_token_check('items')
+         * 已经一次性校验并删除，重放会被 419 拦掉）。 */
+        if ($key === 'give_memory_lobby') {
+            if (post_q('confirm_all') !== '1') {
+                flash_set('「发放全部记忆大厅」需要页面上的二次确认（确认框）', 'err');
+                redirect_self();
+            }
+
+            $perMail = gm_memory_lobby_clamp_per_mail(
+                post_int('parcels_per_mail', gm_memory_lobby_default_per_mail())
+            );
+            $plan  = gm_memory_lobby_plan(null, $perMail);
+            $label = $acts[$key][0] . '（每人 ' . $plan['mails'] . ' 封 · 每封最多 '
+                   . $plan['perMail'] . ' 个 · 共 ' . $plan['parcels'] . ' 个）';
+
+            /* scope=selected 是勾选的那几个，scope=all 是全服账号列表，都交给这一个批量函数逐人跑 */
+            foreach (gm_grant_memory_lobbies_batch($ids, $perMail) as $g) {
+                $rows[] = array(
+                    'sid'       => (int)$g['account'],
+                    'ok'        => (bool)$g['ok'],
+                    'msg'       => $g['ok']
+                        ? ('已发出 ' . $g['ok_mails'] . '/' . $g['mails'] . ' 封')
+                        : ('失败 ' . $g['fail_mails'] . '/' . $g['mails'] . ' 封'),
+                    'mails'     => (int)$g['mails'],
+                    'mails_ok'  => (int)$g['ok_mails'],
+                    'parcels'   => (int)$g['parcels'],
+                    'errs'      => $g['errors'],
+                );
+                $g['ok'] ? $okN++ : $failN++;
+            }
+
+            $isLobby = true;
+            panel_op_log('quick.give_memory_lobby', $ids, array(
+                'batch'       => $batch,
+                'per_mail'    => $perMail,
+                'mails'       => $plan['mails'],
+                'sizes'       => $plan['sizes'],
+                'parcels'     => $plan['parcels'],
+                'type'        => gm_memory_lobby_type_value(),
+                'confirm_all' => 1,
+            ), $okN, $failN, $batch);
+
+        } else {
+            $label = $acts[$key][0];
+            $cmd   = $acts[$key][1];
+            foreach ($ids as $sid) {
+                $r = ba_command($sid, $cmd);
+                $out = ($r['ok'] && isset($r['data']['output'])) ? (string)$r['data']['output'] : '';
+                $rows[] = array('sid' => $sid, 'ok' => (bool)$r['ok'],
+                                'msg' => $r['ok'] ? (str_limit($out !== '' ? $out : '已执行', 60)) : $r['error']);
+                $r['ok'] ? $okN++ : $failN++;
+            }
+            panel_op_log('quick.' . $key, $ids, array('batch' => $batch, 'command' => $cmd), $okN, $failN, $batch);
         }
-        panel_op_log('quick.' . $key, $ids, array('batch' => $batch, 'command' => $cmd), $okN, $failN, $batch);
     } elseif ($mode === 'item') {
         $uid = post_int('unique_id', 0);
         $amt = post_int('amount', 1);
```

```diff
@@ -137,7 +195,8 @@ if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_ME
     }
 
     audit_log('player.bulk_op', implode(',', $ids), $mode . ' ' . $label . ' ok=' . $okN . ' fail=' . $failN);
-    $result = array('batch' => $batch, 'rows' => $rows, 'ok' => $okN, 'fail' => $failN, 'label' => $label);
+    $result = array('batch' => $batch, 'rows' => $rows, 'ok' => $okN, 'fail' => $failN,
+                    'label' => $label, 'lobby' => $isLobby);
 }
 
 $roster = player_roster(array());
```

```diff
@@ -176,13 +235,39 @@ echo alert_box('当前客户端有 ' . count($deniedIds) . ' 个角色无法解
   </div>
   <div class="table-wrap">
   <table class="tbl">
+    <?php if (!empty($result['lobby'])) { ?>
+    <thead><tr><th>ServerId</th><th>邮件</th><th>包裹</th><th>结果 / 失败原因</th></tr></thead>
+    <?php } else { ?>
     <thead><tr><th>ServerId</th><th>结果</th></tr></thead>
+    <?php } ?>
     <tbody>
     <?php foreach ($result['rows'] as $rr) { ?>
       <tr>
         <td><a href="<?php echo e(u('pages/player_detail.php?sid=' . $rr['sid'])); ?>">#<?php echo (int)$rr['sid']; ?></a></td>
+        <?php if (!empty($result['lobby'])) { ?>
+          <td class="nowrap">
+            <?php echo (int)$rr['mails_ok']; ?>/<?php echo (int)$rr['mails']; ?> 封
+          </td>
+          <td class="nowrap"><?php echo (int)$rr['parcels']; ?> 个</td>
+          <td>
+            <?php if ($rr['ok']) { ?>
+              <span class="tag tag-ok"><?php echo e($rr['msg']); ?></span>
+            <?php } else { ?>
+              <span class="tag tag-err"><?php echo e($rr['msg']); ?></span>
+              <div class="small" style="margin-top:4px">
+                <?php foreach ((array)$rr['errs'] as $one) { ?>
+                  <div class="bad"><?php echo e($one); ?></div>
+                <?php } ?>
+                <?php if (!empty($rr['mails_ok'])) { ?>
+                  <div class="muted">已发出的那几封不用重发（幂等），重跑整个动作是安全的。</div>
+                <?php } ?>
+              </div>
+            <?php } ?>
+          </td>
+        <?php } else { ?>
         <td><?php echo $rr['ok'] ? '<span class="tag tag-ok">' . e($rr['msg']) . '</span>'
                                   : '<span class="tag tag-err">' . e($rr['msg']) . '</span>'; ?></td>
+        <?php } ?>
       </tr>
     <?php } ?>
     </tbody>
```

```diff
@@ -219,21 +304,51 @@ echo alert_box('当前客户端有 ' . count($deniedIds) . ' 个角色无法解
 <div class="detail-grid">
   <section class="card">
     <div class="card-h"><h2>快捷动作</h2></div>
+    <?php
+    /* 记忆大厅：258 个 id 的发送计划（不发请求），供按钮下方那行说明与输入框用 */
+    $lobbyIds   = gm_memory_lobby_ids();
+    $lobbyChk   = gm_memory_lobby_selfcheck();
+    $lobbyPlan  = gm_memory_lobby_plan();
+    $lobbyCount = count($lobbyIds);
+    ?>
     <form method="post" action="<?php echo e(u('pages/items.php')); ?>" id="f-quick">
       <?php echo csrf_field(); ?>
       <?php echo action_token_field('items'); ?>
       <input type="hidden" name="mode" value="quick">
       <input type="hidden" name="scope" value="selected" class="scope-holder">
+      <?php /* 发放类动作的二次确认标记；其他快捷动作忽略它 */ ?>
+      <input type="hidden" name="confirm_all" value="1">
       <div class="actions" style="flex-wrap:wrap">
         <?php foreach (item_quick_actions() as $k => $a) { ?>
           <button type="submit" name="quick" value="<?php echo e($k); ?>" class="btn btn-sm"
-                  title="<?php echo e($a[2]); ?>"><?php echo e($a[0]); ?></button>
+                  title="<?php echo e($a[2]); ?>"
+                  <?php echo $k === 'give_memory_lobby' ? ' onclick="return confirmLobbyGrant(this);"' : ''; ?>><?php echo e($a[0]); ?></button>
         <?php } ?>
       </div>
+      <div class="fld" style="max-width:460px;margin-top:12px">
+        <span>每封邮件的包裹数（1–<?php echo (int)$lobbyCount; ?>，只影响「发放全部记忆大厅」）</span>
+        <input type="number" name="parcels_per_mail" id="lobby-per-mail"
+               value="<?php echo (int)$lobbyPlan['perMail']; ?>"
+               min="1" max="<?php echo (int)$lobbyCount; ?>" step="1" inputmode="numeric">
+        <em>默认 <?php echo (int)gm_memory_lobby_default_per_mail(); ?>。
+          本次将分 <b id="lobby-mails"><?php echo (int)$lobbyPlan['mails']; ?></b> 封邮件发送
+          （共 <b id="lobby-total"><?php echo (int)$lobbyPlan['parcels']; ?></b> 个大厅，
+          每封 ≤ <b id="lobby-pm"><?php echo (int)$lobbyPlan['perMail']; ?></b> 个）。</em>
+      </div>
     </form>
+    <?php if (!$lobbyChk['ok']) { ?>
+      <?php echo alert_box('记忆大厅自检：' . $lobbyChk['warn'] . '（已按实际 ' . (int)$lobbyChk['actual']
+          . ' 个 id 继续，不会因此报错）', 'warn'); ?>
+    <?php } ?>
     <p class="muted small" style="margin-top:8px">
+      只发放<b>客户端认识</b>的 <?php echo (int)$lobbyCount; ?> 个记忆大厅（来源：客户端表
+      <code>MemoryLobbyDBSchema</code>）。该操作幂等：重复点击不会重复获得大厅，只会多几封邮件。
+    </p>
+    <p class="muted small">
       快捷动作走 GM 命令（<code>/api/admin/command</code>，Uid=目标玩家），不需要玩家在线。
-      命令清单见「GM 命令台」。
+      命令清单见「GM 命令台」。<b>「发放全部记忆大厅」例外</b>：它走邮件接口
+      （<code>/api/admin/mail/send</code>，包裹类型 <code>MemoryLobby</code>），
+      邮件进邮箱后要玩家在游戏里领取才真正到账。
     </p>
   </section>
 
```

```diff
@@ -328,6 +443,36 @@ echo alert_box('当前客户端有 ' . count($deniedIds) . ' 个角色无法解
 </section>
 
 <script>
+/* 「发放全部记忆大厅」的二次确认（confirm + 服务端 confirm_all=1 + 一次性令牌）。
+   定义在 IIFE 外面，按钮的 onclick 才看得到它。 */
+function confirmLobbyGrant(btn) {
+  var TOTAL = <?php echo (int)$lobbyCount; ?>;
+  var DEF   = <?php echo (int)gm_memory_lobby_default_per_mail(); ?>;
+
+  var pmEl = document.getElementById('lobby-per-mail');
+  var pm = parseInt(pmEl ? pmEl.value : '', 10);
+  if (!isFinite(pm) || pm < 1) { pm = DEF; }
+  if (pm > TOTAL) { pm = TOTAL; }
+  var mails = Math.ceil(TOTAL / pm);
+
+  var all = document.getElementById('scope-all');
+  var who;
+  if (all && all.checked) {
+    who = '全服全部玩家';
+  } else {
+    var n = document.querySelectorAll('.msid:checked').length;
+    if (n === 0) {
+      alert('请先勾选玩家，或勾选「对全服执行」。');
+      return false;
+    }
+    who = n + ' 名选中玩家';
+  }
+
+  return confirm('确定对「' + who + '」发放全部 ' + TOTAL + ' 个记忆大厅吗？\n'
+    + '每人 ' + mails + ' 封邮件，每封最多 ' + pm + ' 个包裹。\n'
+    + '该操作幂等：重复执行不会重复获得大厅，只会多几封邮件。');
+}
+
 (function () {
   var picks = Array.prototype.slice.call(document.querySelectorAll('.msid'));
   var counter = document.getElementById('sel-count');
```

```diff
@@ -351,6 +496,25 @@ echo alert_box('当前客户端有 ' . count($deniedIds) . ' 个角色无法解
     });
   }
 
+  /* 「每封邮件的包裹数」改动时，实时重算「本次将分 X 封邮件发送」 */
+  var pmEl = document.getElementById('lobby-per-mail');
+  if (pmEl) {
+    var LOBBY_TOTAL = <?php echo (int)$lobbyCount; ?>;
+    var LOBBY_DEF   = <?php echo (int)gm_memory_lobby_default_per_mail(); ?>;
+    var mailsEl = document.getElementById('lobby-mails');
+    var pmOut   = document.getElementById('lobby-pm');
+    var syncPlan = function () {
+      var pm = parseInt(pmEl.value, 10);
+      if (!isFinite(pm) || pm < 1) { pm = LOBBY_DEF; }
+      if (pm > LOBBY_TOTAL) { pm = LOBBY_TOTAL; }
+      if (mailsEl) { mailsEl.textContent = String(Math.ceil(LOBBY_TOTAL / pm)); }
+      if (pmOut) { pmOut.textContent = String(pm); }
+    };
+    pmEl.addEventListener('input', syncPlan);
+    pmEl.addEventListener('change', syncPlan);
+    syncPlan();
+  }
+
   /* 三个表单共享一组 checkbox：提交前把勾选的 sid 复制进该表单 */
   document.querySelectorAll('form#f-quick, form#f-item, form#f-cmd').forEach(function (f) {
     f.addEventListener('submit', function () {
```

---

## 3. 258 个 id 的来源与校验

### 3.1 来源

客户端表 `work/ba/data/ExcelDB.db` → `MemoryLobbyDBSchema(Id INTEGER, Bytes BLOB)`，**258 行**，
只读导出后硬编码进 `inc/gm_lobby.php`（`gm_memory_lobby_ids()`）。
**运行时不读 ExcelDB.db、不查服务端**，页面渲染零 IO。

### 3.2 三重校验（全部通过）

| 校验项 | 结果 |
|---|---|
| `ExcelDB.db` 只读导出 `SELECT Id FROM MemoryLobbyDBSchema ORDER BY Id` | **258 行，无重复** |
| 导出结果 vs `srv_src/Shittim-Server/Resources/ClientMemoryLobbyIds.txt` | **逐行完全相同**（`db == ref` → `True`，对称差为空） |
| 导出结果 vs 题述分段 `10000-10098, 10100-10136, 13000-13014, 16000-16019, 20000-20056, 23000-23008, 26000-26015` + 5 个 7 位 id | **集合完全相同**（双向差集都为空） |

分段计数：`99 + 37 + 15 + 20 + 57 + 9 + 16 = 253`，`+ 5`（`1000501 / 1001001 / 1300401 / 1300801 / 2300501`）= **258** ✅

```python
# 实际跑过的校验脚本输出
db count: 258  ref count: 258
db  == ref : True
db set xor ref: []
dup in db: 0
segment-only count: 253  + seven = 258
expected(set) == db(set): True
db ids not in expected: []
expected ids not in db: []
seven-digit in db: [1000501, 1001001, 1300401, 1300801, 2300501]
first5: [10000, 10001, 10002, 10003, 10004] last5: [1000501, 1001001, 1300401, 1300801, 2300501]
```

### 3.3 运行时自检

`gm_memory_lobby_selfcheck()`：

- `count() === 258` 且无重复 → `ok = true`，页面什么都不显示。
- 不等于 258 → **`error_log('[gm_lobby] WARN …')` 记一条 WARN**，返回 `warn` 文案，
  页面顶部显示一条 `alert-warn`，**但操作照常按实际数组执行，不报错、不拦截**。
- 自检结果按请求缓存（`static`），不重复计算。

---

## 4. 切片逻辑

```php
gm_memory_lobby_slice($ids, $perMail)   // array_slice 顺序切，不留空份
gm_memory_lobby_plan($ids, $perMail)    // 只算不发：perMail / mails / parcels / sizes / slices
gm_grant_memory_lobbies($uid, $perMail) // 真发：逐封 POST，收集错误
gm_grant_memory_lobbies_batch($ids, …)  // 对每个账号各调一次（selected / all 都走它）
```

规则：

1. `$perMail` 先夹到 `1..count(ids)`；`0`、负数、非数字 → 回落默认 `60`；超上限 → 夹到 `258`。
2. 从第 0 个开始每 `$perMail` 个切一段，**顺序不变**，最后一段可以短。
3. 每封 `Comment = 记忆大厅全部解锁（i/N）`，`i` 从 1 开始。
4. 每个包裹：`{"Type":"MemoryLobby","Id":<id>,"Amount":1}`（`Amount` 必须 ≥1）。
5. **单封失败 → 记 error，继续下一封**；只要有一封失败该玩家 `ok=false`，
   但已成功的邮件已经进邮箱，重跑整个动作是安全的（幂等）。

默认 60 的切法（自测已断言）：

| perMail | 封数 | 每封大小 |
|---|---|---|
| **60（默认）** | **5** | **[60, 60, 60, 60, 18]**（60×4 + 18 = 258） |
| 1 | 258 | 每封 1 |
| 100 | 3 | [100, 100, 58] |
| 258 | 1 | [258] |

**可配置**的两处：

- 常量：`inc/gm_lobby.php` 顶部 `GM_MEMORY_LOBBY_PARCELS_PER_MAIL`（默认 `60`）。
- 页面：快捷动作卡片里的 `每封邮件的包裹数` 输入框（`name=parcels_per_mail`），提交即生效。
- 页面实时显示「本次将分 **X** 封邮件发送」，输入框一改就重算（`Math.ceil(258/pm)`）。

> ⚠️ 实测已证明**一封挂 258 个是 HTTP 200**（13 KB 请求体，见
> `GM_LOBBY_MAIL_CAPACITY.md` §3-D），所以默认 60 纯属按任务要求取的保守值，**不是接口限制**。
> 想一封发完：页面输入框填 `258`，或把常量改成 `258`。

---

## 5. 接口契约（代码以实测为准）

`POST /api/admin/mail/send`

```json
{"AccountServerId":4,
 "Sender":"Schale",
 "Comment":"记忆大厅全部解锁（1/5）",
 "Parcels":[{"Type":"MemoryLobby","Id":10000,"Amount":1}, …]}
```

服务端侧依据（`srv_src`）：

- `Controllers/AdminController.cs` → `SendMail([FromBody] SendMailRequest)`
- `SendMailRequest.ParcelRequest { string Type; long Id; long Amount; }`
- `Enum.Parse<ParcelType>(p.Type)` → `Type` 是**字符串**枚举名
- `Schale/FlatData/ParcelType.cs:18` → `MemoryLobby = 8`
- `Services/ParcelResolver.cs:253` `UpdateMemoryLobby()` →
  `if (memoryLobby != null) return;`（按 `AccountServerId + MemoryLobbyUniqueId` 去重 ⇒ **幂等**）

`Type` 两种写法（**实测结论，不是推测**）：

| 写法 | 结果 |
|---|---|
| `"Type": "MemoryLobby"`（字符串） | **HTTP 200**，落库 `Key.Type = 8` ✅ |
| `"Type": 8`（裸 JSON 数字） | **HTTP 400** `The JSON value could not be converted to System.String` ❌ |

⇒ 默认走 `'name'`。`'number'` 模式存在，但它发的是**字符串 `"8"`**（不是整数 8）：
`.NET Enum.Parse` 接受数字字符串，理论上可行，**但实测没测过这条路** —— 实测已经证明
`'name'` 可用，**没有理由切过去**。开关：`GM_MEMORY_LOBBY_TYPE_MODE`。

---

## 6. 自测输出（本地真跑，无服务器）

环境：`PHP 8.3.36 (cli)`；`ba_post` 被替换成假函数（记录每次调用 + 可指定第几次失败）。

### 6.1 `php -l`

```
gm_lobby.php  ->  No syntax errors detected in …\gm_lobby\inc\gm_lobby.php
items.php     ->  No syntax errors detected in …\gm_lobby\pages\items.php
run.php       ->  No syntax errors detected in …\gm_lobby_selftest\run.php
```

### 6.2 函数存在性 + HTML 结构

```
已声明函数 288 个，内置函数 1021 个
检查文件：items.php, gm_lobby.php

[ok] 所有被调用的函数都能在 inc/ 或内置函数里找到

基准 p0rates/pages/items.php
  纯 HTML 6851 字节 · DOM 结构错误 7 条
改动 gm_lobby/pages/items.php
  纯 HTML 10536 字节 · DOM 结构错误 7 条

[ok] 改动后结构错误数（7）与基准（7）一致 —— 新增标记没有引入结构问题
```

> 那 7 条是 DOMDocument 的 HTML4 解析器不认识 `<section>` / `<datalist>` 造成的，
> **基准里一模一样**，不是新增问题。

### 6.3 主用例（79 项）

```
== 1. 258 个 id 清单 ==
  [ ok ] id 总数 === 258  → 258
  [ ok ] id 无重复  → 258
  [ ok ] id 升序且去重
  [ ok ] 第一个 id  → 10000
  [ ok ] 最后一个 id  → 2300501
  [ ok ] 5 个 7 位 id  → [1000501,1001001,1300401,1300801,2300501]
  [ ok ] 自检通过（258/258）  → 无 WARN

== 2. 切片（默认 60 一封）==
  [ ok ] 默认每封 60 个  → 60
  [ ok ] perMail = 60  → 60
  [ ok ] 邮件数 = 5  → 5
  [ ok ] 包裹总数 = 258  → 258
  [ ok ] 每封大小 = [60,60,60,60,18]  → [60,60,60,60,18]
  [ ok ] 5 封加起来 = 258

== 3. 正常发放（60 一封）==
  [ ok ] 结果 ok === true
  [ ok ] mails = 5  → 5
  [ ok ] parcels = 258  → 258
  [ ok ] ok_mails = 5  → 5
  [ ok ] fail_mails = 0  → 0
  [ ok ] errors 为空  → []
  [ ok ] account = 7001  → 7001
  [ ok ] per_mail = 60  → 60
  [ ok ] 实际 POST 了 5 次  → 5
  [ ok ] 5 次都 POST /api/admin/mail/send
  [ ok ] 5 次 AccountServerId 都是 7001
  [ ok ] 每个包裹 Amount 都 = 1（服务端要求 ≥1）
  [ ok ] 每封 Parcels 数量 = [60,60,60,60,18]
  [ ok ] 每封 Comment = 记忆大厅全部解锁（i/5）
  [ ok ] 每个 parcel.Type = 'MemoryLobby'
  [ ok ] 第 1 封 Comment 原文  → "记忆大厅全部解锁（1/5）"
  [ ok ] 第 5 封 Comment 原文  → "记忆大厅全部解锁（5/5）"
  [ ok ] 摊平后共 258 个包裹  → 258
  [ ok ] 摊平后的 Id 序列 === 258 个 id（顺序不变、无缺失）  → [10000,10001,…,26014,26015,1000501,…,2300501]
  [ ok ] JSON 里 Type 是字符串 "MemoryLobby"
  [ ok ] JSON 里有 AccountServerId

== 4. 第 3 封失败，其它封继续 ==
  [ ok ] 仍然 POST 了 5 次（失败不中断）  → 5
  [ ok ] 结果 ok === false  → false
  [ ok ] ok_mails = 4  → 4
  [ ok ] fail_mails = 1  → 1
  [ ok ] errors 收集到 1 条  → 1
  [ ok ] errors[0] 指明是第 3/5 封  → 第 3/5 封（60 个包裹，Id 10121–20008）失败：mock 服务端 500（HTTP 500）
  [ ok ] errors[0] 带上了原始错误
  [ ok ] errors[0] 带上了 HTTP 500
  [ ok ] errors[0] 带上了该封包裹数
  [ ok ] 第 4 封仍发了 60 个  → 60
  [ ok ] 第 5 封仍发了 18 个  → 18
  [ ok ] 第 5 封最后一个 Id 正确  → 2300501

== 5. 批量：3 个账号（scope=all 走这条）==
  [ ok ] 每个账号一个结果  → 3
  [ ok ] 3 个账号 × 5 封 = 15 次 POST  → 15
  [ ok ] 每个账号各被调 5 次  → {"8001":5,"8002":5,"8003":5}
  [ ok ] 3 个账号全部 ok
  [ ok ] 结果顺序与传入账号顺序一致
  [ ok ] 某账号失败，其它账号仍然跑完（15 次）  → 15
  [ ok ] 账号 8001 失败  → false
  [ ok ] 账号 8001 失败 2 封  → 2
  [ ok ] 账号 8002 不受影响  → true
  [ ok ] 账号 8003 不受影响  → true

== 6. 自检数量不符（注入 257 个）==
  [ ok ] 注入 257 个 → ok === false  → false
  [ ok ] expected = 258  → 258
  [ ok ] actual = 257  → 257
  [ ok ] warn 说明数量异常  → 记忆大厅 id 数量异常：期望 258 个，实际 257 个（以实际数组为准，操作继续）
  [ ok ] warn 说明以实际数组为准
  [ ok ] 注入后真实数组仍是 258（互不影响）
  [ ok ] WARN 已写进 error_log  → [19-Nov-2026 23:40:12 Asia/Shanghai] [gm_lobby] WARN 记忆大厅 id 数量异常：期望 258 个，实际 257 个（以实际数组为准，操作继续）
  [ ok ] 257 个在 60 一封下仍是 5 封  → 5
  [ ok ] parcels = 257（按实际数组）  → 257
  [ ok ] 仍能正常发完（不因数量不符报错）  → true
  [ ok ] 257 个实际 POST 5 次  → 5

== 7. 边界值 ==
  [ ok ] per-mail=0 → 回落默认 60  → 60
  [ ok ] per-mail=0 → 5 封
  [ ok ] per-mail=-5 → 回落默认 60  → 60
  [ ok ] per-mail=999 → 夹到 258  → 258
  [ ok ] per-mail=999 → 1 封
  [ ok ] per-mail=1 → 258 封
  [ ok ] per-mail=1 → 每封 1 个
  [ ok ] per-mail=100 → [100,100,58]
  [ ok ] per-mail=258 → 1 封发完全部

== 8. uid 非法 ==
  [ ok ] uid=0 → ok === false  → false
  [ ok ] uid=0 → 1 条错误  → AccountServerId 无效：0
  [ ok ] uid=0 → 一次 POST 都没发

============================================================
总计 79 项检查，0 项失败
ALL PASS
```

（第 3 节里那条摊平的 Id 序列原文有 258 个数字，这里为了可读性截断成 `…`，
脚本里是 `same($flat, $ids)` 的**全等比较**，不是抽样。）

### 6.4 `Type` 的 `'number'` 模式（8 项）

```
== Type 模式 number（GM_MEMORY_LOBBY_TYPE_MODE=number）==
  [ ok ] type_mode 是 'number'  → "number"
  [ ok ] type_value 是字符串 '8'  → "8"
  [ ok ] 258 个一封 → 1 次 POST  → 1
  [ ok ] parcel.Type === 字符串 '8'  → "8"
  [ ok ] parcel.Type 是 string 类型（不是 int）  → string
  [ ok ] JSON 里是 "Type":"8"（带引号）
  [ ok ] JSON 里没有裸数字 "Type":8
  [ ok ] 结果里的 type 也是 "8"

ALL PASS : 8 checks, 0 failed
```

### 6.5 复现方式

```bash
php gm_lobby_selftest/run.php                # 79 项
php gm_lobby_selftest/run.php --type=number  # 8 项
php gm_lobby_selftest/check_funcs.php        # 被调函数存在性
php gm_lobby_selftest/check_html.php         # HTML 结构 vs 基准
```

---

## 7. 实现决策（3 处值得说明的地方）

### 7.1 二次确认：复用 `items` 的一次性令牌，没有新开一个 scope

`pages/items.php` 的 POST 第一行就是 `action_token_check('items')`，它**校验后立即 `unlink`**
（一次性，重放 419）。快捷动作表单里本来就有 `action_token_field('items')`。所以：

- 浏览器 `confirm()` → `confirmLobbyGrant()`（会报出「1 名选中玩家 / 全服全部玩家 + 每人几封」）
- 服务端 `confirm_all=1` 校验
- 服务端**一次性令牌**（`items` scope）

**为什么不在同一个表单里再塞一个 `action_token_field('lobby')`**：`action_token_field()`
写死 `name="_atoken"`，两个同名 hidden 一起提交会互相覆盖，PHP 只留最后一个 → 必然 419。
新开 scope 就必须给按钮单独做一个表单，而快捷动作这 9+1 个按钮共用 `#f-quick`。

结果与 `gacha_rates.php` 的 `reset_all` **语义完全相同**（`confirm()` + `confirm_all=1` + 服务端一次性令牌）；
差别只在于：那个页面 `confirm_all=1` 也是常驻 hidden，真正拦住重放的是令牌，本页同理。
**老实说清楚**：`confirm_all=1` 是常驻 hidden，绕过 JS 直接 POST 时它也照样是 1；
真正的一次性保护是 `action_token_check('items')`。

### 7.2 批量循环放在 `inc/gm_lobby.php`，不写在页面里

`gm_grant_memory_lobbies_batch()` 让「选中玩家」和「全服」共用同一条路径，
好处是 `scope=all`（遍历全部账号、每人各调一次）能被自测直接覆盖，而不是靠读代码猜。
页面只负责把结果映射成表格行。

### 7.3 结果卡片：只有这个动作多两列

`$result['lobby']` 为真时表头变成 `ServerId / 邮件 / 包裹 / 结果 · 失败原因`，
每个失败原因一行 `<div class="bad">`；其它 9 个动作的表头/单元格**完全不变**（`else` 分支原样保留）。

---

## 8. 部署步骤（给 srv-ops）

> 前置：本次只动 **2 个文件**。`inc/gacha.php`、`pages/gacha_rates.php` **不许碰**（刚上线）。

### 8.1 上传前校验（本地）

```bash
sha256sum inc/gm_lobby.php pages/items.php
# 期望：
# 7623fe9889eac4c26e1d8b45eaad7a21049f45c158288f7247b06cbdb74ec268  inc/gm_lobby.php
# 25f7e2b3d29fec83fcc5abf57b121c2c733e491dd958d712f9693f4767dc0c26  pages/items.php
```

### 8.2 备份（服务器）

```bash
cd /www/wwwroot/ba_cardadmin
TS=$(date +%Y%m%d_%H%M%S)
cp -a pages/items.php  "pages/items.php.bak_$TS"
# inc/gm_lobby.php 是新文件，本来就不存在，无需备份
ls -l "pages/items.php.bak_$TS"
```

### 8.3 上传 + 落位

```bash
# 1) 新增
install -m 0644 -o www -g www  inc/gm_lobby.php        /www/wwwroot/ba_cardadmin/inc/gm_lobby.php
# 2) 覆盖
install -m 0644 -o www -g www  pages/items.php          /www/wwwroot/ba_cardadmin/pages/items.php
```

> 属主/权限按现网 `pages/items.php` 的实际情况来（上面 `www:www` 只是常见值，
> **先 `ls -l pages/items.php` 看一眼再照抄**）。

### 8.4 落位后校验（服务器）

```bash
cd /www/wwwroot/ba_cardadmin
sha256sum inc/gm_lobby.php pages/items.php     # 必须与 8.1 完全一致
php -l inc/gm_lobby.php
php -l pages/items.php
```

### 8.5 页面自检（不改数据）

1. 打开「道具 / 角色」页 → 「快捷动作」卡片。
2. 应看到 10 个按钮，最后一个是 **「发放全部记忆大厅」**。
3. 按钮下方有 `每封邮件的包裹数` 输入框，默认 **60**，右侧写
   **「本次将分 5 封邮件发送（共 258 个大厅，每封 ≤ 60 个）」**。
4. 输入框改成 `258` → 那句应实时变成「本次将分 **1** 封」。
5. 再下面一行说明：**「只发放客户端认识的 258 个记忆大厅（来源：客户端表 `MemoryLobbyDBSchema`）。
   该操作幂等：重复点击不会重复获得大厅，只会多几封邮件。」**
6. 若自检不通过（id 不是 258），这里会多一条黄色 `alert-warn`，属预期（不拦截）。

### 8.6 小范围试发（建议先做，用测试账号）

用 **`AccountServerId = 4`**（测试号 `222`）单发一次：

1. 只勾选该账号 → 点「发放全部记忆大厅」→ confirm 框确认。
2. 结果卡片出现一行：`#4 | 5/5 封 | 258 个 | tag-ok 已发出 5/5 封`。
3. 查库核对（只读）：

```sql
SELECT ServerId, AccountServerId, Comment, Sender, SendDate,
       json_array_length(ParcelInfos) AS parcels
FROM Mails WHERE AccountServerId = 4 ORDER BY ServerId DESC LIMIT 6;
```

期望：5 行，`Comment` 依次 `记忆大厅全部解锁（1/5）…（5/5）`，
`parcels` = `60,60,60,60,18`，`Sender='Schale'`。

4. 再点一次同一个按钮 → 仍生成 5 封新邮件；玩家**领取后**大厅数量**不会翻倍**
   （`ParcelResolver.UpdateMemoryLobby()` 去重）。这一步就是幂等验证。

> ⚠️ 现场注意：`GM_LOBBY_MAIL_CAPACITY.md` 里 srv-ops 之前测过 5 封信
> （`ServerId` 128/129/130/131/132）都还挂在 `AccountServerId=4` 的邮箱里没领取。
> **试发后建议把 131/132（500/1000 个包裹的容量测试）删掉**，别让测试号邮箱里堆垃圾。

### 8.7 正式发放

- 小范围：勾选玩家 → 点按钮 → confirm。
- 全服：勾上「**对全服执行**」→ 点按钮 → confirm 框会显示「全服全部玩家」。

**性能提示**：默认 60 一封 = **每人 5 次 HTTP POST**，串行。全服 N 人 = `5 × N` 次请求。
若账号数较多（比如 100 人 → 500 次请求），注意 PHP `max_execution_time` 与网关超时；
稳妥做法是分几批勾选发放，或把 `每封邮件的包裹数` 改成 **258**（**每人 1 次**，
实测 13 KB 请求体、HTTP 200，强烈推荐全服时用这个值）。

### 8.8 回滚

```bash
cd /www/wwwroot/ba_cardadmin
cp -a "pages/items.php.bak_$TS" pages/items.php
rm -f inc/gm_lobby.php
php -l pages/items.php
```

回滚后页面回到 9 个按钮，已发出的邮件留在邮箱里（删邮件用「邮件」页或 SQL，不在本次范围）。

---

## 9. 已知边界

1. **邮件要玩家自己领**：动作成功 ≠ 到账，只是「邮件进邮箱」。玩家在游戏里点领取，
   走 `ParcelResolver.UpdateMemoryLobby()` 才真正写 `MemoryLobbies` 表。结果卡片里也写了这句。
2. **幂等的颗粒度**：幂等发生在「领取」那一步，不在「发信」那一步。重复点会多 5 封邮件，
   玩家得领一次才有大厅；重复领不会重复加。极端情况下邮箱会堆重复附件，删掉即可。
3. **`ok` 的判定**：玩家行 `ok=true` 要求「所有封都 2xx 且至少发出一封」。
   有 1 封失败 → 该玩家算失败，但成功的那几封**已经进邮箱**，重跑安全。
4. **没有做「删除已发邮件」**：本次只负责发放。
5. **未实机验证的部分**：本地无 PHP 服务端与数据库，**页面渲染没在真机上点过**
   （靠 `php -l` + 被调函数存在性 + HTML 结构对齐基准来保证）。§8.5/8.6 就是给现场补这一环的。
