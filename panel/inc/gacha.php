<?php
/**
 * inc/gacha.php — 抽卡概率（gacha rates）admin API 封装
 *
 * 后端（Shittim / P0RATES v1）：
 *   GET  /api/admin/gacha/rates          读当前生效值 + 默认值 + 状态
 *   POST /api/admin/gacha/rates          {"rates":{"Pickup":{...}}}  整份/部分覆盖
 *   POST /api/admin/gacha/rates/reset    {"scope":"all"|"Normal"|"Pickup"|"Limited"|"Fes"}
 *
 * 复用 inc/ba.php 的 ba_get() / ba_post()（X-Admin-Key、超时、JSON 解码都在那一层），
 * 这里不自己发 curl；也绝不读写服务端的 gacha_rates*.json / gacha_config.json。
 *
 * 数值语义（与 GachaRateConfig / ShopManager 的判定顺序一致）：
 *   · 所有字段都是 0..1000 的**绝对阈值（‰）**，不是区间宽度，更不是相加后的概率；
 *   · 判定顺序：random(0..999) < upSsrRate → UP 3★；Fes 池再判 < fesSsrRate → Fes 3★；
 *     否则 < ssrThreshold → 其它 3★；否则 < srRate → 2★；否则 1★。
 *   · 所以 总 3★ = ssrThreshold/10 %，UP 3★ = upSsrRate/10 %，
 *     其它 3★ = (ssrThreshold − upSsrRate)/10 %（Fes 还要再减掉 fesSsrRate 那一段）。
 *
 * 约定：所有函数都不抛异常（除参数明显错误），失败返回 ok=false 的结构，调用方负责展示。
 */

if (!defined('CARDADMIN')) {
    http_response_code(403);
    exit('403 Forbidden');
}

require_once __DIR__ . '/ba.php';

/* ------------------------------------------------------------ 分类定义 --- */

/**
 * 四个分类及其可编辑字段（顺序 = 页面表格 = 服务端 GachaRateConfig.Groups）。
 * Normal 没有 UP / Fes 段；Fes 多一个 fesSsrRate。
 */
function gacha_rate_groups()
{
    static $defs = null;
    if ($defs !== null) {
        return $defs;
    }
    $defs = array(
        'Normal' => array(
            'label'  => '常驻',
            'note'   => '常驻池 · NormalGacha',
            'fields' => array('ssrThreshold', 'srRate'),
        ),
        'Pickup' => array(
            'label'  => 'Pickup',
            'note'   => 'UP 池 · PickupGacha 及未单列的分类',
            'fields' => array('upSsrRate', 'ssrThreshold', 'srRate'),
        ),
        'Limited' => array(
            'label'  => '限定',
            'note'   => '限定池 · LimitedGacha',
            'fields' => array('upSsrRate', 'ssrThreshold', 'srRate'),
        ),
        'Fes' => array(
            'label'  => 'Fes',
            'note'   => 'Fes 池 · FesGacha',
            'fields' => array('upSsrRate', 'fesSsrRate', 'ssrThreshold', 'srRate'),
        ),
    );
    return $defs;
}

/** 字段元信息（页面标题 / 审计文案共用） */
function gacha_rate_field_meta()
{
    static $m = null;
    if ($m !== null) {
        return $m;
    }
    $m = array(
        'upSsrRate'    => array('label' => 'UP 出率', 'hint' => 'UP 3★ 的上限'),
        'fesSsrRate'   => array('label' => 'Fes 专属', 'hint' => 'Fes 专属 3★ 的上限'),
        'ssrThreshold' => array('label' => '总出彩阈值', 'hint' => '总 3★ 上限（含 UP / Fes 段）'),
        'srRate'       => array('label' => '2★ 率', 'hint' => '2★ 上限（绝对阈值）'),
    );
    return $m;
}

function gacha_rate_field_label($f)
{
    $m = gacha_rate_field_meta();
    return isset($m[$f]) ? $m[$f]['label'] : (string)$f;
}

function gacha_rate_field_hint($f)
{
    $m = gacha_rate_field_meta();
    return isset($m[$f]) ? $m[$f]['hint'] : '';
}

function gacha_rate_group_label($g)
{
    $defs = gacha_rate_groups();
    return isset($defs[$g]) ? $defs[$g]['label'] : (string)$g;
}

/* ------------------------------------------------------------ 小工具 --- */

/** ‰（绝对阈值，0..1000）→ 人类可读百分比，如 23 => "2.3%"，30 => "3%" */
function gacha_pct($permille)
{
    $s = number_format(((int)$permille) / 10, 1, '.', '');
    if (substr($s, -2) === '.0') {
        $s = substr($s, 0, -2);
    }
    return $s . '%';
}

