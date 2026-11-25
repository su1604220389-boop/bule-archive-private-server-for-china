<?php
/**
 * pages/gacha_rates.php — 抽卡概率设置（P0）
 *
 * 读 / 写都走 Shittim 的 /api/admin/gacha/rates*（X-Admin-Key 由 inc/ba.php 统一带上），
 * 本页不读也不写服务端的 gacha_rates.json / gacha_config.json，不重启任何服务。
 *
 * 写操作遵循面板惯例：
 *   POST → require_post_csrf() → 校验 → 调 API → audit_log() → flash_set() → 302 回本页（PRG）
 * 「恢复全部默认」额外要求服务端一次性令牌（action_token_*），并在审计里记明二次确认。
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/gacha.php';

require_login();

$groups   = gacha_rate_groups();
$self     = 'pages/gacha_rates.php';
$self_url = u($self);

/* ------------------------------------------------------------------ 写 --- */

if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $act = post_q('action');

    try {
        /* --- 保存（整份提交） --- */
        if ($act === 'save') {
            $err   = '';
            $rates = gacha_rates_validate(isset($_POST['rates']) ? $_POST['rates'] : null, $err);
            if ($rates === null) {
                flash_set('保存失败：' . $err, 'err');
                redirect_self();
            }

            /* 先读一次当前值：服务端 200 契约里没有 changed 时，用它算「旧值→新值」写进审计 */
            $before = gacha_rates_fetch();

            $r = gacha_rates_save($rates);
            if (!$r['ok']) {
                $msg = '保存失败：' . $r['error'];
                if ($r['status'] > 0) {
                    $msg .= '（HTTP ' . (int)$r['status'] . '）';
                }
                $raw = trim($r['raw_text']);
                if ($raw !== '') {
                    $msg .= '；服务端响应：' . substr($raw, 0, 300);
                }
                audit_log('gacha.rates.save', '抽卡概率',
                    '失败：' . $r['error'] . '；提交值=' . gacha_rates_describe($rates));
                flash_set($msg, 'err');
                redirect_self();
            }

            $changes = gacha_changes_cn($r['changed']);
            if (!$changes && $before['ok']) {
                /* 服务端没给 changed（或本次没有变化）：自己对比保存前后的生效值 */
                $changes = gacha_rates_diff($before['rates'], $r['rates']);
            }
            if ($changes) {
                $detail = '变更：' . implode('；', $changes);
            } elseif ($before['ok'] || $r['changed']) {
                $detail = '提交值与当前生效值一致，无变更';
            } else {
                $detail = '变更列表不可用（保存前读取失败：' . substr((string)$before['error'], 0, 120)
                        . '）；提交值=' . gacha_rates_describe($rates);
            }
            $detail .= '；备份=' . ($r['backupFile'] !== '' ? gacha_basename($r['backupFile']) : '无')
                     . '；isDefault=' . ($r['isDefault'] ? '1' : '0');
            audit_log('gacha.rates.save', '抽卡概率', $detail);

            if ($changes) {
                $suffix = '（' . count($changes) . ' 项变更）';
            } elseif ($before['ok'] || $r['changed']) {
                $suffix = '（无变更）';
            } else {
                $suffix = '（变更列表不可用）';
            }
            flash_set('已保存，立即生效' . $suffix, 'ok');
            redirect_self();
        }

        /* --- 恢复单个分组 --- */
        if ($act === 'reset_group') {
            $scope = post_q('scope');
            if (!isset($groups[$scope])) {
                flash_set('未知的分类：' . substr((string)$scope, 0, 32), 'err');
                redirect_self();
            }
            $glabel = $groups[$scope]['label'];

            $before = gacha_rates_fetch();
            $r      = gacha_rates_reset($scope);
            if (!$r['ok']) {
                $msg = '恢复「' . $glabel . '」默认值失败：' . $r['error'];
                if ($r['status'] > 0) {
                    $msg .= '（HTTP ' . (int)$r['status'] . '）';
                }
                audit_log('gacha.rates.reset', '抽卡概率 · ' . $glabel, '失败：' . $r['error']);
                flash_set($msg, 'err');
                redirect_self();
            }

            $diff = $before['ok'] ? gacha_rates_diff($before['rates'], $r['rates']) : array();
            if ($diff) {
                $detail = '旧值→新值：' . implode('；', $diff);
            } elseif ($before['ok']) {
                $detail = '重置前后一致（本来已是默认值）';
            } else {
                $detail = '旧值读取失败（' . substr((string)$before['error'], 0, 120) . '），仅记录新值：'
                        . gacha_rates_describe($r['rates'], $scope);
            }
            $detail .= '；备份=' . ($r['backupFile'] !== '' ? gacha_basename($r['backupFile']) : '无');
            audit_log('gacha.rates.reset', '抽卡概率 · ' . $glabel . ' 恢复默认', $detail);

            flash_set('已把「' . $glabel . '」恢复为默认值，立即生效', 'ok');
            redirect_self();
        }

        /* --- 恢复全部（二次确认 + 服务端一次性令牌） --- */
        if ($act === 'reset_all') {
            action_token_check('gacha-reset-all');
            if (post_q('confirm_all') !== '1') {
                flash_set('恢复全部默认需要二次确认（页面上的确认框）', 'err');
                redirect_self();
            }

            $before = gacha_rates_fetch();
            $r      = gacha_rates_reset('all');
            if (!$r['ok']) {
                $msg = '恢复全部默认失败：' . $r['error'];
                if ($r['status'] > 0) {
                    $msg .= '（HTTP ' . (int)$r['status'] . '）';
                }
                audit_log('gacha.rates.reset_all', '抽卡概率 · 全部分类恢复默认', '失败：' . $r['error']);
                flash_set($msg, 'err');
                redirect_self();
            }

            $diff = $before['ok'] ? gacha_rates_diff($before['rates'], $r['rates']) : array();
            if ($diff) {
                $detail = '旧值→新值：' . implode('；', $diff);
            } elseif ($before['ok']) {
                $detail = '重置前后一致（本来全是默认值）';
            } else {
                $detail = '旧值读取失败（' . substr((string)$before['error'], 0, 120) . '），新值=' 
                        . gacha_rates_describe($r['rates']);
            }
            $detail = '二次确认=前端 confirm + 服务端一次性令牌；' . $detail
                    . '；备份=' . ($r['backupFile'] !== '' ? gacha_basename($r['backupFile']) : '无');
            audit_log('gacha.rates.reset_all', '抽卡概率 · 全部分类恢复默认', $detail);

            flash_set('已恢复全部默认值，立即生效', 'ok');
            redirect_self();
        }

        flash_set('未知操作', 'err');
    } catch (Throwable $e) {
        flash_set('操作失败：' . $e->getMessage(), 'err');
    }
    redirect_self();
}

