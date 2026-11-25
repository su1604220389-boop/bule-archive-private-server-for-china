#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""set_gw_dto.py —— 参数化修改 gsqc DTO A（24 字段），只改指定键，类型按模板保留。

用法：
  set_gw_dto.py                                   # 显示模板与线上差异
  set_gw_dto.py ResourceVersion=0 TableVersion=0   # 默认按模板类型转换（str 还是 str）
  set_gw_dto.py ResourceVersion=s:0                # 强制字符串 "0"
  set_gw_dto.py CDNLineCount=i:2                   # 强制整数
  set_gw_dto.py IsOpenPreDownload=b:true           # 强制布尔
  set_gw_dto.py Addr=null                          # null（不分类型）
  set_gw_dto.py --restore                         # 完全恢复成模板
  set_gw_dto.py --show                            # 只打印当前线上 JSON

设计：模板 = 基线（24 字段、Msg=""）；每次修改都从模板合并，永不因手改漂移。
类型规则：**默认沿用模板里该键的类型**（模板是 str 就给 str），避免类型漂移污染实验。
"""
import json, os, sys, shutil, hashlib

TEMPLATE = '/www/wwwroot/bapatch/state/gw/api-state.template.json'
LIVE     = '/www/wwwroot/_ba_state/gw/api-state.json'
BACKUP   = '/www/wwwroot/bapatch/state/gw/api-state.bak'

def load(p):
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)

def dump(d):
    return json.dumps(d, ensure_ascii=False, separators=(',', ':'))

def coerce(v, tmpl_val):
    """按显式前缀转换；否则沿用模板类型"""
    if v == 'null' or v == 'None':
        return None
    if v.startswith('s:'):
        return v[2:]
    if v.startswith('i:'):
        return int(v[2:])
    if v.startswith('b:'):
        return v[2:].lower() in ('1', 'true', 'yes')
    # 无前缀：沿用模板类型
    if isinstance(tmpl_val, bool):
        return v.lower() in ('1', 'true', 'yes')
    if isinstance(tmpl_val, int):
        return int(v)
    if isinstance(tmpl_val, list):
        return [x for x in v.split(',') if x] if v else []
    return v          # 模板是 str/None → 保持字符串

def write(path, data, changes=None, src='template'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        try:
            shutil.copy2(path, BACKUP)
        except Exception:
            pass
    s = dump(data)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)
    os.chmod(path, 0o644)
    try:
        import pwd
        os.chown(path, pwd.getpwnam('www').pw_uid, pwd.getpwnam('www').pw_gid)
    except Exception:
        pass
    print('written %s' % path)
    print('  bytes=%d  keys=%d  sha256=%s' % (len(s.encode('utf-8')), len(data),
                                              hashlib.sha256(s.encode()).hexdigest()[:16]))
    if changes:
        for k, v in changes.items():
            print('  SET %-24s = %r  (%s)' % (k, v, type(v).__name__))
    print('  Msg=%r  CDNLineCount=%r' % (data.get('Msg'), data.get('CDNLineCount')))

def main():
    args = sys.argv[1:]
    if not os.path.exists(TEMPLATE):
        print('ERROR: template missing: %s' % TEMPLATE); sys.exit(1)
    tpl = load(TEMPLATE)
    if len(tpl) != 24:
        print('ERROR: template has %d keys (expect 24)' % len(tpl)); sys.exit(1)

    if '--show' in args:
        print(dump(load(LIVE)) if os.path.exists(LIVE) else '(no live file)')
        return
    if '--restore' in args:
        write(LIVE, dict(tpl), None, 'template')
        return

    changes = {}
    for a in args:
        if '=' not in a:
            print('ERROR: bad arg %r (expect Key=Value)' % a); sys.exit(1)
        k, v = a.split('=', 1)
        if k not in tpl:
            print('ERROR: unknown key %r' % k); sys.exit(1)
        changes[k] = coerce(v, tpl[k])

    if not changes:
        cur = load(LIVE) if os.path.exists(LIVE) else dict(tpl)
        print('template : %d keys, %d bytes' % (len(tpl), len(dump(tpl).encode())))
        print('live     : %d keys, %d bytes' % (len(cur), len(dump(cur).encode())))
        diff = {k: (tpl.get(k), cur.get(k)) for k in tpl if tpl.get(k) != cur.get(k)}
        if diff:
            for k, (t, c) in diff.items():
                print('  DIFF %-24s template=%r  live=%r' % (k, t, c))
        else:
            print('  no diff (live == template)')
        return

    out = dict(tpl); out.update(changes)
    write(LIVE, out, changes)

if __name__ == '__main__':
    main()
