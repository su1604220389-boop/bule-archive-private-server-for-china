<?php
/**
 * pages/player_detail.php —— 单个玩家：资料 / 货币 / 角色 / 邮件 / 卡密 / 封禁
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';

require_login();

$sid = get_int('sid', 0, 1);
$cur = ba_currency_maps();

/* ------------------------------------------------------------------ POST --- */
if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $action = post_q('action', '');
    $sidP   = post_int('sid', 0, 1);
    if ($sidP > 0) {
        $sid = $sidP;
    }
    $back = u('pages/player_detail.php?sid=' . $sid);

    if ($action === 'ban' || $action === 'unban') {
        /* F3：旧 State → 新 State 写进审计 */
        $d   = ba_account_detail($sid);
        $old = ($d['ok'] && isset($d['data']['state'])) ? (int)$d['data']['state'] : null;
        $r = player_set_ban($sid, $action === 'ban');
        audit_log($action === 'ban' ? 'player.ban' : 'player.unban', 'server#' . $sid,
            'State ' . ($old === null ? '?' : $old) . '→' . ($action === 'ban' ? '2' : '1')
            . ($r['ok'] ? ' ok' : (' fail: ' . $r['error'])));
        flash_set($r['ok'] ? ($action === 'ban' ? '已封禁，下次登录会被拒绝' : '已解封') : ('失败：' . $r['error']),
                  $r['ok'] ? 'ok' : 'err');
        redirect($back);
    }

    if ($action === 'cur_set') {
        $type = post_int('currency_type', 0);
        $amt  = post_int('amount', 0, 0);
        if ($type <= 0) {
            flash_set('货币类型无效', 'err');
            redirect($back);
        }
        $r = ba_currency_set($sid, $type, $amt);
        panel_op_log('currency.set', array($sid), array('type' => $type, 'amount' => $amt), $r['ok'] ? 1 : 0, $r['ok'] ? 0 : 1);
        audit_log('player.currency_set', 'server#' . $sid . ' type#' . $type, 'amount=' . $amt . ' ' . ($r['ok'] ? 'ok' : $r['error']));
        flash_set($r['ok'] ? ('已设置为 ' . number_format($amt)) : ('失败：' . $r['error']), $r['ok'] ? 'ok' : 'err');
        redirect($back);
    }

    if ($action === 'profile') {
        $fields = array(
            'Nickname' => trim((string)post_q('nickname', '')),
            'CallName' => trim((string)post_q('call_name', '')),
            'Comment'  => (string)post_q('comment', ''),
        );
        if (post_q('level', '') !== '') {
            $fields['Level'] = post_int('level', 1, 1, 999);
        }
        if (post_q('exp', '') !== '') {
            $fields['Exp'] = post_int('exp', 0);
        }
        $r = ba_account_update($sid, $fields);
        panel_op_log('account.update', array($sid), $fields, $r['ok'] ? 1 : 0, $r['ok'] ? 0 : 1);
        audit_log('player.profile', 'server#' . $sid, json_encode($fields, JSON_UNESCAPED_UNICODE));
        flash_set($r['ok'] ? '资料已更新' : ('失败：' . $r['error']), $r['ok'] ? 'ok' : 'err');
        redirect($back);
    }

    if ($action === 'mail_del') {
        $mid  = post_int('mail_id', 0);
        $all  = post_int('clear_all', 0) === 1;
        $r    = ba_mail_delete($sid, $mid, $all);
        panel_op_log('mail.delete', array($sid), array('mail' => $mid, 'all' => $all), $r['ok'] ? 1 : 0, $r['ok'] ? 0 : 1);
        audit_log('player.mail_delete', 'server#' . $sid, 'mail#' . $mid . ' all=' . ($all ? 1 : 0));
        flash_set($r['ok'] ? ('已删除 ' . (isset($r['data']['deleted']) ? (int)$r['data']['deleted'] : 0) . ' 封')
                           : ('失败：' . $r['error']), $r['ok'] ? 'ok' : 'err');
        redirect($back);
    }

    if ($action === 'bind_card') {
        $cardId = post_int('card_id', 0);
        $detail = ba_account_detail($sid);
        $pub    = ($detail['ok'] && isset($detail['data']['publisherAccountId'])) ? (int)$detail['data']['publisherAccountId'] : 0;
        $r = player_bind_card($cardId, $pub, $sid, 'manual', '', current_admin() ? current_admin()['username'] : '');
        audit_log('player.bind_card', 'card#' . $cardId . '→server#' . $sid, $r['ok'] ? 'ok' : $r['error']);
        flash_set($r['ok'] ? '已绑定' : ('失败：' . $r['error']), $r['ok'] ? 'ok' : 'err');
        redirect($back);
    }

    if ($action === 'unbind_card') {
        $r = player_unbind_card(post_int('card_id', 0));
        audit_log('player.unbind_card', 'card#' . post_int('card_id', 0) . '/server#' . $sid, $r['ok'] ? 'ok' : $r['error']);
        flash_set($r['ok'] ? '已解绑' : ('失败：' . $r['error']), $r['ok'] ? 'ok' : 'err');
        redirect($back);
    }

    if ($action === 'command') {
        $cmd = trim((string)post_q('command', ''));
        if ($cmd === '') {
            flash_set('命令不能为空', 'err');
            redirect($back);
        }
        /* 角色排除名单：命令里点名客户端解析不了的角色就直接拒绝 */
        $denyErr = ba_validate_command($cmd);
        if ($denyErr !== '') {
            flash_set($denyErr, 'err');
            redirect($back);
        }
        $r = ba_command($sid, $cmd);
        $out = $r['ok'] && isset($r['data']['output']) ? (string)$r['data']['output'] : '';
        panel_op_log('command', array($sid), array('command' => $cmd, 'output' => $out), $r['ok'] ? 1 : 0, $r['ok'] ? 0 : 1);
        audit_log('player.command', 'server#' . $sid, $cmd);
        if ($r['ok']) {
            flash_set('命令已执行', 'ok');
        } else {
            flash_set('执行失败：' . $r['error'], 'err');
        }
        redirect($back . '&cmd_out=' . rawurlencode(substr($out, 0, 4000)));
    }

    flash_set('未知操作', 'err');
    redirect($back);
}

