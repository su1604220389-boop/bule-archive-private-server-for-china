<?php
/**
 * pages/dashboard.php — 仪表盘
 * 也可由 index.php include（此时脚本名是 index.php）
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';

require_login();

/* 手动同步 / 导入现有卡密（PRG，避免刷新重复提交） */
if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $r = sync_do_web_action();
    if ($r !== null) {
        flash_set($r['msg'], $r['ok'] ? 'ok' : 'err');
        redirect_self();
    }
    flash_set('未知操作', 'err');
    redirect_self();
}

$now    = time();
$today0 = strtotime('today');
$today  = date('Y-m-d 00:00:00');

$stat = array(
    'total'        => 0,
    'active'       => 0,
    'expired'      => 0,
    'disabled'     => 0,
    'devices'      => 0,
    'cards_bound'  => 0,
    'new_today'    => 0,
    'logins_today' => 0,
);
$page_errors = array();
try {
    $stat['total']        = (int)db_val('SELECT COUNT(*) FROM cards', array(), 0);
    $stat['active']       = (int)db_val(
        "SELECT COUNT(*) FROM cards WHERE status = 'active' AND (expire_at = 0 OR expire_at >= ?)",
        array($now), 0
    );
    $stat['expired']      = (int)db_val(
        'SELECT COUNT(*) FROM cards WHERE expire_at > 0 AND expire_at < ?', array($now), 0
    );
    $stat['disabled']     = (int)db_val("SELECT COUNT(*) FROM cards WHERE status = 'disabled'", array(), 0);
    $stat['devices']      = (int)db_val('SELECT COUNT(*) FROM card_devices', array(), 0);
    $stat['cards_bound']  = (int)db_val('SELECT COUNT(DISTINCT card_id) FROM card_devices', array(), 0);
    $stat['new_today']    = (int)db_val('SELECT COUNT(*) FROM cards WHERE created_at >= ?', array($today), 0);
    $stat['logins_today'] = (int)db_val(
        "SELECT COUNT(*) FROM login_logs WHERE ts >= ? AND result = 'ok'", array($today0), 0
    );
} catch (Throwable $e) {
    $page_errors[] = '统计查询失败：' . $e->getMessage();
}

$recent = array();
try {
    $recent = db_all('SELECT id, card_key, device_id, result, source, ts FROM login_logs ORDER BY ts DESC, id DESC LIMIT 20');
} catch (Throwable $e) {
    $recent = array();
}

$sync = sync_status();

/* ---- 玩家域（Shittim admin API）---- */
$health   = ba_health();
$roster   = $health['ok'] ? player_roster(array()) : array('ok' => false, 'rows' => array(), 'error' => '服务端离线');
$p_rows   = isset($roster['rows']) ? $roster['rows'] : array();
$p_total  = count($p_rows);
$p_banned = 0;
$p_card   = 0;
$p_today  = 0;
$today0ts = strtotime('today');
foreach ($p_rows as $pr) {
    if (player_is_banned($pr['state'])) {
        $p_banned++;
    }
    if ($pr['cards']) {
        $p_card++;
    }
    $t = $pr['last_connect'] !== '' ? $pr['last_connect'] : $pr['bridge_last'];
    if ($t !== '' && ($ts0 = strtotime($t)) !== false && $ts0 >= $today0ts) {
        $p_today++;
    }
}
$opsRecent = panel_op_recent(5);

page_header('仪表盘', 'dashboard');
foreach ($page_errors as $pe) {
    echo alert_box($pe, 'err');
}
if (!$health['ok']) {
    echo '<div class="srv-down">游戏服务端连不上：<b>' . e($health['error']) . '</b>（'
        . e(ba_admin_base()) . '）— 卡密功能不受影响，玩家相关页面会显示为空。</div>';
}
?>

<?php echo alert_box('卡密改动不会立刻生效：cron 每分钟把 MySQL 导出到 cards.json，'
    . '所以最长约 60 秒后客户端才会看到变化。玩家域的发奖/改数值是<b>实时</b>写入游戏服务端的。', 'info'); ?>

