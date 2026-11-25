#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5 = v4  +  re-add the 游客登录 / 卡密登录 two-entry segmented strip.

Why this file exists
--------------------
v4 dropped the "游客登录 / 卡密登录" entry switch that the user wants back.
v5 re-adds it as a *display-only* RadioGroup (2x RadioButton), everything else
is byte-for-byte the v4 layout design.

Design decisions (all forced by the hard constraints)
-----------------------------------------------------
* element order: the strip goes in as root child **index 1**, i.e. directly
  under the header row and ABOVE the v4 "卡密登录" title.
* NO android:id on any new node -> no new aapt id entry -> resources.arsc
  untouched.  (AOSP RadioGroup assigns a generated id to id-less RadioButton
  children itself at addView() time; that is framework runtime behaviour, not a
  new resource.)
* NO @drawable / @color / @style / @string / @dimen reference in the new nodes:
  only XML literals (colour "#FFRRGGBB", text, numbers) -> nothing new to
  resolve against resources.arsc.
* android:buttonTint is a *framework* attr (android.R.attr.buttonTint, API 21+,
  minSdk here is 24) so it compiles against the framework table only.

Everything from v4 is reused by importing v4's edit() function verbatim, so the
v4 baseline edits cannot drift.

Usage (inside WSL, ext4 only):
    python3 /mnt/c/.../v5/make_layout_v5.py /root/ba_work/v5_layout.axml