/* ------------------------------------------------------------------ 数据 --- */
$p = player_one($sid);
if (!$p['ok']) {
    page_header('玩家详情', 'players');
    echo '<div class="srv-down">读取失败：<b>' . e($p['error']) . '</b></div>';
    echo '<p><a class="btn" href="' . e(u('pages/players.php')) . '">返回玩家列表</a></p>';
    page_footer();
    exit;
}
$d      = $p['detail'];
$bridge = $p['bridge'];
$banned = player_is_banned($p['state']);

$charsR = ba_account_characters($sid);
$chars  = ($charsR['ok'] && is_array($charsR['data'])) ? $charsR['data'] : array();
$mailsR = ba_account_mails($sid);
$mails  = ($mailsR['ok'] && is_array($mailsR['data'])) ? $mailsR['data'] : array();
$itemsR = ba_account_items($sid);
$itemCount = ($itemsR['ok'] && is_array($itemsR['data'])) ? count($itemsR['data']) : (int)(isset($d['itemCount']) ? $d['itemCount'] : 0);

$curDict = (isset($d['currencies']) && is_array($d['currencies'])) ? $d['currencies'] : array();
$cmdOut  = get_q('cmd_out', '');

$bindableCards = array();
try {
    $bound = array();
    foreach (player_card_bindings() as $cid => $b) {
        $bound[$cid] = true;
    }
    foreach (db_all('SELECT id, card_key, status FROM cards ORDER BY id DESC LIMIT 500') as $c) {
        if (!isset($bound[(int)$c['id']])) {
            $bindableCards[] = $c;
        }
    }
} catch (Throwable $e) {
    $bindableCards = array();
}

page_header('玩家详情 · ' . ($d['nickname'] !== '' ? $d['nickname'] : ('#' . $sid)), 'players');
?>

<?php if ($banned) { echo alert_box('该账号已被封禁：下次登录会被服务端拒绝（Account_CheckNexon / CheckYostar 直接抛 ACCOUNT_SUSPENDED）。', 'err'); } ?>

<div class="card-h" style="margin-bottom:10px">
  <a class="btn btn-sm" href="<?php echo e(u('pages/players.php')); ?>">← 玩家列表</a>
  <a class="btn btn-sm btn-primary" href="<?php echo e(u('pages/mail.php?sid=' . $sid)); ?>">发奖 / 发邮件</a>
  <a class="btn btn-sm" href="<?php echo e(u('pages/console.php?sid=' . $sid)); ?>">GM 命令台</a>
</div>