<div class="stats">
  <div class="stat">
    <div class="stat-k">总卡密</div>
    <div class="stat-v"><?php echo number_format($stat['total']); ?></div>
  </div>
  <div class="stat stat-ok">
    <div class="stat-k">可用</div>
    <div class="stat-v"><?php echo number_format($stat['active']); ?></div>
    <div class="stat-sub">启用且未过期</div>
  </div>
  <div class="stat stat-warn">
    <div class="stat-k">已过期</div>
    <div class="stat-v"><?php echo number_format($stat['expired']); ?></div>
  </div>
  <div class="stat stat-err">
    <div class="stat-k">已禁用</div>
    <div class="stat-v"><?php echo number_format($stat['disabled']); ?></div>
  </div>
  <div class="stat">
    <div class="stat-k">已绑定设备</div>
    <div class="stat-v"><?php echo number_format($stat['devices']); ?></div>
    <div class="stat-sub"><?php echo number_format($stat['cards_bound']); ?> 张卡绑过设备</div>
  </div>
  <div class="stat">
    <div class="stat-k">今日新增</div>
    <div class="stat-v"><?php echo number_format($stat['new_today']); ?></div>
  </div>
  <div class="stat">
    <div class="stat-k">今日登录次数</div>
    <div class="stat-v"><?php echo number_format($stat['logins_today']); ?></div>
    <div class="stat-sub">来源：login_logs</div>
  </div>
</div>

<div class="stats">
  <div class="stat <?php echo $health['ok'] ? 'stat-ok' : 'stat-err'; ?>">
    <div class="stat-k">游戏服务端</div>
    <div class="stat-v" style="font-size:18px"><?php echo $health['ok'] ? '在线' : '离线'; ?></div>
    <div class="stat-sub"><?php echo $health['ok'] ? ('响应 ' . (int)$health['ms'] . ' ms') : e(str_limit($health['error'], 46)); ?></div>
  </div>
  <div class="stat">
    <div class="stat-k">注册玩家</div>
    <div class="stat-v"><?php echo number_format($p_total); ?></div>
    <div class="stat-sub">Shittim 账号表</div>
  </div>
  <div class="stat">
    <div class="stat-k">今日活跃</div>
    <div class="stat-v"><?php echo number_format($p_today); ?></div>
    <div class="stat-sub">今天连过的号</div>
  </div>
  <div class="stat">
    <div class="stat-k">已绑卡密玩家</div>
    <div class="stat-v"><?php echo number_format($p_card); ?></div>
    <div class="stat-sub">共 <?php echo number_format($stat['total']); ?> 张卡</div>
  </div>
  <div class="stat <?php echo $p_banned ? 'stat-err' : ''; ?>">
    <div class="stat-k">封禁中</div>
    <div class="stat-v"><?php echo number_format($p_banned); ?></div>
  </div>
</div>

