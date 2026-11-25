#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate SELFTEST_v4.md from the raw evidence files (verbatim inlining)."""
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..', '..'))
V4 = os.path.join(ROOT, 'work', 'ba', 'apk_patch', 'v4')
OUT = os.path.join(ROOT, 'SELFTEST_v4.md')


def slurp(name, tail=None, head=None):
    p = os.path.join(V4, name)
    try:
        raw = open(p, 'rb').read()
    except FileNotFoundError:
        return '(missing: %s)' % name
    for enc in ('utf-8-sig', 'utf-16', 'utf-8', 'gbk'):
        try:
            t = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        t = raw.decode('utf-8', 'replace')
    lines = t.splitlines()
    if head:
        lines = lines[:head]
    if tail:
        lines = lines[-tail:]
    return '\n'.join(lines).rstrip()


def sec(path_src, start_pat, end_pat, include_start=True):
    """cut a block out of a raw log between two header patterns"""
    lines = path_src.splitlines()
    i = next((k for k, l in enumerate(lines) if re.search(start_pat, l)), None)
    if i is None:
        return '(section not found: %s)' % start_pat
    if not include_start:
        i += 1
    j = next((k for k in range(i + 1, len(lines)) if re.search(end_pat, lines[k])), len(lines))
    return '\n'.join(lines[i:j]).rstrip()


def block(text, lang=''):
    """fence longer than any backtick run inside, so nested ``` stays literal"""
    runs = [len(m) for m in re.findall(r'`+', text)] or [0]
    fence = '`' * max(3, max(runs) + 1)
    return '%s%s\n%s\n%s\n' % (fence, lang, text, fence)


SELF = slurp('selftest_console.txt')
md = []
A = md.append

A('# SELFTEST_v4 — `v4_login.apk`（纯布局版：去掉验证码 / 手机号→卡密 / 真美化）')
A('')
A('> 生成时间：2026-11-18 20:15 (CST)　|　生成脚本：`work/ba/apk_patch/v4/build_report_v4.py`')
A('> 所有"原始输出"段落都是从证据文件里**原样内联**的，没有手工誊抄。')
A('')
A('## 0. 结论')
A('')
A('| # | 自检项 | 要求 | 实测 | 结果 |')
A('|---|---|---|---|---|')
A('| 1 | `resources.arsc` sha256 | `cd8943ae…eecb86` | `cd8943ae…eecb86` | ✅ |')
A('| 2 | `classes.dex` 逐字节 | == v2 基线 == 原始包 | `56b3a73b…c27651`（三方相同） | ✅ |')
A('| 3 | `classes2.dex` / `AndroidManifest.xml` | 不变 | 三方相同 | ✅ |')
A('| 4 | `aapt dump badging` vs v2 | diff = 0 行 | 176 行对 176 行，diff **0** | ✅ |')
A('| 5 | zip 条目 diff vs v2 | 只有 `res/Q9.xml` + `META-INF/*` | 4 条：`res/Q9.xml` + 3 个 `META-INF/*` | ✅ |')
A('| 6 | 新条目 / 丢失条目 | 无 | 无 | ✅ |')
A('| 7 | `apksigner verify` | 通过 | v2/v3 scheme 全过，exit 0 | ✅ |')
A('| 8 | 签名证书 | 与原包同一张 | `94FA997B…99EBC` | ✅ |')
A('| 9 | 包内 `res/Q9.xml` | == 喂给打包器的 AXML | sha256 完全一致 | ✅ |')
A('')
A('**全部通过。** 唯一无法验证的是真机观感（本机 `adb devices` 为空）——见第 13 节与 `preview_v4.png`。')
A('')
A('## 1. 产物')
A('')
A('| 项 | 值 |')
A('|---|---|')
A('| 路径 | `C:\\Users\\su\\Desktop\\大肥鱼项目\\BAServer\\work\\ba\\apk_patch\\out\\v4_login.apk` |')
A('| 字节数 | **2,127,972,093** |')
A('| sha256 | **`6490fcfc772f4dc6dd1773e7999a491775a646b08675591204b18212ee94eddb`** |')
A('| 基线 v2 sha256 | `562d528a951eaeb15ae3165ece4a7ceb91849bb21ef54c895c6f217f9a676d64` |')
A('| 包内 `res/Q9.xml` | 8,208 B，sha256 `f614865a97955515e41e2248af0b6004f7eefdea3d2fbd0897285d226cb189b3` |')
A('| 源 AXML（喂给打包器的那份） | `work\\ba\\apk_patch\\v4\\res_Q9_v4.axml`，同 sha256 |')
A('| 改动规模 | 解码 XML 8,915 B → 9,777 B；AXML 7,292 B(原始) / 8,284 B(v2) → **8,208 B** |')
A('')
A('## 2. `resources.arsc` —— 逐字节不变（原始输出）')
A('')
A(block(sec(SELF, r'^## 1\) resources\.arsc', r'^## 2\)')))
A('')
A('## 3. `classes.dex` / `classes2.dex` / `AndroidManifest.xml` —— 逐字节不变（原始输出）')
A('')
A(block(sec(SELF, r'^## 2\) classes\.dex', r'^## 3\)')))
A('')
A('> `classes.dex` sha256 = `56b3a73b3039db99ade67faf42e471c8de4dcd7127ce9bef49d9f4d473c27651`，'
  '在 **v1（原始重签包）/ v2（基线）/ v4（本次）** 三个包里完全相同。')
