<?php
/**
 * pages/items.php —— 道具 / 角色 / 批量快捷操作
 *
 * 两条路：
 *   · 发道具 → POST /api/admin/items/give（精确、可指定叠加或覆盖）
 *   · 快捷动作（全角色 / 满级 / 解锁 …）→ POST /api/admin/command（GM 命令，Uid=目标玩家）
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';

require_login();

/** 一键快捷动作：key => [标题, 命令, 说明] */
function item_quick_actions()
{
    return array(
        'giveall'         => array('发全部角色',      'giveall',                  '把全部角色塞进该账号（含未实装的默认星级）'),
        'maxall'          => array('全角色满级',      'max all',                  'Lv90 + 满星 + 技能 10/5/10/10 + 好感满'),
        'giveallequip'    => array('发全部装备',      'giveallequip',             '把全部装备塞进背包'),
        'unlock_campaign' => array('解锁主线',        'unlockall campaign',       '主线关卡全部解锁'),
        'unlock_story'    => array('解锁剧情',        'unlockall story',          '剧情全部解锁'),
        'unlock_week'     => array('解锁周常',        'unlockall weekdungeon',    '周常地下城全部解锁'),
        'unlock_school'   => array('解锁学院',        'unlockall schooldungeon',  '学院地下城全部解锁'),
        'unlock_mission'  => array('解锁任务',        'unlockall mission',        '任务全部解锁'),
        'battlepass'      => array('解锁通行证',      'unlockbattlepass',         '战斗通行证解锁'),
    );
}

$preselect = array();
if (isset($_GET['sid'])) {
    foreach ((array)$_GET['sid'] as $v) {
        foreach (explode(',', (string)$v) as $p) {
            $p = (int)trim($p);
            if ($p > 0) {
                $preselect[$p] = $p;
            }
        }
    }
}

$result = null;

if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    action_token_check('items');

    $scope = post_q('scope', 'selected');
    $mode  = post_q('mode', 'quick');       // quick | item | command

    $ids = array();
    foreach ((array)(isset($_POST['sid']) ? $_POST['sid'] : array()) as $v) {
        $v = (int)$v;
        if ($v > 0) {
            $ids[$v] = $v;
        }
    }
    $ids = array_values($ids);
    if ($scope === 'all') {
        $roster = player_roster(array());
        $ids = array();
        if ($roster['ok']) {
            foreach ($roster['rows'] as $rr) {
                $ids[] = (int)$rr['server_id'];
            }
        }
    }
    if (!$ids) {
        flash_set('没有选中任何玩家', 'err');
        redirect_self();
    }

    $batch = substr(bin2hex(random_bytes(6)), 0, 12);
    $rows  = array();
    $okN   = 0;
    $failN = 0;
    $label = '';

    if ($mode === 'quick') {
        $key   = post_q('quick', '');
        $acts  = item_quick_actions();
        if (!isset($acts[$key])) {
            flash_set('未知的快捷动作', 'err');
            redirect_self();
        }
        $label = $acts[$key][0];
        $cmd   = $acts[$key][1];
        foreach ($ids as $sid) {
            $r = ba_command($sid, $cmd);
            $out = ($r['ok'] && isset($r['data']['output'])) ? (string)$r['data']['output'] : '';
            $rows[] = array('sid' => $sid, 'ok' => (bool)$r['ok'],
                            'msg' => $r['ok'] ? (str_limit($out !== '' ? $out : '已执行', 60)) : $r['error']);
            $r['ok'] ? $okN++ : $failN++;
        }
        panel_op_log('quick.' . $key, $ids, array('batch' => $batch, 'command' => $cmd), $okN, $failN, $batch);
    } elseif ($mode === 'item') {
        $uid = post_int('unique_id', 0);
        $amt = post_int('amount', 1);
        $exact = post_int('set_exact', 0) === 1;
        if ($uid <= 0) {
            flash_set('道具 Id 无效', 'err');
            redirect_self();
        }
        $label = '道具 #' . $uid . ($exact ? '（覆盖为 ' : '（+') . $amt . '）';
        foreach ($ids as $sid) {
            $r = ba_item_give($sid, $uid, $amt, $exact);
            $rows[] = array('sid' => $sid, 'ok' => (bool)$r['ok'], 'msg' => $r['ok'] ? '已发放' : $r['error']);
            $r['ok'] ? $okN++ : $failN++;
        }
        panel_op_log('item.give', $ids, array('batch' => $batch, 'unique_id' => $uid, 'amount' => $amt, 'exact' => $exact), $okN, $failN, $batch);
    } else {
        $cmd = trim((string)post_q('command', ''));
        if ($cmd === '') {
            flash_set('命令不能为空', 'err');
            redirect_self();
        }
        /* 角色排除名单：命令里点名客户端解析不了的角色就直接拒绝 */
        $denyErr = ba_validate_command($cmd);
        if ($denyErr !== '') {
            flash_set($denyErr, 'err');
            redirect_self();
        }
        $label = $cmd;
        foreach ($ids as $sid) {
            $r = ba_command($sid, $cmd);
            $out = ($r['ok'] && isset($r['data']['output'])) ? (string)$r['data']['output'] : '';
            $rows[] = array('sid' => $sid, 'ok' => (bool)$r['ok'],
                            'msg' => $r['ok'] ? (str_limit($out !== '' ? $out : '已执行', 60)) : $r['error']);
            $r['ok'] ? $okN++ : $failN++;
        }
        panel_op_log('command.batch', $ids, array('batch' => $batch, 'command' => $cmd), $okN, $failN, $batch);
    }

    audit_log('player.bulk_op', implode(',', $ids), $mode . ' ' . $label . ' ok=' . $okN . ' fail=' . $failN);
    $result = array('batch' => $batch, 'rows' => $rows, 'ok' => $okN, 'fail' => $failN, 'label' => $label);
}