<div class="detail-grid">

  <section class="card">
    <div class="card-h"><h2>账号资料</h2>
      <div class="card-h-act">
        <form method="post" action="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>" class="inline">
          <?php echo csrf_field(); ?>
          <input type="hidden" name="sid" value="<?php echo $sid; ?>">
          <button type="submit" name="action" value="<?php echo $banned ? 'unban' : 'ban'; ?>"
                  class="btn btn-sm <?php echo $banned ? 'btn-warn' : 'btn-danger'; ?>"
                  onclick="return confirm('<?php echo $banned ? '确认解封？' : '确认封禁该账号？'; ?>');">
            <?php echo $banned ? '解封' : '封禁'; ?>
          </button>
        </form>
      </div>
    </div>
    <table class="kv">
      <tr><th>ServerId</th><td><code><?php echo $sid; ?></code></td></tr>
      <tr><th>publisherId</th><td><code><?php echo e(isset($d['publisherAccountId']) ? (string)$d['publisherAccountId'] : '—'); ?></code></td></tr>
      <tr><th>昵称</th><td><?php echo e($d['nickname'] !== '' ? $d['nickname'] : '—'); ?></td></tr>
      <tr><th>称呼</th><td><?php echo e(isset($d['callName']) ? (string)$d['callName'] : '—'); ?></td></tr>
      <tr><th>等级 / EXP</th><td>Lv <?php echo (int)$d['level']; ?> · <?php echo number_format((int)$d['exp']); ?></td></tr>
      <tr><th>状态</th><td>
        <?php if ($banned) { ?><span class="tag tag-err">已封禁（Dormant）</span>
        <?php } else { ?><span class="tag tag-ok"><?php echo e(player_state_label($p['state'])); ?></span><?php } ?>
      </td></tr>
      <tr><th>VIP</th><td><?php echo (int)(isset($d['vipLevel']) ? $d['vipLevel'] : 0); ?></td></tr>
      <tr><th>签名</th><td><?php echo e(isset($d['comment']) && $d['comment'] !== null ? (string)$d['comment'] : '—'); ?></td></tr>
      <tr><th>创建</th><td><?php echo e(player_dt(isset($d['createDate']) ? $d['createDate'] : '')); ?></td></tr>
      <tr><th>最后连接</th><td><?php echo e(player_dt(isset($d['lastConnectTime']) ? $d['lastConnectTime'] : '')); ?></td></tr>
      <tr><th>未读邮件</th><td><?php echo (int)(isset($d['unReadMailCount']) ? $d['unReadMailCount'] : 0); ?></td></tr>
      <tr><th>角色 / 道具 / 邮件</th><td><?php echo (int)(isset($d['characterCount']) ? $d['characterCount'] : count($chars)); ?> / <?php echo $itemCount; ?> / <?php echo (int)(isset($d['mailCount']) ? $d['mailCount'] : count($mails)); ?></td></tr>
    </table>

    <details style="margin-top:10px">
      <summary class="muted small">编辑资料</summary>
      <form method="post" action="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>" style="margin-top:8px">
        <?php echo csrf_field(); ?>
        <input type="hidden" name="sid" value="<?php echo $sid; ?>">
        <div class="field-row">
          <div class="field"><label>昵称</label>
            <input type="text" name="nickname" value="<?php echo e((string)$d['nickname']); ?>" maxlength="32"></div>
          <div class="field"><label>称呼</label>
            <input type="text" name="call_name" value="<?php echo e(isset($d['callName']) ? (string)$d['callName'] : ''); ?>" maxlength="32"></div>
        </div>
        <div class="field-row">
          <div class="field"><label>等级</label>
            <input type="number" name="level" value="<?php echo (int)$d['level']; ?>" min="1" max="999"></div>
          <div class="field"><label>EXP</label>
            <input type="number" name="exp" value="<?php echo (int)$d['exp']; ?>" min="0"></div>
        </div>
        <div class="field"><label>签名</label>
          <input type="text" name="comment" value="<?php echo e(isset($d['comment']) && $d['comment'] !== null ? (string)$d['comment'] : ''); ?>" maxlength="120"></div>
        <button type="submit" name="action" value="profile" class="btn btn-primary btn-sm">保存</button>
      </form>
    </details>
  </section>

  <section class="card">
    <div class="card-h"><h2>桥接 / 卡密</h2></div>
    <table class="kv">
      <tr><th>桥接账号</th><td><?php echo $bridge ? ('<code>' . e((string)$bridge['server_id']) . '</code>') : '<span class="muted">未找到（publisherId 对不上 accounts.db）</span>'; ?></td></tr>
      <tr><th>设备号</th><td><?php echo $bridge && $bridge['device_unique_id'] !== '' ? '<code class="small">' . e((string)$bridge['device_unique_id']) . '</code>' : '<span class="muted">—</span>'; ?></td></tr>
      <tr><th>dev_id</th><td><?php echo $bridge ? '<code class="small">' . e((string)$bridge['dev_id']) . '</code>' : '—'; ?></td></tr>
      <tr><th>登录次数</th><td><?php echo $bridge ? number_format((int)$bridge['login_count']) : '—'; ?></td></tr>
      <tr><th>最后登录</th><td><?php echo $bridge ? e(player_dt((string)$bridge['last_login_at'])) : '—'; ?></td></tr>
    </table>

    <h3 style="margin-top:14px">绑定的卡密</h3>
    <?php if (!$p['cards']) { ?>
      <p class="muted small">还没有绑定卡密。绑定之后「玩家列表」就能按卡密查到这个人。</p>
    <?php } else { ?>
      <div class="table-wrap">
      <table class="tbl">
        <thead><tr><th>卡密</th><th>状态</th><th>来源</th><th></th></tr></thead>
        <tbody>
        <?php foreach ($p['cards'] as $mc) { ?>
          <tr>
            <td><code><?php echo e($mc['card_key']); ?></code></td>
            <td><?php echo $mc['status'] === 'active' ? '<span class="tag tag-ok">可用</span>' : '<span class="tag tag-err">停用</span>'; ?></td>
            <td class="muted small"><?php echo $mc['source'] === 'manual' ? '手动' : e($mc['source']); ?></td>
            <td>
              <form method="post" action="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>" class="inline">
                <?php echo csrf_field(); ?>
                <input type="hidden" name="sid" value="<?php echo $sid; ?>">
                <input type="hidden" name="card_id" value="<?php echo (int)$mc['card_id']; ?>">
                <button type="submit" name="action" value="unbind_card" class="btn btn-xs btn-danger"
                        onclick="return confirm('解绑这张卡密？');">解绑</button>
              </form>
            </td>
          </tr>
        <?php } ?>
        </tbody>
      </table>
      </div>
    <?php } ?>

    <?php if ($bindableCards) { ?>
      <form method="post" action="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>" style="margin-top:8px;display:flex;gap:6px;align-items:center">
        <?php echo csrf_field(); ?>
        <input type="hidden" name="sid" value="<?php echo $sid; ?>">
        <select name="card_id" style="max-width:260px">
          <option value="0">选择一张卡密…</option>
          <?php foreach ($bindableCards as $c0) { ?>
            <option value="<?php echo (int)$c0['id']; ?>"><?php echo e($c0['card_key']); ?></option>
          <?php } ?>
        </select>
        <button type="submit" name="action" value="bind_card" class="btn btn-sm">绑定</button>
      </form>
    <?php } ?>
  </section>
