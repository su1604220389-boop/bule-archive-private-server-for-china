#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build res/Q9.xml (binary AXML) WITHOUT reassembling any dex.

Pipeline
  1. copy /root/ba_work/dec0 (apktool decode of the 878-entry slim.apk) -> decL
  2. edit decL/res/layout/fragment_default_mobile_code_login.xml (Q9.xml)
  3. `apktool b -s`  (-s = --no-src:  DO NOT build smali -> no dex is produced)
  4. take ONLY res/layout/fragment_default_mobile_code_login.xml out of the
     throw-away build apk; everything else apktool produced is discarded.
"""
import os
import re
import shutil
import subprocess
import sys
import hashlib
import zipfile

WORK = '/root/ba_work'
DEC0 = os.path.join(WORK, 'dec0')
DECL = os.path.join(WORK, 'decL')
LAYOUT_REL = 'res/layout/fragment_default_mobile_code_login.xml'
APKTOOL = ['java', '-jar', '/opt/ba-tools/apktool.jar']
OUT_APK = os.path.join(WORK, 'v2_layout_build.apk')
DEST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORK, 'v2_layout.axml')

RADIO_BLOCK = '''    <RadioGroup android:orientation="horizontal" android:gravity="center_vertical" android:background="#FFF5F6F8" android:paddingLeft="6.0dip" android:paddingTop="2.0dip" android:paddingRight="6.0dip" android:paddingBottom="2.0dip" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginLeft="@dimen/dp24" android:layout_marginTop="10.0dip" android:layout_marginRight="@dimen/dp24">
        <RadioButton android:id="@android:id/text1" android:textSize="14.0sp" android:textColor="#FF2B3445" android:gravity="center" android:buttonTint="#FF2F6FED" android:paddingTop="8.0dip" android:paddingBottom="8.0dip" android:layout_width="0.0dip" android:layout_height="wrap_content" android:layout_weight="1.0" android:text="游客登录" android:checked="true" />
        <RadioButton android:id="@android:id/text2" android:textSize="14.0sp" android:textColor="#FF2B3445" android:gravity="center" android:buttonTint="#FF2F6FED" android:paddingTop="8.0dip" android:paddingBottom="8.0dip" android:layout_width="0.0dip" android:layout_height="wrap_content" android:layout_weight="1.0" android:text="卡密登录" />
    </RadioGroup>'''


def sub1(line, old, new, tag):
    n = line.count(old)
    if n != 1:
        raise SystemExit('EDIT FAIL [%s]: %r found %d times' % (tag, old, n))
    return line.replace(old, new)


def edit(lines):
    log = []
    out = []
    inserted = False
    for ln in lines:
        raw = ln.rstrip('\n')

        # ---- 1. et_phone : length clamp + keyboard type + 美化 -----------------
        if 'android:id="@id/et_phone"' in raw:
            before = raw
            raw = sub1(raw, 'android:maxLength="11"', 'android:maxLength="64"', 'maxLength')
            raw = sub1(raw, 'android:inputType="phone"', 'android:inputType="text"', 'inputType')
            raw = sub1(raw, 'android:textSize="@dimen/sp14"', 'android:textSize="15.0sp"', 'et_phone.textSize')
            raw = sub1(raw, 'android:textColorHint="@color/disable_text"',
                       'android:textColorHint="#FF9AA3B2"', 'et_phone.hintColor')
            raw = sub1(raw, 'android:layout_height="@dimen/dp40"',
                       'android:layout_height="44.0dip"', 'et_phone.height')
            raw = sub1(raw, 'android:paddingStart="@dimen/dp12"',
                       'android:paddingStart="14.0dip"', 'et_phone.paddingStart')
            log.append('et_phone: 6 attrs changed')

        # ---- 2. layout_phone_code : keep the two boxes the same height --------
        elif 'android:id="@id/layout_phone_code"' in raw:
            raw = sub1(raw, 'android:layout_height="@dimen/dp40"',
                       'android:layout_height="44.0dip"', 'layout_phone_code.height')
            log.append('layout_phone_code: height dp40 -> 44.0dip (et_phone_code untouched)')

        # ---- 3. login button : taller / more air above ------------------------
        elif 'android:id="@id/login"' in raw:
            raw = sub1(raw, 'android:layout_height="@dimen/dp40"',
                       'android:layout_height="46.0dip"', 'login.height')
            raw = sub1(raw, 'android:layout_marginTop="@dimen/dp12"',
                       'android:layout_marginTop="16.0dip"', 'login.marginTop')
            log.append('login button: height 46.0dip, marginTop 16.0dip')

        # ---- 4. input container : a bit more air under the radio row ----------
        elif 'android:layout_marginTop="@dimen/dp7"' in raw:
            raw = sub1(raw, 'android:layout_marginTop="@dimen/dp7"',
                       'android:layout_marginTop="10.0dip"', 'input_container.marginTop')
            log.append('input ConstraintLayout: marginTop dp7 -> 10.0dip')

        out.append(raw + '\n')

        # ---- 5. insert the RadioGroup right AFTER tv_bind_phone_desc ----------
        if 'android:id="@id/tv_bind_phone_desc"' in raw and not inserted:
            out.append(RADIO_BLOCK + '\n')
            inserted = True
            log.append('RadioGroup+2xRadioButton inserted after tv_bind_phone_desc '
                       '(root child index 2)')

    if not inserted:
        raise SystemExit('EDIT FAIL: tv_bind_phone_desc not found, radio group not inserted')
    return out, log


def main():
    if os.path.exists(DECL):
        shutil.rmtree(DECL)
    # dec0 只复制需要的部分（res/ + apktool.yml + AndroidManifest.xml + original/）
    shutil.copytree(DEC0, DECL, symlinks=True, ignore=shutil.ignore_patterns(
        'smali', 'smali_classes2', 'build'))
    p = os.path.join(DECL, LAYOUT_REL)
    lines = open(p, encoding='utf-8').read().split('\n')
    new_lines, log = edit(lines)
    before = open(p, encoding='utf-8').read()
    after = ''.join(new_lines)
    open(p, 'w', encoding='utf-8', newline='\n').write(after)
    print('=== decoded XML edits ===')
    for l in log:
        print('  -', l)
    print('  decoded xml %d B -> %d B' % (len(before.encode()), len(after.encode())))

    # ---- apktool b -s : resources only, NO smali -> NO dex ----------------
    cmd = APKTOOL + ['b', '-s', '-f', '-o', OUT_APK, DECL]
    print('\n=== %s ===' % ' '.join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip())
    print(r.stderr.strip())
    if r.returncode != 0:
        raise SystemExit('apktool b failed rc=%d' % r.returncode)

    with zipfile.ZipFile(OUT_APK) as z:
        names = z.namelist()
        print('\n=== throw-away build apk: %d entries ===' % len(names))
        print('  has classes.dex     :', 'classes.dex' in names)
        print('  has classes2.dex    :', 'classes2.dex' in names)
        print('  has resources.arsc  :', 'resources.arsc' in names)
        axml = z.read(LAYOUT_REL)
        allxml = sorted(n for n in names if n.endswith('.xml'))
    open(DEST, 'wb').write(axml)
    print('  %s -> %s  %d B  sha256=%s'
          % (LAYOUT_REL, DEST, len(axml), hashlib.sha256(axml).hexdigest()))
    # the compiled AXML of every *other* layout must be byte-identical to the
    # original package, as a sanity check that aapt2 is not rewriting the world
    print('  (checked separately by selftest)')


if __name__ == '__main__':
    main()
