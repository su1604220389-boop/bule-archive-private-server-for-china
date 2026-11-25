#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4 layout build: res/Q9.xml  (fragment_default_mobile_code_login)

Difference to v2 (make_layout.py):
  v2 = tiny font/spacing/colour tweaks + a dead "游客登录/卡密登录" radio strip
  v4 = real redesign:
        * whole card re-spaced (root padding 8/24 dip)
        * NEW big bold title "卡密登录" + subtitle + divider line
        * verification-code row (@id/layout_phone_code) -> visibility=gone
          AND @id/et_phone_code gets a literal android:text="000000"
          (so handleLoginLink()'s `code.length() != 6` guard still passes)
        * phone EditText -> card-key EditText: literal hint "请输入卡密",
          64 chars, inputType=text, 16sp, filled background, 52dip tall
        * login button -> solid #FF2F6FED, white bold 18sp text, 52dip tall
        * 3rd-party login strip (一键登录/TapTap, dead in this build) -> gone

Hard rules honoured:
  * only XML literals (no new @drawable/@color/@style, no @+id, no new

    resource entries) -> resources.arsc untouched
  * ids / widget classes / view tree shape of every *referenced* view kept
    (the only tree change is +3 id-less decorative views)

Usage (inside WSL, ext4 only):
    python3 /mnt/c/.../v4/make_layout_v4.py <out.axml>
"""
import os
import shutil
import subprocess
import sys
import hashlib
import zipfile
import xml.etree.ElementTree as ET

WORK = '/root/ba_work'
DEC0 = os.path.join(WORK, 'dec0')
DEC4 = os.path.join(WORK, 'dec4')
LAYOUT_REL = 'res/layout/fragment_default_mobile_code_login.xml'
APKTOOL = ['java', '-jar', '/opt/ba-tools/apktool.jar']
OUT_APK = os.path.join(WORK, 'v4_layout_build.apk')
DEST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORK, 'v4_layout.axml')

# ---------------------------------------------------------------- new views --
TITLE_BLOCK = '''    <TextView android:textSize="21.0sp" android:textColor="#FF12203A" android:textStyle="bold" android:gravity="center" android:paddingLeft="24.0dip" android:paddingRight="24.0dip" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="6.0dip" android:text="\u5361\u5bc6\u767b\u5f55" />
    <TextView android:textSize="12.0sp" android:textColor="#FF8A94A6" android:gravity="center" android:paddingLeft="24.0dip" android:paddingRight="24.0dip" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="5.0dip" android:text="\u65e0\u9700\u9a8c\u8bc1\u7801\uff0c\u8f93\u5165\u5361\u5bc6\u76f4\u63a5\u767b\u5f55" />
    <View android:layout_width="fill_parent" android:layout_height="1.0dip" android:layout_marginLeft="24.0dip" android:layout_marginTop="14.0dip" android:layout_marginRight="24.0dip" android:background="#FFE7ECF5" />'''

LOG = []


def sub1(s, old, new, tag):
    n = s.count(old)
    if n != 1:
        raise SystemExit('EDIT FAIL [%s]: anchor %r found %d times' % (tag, old, n))
    LOG.append('%-28s %-46s -> %s' % (tag, old, new))
    return s.replace(old, new)


def edit(text):
    lines = text.split('\n')
    out = []

    # ---- locate the header row so the title block can be inserted after it --
    i_close = [i for i, l in enumerate(lines) if 'android:id="@id/iv_close"' in l]
    if len(i_close) != 1:
        raise SystemExit('EDIT FAIL: iv_close found %d times' % len(i_close))
    i_end = None
    for i in range(i_close[0] + 1, len(lines)):
        if lines[i] == '    </LinearLayout>':
            i_end = i
            break
    if i_end is None:
        raise SystemExit('EDIT FAIL: header </LinearLayout> not found')

    for i, ln in enumerate(lines):
        raw = ln

        # ---------------- 1. root card: more air, keep the white shape bg -----
        if raw.startswith('<LinearLayout android:gravity="center_horizontal"'):
            raw = sub1(raw, 'android:paddingBottom="@dimen/dp12"',
                       'android:paddingTop="8.0dip" android:paddingBottom="24.0dip"',
                       'root.padding')

        # ---------------- 2. card-key EditText --------------------------------
        elif 'android:id="@id/et_phone"' in raw:
            raw = sub1(raw, 'android:textSize="@dimen/sp14"', 'android:textSize="16.0sp"',
                       'et_phone.textSize')
            raw = sub1(raw, 'android:textColor="@color/c_000000"',
                       'android:textColor="#FF16213A"', 'et_phone.textColor')
            raw = sub1(raw, 'android:textColorHint="@color/disable_text"',
                       'android:textColorHint="#FF9AA3B2"', 'et_phone.hintColor')
            raw = sub1(raw, 'android:background="@drawable/login_edit_bg_fragment"',
                       'android:background="#FFEAF0FB"', 'et_phone.background')
            raw = sub1(raw, 'android:layout_height="@dimen/dp40"',
                       'android:layout_height="52.0dip"', 'et_phone.height')
            raw = sub1(raw, 'android:hint="@string/hint_phone_number"',
                       'android:hint="\u8bf7\u8f93\u5165\u5361\u5bc6"', 'et_phone.hint')
            raw = sub1(raw, 'android:maxLength="11"', 'android:maxLength="64"',
                       'et_phone.maxLength')
            raw = sub1(raw, 'android:inputType="phone"', 'android:inputType="text"',
                       'et_phone.inputType')
            raw = sub1(raw, 'android:paddingStart="@dimen/dp12"',
                       'android:paddingStart="16.0dip"', 'et_phone.paddingStart')

        # ---------------- 3. whole verification-code row -> GONE --------------
        elif 'android:id="@id/layout_phone_code"' in raw:
            raw = sub1(raw, 'android:id="@id/layout_phone_code"',
                       'android:id="@id/layout_phone_code" android:visibility="gone"',
                       'layout_phone_code.visibility')

        # ---------------- 4. code field: prefill 6 digits ---------------------
        elif 'android:id="@id/et_phone_code"' in raw:
            raw = sub1(raw, 'android:id="@id/et_phone_code"',
                       'android:id="@id/et_phone_code" android:text="000000"',
                       'et_phone_code.text')
            raw = sub1(raw, 'android:textColor="@color/c_000000"',
                       'android:textColor="#FF16213A"', 'et_phone_code.textColor')

        # ---------------- 5. login button: solid blue, bold, 52dip ------------
        # NB: initView() does  login.setLayoutParams(<its own LP>)  after setting
        # topMargin = @dimen/dp12, so an XML marginTop here would be thrown away
        # at runtime.  The extra air above the button therefore comes from
        # paddingTop on @id/ll_container_login (code never touches that view).
        elif 'android:id="@id/login"' in raw:
            raw = sub1(raw, 'android:textSize="@dimen/sp16"', 'android:textSize="18.0sp"',
                       'login.textSize')
            raw = sub1(raw, 'android:textColor="@color/bt_text"',
                       'android:textColor="#FFFFFFFF"', 'login.textColor')
            raw = sub1(raw, 'android:background="@drawable/login_btn_selector"',
                       'android:textStyle="bold" android:background="#FF2F6FED"',
                       'login.background+style')
            raw = sub1(raw, 'android:layout_height="@dimen/dp40"',
                       'android:layout_height="52.0dip"', 'login.height')
            raw = sub1(raw, 'android:text="@string/login"', 'android:text="\u767b \u5f55"',
                       'login.text')

        elif 'android:id="@id/ll_container_login"' in raw:
            raw = sub1(raw, 'android:orientation="vertical" android:id="@id/ll_container_login"',
                       'android:orientation="vertical" android:paddingTop="8.0dip" '
                       'android:id="@id/ll_container_login"', 'loginbox.paddingTop')

        # ---------------- 6. input container spacing --------------------------
        elif 'android:layout_marginTop="@dimen/dp7"' in raw:
            raw = sub1(raw, 'android:layout_marginTop="@dimen/dp7"',
                       'android:layout_marginTop="8.0dip"', 'inputbox.marginTop')

        # ---------------- 7. agreement row: a bit lower, calmer colour --------
        elif 'android:id="@id/agreement_layout"' in raw:
            raw = sub1(raw, 'android:layout_marginTop="@dimen/dp12"',
                       'android:layout_marginTop="16.0dip"', 'agreement.marginTop')

        elif 'android:id="@id/tv_privacy_agreement"' in raw:
            raw = sub1(raw, 'android:textColor="@color/c_a3a3a3"',
                       'android:textColor="#FF9AA3B2"', 'privacy.textColor')

        # ---------------- 8. dead 3rd-party row (one-key / TapTap) ------------
        # NOT touched: initView() sets third_party_login / one_login / taptap_login
        # visibility from LoginPageType params, so an XML visibility="gone" here
        # would simply be overwritten again a few ms later.  Left bit-identical.

        out.append(raw)
        if i == i_end:
            out.append(TITLE_BLOCK)
            LOG.append('%-28s inserted after header row (root child #3/#4/#5)' % 'title block')

    return '\n'.join(out)


def main():
    src = os.path.join(DEC0, LAYOUT_REL)
    before = open(src, encoding='utf-8').read()

    if os.path.exists(DEC4):
        shutil.rmtree(DEC4)
    shutil.copytree(DEC0, DEC4, symlinks=True, ignore=shutil.ignore_patterns(
        'smali', 'smali_classes2', 'build'))
    p = os.path.join(DEC4, LAYOUT_REL)
    after = edit(before)
    open(p, 'w', encoding='utf-8', newline='\n').write(after)

    print('=== decoded-XML edits (%d) ===' % len(LOG))
    for l in LOG:
        print('  ' + l)
    print('  decoded xml %d B -> %d B' % (len(before.encode()), len(after.encode())))

    # structural sanity on the *edited* xml
    root = ET.fromstring(after)
    kids = list(root)
    print('=== root children after edit: %d' % len(kids))
    for k in kids:
        tag = k.tag.split('}')[-1]
        aid = k.get('{http://schemas.android.com/apk/res/android}id')
        print('    %-52s %s' % (tag, aid or ''))
    # ids that the fragment code depends on must still be there, exactly once
    for i in ('@id/et_phone', '@id/et_phone_code', '@id/get_phone_code',
              '@id/layout_phone_code', '@id/login', '@id/ll_container_login',
              '@id/agreement_layout', '@id/iv_close', '@id/iv_back'):
        n = after.count('android:id="%s"' % i)
        print('  id %-26s x%d %s' % (i, n, 'OK' if n == 1 else '!! CHECK'))
        if n != 1:
            raise SystemExit('id %s count %d' % (i, n))

    # ---- apktool b -s : resources only, NO smali -> the build apk has no dex
    cmd = APKTOOL + ['b', '-s', '-f', '-o', OUT_APK, DEC4]
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