/* ------------------------------------------------------------------ 读 --- */

$view   = gacha_rates_fetch();
$api_ok = $view['ok'];
$cur    = $view['rates'];
$dft    = $view['defaults'];

page_header('抽卡概率设置', 'gacha');

/* 旧 gacha_config.json 接管时，必须最先看到，所以放在最顶部 */
if ($api_ok && $view['legacyOverrideActive']) {
    echo '<div class="alert alert-err"><b>警告：旧的 gacha_config.json 正在接管抽卡概率，本页改动不会生效。</b><br>';
    echo '服务端检测到 <code>' . e($view['legacyOverridePath'] !== '' ? $view['legacyOverridePath'] : 'gacha_config.json')
       . '</code> 里的 <code>custom_rates</code> 非空，抽卡会先走这个旧分支，'
       . '<code>/api/admin/gacha/rates</code> 写入的数值会被绕过。<br>';
    echo '处理办法：让运维确认后清掉该文件的 <code>custom_rates</code>（或删除 / 改名 <code>gacha_config.json</code>），'
       . '再刷新本页。本页不会去修改它。</div>';
}
?>

<section class="card">
  <div class="card-h">
    <h2>当前状态</h2>
    <div class="card-h-act">
      <?php if (!$api_ok) { ?>
        <span class="tag tag-err">读取失败</span>
      <?php } elseif ($view['isDefault']) { ?>
        <span class="tag tag-ok">默认值</span>
      <?php } else { ?>
        <span class="tag tag-warn">已自定义</span>
      <?php } ?>
      <?php if ($api_ok && $view['legacyOverrideActive']) { ?>
        <span class="tag tag-err">旧 gacha_config.json 生效中</span>
      <?php } ?>
      <span class="muted small">读取 <?php echo (int)$view['ms']; ?> ms</span>
    </div>
  </div>

  <?php if (!$api_ok) { ?>
    <p class="bad">当前状态未知：读取 API 失败（<?php echo e($view['error']); ?>）。详见下方「读取当前概率失败」。</p>
  <?php } else { ?>
    <table class="kv">
      <tr><th>当前状态</th><td>
        <?php if ($view['isDefault']) { ?>
          <b>默认值</b>
          <span class="muted small">— 当前生效值与服务端 defaults 完全一致</span>
        <?php } else { ?>
          <b>已自定义</b>
          <span class="muted small">— 当前生效值被覆盖，保存 / 恢复后立即生效</span>
        <?php } ?>
      </td></tr>
      <tr><th>最后修改时间</th><td>
        <?php if ($view['updatedAt'] === '') { ?>
          <span class="muted">—（服务端没有记录）</span>
        <?php } else { ?>
          <?php echo e(gacha_time_local($view['updatedAt'])); ?>
          <span class="muted small">（UTC 原值 <code><?php echo e($view['updatedAt']); ?></code>）</span>
        <?php } ?>
      </td></tr>
      <tr><th>版本 / 配置文件</th><td>
        v<?php echo (int)$view['version']; ?>
        <?php if ($view['filePath'] !== '') { ?>
          · <code class="small"><?php echo e($view['filePath']); ?></code>
        <?php } ?>
        <?php if ($view['overrideFileExists'] === null) { ?>
          <span class="muted small"> · 覆盖文件状态未知</span>
        <?php } elseif (!$view['overrideFileExists']) { ?>
          <span class="muted small"> · 无覆盖文件（全部使用默认值）</span>
        <?php } elseif ($view['overrideFileValid'] === false) { ?>
          <span class="warn"> · 覆盖文件存在但校验失败</span>
        <?php } else { ?>
          <span class="ok"> · 覆盖文件已生效</span>
        <?php } ?>
      </td></tr>
      <tr><th>旧 gacha_config.json</th><td>
        <?php if ($view['legacyOverrideActive']) { ?>
          <span class="bad"><b>正在接管</b></span>
          <?php if ($view['legacyOverridePath'] !== '') { ?>
            <code class="small"><?php echo e($view['legacyOverridePath']); ?></code>
          <?php } ?>
          <span class="muted small">— 本页写入不会生效，见页面顶部警告</span>
        <?php } else { ?>
          <span class="ok">未检测到</span>
          <span class="muted small">— 抽卡走本页这套 gacha_rates 配置</span>
        <?php } ?>
      </td></tr>
    </table>

    <?php if ($view['warnings']) { ?>
      <div class="alert alert-warn" style="margin-top:10px">
        <b>服务端提示：</b><br>
        <?php foreach ($view['warnings'] as $w) { ?>
          <?php echo e($w); ?><br>
        <?php } ?>
      </div>
    <?php } ?>
    <?php if ($view['lastError'] !== '') { ?>
      <div class="alert alert-err" style="margin-top:10px">
        <b>服务端上次读取配置时的错误：</b><?php echo e($view['lastError']); ?>
        <div class="small">出现这个错误时服务端会回落到默认值；如果数值看起来不对，先处理它。</div>
      </div>
    <?php } ?>
  <?php } ?>