/** ISO8601（updatedAt，UTC）→ 本地时间字符串；解析不了就原样返回 */
function gacha_time_local($iso)
{
    $iso = trim((string)$iso);
    if ($iso === '') {
        return '';
    }
    $ts = strtotime($iso);
    if ($ts === false) {
        return $iso;
    }
    return date('Y-m-d H:i:s', $ts);
}

/** 路径取文件名（Linux / Windows 都能处理） */
function gacha_basename($path)
{
    $p = str_replace('\\', '/', (string)$path);
    $i = strrpos($p, '/');
    return $i === false ? $p : substr($p, $i + 1);
}

/** 把 API 返回的 rates/defaults 规范成 [分类][字段] => int 的完整结构；缺字段填 0 */
function gacha_rate_normalize($raw)
{
    $out = array();
    foreach (gacha_rate_groups() as $g => $def) {
        $src = (is_array($raw) && isset($raw[$g]) && is_array($raw[$g])) ? $raw[$g] : array();
        foreach ($def['fields'] as $f) {
            $out[$g][$f] = isset($src[$f]) ? (int)$src[$f] : 0;
        }
    }
    return $out;
}

/**
 * 把一份 rates 描述成紧凑文本（审计日志用），如
 *   Pickup{upSsrRate=7, ssrThreshold=23, srRate=185}
 */
function gacha_rates_describe($rates, $only_group = '')
{
    $chunks = array();
    foreach (gacha_rate_groups() as $g => $def) {
        if ($only_group !== '' && $g !== $only_group) {
            continue;
        }
        $row   = (isset($rates[$g]) && is_array($rates[$g])) ? $rates[$g] : array();
        $parts = array();
        foreach ($def['fields'] as $f) {
            $parts[] = $f . '=' . (isset($row[$f]) ? (int)$row[$f] : 0);
        }
        $chunks[] = $g . '{' . implode(', ', $parts) . '}';
    }
    return implode(' ', $chunks);
}

/**
 * 对比两份 rates，返回「中文分类 中文字段(字段名) 旧→新」的列表。
 * 用于审计日志里的「改了哪个分类哪个字段、旧值→新值」。
 */
function gacha_rates_diff($before, $after)
{
    $out = array();
    foreach (gacha_rate_groups() as $g => $def) {
        foreach ($def['fields'] as $f) {
            $a = (isset($before[$g]) && isset($before[$g][$f])) ? (int)$before[$g][$f] : null;
            $b = (isset($after[$g]) && isset($after[$g][$f])) ? (int)$after[$g][$f] : null;
            if ($a === $b) {
                continue;
            }
            $out[] = gacha_rate_group_label($g) . ' ' . gacha_rate_field_label($f) . '(' . $f . ') '
                   . ($a === null ? '?' : $a) . '→' . ($b === null ? '?' : $b);
        }
    }
    return $out;
}

/** 把服务端 changed 列表（"Pickup.ssrThreshold 23 -> 30"）翻成中文；认不出的原样保留 */
function gacha_changes_cn($changes)
{
    $out = array();
    foreach ((array)$changes as $c) {
        $c = trim((string)$c);
        if ($c === '') {
            continue;
        }
        if (preg_match('/^([A-Za-z]+)\.([A-Za-z]+)\s+(-?[0-9]+)\s*->\s*(-?[0-9]+)$/', $c, $m)) {
            $out[] = gacha_rate_group_label($m[1]) . ' ' . gacha_rate_field_label($m[2]) . '(' . $m[2] . ') '
                   . $m[3] . '→' . $m[4];
        } else {
            $out[] = $c;
        }
    }
    return $out;
}

/**
 * 按 ShopManager 的判定顺序推算一行各段实际出率（单位：‰，整数）。
 * 返回 total/up/fes/other/sr/r；非 Fes 行 fes 恒为 0，非 Normal 行 up 为 0。
 */
function gacha_band_summary($group, $row)
{
    $ssr = isset($row['ssrThreshold']) ? max(0, min(1000, (int)$row['ssrThreshold'])) : 0;
    $up  = ($group !== 'Normal' && isset($row['upSsrRate'])) ? max(0, min(1000, (int)$row['upSsrRate'])) : 0;
    $fes = ($group === 'Fes' && isset($row['fesSsrRate'])) ? max(0, min(1000, (int)$row['fesSsrRate'])) : 0;
    $sr  = isset($row['srRate']) ? max(0, min(1000, (int)$row['srRate'])) : 0;

    $out    = array('total' => $ssr, 'up' => 0, 'fes' => 0, 'other' => 0, 'sr' => 0, 'r' => 0);
    $cursor = 0;

    if ($up > $cursor) {
        $out['up'] = max(0, min($up, $ssr));
        $cursor    = $out['up'];
    }
    if ($group === 'Fes' && $fes > $cursor) {
        $out['fes'] = max(0, min($fes, $ssr) - $cursor);
        $cursor    += $out['fes'];
    }
    $out['other'] = max(0, $ssr - $cursor);
    $out['sr']    = max(0, $sr - $ssr);
    $out['r']     = max(0, 1000 - $ssr - $out['sr']);
    return $out;
}

