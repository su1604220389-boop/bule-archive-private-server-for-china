#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_replay.py -- 任务书第 4 项：用我们的引擎 + **官方的数据**渲染一次，
验证引擎本身有没有 bug（期望：与官方 packet 逐字节相同）。

做法：把官方抓包里的**全部**动态值原样喂给 b24000_build：
    AccountId / MxToken / RequestId / ServerTimeTicks / LastUpdate /
    AcademyLocationDBs 全部 9 条 / ZoneVisitCharacterDBs 全部 71 zone 的 138 个元素
然后把它序列化成官方信封 {"protocol","packet","requestid"}，与抓包里的 plain 逐字节比。

只读抓包，只往 work\\ba\\noroot 下写结果。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
DEPLOY = os.path.join(ROOT, 'work', 'ba', 'server', 'deploy')
sys.path.insert(0, DEPLOY)
sys.dont_write_bytecode = True

import gen24000 as G  # noqa: E402

CAP = os.path.join(ROOT, 'report', '_tmp', 'official_decoded_201',
                   '01_24000_api_academy_getinfo.response.json')


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    with io.open(CAP, 'r', encoding='utf-8') as fh:
        cap = json.load(fh)
    off = cap['inner']
    plain = json.loads(cap['plain'])
    want_packet = plain['packet']          # 官方 packet 字符串（== 官方 inner 序列化结果）
    want_plain = cap['plain']              # 官方整条 plain（含信封）

    obj = G.b24000_build(
        off['AcademyDB']['AccountId'],
        off['SessionKey']['MxToken'],
        off['RequestId'],
        off['ServerTimeTicks'],
        locations=off['AcademyLocationDBs'],
        last_update=off['AcademyDB']['LastUpdate'],
        zone_visit=off['AcademyDB']['ZoneVisitCharacterDBs'],
    )

    got_packet = G.b24000_compact(obj)
    env = json.dumps({'protocol': plain['protocol'],
                      'packet': got_packet,
                      'requestid': off['RequestId']},
                     ensure_ascii=False, separators=(',', ':'))

    # 写出可直接拿去 diff24000.py 对比的文件
    out_inner = os.path.join(HERE, 'official_replay_exact.json')
    with io.open(out_inner, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write('\n')
    out_plain = os.path.join(HERE, 'official_replay_exact.plain.txt')
    with io.open(out_plain, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(env)

    def cmp(a, b):
        """逐字节比较，返回 (相同?, 首个差异位置, 长度)。"""
        ba, bb = a.encode('utf-8'), b.encode('utf-8')
        if ba == bb:
            return True, -1, len(ba)
        for i in range(min(len(ba), len(bb))):
            if ba[i] != bb[i]:
                return False, i, (len(ba), len(bb))
        return False, min(len(ba), len(bb)), (len(ba), len(bb))

    ok_packet, dp, lp = cmp(got_packet, want_packet)
    ok_plain, dpl, lpl = cmp(env, want_plain)

    print('== 引擎 + 官方数据 重放 ==')
    print('  输入        : %s' % CAP)
    print('  账号        : %d' % off['AcademyDB']['AccountId'])
    print('  MxToken     : %d 字符' % len(off['SessionKey']['MxToken']))
    print('  ticks       : %d' % off['ServerTimeTicks'])
    print('  地点条数    : %d' % len(off['AcademyLocationDBs']))
    zv = off['AcademyDB']['ZoneVisitCharacterDBs']
    print('  zone 数     : %d   元素总数 %d' % (len(zv), sum(len(v) for v in zv.values())))
    print()
    print('  packet 逐字节 : %s  (%d B vs 官方 %d B)%s'
          % ('IDENTICAL' if ok_packet else 'DIFFERS', len(got_packet.encode('utf-8')),
             len(want_packet.encode('utf-8')), '' if ok_packet else '  首个差异 @%d' % dp))
    print('  整条 plain    : %s  (%d B vs 官方 %d B)%s'
          % ('IDENTICAL' if ok_plain else 'DIFFERS', len(env.encode('utf-8')),
             len(want_plain.encode('utf-8')), '' if ok_plain else '  首个差异 @%d' % dpl))
    print()
    print('  写出        : %s' % out_inner)
    print('  写出        : %s' % out_plain)
    if not ok_packet:
        print('  引擎差异位置 @%d: 我们 %r | 官方 %r'
              % (dp, got_packet[max(0, dp - 30):dp + 30], want_packet[max(0, dp - 30):dp + 30]))
    return 0 if ok_packet else 1


if __name__ == '__main__':
    sys.exit(main())
