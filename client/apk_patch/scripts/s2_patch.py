#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STEP2 patcher for BA APK (res/Q9.xml + classes.dex).
Runs on WSL ext4 only.  Edits a fresh copy of /root/ba_work/dec0 -> /root/ba_work/dec2.

4 tasks:
  1) login UI beautification (literals only for XML; GradientDrawable in smali)
  2) guest / card-key RadioGroup entry  (root LinearLayout child index 2)
  3) ban dialog shows server msg        (HttpCallBack.handleErrorCode)
  4) no client-side input validation    (maxLength 64, inputType text, regex ^.{1,64}$)
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile

DEC0 = '/root/ba_work/dec0'
DEC = '/root/ba_work/dec2'
OUTAPK = '/root/ba_work/exp_final.apk'
OUTDIR = '/root/ba_work/out'
APKTOOL = '/opt/ba-tools/apktool.jar'

LAYOUT = 'res/layout/fragment_default_mobile_code_login.xml'
FRAG = 'smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali'
HCB = 'smali/com/airi/official/core/http/net/HttpCallBack.smali'
CUTIL = 'smali/com/airi/common/utils/CommonUtil.smali'


def s32(n):
    """unsigned 32-bit colour -> signed java int literal"""
    return n - 0x100000000 if n >= 0x80000000 else n


WHITE = s32(0xFFFFFFFF)
IN_FILL = s32(0xFFF5F6F8)
IN_STROKE = s32(0xFFE6E9EF)

FAIL = []


def die(msg):
    print('!! FATAL: ' + msg)
    sys.exit(1)


def read(p):
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()


def write(p, s):
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(s)


def once(container, needle, what):
    n = container.count(needle)
    if n != 1:
        die('%s : anchor found %d times (need exactly 1): %r' % (what, n, needle[:90]))
    return container.index(needle)


# ----------------------------------------------------------------------------
# 0. fresh tree
# ----------------------------------------------------------------------------
if os.path.isdir(DEC):
    shutil.rmtree(DEC)
subprocess.check_call(['cp', '-a', DEC0, DEC])
shutil.rmtree(os.path.join(DEC, 'build'), ignore_errors=True)
log = []
log.append('[0] fresh tree: %s  (build/ removed)' % DEC)


# ----------------------------------------------------------------------------
# 1. layout XML
# ----------------------------------------------------------------------------
p = os.path.join(DEC, LAYOUT)
xml = read(p)
lines = xml.split('\n')
orig_n = len(lines)


def only_one(pred, what):
    idx = [i for i, l in enumerate(lines) if pred(l)]
    if len(idx) != 1:
        die('%s : matched %d lines (need 1)' % (what, len(idx)))
    return idx[0]


# ---- (a) root LinearLayout: +paddingTop (literal) ----
i_root = only_one(lambda l: l.startswith('<LinearLayout android:gravity="center_horizontal"'), 'root LinearLayout')
if 'android:paddingBottom="@dimen/dp12"' not in lines[i_root]:
    die('root: paddingBottom anchor missing')
lines[i_root] = lines[i_root].replace(
    'android:paddingBottom="@dimen/dp12"',
    'android:paddingTop="4.0dip" android:paddingBottom="@dimen/dp12"')
log.append('[1a] layout line %d (root LinearLayout): +android:paddingTop="4.0dip"' % (i_root + 1))

# ---- (b) insert RadioGroup right AFTER tv_bind_phone_desc (=> root child index 2) ----
i_desc = only_one(lambda l: 'android:id="@id/tv_bind_phone_desc"' in l, 'tv_bind_phone_desc')
RADIO = [
    '    <RadioGroup android:orientation="horizontal" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="6.0dip" android:layout_marginBottom="0.0dip">',
    '        <RadioButton android:textSize="14.0sp" android:textColor="#FF2B3445" android:gravity="center" android:buttonTint="#FF2F6FED" android:paddingTop="8.0dip" android:paddingBottom="8.0dip" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_weight="1.0" />',
    '        <RadioButton android:textSize="14.0sp" android:textColor="#FF2B3445" android:gravity="center" android:buttonTint="#FF2F6FED" android:paddingTop="8.0dip" android:paddingBottom="8.0dip" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_weight="1.0" />',
    '    </RadioGroup>',
]
lines[i_desc + 1:i_desc + 1] = RADIO
log.append('[1b] layout: RadioGroup(2x RadioButton, no id/no text) inserted after line %d -> root child index 2' % (i_desc + 1))