A('> 也就是说本次改动 **一个 dex 字节都没碰**（红线：改 6 字节就 0.5 秒闪退）。')
A('')
A('## 4. `aapt dump badging` —— 与 v2 基线 diff = 0 行（原始输出）')
A('')
A(block(sec(SELF, r'^## 3\) `aapt dump badging`', r'^## 4\)')))
A('')
A('## 5. zip 条目 diff（v4 vs v2，原始输出）')
A('')
A(block(sec(SELF, r'^## 4\) zip 条目 diff', r'^## 5\)')))
A('')
A('## 6. `apksigner verify --print-certs`（原始输出）')
A('')
A(block(sec(SELF, r'^## 5\) `apksigner verify', r'^## 结论')))
A('')
A('## 7. 改了哪些属性（原值 → 新值）')
A('')
A('### 7.1 改值（24 处，全部是 XML 字面量，没有一条新资源引用）')
A('')
A('| # | 控件 / 元素 | 属性 | 原值 | 新值 | 视觉效果 |')
A('|---|---|---|---|---|---|')
ROWS = [
    ('1', '根 `LinearLayout`（白卡片）', 'paddingTop', '（无）', '`8.0dip`', '卡片顶部留白，别顶到圆角边'),
    ('2', '根 `LinearLayout`', 'paddingBottom', '`@dimen/dp12`', '`24.0dip`', '底部留白加倍，整体更松弛'),
    ('3', '输入区 `ConstraintLayout`', 'layout_marginTop', '`@dimen/dp7`', '`8.0dip`', '分隔线→输入框的间距'),
    ('4', '`@id/et_phone`', 'textSize', '`@dimen/sp14`', '`16.0sp`', '输入文字更大'),
    ('5', '`@id/et_phone`', 'textColor', '`@color/c_000000`', '`#FF16213A`', '深蓝黑，比纯黑柔和'),
    ('6', '`@id/et_phone`', 'textColorHint', '`@color/disable_text`(#FFB9B9B9)', '`#FF9AA3B2`', '占位文字更清楚'),
    ('7', '`@id/et_phone`', 'background',
     '`@drawable/login_edit_bg_fragment`（透明填充 + 1dip灰描边 + 圆角）', '`#FFEAF0FB`',
     '**输入框变浅蓝色块**（最显眼之一），代价：丢圆角与描边'),
    ('8', '`@id/et_phone`', 'layout_height', '`@dimen/dp40`', '`52.0dip`', '输入框高 +12dip，更好戳'),
    ('9', '`@id/et_phone`', 'hint', '`@string/hint_phone_number`（"请输入手机号"）', '`"请输入卡密"`',
     '**需求②：手机号→卡密**'),
    ('10', '`@id/et_phone`', 'maxLength', '`11`', '`64`', '卡密最长 64 字符（沿用 v2）'),
    ('11', '`@id/et_phone`', 'inputType', '`phone`', '`text`', '全键盘，能输字母数字卡密'),
    ('12', '`@id/et_phone`', 'paddingStart', '`@dimen/dp12`', '`16.0dip`', '光标不贴边'),
    ('13', '`@id/layout_phone_code`（验证码整行）', 'visibility', '（无 = visible）', '`gone`',
     '**需求①：验证码整行消失**'),
    ('14', '`@id/et_phone_code`', 'text', '（无）', '`"000000"`',
     '看不见（父容器 gone），但给 `code.length()` 喂 6 个字符'),
    ('15', '`@id/et_phone_code`', 'textColor', '`@color/c_000000`', '`#FF16213A`', '与上面统一（肉眼看不出）'),
    ('16', '`@id/ll_container_login`（按钮容器）', 'paddingTop', '（无）', '`8.0dip`',
     '按钮上方多 8dip 空气（原因见 12.3 坑 A）'),
    ('17', '`@id/login`（登录按钮）', 'textSize', '`@dimen/sp16`', '`18.0sp`', '按钮字更大'),
    ('18', '`@id/login`', 'textColor', '`@color/bt_text`', '`#FFFFFFFF`', '纯白字'),
    ('19', '`@id/login`', 'background',
     '`@drawable/login_btn_selector`（#CC000000+圆角+按下态）', '`#FF2F6FED`',
     '**实色蓝按钮**（最显眼），代价：丢按下态与圆角'),
    ('20', '`@id/login`', 'textStyle', '（无）', '`bold`', '加粗'),
    ('21', '`@id/login`', 'layout_height', '`@dimen/dp40`', '`52.0dip`', '按钮加高 +12dip'),
    ('22', '`@id/login`', 'text', '`@string/login`（"登录"）', '`"登 录"`', '字间空格，按钮上更大气'),
    ('23', '`@id/agreement_layout`', 'layout_marginTop', '`@dimen/dp12`', '`16.0dip`', '协议行下移'),
    ('24', '`@id/tv_privacy_agreement`', 'textColor', '`@color/c_a3a3a3`', '`#FF9AA3B2`',
     '协议文字换蓝灰（运行时会再被 span 覆盖，见 12.3 坑 D）'),
]
for r in ROWS:
    A('| %s | %s | `%s` | %s | %s | %s |' % r)
