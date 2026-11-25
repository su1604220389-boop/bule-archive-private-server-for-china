<?php
/**
 * pages/settings.php — 系统设置
 *   同步（立即同步 / 从 cards.json 导入）、生成默认规则、路径、环境自检
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';

require_login();

$charset_presets = array(
    'safe'   => array('不含易混字符（推荐）', 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'),
    'upper'  => array('大写字母', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
    'alnum'  => array('大写+小写+数字', 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'),
    'digits' => array('纯数字', '0123456789'),
);

if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $act = post_q('action');

    /* 同步类动作交给 inc/sync.php */
    $sync_res = sync_do_web_action();
    if ($sync_res !== null) {
        flash_set($sync_res['msg'], $sync_res['ok'] ? 'ok' : 'err');
        redirect_self();
    }

    try {
        if ($act === 'save_general') {
            $len     = post_int('auto_gen_len', 16, 8, 64);
            $charset = post_q('auto_gen_charset');
            $prefix  = trim(post_q('auto_gen_prefix'));
            $per     = post_int('page_size', 50, 10, 500);

            $preset_name = $charset;
            if (isset($charset_presets[$charset])) {
                $charset = $charset_presets[$charset][1];
            }
            $charset = preg_replace('/\s+/', '', (string)$charset);
            if (strlen($charset) < 2) {
                flash_set('字符集至少 2 个字符', 'err');
                redirect_self();
            }
            if (preg_match('/[^\x21-\x7E]/', $charset)) {
                flash_set('字符集只支持可见 ASCII 字符', 'err');
                redirect_self();
            }
            if ($prefix !== '' && !preg_match('/^[A-Za-z0-9_\-]{1,16}$/', $prefix)) {
                flash_set('前缀只能是 1-16 位字母/数字/下划线/减号', 'err');
                redirect_self();
            }
            setting_set('auto_gen_len', $len);
            setting_set('auto_gen_charset', $charset);
            setting_set('auto_gen_prefix', $prefix);
            setting_set('page_size', $per);
            audit_log('settings.save', '生成默认规则',
                'len=' . $len . ' charset_len=' . strlen($charset) . ' prefix=' . $prefix . ' page_size=' . $per);
            flash_set('已保存生成默认规则', 'ok');
        } elseif ($act === 'save_paths') {
            $jp = trim(post_q('cards_json_path'));
            $lp = trim(post_q('sdk_log_path'));
            if ($jp === '' || substr($jp, 0, 1) !== '/') {
                flash_set('cards.json 必须是绝对路径（以 / 开头）', 'err');
                redirect_self();
            }
            if ($lp === '' || substr($lp, 0, 1) !== '/') {
                flash_set('sdk.log 必须是绝对路径（以 / 开头）', 'err');
                redirect_self();
            }
            setting_set('cards_json_path', $jp);
            setting_set('sdk_log_path', $lp);
            audit_log('settings.save', '路径设置', 'cards_json=' . $jp . ' sdk_log=' . $lp);
            flash_set('已保存路径设置（注意：改路径后要确认 cron 用的是新路径）', 'ok');
        } elseif ($act === 'save_ba') {
            $base  = trim((string)post_q('ba_admin_base', ''));
            $key   = trim((string)post_q('ba_admin_key', ''));
            $clear = post_q('clear_ba_key', '') === '1';
            $acc   = trim((string)post_q('ba_accounts_db', ''));
            if ($base !== '' && !preg_match('#^https?://#i', $base)) {
                flash_set('服务端地址必须以 http:// 或 https:// 开头', 'err');
                redirect_self();
            }
            if ($acc !== '' && substr($acc, 0, 1) !== '/') {
                flash_set('accounts.db 必须是绝对路径', 'err');
                redirect_self();
            }
            setting_set('ba_admin_base', $base === '' ? 'http://127.0.0.1:5000' : rtrim($base, '/'));
            if ($clear) {
                setting_set('ba_admin_key', '');
            } elseif ($key !== '') {
                setting_set('ba_admin_key', $key);
            }
            /* 留空且未勾"清除" = 保持原值：页面不显示明文，管理员无法提交回原值 */
            setting_set('ba_accounts_db', $acc);
            ba_cache_flush('static_');
            ba_cfg(true);
            audit_log('settings.save', '游戏服务端连接',
                'base=' . $base . ' key=' . ($clear ? 'cleared'
                    : ($key !== '' ? 'set(len=' . strlen($key) . ')' : 'kept'))
                . ' accounts_db=' . $acc);
            flash_set('已保存服务端连接设置', 'ok');
        } elseif ($act === 'reveal_key') {
            $revealNow = (string)setting_get('ba_admin_key', defined('BA_ADMIN_KEY') ? BA_ADMIN_KEY : '');
            if ($revealNow === '') {
                flash_set('当前没有配置 Admin Key', 'err');
            } else {
                /* 只在一次后续请求里出现，不写入页面静态内容 */
                secret_once_set('ba_admin_key', $revealNow, 120);
                audit_log('settings.reveal_key', 'Admin Key', '管理员在设置页点击了一次「显示」');
                flash_set('Admin Key 已临时显示一次，刷新或离开本页后消失', 'info');
            }
        } elseif ($act === 'test_ba') {
            $h = ba_health();
            if ($h['ok']) {
                flash_set('连通正常：' . $h['name'] . ' 版本 ' . $h['version']
                    . '，账号 ' . $h['accounts'] . ' 个，响应 ' . $h['ms'] . ' ms', 'ok');
            } else {
                flash_set('连不上：' . $h['error'] . '（地址 ' . ba_admin_base() . '）', 'err');
            }
        } elseif ($act === 'flush_ba_cache') {
            $n = ba_cache_flush('');
            audit_log('settings.save', '清空玩家域缓存', $n . ' 个文件');
            flash_set('已清空静态数据缓存 ' . $n . ' 个文件', 'ok');
        } elseif ($act === 'cleanup_sessions') {
            $st = db_run('DELETE FROM sessions WHERE expires_at < ?', array(time()));
            $st2 = db_run('DELETE FROM login_attempts WHERE ts < ?', array(time() - 86400));
            audit_log('settings.save', '清理会话', 'sessions=' . $st->rowCount() . ' attempts=' . $st2->rowCount());
            flash_set('已清理过期会话 ' . $st->rowCount() . ' 条、旧登录记录 ' . $st2->rowCount() . ' 条', 'ok');
        } else {
            flash_set('未知操作', 'err');
        }
    } catch (Throwable $e) {
        flash_set('保存失败：' . $e->getMessage(), 'err');
    }
    redirect_self();
}

