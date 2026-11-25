<?php
/**
 * bans_page.php —— 封禁管理（账号 / 卡密 / 设备，三个**正交**维度 + 限时封禁）
 *
 * 部署名：`/www/wwwroot/ba_cardadmin/pages/bans.php`（本文件就是它的完整源码）
 *
 * 页面只做三件事，而且三件事互不联动：
 *   · 账号封禁  → bans_inc.php banexp_toggle_account() → bans 表 + Shittim State（2 Dormant / 1 Normal）
 *   · 卡密封禁  → bans_inc.php banexp_toggle_card()    → bans 表 +（永久时）MySQL cards.status
 *   · 设备封禁  → bans_inc.php banexp_toggle_device()  → bans 表 +（永久时）SDK 黑名单文件
 * 另加：删除账号（硬删除，二次确认 + 手输昵称/ServerId）、限时封禁表（解封/清理已到期）。
 *      「清理到期记录」固定按「先还原账号 State → 写审计 → 再删行」执行（2026-11-18 修复；
 *      旧实现只删行不还原 State，会把账号永久锁死在 Dormant，详见 bans_inc.php banexp_purge_expired()）。
 *      页面顶部另有「孤儿封禁」只读提示（banexp_orphan_accounts()），不改任何数据。
 *
 * 时长（三个维度都有）：永久（默认）/ 1 小时 / 1 天 / 7 天 / 30 天 / 自定义（datetime-local）
 *   → 提交时由 banexp_until_from_post() 换算成 until_epoch（服务器时间 + 时长，或自定义时间点）。
 * 文案：bans_inc.php ban_msg()，与 SDK 侧 ban_message.py 逐字一致（CHECK.md §3）。
 *
 * 所有写操作：POST + CSRF + audit_log()，然后 PRG 重定向。
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/bans.php';

require_login();

/* ------------------------------------------------------- 本页私有小工具 --- */

/** POST 之后回到带筛选条件的本页 */
function bans_back_url()
{
    $keep = array();
    $q = post_q('keep_q', '');
    if ($q !== '') {
        $keep['q'] = $q;
    }
    $st = post_q('keep_state', '');
    if ($st !== '') {
        $keep['state'] = $st;
    }
    $url = u('pages/bans.php');
    return $keep ? ($url . '?' . http_build_query($keep)) : $url;
}

/** flash + 跳回（PRG，避免刷新重复提交） */
function bans_finish($msg, $type = 'ok')
{
    flash_set($msg, $type);
    redirect(bans_back_url());
}

/** 当前操作的管理员名（写进 bans.created_by / 审计） */
function bans_actor()
{
    $a = function_exists('current_admin') ? current_admin() : null;
    if (is_array($a) && isset($a['username']) && trim((string)$a['username']) !== '') {
        return trim((string)$a['username']);
    }
    return 'panel';
}

/** 三个维度的中文名 */
function bans_dim_label($dim)
{
    $map = array('account' => '账号', 'card' => '卡密', 'device' => '设备');
    return isset($map[$dim]) ? $map[$dim] : $dim;
}

/**
 * 时长下拉框（三个维度共用；默认「永久」，与旧行为一致）
 * @param string $name
 * @return string HTML
 */
function bans_duration_select($name = 'duration')
{
    $opts = function_exists('banexp_duration_options')
        ? banexp_duration_options()
        : array('perm' => '永久');
    $html = '<select name="' . e($name) . '" class="bans-dur" title="封禁时长"'
        . ' style="width:104px;font-size:12px;padding:4px 4px;border:1px solid #d3dae3;border-radius:8px;font-family:inherit">';
    foreach ($opts as $v => $label) {
        $html .= '<option value="' . e($v) . '"' . ((string)$v === 'perm' ? ' selected' : '') . '>'
            . e($label) . '</option>';
    }
    $html .= '</select>';
    return $html;
}

/**
 * 自定义时间点输入（选了「自定义」才用它；不选就当没填）
 * @return string HTML
 */
function bans_until_input()
{
    return '<input type="datetime-local" name="until_local" value="" class="bans-until"'
        . ' title="选「自定义」时必填：如 2026-11-20 20:00（Asia/Shanghai）"'
        . ' style="width:158px;font-size:12px;padding:4px 6px;border:1px solid #d3dae3;border-radius:8px;font-family:inherit">';
}

/** 可选的原因输入（写进 bans.reason） */
function bans_reason_input()
{
    return '<input type="text" name="reason" value="" class="bans-reason" autocomplete="off"'
        . ' placeholder="原因（可选）" title="会写进 bans.reason 与审计日志"'
        . ' style="width:104px;font-size:12px;padding:4px 6px;border:1px solid #d3dae3;border-radius:8px;font-family:inherit">';
}

/** 封禁行 -> 小标签（封禁中 / 已到期） */
function bans_state_tag($row)
{
    if (!is_array($row)) {
        return '';
    }
    if (!banexp_is_active($row)) {
        return '<span class="tag tag-gray">已到期</span>';
    }
    if ($row['until_epoch'] === null) {
        return '<span class="tag tag-err">永久</span>';
    }
    return '<span class="tag tag-warn">限时</span>';
}

/**
 * 一行玩家实际涉及到的设备号：桥接库里的两个字段 + 他卡密在 cards.json/card_devices 里绑过的设备
 * @param array $row  player_roster() 的一行
 * @param array $cand ban_device_candidates() 的结果
 * @return array 设备号数组
 */
function bans_row_devices($row, $cand)
{
    $devs = array();
    /* [DEVFIX2 2026-11-18] 这里原来读 $row['device'] 和 $row['dev_id']，两个都不是 SDK 认的设备号：
     *     $row['device'] = 桥的 accounts.device_unique_id（32 位串，没有任何一层拿它做拦截）
     *     $row['dev_id'] = publisherId 的副本（9 位数字，账号身份）
     * 真设备号（客户端上报的 Authorization.Head.DeviceID，16 位）只从下面的
     * $cand 合并里来（cards.json / card_devices / device_ban.txt），所以这里留空。
     * 原代码（留档）：
     *   foreach (array('device', 'dev_id') as $k) {
     *       $d = isset($row[$k]) ? trim((string)$row[$k]) : '';
     *       if ($d !== '') { $devs[$d] = true; }
     *   }
     */
    $sid  = isset($row['server_id']) ? (int)$row['server_id'] : 0;
    $keys = array();
    if (isset($row['cards']) && is_array($row['cards'])) {
        foreach ($row['cards'] as $c) {
            if (isset($c['card_key'])) {
                $keys[(string)$c['card_key']] = true;
            }
        }
    }
    if ($sid > 0 && isset($cand['devices']) && is_array($cand['devices'])) {
        foreach ($cand['devices'] as $d => $info) {
            if (isset($info['accounts'][$sid])) {
                $devs[(string)$d] = true;
                continue;
            }
            if (!empty($info['cards'])) {
                foreach ($info['cards'] as $ck) {
                    if (isset($keys[$ck])) {
                        $devs[(string)$d] = true;
                        break;
                    }
                }
            }
        }
    }
    $list = array_keys($devs);
    sort($list);
    return $list;
}

