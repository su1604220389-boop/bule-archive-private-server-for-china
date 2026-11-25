#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等长补丁：把 Unity TextAsset「SDKConfigSettings」里的 SDK 配置改成我们的域名。

背景
----
APK 里有两份 SDK 配置，内容逐字节相同（2840 B）：

  1) assets/SDKConfigSettings.json                      ← loose 文件，Java/AiriSDK 读
  2) assets/bin/Data/129346de773e72d2ec581682f32d43da   ← Unity TextAsset，C# 侧
                                                          （[TechSDK] 用 Resources 路径加载）

`build_noroot_apk.py --sdk-url` 只改第 1 份。本脚本补第 2 份。

为什么必须"等长"
----------------
该容器（6,964 B）布局（实测）：

    0x1C    u32 BE = 6964            ← 疑似文件大小字段
    0x1008  [u32 17] "SDKConfigSettings" [pad 3]
    0x1018  u32 LE = 2840            ← 文本长度前缀
    0x101C  ...2840 B JSON...        正好结束于 EOF（0x1B34 = 6964）

文本是文件里最后一个对象，后面没有任何东西，所以"内容变长"不会连锁位移；
但文件头里那个等于文件大小的 u32 还压着 —— 容器格式未完全解析，变长改动的
加载风险不可控。**所以本脚本只做等长改写**：总长恒 2840 / 恒 6964。

等长的实现手法
--------------
替换后 JSON 会变短（25→24 字符等）。差额用**尾部空格**补回 2840：

    ...}                     +  ' ' * N     ->  长度重新等于 2840

尾部空白对 JSON 解析器无意义（`JsonUtility.FromJson` / 标准 JSON 都容忍）。
如果哪天客户端换成严格定长解析器，这里会是第一个怀疑点 —— 先记着。

用法
----
    python _patch_textasset_sdkconfig.py --plan sdk-only            # 只改 sdk_url
    python _patch_textasset_sdkconfig.py --plan both                # sdk_url + 4 处探测地址
    python _patch_textasset_sdkconfig.py --plan sdk-only --dry-run  # 只算不改盘

默认 --dry-run：**不加 --apply 不会写任何文件**。

注意
----
* 本脚本**不**接进 build_noroot_apk.py，产物通过工具已有的
  `--asset-replace assets/bin/Data/129346de...=<本脚本输出>` 塞回去。