</section>

<?php if (!$api_ok) { ?>
<section class="card">
  <div class="card-h"><h2>读取当前概率失败</h2></div>
  <div class="srv-down">
    读取不到抽卡概率：<b><?php echo e($view['error']); ?></b><br>
    请求：<code><?php echo e($view['url'] !== '' ? $view['url'] : '/api/admin/gacha/rates'); ?></code>
    · HTTP <?php echo (int)$view['status']; ?>
    · <?php echo (int)$view['ms']; ?> ms
  </div>
  <p class="muted small">
    本页只通过 <code>/api/admin/gacha/rates</code> 读写，读不到就不会显示当前值，也不会允许保存 / 恢复。
    请检查服务端是否在线、系统设置里的服务端地址与 <code>X-Admin-Key</code> 是否与 Config.json 的 <code>AdminApiKey</code> 一致。
  </p>
  <p><a class="btn btn-sm" href="<?php echo e($self_url); ?>">重新读取</a></p>
  <details style="margin-top:6px">
    <summary class="muted small">原始响应体（点击展开）</summary>
    <pre class="code"><?php echo e($view['raw_text'] !== '' ? $view['raw_text'] : '(空响应体)'); ?></pre>
  </details>
</section>
<?php } ?>

<section class="card">
  <div class="card-h"><h2>数值怎么读（务必先看）</h2></div>
  <p>这里的「总出彩阈值」是<b>阈值</b>，不是相加后的概率。当前判定逻辑是：随机数（0–999）小于 <code>upSsrRate</code> 出 UP 3★；否则小于 <code>ssrThreshold</code> 出其它 3★。</p>
  <p>所以 <b>UP 实际出率 = upSsrRate/10 %</b>，<b>其它 3★ 实际出率 = (ssrThreshold − upSsrRate)/10 %</b>，<b>总出率 = ssrThreshold/10 %</b>。</p>
  <p>例：<code>upSsrRate=7, ssrThreshold=23</code> → UP 0.7% + 其它 1.6% = <b>总 2.3%</b>。</p>
  <p class="muted small">
    补充：Fes 池在 UP 段之后还有一段 <code>fesSsrRate</code>（默认 7 / 9 / 44 → UP 0.7% + Fes 专属 0.2% + 其它 3.5% = 总 4.4%）；
    2★ 的 <code>srRate</code> 同样是绝对阈值，区间是 [ssrThreshold, srRate)，所以 185 并不代表“2★ 占 18.5%”。
    表里的「换算」只是 ‰ ÷ 10 的单位换算，实际占比看右侧「实际出率（只读）」列。
  </p>