/** 原始响应文本（给页面折叠展示用）：字符串原样，数组转 pretty JSON */
function gacha_raw_text($data)
{
    if ($data === null) {
        return '';
    }
    if (is_string($data)) {
        return $data;
    }
    $json = json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
    return $json === false ? '(无法序列化的响应)' : $json;
}

/* ------------------------------------------------------------ HTTP 层 --- */

/**
 * 把 ba_http() 的返回统一成页面/函数能直接用的结构。
 *
 * @param array $r ba_http() 的返回值
 * @return array
 */
function gacha_rates_unpack($r)
{
    $data    = isset($r['data']) ? $r['data'] : null;
    $http_ok = !empty($r['ok']);

    $out = array(
        'ok'                   => false,
        'rates'                => gacha_rate_normalize(null),
        'defaults'             => gacha_rate_normalize(null),
        'isDefault'            => false,
        'legacyOverrideActive' => false,
        'legacyOverridePath'   => '',
        'version'              => 0,
        'updatedAt'            => '',
        'warnings'             => array(),
        'lastError'            => '',
        'overrideFileExists'   => null,
        'overrideFileValid'    => null,
        'filePath'             => '',
        'backupFile'           => '',
        'changed'              => array(),
        'resetScope'           => '',
        'status'               => isset($r['status']) ? (int)$r['status'] : 0,
        'ms'                   => isset($r['ms']) ? (int)$r['ms'] : 0,
        'url'                  => isset($r['url']) ? (string)$r['url'] : '',
        'error'                => isset($r['error']) ? trim((string)$r['error']) : '',
        'raw_text'             => gacha_raw_text($data),
    );

    if (!is_array($data)) {
        if ($out['error'] === '') {
            $out['error'] = $http_ok ? '服务端返回的不是 JSON' : '服务端无响应';
        }
        return $out;
    }

    /* 失败响应也可能带这些元信息，先填，方便页面解释状态 */
    $out['isDefault']            = !empty($data['isDefault']);
    $out['version']              = isset($data['version']) ? (int)$data['version'] : 0;
    $out['updatedAt']            = isset($data['updatedAt']) ? (string)$data['updatedAt'] : '';
    $out['filePath']             = isset($data['filePath']) ? (string)$data['filePath'] : '';
    $out['legacyOverrideActive'] = !empty($data['legacyOverrideActive']);
    $out['legacyOverridePath']   = isset($data['legacyOverridePath']) ? (string)$data['legacyOverridePath'] : '';
    $out['lastError']            = isset($data['lastError']) ? trim((string)$data['lastError']) : '';
    $out['backupFile']           = isset($data['backupFile']) ? (string)$data['backupFile'] : '';
    $out['resetScope']           = isset($data['resetScope']) ? (string)$data['resetScope'] : '';
    if (isset($data['overrideFileExists'])) {
        $out['overrideFileExists'] = (bool)$data['overrideFileExists'];
    }
    if (isset($data['overrideFileValid'])) {
        $out['overrideFileValid'] = (bool)$data['overrideFileValid'];
    }
    if (isset($data['rates'])) {
        $out['rates'] = gacha_rate_normalize($data['rates']);
    }
    if (isset($data['defaults'])) {
        $out['defaults'] = gacha_rate_normalize($data['defaults']);
    }
    if (isset($data['warnings']) && is_array($data['warnings'])) {
        foreach ($data['warnings'] as $w) {
            if (is_string($w) && trim($w) !== '') {
                $out['warnings'][] = trim($w);
            }
        }
    }
    if (isset($data['changed']) && is_array($data['changed'])) {
        foreach ($data['changed'] as $c) {
            if (is_string($c) && trim($c) !== '') {
                $out['changed'][] = trim($c);
            }
        }
    }

    if (!$http_ok) {
        if ($out['error'] === '') {
            $out['error'] = 'HTTP ' . $out['status'];
        }
        return $out;
    }

    if (!isset($data['ok']) || $data['ok'] !== true) {
        $err = isset($data['error']) ? trim((string)$data['error']) : '';
        $out['error'] = $err !== '' ? $err : '服务端返回 ok:false（未给出 error 文本）';
        return $out;
    }

    if (!isset($data['rates']) || !is_array($data['rates'])) {
        $out['error'] = '服务端返回 ok:true 但缺少 rates 对象';
        return $out;
    }

    /* 防御：契约要求四个分类的完整字段。缺任何一项都不能当 0 处理（否则保存会把缺的组清零）。 */
    $missing = '';
    foreach (gacha_rate_groups() as $g => $def) {
        if (!isset($data['rates'][$g]) || !is_array($data['rates'][$g])) {
            $missing = '服务端返回的 rates 缺少分类「' . $def['label'] . '」(' . $g . ')';
            break;
        }
        foreach ($def['fields'] as $f) {
            if (!isset($data['rates'][$g][$f]) || !is_numeric($data['rates'][$g][$f])) {
                $missing = '服务端返回的 rates 缺少字段「' . $def['label'] . ' · '
                         . gacha_rate_field_label($f) . '」(' . $g . '.' . $f . ')';
                break 2;
            }
        }
    }
    if ($missing !== '') {
        $out['error'] = $missing;
        return $out;
    }

    $out['ok'] = true;
    return $out;
}