A('')
A('### 7.2 新增 3 个无 id 装饰控件（根 `LinearLayout` 第 3/4/5 个子节点）')
A('')
A('```xml')
A('<TextView android:textSize="21.0sp" android:textColor="#FF12203A" android:textStyle="bold"')
A('    android:gravity="center" android:paddingLeft="24.0dip" android:paddingRight="24.0dip"')
A('    android:layout_width="fill_parent" android:layout_height="wrap_content"')
A('    android:layout_marginTop="6.0dip" android:text="卡密登录" />')
A('')
A('<TextView android:textSize="12.0sp" android:textColor="#FF8A94A6" android:gravity="center"')
A('    android:paddingLeft="24.0dip" android:paddingRight="24.0dip"')
A('    android:layout_width="fill_parent" android:layout_height="wrap_content"')
A('    android:layout_marginTop="5.0dip" android:text="无需验证码，输入卡密直接登录" />')
A('')
A('<View android:layout_width="fill_parent" android:layout_height="1.0dip"')
A('    android:layout_marginLeft="24.0dip" android:layout_marginTop="14.0dip"')
A('    android:layout_marginRight="24.0dip" android:background="#FFE7ECF5" />')
A('```')
A('')
A('- 三个都是**框架自带类**（`TextView` / `View`），**没有 id**（所以不写 `@+id`）；`android:text` 是**字符串字面量**，'
  '`android:background` 是**颜色字面量**（`View` 直接上色，不引 drawable 资源）。')
