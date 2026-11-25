<?php
/**
 * pages/players.php —— 玩家列表（全部账号 / 筛选 / 批量操作）
 *
 * 数据来自 Shittim admin API（唯一真源）；卡密绑定来自 MySQL card_players；
 * 设备/登录次数来自桥接账号镜像 accounts.db（只读）。
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';

require_login();

/* ------------------------------------------------------------------ POST --- */
if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $action = post_q('action', '');
    $ids    = array();
    foreach ((array)(isset($_POST['sid']) ? $_POST['sid'] : array()) as $v) {
        $v = (int)$v;
        if ($v > 0) {
            $ids[$v] = $v;
        }
    }
    $ids = array_values($ids);

    if ($action === 'ban' || $action === 'unban') {
        if (!$ids) {
            flash_set('没有选中任何玩家', 'err');
            redirect_self();
        }
        $ban   = ($action === 'ban');
        $ok    = 0;
        $fails = array();
        $diffs = array();
        foreach ($ids as $sid) {
            /* F3：记旧 State，审计里给「旧值→新值」 */
            $d    = ba_account_detail($sid);
            $old  = ($d['ok'] && isset($d['data']['state'])) ? (int)$d['data']['state'] : null;
            $r    = player_set_ban($sid, $ban);
            if ($r['ok']) {
                $ok++;
            } else {
                $fails[] = 'ServerId ' . $sid . '：' . $r['error'];
            }
            $diffs[] = $sid . ':' . ($old === null ? '?' : $old) . '→' . ($ban ? '2' : '1')
                     . ($r['ok'] ? '' : '(fail)');
        }
        audit_log($ban ? 'player.ban' : 'player.unban', implode(',', $ids),
            'State ' . implode(' ', array_slice($diffs, 0, 80)) . ' 成功 ' . $ok . ' 个');
        if ($fails) {
            flash_set(($ban ? '封禁' : '解封') . ' 完成 ' . $ok . ' 个，失败 ' . count($fails) . ' 个：' . implode('；', $fails), 'err');
        } else {
            flash_set(($ban ? '已封禁 ' : '已解封 ') . $ok . ' 个账号（下次登录生效）', 'ok');
        }
        redirect_self();
    }

    if ($action === 'bind_card') {
        $cardId = post_int('card_id', 0);
        $sid    = post_int('server_id', 0);
        $pub    = post_int('publisher_id', 0);
        if ($cardId <= 0 || $sid <= 0) {
            flash_set('绑定失败：卡密或玩家无效', 'err');
            redirect_self();
        }
        $r = player_bind_card($cardId, $pub, $sid, 'manual', '', current_admin() ? current_admin()['username'] : '');
        audit_log('player.bind_card', 'card#' . $cardId . '→server#' . $sid, $r['ok'] ? 'ok' : $r['error']);
        flash_set($r['ok'] ? '已绑定卡密到该玩家' : ('绑定失败：' . $r['error']), $r['ok'] ? 'ok' : 'err');
        redirect_self();
    }

    if ($action === 'unbind_card') {
        $cardId = post_int('card_id', 0);
        $r = player_unbind_card($cardId);
        audit_log('player.unbind_card', 'card#' . $cardId, $r['ok'] ? 'ok' : $r['error']);
        flash_set($r['ok'] ? '已解绑' : ('解绑失败：' . $r['error']), $r['ok'] ? 'ok' : 'err');
        redirect_self();
    }

    flash_set('未知操作', 'err');
    redirect_self();
}

/* ------------------------------------------------------------------ 查询 --- */
$q       = get_q('q', '');
$stateF  = get_q('state', '');
$onlyCard = get_int('has_card', 0) === 1;

$roster = player_roster(array('q' => $q, 'state' => $stateF, 'has_card' => $onlyCard));
$health = ba_health();

/* 货币摘要：玩家数不多时逐人取一次（上限 30，避免把服务端打爆） */
$money = array();
if ($roster['ok'] && count($roster['rows']) <= 30) {
    foreach ($roster['rows'] as $row) {
        $d = player_currency_dict($row['server_id']);
        if ($d) {
            $money[$row['server_id']] = array(
                'gem'  => player_currency_key($d, array('Gem', 'GemBonus')),
                'gold' => player_currency_key($d, array('Gold')),
                'ap'   => player_currency_key($d, array('ActionPoint')),
            );
        }
    }
}

/* 可绑定的卡密（给详情页外的快速绑定用） */
$allCards = array();
try {
    $allCards = db_all("SELECT id, card_key, status FROM cards ORDER BY id DESC LIMIT 500");
} catch (Throwable $e) {
    $allCards = array();
}