$sync = sync_status();
$log_path = (string)setting_get('sdk_log_path', SDK_LOG_PATH);

/* cards.json 预览 */
$preview = array('ok' => false, 'count' => 0, 'keys' => array(), 'err' => '');
$rd = sync_read_json($sync['json_path']);
if ($rd['err'] !== '') {
    $preview['err'] = $rd['err'];
} elseif ($rd['exists']) {
    $preview['ok']    = true;
    $preview['count'] = count($rd['cards']);
    $i = 0;
    foreach ($rd['cards'] as $k => $v) {
        if ($i++ >= 3) {
            break;
        }
        $devs = isset($v['devices']) && is_array($v['devices']) ? count($v['devices']) : 0;
        $preview['keys'][] = array((string)$k, $devs, isset($v['expire']) ? (int)$v['expire'] : 0);
    }
}

/* 环境自检 */
$check = array();
$check['php_version'] = array(PHP_VERSION, version_compare(PHP_VERSION, '7.4.0', '>='));
foreach (array('pdo_mysql', 'mbstring', 'json', 'openssl') as $ext) {
    $check['ext_' . $ext] = array(extension_loaded($ext) ? '已加载' : '缺失', extension_loaded($ext));
}
$check['install_php'] = array(
    is_file(APP_ROOT . '/install.php') ? 'install.php 仍在（建议删除）' : '已删除',
    !is_file(APP_ROOT . '/install.php'),
);
$check['lock'] = array(
    is_file(APP_ROOT . '/installed.lock') ? '已自锁' : '无 installed.lock',
    is_file(APP_ROOT . '/installed.lock'),
);
$check['state_dir'] = array(
    is_dir(APP_STATE_DIR) ? (is_writable(APP_STATE_DIR) ? '可写' : '不可写（面板同步会退化）') : '不存在',
    is_dir(APP_STATE_DIR) && is_writable(APP_STATE_DIR),
);
$check['log_dir'] = array(
    is_dir(APP_LOG_DIR) ? (is_writable(APP_LOG_DIR) ? '可写' : '不可写') : '不存在',
    is_dir(APP_LOG_DIR) && is_writable(APP_LOG_DIR),
);
$check['post_max'] = array((string)ini_get('post_max_size'), true);
$check['upload_max'] = array((string)ini_get('upload_max_filesize'), true);