* 不改源包、不改产物、不构建。
"""

from __future__ import print_function

import argparse
import hashlib
import io
import json
import os
import struct
import sys
import zipfile

# ---------------------------------------------------------------- 常量（实测）

ENTRY = 'assets/bin/Data/129346de773e72d2ec581682f32d43da'
LOOSE = 'assets/SDKConfigSettings.json'

CONTAINER_SIZE = 6964          # 实测
SCRIPT_OFF_EXPECT = 0x1018     # u32 长度前缀位置
JSON_OFF_EXPECT = 0x101C       # JSON 起始
SCRIPT_LEN_EXPECT = 2840       # 文本长度
SIZE_FIELD_OFF = 0x1C          # 疑似文件大小字段（u32 BE）

OUR_HOST = 'https://example.com'
OUR_SDK = 'https://example.com/sdk'

# (定位/替换串, 替换成, 期望出现次数, 说明)
#   规则：按列表顺序做**全局**替换，每次替换前断言 old 恰好出现 expected 次。
#   sdk-api.yostar.cn 在 JSON 里共 3 次（sdk_url / http[1] / mtr[1]），
#   所以先用带 key 的整段把 sdk_url 那一次单独摘掉，后面才能按"恰好 2 次"处理。
PLANS = {
    'sdk-only': [
        ('"sdk_url": "https://sdk-api.yostar.cn"',
         '"sdk_url": "%s"' % OUR_HOST,
         1,
         'sdk_url（25→24，差 -1 ⇒ 尾部补 1 空格）'),
    ],
    'both': [
        ('"sdk_url": "https://sdk-api.yostar.cn"',
         '"sdk_url": "%s"' % OUR_HOST,
         1,
         'sdk_url（25→24）'),
        ('https://static.bluearchive-cn.com/checkhealth.html',
         OUR_HOST + '/checkhealth.html',
         2,
         'auto_url.http[0] + mtr[0]（50→41，两处）'),
        ('https://sdk-api.yostar.cn',
         OUR_HOST,
         2,
         'auto_url.http[1] + mtr[1]（25→24，两处，仅剩 2 次）'),
        ('https://gs-api.bluearchive-cn.com/api/health',
         OUR_HOST + '/api/health',
         2,
         'auto_url.http[2] + mtr[2]（44→35，两处）'),
    ],
}


def die(msg):
    sys.stderr.write('ERROR: %s\n' % msg)
    raise SystemExit(2)


def log(msg):
    sys.stdout.write(msg + '\n')


# ---------------------------------------------------------------- 容器解析


def read_entry(path, name):
    with zipfile.ZipFile(path) as z:
        if name not in z.namelist():
            die('%s 里没有条目 %s' % (path, name))
        return z.read(name)


def locate_json(blob):
    """返回 (json_off, script_len, script_off)。全部做断言，不做猜测。"""
    if len(blob) != CONTAINER_SIZE:
        die('容器大小 %d != 预期 %d（源包变了？）' % (len(blob), CONTAINER_SIZE))
    marker = b'{\n "sdk_url"'
    n = blob.count(marker)
    if n != 1:
        die('JSON 起始标记出现 %d 次（预期 1 次），拒绝继续' % n)
    json_off = blob.find(marker)
    if json_off != JSON_OFF_EXPECT:
        die('JSON 偏移 0x%X != 预期 0x%X' % (json_off, JSON_OFF_EXPECT))
    script_off = json_off - 4
    if script_off != SCRIPT_OFF_EXPECT:
        die('长度前缀偏移 0x%X != 预期 0x%X' % (script_off, SCRIPT_OFF_EXPECT))
    script_len = struct.unpack_from('<I', blob, script_off)[0]
    if script_len != SCRIPT_LEN_EXPECT:
        die('文本长度 %d != 预期 %d' % (script_len, SCRIPT_LEN_EXPECT))
    if json_off + script_len != len(blob):
        die('文本没有结束于 EOF（%d+%d != %d）—— 布局与预期不符'
            % (json_off, script_len, len(blob)))
    return json_off, script_len, script_off


# ---------------------------------------------------------------- 替换


def apply_plan(text, plan):
    """按 plan 顺序做等长替换；返回 (新文本, 明细列表)。

    每条：替换前断言 old 恰好出现 expected 次（多一次少一次都 die），
    然后全局替换。这样"同一 URL 出现多处"的语义是明确的、可复算的。
    """
    detail = []
    for old, new, expected, what in plan:
        if '\r\n' in text:
            die('JSON 里出现 CRLF，与预期（只有 \\n）不符，拒绝继续')
        c = text.count(old)
        if c != expected:
            die('%r 出现 %d 次，预期 %d 次 —— %s' % (old, c, expected, what))
        if new in text:
            die('文本里已含目标串 %r，可能重复执行过 —— %s' % (new, what))
        text = text.replace(old, new)
        detail.append((what, old, new, len(old), len(new), len(new) - len(old)))
    return text, detail


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='等长修补 Unity TextAsset「SDKConfigSettings」（只写不跑构建）')
    ap.add_argument('--src', default=r'report\_tmp\cn_base.apk',
                    help='源包（官方 3.0.2），默认 %(default)s')
    ap.add_argument('--out-dir', default=r'work\ba\noroot\_tmp4',
                    help='输出目录，默认 %(default)s')
    ap.add_argument('--plan', choices=sorted(PLANS), default='sdk-only')
    ap.add_argument('--apply', action='store_true',
                    help='真的写文件；不加则只做 dry-run')
    a = ap.parse_args(argv)

    if not os.path.isfile(a.src):
        die('源包不存在：%s' % a.src)

    blob = read_entry(a.src, ENTRY)
    json_off, script_len, script_off = locate_json(blob)
    text_bytes = blob[json_off:json_off + script_len]
    text = text_bytes.decode('utf-8')

    # 交叉校验：TextAsset 里这份必须和 loose 的 assets/SDKConfigSettings.json 逐字节相同
    loose = read_entry(a.src, LOOSE)
    if text_bytes != loose:
        die('TextAsset 里的文本与 %s 不一致（%d vs %d B），拒绝继续'
            % (LOOSE, len(text_bytes), len(loose)))

    # 原始字段表（只读展示，便于人工比对）
    try:
        before = json.loads(text)
    except Exception as ex:
        die('原始文本不是合法 JSON：%s' % ex)

    new_text, detail = apply_plan(text, PLANS[a.plan])
    new_len = len(new_text.encode('utf-8'))

    log('=' * 74)
    log(' 计划         : %s' % a.plan)
    log(' 源包         : %s' % a.src)
    log(' 条目         : %s' % ENTRY)
    log(' 容器         : %d B（容器头 size 字段 @0x%02X，u32 BE）'
        % (len(blob), SIZE_FIELD_OFF))
    log(' 文本区       : JSON @0x%04X，长度前缀 @0x%04X = %d'
        % (json_off, script_off, script_len))
    log('-' * 74)
    for what, old, new, lo, ln, delta in detail:
        log('   [%s] %d -> %d 字符 (%+d)' % (what, lo, ln, delta))
        log('       %r' % old)
        log('       %r' % new)
    log('-' * 74)

    if new_len > script_len:
        die('替换后 %d B > 原 %d B，等长方案不成立（需要变长，本脚本不处理）'
            % (new_len, script_len))

    pad = script_len - new_len
    pad_bytes = b' ' * pad
    final_text = new_text.encode('utf-8') + pad_bytes

    # ---- 硬断言：长度、容器、可解析、字段语义 ----
    assert len(final_text) == script_len == 2840, '文本长度断言失败'
    try:
        after = json.loads(final_text.decode('utf-8'))
    except Exception as ex:
        die('补丁后 JSON 解析失败（尾部空格方案不成立）：%s' % ex)

    # 逐字段比对：只允许我们改的那几个叶子变
    def flatten(o, pre='', out=None):
        if out is None:
            out = {}
        if isinstance(o, dict):
            for k, v in o.items():
                flatten(v, pre + '.' + k if pre else k, out)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                flatten(v, '%s[%d]' % (pre, i), out)
        else:
            out[pre] = o
        return out

    fb, fa = flatten(before), flatten(after)
    if set(fb) != set(fa):
        die('字段集合变了：多了 %r 少了 %r'
            % (sorted(set(fa) - set(fb)), sorted(set(fb) - set(fa))))
    changed = [(k, fb[k], fa[k]) for k in fb if fb[k] != fa[k]]
    log(' 尾部补齐     : %d 个空格（%d -> %d -> 回 %d）'
        % (pad, script_len, new_len, script_len))
    log(' 字段变化     : %d 个' % len(changed))
    for k, o, n in changed:
        log('   %-32s %r -> %r' % (k, o, n))
    log(' 未变化字段数 = %d' % (len(fb) - len(changed)))

    # ---- 拼回容器（长度不变，只动 JSON 区）----
    out_blob = blob[:json_off] + final_text + blob[json_off + script_len:]
    assert len(out_blob) == len(blob) == CONTAINER_SIZE, '容器长度断言失败'
    assert out_blob[:json_off] == blob[:json_off], '容器头/名称区被改动'
    assert out_blob[json_off + script_len:] == blob[json_off + script_len:], \
        '文本之后的字节被改动'
    assert struct.unpack_from('<I', out_blob, script_off)[0] == script_len, \
        '长度前缀被改动'
    assert struct.unpack_from('>I', out_blob, SIZE_FIELD_OFF)[0] == CONTAINER_SIZE, \
        '容器头 size 字段被改动'

    diff = sum(1 for i in range(len(blob)) if blob[i] != out_blob[i])
    log('-' * 74)
    log(' 改动的字节数 : %d（全部落在 0x%04X..0x%04X）'
        % (diff, json_off, json_off + script_len - 1))
    log(' 容器 sha256  : %s -> %s'
        % (hashlib.sha256(blob).hexdigest()[:16],
           hashlib.sha256(out_blob).hexdigest()[:16]))

    if not a.apply:
        log('=' * 74)
        log(' DRY-RUN：没有写任何文件。加 --apply 才会落盘。')
        return 0

    if not os.path.isdir(a.out_dir):
        os.makedirs(a.out_dir)
    out_path = os.path.join(a.out_dir, os.path.basename(ENTRY))
    with open(out_path, 'wb') as f:
        f.write(out_blob)

    # 落盘后回读自检
    back = open(out_path, 'rb').read()
    assert len(back) == CONTAINER_SIZE
    assert json.loads(back[json_off:json_off + script_len]
                      .decode('utf-8')) == after
    log('=' * 74)
    log(' 已写：%s (%d B)' % (out_path, len(back)))
    log(' sha256 = %s' % hashlib.sha256(back).hexdigest())
    log('')
    log(' 下一步（手动，别自动跑）：把该文件喂给构建器的 --asset-replace：')
    log('   --asset-replace %s=%s' % (ENTRY, out_path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