</section>

<?php if ($api_ok) { ?>
<section class="card">
  <div class="card-h">
    <h2>各分类阈值（单位 ‰，0–1000）</h2>
    <div class="card-h-act">
      <span class="muted small">保存 = 整份提交四个分类；未改的字段按当前值提交</span>
    </div>
  </div>

  <div class="table-wrap">
  <table class="tbl">
    <thead>
      <tr>
        <th class="nowrap">分类</th>
        <th>总出彩阈值 <code>ssrThreshold</code>
          <div class="muted small">总 3★ 上限（含 UP / Fes 段）</div></th>
        <th>UP 出率 <code>upSsrRate</code>
          <div class="muted small">UP 3★ 上限</div></th>
        <th>Fes 专属 <code>fesSsrRate</code>
          <div class="muted small">仅 Fes 行可填</div></th>
        <th>2★ 率 <code>srRate</code>
          <div class="muted small">2★ 上限（绝对阈值）</div></th>
        <th class="nowrap">实际出率（只读）</th>
        <th class="nowrap">操作</th>
      </tr>
    </thead>
    <tbody>
    <?php
    foreach ($groups as $g => $def) {
        $row   = isset($cur[$g]) ? $cur[$g] : array();
        $drow  = isset($dft[$g]) ? $dft[$g] : array();
        $bands = gacha_band_summary($g, $row);

        $band_parts = array();
        if ($bands['up'] > 0) {
            $band_parts[] = 'UP ' . gacha_pct($bands['up']);
        }
        if ($bands['fes'] > 0) {
            $band_parts[] = 'Fes ' . gacha_pct($bands['fes']);
        }
        $band_parts[] = '其它 ' . gacha_pct($bands['other']);
        $band_3 = ($g === 'Normal')
            ? ('总 3★ ' . gacha_pct($bands['total']))
            : ('总 3★ ' . gacha_pct($bands['total']) . '（' . implode(' + ', $band_parts) . '）');
    ?>
      <tr data-gacha-row data-group="<?php echo e($g); ?>" data-label="<?php echo e($def['label']); ?>">
        <td class="nowrap">
          <b><?php echo e($def['label']); ?></b>
          <div class="muted small"><?php echo e($def['note']); ?></div>
          <div class="muted small"><code class="small"><?php echo e($g); ?></code></div>
        </td>
        <?php
        /* 五列固定顺序：ssrThreshold / upSsrRate / fesSsrRate / srRate；该分类没有的字段显示 — */
        foreach (array('ssrThreshold', 'upSsrRate', 'fesSsrRate', 'srRate') as $f) {
            echo '<td>';
            if (!in_array($f, $def['fields'], true)) {
                echo '<span class="muted">—</span>';
            } else {
                $val = isset($row[$f]) ? (int)$row[$f] : 0;
                $dv  = isset($drow[$f]) ? (int)$drow[$f] : 0;
                echo '<label class="fld">';
                echo '<input type="number" form="gacha-save-form"'
                   . ' name="rates[' . e($g) . '][' . e($f) . ']"'
                   . ' value="' . $val . '" min="0" max="1000" step="1" inputmode="numeric" required'
                   . ' data-field="' . e($f) . '" data-label="' . e(gacha_rate_field_label($f)) . '">';
                echo '<em>换算 <b class="pct" data-pct="' . e($f) . '">' . e(gacha_pct($val)) . '</b>'
                   . ' · 默认 ' . $dv . '（' . e(gacha_pct($dv)) . '）</em>';
                echo '</label>';
            }
            echo '</td>';
        }
        ?>
        <td>
          <div class="gacha-bands3"><?php echo e($band_3); ?></div>
          <div class="muted small gacha-bandsrest">2★ <?php echo e(gacha_pct($bands['sr'])); ?> · 1★ <?php echo e(gacha_pct($bands['r'])); ?></div>
        </td>
        <td class="nowrap">
          <form method="post" action="<?php echo e($self_url); ?>" class="inline"
                onsubmit="return confirm(<?php echo e(json_encode('把「' . $def['label'] . '」整组恢复为默认值？该组所有字段都会被重置，保存后立即生效。', JSON_UNESCAPED_UNICODE)); ?>);">
            <?php echo csrf_field(); ?>
            <input type="hidden" name="action" value="reset_group">
            <input type="hidden" name="scope" value="<?php echo e($g); ?>">
            <button type="submit" class="btn btn-sm">恢复本组默认</button>
          </form>
        </td>
      </tr>
    <?php } ?>
    </tbody>
  </table>
  </div>

  <form method="post" action="<?php echo e($self_url); ?>" id="gacha-save-form">
    <?php echo csrf_field(); ?>
    <input type="hidden" name="action" value="save">
    <div class="row-gap">
      <button type="submit" class="btn btn-primary">保存（整份提交）</button>
      <span class="muted small">保存成功后立即生效，无需重启服务端；服务端会先备份上一份配置。</span>
      <?php if ($view['legacyOverrideActive']) { ?>
        <span class="warn small">注意：旧 gacha_config.json 正在接管，保存会写入 gacha_rates.json，但清理旧文件前不会改变实际抽卡。</span>
      <?php } ?>
    </div>
  </form>
</section>

<section class="card">
  <div class="card-h"><h2>整体恢复</h2></div>
  <p class="muted small">
    「恢复全部默认」会把常驻 / Pickup / 限定 / Fes 四个分类的所有字段恢复为服务端出厂 defaults，
    并清掉覆盖文件里的自定义值；恢复后立即生效。
  </p>
  <form method="post" action="<?php echo e($self_url); ?>"
        onsubmit="return confirm(<?php echo e(json_encode('确定把四个分类全部恢复为出厂默认值吗？当前所有自定义值都会被覆盖。', JSON_UNESCAPED_UNICODE)); ?>);">
    <?php echo csrf_field(); ?>
    <?php echo action_token_field('gacha-reset-all'); ?>
    <input type="hidden" name="action" value="reset_all">
    <input type="hidden" name="confirm_all" value="1">
    <button type="submit" class="btn btn-warn">恢复全部默认</button>
    <span class="muted small">会二次确认（浏览器 confirm + 服务端一次性令牌），并写入审计日志。</span>
  </form>
</section>

<script>
(function () {
  var rows = Array.prototype.slice.call(document.querySelectorAll('tr[data-gacha-row]'));
  if (!rows.length) {
    return;
  }

  function pct(n) {
    var s = (Number(n) / 10).toFixed(1);
    if (s.slice(-2) === '.0') {
      s = s.slice(0, -2);
    }
    return s + '%';
  }

  function clamp(n) {
    n = parseInt(n, 10);
    if (!isFinite(n)) {
      return 0;
    }
    if (n < 0) {
      return 0;
    }
    if (n > 1000) {
      return 1000;
    }
    return n;
  }

  function inputOf(tr, field) {
    return tr.querySelector('input[data-field="' + field + '"]');
  }

  function val(tr, field) {
    var el = inputOf(tr, field);
    return el ? clamp(el.value) : 0;
  }

  function bands(group, tr) {
    var ssr = val(tr, 'ssrThreshold');
    var up = (group === 'Normal') ? 0 : val(tr, 'upSsrRate');
    var fes = (group === 'Fes') ? val(tr, 'fesSsrRate') : 0;
    var sr = val(tr, 'srRate');
    var out = { total: ssr, up: 0, fes: 0, other: 0, sr: 0, r: 0 };
    var cursor = 0;
    if (up > cursor) {
      out.up = Math.max(0, Math.min(up, ssr));
      cursor = out.up;
    }
    if (group === 'Fes' && fes > cursor) {
      out.fes = Math.max(0, Math.min(fes, ssr) - cursor);
      cursor += out.fes;
    }
    out.other = Math.max(0, ssr - cursor);
    out.sr = Math.max(0, sr - ssr);
    out.r = Math.max(0, 1000 - ssr - out.sr);
    return out;
  }

  function sync(tr) {
    var group = tr.getAttribute('data-group') || '';
    var b = bands(group, tr);
    var inputs = Array.prototype.slice.call(tr.querySelectorAll('input[data-field]'));
    var i;
    for (i = 0; i < inputs.length; i++) {
      var f = inputs[i].getAttribute('data-field');
      var span = tr.querySelector('.pct[data-pct="' + f + '"]');
      if (span) {
        span.textContent = pct(clamp(inputs[i].value));
      }
    }

    var b3 = tr.querySelector('.gacha-bands3');
    if (b3) {
      if (group === 'Normal') {
        b3.textContent = '总 3★ ' + pct(b.total);
      } else {
        var parts = [];
        if (b.up > 0) {
          parts.push('UP ' + pct(b.up));
        }
        if (b.fes > 0) {
          parts.push('Fes ' + pct(b.fes));
        }
        parts.push('其它 ' + pct(b.other));
        b3.textContent = '总 3★ ' + pct(b.total) + '（' + parts.join(' + ') + '）';
      }
    }
    var br = tr.querySelector('.gacha-bandsrest');
    if (br) {
      br.textContent = '2★ ' + pct(b.sr) + ' · 1★ ' + pct(b.r);
    }
  }

  rows.forEach(function (tr) {
    Array.prototype.slice.call(tr.querySelectorAll('input[data-field]')).forEach(function (input) {
      input.addEventListener('input', function () { sync(tr); });
      input.addEventListener('change', function () { sync(tr); });
    });
    sync(tr);
  });

  /* 前端先拦一遍阈值关系（服务端还会再校验一次，以服务端为准） */
  var saveForm = document.getElementById('gacha-save-form');
  if (saveForm) {
    saveForm.addEventListener('submit', function (ev) {
      var msg = '';
      rows.forEach(function (tr) {
        var group = tr.getAttribute('data-group') || '';
        var glabel = tr.getAttribute('data-label') || group;
        var ssr = val(tr, 'ssrThreshold');
        var checks = [];
        if (group !== 'Normal') {
          checks.push(['upSsrRate', 'UP 出率']);
        }
        if (group === 'Fes') {
          checks.push(['fesSsrRate', 'Fes 专属']);
        }
        checks.forEach(function (pair) {
          var el = inputOf(tr, pair[0]);
          var v = el ? clamp(el.value) : 0;
          if (v > ssr && msg === '') {
            msg = '「' + glabel + '」的总出彩阈值（' + ssr + '）必须 ≥ ' + pair[1] + '（' + v + '）';
          }
        });
      });
      if (msg !== '') {
        ev.preventDefault();
        alert(msg);
      }
    });
  }
})();
</script>
<?php } ?>

<?php page_footer(); ?>