$cur_charset = (string)setting_get('auto_gen_charset', $charset_presets['safe'][1]);
$cur_preset  = 'custom';
foreach ($charset_presets as $pk => $pv) {
    if ($pv[1] === $cur_charset) {
        $cur_preset = $pk;
    }
}

page_header('系统设置', 'settings');
?>

<div class="cols">
  <section class="card">
    <div class="card-h"><h2>同步（MySQL → cards.json）</h2>
      <div class="card-h-act">
        <form method="post" action="<?php echo e(u('pages/settings.php')); ?>" class="inline">
          <?php echo csrf_field(); ?>
          <input type="hidden" name="action" value="sync_now">
          <button type="submit" class="btn btn-sm btn-primary">立即同步</button>
        </form>
        <form method="post" action="<?php echo e(u('pages/settings.php')); ?>" class="inline"
              onsubmit="return confirm('把 cards.json 里数据库没有的卡密导入数据库？不会删除任何东西。');">
          <?php echo csrf_field(); ?>
          <input type="hidden" name="action" value="import_json">
          <button type="submit" class="btn btn-sm">从 cards.json 导入</button>
        </form>
      </div>
    </div>
    <table class="kv">
      <tr><th>最后同步</th><td><?php echo $sync['last_sync_at'] > 0 ? e(fmt_ts($sync['last_sync_at'])) : '<span class="bad">从未同步</span>'; ?></td></tr>
      <tr><th>上次导出条数</th><td><?php echo number_format($sync['last_count']); ?>
        <?php if ($sync['last_source'] !== '') { ?><span class="muted small">（<?php echo e($sync['last_source']); ?>）</span><?php } ?></td></tr>
      <tr><th>cards.json</th><td><code class="small"><?php echo e($sync['json_path']); ?></code><br>
        <?php if ($preview['err'] !== '') { ?>
          <span class="bad"><?php echo e($preview['err']); ?></span>
        <?php } elseif (!$preview['ok']) { ?>
          <span class="warn">文件不存在（第一次同步后会出现）</span>
        <?php } else { ?>
          文件内 <b><?php echo number_format($preview['count']); ?></b> 个卡密 ·
          <?php echo e(bytes_human($sync['bytes'])); ?> · mtime <?php echo e(fmt_ts($sync['mtime'])); ?>
          <?php if ($preview['keys']) { ?>
            <div class="muted small">示例：
              <?php foreach ($preview['keys'] as $pk) { ?>
                <code><?php echo e(mask_card($pk[0])); ?></code>(<?php echo (int)$pk[1]; ?>台)
              <?php } ?>
            </div>
          <?php } ?>
        <?php } ?>
      </td></tr>
      <tr><th>数据库</th><td>共 <?php echo number_format($sync['db_all']); ?> 张，
        active <?php echo number_format($sync['db_active']); ?> 张</td></tr>
      <tr><th>写权限</th><td><?php echo $sync['dir_writable']
        ? '<span class="ok">目录可写，面板可直连同步</span>'
        : '<span class="warn">目录不可写 → 点"立即同步"只写标记，由 cron 执行</span>'; ?></td></tr>
      <tr><th>sdk.log</th><td><code class="small"><?php echo e($log_path); ?></code>
        <?php echo is_readable($log_path) ? '<span class="ok">可读</span>' : '<span class="warn">读不到</span>'; ?></td></tr>
    </table>
    <p class="muted small">
      卡密变动最多 60 秒生效。cron（宝塔计划任务，root 身份）：
    </p>
    <pre class="code">* * * * * /usr/bin/php <?php echo e(str_replace('\\', '/', dirname(__DIR__))); ?>/cron/sync_cards.php &gt;&gt; <?php echo e(str_replace('\\', '/', dirname(__DIR__))); ?>/logs/sync.log 2&gt;&amp;1</pre>
    <p class="muted small">想更快生效：把周期改成"1 分钟"，或在面板点「立即同步」。</p>
  </section>

  <section class="card">
    <div class="card-h"><h2>生成默认规则</h2></div>
    <form method="post" action="<?php echo e(u('pages/settings.php')); ?>" class="form-grid">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="action" value="save_general">
      <label class="fld"><span>默认长度</span>
        <input type="number" name="auto_gen_len" value="<?php echo (int)setting_int('auto_gen_len', 16); ?>" min="8" max="64">
      </label>
      <label class="fld"><span>默认字符集</span>
        <select name="auto_gen_charset">
          <?php foreach ($charset_presets as $pk => $pv) { ?>
            <option value="<?php echo e($pk); ?>"<?php echo $cur_preset === $pk ? ' selected' : ''; ?>>
              <?php echo e($pv[0]); ?>
            </option>
          <?php } ?>
          <option value="<?php echo e($cur_charset); ?>"<?php echo $cur_preset === 'custom' ? ' selected' : ''; ?>>
            自定义（当前 <?php echo e(str_limit($cur_charset, 24)); ?>）
          </option>
        </select>
        <em>选"自定义"这个选项会保留当前值</em>
      </label>
      <label class="fld"><span>默认前缀</span>
        <input type="text" name="auto_gen_prefix" value="<?php echo e((string)setting_get('auto_gen_prefix', '')); ?>" maxlength="16">
      </label>
      <label class="fld"><span>列表默认每页</span>
        <input type="number" name="page_size" value="<?php echo (int)setting_int('page_size', 50); ?>" min="10" max="500">
      </label>
      <div class="fld fld-wide fld-actions">
        <button type="submit" class="btn btn-primary">保存</button>
      </div>
    </form>
  </section>