# ---- (c) et_phone ----
i_phone = only_one(lambda l: 'android:id="@id/et_phone"' in l, 'et_phone')
s = lines[i_phone]
for old, new, tag in [
    ('android:maxLength="11"', 'android:maxLength="64"', 'maxLength 11->64'),
    ('android:inputType="phone"', 'android:inputType="text"', 'inputType phone->text'),
    ('android:textColorHint="@color/disable_text"', 'android:textColorHint="#FF9AA3B2"', 'hint color literal'),
    ('android:layout_height="@dimen/dp40"', 'android:layout_height="44.0dip"', 'height 40->44'),
    ('android:paddingStart="@dimen/dp12"', 'android:paddingStart="14.0dip"', 'paddingStart 12->14'),
]:
    if s.count(old) != 1:
        die('et_phone: %s anchor count!=1 (%r)' % (tag, old))
    s = s.replace(old, new)
lines[i_phone] = s
log.append('[1c/4a/4b] layout line %d (et_phone): maxLength 64, inputType text, hint #FF9AA3B2, h44dip, pad14dip' % (i_phone + 1))

# ---- (d) layout_phone_code container ----
i_cont = only_one(lambda l: 'android:id="@id/layout_phone_code"' in l, 'layout_phone_code')
if lines[i_cont].count('android:layout_height="@dimen/dp40"') != 1:
    die('layout_phone_code: height anchor')
lines[i_cont] = lines[i_cont].replace('android:layout_height="@dimen/dp40"', 'android:layout_height="44.0dip"')
log.append('[1d] layout line %d (layout_phone_code): height 40->44dip' % (i_cont + 1))

# ---- (e) et_phone_code  (KEEP maxLength=6 / inputType=number) ----
i_code = only_one(lambda l: 'android:id="@id/et_phone_code"' in l, 'et_phone_code')
s = lines[i_code]
if 'android:maxLength="6"' not in s:
    die('et_phone_code: maxLength!=6 before patch')
if 'android:inputType="number"' not in s:
    die('et_phone_code: inputType!=number before patch')
s = s.replace('android:layout_height="@dimen/dp40"', 'android:layout_height="44.0dip"')
s = s.replace('android:paddingStart="@dimen/dp12"', 'android:paddingStart="14.0dip"')
lines[i_code] = s
if 'android:maxLength="6"' not in lines[i_code] or 'android:inputType="number"' not in lines[i_code]:
    die('et_phone_code: 6-digit limit was disturbed!')
log.append('[1e] layout line %d (et_phone_code): height 44dip, pad14dip  [maxLength=6 / inputType=number KEPT]' % (i_code + 1))

# ---- (f) login Button ----
i_btn = only_one(lambda l: 'android:text="@string/login"' in l, 'login Button')
s = lines[i_btn]
if s.count('android:layout_height="@dimen/dp40"') != 1:
    die('login: height anchor')
s = s.replace('android:layout_height="@dimen/dp40"', 'android:layout_height="46.0dip"')
s = s.replace('android:layout_marginTop="@dimen/dp12"', 'android:layout_marginTop="14.0dip"')
lines[i_btn] = s
log.append('[1f] layout line %d (login Button): height 40->46dip, marginTop 12->14dip' % (i_btn + 1))

xml_new = '\n'.join(lines)
write(p, xml_new)
log.append('[1] layout written: %d -> %d lines' % (orig_n, len(lines)))