$roster = player_roster(array());
$allPlayers = $roster['ok'] ? $roster['rows'] : array();

$q = get_q('q', '');
$itemRows = array();
$ri = ba_static_items($q, 300);
if ($ri['ok'] && is_array($ri['data'])) {
    $itemRows = $ri['data'];
}
$charRows = array();
$rc = ba_static_characters($q, 500);
if ($rc['ok'] && is_array($rc['data'])) {
    $charRows = $rc['data'];
}

page_header('道具 / 角色', 'items');
if (!$roster['ok']) {
    echo '<div class="srv-down">读取不到游戏服务端：<b>' . e($roster['error']) . '</b></div>';
}
$deniedIds = ba_denied_character_ids();
echo alert_box('当前客户端有 ' . count($deniedIds) . ' 个角色无法解析（会导致登录同步失败），'
    . '服务端已在角色表里剔除它们，面板也会拒绝任何点名它们的操作：'
    . implode('、', $deniedIds), 'info');
?>

<?php if ($result) { ?>
<section class="card card-result">
  <div class="card-h"><h2>执行结果 · <?php echo e($result['label']); ?></h2>
    <div class="card-h-act">
      <span class="tag <?php echo $result['fail'] ? 'tag-warn' : 'tag-ok'; ?>">
        成功 <?php echo (int)$result['ok']; ?> / 失败 <?php echo (int)$result['fail']; ?></span>
      <code class="small">batch <?php echo e($result['batch']); ?></code>
    </div>
  </div>
  <div class="table-wrap">
  <table class="tbl">
    <thead><tr><th>ServerId</th><th>结果</th></tr></thead>
    <tbody>
    <?php foreach ($result['rows'] as $rr) { ?>
      <tr>
        <td><a href="<?php echo e(u('pages/player_detail.php?sid=' . $rr['sid'])); ?>">#<?php echo (int)$rr['sid']; ?></a></td>
        <td><?php echo $rr['ok'] ? '<span class="tag tag-ok">' . e($rr['msg']) . '</span>'
                                  : '<span class="tag tag-err">' . e($rr['msg']) . '</span>'; ?></td>
      </tr>
    <?php } ?>
    </tbody>
  </table>
  </div>
</section>
<?php } ?>