</div>

<div class="cols">
  <section class="card">
    <div class="card-h"><h2>路径设置</h2></div>
    <form method="post" action="<?php echo e(u('pages/settings.php')); ?>" class="form-grid">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="action" value="save_paths">
      <label class="fld fld-wide"><span>cards.json 路径</span>
        <input type="text" name="cards_json_path" value="<?php echo e($sync['json_path']); ?>" maxlength="500">
        <em>必须和 sdkcard.py 里的 CARDS 常量一致</em>
      </label>
      <label class="fld fld-wide"><span>sdk.log 路径</span>
        <input type="text" name="sdk_log_path" value="<?php echo e($log_path); ?>" maxlength="500">
        <em>只读解析，不会修改它</em>
      </label>
      <div class="fld fld-wide fld-actions">
        <button type="submit" class="btn btn-primary">保存路径</button>
      </div>
    </form>
  </section>

  <section class="card">
    <div class="card-h"><h2>环境自检</h2></div>
    <table class="kv">
      <?php foreach ($check as $k => $v) { ?>
        <tr>
          <th><?php echo e($k); ?></th>
          <td><?php echo $v[1] ? '<span class="ok">✓</span> ' : '<span class="bad">✗</span> '; ?><?php echo e($v[0]); ?></td>
        </tr>
      <?php } ?>
    </table>
    <form method="post" action="<?php echo e(u('pages/settings.php')); ?>" class="inline" style="margin-top:10px">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="action" value="cleanup_sessions">
      <button type="submit" class="btn btn-sm">清理过期会话 / 旧登录记录</button>
    </form>
  </section>
