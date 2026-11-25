<?php
/**
 * pages/admins.php — 管理员管理（改密码 / 增删 / 启用禁用）
 *
 * 说明：这里没有角色体系，任何管理员都能管理其他管理员。
 * 想更安全就只留一个管理员账号，并改掉默认用户名。
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';

require_login();
$me = current_admin();

if (isset($_SERVER['REQUEST_METHOD']) && strtoupper((string)$_SERVER['REQUEST_METHOD']) === 'POST') {
    require_post_csrf();
    $act = post_q('action');
    $msg = '';
    $ok  = true;

    try {
        if ($act === 'create') {
            $u   = trim(post_q('username'));
            $p1  = post_q('pass');
            $p2  = post_q('pass2');
            if (!preg_match('/^[A-Za-z0-9_\-]{3,32}$/', $u)) {
                $ok  = false;
                $msg = '用户名只能是 3-32 位字母/数字/下划线/减号';
            } elseif (strlen($p1) < 12) {
                $ok  = false;
                $msg = '密码至少 12 位';
            } elseif ($p1 !== $p2) {
                $ok  = false;
                $msg = '两次输入的密码不一致';
            } else {
                $dup = (int)db_val('SELECT COUNT(*) FROM admins WHERE username = ?', array($u), 0);
                if ($dup > 0) {
                    $ok  = false;
                    $msg = '用户名已存在';
                } else {
                    $salt = new_salt();
                    db_run(
                        'INSERT INTO admins (username, pass_hash, salt, created_at, enabled) VALUES (?, ?, ?, NOW(), 1)',
                        array($u, make_pass_hash($p1, $salt), $salt)
                    );
                    audit_log('admin.create', '管理员 ' . $u, '新建管理员');
                    $msg = '已创建管理员 ' . $u;
                }
            }
        } elseif ($act === 'reset_pass') {
            $id = post_int('id', 0, 1);
            $p1 = post_q('pass');
            $p2 = post_q('pass2');
            $row = $id > 0 ? db_row('SELECT * FROM admins WHERE id = ?', array($id)) : null;
            if (!$row) {
                $ok  = false;
                $msg = '管理员不存在';
            } elseif (strlen($p1) < 12) {
                $ok  = false;
                $msg = '密码至少 12 位';
            } elseif ($p1 !== $p2) {
                $ok  = false;
                $msg = '两次输入的密码不一致';
            } else {
                $salt = new_salt();
                db_run('UPDATE admins SET pass_hash = ?, salt = ? WHERE id = ?',
                    array(make_pass_hash($p1, $salt), $salt, $id));
                /* 让该管理员的所有其他会话失效（自己改自己的除外） */
                if ($id !== (int)$me['id']) {
                    db_run('DELETE FROM sessions WHERE admin_id = ?', array($id));
                }
                audit_log('admin.reset_pass', '管理员 ' . $row['username'], '重置密码');
                $msg = '已重置 ' . $row['username'] . ' 的密码';
            }
        } elseif ($act === 'toggle') {
            $id  = post_int('id', 0, 1);
            $row = $id > 0 ? db_row('SELECT * FROM admins WHERE id = ?', array($id)) : null;
            if (!$row) {
                $ok  = false;
                $msg = '管理员不存在';
            } elseif ($id === (int)$me['id']) {
                $ok  = false;
                $msg = '不能禁用自己的账号';
            } else {
                $new = ((int)$row['enabled'] === 1) ? 0 : 1;
                if ($new === 0) {
                    $enabled_cnt = (int)db_val('SELECT COUNT(*) FROM admins WHERE enabled = 1', array(), 0);
                    if ($enabled_cnt <= 1) {
                        $ok  = false;
                        $msg = '至少要保留一个启用状态的管理员';
                    }
                }
                if ($ok) {
                    db_run('UPDATE admins SET enabled = ? WHERE id = ?', array($new, $id));
                    if ($new === 0) {
                        db_run('DELETE FROM sessions WHERE admin_id = ?', array($id));
                    }
                    audit_log('admin.toggle', '管理员 ' . $row['username'], $new ? '启用' : '禁用');
                    $msg = ($new ? '已启用 ' : '已禁用 ') . $row['username'];
                }
            }
        } elseif ($act === 'delete') {
            $id  = post_int('id', 0, 1);
            $row = $id > 0 ? db_row('SELECT * FROM admins WHERE id = ?', array($id)) : null;
            if (!$row) {
                $ok  = false;
                $msg = '管理员不存在';
            } elseif ($id === (int)$me['id']) {
                $ok  = false;
                $msg = '不能删除自己的账号';
            } else {
                $cnt = (int)db_val('SELECT COUNT(*) FROM admins', array(), 0);
                if ($cnt <= 1) {
                    $ok  = false;
                    $msg = '至少要保留一个管理员';
                } else {
                    db_run('DELETE FROM sessions WHERE admin_id = ?', array($id));
                    db_run('DELETE FROM admins WHERE id = ?', array($id));
                    audit_log('admin.delete', '管理员 ' . $row['username'], '删除管理员');
                    $msg = '已删除管理员 ' . $row['username'];
                }
            }
        } elseif ($act === 'my_pass') {
            $old  = post_q('old_pass');
            $p1   = post_q('pass');
            $p2   = post_q('pass2');
            $row  = db_row('SELECT * FROM admins WHERE id = ?', array((int)$me['id']));
            if (!$row) {
                $ok  = false;
                $msg = '读不到当前账号';
            } elseif (!check_pass($old, (string)$row['pass_hash'], (string)$row['salt'])) {
                $ok  = false;
                $msg = '当前密码不正确';
            } elseif (strlen($p1) < 12) {
                $ok  = false;
                $msg = '新密码至少 12 位';
            } elseif ($p1 !== $p2) {
                $ok  = false;
                $msg = '两次输入的新密码不一致';
            } else {
                $salt = new_salt();
                db_run('UPDATE admins SET pass_hash = ?, salt = ? WHERE id = ?',
                    array(make_pass_hash($p1, $salt), $salt, (int)$me['id']));
                audit_log('admin.my_pass', '管理员 ' . $me['username'], '修改自己的密码');
                $msg = '密码已修改';
            }
        } else {
            $ok  = false;
            $msg = '未知操作';
        }
    } catch (Throwable $e) {
        $ok  = false;
        $msg = '操作失败：' . $e->getMessage();
    }

    flash_set($msg, $ok ? 'ok' : 'err');
    redirect_self();
}