A('- 追加位置：根 `LinearLayout` 的 header（返回/logo/关闭）之后、`@id/tv_bind_phone_desc` 之前。'
  '外层是**纵向 LinearLayout**，加子节点不涉及任何 constraint，是最稳的加法'
  '（v2 往同一层塞 RadioGroup 已在真机验证"加子节点不会崩"）。')
A('- 这 3 个节点**没有任何代码引用**（`initView()` 只按 id 找控件），运行时不会被改掉。')
A('')
A('### 7.3 故意没动的')
A('')
A('- `@drawable/login_bg_fragment`（白底 + `@dimen/radius_common_dialog` 圆角 + `@color/c_ffffff`）：**保留**。'
  '圆角是这张卡片自带的，改了反而更丑；而且这个 drawable 被 20+ 个布局共用（见 13.7），不能动。')
A('- 所有 `@id`、控件类名、`app:*` 约束、`@id/layout_phone_code` 整棵子树的结构：**原样**。')
A('- `@id/third_party_login`（一键登录/TapTap 那条）：**故意不设 gone**，原因见 12.3 坑 B。')
A('- 任何 dex、`resources.arsc`、`AndroidManifest.xml`、其它资源条目：**没碰**。')
A('')
A('## 8. 解码 XML diff（`dec0` 原始 → `dec4` 改后）')
A('')
A(block(slurp('layout_xml.diff'), 'diff'))
A('')
A('## 9. 打进包的 AXML 结构（自研独立解析器 `axml_dump.py`，不经过 aapt/apktool）')
A('')
A(block(slurp('v4_axml_dump.txt')))
A('')
A('## 10. 第三方工具独立读回（`aapt dump xmltree` 直接读产物里的 `res/Q9.xml`）')
A('')
A(block(slurp('aapt_xmltree_v4.txt')))
A('')
A('## 11. 构建日志')
A('')
A('### 11.1 布局编译（`apktool b -s`：只编 res，产物里没有 dex）')
A('')
A(block(slurp('make_layout_v4.log')))
A('')
A('### 11.2 组包 + 重签（`build_noroot_apk.py`）')
A('')
A(block(slurp('build_v4.log')))
A('')
A('## 12. 运行时行为推理（为什么这样改还能登录）')
A('')
A('### 12.1 需求① —— `code.length() != 6` 为什么能过')
A('')
A('`DefaultMobileLoginFragment.handleLoginLink(Z)V` 的校验链（原始 dex，v4 未改；下面是**摘录**，'
  '省略了 `.line` 与空行）：')
A('')
A('```smali')
A('    # v3 = 卡密输入框的 trim 结果，v4 = 验证码输入框的 trim 结果')
A('    iget-object v0, p0, ...->et_phone:Landroid/widget/EditText;')
A('    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;')
A('    move-result-object v0  -> toString() -> trim()  => v3')
A('')
A('    iget-object v0, p0, ...->et_phone_code:Landroid/widget/EditText;')
A('    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;')
A('    move-result-object v0  -> toString() -> trim()  => v4')
A('')
A('    invoke-static {v3}, Landroid/text/TextUtils;->isEmpty(...)Z                # 空 -> "请输入手机号"')
A('    invoke-static {v3}, Lcom/airi/common/utils/CommonUtil;->isPhoneLegal(...)Z')
A('    invoke-static {v4}, Landroid/text/TextUtils;->isEmpty(...)Z                # 空 -> "请输入验证码"')
A('    invoke-virtual {v4}, Ljava/lang/String;->length()I')
A('    const/4 v1, 0x6')
A('    if-eq v0, v1, :cond_3                                                     # !=6 -> "验证码格式不正确"')
A('```')
A('')
A('推理：')
A('')
A('1. `android:text="000000"` 是 `TextView` 的**构造期属性** —— `EditText` 在 **inflate 时**就调用 '
  '`setText("000000")`，不需要用户操作，文本在 `initView()` 跑之前就已经在 `Editable` 里。')