<div class="cols">
  <section class="card">
    <div class="card-h"><h2>玩家快捷入口</h2>
      <div class="card-h-act"><a class="btn btn-sm" href="<?php echo e(u('pages/players.php')); ?>">全部玩家</a></div>
    </div>
    <div class="quick" style="margin:0">
      <a class="btn" href="<?php echo e(u('pages/players.php')); ?>">👥 玩家列表</a>
      <a class="btn" href="<?php echo e(u('pages/mail.php')); ?>">🎁 发奖 / 邮件</a>
      <a class="btn" href="<?php echo e(u('pages/currency.php')); ?>">💎 货币调整</a>
      <a class="btn" href="<?php echo e(u('pages/items.php')); ?>">🧰 道具 / 角色</a>
      <a class="btn" href="<?php echo e(u('pages/console.php')); ?>">⌨ GM 命令台</a>
    </div>
    <?php if ($opsRecent) { ?>
      <table class="kv" style="margin-top:10px">
        <?php foreach ($opsRecent as $op) {
            $pl = json_decode((string)$op['payload'], true);
            $desc = (string)$op['action'];
            if (is_array($pl) && isset($pl['parcels'])) {
                $bits = array();
                foreach ($pl['parcels'] as $pc0) {
                    $bits[] = $pc0['type'] . '×' . number_format((int)$pc0['amount']);
                }
                $desc .= '：' . implode(' + ', $bits);
            } elseif (is_array($pl) && isset($pl['command'])) {
                $desc .= '：' . (string)$pl['command'];
            }
            ?>
          <tr>
            <th class="small muted"><?php echo e(fmt_ts((int)$op['ts'])); ?></th>
            <td class="small"><?php echo e(str_limit($desc, 50)); ?>
              <span class="muted">（成功 <?php echo (int)$op['ok_count']; ?><?php echo (int)$op['fail_count'] ? '，失败 ' . (int)$op['fail_count'] : ''; ?>）</span></td>
          </tr>
        <?php } ?>
      </table>
    <?php } else { ?>
      <p class="muted small" style="margin-top:8px">还没有玩家域操作记录。发奖 / 改货币 / 封禁都会记在这里。</p>
    <?php } ?>
  </section>

  <section class="card">
    <div class="card-h"><h2>最近活跃玩家</h2>
      <div class="card-h-act"><a class="btn btn-sm" href="<?php echo e(u('pages/players.php')); ?>">查看全部</a></div>
    </div>
    <?php if (!$p_rows) { ?>
      <p class="muted small"><?php echo $health['ok'] ? '还没有玩家登录过。' : '服务端离线，读不到玩家。'; ?></p>
    <?php } else { ?>
      <table class="tbl">
        <thead><tr><th>玩家</th><th>等级</th><th>最后连接</th><th>状态</th></tr></thead>
        <tbody>
        <?php $shown = 0; foreach ($p_rows as $pr) { if ($shown++ >= 6) { break; } ?>
          <tr>
            <td><a href="<?php echo e(u('pages/player_detail.php?sid=' . (int)$pr['server_id'])); ?>"><?php echo e($pr['nickname'] !== '' ? $pr['nickname'] : ('#' . (int)$pr['server_id'])); ?></a></td>
            <td><?php echo (int)$pr['level']; ?></td>
            <td class="small nowrap"><?php echo e(player_dt($pr['last_connect'] !== '' ? $pr['last_connect'] : $pr['bridge_last'])); ?></td>
            <td><?php echo player_is_banned($pr['state']) ? '<span class="tag tag-err">封禁</span>'
                      : '<span class="tag tag-ok">' . e(player_state_label($pr['state'])) . '</span>'; ?></td>
          </tr>
        <?php } ?>
        </tbody>
      </table>
    <?php } ?>
  </section>
</div>

