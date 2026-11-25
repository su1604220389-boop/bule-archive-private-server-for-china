# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
p = r'work\ba\noroot\build_noroot_apk.py'
lines = open(p, encoding='utf-8').read().split('\n')
print('==== how replaced entries get their zip method ====')
for i, l in enumerate(lines, 1):
    if ("'method'" in l) or ('rep[' in l) or ('in rep' in l) or ('not in rep' in l):
        print('%5d| %s' % (i, l))
print()
print('==== context 730-760 (SrcZip.load) ====')
for n in range(730, 760):
    print('%5d| %s' % (n, lines[n - 1]))
print()
print('==== context 1655-1700 (write loop head) ====')
for n in range(1655, 1700):
    print('%5d| %s' % (n, lines[n - 1]))
