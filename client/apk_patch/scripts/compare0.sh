#!/bin/bash
# Compare original slim.apk vs apktool-rebuilt slim, byte level + aapt-level
W=/root/ba_work
SLIM=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/slim/slim.apk
REB=$W/slim_rebuild.apk
OUT=$W/cmp
rm -rf $OUT; mkdir -p $OUT

python3 - "$SLIM" "$REB" <<'PY'
import sys, zipfile, hashlib
a, b = zipfile.ZipFile(sys.argv[1]), zipfile.ZipFile(sys.argv[2])
na = {i.filename: i for i in a.infolist()}
nb = {i.filename: i for i in b.infolist()}
print('orig entries:', len(na), ' rebuilt entries:', len(nb))
print('only-in-orig :', sorted(set(na) - set(nb))[:20])
print('only-in-rebuilt:', sorted(set(nb) - set(na))[:20])
KEY = ['resources.arsc', 'AndroidManifest.xml', 'res/Q9.xml', 'res/nW.xml', 'res/o4.xml',
       'res/EQ.xml', 'res/Dk.xml', 'classes.dex', 'classes2.dex']
print('\n%-24s %10s %10s  %s' % ('entry', 'orig', 'rebuild', 'byte-identical?'))
for k in KEY:
    ia, ib = na.get(k), nb.get(k)
    if not ia or not ib:
        print('%-24s %s' % (k, 'MISSING in rebuild' if ia else 'MISSING in orig')); continue
    da, db = a.read(k), b.read(k)
    ident = 'YES' if da == db else 'NO'
    ndiff = sum(1 for x, y in zip(da, db) if x != y) if len(da) == len(db) else -1
    print('%-24s %10d %10d  %s  (len_delta=%+d, differing_bytes=%d)' %
          (k, ia.file_size, ib.file_size, ident, ib.file_size - ia.file_size, ndiff))
# global byte diff count for arsc
da = a.read('resources.arsc'); db = b.read('resources.arsc')
print('\narsc sha256 orig   :', hashlib.sha256(da).hexdigest())
print('arsc sha256 rebuilt:', hashlib.sha256(db).hexdigest())
PY

echo ""
echo "=== aapt version ==="
aapt version

echo ""
echo "=== dump xmltree res/Q9.xml (orig vs rebuilt) ==="
cd $W
unzip -o -q "$SLIM" 'res/Q9.xml' -d $OUT/orig 2>/dev/null
unzip -o -q "$REB"   'res/Q9.xml' -d $OUT/reb 2>/dev/null
aapt dump xmltree "$SLIM" res/Q9.xml > $OUT/q9_orig.txt 2>&1; echo "orig rc=$?"
aapt dump xmltree "$REB"  res/Q9.xml > $OUT/q9_reb.txt  2>&1; echo "reb  rc=$?"
wc -l $OUT/q9_orig.txt $OUT/q9_reb.txt
diff $OUT/q9_orig.txt $OUT/q9_reb.txt > $OUT/q9.diff 2>&1
echo "diff lines: $(wc -l < $OUT/q9.diff)"
head -60 $OUT/q9.diff

echo ""
echo "=== dump resources (orig vs rebuilt) ==="
aapt dump --values resources "$SLIM" > $OUT/res_orig.txt 2>&1; echo "orig rc=$?"
aapt dump --values resources "$REB"  > $OUT/res_reb.txt  2>&1; echo "reb  rc=$?"
wc -l $OUT/res_orig.txt $OUT/res_reb.txt
diff $OUT/res_orig.txt $OUT/res_reb.txt > $OUT/res.diff 2>&1
echo "res diff lines: $(wc -l < $OUT/res.diff)"
head -40 $OUT/res.diff

echo ""
echo "=== badging ==="
aapt dump badging "$SLIM" 2>&1 | head -6
echo "---"
aapt dump badging "$REB" 2>&1 | head -6
echo "=== DONE ==="