/** 全封 / 全解的二次确认文案（必须写清楚会影响哪三项，以及时长按哪个下拉框） */
function bans_all_confirm($nick, $sid, $cardN, $devN, $on)
{
    $who = ($nick !== '' ? ('「' . $nick . '」') : '') . '（ServerId ' . (int)$sid . '）';
    if ($on) {
        return '即将对玩家 ' . $who . " 一次性执行全部三项（时长取本行「全封」旁边的时长下拉框，默认永久）：\n"
            . "① 封禁账号：写 bans 表 + Shittim Accounts.State 改为 2 Dormant（下次登录被拒）\n"
            . '② 封禁 ' . (int)$cardN . " 张卡密：写 bans 表 +（永久时）cards.status 改为 disabled（≤60 秒同步到 cards.json）\n"
            . '③ 封禁 ' . (int)$devN . " 台设备：写 bans 表 +（永久时）device_ban.txt（SDK 命中即弹封禁文案）\n"
            . "\n选「永久」时三处旧机制一起写；选限时时只写 bans 表，到期自动解除。"
            . "三项互相独立，之后可以单独解除任意一项。确定继续吗？";
    }
    return '即将对玩家 ' . $who . " 一次性解除全部三项：\n"
        . "① 解封账号：删 bans 行 + State 改回 1 Normal\n"
        . '② 解封 ' . (int)$cardN . " 张卡密：删 bans 行 + cards.status 改为 active（≤60 秒同步到 cards.json）\n"
        . '③ 解封 ' . (int)$devN . " 台设备：删 bans 行 + 从 device_ban.txt 移除\n"
        . "\n只想解除其中一项时请用行内对应的单独按钮。确定继续吗？";
}

/**
 * 「清理到期记录」的二次确认文案。
 *
 * 必须写清楚：会**先还原账号封禁状态、再删记录**，而且不可撤销。
 * 旧文案只写"只删已到期的行"，会让人以为删行是件无害的事 —— 实际上删行之前
 * 必须先把 Shittim 的 Accounts.State 还原，否则账号会被永久锁死（见 bans_inc.php
 * banexp_purge_expired() 的注释）。
 */
function bans_purge_confirm()
{
    return "「清理到期记录」按固定顺序做两件事：\n"
        . "① 先把每个「已到期的账号封禁」对应的 Shittim Accounts.State 还原成 1 Normal（= 解封）\n"
        . "② 再删掉 bans 表里这些已到期的行（until_epoch ≤ 现在）；永久行一条都不会动\n"
        . "\n"
        . "卡密 / 设备两个维度的到期行只删记录：不会去改 MySQL cards.status，也不会动 device_ban.txt。\n"
        . "State 还原失败的那些行会「保留」（不会被删掉），下次再点这个按钮会重试。\n"
        . "解析不到 Shittim ServerId 的账号行，只删记录、不写 State，审计里记 state=unknown。\n"
        . "\n"
        . "此操作不可撤销：删掉的封禁记录无法恢复。确定继续吗？";
}

/* ==================================================================== POST --- */