# sanity: root child order
order = []
for l in lines:
    t = l.strip()
    if t.startswith('</') or t.startswith('<?'):
        continue
    indent = len(l) - len(l.lstrip())
    if indent == 4:
        m = re.match(r'<([A-Za-z0-9_.]+)', t)
        if m:
            order.append(m.group(1))
log.append('[1] root LinearLayout children (index -> tag): %s'
           % ', '.join('%d->%s' % (i, t) for i, t in enumerate(order)))
if len(order) != 4 or order[2] != 'RadioGroup':
    die('root child order wrong: %r' % (order,))


# ----------------------------------------------------------------------------
# 2. smali: DefaultMobileLoginFragment
# ----------------------------------------------------------------------------
BF = open(os.path.join(DEC, FRAG), encoding='utf-8', newline='').read()
frag_orig = BF

BLOCK_A = """\
    # ===== BPK-A : 登录卡片圆角 + 游客/卡密双入口（根容器第 3 个子节点 index=2）=====
    move-object v0, p1
    invoke-virtual {v0}, Landroid/view/View;->getContext()Landroid/content/Context;

    move-result-object v1

    # A1: 根容器背景 -> 16dp 圆角白色卡片（GradientDrawable，零新增资源）
    new-instance v2, Landroid/graphics/drawable/GradientDrawable;

    invoke-direct {v2}, Landroid/graphics/drawable/GradientDrawable;-><init>()V

    const v3, %(WHITE)d

    invoke-virtual {v2, v3}, Landroid/graphics/drawable/GradientDrawable;->setColor(I)V

    const/high16 v5, 0x41800000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    int-to-float v3, v3

    invoke-virtual {v2, v3}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V

    invoke-virtual {v0, v2}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    # A2a: et_phone 输入框 -> 10dp 圆角浅灰底 + 1dp 描边
    sget v3, Lcom/airi/official/core/R$id;->et_phone:I

    invoke-virtual {v0, v3}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v4

    new-instance v2, Landroid/graphics/drawable/GradientDrawable;

    invoke-direct {v2}, Landroid/graphics/drawable/GradientDrawable;-><init>()V

    const v6, %(IN_FILL)d

    invoke-virtual {v2, v6}, Landroid/graphics/drawable/GradientDrawable;->setColor(I)V

    const/high16 v5, 0x41200000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    int-to-float v3, v3

    invoke-virtual {v2, v3}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V

    const/high16 v5, 0x3f800000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    const v6, %(IN_STROKE)d

    invoke-virtual {v2, v3, v6}, Landroid/graphics/drawable/GradientDrawable;->setStroke(II)V

    invoke-virtual {v4, v2}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    # A2b: layout_phone_code 容器 -> 同一套背景（内部 et_phone_code 的 background=@null 透出）
    sget v3, Lcom/airi/official/core/R$id;->layout_phone_code:I

    invoke-virtual {v0, v3}, Landroid/view/View;->findViewById(I)Landroid/view/View;

    move-result-object v4

    new-instance v2, Landroid/graphics/drawable/GradientDrawable;

    invoke-direct {v2}, Landroid/graphics/drawable/GradientDrawable;-><init>()V

    const v6, %(IN_FILL)d

    invoke-virtual {v2, v6}, Landroid/graphics/drawable/GradientDrawable;->setColor(I)V

    const/high16 v5, 0x41200000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    int-to-float v3, v3

    invoke-virtual {v2, v3}, Landroid/graphics/drawable/GradientDrawable;->setCornerRadius(F)V

    const/high16 v5, 0x3f800000

    invoke-static {v1, v5}, Lcom/airi/official/core/utils/DisplayUtils;->dp2px(Landroid/content/Context;F)I

    move-result v3

    const v6, %(IN_STROKE)d

    invoke-virtual {v2, v3, v6}, Landroid/graphics/drawable/GradientDrawable;->setStroke(II)V

    invoke-virtual {v4, v2}, Landroid/view/View;->setBackground(Landroid/graphics/drawable/Drawable;)V

    # A3: RadioGroup = 根容器 index 2；两个 RadioButton 无 id，按位置取
    move-object v0, p1

    instance-of v2, v0, Landroid/view/ViewGroup;

    if-eqz v2, :bpk_sel_done

    check-cast v0, Landroid/view/ViewGroup;

    const/4 v2, 0x2

    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;

    move-result-object v0

    instance-of v2, v0, Landroid/widget/RadioGroup;

    if-eqz v2, :bpk_sel_done

    check-cast v0, Landroid/widget/RadioGroup;

    const/4 v2, 0x0

    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;

    move-result-object v8

    check-cast v8, Landroid/widget/RadioButton;

    invoke-virtual {v8, p0}, Landroid/view/View;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    const-string v7, "游客登录"

    invoke-virtual {v8, v7}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V

    const/4 v10, 0x1

    invoke-virtual {v8, v10}, Landroid/widget/CompoundButton;->setChecked(Z)V

    const/4 v2, 0x1

    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;

    move-result-object v9

    check-cast v9, Landroid/widget/RadioButton;

    invoke-virtual {v9, p0}, Landroid/view/View;->setOnClickListener(Landroid/view/View$OnClickListener;)V

    const-string v7, "卡密登录"

    invoke-virtual {v9, v7}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V

    :bpk_sel_done
    # ===== BPK-A END =====
""" % {'WHITE': WHITE, 'IN_FILL': IN_FILL, 'IN_STROKE': IN_STROKE}

