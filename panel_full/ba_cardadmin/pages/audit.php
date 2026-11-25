<?php
/**
 * pages/audit.php — 审计日志（所有写操作都记一条）
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';

require_login();

$q       = trim(get_q('q'));
$action  = trim(get_q('action_q'));
$admin   = trim(get_q('admin'));
$per     = get_int('per', 50);
if (!in_array($per, array(50, 100, 200), true)) {
    $per = 50;
}
$page    = get_int('page', 1, 1);

$where  = array('1=1');
$params = array();
if ($q !== '') {
    $where[]  = '(target LIKE ? OR detail LIKE ?)';
    $params[] = '%' . like_escape($q) . '%';
    $params[] = '%' . like_escape($q) . '%';
}
if ($action !== '') {
    $where[]  = 'action LIKE ?';
    $params[] = '%' . like_escape($action) . '%';
}
if ($admin !== '') {
    $where[]  = 'admin_name LIKE ?';
    $params[] = '%' . like_escape($admin) . '%';
}
$wsql  = implode(' AND ', $where);
$total = (int)db_val('SELECT COUNT(*) FROM audit_logs WHERE ' . $wsql, $params, 0);
$pages = max(1, (int)ceil($total / $per));
if ($page > $pages) {
    $page = $pages;
}
$offset = ($page - 1) * $per;

$rows = array();
if ($total > 0) {
    $rows = db_all(
        'SELECT * FROM audit_logs WHERE ' . $wsql . ' ORDER BY ts DESC, id DESC'
        . ' LIMIT ' . (int)$per . ' OFFSET ' . (int)$offset,
        $params
    );
}

/* 动作中文名 */
function audit_action_cn($a)
{
    $map = array(
        'login'             => '登录',
        'logout'            => '退出',
        'card.create'       => '新建卡密',
        'card.batch_create' => '批量生成',
        'card.import'       => '批量导入',
        'card.edit'         => '编辑卡密',
        'card.delete'       => '删除卡密',
        'card.unbind'       => '解绑设备',
        'card.enable'       => '启用卡密',
        'card.disable'      => '禁用卡密',
        'card.never'        => '设为永不过期',
        'card.reveal'       => '查看明文',
        'card.export'       => '导出卡密',
        'card.bulk_delete'  => '批量删除',
        'card.bulk_extend'  => '批量延期',
        'card.bulk_never'   => '批量永不过期',
        'card.bulk_unbind'  => '批量解绑',
        'card.bulk_enable'  => '批量启用',
        'card.bulk_disable' => '批量禁用',
        'sync.manual'       => '手动同步',
        'sync.import_json'  => '从 json 导入',
        'admin.create'      => '新增管理员',
        'admin.reset_pass'  => '重置密码',
        'admin.toggle'      => '启停管理员',
        'admin.delete'      => '删除管理员',
        'admin.my_pass'     => '改自己密码',
        'log.parse'         => '解析日志',
        'log.clear'         => '清理日志',
        'settings.save'     => '改设置',
    );
    return isset($map[$a]) ? $map[$a] : $a;
}

page_header('审计日志', 'audit');
?>

<div class="toolbar">
  <form method="get" action="<?php echo e(u('pages/audit.php')); ?>" class="filters">
    <input type="text" name="q" value="<?php echo e($q); ?>" placeholder="对象/细节关键词" maxlength="64">
    <input type="text" name="action_q" value="<?php echo e($action); ?>" placeholder="动作，如 card." maxlength="32">
    <input type="text" name="admin" value="<?php echo e($admin); ?>" placeholder="管理员名" maxlength="32">
    <select name="per">
      <?php foreach (array(50, 100, 200) as $pv) { ?>
        <option value="<?php echo $pv; ?>"<?php echo $per === $pv ? ' selected' : ''; ?>>每页 <?php echo $pv; ?></option>
      <?php } ?>
    </select>
    <button type="submit" class="btn btn-sm">筛选</button>
    <a class="btn btn-sm" href="<?php echo e(u('pages/audit.php')); ?>">重置</a>
  </form>
</div>

<p class="muted small">共 <?php echo number_format($total); ?> 条 · 只追加不修改 · 谁、什么时候、做了什么、影响多少条</p>

<?php echo pagination($page, $per, $total, array(), 'pages/audit.php'); ?>

<div class="table-wrap">
<table class="tbl">
  <thead><tr><th class="nowrap">时间</th><th>管理员</th><th>动作</th><th>对象</th><th>细节</th><th>IP</th></tr></thead>
  <tbody>
  <?php if (!$rows) { ?>
    <tr><td colspan="6" class="empty">没有审计记录</td></tr>
  <?php } ?>
  <?php foreach ($rows as $r) { ?>
    <tr>
      <td class="nowrap"><?php echo e(fmt_ts((int)$r['ts'])); ?></td>
      <td><b><?php echo e((string)$r['admin_name']); ?></b></td>
      <td><span class="tag tag-info" title="<?php echo e((string)$r['action']); ?>"><?php echo e(audit_action_cn((string)$r['action'])); ?></span></td>
      <td><?php echo e(str_limit((string)$r['target'], 60)); ?></td>
      <td class="muted small"><?php echo e(str_limit((string)$r['detail'], 120)); ?></td>
      <td class="muted small"><?php echo e((string)$r['ip']); ?></td>
    </tr>
  <?php } ?>
  </tbody>
</table>
</div>

<?php echo pagination($page, $per, $total, array(), 'pages/audit.php'); ?>

<?php page_footer(); ?>