$states = player_state_map();

page_header('玩家列表', 'players');
if (!$roster['ok']) {
    echo '<div class="srv-down">读取不到游戏服务端：<b>' . e($roster['error']) . '</b><br>'
        . '检查 <code>' . e(ba_admin_base()) . '</code> 是否在跑，以及「系统设置」里的 Admin Key 是否与服务端一致。</div>';
}
?>

<div class="stats">
  <div class="stat">
    <div class="stat-k">玩家总数</div>
    <div class="stat-v"><?php echo number_format($roster['ok'] ? count($roster['rows']) : 0); ?></div>
    <div class="stat-sub"><?php echo $q !== '' || $stateF !== '' || $onlyCard ? '筛选结果' : '全部账号'; ?></div>
  </div>
  <div class="stat">
    <div class="stat-k">已绑定卡密</div>
    <div class="stat-v"><?php
      $n = 0;
      foreach ((array)$roster['rows'] as $r0) {
          if ($r0['cards']) {
              $n++;
          }
      }
      echo number_format($n);
    ?></div>
  </div>
  <div class="stat <?php echo $health['ok'] ? 'stat-ok' : 'stat-err'; ?>">
    <div class="stat-k">游戏服务端</div>
    <div class="stat-v small" style="font-size:15px"><?php echo $health['ok'] ? '在线' : '离线'; ?></div>
    <div class="stat-sub"><?php echo $health['ok'] ? ('响应 ' . $health['ms'] . ' ms') : e(str_limit($health['error'], 40)); ?></div>
  </div>
  <div class="stat">
    <div class="stat-k">封禁中</div>
    <div class="stat-v"><?php
      $n = 0;
      foreach ((array)$roster['rows'] as $r0) {
          if (player_is_banned($r0['state'])) {
              $n++;
          }
      }
      echo number_format($n);
    ?></div>
  </div>
</div>