if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $action = post_q('action', '');

    /* ---- 账号封禁 / 解封（bans 表 + Shittim Accounts.State，只动账号） ---- */
    if ($action === 'account_set') {
        $sid = post_int('sid', 0);
        $on  = post_q('on', '0') === '1';
        if ($sid <= 0) {
            bans_finish('账号参数无效（ServerId 缺失）', 'err');
        }
        $pub  = post_int('pub', 0);
        $by   = bans_actor();
        $dur  = $on ? banexp_until_from_post() : array('ok' => true, 'until' => null, 'label' => '解封', 'error' => '');
        if (empty($dur['ok'])) {
            bans_finish('账号 ' . $sid . ' 封禁失败：' . $dur['error'], 'err');
        }
        $reason = $on ? post_q('reason', '') : '';
        if ($pub <= 0) {
            /* 兜底：页面没带 pub 时从 Shittim 账号列表里补一次 */
            $idx = ban_accounts_index();
            if ($idx['ok'] && isset($idx['rows'][$sid]['publisherAccountId'])) {
                $pub = (int)$idx['rows'][$sid]['publisherAccountId'];
            }
        }
        $r = banexp_toggle_account($sid, $pub, $on, $dur['until'], $reason, $by);
        audit_log(
            $on ? 'ban.account_on' : 'ban.account_off',
            'ServerId ' . $sid . ' / publisher ' . $pub,
            ($on
                ? ('封禁 ' . $dur['label'] . ' | until=' . ($dur['until'] === null ? 'NULL(永久)' : (int)$dur['until']))
                : '解封（删 bans 行 + State→1）')
            . ' | bans 表 ' . (!empty($r['table_ok']) ? 'ok' : 'fail')
            . ' | Shittim ' . (!empty($r['legacy_ok']) ? 'ok' : 'fail')
            . ' | 原因 ' . str_limit($reason, 60)
            . ' | ' . ($r['ok'] ? 'ok' : ('失败：' . $r['error']))
        );
        $msg = '';
        if ($r['ok']) {
            $msg = $r['notice'];
            if (!empty($r['warnings'])) {
                $msg .= '（注意：' . implode('；', $r['warnings']) . '）';
            }
        } else {
            $msg = '账号 ' . $sid . ' 操作失败：' . $r['error'];
        }
        bans_finish($msg, (!empty($r['warnings']) && $r['ok']) ? 'warn' : ($r['ok'] ? 'ok' : 'err'));
    }

    /* ---- 卡密封禁 / 解封（bans 表 + 永久时 cards.status，只动卡密） ---- */
    if ($action === 'card_set') {
        $cid = post_int('card_id', 0);
        $sid = post_int('sid', 0);
        $on  = post_q('on', '0') === '1';           /* on=1 => 封禁 */
        $key = trim(post_q('card_key', ''));
        $by  = bans_actor();
        $dur = $on ? banexp_until_from_post() : array('ok' => true, 'until' => null, 'label' => '解封', 'error' => '');
        if (empty($dur['ok'])) {
            bans_finish('卡密 #' . $cid . ' 封禁失败：' . $dur['error'], 'err');
        }
        $reason = $on ? post_q('reason', '') : '';
        $r = banexp_toggle_card($cid, $key, $on, $dur['until'], $reason, $by);
        audit_log(
            $on ? 'card.disable' : 'card.enable',
            'card#' . $cid . ($r['card_key'] !== '' ? (' ' . mask_card($r['card_key'])) : ''),
            ($on
                ? ('封禁 ' . $dur['label'] . ' | until=' . ($dur['until'] === null ? 'NULL(永久)' : (int)$dur['until'])
                   . ' | cards.status ' . (!empty($r['legacy_touched']) ? '改成 disabled' : '未动（限时只写封禁表）'))
                : '解封（删 bans 行 + status→active）')
            . ' | 玩家 ServerId ' . $sid
            . ' | 原因 ' . str_limit($reason, 60)
            . ' | ' . ($r['ok'] ? 'ok' : ('失败：' . $r['error']))
        );
        $msg = '';
        if ($r['ok']) {
            $msg = $r['notice'];
            if (!empty($r['warnings'])) {
                $msg .= '（注意：' . implode('；', $r['warnings']) . '）';
            }
        } else {
            $msg = '卡密 #' . $cid . ' 操作失败：' . $r['error'];
        }
        bans_finish($msg, (!empty($r['warnings']) && $r['ok']) ? 'warn' : ($r['ok'] ? 'ok' : 'err'));
    }

    /* ---- 设备封禁 / 解封（bans 表 + 永久时黑名单文件，只动设备） ---- */
    if ($action === 'device_set') {
        $dev = trim(post_q('dev', ''));
        $sid = post_int('sid', 0);
        $on  = post_q('on', '0') === '1';
        if ($dev === '') {
            bans_finish('设备号为空', 'err');
        }
        $by  = bans_actor();
        $dur = $on ? banexp_until_from_post() : array('ok' => true, 'until' => null, 'label' => '解封', 'error' => '');
        if (empty($dur['ok'])) {
            bans_finish('设备封禁失败：' . $dur['error'], 'err');
        }
        $reason = $on ? post_q('reason', '') : '';
        $r = banexp_toggle_device($dev, $on, $dur['until'], $reason, $by);
        audit_log(
            $on ? 'device.ban' : 'device.unban',
            'device ' . str_limit($dev, 40),
            ($on
                ? ('封禁 ' . $dur['label'] . ' | until=' . ($dur['until'] === null ? 'NULL(永久)' : (int)$dur['until'])
                   . ' | device_ban.txt ' . (!empty($r['changed']) ? '已写入' : ($dur['until'] === null ? '无变化' : '未动（限时只写封禁表）')))
                : '解封（删 bans 行 + 从 device_ban.txt 移除）')
            . ' | 玩家 ServerId ' . $sid
            . ' | 原因 ' . str_limit($reason, 60)
            . ' | ' . ($r['ok'] ? 'ok' : ('失败：' . $r['error']))
        );
        $msg = '';
        if ($r['ok']) {
            $msg = $r['notice'];
            if (!empty($r['warnings'])) {
                $msg .= '（注意：' . implode('；', $r['warnings']) . '）';
            }
        } else {
            $msg = '设备封禁失败：' . $r['error'];
        }
        bans_finish($msg, (!empty($r['warnings']) && $r['ok']) ? 'warn' : ($r['ok'] ? 'ok' : 'err'));
    }

    /* ---- 限时封禁表：单行解封（按 kind + target 精确定位） ---- */
    if ($action === 'banexp_clear') {
        $kind   = post_q('kind', '');
        $target = post_q('target', '');
        $by     = bans_actor();
        $r      = banexp_clear($kind, $target);
        audit_log('ban.table_clear', $kind . ' ' . str_limit($target, 60),
            '手动删封禁行 | 删除 ' . (int)$r['deleted'] . ' 行 | ' . ($r['ok'] ? 'ok' : ('失败：' . $r['error'])));
        bans_finish(
            $r['ok']
                ? (bans_dim_label($kind) . '「' . str_limit($target, 40) . '」的封禁行已删除（删了 ' . (int)$r['deleted'] . ' 行）。'
                   . '注意：这里只删封禁表；旧机制（State / cards.status / device_ban.txt）要用行内「解封」按钮才一起还原。')
                : ('删封禁行失败：' . $r['error']),
            $r['ok'] ? 'ok' : 'err'
        );
    }

    /* ---- 限时封禁表：清理所有已到期的行（账号维度**先还原 State 再删行**） ---- */
    if ($action === 'banexp_purge') {
        $r     = banexp_purge_expired();
        $extra = '';
        if (!empty($r['released'])) {
            $extra .= '；其中 ' . (int)$r['released'] . ' 个账号已把 Shittim State 还原成 1 Normal（解封）';
        }
        if (!empty($r['unknown'])) {
            $extra .= '；' . (int)$r['unknown'] . ' 个账号行解析不到 Shittim ServerId，只删了行、没写 State（审计记 state=unknown）';
        }
        if (!empty($r['failed'])) {
            $extra .= '；' . (int)$r['failed'] . ' 个账号 State 还原失败，这些行「没有删」，再点一次会重试';
        }
        if (!empty($r['held'])) {
            $extra .= '；' . (int)$r['held'] . ' 个账号行判定不了目标（Shittim 账号列表读不到），已保留、未删';
        }
        if (!empty($r['deferred'])) {
            $maxRel = defined('BANEXP_PURGE_MAX_RELEASE') ? (int)BANEXP_PURGE_MAX_RELEASE : 200;
            $extra .= '；另有 ' . (int)$r['deferred'] . ' 行超过单次上限（' . $maxRel . '），顺延到下次';
        }
        if (!empty($r['notes'])) {
            $extra .= '；' . implode('；', array_slice($r['notes'], 0, 3));
        }
        audit_log('ban.table_purge', 'bans',
            '清理已到期行：删 ' . (int)$r['deleted'] . ' 条，State 复原 ' . (int)$r['released']
            . '，还原失败保留 ' . (int)$r['failed'] . '，未知 ' . (int)$r['unknown']
            . '，判定不了保留 ' . (int)$r['held']
            . ' | ' . ($r['ok'] ? 'ok' : ('失败：' . $r['error']))
            . '（逐行明细见同一时刻的 ban.purge 那条审计）');
        bans_finish(
            $r['ok'] ? ('已清理 ' . (int)$r['deleted'] . ' 条到期封禁行（永久行一条没动）' . $extra . '。') : ('清理失败：' . $r['error'] . $extra),
            $r['ok'] ? 'ok' : 'err'
        );
    }

    /* ---- 全封 / 全解（显式三项一起做，前端二次确认；时长同样适用） ---- */
    if ($action === 'player_all') {
        $sid = post_int('sid', 0);
        $on  = post_q('on', '0') === '1';
        if ($sid <= 0) {
            bans_finish('账号参数无效（ServerId 缺失）', 'err');
        }
        $by  = bans_actor();
        $dur = $on ? banexp_until_from_post() : array('ok' => true, 'until' => null, 'label' => '解封', 'error' => '');
        if (empty($dur['ok'])) {
            bans_finish('全封失败：' . $dur['error'], 'err');
        }
        $reason = $on ? post_q('reason', '') : '';

        $idx  = ban_accounts_index();
        $pub  = 0;
        $nick = '';
        if ($idx['ok'] && isset($idx['rows'][$sid])) {
            $pub  = isset($idx['rows'][$sid]['publisherAccountId']) ? (int)$idx['rows'][$sid]['publisherAccountId'] : 0;
            $nick = isset($idx['rows'][$sid]['nickname']) ? (string)$idx['rows'][$sid]['nickname'] : '';
        }

        $cards = ban_cards_of_account($sid, $pub);
        $devs  = ban_devices_of_account($sid, $pub);

        $ra = banexp_toggle_account($sid, $pub, $on, $dur['until'], $reason, $by);

        $cardOk   = 0;
        $cardFail = array();
        foreach ($cards as $cid => $c) {
            $rc = banexp_toggle_card($cid, isset($c['card_key']) ? (string)$c['card_key'] : '', $on,
                $dur['until'], $reason, $by);
            if ($rc['ok']) {
                $cardOk++;
            } else {
                $cardFail[] = '#' . $cid . ' ' . $rc['error'];
            }
        }

        $devOk   = 0;
        $devNoop = 0;
        $devFail = array();
        foreach ($devs as $d) {
            $rd = banexp_toggle_device($d, $on, $dur['until'], $reason, $by);
            if ($rd['ok']) {
                if (!empty($rd['changed'])) {
                    $devOk++;
                } else {
                    $devNoop++;
                }
            } else {
                $devFail[] = $d . ' ' . $rd['error'];
            }
        }

        $detail = ($on ? '全封 ' . $dur['label'] : '全解')
            . ' | until=' . ($dur['until'] === null ? 'NULL(永久)' : (int)$dur['until'])
            . ' | 账号：' . ($ra['ok'] ? 'ok' : ('失败 ' . $ra['error']))
            . ' | 卡密：' . $cardOk . '/' . count($cards) . ' 成功'
            . ($cardFail ? ('，失败 ' . implode('；', array_slice($cardFail, 0, 5))) : '')
            . ' | 设备：改动 ' . $devOk . ' / 无变化 ' . $devNoop . ' / 共 ' . count($devs)
            . ($devFail ? ('，失败 ' . implode('；', array_slice($devFail, 0, 5))) : '')
            . ' | 原因 ' . str_limit($reason, 60);
        audit_log($on ? 'ban.all_on' : 'ban.all_off', 'ServerId ' . $sid . ($nick !== '' ? ('（' . $nick . '）') : ''), $detail);

        $errs = array();
        if (!$ra['ok']) {
            $errs[] = '账号：' . $ra['error'];
        }
        if ($cardFail) {
            $errs[] = '卡密：' . implode('；', array_slice($cardFail, 0, 3));
        }
        if ($devFail) {
            $errs[] = '设备：' . implode('；', array_slice($devFail, 0, 3));
        }
        $msg = ($on ? ('全封（' . $dur['label'] . '）') : '全解') . '完成：账号 ' . ($ra['ok'] ? '成功' : '失败')
            . '，卡密 ' . $cardOk . '/' . count($cards) . ' 张'
            . '，设备改动 ' . $devOk . ' 台' . ($devNoop > 0 ? ('（' . $devNoop . ' 台本来就是这个状态）') : '')
            . ($errs ? ('。有失败项 —— ' . implode(' | ', $errs)) : '。三项各自独立，之后可以单独调整。');
        bans_finish($msg, $errs ? 'warn' : 'ok');
    }

    /* ---- 删除账号（硬删除；要求手输昵称或 ServerId） ---- */
    if ($action === 'player_delete') {
        $sid     = post_int('sid', 0);
        $confirm = trim(post_q('confirm_text', ''));
        if ($sid <= 0) {
            bans_finish('账号参数无效（ServerId 缺失）', 'err');
        }

        $idx  = ban_accounts_index();
        $nick = '';
        if ($idx['ok'] && isset($idx['rows'][$sid]) && isset($idx['rows'][$sid]['nickname'])) {
            $nick = trim((string)$idx['rows'][$sid]['nickname']);
        }

        $matched = false;
        foreach (array((string)$sid, '#' . $sid, $nick) as $want) {
            if ($want !== '' && $confirm !== '' && strcasecmp($confirm, $want) === 0) {
                $matched = true;
                break;
            }
        }
        if (!$matched) {
            audit_log('player.delete.abort', 'ServerId ' . $sid,
                '确认文本不匹配，已取消（收到：' . str_limit($confirm, 40) . '）');
            bans_finish('删除已取消：确认框里要输入该玩家的昵称'
                . ($nick !== '' ? ('「' . $nick . '」') : '')
                . ' 或 ServerId ' . $sid . '（比对忽略大小写，其余字符必须完全一致）。', 'err');
        }

        $r = ban_delete_account($sid);
        audit_log('player.delete', 'ServerId ' . $sid . ($nick !== '' ? ('（' . $nick . '）') : ''),
            ($r['ok'] ? 'Shittim 硬删除成功' : ('失败：' . $r['error']))
            . ' | 桥接清理 ' . (int)$r['bridge_rows'] . ' 行'
            . ($r['warning'] !== '' ? (' | ' . $r['warning']) : ''));
        bans_finish(
            $r['ok']
                ? ($r['notice'] . ($r['warning'] !== '' ? ('（注意：' . $r['warning'] . '）') : ''))
                : ('删除失败：' . $r['error']),
            $r['ok'] ? 'ok' : 'err'
        );
    }

    flash_set('未知操作（action=' . str_limit($action, 20) . '）', 'err');
    redirect(bans_back_url());
}