<div class="cols">
  <section class="card">
    <div class="card-h">
      <h2>同步状态</h2>
      <div class="card-h-act">
        <form method="post" action="<?php echo e(u('pages/dashboard.php')); ?>" class="inline">
          <?php echo csrf_field(); ?>
          <input type="hidden" name="action" value="sync_now">
          <button type="submit" class="btn btn-primary btn-sm">立即同步</button>
        </form>
      </div>
    </div>
    <table class="kv">
      <tr><th>最后同步</th>
        <td><?php echo $sync['last_sync_at'] > 0 ? e(fmt_ts($sync['last_sync_at'])) : '<span class="bad">从未同步</span>'; ?>
            <?php if ($sync['last_sync_at'] > 0) { ?>
              <span class="muted small">（<?php echo e(fmt_ts($sync['last_sync_at'])); ?> 起
              <?php echo (int)floor(($now - $sync['last_sync_at']) / 60); ?> 分钟前）</span>
            <?php } ?></td></tr>
      <tr><th>上次导出</th><td><?php echo number_format($sync['last_count']); ?> 个卡密
          <?php if ($sync['last_source'] !== '') { ?><span class="muted small">（来源 <?php echo e($sync['last_source']); ?>）</span><?php } ?></td></tr>
      <tr><th>cards.json</th>
        <td><code class="small"><?php echo e($sync['json_path']); ?></code><br>
          <?php if (!$sync['exists']) { ?>
            <span class="bad">文件不存在</span>
          <?php } else { ?>
            文件内 <?php echo is_int($sync['file_cards']) ? number_format($sync['file_cards']) . ' 个卡密' : e((string)$sync['file_cards']); ?> ·
            <?php echo e(bytes_human($sync['bytes'])); ?> ·
            mtime <?php echo e(fmt_ts($sync['mtime'])); ?>
          <?php } ?></td></tr>
      <tr><th>数据库</th><td><?php echo number_format($sync['db_all']); ?> 张卡（active
          <?php echo number_format($sync['db_active']); ?>）</td></tr>
      <tr><th>可写性</th>
        <td><?php echo $sync['dir_writable'] ? '<span class="ok">当前 PHP 用户可写目录（可面板直连同步）</span>'
            : '<span class="warn">当前 PHP 用户不可写，点"立即同步"会写标记由 cron 执行</span>'; ?>
          <?php if ($sync['flag_pending']) { ?><br><span class="warn">有一个待执行的同步请求（等 cron）</span><?php } ?></td></tr>
    </table>
    <?php if (!$sync['dir_writable']) { ?>
      <p class="muted small">cron 建议以 root 跑（宝塔计划任务默认就是 root）：
        <code>* * * * * /usr/bin/php <?php echo e(str_replace('\\', '/', dirname(__DIR__))); ?>/cron/sync_cards.php</code></p>
    <?php } ?>
  </section>

  <section class="card">
    <div class="card-h"><h2>最近 20 条登录记录</h2>
      <div class="card-h-act"><a class="btn btn-sm" href="<?php echo e(u('pages/logs.php')); ?>">全部日志</a></div>
    </div>
    <?php if (!$recent) { ?>
      <p class="muted">还没有登录记录。到「登录日志」页点一次「解析 sdk.log」可以把历史日志导入。</p>
    <?php } else { ?>
      <div class="table-wrap">
      <table class="tbl">
        <thead><tr><th>时间</th><th>卡密</th><th>设备</th><th>结果</th><th>来源</th></tr></thead>
        <tbody>
        <?php foreach ($recent as $r) { ?>
          <tr>
            <td class="nowrap"><?php echo e(fmt_ts((int)$r['ts'])); ?></td>
            <td><code><?php echo e(mask_card((string)$r['card_key'])); ?></code></td>
            <td><code class="small"><?php echo e((string)$r['device_id'] === '' ? '—' : str_limit((string)$r['device_id'], 20)); ?></code></td>
            <td>
              <?php
              $res = (string)$r['result'];
              if ($res === 'ok') {
                  echo '<span class="tag tag-ok">成功</span>';
              } elseif ($res === 'reject') {
                  echo '<span class="tag tag-err">卡密错误</span>';
              } elseif ($res === 'expired') {
                  echo '<span class="tag tag-warn">已过期</span>';
              } else {
                  echo '<span class="tag tag-warn">设备超限</span>';
              }
              ?>
            </td>
            <td class="muted small"><?php echo e((string)$r['source']); ?></td>
          </tr>
        <?php } ?>
        </tbody>
      </table>
      </div>
    <?php } ?>
  </section>
</div>

<div class="quick">
  <a class="btn" href="<?php echo e(u('pages/cards_new.php')); ?>">＋ 新建卡密</a>
  <a class="btn" href="<?php echo e(u('pages/cards_new.php#batch')); ?>">⚡ 批量生成</a>
  <a class="btn" href="<?php echo e(u('pages/cards_import.php')); ?>">⇩ 批量导入</a>
  <form method="post" action="<?php echo e(u('pages/cards_export.php')); ?>" class="inline">
    <?php echo csrf_field(); ?>
    <input type="hidden" name="format" value="csv">
    <button type="submit" class="btn">⇧ 导出 CSV</button>
  </form>
  <a class="btn" href="<?php echo e(u('pages/logs.php')); ?>">☰ 登录日志</a>
</div>

<?php page_footer(); ?>
