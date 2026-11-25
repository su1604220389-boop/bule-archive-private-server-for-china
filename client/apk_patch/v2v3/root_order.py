#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evidence for 'root LinearLayout child order unchanged, new node at index 2'
plus the human-readable decoded-XML diff between dec0 (original) and decL (patched).
"""
import difflib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import axml_dump as A

ORIG = os.path.join(HERE, 'res_Q9_orig.axml')
NEW = os.path.join(HERE, 'res_Q9_new.axml')
DEC0 = '/root/ba_work/dec0/res/layout/fragment_default_mobile_code_login.xml'
DECL = '/root/ba_work/decL/res/layout/fragment_default_mobile_code_login.xml'


def root_children(p):
    d = A.parse(p)
    out = []
    depth = 0
    for n in d['nodes']:
        if n['k'] == 'E_START':
            depth += 1
            if depth == 2:
                out.append(n['name'])
        elif n['k'] == 'E_END':
            depth -= 1
    return out


o = root_children(ORIG)
n = root_children(NEW)
print('=== root LinearLayout children, ORIGINAL res/Q9.xml (%d) ===' % len(o))
for i, x in enumerate(o):
    print('  [%d] %s' % (i, x))
print('\n=== root LinearLayout children, NEW res/Q9.xml (%d) ===' % len(n))
for i, x in enumerate(n):
    print('  [%d] %s%s' % (i, x, '   <== NEW NODE' if x == 'RadioGroup' else ''))
print('\nRadioGroup index in the new tree      = %d' % n.index('RadioGroup'))
print('original order preserved (minus new)  = %s' % ([x for x in n if x != 'RadioGroup'] == o))
print('ids of the original children all still present in the new tree: %s'
      % ('checked by own_diff.txt: no android:id line changed'))

# ---- decoded XML (human readable) diff ------------------------------------
d = difflib.unified_diff(open(DEC0, encoding='utf-8').read().splitlines(True),
                         open(DECL, encoding='utf-8').read().splitlines(True),
                         fromfile='dec0/res/layout/fragment_default_mobile_code_login.xml',
                         tofile='decL/res/layout/fragment_default_mobile_code_login.xml')
txt = ''.join(d)
open(os.path.join(HERE, 'layout_xml.diff'), 'w').write(txt)
print('\n=== decoded XML diff (=what was edited before aapt2 compiled it) ===')
print(txt)
print('decoded-xml diff lines: %d' % len(txt.splitlines()))