/* ================================================================== 读数据 --- */

$q       = trim(get_q('q', ''));
$stateF  = get_q('state', '');
$roster  = player_roster(array('q' => $q, 'state' => $stateF));
$health  = ba_health();
$summary = ban_summary();
$cand    = ban_device_candidates();
$devStat = ban_device_file_status();
$states  = player_state_map();

/* 封禁表（bans）统计 + 「账号」维度到期自愈（读侧；桥在每次鉴权前也做同样的事，这里是第二张网）。
   自愈只做一件无害的事：把已到期的账号封禁行对应的 Shittim State 还原成 1，然后删掉那行。
   没有过期行时一次 Shittim 调用都不会发生。 */
$bexp  = banexp_summary();
$sweep = array('ok' => true, 'released' => 0, 'failed' => 0, 'checked' => 0, 'notes' => array());
if ($bexp['ok'] && (int)$bexp['account']['expired'] > 0) {
    $sweep = banexp_sweep_account_releases(20);
    if ((int)$sweep['released'] > 0) {
        $bexp = banexp_summary();
    }
}

/* 封禁表所有行（页面「限时封禁表」区块用；封禁中优先、到期近的优先） */
$banRows = array();
$allBans = banexp_all();
if ($allBans['ok']) {
    foreach ($allBans['rows'] as $__r) {
        $banRows[] = $__r;
    }
    usort($banRows, 'banexp_cmp_row');
}

/* 设备候选展示上限（避免设备多的时候页面过大） */
$devShowMax = 300;
$devRows    = array_slice($cand['devices'], 0, $devShowMax, true);

page_header('封禁管理', 'bans');
?>

<div class="alert alert-info">
  <b>三个维度各自独立，互不联动。</b>
  封账号（Shittim <code>Accounts.State</code>）<b>不会</b>禁用卡密，禁卡密（<code>cards.status</code>）<b>不会</b>封账号，
  封设备（SDK 黑名单文件）<b>不会</b>动前两项。需要三项一起做时，用行内的
  <span class="tag tag-err">全封</span> / <span class="tag tag-warn">全解</span>（会二次确认并列出三项）。
  <br>
  <b>每个维度都能限时：</b>封禁按钮左边的时长下拉框 = 永久（默认）/ 1 小时 / 1 天 / 7 天 / 30 天 / 自定义时间点。
  限时封禁只在 <code>bans</code> 表里记一行（<code><?php echo e($bexp['path']); ?></code>），
  <b>到期由读取方判定</b>（until_epoch ≤ 现在 = 未封禁），不需要任何定时任务。
  客户端弹窗文案：永久「<code><?php echo e(ban_msg(null)); ?></code>」，
  限时「<code><?php echo e(ban_msg(time() + 86400, time())); ?></code>」这样的形式。
  <br>
  <b>永久</b>封禁才会同时写旧机制（State / status / device_ban.txt）当双保险；限时不动旧机制，这样到期一定回得来。
</div>

<?php if (!empty($sweep['released']) || !empty($sweep['notes'])) { ?>
  <div class="alert <?php echo empty($sweep['failed']) ? 'alert-info' : 'alert-warn'; ?>">
    <b>账号维度到期自愈：</b>本次释放 <?php echo (int)$sweep['released']; ?> 个已到期账号
    （检查 <?php echo (int)$sweep['checked']; ?> 行，失败 <?php echo (int)$sweep['failed']; ?>）。
    <?php if (!empty($sweep['notes'])) { ?>
      <div class="small muted"><?php echo e(implode('；', array_slice($sweep['notes'], 0, 5))); ?></div>
    <?php } ?>
  </div>
<?php } ?>

<div class="stats">
  <div class="stat <?php echo $summary['account']['banned'] > 0 ? 'stat-err' : 'stat-ok'; ?>">
    <div class="stat-k">① 账号封禁</div>
    <div class="stat-v"><?php echo number_format($summary['account']['banned']); ?></div>
    <div class="stat-sub">
      <?php if ($summary['account']['api_ok']) { ?>
        共 <?php echo number_format($summary['account']['total']); ?> 个账号 · State=Dormant
      <?php } else { ?>
        <span class="tag tag-err">服务端不可达</span>
      <?php } ?>
    </div>
    <div class="stat-sub">bans 表：封禁中 <?php echo (int)$bexp['account']['active']; ?>（永久 <?php echo (int)$bexp['account']['perm']; ?>） · 已到期 <?php echo (int)$bexp['account']['expired']; ?></div>
  </div>
  <div class="stat <?php echo $summary['card']['disabled'] > 0 ? 'stat-warn' : 'stat-ok'; ?>">
    <div class="stat-k">② 卡密禁用</div>
    <div class="stat-v"><?php echo number_format($summary['card']['disabled']); ?></div>
    <div class="stat-sub">
      <?php if ($summary['card']['db_ok']) { ?>
        共 <?php echo number_format($summary['card']['total']); ?> 张卡密 · status=disabled
      <?php } else { ?>
        <span class="tag tag-err">数据库不可用</span>
      <?php } ?>
    </div>
    <div class="stat-sub">bans 表：封禁中 <?php echo (int)$bexp['card']['active']; ?>（永久 <?php echo (int)$bexp['card']['perm']; ?>） · 已到期 <?php echo (int)$bexp['card']['expired']; ?></div>
  </div>
  <div class="stat <?php echo $summary['device']['count'] > 0 ? 'stat-err' : 'stat-ok'; ?>">
    <div class="stat-k">③ 设备封禁</div>
    <div class="stat-v"><?php echo number_format($summary['device']['count']); ?></div>
    <div class="stat-sub">已知设备 <?php echo number_format($summary['device']['known']); ?> 台 · 黑名单文件</div>
    <div class="stat-sub">bans 表：封禁中 <?php echo (int)$bexp['device']['active']; ?>（永久 <?php echo (int)$bexp['device']['perm']; ?>） · 已到期 <?php echo (int)$bexp['device']['expired']; ?></div>
  </div>
  <div class="stat <?php echo $health['ok'] ? 'stat-ok' : 'stat-err'; ?>">
    <div class="stat-k">Shittim 服务端</div>
    <div class="stat-v" style="font-size:15px"><?php echo $health['ok'] ? '在线' : '离线'; ?></div>
    <div class="stat-sub"><?php echo $health['ok'] ? ('响应 ' . (int)$health['ms'] . ' ms') : e(str_limit($health['error'], 40)); ?></div>
  </div>