</div>

<?php
$baBase   = ba_admin_base();
$baKey    = (string)setting_get('ba_admin_key', defined('BA_ADMIN_KEY') ? BA_ADMIN_KEY : '');
$showKey  = secret_once_take('ba_admin_key');   /* 点「显示一次」后仅本次请求可见 */
$baAccDb  = (string)setting_get('ba_accounts_db', '');
$baHealth = ba_health();
$brStatus = player_bridge_status();
$keyMask  = '';
if ($baKey !== '') {
    /* 只显示固定掩码，不泄露任何字符（原来会露首尾各 4 位） */
    $keyMask = '••••••••';
}
?>
<section class="card">
  <div class="card-h"><h2>游戏服务端（玩家域）</h2>
    <div class="card-h-act">
      <form method="post" action="<?php echo e(u('pages/settings.php')); ?>" class="inline">
        <?php echo csrf_field(); ?>
        <input type="hidden" name="action" value="test_ba">
        <button type="submit" class="btn btn-sm btn-primary">测试连接</button>
      </form>
      <form method="post" action="<?php echo e(u('pages/settings.php')); ?>" class="inline">
        <?php echo csrf_field(); ?>
        <input type="hidden" name="action" value="flush_ba_cache">
        <button type="submit" class="btn btn-sm">清空静态缓存</button>
      </form>
    </div>
  </div>

  <table class="kv">
    <tr>
      <th>连通状态</th>
      <td>
        <?php if ($baHealth['ok']) { ?>
          <span class="ok">✓ 在线</span> · <?php echo e($baHealth['name']); ?>
          <?php if ($baHealth['version'] !== '') { ?> · 版本 <?php echo e($baHealth['version']); ?><?php } ?>
          · 账号 <?php echo (int)$baHealth['accounts']; ?> 个
          · 响应 <?php echo (int)$baHealth['ms']; ?> ms
          · 运行 <?php echo floor($baHealth['uptime'] / 60); ?> 分钟
        <?php } else { ?>
          <span class="bad">✗ <?php echo e($baHealth['error']); ?></span>
        <?php } ?>
      </td>
    </tr>
    <tr><th>Admin Key</th><td><?php echo $keyMask !== '' ? '<code>' . e($keyMask) . '</code>（已配置）' : '<span class="warn">未配置</span>'; ?>
      <?php echo $baKey !== '' ? '<span class="muted small">— 会随每次请求以 X-Admin-Key 头发送</span>'
                               : '<span class="muted small">— 服务端配了 key 就必填，否则 403</span>'; ?>
      <?php if ($baKey !== '') { ?>
        <form method="post" action="<?php echo e(u('pages/settings.php')); ?>" class="inline" style="margin-left:6px">
          <?php echo csrf_field(); ?>
          <input type="hidden" name="action" value="reveal_key">
          <button type="submit" class="btn btn-sm">显示一次</button>
        </form>
      <?php } ?>
      <?php if ($showKey !== '') { ?>
        <div class="muted small" style="margin-top:6px;word-break:break-all">
          本次显示：<code><?php echo e($showKey); ?></code>（刷新或离开本页后消失）
        </div>
      <?php } ?></td></tr>
    <tr><th>桥接账号库</th><td>
      <?php if ($brStatus['has_pdo_sqlite'] && $brStatus['readable']) { ?>
        <span class="ok">✓ 可读</span> · <?php echo (int)$brStatus['rows']; ?> 个账号镜像
        <br><code class="small"><?php echo e($brStatus['path']); ?></code>
      <?php } else { ?>
        <span class="warn">✗ <?php echo e($brStatus['error']); ?></span>
        <br><code class="small"><?php echo e($brStatus['path']); ?></code>
      <?php } ?>
    </td></tr>
    <tr><th>PHP 扩展</th><td>
      <span class="<?php echo $brStatus['has_pdo_sqlite'] ? 'ok' : 'bad'; ?>">pdo_sqlite</span> ·
      <span class="<?php echo extension_loaded('curl') ? 'ok' : 'bad'; ?>">curl</span> ·
      <span class="<?php echo extension_loaded('json') ? 'ok' : 'bad'; ?>">json</span>
    </td></tr>
    <?php $denyIds = ba_denied_character_ids(); ?>
    <tr><th>角色排除名单</th><td>
      <b><?php echo count($denyIds); ?></b> 个角色（客户端无法解析，服务端已剔除、面板会拒绝发放）
      <div class="muted small" style="margin-top:2px"><?php echo e(implode('、', $denyIds)); ?></div>
      <div class="muted small">客户端更新后可在此覆盖：
        <code><?php echo e((defined('APP_STATE_DIR') ? APP_STATE_DIR : '') . '/character_denylist.txt'); ?></code>
        一行一个 id，<code>#</code> 开头为注释。服务端侧同名覆盖文件是
        <code>Resources/ClientUnsupportedCharacters.txt</code>。
      </div>
    </td></tr>
    <tr><th>缓存目录</th><td><code class="small"><?php echo e(ba_cache_dir()); ?></code>
      <?php echo is_writable(ba_cache_dir()) ? '<span class="ok">可写</span>' : '<span class="warn">不可写（静态数据每次都要回源）</span>'; ?></td></tr>
  </table>

  <form method="post" action="<?php echo e(u('pages/settings.php')); ?>" style="margin-top:12px">
    <?php echo csrf_field(); ?>
    <input type="hidden" name="action" value="save_ba">
    <div class="field-row">
      <div class="field"><label>服务端地址</label>
        <input type="text" name="ba_admin_base" value="<?php echo e($baBase); ?>" placeholder="http://127.0.0.1:5000">
        <span class="muted small">同机就填环回地址，不要填公网域名</span>
      </div>
      <div class="field"><label>Admin Key（X-Admin-Key）</label>
        <input type="password" name="ba_admin_key" value="" placeholder="<?php echo $baKey !== '' ? '已配置（••••••••），留空=不修改' : '未配置；与服务端 Config.json 的 AdminApiKey 一致'; ?>" autocomplete="new-password">
        <span class="muted small">不回显明文：留空=保持原值；如需更换请直接填入新值。</span>
        <label class="small" style="display:block;margin-top:4px"><input type="checkbox" name="clear_ba_key" value="1"> 清除已保存的 Key</label>
      </div>
    </div>
    <div class="field"><label>桥接账号库（只读）</label>
      <input type="text" name="ba_accounts_db" value="<?php echo e($baAccDb); ?>" placeholder="/www/wwwroot/bapatch/data/accounts.db">
      <span class="muted small">用来显示玩家的设备号与登录次数；留空用默认路径</span>
    </div>
    <button type="submit" class="btn btn-primary">保存连接设置</button>
  </form>

  <p class="muted small" style="margin-top:10px">
    玩家域的所有写操作都通过服务端自带的 <code>/api/admin/*</code> 下发（走它自己的 EF Core），
    面板<b>从不直接写</b> <code>shittim.sqlite3</code>。
  </p>
</section>

<?php page_footer(); ?>