</div>

<section class="card">
  <div class="card-h"><h2>货币</h2>
    <div class="card-h-act"><span class="muted small">青辉石是派生值（Gem = 免费 + 付费），写「合计(4)」时服务端会把免费石设为该值、付费石清零</span></div>
  </div>
  <?php if (!$curDict) { ?>
    <p class="muted">读不到货币数据。</p>
  <?php } else { ?>
    <div class="cur-grid">
      <?php foreach ($curDict as $cname => $cval) {
          $cid2 = isset($cur['name2id'][$cname]) ? (int)$cur['name2id'][$cname] : 0; ?>
        <div class="cur-item">
          <div class="k"><?php echo e(ba_currency_label($cid2, (string)$cname)); ?></div>
          <div class="v"><?php echo number_format((int)$cval); ?></div>
          <?php if ($cid2 > 0) { ?>
          <form method="post" action="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>" style="display:flex;gap:4px;margin-top:4px">
            <?php echo csrf_field(); ?>
            <input type="hidden" name="sid" value="<?php echo $sid; ?>">
            <input type="hidden" name="action" value="cur_set">
            <input type="hidden" name="currency_type" value="<?php echo $cid2; ?>">
            <input type="number" name="amount" value="<?php echo (int)$cval; ?>" min="0" style="width:100px;padding:2px 6px">
            <button type="submit" class="btn btn-xs">改</button>
          </form>
          <?php } ?>
        </div>
      <?php } ?>
    </div>
  <?php } ?>
</section>