</div>

<?php
/* ------------------------------------------------- 「孤儿封禁」只读提示 ---
 * 条件：桥接 accounts.db 里 shittim_server_id 非 NULL 的账号，Shittim 侧 State=2(Dormant)，
 *       但 bans 表里没有任何 kind='account' 的对应行。
 * 数据源：player_bridge_accounts() + ban_accounts_index() + banexp_all()，
 *        三份在本页都已经读过（进程内缓存），**不产生额外 API 调用**；
 *        本段只读、不写任何数据（不删行、不改 State）。
 * 历史 bug（只删到期行不还原 State）留下的账号，靠这个提示才看得见。
 */
$orphans = banexp_orphan_accounts(12);
?>
<?php if (!$orphans['ok'] && $orphans['error'] !== '') { ?>
  <div class="alert alert-warn">
    <b>孤儿封禁检测没跑成：</b><?php echo e($orphans['error']); ?>（只影响这条提示，下面的操作都正常）
  </div>
<?php } elseif ($orphans['ok'] && (int)$orphans['count'] > 0) { ?>
  <div class="alert alert-err">
    <b>检测到 <?php echo (int)$orphans['count']; ?> 个「孤儿封禁」（Shittim 已封但无封禁记录），点到「玩家详情 → 解封」可恢复</b>
    <div class="small" style="margin-top:4px">
      <?php
        $__oBits = array();
        foreach ($orphans['sids'] as $__o) {
            $__oBits[] = 'ServerId ' . (int)$__o['server_id']
                . '（publisher ' . (int)$__o['publisher']
                . ($__o['nickname'] !== '' ? ('，' . $__o['nickname']) : '') . '）';
        }
        echo e(implode('、', $__oBits));
        if ((int)$orphans['count'] > count($orphans['sids'])) {
            echo e(' …等共 ' . (int)$orphans['count'] . ' 个');
        }
      ?>
    </div>
    <div class="small muted" style="margin-top:4px">
      Shittim 侧 <code>Accounts.State</code> 还是 2（Dormant），但 <code>bans</code> 表里找不到对应的
      <code>kind='account'</code> 行，桥和本页的「到期自愈」都拿不到线索，这个账号会一直进不去。
      用该玩家行内的「解封」（或「玩家详情 → 解封」）写一次 <code>State=1</code> 即可恢复。
      本提示只读：没有删行、也没有改任何 State（管理员在 Shittim 侧直接改 State 也会命中这条提示，
      那种情况同样用「解封」按钮收回）。已检查 <?php echo (int)$orphans['checked']; ?> 个绑定了 Shittim ServerId 的账号。
    </div>
  </div>
<?php } ?>

<?php if (!$summary['account']['api_ok']) { ?>
  <div class="srv-down">
    读取不到游戏服务端：<b><?php echo e($summary['account']['error']); ?></b><br>
    检查 <code><?php echo e(ba_admin_base()); ?></code> 是否在跑，以及「系统设置」里的 Admin Key 是否与服务端一致。<br>
    账号封禁与删除按钮在此期间不可用；<b>卡密与设备两个维度不依赖 Shittim，仍然可以正常操作。</b>
  </div>
<?php } ?>