$admins = db_all('SELECT * FROM admins ORDER BY id ASC');

page_header('管理员', 'admins');
?>

<div class="cols">
  <section class="card">
    <div class="card-h"><h2>管理员列表</h2></div>
    <div class="table-wrap">
    <table class="tbl">
      <thead><tr><th>ID</th><th>用户名</th><th>状态</th><th>创建</th><th>最后登录</th><th>操作</th></tr></thead>
      <tbody>
      <?php foreach ($admins as $a) {
          $aid = (int)$a['id'];
          $is_me = $aid === (int)$me['id'];
          ?>
        <tr>
          <td><?php echo $aid; ?></td>
          <td><b><?php echo e((string)$a['username']); ?></b><?php echo $is_me ? ' <span class="tag tag-info">我</span>' : ''; ?></td>
          <td><?php echo (int)$a['enabled'] === 1 ? '<span class="tag tag-ok">启用</span>' : '<span class="tag tag-err">禁用</span>'; ?></td>
          <td class="muted small nowrap"><?php echo e(fmt_dt($a['created_at'])); ?></td>
          <td class="muted small nowrap"><?php echo e(fmt_dt($a['last_login_at'])); ?>
            <?php if ((string)$a['last_login_ip'] !== '' && $a['last_login_ip'] !== null) { ?>
              <div><?php echo e((string)$a['last_login_ip']); ?></div>
            <?php } ?></td>
          <td class="nowrap">
            <button type="button" class="btn btn-xs" data-toggle="pw-<?php echo $aid; ?>">改密码</button>
            <?php if (!$is_me) { ?>
              <form method="post" action="<?php echo e(u('pages/admins.php')); ?>" class="inline"
                    onsubmit="return confirm('确认切换该管理员启用状态？');">
                <?php echo csrf_field(); ?>
                <input type="hidden" name="action" value="toggle">
                <input type="hidden" name="id" value="<?php echo $aid; ?>">
                <button type="submit" class="btn btn-xs"><?php echo (int)$a['enabled'] === 1 ? '禁用' : '启用'; ?></button>
              </form>
              <form method="post" action="<?php echo e(u('pages/admins.php')); ?>" class="inline"
                    onsubmit="return confirm('确认删除该管理员？');">
                <?php echo csrf_field(); ?>
                <input type="hidden" name="action" value="delete">
                <input type="hidden" name="id" value="<?php echo $aid; ?>">
                <button type="submit" class="btn btn-xs btn-danger">删除</button>
              </form>
            <?php } ?>
          </td>
        </tr>
        <tr class="row-sub" id="pw-<?php echo $aid; ?>" style="display:none">
          <td colspan="6">
            <form method="post" action="<?php echo e(u('pages/admins.php')); ?>" class="form-inline">
              <?php echo csrf_field(); ?>
              <input type="hidden" name="action" value="reset_pass">
              <input type="hidden" name="id" value="<?php echo $aid; ?>">
              <input type="password" name="pass" placeholder="新密码（≥12 位）" minlength="12" required autocomplete="new-password">
              <input type="password" name="pass2" placeholder="确认新密码" minlength="12" required autocomplete="new-password">
              <button type="submit" class="btn btn-sm btn-primary">重置</button>
            </form>
          </td>
        </tr>
      <?php } ?>
      </tbody>
    </table>
    </div>
    <p class="muted small">没有权限分级：任何管理员都能管理其他管理员。建议只保留一个账号，
      并把用户名从 <code>admin</code> 改掉。</p>
  </section>

  <section class="card">
    <div class="card-h"><h2>新增管理员</h2></div>
    <form method="post" action="<?php echo e(u('pages/admins.php')); ?>" class="form-grid">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="action" value="create">
      <label class="fld"><span>用户名</span>
        <input type="text" name="username" value="" maxlength="32" pattern="[A-Za-z0-9_\-]{3,32}" required>
      </label>
      <label class="fld"><span>密码（≥12 位）</span>
        <input type="password" name="pass" value="" minlength="12" required autocomplete="new-password">
      </label>
      <label class="fld"><span>确认密码</span>
        <input type="password" name="pass2" value="" minlength="12" required autocomplete="new-password">
      </label>
      <div class="fld fld-wide fld-actions">
        <button type="submit" class="btn btn-primary">创建</button>
      </div>
    </form>

    <div class="card-h" style="margin-top:18px"><h2>修改我的密码</h2></div>
    <form method="post" action="<?php echo e(u('pages/admins.php')); ?>" class="form-grid">
      <?php echo csrf_field(); ?>
      <input type="hidden" name="action" value="my_pass">
      <label class="fld"><span>当前密码</span>
        <input type="password" name="old_pass" value="" required autocomplete="current-password">
      </label>
      <label class="fld"><span>新密码（≥12 位）</span>
        <input type="password" name="pass" value="" minlength="12" required autocomplete="new-password">
      </label>
      <label class="fld"><span>确认新密码</span>
        <input type="password" name="pass2" value="" minlength="12" required autocomplete="new-password">
      </label>
      <div class="fld fld-wide fld-actions">
        <button type="submit" class="btn btn-primary">修改密码</button>
        <span class="muted small">改完不会踢掉当前会话</span>
      </div>
    </form>
  </section>
</div>

<?php page_footer(); ?>