# anchor: '.locals 11' inside initView, followed by blank line + '.line 96'
i = once(BF, """    .locals 11

    .line 96""", 'initView .locals 11 / .line 96')
BF = BF[:i + len('    .locals 11\n')] + '\n' + BLOCK_A + BF[i + len('    .locals 11\n'):]
log.append('[2a] initView: inserted block A (%d lines) after .locals 11' % BLOCK_A.count('\n'))

BLOCK_B = """\
    # ===== BPK-B : RadioButton 点击 -> 切 hint（无 id，靠 parent/indexOfChild 判别）=====
    invoke-virtual {p1}, Landroid/view/View;->getParent()Landroid/view/ViewParent;

    move-result-object v0

    instance-of v1, v0, Landroid/widget/RadioGroup;

    if-eqz v1, :bpk_not_sel

    check-cast v0, Landroid/widget/RadioGroup;

    invoke-virtual {v0, p1}, Landroid/view/ViewGroup;->indexOfChild(Landroid/view/View;)I

    move-result v2

    if-eqz v2, :bpk_sel_paid

    const-string v2, "请输入公益卡密"

    goto :bpk_sel_apply

    :bpk_sel_paid
    const-string v2, "请输入付费卡密"

    :bpk_sel_apply
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;

    invoke-virtual {v1, v2}, Landroid/widget/TextView;->setHint(Ljava/lang/CharSequence;)V

    return-void

    :bpk_not_sel
    # ===== BPK-B END =====
"""

# anchor: onClick head  ".line 330" then getId invoke
i = once(BF, """    .line 330
    invoke-virtual {p1}, Landroid/view/View;->getId()I

    move-result p1

    .line 331""", 'onClick .line 330 block')
BF = BF[:i + len('    .line 330\n')] + BLOCK_B + BF[i + len('    .line 330\n'):]
log.append('[2b] onClick: inserted block B (%d lines) before getId()' % BLOCK_B.count('\n'))

BLOCK_C = """\
    # ===== BPK-C : 初始 hint =====
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;

    const-string v1, "请输入公益卡密"

    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setHint(Ljava/lang/CharSequence;)V

    # ===== BPK-C END =====
"""

i = once(BF, """    .line 242
    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->addCodeListener()V

    return-void
.end method""", 'initView tail addCodeListener/return-void')
anchor = """    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->addCodeListener()V

    return-void"""