<!-- ===================================================================== 玩家 -->
<section class="card">
  <div class="card-h">
    <h2>玩家封禁台</h2>
    <div class="card-h-act">
      <a class="btn btn-sm" href="<?php echo e(u('pages/bans.php')); ?>">刷新</a>
      <a class="btn btn-sm" href="<?php echo e(u('pages/dashboard.php')); ?>">去仪表盘点「立即同步」</a>
    </div>
  </div>

  <form method="get" action="<?php echo e(u('pages/bans.php')); ?>" class="inline"
        style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px">
    <input type="search" name="q" value="<?php echo e($q); ?>" placeholder="昵称 / ServerId / 卡密 / 设备号 / publisherId" style="min-width:280px">
    <select name="state">
      <option value="">全部账号状态</option>
      <?php foreach ($states as $sid0 => $sv) { ?>
        <option value="<?php echo e($sv[0]); ?>"<?php echo strcasecmp($stateF, $sv[0]) === 0 ? ' selected' : ''; ?>>
          <?php echo e($sv[1]); ?>（<?php echo e($sv[0]); ?>）
        </option>
      <?php } ?>
    </select>
    <button type="submit" class="btn btn-primary btn-sm">筛选</button>
    <?php if ($q !== '' || $stateF !== '') { ?>
      <a class="btn btn-sm" href="<?php echo e(u('pages/bans.php')); ?>">清空</a>
    <?php } ?>
  </form>

  <?php if (!$roster['ok']) { ?>
    <p class="muted">Shittim 不可达，玩家列表暂时读不出来。设备黑名单在页面下方仍然可以操作。</p>
  <?php } elseif (!$roster['rows']) { ?>
    <p class="muted">没有匹配的玩家。玩家第一次登录游戏后会自动出现在这里。</p>
  <?php } else { ?>
  <div class="table-wrap">
  <table class="tbl tbl-players">
    <thead>
      <tr>
        <th style="min-width:150px">玩家</th>
        <th style="width:80px">等级</th>
        <th style="min-width:190px">① 账号（State）</th>
        <th style="min-width:260px">② 卡密（cards.status）</th>
        <th style="min-width:240px">③ 设备（黑名单文件）</th>
        <th style="width:250px">操作</th>
      </tr>
    </thead>
    <tbody>
    <?php foreach ($roster['rows'] as $r) {
        $sid     = (int)$r['server_id'];
        $rowDevs = bans_row_devices($r, $cand);
        $stAcct  = ban_status_of($sid, 0, '');
        $acc     = $stAcct['account'];
        $cardN   = isset($r['cards']) && is_array($r['cards']) ? count($r['cards']) : 0;
        $devN    = count($rowDevs);
        $nick    = $r['nickname'] !== '' ? $r['nickname'] : '（无昵称）';
    ?>
      <tr>
        <td>
          <div class="who"><?php echo e($nick); ?> <span class="muted small">#<?php echo $sid; ?></span></div>
          <div class="sub">publisher <code><?php echo e($r['publisher_id'] !== '' ? $r['publisher_id'] : '—'); ?></code></div>
          <div class="sub">最后登录 <?php echo e(player_dt($r['last_connect'] !== '' ? $r['last_connect'] : $r['bridge_last'])); ?></div>
        </td>
        <td class="nowrap">Lv <b><?php echo number_format($r['level']); ?></b></td>

        <!-- ① 账号封禁 -->
        <td>
          <?php
            $pubA    = ($acc['publisher_id'] > 0) ? (int)$acc['publisher_id'] : (int)$r['publisher_id'];
            $rowA    = banexp_account_row($pubA);
            $bannedA = $acc['banned'] || banexp_is_active($rowA);
          ?>
          <?php if ($acc['error'] !== '') { ?>
            <span class="tag tag-gray">状态未知</span>
            <div class="sub"><?php echo e(str_limit($acc['error'], 60)); ?></div>
          <?php } elseif ($bannedA) { ?>
            <span class="tag tag-err">已封禁</span>
            <div class="sub">State=<?php echo e($acc['state']); ?>（<?php echo e($acc['label']); ?>）</div>
          <?php } else { ?>
            <span class="tag tag-ok"><?php echo e($acc['label'] !== '' ? $acc['label'] : '正常'); ?></span>
            <div class="sub">State=<?php echo e($acc['state'] !== '' ? $acc['state'] : '—'); ?></div>
          <?php } ?>
          <?php if ($rowA) { ?>
            <div class="sub">
              封禁表：<?php echo e(banexp_status_line($rowA)); ?>
              <?php echo bans_state_tag($rowA); ?>
            </div>
          <?php } elseif ($pubA > 0) { ?>
            <div class="sub muted">封禁表：未封禁</div>
          <?php } else { ?>
            <div class="sub muted">封禁表：读不到 publisherId，限时封禁没法记</div>
          <?php } ?>
          <form method="post" action="<?php echo e(u('pages/bans.php')); ?>" class="inline"
                style="display:flex;gap:4px;flex-wrap:wrap;align-items:center;margin-top:4px">
            <?php echo csrf_field(); ?>
            <input type="hidden" name="action" value="account_set">
            <input type="hidden" name="sid" value="<?php echo $sid; ?>">
            <input type="hidden" name="pub" value="<?php echo (int)$pubA; ?>">
            <input type="hidden" name="on" value="<?php echo $bannedA ? '0' : '1'; ?>">
            <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
            <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
            <?php if (!$bannedA) { ?>
              <?php echo bans_duration_select(); ?>
              <?php echo bans_until_input(); ?>
              <?php echo bans_reason_input(); ?>
            <?php } ?>
            <button type="submit" class="btn btn-xs <?php echo $bannedA ? 'btn-warn' : 'btn-danger'; ?>"
                    <?php echo ($acc['error'] !== '') ? 'disabled' : ''; ?>>
              <?php echo $bannedA ? '解封账号' : '封禁账号'; ?>
            </button>
          </form>
          <div class="sub">只改账号，不动卡密/设备<?php echo $bannedA ? '' : '；默认永久，可选限时'; ?></div>
        </td>

        <!-- ② 卡密封禁 -->
        <td>
          <?php if (!$r['cards']) { ?>
            <span class="muted small">没有绑定的卡密</span>
          <?php } else { foreach ($r['cards'] as $mc) {
              $cidN   = (int)$mc['card_id'];
              $keyC   = (string)$mc['card_key'];
              $stCard = ban_status_of(0, $cidN, '');
              $cc     = $stCard['card'];
              $rowC   = banexp_card_row($keyC);
              $cb     = ($cc['error'] === '' ? $cc['banned'] : ((string)$mc['status'] !== 'active'))
                        || banexp_is_active($rowC);
          ?>
            <div style="margin-bottom:8px">
              <code class="small" title="<?php echo e($keyC); ?>"><?php echo e(mask_card($keyC)); ?></code>
              <?php if ($cc['error'] !== '') { ?>
                <span class="tag tag-gray">未知</span>
              <?php } elseif ($cb) { ?>
                <span class="tag tag-err">已封禁</span>
              <?php } else { ?>
                <span class="tag tag-ok">可用</span>
              <?php } ?>
              <?php echo bans_state_tag($rowC); ?>
              <?php if ($rowC) { ?>
                <div class="sub">封禁表：<?php echo e(banexp_status_line($rowC)); ?></div>
              <?php } ?>
              <form method="post" action="<?php echo e(u('pages/bans.php')); ?>" class="inline"
                    style="display:flex;gap:4px;flex-wrap:wrap;align-items:center;margin-top:2px">
                <?php echo csrf_field(); ?>
                <input type="hidden" name="action" value="card_set">
                <input type="hidden" name="card_id" value="<?php echo $cidN; ?>">
                <input type="hidden" name="card_key" value="<?php echo e($keyC); ?>">
                <input type="hidden" name="sid" value="<?php echo $sid; ?>">
                <input type="hidden" name="on" value="<?php echo $cb ? '0' : '1'; ?>">
                <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
                <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
                <?php if (!$cb) { ?>
                  <?php echo bans_duration_select(); ?>
                  <?php echo bans_until_input(); ?>
                  <?php echo bans_reason_input(); ?>
                <?php } ?>
                <button type="submit" class="btn btn-xs <?php echo $cb ? 'btn-warn' : 'btn-danger'; ?>">
                  <?php echo $cb ? '解封' : '封禁'; ?>
                </button>
              </form>
            </div>
          <?php } } ?>
          <?php if ($r['cards']) { ?>
            <div class="sub">永久：封禁表 + status=disabled（≤60 秒同步）。限时：只写封禁表，到期自动恢复，不用等同步。</div>
          <?php } ?>
        </td>

        <!-- ③ 设备封禁 -->
        <td>
          <?php if (!$rowDevs) { ?>
            <span class="muted small">没有可用设备号</span>
          <?php } else { foreach ($rowDevs as $dev) {
              $rowD      = banexp_device_row($dev);
              $devBanned = ban_device_has($dev) || banexp_is_active($rowD);
          ?>
            <div style="margin-bottom:8px">
              <code class="small" title="<?php echo e($dev); ?>"><?php echo e(str_limit($dev, 18)); ?></code>
              <?php if ($devBanned) { ?>
                <span class="tag tag-err">已封禁</span>
              <?php } else { ?>
                <span class="tag tag-ok">正常</span>
              <?php } ?>
              <?php echo bans_state_tag($rowD); ?>
              <?php if ($rowD) { ?>
                <div class="sub">封禁表：<?php echo e(banexp_status_line($rowD)); ?></div>
              <?php } ?>
              <form method="post" action="<?php echo e(u('pages/bans.php')); ?>" class="inline"
                    style="display:flex;gap:4px;flex-wrap:wrap;align-items:center;margin-top:2px">
                <?php echo csrf_field(); ?>
                <input type="hidden" name="action" value="device_set">
                <input type="hidden" name="dev" value="<?php echo e($dev); ?>">
                <input type="hidden" name="sid" value="<?php echo $sid; ?>">
                <input type="hidden" name="on" value="<?php echo $devBanned ? '0' : '1'; ?>">
                <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
                <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
                <?php if (!$devBanned) { ?>
                  <?php echo bans_duration_select(); ?>
                  <?php echo bans_until_input(); ?>
                  <?php echo bans_reason_input(); ?>
                <?php } ?>
                <button type="submit" class="btn btn-xs <?php echo $devBanned ? 'btn-warn' : 'btn-danger'; ?>">
                  <?php echo $devBanned ? '解封设备' : '封禁设备'; ?>
                </button>
              </form>
            </div>
          <?php } } ?>
          <div class="sub">永久：封禁表 + device_ban.txt。限时：只写封禁表，SDK 每次登录都按到期判定。</div>
        </td>

        <!-- 操作：全封/全解 + 硬删除 -->
        <td>
          <div class="row-actions">
            <a class="btn btn-xs" href="<?php echo e(u('pages/player_detail.php?sid=' . $sid)); ?>">详情</a>
            <a class="btn btn-xs" href="<?php echo e(u('pages/mail.php?sid=' . $sid)); ?>">发奖</a>
          </div>

          <form method="post" action="<?php echo e(u('pages/bans.php')); ?>" style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap;align-items:center">
            <?php echo csrf_field(); ?>
            <input type="hidden" name="action" value="player_all">
            <input type="hidden" name="sid" value="<?php echo $sid; ?>">
            <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
            <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
            <?php echo bans_duration_select(); ?>
            <?php echo bans_until_input(); ?>
            <?php echo bans_reason_input(); ?>
            <button type="submit" name="on" value="1" class="btn btn-xs btn-danger"
                    data-confirm="<?php echo e(bans_all_confirm($nick, $sid, $cardN, $devN, true)); ?>">全封（三项）</button>
            <button type="submit" name="on" value="0" class="btn btn-xs btn-warn"
                    data-confirm="<?php echo e(bans_all_confirm($nick, $sid, $cardN, $devN, false)); ?>">全解（三项）</button>
          </form>
          <div class="sub">会同时改三处，点之前会二次确认；时长取左边的下拉框（默认永久）</div>

          <details style="margin-top:6px">
            <summary class="btn btn-xs btn-danger" style="list-style:none">删除账号…</summary>
            <form method="post" action="<?php echo e(u('pages/bans.php')); ?>"
                  style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap;align-items:center">
              <?php echo csrf_field(); ?>
              <input type="hidden" name="action" value="player_delete">
              <input type="hidden" name="sid" value="<?php echo $sid; ?>">
              <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
              <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
              <input type="text" name="confirm_text" value="" autocomplete="off"
                     placeholder="输入昵称或 <?php echo $sid; ?>"
                     style="width:170px;padding:5px 7px;border:1px solid #d3dae3;border-radius:8px;font-size:12.5px;font-family:inherit">
              <button type="submit" class="btn btn-xs btn-danger"
                      data-confirm="<?php echo e('即将硬删除玩家 ' . ($r['nickname'] !== '' ? $r['nickname'] : '（无昵称）') . '（ServerId ' . $sid . '）：' . "\n" . '· Shittim 里该账号的所有数据（货币/角色/道具/邮件/各类 AccountServerId 子表）会级联删除' . "\n" . '· 桥接 accounts.db 里 shittim_server_id=' . $sid . ' 的那一行也会删掉' . "\n" . '· 这个操作不可恢复，也没有回收站。确定删除吗？'); ?>">确认硬删除</button>
            </form>
            <div class="sub" style="margin-top:4px">
              硬删除不可恢复：会清空 Shittim 里该账号的全部数据，并删掉桥接
              <code>accounts.db</code> 中 <code>shittim_server_id=<?php echo $sid; ?></code> 的那一行
              （<code>shittim_server_id IS NULL</code> 的老行不动）。
              必须先在输入框里手打昵称或 ServerId 才能提交。
            </div>
          </details>
        </td>
      </tr>
    <?php } ?>
    </tbody>
  </table>
  </div>
  <p class="muted small" style="margin-top:8px">
    共 <?php echo number_format(count($roster['rows'])); ?> 个玩家。三个按钮/表单各管一件事，互不牵连。
  </p>
  <?php } ?>
