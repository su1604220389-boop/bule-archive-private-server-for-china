<?php
/**
 * pages/console.php —— GM 命令台
 *
 * 端点：POST /api/admin/command { Uid: <AccountServerId>, Command: "..." }
 * 直接把命令送给目标玩家的 WebConnection，等价于官方控制台的 `--id <uid>`。
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';

require_login();

/** 命令参考（来自 Shittim 的 Commands/ 实现） */
function console_command_help()
{
    return array(
        array('help',                  '',                        '列出全部命令'),
        array('give',                  '<包裹类型> <id> <数量>',  '发放单个包裹（如 give Currency 3 1000）'),
        array('giveall',               '',                        '发放全部角色'),
        array('giveequip',             '<装备id> [数量]',         '发放装备'),
        array('giveallequip',          '',                        '发放全部装备'),
        array('max',                   '<all|角色名>',            '把角色拉满（Lv90/满星/技能/好感）'),
        array('currency',              '<货币> <数量>',           '改货币（数量为绝对值）'),
        array('character',             '<...>',                   '角色增删 / 改星级'),
        array('addeleph',              '<角色id> <数量>',         '加碎片'),
        array('inventory',             '',                        '查看背包'),
        array('listitem',              '',                        '列出道具'),
        array('checkitem',             '<id>',                    '查某个道具'),
        array('clearinventory',        '',                        '清空背包（危险）'),
        array('mail',                  '<类型> <id,...> <数量>',  '发邮件'),
        array('accountdata',           'list|load|export',        '整包存档导入导出'),
        array('setaccount',            '<属性> <值>',             '反射设置账号属性'),
        array('setseason',             'total|grand|drill|final <id>', '设置赛季'),
        array('setraid',               '<...>',                   '总力战参数'),
        array('setting',               'trackpvp|usefinal|bypassteam|bypasssummon|changetime', '开关类设置'),
        array('unlockall',             'campaign|story|weekdungeon|schooldungeon|battlepass|mission', '批量解锁'),
        array('unlockbattlepass',      '',                        '解锁战斗通行证'),
        array('gacha',                 '<...>',                   '抽卡模拟'),
    );
}

$sid = get_int('sid', 0, 0);
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

$run = null;
$hist = array();

/* ------------------------------------------------------------- POST --- */
if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    action_token_check('console');

    $ids = array();
    foreach ((array)(isset($_POST['sid']) ? $_POST['sid'] : array()) as $v) {
        $v = (int)$v;
        if ($v > 0) {
            $ids[$v] = $v;
        }
    }
    $ids = array_values($ids);
    if (!$ids) {
        flash_set('选一个目标玩家', 'err');
        redirect_self();
    }

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

    $run = array('command' => $cmd, 'rows' => array(), 'ok' => 0, 'fail' => 0);
    $befores = array();
    foreach ($ids as $one) {
        /* F3：setaccount 能定位到属性时，先取旧值写审计 */
        if (preg_match('/^\s*setaccount\s+([A-Za-z0-9_]+)/i', $cmd, $mm)) {
            $d = ba_account_detail($one);
            if ($d['ok'] && is_array($d['data'])) {
                foreach ($d['data'] as $kk => $vv) {
                    if (strcasecmp((string)$kk, $mm[1]) === 0) {
                        $befores[$one] = (string)$vv;
                        break;
                    }
                }
            }
        }
        $r = ba_command($one, $cmd);
        $out = ($r['ok'] && isset($r['data']['output'])) ? (string)$r['data']['output'] : '';
        $run['rows'][] = array('sid' => $one, 'ok' => (bool)$r['ok'], 'out' => $out, 'err' => $r['error'], 'ms' => (int)$r['ms']);
        $r['ok'] ? $run['ok']++ : $run['fail']++;
    }
    panel_op_log('console.command', $ids, array('command' => $cmd,
        'outputs' => array_map(function ($x) { return $x['out'] !== '' ? $x['out'] : $x['err']; }, $run['rows'])),
        $run['ok'], $run['fail']);
    $beforeTxt = '';
    foreach ($befores as $bsid => $bval) {
        $beforeTxt .= ' ' . $bsid . ':' . $bval . '→(cmd)';
    }
    audit_log('console.command', implode(',', $ids), $cmd . ($beforeTxt !== '' ? ' | before:' . $beforeTxt : ''));
}

$hist = panel_op_recent(15);
$roster = player_roster(array());
$allPlayers = $roster['ok'] ? $roster['rows'] : array();
$selected = array();
if ($sid > 0) {
    $selected[$sid] = $sid;
}

page_header('GM 命令台', 'console');
if (!$roster['ok']) {
    echo '<div class="srv-down">读取不到游戏服务端：<b>' . e($roster['error']) . '</b></div>';
}
?>

