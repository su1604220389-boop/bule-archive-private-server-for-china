# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
p = r'work\ba\noroot\build_noroot_apk.py'
lines = open(p, encoding='utf-8').read().split('\n')
hits = [i for i, l in enumerate(lines, 1)
        if 'ZIP_STORED' in l or 'ZIP_DEFLATED' in l or 'compress_type' in l
        or 'compresslevel' in l or 'ALIGN' in l.upper()]
for i in hits:
    print('%5d| %s' % (i, lines[i - 1]))