</section>

<!-- =========================================================== 限时封禁表 bans -->
<section class="card">
  <div class="card-h">
    <h2>限时封禁表（bans）</h2>
    <div class="card-h-act">
      <form method="post" action="<?php echo e(u('pages/bans.php')); ?>" class="inline" style="display:inline">
        <?php echo csrf_field(); ?>
        <input type="hidden" name="action" value="banexp_purge">
        <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
        <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
        <button type="submit" class="btn btn-sm btn-warn"
                data-confirm="<?php echo e(bans_purge_confirm()); ?>"
                title="会先把对应账号的 Shittim State 还原成 1 Normal，再删除到期记录；不可撤销">
          清理到期记录（会自动解除账号封禁）
        </button>
      </form>
      <a class="btn btn-sm" href="<?php echo e(u('pages/bans.php')); ?>">刷新</a>
    </div>
  </div>

  <div class="small muted" style="margin-bottom:8px">
    路径 <code><?php echo e($bexp['path']); ?></code> ·
    共 <?php echo number_format((int)$bexp['total']); ?> 行
    （封禁中 <?php echo (int)($bexp['account']['active'] + $bexp['card']['active'] + $bexp['device']['active']); ?>，
    其中永久 <?php echo (int)($bexp['account']['perm'] + $bexp['card']['perm'] + $bexp['device']['perm']); ?>；
    已到期 <?php echo (int)($bexp['account']['expired'] + $bexp['card']['expired'] + $bexp['device']['expired']); ?>）
    · 到期判定只在读取方做，没有任何定时任务
  </div>

  <?php if (!$bexp['ok']) { echo alert_box($bexp['error'], 'err'); } ?>

  <?php if (!$banRows) { ?>
    <p class="muted">封禁表是空的。上面三个维度点「封禁」时会自动往里写一行（永久 until_epoch=NULL，限时写到期时间）。</p>
  <?php } else { ?>
  <div class="table-wrap">
  <table class="tbl">
    <thead>
      <tr>
        <th style="width:70px">维度</th>
        <th style="min-width:220px">目标</th>
        <th style="min-width:150px">状态</th>
        <th style="min-width:150px">到期</th>
        <th style="min-width:120px">原因</th>
        <th style="min-width:120px">创建</th>
        <th style="width:80px">操作</th>
      </tr>
    </thead>
    <tbody>
    <?php foreach ($banRows as $brow) {
        $bKind = (string)$brow['kind'];
        $bTgt  = (string)$brow['target'];
        $bShow = ($bKind === 'card') ? mask_card($bTgt) : str_limit($bTgt, 40);
    ?>
      <tr>
        <td><?php echo e(bans_dim_label($bKind)); ?></td>
        <td><code class="small" title="<?php echo e($bTgt); ?>"><?php echo e($bShow); ?></code></td>
        <td>
          <?php if (banexp_is_active($brow)) { ?>
            <span class="tag tag-err">封禁中</span>
          <?php } else { ?>
            <span class="tag tag-gray">已到期（未封禁）</span>
          <?php } ?>
          <?php echo bans_state_tag($brow); ?>
        </td>
        <td class="small">
          <?php echo $brow['until_epoch'] === null ? '永久' : e(ban_msg_time((int)$brow['until_epoch'])); ?>
        </td>
        <td class="small muted"><?php echo e(str_limit((string)$brow['reason'], 30)); ?></td>
        <td class="small muted">
          <?php echo e((string)$brow['created_at']); ?><br>
          <span class="muted"><?php echo e(str_limit((string)$brow['created_by'], 14)); ?></span>
        </td>
        <td>
          <form method="post" action="<?php echo e(u('pages/bans.php')); ?>" class="inline">
            <?php echo csrf_field(); ?>
            <input type="hidden" name="action" value="banexp_clear">
            <input type="hidden" name="kind" value="<?php echo e($bKind); ?>">
            <input type="hidden" name="target" value="<?php echo e($bTgt); ?>">
            <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
            <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
            <button type="submit" class="btn btn-xs btn-warn"
                    data-confirm="只删这一行封禁记录（不影响其他行）。如果要连旧机制一起还原，请用上面玩家表/设备表里的「解封」按钮。确定删除吗？">
              删行
            </button>
          </form>
        </td>
      </tr>
    <?php } ?>
    </tbody>
  </table>
  </div>
  <?php } ?>
</section>