"""
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

WORK = '/root/ba_work'
DEC0 = os.path.join(WORK, 'dec0')
DEC5 = os.path.join(WORK, 'dec5')
LAYOUT_REL = 'res/layout/fragment_default_mobile_code_login.xml'
APKTOOL = ['java', '-jar', '/opt/ba-tools/apktool.jar']
OUT_APK = os.path.join(WORK, 'v5_layout_build.apk')
DEST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORK, 'v5_layout.axml')
V4_PY = ('/mnt/c/Users/su/Desktop/\u5927\u80a5\u9c7c\u9879\u76ee/BAServer/'
         'work/ba/apk_patch/v4/make_layout_v4.py')

# ---------------------------------------------------------------------------
# the new block: 1 RadioGroup + 2 RadioButton, all literals, no ids.
#   * 44dip of card width on each side is already spent on margins -> the strip
#     is 328-48 = 280dip wide, i.e. exactly as wide as the v4 title/divider.
#   * 40dip tall rows + 2dip group padding = 44dip total strip height.
#   * first button carries android:checked="true"  (default = 游客登录)
# ---------------------------------------------------------------------------
RADIO_BLOCK = (
    '    <RadioGroup android:orientation="horizontal" android:gravity="center_vertical"'
    ' android:background="#FFF1F5FC" android:paddingLeft="4.0dip" android:paddingTop="2.0dip"'
    ' android:paddingRight="4.0dip" android:paddingBottom="2.0dip"'
    ' android:layout_width="fill_parent" android:layout_height="wrap_content"'
    ' android:layout_marginLeft="24.0dip" android:layout_marginTop="10.0dip"'
    ' android:layout_marginRight="24.0dip">\n'
    '        <RadioButton android:textSize="15.0sp" android:textColor="#FF2B3445"'
    ' android:gravity="center" android:buttonTint="#FF2F6FED"'
    ' android:layout_width="0.0dip" android:layout_height="40.0dip"'
    ' android:layout_weight="1.0" android:text="\u6e38\u5ba2\u767b\u5f55"'
    ' android:checked="true" />\n'
    '        <RadioButton android:textSize="15.0sp" android:textColor="#FF2B3445"'
    ' android:gravity="center" android:buttonTint="#FF2F6FED"'
    ' android:layout_width="0.0dip" android:layout_height="40.0dip"'
    ' android:layout_weight="1.0" android:text="\u5361\u5bc6\u767b\u5f55" />\n'
    '    </RadioGroup>'
)


def load_v4():
    spec = importlib.util.spec_from_file_location('make_layout_v4', V4_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def insert_radio(after_v4):
    """Insert RADIO_BLOCK right after the header row -> new root child index 1."""
    lines = after_v4.split('\n')
    idx = [i for i, l in enumerate(lines) if 'android:id="@id/iv_close"' in l]
    if len(idx) != 1:
        raise SystemExit('EDIT FAIL: iv_close found %d times' % len(idx))
    i_end = None
    for i in range(idx[0] + 1, len(lines)):
        if lines[i] == '    </LinearLayout>':
            i_end = i
            break
    if i_end is None:
        raise SystemExit('EDIT FAIL: header </LinearLayout> not found')
    out = lines[:i_end + 1] + [RADIO_BLOCK] + lines[i_end + 1:]
    print('  %-28s inserted after header row (new root child #1)' % 'radio strip')
    return '\n'.join(out)


def main():
    src = os.path.join(DEC0, LAYOUT_REL)
    before = open(src, encoding='utf-8').read()

    v4 = load_v4()
    print('=== v4 baseline edits replayed (%d) ===' % 23)
    after4 = v4.edit(before)
    for l in v4.LOG:
        print('  ' + l)
    print('  (v4 decoded xml %d B)' % len(after4.encode()))

    print('=== v5 additional edit ===')
    after = insert_radio(after4)
    print('  decoded xml %d B -> %d B (+%d B)'
          % (len(after4.encode()), len(after.encode()),
             len(after.encode()) - len(after4.encode())))

    # ---------------------------------------------------- structural sanity --
    root = ET.fromstring(after)
    kids = list(root)
    print('=== root children after v5 edit: %d' % len(kids))
    for n, k in enumerate(kids):
        tag = k.tag.split('}')[-1]
        aid = k.get('{http://schemas.android.com/apk/res/android}id')
        print('    [%d] %-52s %s' % (n, tag, aid or ''))

    rg = kids[1]
    if rg.tag.split('}')[-1] != 'RadioGroup':
        raise SystemExit('index 1 is not the RadioGroup: %s' % rg.tag)
    A = '{http://schemas.android.com/apk/res/android}'
    rb = list(rg)
    if len(rb) != 2:
        raise SystemExit('RadioGroup has %d children' % len(rb))
    print('=== new RadioGroup @ root child #1 ===')
    print('    RadioGroup children=%d  id=%r  bg=%s'
          % (len(rb), rg.get(A + 'id'), rg.get(A + 'background')))
    for n, b in enumerate(rb):
        print('    [%d] %-16s text=%-8s checked=%-5s id=%r buttonTint=%s'
              % (n, b.tag.split('}')[-1], b.get(A + 'text'),
                 b.get(A + 'checked'), b.get(A + 'id'), b.get(A + 'buttonTint')))
    if rb[0].get(A + 'checked') != 'true':
        raise SystemExit('first RadioButton is not checked="true"')
    for b in rb:
        if b.get(A + 'id') is not None:
            raise SystemExit('new RadioButton must not carry an id')

    # no new resource references anywhere in the new block
    for bad in ('@drawable', '@color', '@style', '@string', '@dimen', '@+id', '@android:'):
        if bad in RADIO_BLOCK:
            raise SystemExit('new block references %s (forbidden)' % bad)

    # the ids the fragment code depends on must still be there, exactly once
    for i in ('@id/et_phone', '@id/et_phone_code', '@id/get_phone_code',
              '@id/layout_phone_code', '@id/login', '@id/ll_container_login',
              '@id/agreement_layout', '@id/iv_close', '@id/iv_back',
              '@id/tv_bind_phone_desc', '@id/tv_privacy_agreement',
              '@id/third_party_login', '@id/one_login', '@id/taptap_login',
              '@id/iv_privacy_agreement_select', '@id/login_helper'):
        n = after.count('android:id="%s"' % i)
        print('  id %-32s x%d %s' % (i, n, 'OK' if n == 1 else '!! CHECK'))
        if n != 1:
            raise SystemExit('id %s count %d' % (i, n))
    print('  android:checked="true" count = %d' % after.count('android:checked="true"'))
    print('  android:visibility="gone" count = %d' % after.count('android:visibility="gone"'))
    print('  et_phone_code text="000000" = %s' % ('android:text="000000"' in after))

    # ------------------------------------------------------------- rebuild --
    if os.path.exists(DEC5):
        shutil.rmtree(DEC5)
    shutil.copytree(DEC0, DEC5, symlinks=True,
                    ignore=shutil.ignore_patterns('smali', 'smali_classes2', 'build'))
    open(os.path.join(DEC5, LAYOUT_REL), 'w', encoding='utf-8',
         newline='\n').write(after)

    cmd = APKTOOL + ['b', '-s', '-f', '-o', OUT_APK, DEC5]
    print('\n=== %s ===' % ' '.join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip()[-3000:])
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit('apktool b failed rc=%d' % r.returncode)

    with zipfile.ZipFile(OUT_APK) as z:
        names = z.namelist()
        print('\n=== throw-away build apk: %d entries' % len(names))
        print('  has classes.dex   :', 'classes.dex' in names)
        print('  has classes2.dex  :', 'classes2.dex' in names)
        print('  has resources.arsc:', 'resources.arsc' in names)
        axml = z.read(LAYOUT_REL)
    open(DEST, 'wb').write(axml)
    print('  %s -> %s  %d B  sha256=%s'
          % (LAYOUT_REL, DEST, len(axml), hashlib.sha256(axml).hexdigest()))


if __name__ == '__main__':
    main()