<section class="card">
  <div class="card-h"><h2>对象</h2>
    <div class="card-h-act">
      <button type="button" class="btn btn-xs" id="sel-all">全选</button>
      <button type="button" class="btn btn-xs" id="sel-none">清空</button>
      <span class="muted small" id="sel-count"></span>
    </div>
  </div>
  <div style="max-height:200px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px" id="picker">
    <?php foreach ($allPlayers as $p) { $psid = (int)$p['server_id']; ?>
      <label class="small" style="display:block;padding:2px 0">
        <input type="checkbox" name="sid[]" value="<?php echo $psid; ?>" class="msid"
               <?php echo isset($preselect[$psid]) ? ' checked' : ''; ?>>
        <?php echo e($p['nickname'] !== '' ? $p['nickname'] : '（无昵称）'); ?>
        <span class="muted">#<?php echo $psid; ?> · Lv<?php echo (int)$p['level']; ?></span>
        <?php if (player_is_banned($p['state'])) { ?><span class="tag tag-err">已封禁</span><?php } ?>
      </label>
    <?php } ?>
    <?php if (!$allPlayers) { ?><span class="muted small">还没有玩家</span><?php } ?>
  </div>
  <label class="small muted" style="display:block;margin-top:6px">
    <input type="checkbox" id="scope-all"> 对<b>全服</b>执行（忽略上面的勾选）
  </label>
</section>

<div class="detail-grid">
  <section class="card">
    <div class="card-h"><h2>快捷动作</h2></div>
    <form method="post" action="<?php echo e(u('pages/items.php')); ?>" id="f-quick">
      <?php echo csrf_field(); ?>
      <?php echo action_token_field('items'); ?>
      <input type="hidden" name="mode" value="quick">
      <input type="hidden" name="scope" value="selected" class="scope-holder">
      <div class="actions" style="flex-wrap:wrap">
        <?php foreach (item_quick_actions() as $k => $a) { ?>
          <button type="submit" name="quick" value="<?php echo e($k); ?>" class="btn btn-sm"
                  title="<?php echo e($a[2]); ?>"><?php echo e($a[0]); ?></button>
        <?php } ?>
      </div>
    </form>
    <p class="muted small" style="margin-top:8px">
      快捷动作走 GM 命令（<code>/api/admin/command</code>，Uid=目标玩家），不需要玩家在线。
      命令清单见「GM 命令台」。
    </p>
  </section>

  <section class="card">
    <div class="card-h"><h2>发道具</h2></div>
    <form method="post" action="<?php echo e(u('pages/items.php')); ?>" id="f-item">
      <?php echo csrf_field(); ?>
      <?php echo action_token_field('items'); ?>
      <input type="hidden" name="mode" value="item">
      <input type="hidden" name="scope" value="selected" class="scope-holder">
      <div class="field-row">
        <div class="field"><label>道具 Id</label>
          <input type="number" name="unique_id" min="1" list="dl-items" placeholder="从下方表格查 Id">
          <datalist id="dl-items">
            <?php foreach ($itemRows as $it) { if (!isset($it['id'])) { continue; } ?>
              <option value="<?php echo (int)$it['id']; ?>"><?php echo e(isset($it['name']) ? $it['name'] : ''); ?></option>
            <?php } ?>
          </datalist>
        </div>
        <div class="field"><label>数量</label>
          <input type="number" name="amount" value="1" min="1"></div>
      </div>
      <label class="small"><input type="checkbox" name="set_exact" value="1"> 覆盖为指定数量（不勾=在现有数量上叠加）</label>
      <div class="actions"><button type="submit" class="btn btn-primary btn-sm">发放</button></div>
    </form>
  </section>
</div>

<section class="card">
  <div class="card-h"><h2>自定义 GM 命令（批量）</h2></div>
  <form method="post" action="<?php echo e(u('pages/items.php')); ?>" id="f-cmd">
    <?php echo csrf_field(); ?>
    <?php echo action_token_field('items'); ?>
    <input type="hidden" name="mode" value="command">
    <input type="hidden" name="scope" value="selected" class="scope-holder">
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <input type="text" name="command" placeholder="give 2 5 1000 / max all / setaccount level 90"
             style="flex:1;min-width:320px">
      <button type="submit" class="btn btn-primary">对选中玩家执行</button>
    </div>
  </form>
  <p class="muted small" style="margin-top:6px">命令会逐人执行，任何一个失败不影响其他人。</p>