/**
 * 读当前生效概率。
 * @param array $opts ba_http 选项（timeout）
 * @return array gacha_rates_unpack() 的结构
 */
function gacha_rates_fetch($opts = array())
{
    return gacha_rates_unpack(ba_get('/api/admin/gacha/rates', array(), $opts));
}

/**
 * 整份覆盖写入（只提交 $rates 里存在的分类/字段；本页总是整份提交）。
 * @param array $rates [分类][字段] => int
 * @param array $opts
 * @return array
 */
function gacha_rates_save($rates, $opts = array())
{
    return gacha_rates_unpack(ba_post('/api/admin/gacha/rates', array('rates' => $rates), $opts));
}

/**
 * 恢复默认：$scope = 'all' 或 Normal / Pickup / Limited / Fes。
 * @param string $scope
 * @param array  $opts
 * @return array
 */
function gacha_rates_reset($scope, $opts = array())
{
    return gacha_rates_unpack(ba_post('/api/admin/gacha/rates/reset', array('scope' => (string)$scope), $opts));
}

/* ------------------------------------------------------------ 表单校验 --- */

/**
 * 校验并规范化表单提交的整份 rates。
 * 规则：每个分类的每个字段必须存在、为不带小数点的整数、范围 0..1000；
 *       ssrThreshold >= upSsrRate 且 ssrThreshold >= fesSsrRate。
 *
 * @param mixed  $input $_POST['rates']
 * @param string $err   出参：第一条错误（中文，可直接展示）
 * @return array|null   通过返回完整 rates；失败返回 null
 */
function gacha_rates_validate($input, &$err = '')
{
    $err = '';
    if (!is_array($input)) {
        $err = '表单数据缺失（没有收到 rates），请刷新页面后重试';
        return null;
    }

    $out = array();
    foreach (gacha_rate_groups() as $g => $def) {
        $glabel = $def['label'];
        $row    = (isset($input[$g]) && is_array($input[$g])) ? $input[$g] : array();

        foreach ($def['fields'] as $f) {
            $flabel = gacha_rate_field_label($f);

            if (!array_key_exists($f, $row)) {
                $err = '「' . $glabel . '」缺少「' . $flabel . '」(' . $f . ') 字段';
                return null;
            }

            $v = $row[$f];
            if (is_array($v)) {
                $err = '「' . $glabel . ' · ' . $flabel . '」格式不对';
                return null;
            }

            $v = trim((string)$v);
            if ($v === '' || !preg_match('/^[0-9]{1,4}$/', $v)) {
                $err = '「' . $glabel . ' · ' . $flabel . '」必须是不带小数点的整数（0–1000），收到 “'
                     . substr($v, 0, 20) . '”';
                return null;
            }

            $n = (int)$v;
            if ($n < 0 || $n > 1000) {
                $err = '「' . $glabel . ' · ' . $flabel . '」必须在 0–1000 之间（收到 ' . $n . '）';
                return null;
            }
            $out[$g][$f] = $n;
        }

        /* 阈值关系：UP / Fes 的段必须落在总阈值里面（服务端同样会拒） */
        foreach (array('upSsrRate', 'fesSsrRate') as $f) {
            if (!isset($out[$g][$f])) {
                continue;
            }
            if ($out[$g]['ssrThreshold'] < $out[$g][$f]) {
                $err = '「' . $glabel . '」的总出彩阈值（' . $out[$g]['ssrThreshold'] . '）必须 ≥ '
                     . gacha_rate_field_label($f) . '（' . $out[$g][$f] . '）';
                return null;
            }
        }
    }

    return $out;
}