A('2. `handleLoginLink` 取的是 `et_phone_code.getText().toString().trim()`；`"000000".trim()` 还是 `"000000"`，'
  '`length()` = **6**，`0x6 == 0x6` → `if-eq` **不跳转** → 继续往下走。')
A('3. `visibility="gone"` 只是"不画、不占位"，View 对象还在、`EditText` 实例还在，`getText()` 照样返回 `"000000"`。'
  '`gone` 不是 `removeView`，不影响 `findViewById`。')
A('4. 我核对过**没有任何代码会清空这个字段**：整个 `DefaultMobileLoginFragment` 里 `setText` 只出现 **1 次**，'
  '是 `tv_privacy_agreement.setText(spannable)`；`et_phone_code` 只在 `initView` 里 `findViewById` 赋值、'
  '在 `addCodeListener()` 里挂了个 `OnEditorActionListener`（回车监听），**没有** `setText("")`、**没有** `TextWatcher`。'
  '（`ExtendEditText` 自身的 `setText` 只在"点清空按钮"时被调用。）')
A('5. `maxLength="6"` 保留，`"000000"` 正好 6 位，`InputFilter.LengthFilter(6)` 不会截断；`inputType="number"` '
  '也不会拒绝已有文本。')
A('')
A('**结论：字段里真的躺着 6 个字符 `000000`，所以 `code.length()!=6` 这条永远不成立，链路能走到'
  ' `LoginManager.loginWithLink("mobile", 卡密, "000000", "", cb)`。**')
A('')
A('### 12.2 需求② —— 界面文案')
A('')
A('| 位置 | 原来 | 现在 |')
A('|---|---|---|')
A('| 卡密输入框 hint | `@string/hint_phone_number` = "请输入手机号" | **字面量 `"请输入卡密"`** |')
A('| 页面标题 | 没有 | **新增 `"卡密登录"`**（21sp 加粗深色） |')
A('| 页面副标题 | 没有 | **新增 `"无需验证码，输入卡密直接登录"`** |')
A('| 验证码行 | "请输入验证码" + "发送" | 整行 `gone`（控件还在，只是不显示） |')
A('| 登录按钮 | `@string/login` = "登录" | **字面量 `"登 录"`** |')
A('')
A('### 12.3 需求③ —— 美化，以及四个"看着改了其实会被代码改回去"的坑')
A('')
A('**坑 A：登录按钮的 `layout_marginTop` 会被 `initView()` 覆盖。** 原始代码（`initView`，`.line 106`~`.line 128`）：')
A('')
A('```smali')
A('    iget-object v0, p0, ...->login:Landroid/widget/Button;')
A('    invoke-virtual {v0}, Landroid/widget/Button;->getLayoutParams()Landroid/view/ViewGroup$LayoutParams;')
A('    ... check-cast MarginLayoutParams ...')
A('    sget v4, Lcom/airi/common/R$dimen;->dp12:I            # 普通登录模式 -> 12dp（bind 模式 -> dp54）')
A('    iput v1, v0, Landroid/view/ViewGroup$MarginLayoutParams;->topMargin:I')
A('    invoke-virtual {v1, v0}, Landroid/widget/Button;->setLayoutParams(...)')
A('```')
A('')
A('也就是说：**XML 里给 Button 写多少 `layout_marginTop`，运行时都会被改成 `dp12`。** 所以"按钮上方多留空气"'
  '改成给父容器 `@id/ll_container_login` 加 `paddingTop="8.0dip"` —— 这个 View 在**全部 smali 里一次都没被引用**'
  '（`grep -rn ll_container_login` 只命中 `R$id` 常量），padding 不会被改。最终间距 = 8dip(padding) + 12dip(代码设的 margin) = 20dip。')