<div class="detail-grid">
  <section class="card">
    <div class="card-h"><h2>角色（<?php echo count($chars); ?>）</h2></div>
    <?php if (!$chars) { ?>
      <p class="muted small">没有角色。</p>
    <?php } else { ?>
      <div class="table-wrap" style="max-height:360px;overflow:auto">
      <table class="tbl">
        <thead><tr><th>Id</th><th>角色</th><th>星级</th><th>等级</th><th>好感</th></tr></thead>
        <tbody>
        <?php foreach ($chars as $c) { ?>
          <tr>
            <td class="muted small"><?php echo (int)$c['uniqueId']; ?></td>
            <td><?php echo e(isset($c['name']) && $c['name'] !== null ? (string)$c['name'] : (isset($c['devName']) ? (string)$c['devName'] : '—')); ?></td>
            <td><?php echo str_repeat('★', max(1, (int)$c['starGrade'])); ?></td>
            <td><?php echo (int)$c['level']; ?></td>
            <td><?php echo (int)$c['favorRank']; ?></td>
          </tr>
        <?php } ?>
        </tbody>
      </table>
      </div>
    <?php } ?>
  </section>

  <section class="card">
    <div class="card-h"><h2>邮件（<?php echo count($mails); ?>）</h2>
      <div class="card-h-act">
        <form method="post" action="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>" class="inline">
          <?php echo csrf_field(); ?>
          <input type="hidden" name="sid" value="<?php echo $sid; ?>">
          <input type="hidden" name="action" value="mail_del">
          <input type="hidden" name="clear_all" value="1">
          <button type="submit" class="btn btn-xs btn-danger"
                  onclick="return confirm('清空该玩家全部邮件？未领取的附件会一起消失。');">清空全部</button>
        </form>
      </div>
    </div>
    <?php if (!$mails) { ?>
      <p class="muted small">没有邮件。</p>
    <?php } else { ?>
      <div class="table-wrap" style="max-height:360px;overflow:auto">
      <table class="tbl">
        <thead><tr><th>#</th><th>发件人 / 内容</th><th>附件</th><th>状态</th><th></th></tr></thead>
        <tbody>
        <?php foreach ($mails as $m) {
            $pl = array();
            if (isset($m['parcels']) && is_array($m['parcels'])) {
                foreach ($m['parcels'] as $pc) {
                    $nm = (string)$pc['type'];
                    if ($nm === 'Currency') {
                        $nm = isset($cur['id2name'][(int)$pc['id']]) ? $cur['id2name'][(int)$pc['id']] : ('Cur#' . $pc['id']);
                    }
                    $pl[] = $nm . '×' . number_format((int)$pc['amount']);
                }
            }
            ?>
          <tr>
            <td class="muted small"><?php echo (int)$m['serverId']; ?></td>
            <td>
              <div class="small"><?php echo e((string)$m['sender']); ?><?php echo (string)$m['sender'] === '' ? '' : '：'; ?><?php echo e(str_limit((string)$m['comment'], 40)); ?></div>
              <div class="muted small"><?php echo e(player_dt((string)$m['sendDate'])); ?> · <?php echo e((string)$m['type']); ?></div>
            </td>
            <td class="small"><?php echo e(implode(' + ', $pl)); ?></td>
            <td><?php echo !empty($m['collected']) ? '<span class="tag tag-gray">已领</span>' : '<span class="tag tag-info">未领</span>'; ?></td>
            <td>
              <form method="post" action="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>" class="inline">
                <?php echo csrf_field(); ?>
                <input type="hidden" name="sid" value="<?php echo $sid; ?>">
                <input type="hidden" name="action" value="mail_del">
                <input type="hidden" name="mail_id" value="<?php echo (int)$m['serverId']; ?>">
                <button type="submit" class="btn btn-xs" onclick="return confirm('删除这封邮件？');">×</button>
              </form>
            </td>
          </tr>
        <?php } ?>
        </tbody>
      </table>
      </div>
    <?php } ?>
  </section>
</div>

<section class="card">
  <div class="card-h"><h2>GM 命令（对 <code>#<?php echo $sid; ?></code> 执行）</h2></div>
  <form method="post" action="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>" style="display:flex;gap:8px;flex-wrap:wrap">
    <?php echo csrf_field(); ?>
    <input type="hidden" name="sid" value="<?php echo $sid; ?>">
    <input type="text" name="command" placeholder="例如：max all / giveall / unlockall campaign / currency GemBonus 5000"
           style="flex:1;min-width:320px" value="<?php echo e(get_q('cmd', '')); ?>">
    <button type="submit" name="action" value="command" class="btn btn-primary">执行</button>
  </form>
  <p class="muted small" style="margin-top:6px">命令白名单见「GM 命令台」页。Uid 固定为本页玩家 #<?php echo $sid; ?>。</p>
  <?php if ($cmdOut !== '') { ?>
    <pre class="cmd-out"><?php echo e($cmdOut); ?></pre>
  <?php } ?>
</section>

<?php page_footer(); ?>