<section class="card">
  <div class="card-h">
    <h2>全部玩家</h2>
    <div class="card-h-act">
      <a class="btn btn-sm" href="<?php echo e(u('pages/players.php')); ?>">刷新</a>
    </div>
  </div>

  <form method="get" action="<?php echo e(u('pages/players.php')); ?>" class="inline" style="margin-bottom:10px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
    <input type="search" name="q" value="<?php echo e($q); ?>" placeholder="昵称 / ServerId / 卡密 / 设备号 / publisherId" style="min-width:280px">
    <select name="state">
      <option value="">全部状态</option>
      <?php foreach ($states as $sid0 => $sv) { ?>
        <option value="<?php echo e($sv[0]); ?>"<?php echo strcasecmp($stateF, $sv[0]) === 0 ? ' selected' : ''; ?>><?php echo e($sv[1]); ?>（<?php echo e($sv[0]); ?>）</option>
      <?php } ?>
    </select>
    <label class="small muted"><input type="checkbox" name="has_card" value="1"<?php echo $onlyCard ? ' checked' : ''; ?>> 只看有卡密的</label>
    <button type="submit" class="btn btn-primary btn-sm">筛选</button>
    <?php if ($q !== '' || $stateF !== '' || $onlyCard) { ?>
      <a class="btn btn-sm" href="<?php echo e(u('pages/players.php')); ?>">清空</a>
    <?php } ?>
  </form>

  <?php if (!$roster['rows'] && $roster['ok']) { ?>
    <p class="muted">没有匹配的玩家。玩家第一次登录游戏后会自动出现在这里。</p>
  <?php } else { ?>
  <form method="post" action="<?php echo e(u('pages/players.php')); ?>" id="players-form">
    <?php echo csrf_field(); ?>
    <div class="bulkbar">
      <span class="bulk-count" id="bulk-count">已选 0 人</span>
      <button type="submit" name="action" value="ban" class="btn btn-sm btn-danger"
              onclick="return window.__pcount() > 0 ? confirm('确认封禁选中账号？封禁后下次登录会被拒绝。') : (alert('先勾选玩家'), false);">封禁</button>
      <button type="submit" name="action" value="unban" class="btn btn-sm btn-warn"
              onclick="return window.__pcount() > 0 ? true : (alert('先勾选玩家'), false);">解封</button>
      <button type="button" class="btn btn-sm btn-primary" id="bulk-reward"
              onclick="return window.__bulkReward();">批量发奖 →</button>
      <span class="muted small">批量发奖会带着选中的人跳到发奖页</span>
    </div>

    <div class="table-wrap">
    <table class="tbl tbl-players">
      <thead>
        <tr>
          <th style="width:34px"><input type="checkbox" id="check-all" title="全选"></th>
          <th>玩家</th>
          <th>等级 / EXP</th>
          <th>青辉石 / 金币 / 体力</th>
          <th>卡密</th>
          <th>设备</th>
          <th>最后登录</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
      <?php foreach ($roster['rows'] as $r) { $sid = (int)$r['server_id']; ?>
        <tr>
          <td><input type="checkbox" name="sid[]" value="<?php echo $sid; ?>" class="pick"></td>
          <td>
            <div class="who"><?php echo e($r['nickname'] !== '' ? $r['nickname'] : '（无昵称）'); ?>
              <span class="muted small">#<?php echo $sid; ?></span></div>
            <div class="sub">publisher <code><?php echo e($r['publisher_id'] !== '' ? $r['publisher_id'] : '—'); ?></code></div>
          </td>
          <td class="nowrap">Lv <b><?php echo number_format($r['level']); ?></b>
            <div class="sub">EXP <?php echo number_format($r['exp']); ?></div></td>
          <td class="nowrap">
            <?php if (isset($money[$sid])) { ?>
              <span title="青辉石">💎 <?php echo number_format($money[$sid]['gem']); ?></span>
              <div class="sub">💰 <?php echo number_format($money[$sid]['gold']); ?> ·
                ⚡ <?php echo number_format($money[$sid]['ap']); ?></div>
            <?php } else { ?>
              <span class="muted small">—</span>
            <?php } ?>
          </td>
          <td>
            <?php if ($r['cards']) { foreach ($r['cards'] as $mc) { ?>
              <div><code class="small"><?php echo e(mask_card($mc['card_key'])); ?></code>
                <?php echo $mc['status'] === 'active' ? '<span class="tag tag-ok">可用</span>' : '<span class="tag tag-err">停用</span>'; ?>
              </div>
            <?php } } else { ?>
              <span class="muted small">未绑定</span>
            <?php } ?>
          </td>
          <td>
            <?php if ($r['device'] !== '') { ?>
              <code class="small" title="<?php echo e($r['device']); ?>"><?php echo e(str_limit($r['device'], 12)); ?></code>
              <div class="sub">登录 <?php echo number_format($r['login_count']); ?> 次</div>
            <?php } else { ?>
              <span class="muted small">—</span>
            <?php } ?>
          </td>
          <td class="nowrap"><?php echo e(player_dt($r['last_connect'] !== '' ? $r['last_connect'] : $r['bridge_last'])); ?></td>
          <td>
            <?php if (player_is_banned($r['state'])) { ?>
              <span class="tag tag-err">已封禁</span>
            <?php } else { ?>
              <span class="tag tag-ok"><?php echo e(player_state_label($r['state'])); ?></span>
            <?php } ?>
          </td>
          <td>
            <div class="row-actions">
              <a class="btn btn-xs" href="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>">详情</a>
              <a class="btn btn-xs" href="<?php echo e(u('pages/mail.php?sid=' . $sid)); ?>">发奖</a>
              <button type="submit" name="action" value="<?php echo player_is_banned($r['state']) ? 'unban' : 'ban'; ?>"
                      class="btn btn-xs <?php echo player_is_banned($r['state']) ? 'btn-warn' : 'btn-danger'; ?>"
                      formnovalidate
                      onclick="this.form.querySelectorAll('.pick').forEach(function(c){c.checked=(c.value==='<?php echo $sid; ?>');});">
                <?php echo player_is_banned($r['state']) ? '解封' : '封禁'; ?>
              </button>
            </div>
          </td>
        </tr>
      <?php } ?>
      </tbody>
    </table>
    </div>
  </form>
  <?php } ?>
</section>

<script>
(function () {
  var all = document.getElementById('check-all');
  var picks = Array.prototype.slice.call(document.querySelectorAll('.pick'));
  var counter = document.getElementById('bulk-count');
  function n() { return picks.filter(function (c) { return c.checked; }).length; }
  function sync() {
    if (counter) { counter.textContent = '已选 ' + n() + ' 人'; }
  }
  window.__pcount = n;
  window.__bulkReward = function () {
    var ids = picks.filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
    if (!ids.length) { alert('先勾选玩家'); return false; }
    location.href = <?php echo json_encode(u('pages/mail.php')); ?> + '?sid=' + ids.join(',');
    return false;
  };
  if (all) {
    all.addEventListener('change', function () {
      picks.forEach(function (c) { c.checked = all.checked; });
      sync();
    });
  }
  picks.forEach(function (c) { c.addEventListener('change', sync); });
  sync();
})();
</script>

<?php page_footer(); ?>