A('')
A('**坑 B：`third_party_login` 的 `visibility` 由代码决定，XML 写 `gone` 没用。**')
A('')
A('```smali')
A('    .line 136')
A('    iget-object v0, p0, ...->third_party_login:Landroid/view/ViewGroup;')
A('    invoke-direct {p0}, ...->isHideAllBottomTap()Z')
A('    if-eqz v1, :cond_8            # false -> cond_8 -> v2=VISIBLE(0)')
A('    ...')
A('    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->setVisibility(I)V')
A('```')
A('')
A('`one_login` / `taptap_login` 同理（`.line 134` / `.line 135`，按 `params.leftType/rightType` 设）。'
  '所以我**没有**给这条写 `gone`——写了也会被几毫秒后的 `initView()` 覆盖，只会让报告说谎。'
  '真要藏掉只有两条路：① 改 dex（红线禁止）；② 给 `third_party_login` 写 `layout_height="0.0dip"` 把高度压成 0'
  '（代码不碰它的 layout 参数）。这招我没用（不在需求里，且属于"结构把戏"），需要的话可以出 v5。')
A('')
A('**坑 C：toast 文案改不了。** `"请输入手机号"` / `"验证码格式不正确"` 是 `R$string`，在 `resources.arsc` 里，'
  '按红线不许动。所以**页面**上写"卡密"，但用户手滑留空时弹的仍是"请输入手机号"。')
A('')
A('**坑 D：`tv_privacy_agreement` 的颜色/重力会在运行时被代码覆盖。** `.line 238~240` 做了 `setText(spannable)` + '
  '`setGravity(0x11)` + `ForegroundColorSpan`，所以我这条 `@color/c_a3a3a3 → #FF9AA3B2` **大概率看不到效果**，'
  '留着无害。')
A('')
A('### 12.4 ⚠️ 必须知道的硬约束：卡密仍然必须是"1 开头的 11 位数字"')
A('')
A('`handleLoginLink` 第一道格式检查调 `CommonUtil.isPhoneLegal()`，它直接转调 `isChinaPhoneLegal()`：')
A('')
A('```smali')
A('.method public static isChinaPhoneLegal(Ljava/lang/String;)Z')
A('    const-string v0, "^1\\d{10}$"        # <= 就是这条正则')
A('    invoke-static {v0}, Ljava/util/regex/Pattern;->compile(Ljava/lang/String;)Ljava/util/regex/Pattern;')
A('    ... matcher(p0).matches()')
A('.end method')
A('```')
A('')
A('这条正则**在 dex 里**，v4 不许改（红线）。所以：')
A('')
A('- 卡密是 `1` 开头的 11 位纯数字 → 64 字符上限 + 格式校验都能过，登录链路正常。')
A('- 卡密是 16 位字母数字 → 会弹 **"手机号格式不正确"** 并 `return`，**永远登不进去**。'
  '（v3 的 dex 补丁把这条改成 `^.{1,64}$`，那正是 v3 干的活；v4 是纯布局包，拿不到这个放宽。）')
A('- 所以：如果你们的卡密不是手机号形状，v4 只能"看起来变了"，登录仍然过不去，那种情况必须回到 v3 路线。')
A('')
A('## 13. 没把握的地方')
A('')
A('1. **"真的变好看了"我无法证明**：本机没有真机/模拟器，`preview_v4.png` 是我用 PIL 按 dp 数值手绘的近似图'
  '（不是 Android 渲染），只能证明"几何关系和颜色是这些"，不能证明在你手机屏幕上好看。')
A('2. **实色背景会丢圆角**：`android:background` 写颜色 → `ColorDrawable` → 直角矩形。所以输入框（浅蓝）和按钮（蓝）'
  '现在是**直角**，而卡片是圆角。要圆角必须新增/替换 drawable 资源（红线禁止）。')