BF = BF.replace(anchor, """    invoke-virtual {p0}, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->addCodeListener()V

""" + BLOCK_C + """    return-void""", 1)
log.append('[2c] initView tail: inserted block C (%d lines) before return-void' % BLOCK_C.count('\n'))

write(os.path.join(DEC, FRAG), BF)


# ----------------------------------------------------------------------------
# 3. smali: HttpCallBack.handleErrorCode
# ----------------------------------------------------------------------------
HC = open(os.path.join(DEC, HCB), encoding='utf-8', newline='').read()
BLOCK_D = """\
    # ===== BPK-D : 用服务端 msg 重建 ErrorCodeInfo（保留 isLogout/isRemoveUserData）=====
    invoke-static {p2}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z

    move-result v2

    if-eqz v2, :bpk_keep_local

    invoke-virtual {v1}, Lcom/airi/official/core/http/net/ErrorCodeInfo;->component3()Z

    move-result v2

    invoke-virtual {v1}, Lcom/airi/official/core/http/net/ErrorCodeInfo;->component4()Z

    move-result v3

    new-instance v1, Lcom/airi/official/core/http/net/ErrorCodeInfo;

    invoke-direct {v1, p1, p2, v2, v3}, Lcom/airi/official/core/http/net/ErrorCodeInfo;-><init>(ILjava/lang/String;ZZ)V

    :bpk_keep_local
    # ===== BPK-D END =====
"""
i = once(HC, """    invoke-static {p1}, Lcom/airi/official/core/http/net/ErrorCodeHandler;->getCodeInfoByCode(I)Lcom/airi/official/core/http/net/ErrorCodeInfo;

    move-result-object v1

    .line 72""", 'handleErrorCode getCodeInfoByCode/move-result-object v1')
needle = """    move-result-object v1

    .line 72"""
HC = HC.replace(needle, """    move-result-object v1

""" + BLOCK_D + """
    .line 72""", 1)
write(os.path.join(DEC, HCB), HC)
log.append('[3] HttpCallBack.handleErrorCode: inserted block D (%d lines) after move-result-object v1' % BLOCK_D.count('\n'))


# ----------------------------------------------------------------------------
# 4. smali: CommonUtil regex
# ----------------------------------------------------------------------------
CU = open(os.path.join(DEC, CUTIL), encoding='utf-8', newline='').read()
old = '    const-string v0, "^1\\\\d{10}$"'
if CU.count(old) != 1:
    die('CommonUtil regex anchor count=%d' % CU.count(old))
CU = CU.replace(old, '    const-string v0, "^.{1,64}$"')
write(os.path.join(DEC, CUTIL), CU)
log.append('[4] CommonUtil.isChinaPhoneLegal: regex ^1\\d{10}$ -> ^.{1,64}$')


# ----------------------------------------------------------------------------
# 5. build
# ----------------------------------------------------------------------------
print('\n'.join(log))
print('\n[5] apktool b ...')
r = subprocess.run(['java', '-jar', APKTOOL, 'b', '-f', '-o', OUTAPK, DEC],
                   capture_output=True, text=True)
print(r.stdout[-4000:])
if r.returncode != 0:
    print(r.stderr[-6000:])
    die('apktool b rc=%d' % r.returncode)

os.makedirs(OUTDIR, exist_ok=True)
with zipfile.ZipFile(OUTAPK) as z:
    names = z.namelist()
    print('\n[6] rebuilt apk entries: %d' % len(names))
    print('    has layout entry: %s' % (LAYOUT in names))
    print('    has classes.dex : %s' % ('classes.dex' in names))
    print('    has classes2.dex: %s' % ('classes2.dex' in names))
    a = z.read(LAYOUT)
    b = z.read('classes.dex')
open(os.path.join(OUTDIR, 'Q9.xml'), 'wb').write(a)
open(os.path.join(OUTDIR, 'classes.dex'), 'wb').write(b)
print('[6] extracted %s -> %d B' % (LAYOUT, len(a)))
print('[6] extracted classes.dex -> %d B' % len(b))
print('[DONE]')