<!-- ================================================================= 设备黑名单 -->
<section class="card">
  <div class="card-h">
    <h2>设备黑名单文件（SDK 侧）</h2>
    <div class="card-h-act">
      <a class="btn btn-sm" href="<?php echo e(u('pages/bans.php')); ?>">刷新</a>
    </div>
  </div>

  <div class="small" style="margin-bottom:8px">
    路径 <code><?php echo e($devStat['path']); ?></code> ·
    <?php if ($devStat['exists']) { ?>
      已存在 <?php echo number_format($devStat['bytes']); ?> B，<?php echo number_format($devStat['count']); ?> 条，最后修改
      <?php echo e(fmt_ts($devStat['mtime'])); ?>
    <?php } else { ?>
      文件还不存在（第一次封禁会自动创建）
    <?php } ?>
    ·
    <?php if ($devStat['writable'] || $devStat['dir_writable']) { ?>
      <span class="tag tag-ok">PHP 可写</span>
    <?php } else { ?>
      <span class="tag tag-err">PHP 不可写</span>
    <?php } ?>
  </div>
  <?php if ($devStat['error'] !== '') { echo alert_box($devStat['error'], 'warn'); } ?>
  <?php foreach ($cand['warnings'] as $w) { echo alert_box($w, 'warn'); } ?>

  <form method="post" action="<?php echo e(u('pages/bans.php')); ?>"
        style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:10px 0">
    <?php echo csrf_field(); ?>
    <input type="hidden" name="action" value="device_set">
    <input type="hidden" name="on" value="1">
    <input type="hidden" name="sid" value="0">
    <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
    <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
    <input type="text" name="dev" value="" autocomplete="off" placeholder="手打一个设备号，直接封禁"
           style="min-width:260px;padding:6px 8px;border:1px solid #d3dae3;border-radius:8px;font-size:13px;font-family:inherit">
    <?php echo bans_duration_select(); ?>
    <?php echo bans_until_input(); ?>
    <?php echo bans_reason_input(); ?>
    <button type="submit" class="btn btn-sm btn-danger">封禁设备</button>
    <span class="muted small">默认永久（= 写进 device_ban.txt）；选限时则只写 bans 表，到期自动解除</span>
  </form>

  <?php if (!$cand['devices']) { ?>
    <p class="muted">还没有可封禁的设备号（accounts.db / cards.json / card_devices 三路都没有数据）。</p>
  <?php } else { ?>
  <div class="table-wrap">
  <table class="tbl">
    <thead>
      <tr>
        <th style="min-width:220px">设备号</th>
        <th style="width:90px">状态</th>
        <th style="min-width:140px">来源</th>
        <th style="min-width:160px">绑定过的卡密</th>
        <th style="min-width:150px">关联账号</th>
        <th style="width:110px">操作</th>
      </tr>
    </thead>
    <tbody>
    <?php foreach ($devRows as $dev => $info) { ?>
      <tr>
        <td><code class="small" title="<?php echo e($dev); ?>"><?php echo e(str_limit($dev, 40)); ?></code></td>
        <td>
          <?php
            $rowD      = banexp_device_row($dev);
            $devBanned = !empty($info['banned']) || banexp_is_active($rowD);
          ?>
          <?php if ($devBanned) { ?>
            <span class="tag tag-err">已封禁</span>
          <?php } else { ?>
            <span class="tag tag-ok">未封禁</span>
          <?php } ?>
          <?php echo bans_state_tag($rowD); ?>
          <?php if ($rowD) { ?>
            <div class="sub"><?php echo e(banexp_status_line($rowD)); ?></div>
          <?php } ?>
        </td>
        <td class="small muted"><?php echo e(implode(' / ', $info['sources'])); ?></td>
        <td class="small">
          <?php if ($info['cards']) { ?>
            <?php foreach (array_slice($info['cards'], 0, 3) as $ck) { ?>
              <div><code class="small"><?php echo e(mask_card($ck)); ?></code></div>
            <?php } ?>
            <?php if (count($info['cards']) > 3) { ?>
              <div class="muted small">还有 <?php echo count($info['cards']) - 3; ?> 张</div>
            <?php } ?>
          <?php } else { ?>
            <span class="muted">—</span>
          <?php } ?>
        </td>
        <td class="small">
          <?php if ($info['accounts']) { ?>
            <?php $accShown = 0; foreach ($info['accounts'] as $accItem) { $accShown++; if ($accShown > 3) { break; } ?>
              <div>
                <a href="<?php echo e(u('pages/player_detail.php?sid=' . (int)$accItem['server_id'])); ?>">#<?php echo (int)$accItem['server_id']; ?></a>
                <?php echo e(str_limit($accItem['nickname'] !== '' ? $accItem['nickname'] : '（无昵称）', 14)); ?>
              </div>
            <?php } ?>
            <?php if (count($info['accounts']) > 3) { ?>
              <div class="muted small">还有 <?php echo count($info['accounts']) - 3; ?> 个</div>
            <?php } ?>
          <?php } else { ?>
            <span class="muted">—</span>
          <?php } ?>
        </td>
        <td>
          <form method="post" action="<?php echo e(u('pages/bans.php')); ?>" class="inline"
                style="display:flex;gap:4px;flex-wrap:wrap;align-items:center">
            <?php echo csrf_field(); ?>
            <input type="hidden" name="action" value="device_set">
            <input type="hidden" name="dev" value="<?php echo e($dev); ?>">
            <input type="hidden" name="sid" value="0">
            <input type="hidden" name="on" value="<?php echo $devBanned ? '0' : '1'; ?>">
            <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
            <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
            <?php if (!$devBanned) { ?>
              <?php echo bans_duration_select(); ?>
              <?php echo bans_until_input(); ?>
            <?php } ?>
            <button type="submit" class="btn btn-xs <?php echo $devBanned ? 'btn-warn' : 'btn-danger'; ?>">
              <?php echo $devBanned ? '解封' : '封禁'; ?>
            </button>
          </form>
        </td>
      </tr>
    <?php } ?>
    </tbody>
  </table>
  </div>
  <?php if (count($cand['devices']) > $devShowMax) { ?>
    <p class="muted small">共 <?php echo number_format(count($cand['devices'])); ?> 台设备，这里只显示前
      <?php echo number_format($devShowMax); ?> 台。其余可以在上面用「手打一个设备号」直接封禁。</p>
  <?php } ?>
  <?php } ?>

  <?php if ($devStat['count'] > 0) { ?>
    <div style="margin-top:10px">
      <div class="small muted" style="margin-bottom:4px">当前黑名单内容（<?php echo number_format($devStat['count']); ?> 条，按文件顺序）：</div>
      <?php foreach (ban_device_list() as $dev) { ?>
        <div class="small" style="display:flex;gap:6px;align-items:center;margin-bottom:4px">
          <code title="<?php echo e($dev); ?>"><?php echo e(str_limit($dev, 44)); ?></code>
          <form method="post" action="<?php echo e(u('pages/bans.php')); ?>" class="inline">
            <?php echo csrf_field(); ?>
            <input type="hidden" name="action" value="device_set">
            <input type="hidden" name="dev" value="<?php echo e($dev); ?>">
            <input type="hidden" name="sid" value="0">
            <input type="hidden" name="on" value="0">
            <input type="hidden" name="keep_q" value="<?php echo e($q); ?>">
            <input type="hidden" name="keep_state" value="<?php echo e($stateF); ?>">
            <button type="submit" class="btn btn-xs btn-warn">解封</button>
          </form>
        </div>
      <?php } ?>
    </div>
  <?php } ?>
</section>

<script>
(function () {
  function findByAttr(el, attr) {
    while (el && el !== document && el !== document.documentElement) {
      if (el.getAttribute && el.getAttribute(attr) !== null) { return el; }
      el = el.parentNode;
    }
    return null;
  }
  /* 全封 / 全解 / 硬删除：点之前弹服务端拼好的确认文案 */
  document.addEventListener('click', function (ev) {
    var el = findByAttr(ev.target, 'data-confirm');
    if (!el) { return; }
    var msg = el.getAttribute('data-confirm') || '确定继续？';
    if (!window.confirm(msg)) {
      ev.preventDefault();
      ev.stopPropagation();
    }
  }, true);
})();
</script>

<?php page_footer(); ?>