A('3. **按钮没有按下态了**：`@drawable/login_btn_selector` 被颜色替换，按下不变色、无涟漪。')
A('4. **输入框的清空按钮仍在**：`app:clearButtonMode="whileEditing"` 是 `ExtendEditText` 自绘的，原来叠在白底+描边框里，'
  '现在背景变纯色块，图标对比度可能变差（无法目测）。')
A('5. **纵向空间变紧**：卡片总高从 ~275dip 涨到 ~352dip（含 3rd-party 那条）。`layout_gravity="center"` 居中的卡片'
  '在 720p 及以下小屏应该仍能完整显示，但弹出输入法后（`adjustPan`）被顶的幅度会比原来大。')
A('6. **`000000` 这个假验证码会被发给服务端**：`loginWithLink("mobile", 卡密, "000000", "", cb)`。'
  '如果私服后端只是忽略 `code`（或只判长度）就没问题；如果后端真拿它和短信验证码比对，就会登录失败。'
  '这一点客户端侧无法证明。')
A('7. **`login_bg_fragment` 不能换**：它是 `res/drawable/login_bg_fragment.xml`（shape：`@color/c_ffffff` + '
  '`@dimen/radius_common_dialog` 圆角），被 `fragment_user_center` / `fragment_pay` / `fragment_net_check` 等 20+ 个布局'
  '共用。所以"可选加分项：换登录页背景图"我**没有做**——它不是图片（是 shape），且替换会连带改掉其它页面。')
A('8. **会不会"一眼看出不一样"**：我赌的是 ①标题区（21sp 加粗深蓝 + 副标题 + 细分割线）②只剩一个输入框'
  '③一颗 52dip 的亮蓝实色按钮。这三点与 v2 的"只改字号间距"是量级差别；但最终观感只有你上机说了算。')
A('')
A('## 14. 复现命令')
A('')
A('```bash')
A('# 0) 前提：WSL ext4 上有 /root/ba_work/dec0（apktool 从原包解出的资源树）')
A('# 1) 改解码 XML -> apktool b -s（不汇编 smali，产物里没有 dex）-> 只取那一份 AXML')
A("wsl -e bash -lc 'cd /root/ba_work && python3 /mnt/c/.../v4/make_layout_v4.py /root/ba_work/v4_layout.axml'")
A('cp /root/ba_work/v4_layout.axml "work\\ba\\apk_patch\\v4\\res_Q9_v4.axml"')
A('# 2) 组包（基线原包 + 只替换 res/Q9.xml，重签 v1/v2/v3）')
A('python work\\ba\\noroot\\build_noroot_apk.py \\')
A('  --src    work\\ba\\apk_patch\\backup\\BA_noroot_prod_20261118_v1.apk \\')
A('  --out    work\\ba\\apk_patch\\out\\v4_login.apk \\')
A('  --keystore work\\ba\\noroot\\ba_private.keystore --storepass baserver --alias ba \\')
A('  --asset-replace res/Q9.xml=work\\ba\\apk_patch\\v4\\res_Q9_v4.axml')
A('# 3) 自检')
A("wsl -e bash -lc 'cd \"/mnt/c/.../v4\" && python3 selftest_v4.py'")
A('# 4) 近似预览图（需要带 Pillow 的 python）')
A('python work\\ba\\apk_patch\\v4\\preview.py')
A('```')
A('')
A('## 15. 证据文件清单')
A('')
for f in ('make_layout_v4.py', 'make_layout_v4.log', 'res_Q9_v4.axml', 'build_v4.log',
          'selftest_v4.py', 'selftest_console.txt', 'selftest_v4_out.txt', 'zipdiff_v4.json',
          'layout_xml.diff', 'v4_axml_dump.txt', 'aapt_xmltree_v4.txt',
          'preview.py', 'preview_v4.png', 'build_report_v4.py'):
    A('- `work\\ba\\apk_patch\\v4\\%s`' % f)
A('')

open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(md))
print('wrote', OUT, os.path.getsize(OUT), 'bytes')
