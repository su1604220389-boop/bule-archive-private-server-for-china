# -*- coding: utf-8 -*-
"""STEP2 self-check: entry-by-entry zip diff of baseline vs new APK.
Compares central-directory metadata (name/crc32/usize/csize/method) -- no need to
decompress 2.1 GB.  For entries whose CRC differs we also print sha256 of both."""
import hashlib
import json
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OLD = r'work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk'
NEW = r'work\ba\apk_patch\out\BlueArchive_cardlogin_v1.apk'


def cd(path):
    z = zipfile.ZipFile(path)
    m = {}
    for i in z.infolist():
        m[i.filename] = i
    return z, m


def sha_entry(z, name):
    h = hashlib.sha256()
    with z.open(name) as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


zo, mo = cd(OLD)
zn, mn = cd(NEW)
print('baseline entries = %d' % len(mo))
print('new      entries = %d' % len(mn))

only_old = sorted(set(mo) - set(mn))
only_new = sorted(set(mn) - set(mo))
print('\nentries ONLY in baseline (%d):' % len(only_old))
for n in only_old:
    print('   - %-40s usize=%d crc=%08x' % (n, mo[n].file_size, mo[n].CRC))
print('entries ONLY in new (%d):' % len(only_new))
for n in only_new:
    print('   + %-40s usize=%d crc=%08x' % (n, mn[n].file_size, mn[n].CRC))

# ---- same-name entries: compare metadata ----
changed_meta = []
same_meta = 0
for n in sorted(set(mo) & set(mn)):
    a, b = mo[n], mn[n]
    if (a.CRC, a.file_size, a.compress_size, a.compress_type) != (b.CRC, b.file_size, b.compress_size, b.compress_type):
        changed_meta.append(n)
    else:
        same_meta += 1

print('\nidentical metadata (crc+size+method): %d entries' % same_meta)
print('changed entries: %d' % len(changed_meta))
print('\n%-30s %10s %10s %10s %10s  %s' % ('entry', 'old_size', 'new_size', 'old_crc', 'new_crc', 'sha256'))
print('-' * 130)
report = {}
for n in changed_meta:
    a, b = mo[n], mn[n]
    sa = sha_entry(zo, n)
    sb = sha_entry(zn, n)
    print('%-30s %10d %10d %08x %08x  %s'
          % (n, a.file_size, b.file_size, a.CRC, b.CRC, 'SAME' if sa == sb else 'DIFF'))
    report[n] = {
        'old_size': a.file_size, 'new_size': b.file_size,
        'old_crc': '%08x' % a.CRC, 'new_crc': '%08x' % b.CRC,
        'old_sha256': sa, 'new_sha256': sb,
        'old_method': a.compress_type, 'new_method': b.compress_type,
    }

print('\n=========== REQUIRED INVARIANTS ===========')
ok = True


def check(name, cond, extra=''):
    global ok
    print('%-52s %s %s' % (name, 'PASS' if cond else 'FAIL', extra))
    if not cond:
        ok = False


# resources.arsc must be byte identical
arsc_old = sha_entry(zo, 'resources.arsc')
arsc_new = sha_entry(zn, 'resources.arsc')
check('resources.arsc sha256 identical', arsc_old == arsc_new,
      '\n    orig = %s\n    new  = %s' % (arsc_old, arsc_new))
check('resources.arsc in changed list', 'resources.arsc' not in changed_meta)

allowed = {'res/Q9.xml', 'classes.dex'}
unexpected = [n for n in changed_meta if n not in allowed and not n.startswith('META-INF/')]
check('no unexpected changed entries (non META-INF)', not unexpected, str(unexpected))
check('res/Q9.xml changed', 'res/Q9.xml' in changed_meta)
check('classes.dex changed', 'classes.dex' in changed_meta)
check('classes2.dex NOT changed', 'classes2.dex' not in changed_meta)
check('AndroidManifest.xml NOT changed', 'AndroidManifest.xml' not in changed_meta)
check('res/Dk.xml NOT changed', 'res/Dk.xml' not in changed_meta)
check('assets/SDKConfigSettings.json NOT changed', 'assets/SDKConfigSettings.json' not in changed_meta)
check('entry set: nothing removed', not only_old, str(only_old))
check('entry set: only META-INF added', all(n.startswith('META-INF/') for n in only_new), str(only_new))

json.dump({'changed': report, 'only_old': only_old, 'only_new': only_new,
           'arsc_old': arsc_old, 'arsc_new': arsc_new,
           'entries_old': len(mo), 'entries_new': len(mn)},
          open(r'work\ba\apk_patch\out\zipdiff.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=2)
print('\n[%s]  (details -> out\\zipdiff.json)' % ('ALL INVARIANTS PASS' if ok else 'INVARIANT FAILURE'))
sys.exit(0 if ok else 1)