<section class="card">
  <div class="card-h"><h2>执行命令</h2>
    <div class="card-h-act"><span class="muted small">等价于官方控制台 <code>--id &lt;ServerId&gt;</code>；不需要玩家在线</span></div>
  </div>

  <form method="post" action="<?php echo e(u('pages/console.php')); ?>">
    <?php echo csrf_field(); ?>
    <?php echo action_token_field('console'); ?>

    <div class="field">
      <label><b>目标玩家</b></label>
      <div style="max-height:150px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px">
        <?php foreach ($allPlayers as $p) { $psid = (int)$p['server_id']; ?>
          <label class="small" style="display:inline-block;min-width:230px;padding:2px 6px 2px 0">
            <input type="checkbox" name="sid[]" value="<?php echo $psid; ?>"
                   <?php echo (isset($preselect[$psid]) || isset($selected[$psid])) ? ' checked' : ''; ?>>
            <?php echo e($p['nickname'] !== '' ? $p['nickname'] : '（无昵称）'); ?>
            <span class="muted">#<?php echo $psid; ?></span>
          </label>
        <?php } ?>
        <?php if (!$allPlayers) { ?><span class="muted small">还没有玩家</span><?php } ?>
      </div>
    </div>

    <div class="field">
      <label><b>命令</b></label>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <input type="text" name="command" id="cmd-input" placeholder="例如：max all"
               value="<?php echo e($run ? $run['command'] : ''); ?>" style="flex:1;min-width:300px" autofocus>
        <button type="submit" class="btn btn-primary">执行</button>
      </div>
      <div class="actions" style="margin-top:6px;flex-wrap:wrap">
        <?php foreach (array('help', 'max all', 'giveall', 'giveallequip', 'unlockall campaign', 'unlockbattlepass') as $q0) { ?>
          <button type="button" class="btn btn-xs" data-cmd="<?php echo e($q0); ?>"><?php echo e($q0); ?></button>
        <?php } ?>
      </div>
    </div>
  </form>

  <?php if ($run) { ?>
    <div class="card-h" style="margin-top:12px">
      <h3>输出 · <?php echo e($run['command']); ?></h3>
      <div class="card-h-act">
        <span class="tag tag-ok"><?php echo (int)$run['ok']; ?></span>
        <?php if ($run['fail']) { ?><span class="tag tag-err"><?php echo (int)$run['fail']; ?></span><?php } ?>
      </div>
    </div>
    <?php foreach ($run['rows'] as $rr) { ?>
      <div style="margin-bottom:8px">
        <div class="small">
          <a href="<?php echo e(u('pages/player_detail.php?sid=' . $rr['sid'])); ?>">#<?php echo (int)$rr['sid']; ?></a>
          <?php echo $rr['ok'] ? '<span class="tag tag-ok">OK</span>' : '<span class="tag tag-err">' . e($rr['err']) . '</span>'; ?>
          <span class="muted"><?php echo (int)$rr['ms']; ?> ms</span>
        </div>
        <?php if ($rr['out'] !== '') { ?><pre class="cmd-out"><?php echo e($rr['out']); ?></pre><?php } ?>
      </div>
    <?php } ?>
  <?php } ?>
</section>

<div class="detail-grid">
  <section class="card">
    <div class="card-h"><h2>命令参考</h2></div>
    <div class="table-wrap" style="max-height:420px;overflow:auto">
    <table class="tbl">
      <thead><tr><th>命令</th><th>参数</th><th>说明</th></tr></thead>
      <tbody>
      <?php foreach (console_command_help() as $h) { ?>
        <tr>
          <td><code><?php echo e($h[0]); ?></code></td>
          <td class="small muted"><?php echo e($h[1]); ?></td>
          <td class="small"><?php echo e($h[2]); ?></td>
        </tr>
      <?php } ?>
      </tbody>
    </table>
    </div>
  </section>

  <section class="card">
    <div class="card-h"><h2>最近命令</h2></div>
    <?php if (!$hist) { ?>
      <p class="muted small">还没有执行记录。</p>
    <?php } else { ?>
      <div class="table-wrap" style="max-height:420px;overflow:auto">
      <table class="tbl">
        <thead><tr><th>时间</th><th>命令</th><th>对象</th><th>结果</th></tr></thead>
        <tbody>
        <?php foreach ($hist as $op) {
            $pl = json_decode((string)$op['payload'], true);
            $cmd = is_array($pl) && isset($pl['command']) ? (string)$pl['command'] : (string)$op['action'];
            $n = count(array_filter(explode(',', (string)$op['targets'])));
            ?>
          <tr>
            <td class="nowrap small"><?php echo e(fmt_ts((int)$op['ts'])); ?></td>
            <td><code class="small"><?php echo e(str_limit($cmd, 40)); ?></code>
              <div class="muted small"><?php echo e((string)$op['action']); ?></div></td>
            <td class="small"><?php echo $n; ?> 人</td>
            <td class="nowrap">
              <span class="tag tag-ok"><?php echo (int)$op['ok_count']; ?></span>
              <?php if ((int)$op['fail_count'] > 0) { ?><span class="tag tag-err"><?php echo (int)$op['fail_count']; ?></span><?php } ?>
            </td>
          </tr>
        <?php } ?>
        </tbody>
      </table>
      </div>
    <?php } ?>
  </section>
</div>

<script>
document.querySelectorAll('[data-cmd]').forEach(function (b) {
  b.addEventListener('click', function () {
    var i = document.getElementById('cmd-input');
    i.value = b.getAttribute('data-cmd');
    i.focus();
  });
});
</script>

<?php page_footer(); ?>