</section>

<section class="card">
  <div class="card-h"><h2>静态数据（查 Id）</h2>
    <div class="card-h-act">
      <form method="get" action="<?php echo e(u('pages/items.php')); ?>" class="inline" style="display:flex;gap:6px">
        <input type="search" name="q" value="<?php echo e($q); ?>" placeholder="搜名称">
        <button type="submit" class="btn btn-sm">搜索</button>
      </form>
    </div>
  </div>
  <div class="detail-grid">
    <div>
      <h3>道具（<?php echo count($itemRows); ?>）</h3>
      <div class="table-wrap" style="max-height:340px;overflow:auto">
      <table class="tbl">
        <thead><tr><th>Id</th><th>名称</th><th>品质</th><th>堆叠</th></tr></thead>
        <tbody>
        <?php foreach ($itemRows as $it) { ?>
          <tr>
            <td class="muted small"><?php echo (int)$it['id']; ?></td>
            <td><?php echo e(isset($it['name']) ? (string)$it['name'] : ''); ?></td>
            <td class="small"><?php echo e(isset($it['quality']) ? (string)$it['quality'] : ''); ?></td>
            <td class="small"><?php echo isset($it['stackMax']) ? (int)$it['stackMax'] : ''; ?></td>
          </tr>
        <?php } ?>
        </tbody>
      </table>
      </div>
    </div>
    <div>
      <h3>角色（<?php echo count($charRows); ?>）</h3>
      <div class="table-wrap" style="max-height:340px;overflow:auto">
      <table class="tbl">
        <thead><tr><th>Id</th><th>名称</th><th>Dev</th><th>星级</th></tr></thead>
        <tbody>
        <?php foreach ($charRows as $ch) { ?>
          <tr>
            <td class="muted small"><?php echo (int)$ch['id']; ?></td>
            <td><?php echo e(isset($ch['name']) ? (string)$ch['name'] : ''); ?></td>
            <td class="small muted"><?php echo e(isset($ch['devName']) ? (string)$ch['devName'] : ''); ?></td>
            <td class="small"><?php echo isset($ch['defaultStar']) ? (int)$ch['defaultStar'] : ''; ?>/<?php echo isset($ch['maxStar']) ? (int)$ch['maxStar'] : ''; ?></td>
          </tr>
        <?php } ?>
        </tbody>
      </table>
      </div>
    </div>
  </div>
</section>

<script>
(function () {
  var picks = Array.prototype.slice.call(document.querySelectorAll('.msid'));
  var counter = document.getElementById('sel-count');
  function sync() {
    var n = picks.filter(function (c) { return c.checked; }).length;
    if (counter) { counter.textContent = '已选 ' + n + ' 人'; }
  }
  picks.forEach(function (c) { c.addEventListener('change', sync); });
  sync();
  var sa = document.getElementById('sel-all');
  if (sa) { sa.addEventListener('click', function () { picks.forEach(function (c) { c.checked = true; }); sync(); }); }
  var sn = document.getElementById('sel-none');
  if (sn) { sn.addEventListener('click', function () { picks.forEach(function (c) { c.checked = false; }); sync(); }); }

  var all = document.getElementById('scope-all');
  if (all) {
    all.addEventListener('change', function () {
      document.querySelectorAll('.scope-holder').forEach(function (h) {
        h.value = all.checked ? 'all' : 'selected';
      });
    });
  }

  /* 三个表单共享一组 checkbox：提交前把勾选的 sid 复制进该表单 */
  document.querySelectorAll('form#f-quick, form#f-item, form#f-cmd').forEach(function (f) {
    f.addEventListener('submit', function () {
      f.querySelectorAll('input[name="sid[]"]').forEach(function (x) { x.remove(); });
      picks.forEach(function (c) {
        if (c.checked) {
          var h = document.createElement('input');
          h.type = 'hidden';
          h.name = 'sid[]';
          h.value = c.value;
          f.appendChild(h);
        }
      });
    });
  });
})();
</script>

<?php page_footer(); ?>
