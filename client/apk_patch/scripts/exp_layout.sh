#!/bin/bash
# Experiment: add the card-kind selector to the layout and prove apktool rebuilds it
# into a drop-in binary res/Q9.xml without touching resources.arsc structure.
APKTOOL="java -Xmx8g -jar /opt/ba-tools/apktool.jar"
W=/root/ba_work
SLIM=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/slim/slim.apk
REB0=$W/slim_rebuild.apk           # empty-change rebuild
EXP=$W/dec1                        # experiment tree
rm -rf $EXP exp1.apk; cp -a $W/dec0 $EXP

LAY=$EXP/res/layout/fragment_default_mobile_code_login.xml
echo "=== before ==="
grep -n 'tv_bind_phone_desc\|ConstraintLayout android:paddingLeft' $LAY | head

python3 - "$LAY" <<'PY'
import sys, io
p = sys.argv[1]
s = io.open(p, encoding='utf-8').read()
anchor = '''    <TextView android:textSize="@dimen/sp12" android:textColor="@color/c_6a6a6a" android:gravity="center" android:id="@id/tv_bind_phone_desc" android:visibility="gone" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginLeft="@dimen/dp32" android:layout_marginRight="@dimen/dp32" android:text="@string/bind_phone_desc" />'''
assert anchor in s, 'anchor not found'
inject = anchor + '''
    <RadioGroup android:gravity="center" android:orientation="horizontal" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="@dimen/dp7" android:layout_marginBottom="@dimen/dp0" android:checkedButton="@null">
        <RadioButton android:textSize="@dimen/sp14" android:textColor="@color/c_6a6a6a" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_weight="1.0" android:button="@null" android:gravity="center" />
        <RadioButton android:textSize="@dimen/sp14" android:textColor="@color/c_6a6a6a" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_weight="1.0" android:button="@null" android:gravity="center" />
    </RadioGroup>'''
s = s.replace(anchor, inject, 1)
io.open(p, 'w', encoding='utf-8').write(s)
print('injected RadioGroup with 2 RadioButtons')
PY

echo ""
echo "=== rebuild ==="
$APKTOOL b -f -o $W/exp1.apk $EXP 2>&1 | tail -30
ls -l $W/exp1.apk

echo ""
echo "=== check: rebuilt layout present, arsc string count unchanged? ==="
python3 - "$SLIM" "$W/slim_rebuild.apk" "$W/exp1.apk" <<'PY'
import sys, zipfile
for tag, apk in (('orig', sys.argv[1]), ('reb0', sys.argv[2]), ('exp1', sys.argv[3])):
    z = zipfile.ZipFile(apk)
    n = {i.filename: i for i in z.infolist()}
    k = 'res/layout/fragment_default_mobile_code_login.xml'
    arsc = n.get('resources.arsc')
    print('%-5s layout=%s  arsc=%d B' % (tag, (n[k].file_size if k in n else 'ABSENT'), arsc.file_size if arsc else -1))
PY

echo ""
echo "=== aapt xmltree of the injected layout (first 30 lines) ==="
aapt dump xmltree $W/exp1.apk res/layout/fragment_default_mobile_code_login.xml 2>&1 | sed -n '1,4p;13,32p'
echo ""
echo "=== does the rest of the tree still match the original? ==="
aapt dump xmltree "$SLIM" res/Q9.xml > $W/o.txt 2>&1
aapt dump xmltree $W/exp1.apk res/layout/fragment_default_mobile_code_login.xml > $W/n.txt 2>&1
sed -e 's/(line=[0-9]*)//' $W/o.txt > $W/o2.txt; sed -e 's/(line=[0-9]*)//' $W/n.txt > $W/n2.txt
diff $W/o2.txt $W/n2.txt > $W/d.txt 2>&1
echo "diff lines: $(wc -l < $W/d.txt)  (expected: only the added RadioGroup subtree)"
head -30 $W/d.txt
echo "=== DONE ==="
