# -*- coding: utf-8 -*-
"""account for the byte delta between baseline and new APK"""
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OLD = r'work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk'
NEW = r'work\ba\apk_patch\out\BlueArchive_cardlogin_v1.apk'


def stats(path, tag):
    z = zipfile.ZipFile(path)
    infos = sorted(z.infolist(), key=lambda i: i.header_offset)
    cd_off = z.start_dir
    fsize = None
    import os
    fsize = os.path.getsize(path)
    sum_c = sum(i.compress_size for i in infos)
    sum_lh = 0
    for i in infos:
        sum_lh += 30 + len(i.filename.encode('utf-8')) + len(i.extra)
    # gaps between entries (alignment padding)
    gaps = 0
    for k, i in enumerate(infos):
        end = i.header_offset + 30 + len(i.filename.encode('utf-8')) + len(i.extra) + i.compress_size
        nxt = infos[k + 1].header_offset if k + 1 < len(infos) else cd_off
        gaps += nxt - end
    print('[%s]' % tag)
    print('   file_size           = %d' % fsize)
    print('   entries             = %d' % len(infos))
    print('   sum(compress_size)  = %d' % sum_c)
    print('   sum(local header)   = %d' % sum_lh)
    print('   sum(gap/padding)    = %d' % gaps)
    print('   cd_offset(start_dir)= %d' % cd_off)
    print('   cd+EOCD tail        = %d' % (fsize - cd_off))
    print('   sum(extra len)      = %d' % sum(len(i.extra) for i in infos))
    return dict(fsize=fsize, sum_c=sum_c, sum_lh=sum_lh, gaps=gaps, cd=cd_off,
                tail=fsize - cd_off, n=len(infos))


a = stats(OLD, 'BASELINE')
print()
b = stats(NEW, 'NEW')
print('\n================ DELTA ================')
for k in ('fsize', 'sum_c', 'sum_lh', 'gaps', 'cd', 'tail'):
    print('   %-8s %+d' % (k, b[k] - a[k]))
