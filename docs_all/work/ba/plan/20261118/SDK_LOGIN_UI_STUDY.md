# SDK_LOGIN_UI_STUDY — AiriSDK 登录界面技术栈 / 两入口方案 / 错误文案显示路径

- 调研时间：2026-11-18（**只读**，未改任何既有文件；未连服务器；未装 APK）
- 调研对象：`work\ba\noroot\BA_noroot_prod_20261118_v1.apk`（2,127,971,177 B，mtime 2026-11-18 00:04，`versionCode=73`）
- 临时产物：`work\ba\plan\20261118\_sdkui_tmp\`（自写的 ARSC / AXML / DEX 解析器 + 全部 dump）
- 证据口径：**代码级已证实** = 有反汇编/资源字节可复现；**推断** = 由已证事实推出但未真机实测；**未知** = 本轮拿不到

---

## 0. 摘要（先给结论）

1. **登录界面是标准 XML 布局 + Fragment**，不是 WebView，也不是代码动态构建。
   - 壳：`com.airi.official.core.base.BackgroundAct` → `R.layout.act_background` → `res/nW.xml`
   - 表单：`com.airi.official.core.ui.fragment.DefaultMobileLoginFragment` → `R.layout.fragment_default_mobile_code_login` → `res/Q9.xml`
   - 文案全部来自 `resources.arsc` 里的 `@string/*`（UTF-8 全局字符串池），**改文案 = 改 arsc，不碰 DEX**
2. **不能"不重签"改任何 UI**。但**重签不是新增成本**：现网这个 APK 本来就是我们自己重签的（`ba_private.keystore` / alias `ba` / pass `baserver`），构建脚本 `build_noroot_apk.py` 自带 v1/v2/v3 签名实现，无需 java/apksigner。
3. **三个方案的代价差距极大**：改 arsc 字符串 + 两个 u32 ≈ 半天；改布局 XML 需要补一个"保真 AXML 重写器"（现有 `Axml` 类写空 resource-map，**不能**用于 layout）≈ 1–2 天；新增 Activity 要造 DEX ≈ 一周且风险最高。
4. **客户端不需要区分两种卡**。服务端 `cards.kind` 已经把身份链分叉完了，客户端两条路最终发出的是**同一个** `LoginReq{Type:"mobile", OpenID:卡密}`。UI 上分两个入口纯属装饰。
5. **但有一个真问题**：客户端有**两条硬卡口**，现在只接受「`1` 开头 11 位数字」的卡密 + 「恰好 6 位」的验证码 ——
   - `CommonUtil.isChinaPhoneLegal` 正则 `^1\d{10}$`（DEX string idx=32792）
   - `et_phone` `maxLength=11`、`inputType=0x3`（`res/Q9.xml` 0xc88 / 0xc9c）
   - `et_phone_code` `maxLength=6` + 代码里 `code.length()!=6` 拦截
   管理面板默认生成的卡密是**16 位 alnum**（`cardadmin_php/inc/helpers.php:809-822` 的 `gen_card_key` + `cards_new.php:46` 默认 `gen_len=16`），**这个格式当前根本输不进去也过不了校验**。
6. **服务端 `Msg` 不会直接显示**。`/user/login` 失败时：
   - 弹窗文案取自**本地 SQLite 表 `error_msg`**（`code → msg/type`），表空就回落 `R.string.UN_KNOW_ERROR` = **"未知错误，请联系客服。"**
   - `Msg` 只进 logcat（`MyLog.e("loginFailedCallBack_code: … , msg: …")`）和一个给 Unity 的 `R_MSG`
   - 弹窗是 `TipsActivity` + `res/o4.xml`，内容 `@id/tv_tips_content` **`maxLines=4`**，超出以"…"截断 ⇒ **上限约 50–60 个汉字**
7. **发现一条零 APK 改动的文案控制通道**：`/common/client-code`。服务端返回 `{Code,Type,Value}` 列表，客户端会写进 `error_msg` 表，之后所有 `Code≠200` 的提示都按我们给的 `Type`（`toast` / `none` / 其它=弹窗）和 `Value` 显示。**当前 `sdkcard_v2.py` 没实现这个端点**（全文只有 `/common/config`、`/common/geo-ip`）。

---

## 1. 现有登录界面技术栈

### 1.1 用的是哪个 APK

| 项 | 值 | 证据 |
|---|---|---|
| 现网/最新产物 | `work\ba\noroot\BA_noroot_prod_20261118_v1.apk` | 2,127,971,177 B，`2026-11-18 00:04:40` |
| 与部署副本同一份 | `work\ba\server\deploy\_noroot\apk\BA_noroot_v2.apk` | 字节数完全相同 2,127,971,177 |
| 构建脚本 | `work\ba\noroot\build_noroot_apk.py`（115,359 B，2026-11-17 20:40） | 单文件纯 Python，自带 AXML 生成 / ZIP 重打包 / APK v1+v2+v3 签名 |
| versionCode | **73** | 解析 `AndroidManifest.xml` 属性 `versionCode` = `0x49` |
| dex | `classes.dex` 9,327,708 + `classes2.dex` 10,158,904；8,030 + 7,882 个类 | Python `zipfile` + 自写 DEX 头解析 |
| `com.airi.*` 全部在 `classes.dex` | 914 个类 | 同上 |

> 另一份 `work\ba\audit\ba-apk\jadx\` 里**确实有 jadx 反编译产物，但它是残缺的**：`com\airi\` 下只有 41 个类，`official\core\base\`（含 `BackgroundAct`）、`official\core\manager\`、`official\core\ui\activity\` **全部缺失**。
> 本报告的所有 SDK 侧结论**不依赖 jadx 产物**，全部来自我自己写的 DEX 反汇编（`_sdkui_tmp\dexlib.py`）。`slim.apk` 里的两个 dex 与现网 APK 的两个 dex **字节数完全一致**（9,327,708 / 10,158,904），所以类清单对得上。

### 1.2 本机工具情况（必须先说清楚）

```
OK   python  (C:\msys64\ucrt64\bin\python.exe)
OK   adb / docker / wsl
MISS java  javac  apktool  jadx  aapt  aapt2  unzip  7z  keytool  apksigner  zipalign
```

⇒ **没有 java / apktool / jadx / aapt / unzip**。所以本轮全部改用：
`zipfile` 读 APK 条目 + 自写 **ARSC 解析器**（`t_arsc*.py`）+ 自写 **AXML 解码器**（`t_axml.py`）+ 自写 **DEX 解析/反汇编器**（`dexlib.py`）。

**好消息**：这条路线不需要任何新装工具，而且**出包侧也不用**——`build_noroot_apk.py` 自己实现了签名与重打包（脚本头注释第 6–7 行明说）。

### 1.3 界面层级：`BackgroundAct` 只是个壳

Manifest 里注册的 activity（`work\ba\audit\ba-apk\jadx\resources\AndroidManifest.xml:387`）：

```xml
<activity android:name="com.airi.official.core.base.BackgroundAct" ... />
```

> ⚠️ 任务书里写的 `com.airi.core.base.BackgroundAct` **名字不准**，真实 FQN 是 `com.airi.official.core.base.BackgroundAct`（`Lcom/airi/official/core/base/BackgroundAct;`，父类 `Lcom/airi/common/ui/CommonActivity;`）。

`BackgroundAct` 的 12 个方法与它引用的资源（`_sdkui_tmp\out1.txt:17-21`）：

| 方法 | 引用的 `R$*` 字段 | 解析出的资源 |
|---|---|---|
| `onCreate` | `R$layout;.act_background` | `res/nW.xml` |
| `initView` | `R$id;.ll_act_background_content`、`R$id;.view_act_background` | 容器 / 背景图 |

`res/nW.xml`（**`layout/act_background`**）全文只有 3 个节点：

```xml
<androidx.constraintlayout.widget.ConstraintLayout match_parent/match_parent>
  <ImageView id=@id/view_act_background background=@color/clean .../>
  <androidx.constraintlayout.widget.ConstraintLayout id=@id/ll_act_background_content .../>
</ConstraintLayout>
```

⇒ `BackgroundAct` = **背景图 + 一个空的 ConstraintLayout 容器**，`showFragment(...)` 把 Fragment 塞进 `ll_act_background_content`。真正的登录表单是 Fragment。

### 1.4 登录表单：`DefaultMobileLoginFragment` + `res/Q9.xml`

`DefaultMobileLoginFragment` 的 `getContentLayoutId()`（`_sdkui_tmp\out1.txt:47`）：

```
getContentLayoutId  →  sget Lcom/airi/official/core/R$layout;->fragment_default_mobile_code_login:I
```

**这就是决定性证据：界面是 XML 布局，靠 `AbsFragment.getContentLayoutId()` 返回 `R.layout.*` 再由 `onCreateView` inflate。**
（`AbsFragment.getContentLayoutId` 是 `acc=0x0404` 抽象方法，没有代码 —— 见 `out2.txt:62`。）

`R$layout;.fragment_default_mobile_code_login` → `res/Q9.xml`（7,292 B）。解码后的结构（片段，完整见 `_sdkui_tmp\out14.txt` / 本节末）：

```xml
<!-- res/Q9.xml = layout/fragment_default_mobile_code_login -->
<LinearLayout orientation=vertical background=@drawable/login_bg_fragment
              layout_width=@dimen/dp328 layout_height=wrap_content>
  <LinearLayout>                                    <!-- 顶栏 -->
    <ImageView id=@id/iv_back background=@drawable/back .../>
    <ImageView id=@id/iv_logo  background=@drawable/ic_login_logo .../>
    <ImageView id=@id/iv_close background=@drawable/close .../>
  </LinearLayout>

  <TextView id=@id/tv_bind_phone_desc visibility=GONE text=@string/bind_phone_desc .../>

  <androidx.constraintlayout.widget.ConstraintLayout paddingLeft=@dimen/dp24 paddingRight=@dimen/dp24>
    <com.airi.official.core.widget.ExtendEditText
        id=@id/et_phone
        hint=@string/hint_phone_number      <!-- "请输入手机号" -->
        maxLength=11  inputType=0x3  singleLine=true
        background=@drawable/login_edit_bg_fragment clearButtonMode=2 .../>

    <androidx.constraintlayout.widget.ConstraintLayout id=@id/layout_phone_code>
      <com.airi.official.core.widget.ExtendEditText
          id=@id/et_phone_code
          hint=@string/hint_phone_code      <!-- "请输入验证码" -->
          maxLength=6  inputType=0x2  singleLine=true .../>
      <TextView id=@id/divide .../>
      <TextView id=@id/get_phone_code text=@string/get_phone_code singleLine=true .../>  <!-- "发送" -->
    </androidx.constraintlayout.widget.ConstraintLayout>

    <LinearLayout id=@id/ll_container_login>        <!-- 空容器，官方预留插槽 -->
      <Button id=@id/login text=@string/login .../>              <!-- "登录" -->
      <View   id=@id/login_helper visibility=GONE .../>
    </LinearLayout>

    <androidx.constraintlayout.widget.ConstraintLayout id=@id/agreement_layout>
      <ImageView id=@id/iv_privacy_agreement_select background=@drawable/disagree .../>
      <TextView  id=@id/tv_privacy_agreement text=@string/privacy_agreement .../>
    </androidx.constraintlayout.widget.ConstraintLayout>

    <FrameLayout id=@id/third_party_login>          <!-- 第三方登录：2 个入口 -->
      <LinearLayout id=@id/one_login  ...><TextView text=@string/one_login/></LinearLayout>   <!-- "一键登录" -->
      <FrameLayout  id=@id/taptap_login .../>
    </FrameLayout>
  </androidx.constraintlayout.widget.ConstraintLayout>
</LinearLayout>
```

`DefaultMobileLoginFragment.initView` 里 `findViewById` 的 id 清单（`out1.txt:53-68`）与上面 XML 完全对得上：
`iv_close, iv_back, et_phone, et_phone_code, get_phone_code, tv_bind_phone_desc, agreement_layout, login, login_helper, third_party_login, taptap_login, one_login, iv_privacy_agreement_select, tv_privacy_agreement`。

**另一页**：`QuickLoginFragment.getContentLayoutId()` → `fragment_quick_login` → `res/EQ.xml`（`out1.txt:105`），就是 `LoginManager.handleLoginWithoutLastUser` 在有历史账号时 `FragmentCommonUtils.goQuickLogin(...)` 打开的那页（`out3.txt:50-58`）：

```xml
<!-- res/EQ.xml = layout/fragment_quick_login -->
<ConstraintLayout background=@drawable/login_bg_fragment layout_width=@dimen/dp328 layout_height=@dimen/dp222>
  <ImageView id=@id/iv_close .../>
  <ImageView id=@id/iv_logo  background=@drawable/ic_login_logo .../>
  <ConstraintLayout id=@id/quick_login_layout>
    <ConstraintLayout id=@id/phone_code_layout background=@drawable/login_edit_bg_fragment>
      <ImageView id=@id/phone_logo src=@drawable/phone .../>
      <TextView id=@id/phone          text=@string/phone_number  .../>   <!-- "137****8888" -->
      <TextView id=@id/login_interval text=@string/login_interval .../>  <!-- "上次登录1天前" -->
      <ImageView id=@id/down_arrow .../>
    </ConstraintLayout>
    <Button id=@id/quick_login text=@string/quick_login .../>            <!-- "进入游戏" -->
  </ConstraintLayout>
  <Button id=@id/other_login text=@string/login_other .../>              <!-- "登录其他账号" -->
</ConstraintLayout>
```

`res/EQ.xml` 里的 `@id/other_login`（文案 = `@string/login_other` = **"登录其他账号"**）点了会 `goDefaultLogin(...)` —— **这就是"第二个入口"的现成范本**（`QuickLoginFragment.onClick` / `getData` 都调 `FragmentCommonUtils.goDefaultLogin`，见 `out11.txt:16-18`）。

### 1.5 文案在哪：`resources.arsc` 的 UTF-8 全局字符串池

| `R.string` | 池 index | 值 |
|---|---|---|
| `hint_phone_number` / `please_input_phone` | **1087**（两个资源共用同一条池字符串） | `请输入手机号` |
| `hint_phone_code` / `please_input_phone_code` | **1095**（共用） | `请输入验证码` |
| `login` | 1052 | `登录` |
| `get_phone_code` | 975 | `发送` |
| `one_login` | 961 | `一键登录` |
| `quick_login` | 1108 | `进入游戏` |
| `bind_phone_desc` | 1082 | `请绑定悠星通行证继续登录。未注册手机号登录后将自动创建悠星通行证。` |
| `privacy_agreement` | 989 | `已阅读并同意《用户协议》,《隐私政策》和《儿童隐私政策》` |
| `UN_KNOW_ERROR` | — | `未知错误，请联系客服。` |
| `illegal_phone` | — | `手机号格式不正确` |
| `illegal_phone_code` | — | `验证码格式不正确` |

（`_sdkui_tmp\out22.txt`、`out14.txt:11-20`；ARSC 全局池 `flags=0x100` ⇒ **UTF-8 编码**，池头 `hdrSize=28`，首条 `off=0x0000bf60`）

**要点**：`hint_phone_number` 和 `please_input_phone` 指向**同一条**池字符串（index 1087）。所以改一次 arsc，输入框 hint 和本地校验 toast **一起变**，不会出现"框里写卡密、toast 喊手机号"的不一致。

### 1.6 能不能改？—— 签名/验签的真相

**结论：任何 UI 改动都必须重签；但重签是现成流程，不是障碍。**

- 现网 APK **已经是我们重签过的**：
  - 钥匙：`work\ba\noroot\ba_private.keystore`（2,568 B）、`ba_private.cert.pem`（1,126 B）、`ba_private.key.pem`（1,698 B），2026-11-16 06:20 生成
  - `build_noroot_apk.py:2242` `gen_keystore(path, password='baserver', alias='ba')`
  - 旁证：`work\ba\noroot\SIGNER_FIXES.md`、`LEAD_VERIFY_SIGNER.md`、`*_signed.apk.idsig`、`_dd4-integrity.md` 结论 4（"重打包做过、而且签名真的换过、而且装机能跑起来"）
- 改 zip 里任何条目（`res/*.xml` / `resources.arsc` / `classes*.dex`）都会让现有 v1/v2/v3 签名失效 ⇒ **必须整包重签**。旧签名不能保留，也不需要保留。
- **不需要担心的**：`libunity.so` / `libtprt.so` 以外的对象没有被"改字节就 SIGBUS"的记录；`libil2cpp.so` 明确**不在**被钉死的名单里（`_dd4-integrity.md` §1.1）；`assets/__tpinfo.*` 这 5 个 ACE 自身完整性清单文件已经被构建脚本**删掉**（`build_noroot_apk.py` 第 70–74 行常量），这正是"能跳过整段校验"的前提。
- **不能保证的**：**"改资源是否会触发 ACE 定点校验"没有一次实测记录**。已知校验点是 native/so 层，资源层无已知校验点 → 属"低风险但未实测"（见 §6）。

---

## 2. 三个方案对比

> 三个方案**都要重签**（第 4 列因此统一为"是"），差别在于**是否需要新工具能力**、是否碰 DEX、以及回归风险。

| | 方案甲：改布局 XML 加两个入口 | 方案乙：只改文案（+ 两处数值） | 方案丙：新增引导页 Activity |
|---|---|---|---|
| **要改的文件** | ① `res/Q9.xml`（= `layout/fragment_default_mobile_code_login`） | ① `resources.arsc` 字符串池 idx 1087 / 1095 / 975 / 1052 | ① `AndroidManifest.xml`（加 `<activity>`）② 新 `classes*.dex`（新 Activity 类）③ 新 `res/*.xml` 布局 ④ `resources.arsc`（新 layout 条目 + 新 string） |
| **改法** | 需要**AXML 树重写**（加 `LinearLayout`+2×`TextView`，还要为 Tab 造新 `@id`） | **纯原位字节替换**：UTF-8 池等长或更短即写，留 NUL 尾；条目偏移表不动 | 编译期产物，需要 DEX 生成器 |
| **要不要改 smali/java** | **不用**（只要点同一个 `@id/login`，或干脆纯展示） | **不用** | **要**（新类 = 新 DEX 代码） |
| **现有工具够不够** | ❌ **不够**。`build_noroot_apk.py:500-520` 的 `Axml` 类 `build()` 写的是 **空 resource-map**：`struct.pack('<HHI', 0x0180, 8, 8)`。`network-security-config` 能用（框架用 XmlPullParser 按**字符串**取属性），但 `LayoutInflater` 靠 `AttributeSet.getAttributeNameResource()` 查 **resource-map**，空 map ⇒ 所有 `android:*` 属性解析失败。**必须先补一个保真 AXML 重写器（解析→改树→带 41 项 resmap 重生成），约 200–300 行纯 Python** | ✅ **够**。只要 130 行左右的补丁脚本（本报告 §5 给了算好的偏移） | ❌ **差得最远**。没有 DEX 生成能力，要走 smali/baksmali 或塞第三方 dex |
| **是否需重签** | 是 | 是 | 是 |
| **是否影响资源校验** | 无已知校验点（同左） | 无已知校验点（同左） | 除资源外还动 DEX/Manifest，风险面更大 |
| **回归风险** | **中**：ConstraintLayout 加节点要新 id + 新约束；一旦约束写错表现为"控件消失/错位"，且**没有 aapt 做编译期校验**（本机无 aapt2），只能靠真机目测 | **低**：只换字符串字节 + 两个 u32。风险集中在"池条目长度算错导致后面字符串错位"（可回读校验） | **高**：Manifest 字符串池要插新类名（池重排是 AXML 里最脏的活）；ACE 对 Activity 注册/加载敏感 |
| **能否真正"两个入口"分行为** | 不能（点了还是走同一个 `@id/login` / `handleLoginLink`）；要分行为得再改 DEX | 不能（只有文案） | 能（新 Activity 可以先选类型再进登录），但代价最大 |
| **预计工作量** | **1–2 天**（其中 AXML 重写器是大头） | **0.5 天** | **3–5 天**（含 DEX 产能调研） |

### 2.1 方案甲的替代低配版（值得优先考虑）

`res/Q9.xml` 里有一个**官方预留的空插槽** `@id/ll_container_login`（`LinearLayout`，XML 里只放了 `@id/login` 和 GONE 掉的 `@id/login_helper`）。理论上往这里塞两个按钮最自然。

但要注意：**只要不动 DEX，两个按钮点了都只能做同一件事**。最省事的实现是：
- 两个 `TextView` 当"假 Tab"，点了只改 `et_phone` 的 hint / 高亮（需要 DEX 才能绑监听）；
- 或者干脆**不做可点击**，只当一行说明文字（"公益卡密 / 付费卡密 都填在这里"）——那就退化成方案乙，没必要改布局。

所以：**方案甲的收益只有"视觉上两个按钮"，成本和风险却比方案乙高一个量级。**

### 2.2 方案丙的廉价变体（值得知道，但不推荐）

不新增 Activity，改为**复用 `BackgroundAct` 容器 + 新增一个 Fragment**。仍需要新类（新 DEX），但省掉 Manifest 改动。工作量约 2–3 天，风险仍高于甲/乙。**只有在"必须先选类型再输卡密"的产品要求下才值得。**

---

## 3. 客户端要不要区分两种卡？——**不要**

### 3.1 服务端已经把分叉做完了

- 服务端 `/user/login` **只读 `OpenID` 一个字段**（`sdkcard_v2.py:758`：`key = str(j.get("OpenID") or "").strip()`），客户端把卡密放这儿。
- 卡的身份分叉在服务端：`kind == "public"` → `publisher_id() = md5("free:"+设备号)`，否则 `md5(卡密)`；`kind_of()` 缺省 `normal`（`sdkcard_v2.py:182-186`）。
  （注：`sdkcard_v2.py` 内部用的词是 `"normal"` / `"public"`，面板/`cards.json` 层叫 `paid` / `free`，两套叫法在服务端内部映射，客户端一概看不到。）
- 客户端能拿到的 `LoginEntity` / `UserDetailEntity` 里，**没有任何"卡类型"字段**供 UI 分支用。

### 3.2 客户端两条路发出的是同一个请求

`DefaultMobileLoginFragment.handleLoginLink(boolean)` 的反汇编（`_sdkui_tmp\out25.txt`）显示，最终调用只有一个：

```
handleLoginLink(Z)V
  phone = et_phone.getText().toString().trim()
  code  = et_phone_code.getText().toString().trim()
  if TextUtils.isEmpty(phone)                  → Toast(please_input_phone); return
  if !CommonUtil.isPhoneLegal(phone)           → Toast(illegal_phone);    return
  if TextUtils.isEmpty(code)                   → Toast(please_input_phone_code); return
  if code.length() != 6                        → Toast(illegal_phone_code); return
  if !is_privacy_agreement_select && !isBindLoginMode()
                                               → Toast(please_read__agree_agreement); return
  tipUtil.showProcessView(activity)
  linkReq = new LoginReq.LinkReq(){ Type="taptap", OpenID="", Token=taptapToken, Secret=taptapSecret }
  LoginManager.getInstance().loginWithLink("mobile", phone, code, "", linkReq, cb)
```

→ `LoginManager.loginWithLink` → `LoginAsyncChainKt.executeMobileLogin` → `mobileLoginSuspend` →
`SDKServiceApi.mobileLogin(header, LoginReq)`，其中 `LoginReq{ Type="mobile", OpenID=phone, Token=code, UserName="", Secret="" }`（`out12.txt:161-169`）。

**不管 UI 上画几个入口，落到服务端的永远是同一对 `(OpenID, Token)`。** 加"游客/卡密"两个按钮只会产生两段一模一样的代码。

### 3.3 客户端唯一相关的类型枚举跟卡无关

`LoginPageType` 的取值（`out19.txt:86-95` + 后续）：`NONE`、`QUICK_LOGIN`、`MOBILE_LOGIN`、`TAPTAP_LOGIN`、`ONEKEY_LOGIN`…—— 全是**登录通道**类型，没有"卡类型"维度。

### 3.4 结论

> **客户端只改文案就够。** 服务端 `cards.kind` 已经能自己判断 free/paid，客户端不需要、也不应该区分。
> 若一定要让用户有"我走的是公益/付费"的感知，正确做法是**把两类卡的差异写进文案**（"公益卡密与付费卡密都填在这里"），而不是造两个功能相同的入口。

**反过来说**：真正该改的不是"加两个入口"，而是**下面这三条卡口**（见 §5），因为它们现在会**直接拒绝**合法卡密：

| 卡口 | 位置 | 现状 | 后果 |
|---|---|---|---|
| 手机号正则 | `CommonUtil.isChinaPhoneLegal`，DEX string **idx=32792**，`^1\d{10}$` | 只认 `1`+10 位数字 | 16 位 alnum 卡密 → toast「手机号格式不正确」，**请求根本不发** |
| 输入长度 | `res/Q9.xml` `@id/et_phone` `maxLength` **0xc88** = `0x0B` | 只能输 11 字符 | 16 位卡密被截断成 11 位 |
| 键盘类型 | `res/Q9.xml` `@id/et_phone` `inputType` **0xc9c** = `0x03` | 数字键盘 | 字母打不进去 |
| 验证码位数 | `et_phone_code` `maxLength` **0xef0** = `6`；代码 `code.length()!=6` 拦截 | 必须**恰好 6 位** | "随便填"其实要求填满 6 位 |

---

## 4. 服务端 `Msg` / `Code` 到底显示在哪

### 4.1 完整调用链（逐跳有反汇编支撑）

```
SDKServiceApi.mobileLogin(header, LoginReq)                    Retrofit Call<BaseResposeEntity>
  └─ LoginAsyncChainKt.mobileLoginSuspend                      (out12.txt:171-183)
       └─ LoginAsyncChainKtKt.access$awaitResponse(call, timeout, transform, cont)
            ├─ 回调类 = LoginAsyncChainKtKt$awaitResponse$2$callback$1
            │    extends com.airi.official.core.http.net.HttpCallBack        ← out13.txt:7
            └─ HttpCallBack.onResponse(Call, Response)              acc=0x0001 ← out16.txt:66
                 ├─ hideLoadingUi()
                 ├─ if response.code() != 200      → handleErrorCode(101404, "unknown error")
                 └─ else if body.Code != 200       → handleErrorCode(body.Code, body.Msg)   ★
                     else                          → onResponse(body)
```

★ 这一行就是「服务端 `Msg` 进入客户端的唯一入口」。

```
HttpCallBack.handleErrorCode(int code, String msg)                 out16.txt:18-42
  ├─ MyLog.i("handleErrorCode_code: <code>, message: <msg>, isHandleErrorCode: true")   ← msg 只用来打日志
  ├─ ErrorCodeInfo info = ErrorCodeHandler.getCodeInfoByCode(code)                     ← 文案从这里来（本地表）
  └─ ErrorCodeHandler.showUiByErrorCodeInfo(gameActivity, getRequestUid(), info,
                                            cb -> onError(info))

ErrorCodeHandler.getCodeInfoByCode(int code)                      out7.txt:11-20
  └─ SdkManager.queryErrorMsg(ctx, String.valueOf(code))          out8.txt:3-18
       └─ DbManager.queryErrorMsg(ctx, String.valueOf(code))      out18.txt:23-66
            └─ SQLiteDatabase.query("error_msg", null, "code=?", [code], ...)
                 ├─ cursor["msg"]  → DataBean.setValue(...)
                 └─ cursor["type"] → DataBean.setType(...)

ErrorCodeHandler.showUiByErrorCodeInfo(...)                       out7.txt:80-94
  ├─ errorType = SdkManager.queryErrorType(ctx, code)   （同一张表的 type 列）
  └─ realShowUiByErrorCode(activity, uid, code, errorType, errorMsg, isLogout, isRemoveUserData, cb)

ErrorCodeHandler$realShowUiByErrorCode$1.invokeSuspend            out8.txt:122-246
  ├─ msg = errMsg
  ├─ if TextUtils.isEmpty(msg) → msg = getString(R.string.UN_KNOW_ERROR)
  │        R.string.UN_KNOW_ERROR = "未知错误，请联系客服。"                  out14.txt:13
  ├─ InitManager.getInstance().initAllErrorMsg()      ← 懒加载 /common/client-code（异步）
  ├─ if equals(errorType,"toast",ignoreCase)  → TipUtils.showToast(ctx, code + ":  " + msg)
  │                                              → handleLoginData(...) → return
  ├─ if equals(errorType,"none",  ignoreCase)  → handleLoginData(...) → return      （静默）
  └─ 其它（含 type 为空）                      → FragmentCommonUtils.goTipsActivityDialog(
                                                   activity, isHaveCloseBtn=false,
                                                   title = getString(R.string.tips) = "提示",
                                                   content = msg,
                                                   cancel = ""      → 取消按钮 GONE,
                                                   ok     = getString(R.string.ok_btn) = "确定",
                                                   okListener → handleLoginData(...))
```

### 4.2 弹窗到底长什么样、能塞多少字

走的是 **`TipsActivity`**（`out15.txt:50-51`：`getContentLayoutId()` → `R$layout;->activity_tips` → `res/o4.xml`）：

```xml
<!-- res/o4.xml = layout/activity_tips -->
<androidx.constraintlayout.widget.ConstraintLayout layout_gravity=center
    background=@drawable/login_bg_fragment
    layout_width=@dimen/dp312  layout_height=wrap_content
    maxHeight=@dimen/dp312  minHeight=@dimen/dp166>
  <TextView id=@id/tv_tips_title  textSize=sp16 singleLine=true  text="提示" />
  <ImageView id=@id/iv_close .../>
  <View id=@id/divide_line background=@color/c_eaeaea height=dp1 />
  <com.airi.common.widget.JustifyTextView
      id=@id/tv_tips_content
      textSize=@dimen/sp14  textColor=@color/c_6a6a6a  ellipsize=3   <!-- END -->
      paddingLeft=dp24 paddingRight=dp24
      layout_width=match_parent  layout_height=wrap_content
      maxLines=4 />                                                   <!-- ★ 4 行上限 -->
  <Button id=@id/btn_tips_cancel ... />
  <Button id=@id/btn_tips_ok     ... />
</androidx.constraintlayout.widget.ConstraintLayout>
```

`TipsActivity.initViews` 全文（`out15.txt:89-174`）**没有改 `maxLines`**，只做：`iv_close` 按 `isHaveCloseBtn` 设 0/4；`cancel` 空 → `setVisibility(8)`；`ok` 空 → `setVisibility(8)`；`content` 空 → `INVISIBLE`，否则 `setText`。⇒ **`maxLines=4` 是硬上限。**

**容量估算（决定"封号时间…请联系客服"能不能放下）**

| 项 | 值 |
|---|---|
| 卡片宽 | `dp312`（`DialogUtils` 同款也是 `dp300`） |
| 内容可用宽 | 312 − 24 − 24 = **264dp** |
| 字号 | `sp14`（中文 ≈ 14sp 宽）→ **约 13–16 字/行** |
| 行数 | **4** |
| ⇒ 上限 | **约 52–64 个汉字**（含标点），超出以 `…` 截断 |

✅ 实测例证：`work\ba\noroot\_err1.png` 是一张真机截图，SDK 用同一套样式（标题 **提示**）显示

```
404: 很抱歉，初始化资源失败，请重试。如果仍然无法解决，请您重启手机，再打开游戏试试。
```

—— 共 48 个字符，渲染成 **3 行**，未截断。**与上面的 4 行上限完全吻合。**

（`_err1.png` 那张的具体容器是 `layout/fragment_init_failed` → `res/Ou.xml`，不是 `activity_tips`，但它同样用 `@id/tv_tips_content` + `maxLines=4`，所以是同一个文字容量规格。）

**所以"封号时间…请联系客服"这类文案能放，但要压到 ~50 字以内。** 例如：

```
账号已被封禁至 2026-11-25 23:59。
如有疑问请联系客服。
```

（27 字，约 2 行，**安全**）

```
您的账号因违规已被封禁，
解封时间：2026-11-25 23:59，
如有疑问请联系客服 QQ 123456789
```

（41 字，约 3 行，**安全**）

### 4.3 toast 分支

`errorType == "toast"` 时文案 = **`"<code>:  " + msg`**（注意冒号后**两个空格**，`const-string v2, ":  "`，`out8.txt:159`）。
容器是 `res/RT.xml`（`layout/view_toast`）：`TextView` `maxWidth=@dimen/dp300`、**`singleLine=false`**（可多行、无 `maxLines` 上限，比弹窗宽松），但 `ToastUtils` 会自动消失（约 3.5 s），且**前面永远带着 `code: ` 前缀**。

### 4.4 `Msg` 本身去哪了

`LoginManager.loginFailedCallBack(int code, String msg)`（`out3.txt:89-109`）：

```
MyLog.e("loginFailedCallBack_code: " + code + " , msg: " + msg)     ← 只进 logcat
SdkManager.getInstance().setAutoLogin(false)
map = ToUnityResult.buildLoginResult()
map.put("R_MSG",  msg)          ← 服务端 Msg 原样交给 Unity
map.put("R_CODE", code)         ← 失败时 R_CODE = 服务端 Code（成功时是 2）
OfficialSDK.getCallBack().onCallBack(map)
```

**这里不弹任何 UI、不 toast、不关登录框。**

再看登录失败后客户端**唯一**接触 `ResponseMod` 的地方 —— `DefaultMobileLoginFragment$6`（`handleLoginLink` 传进去的 `FCallBack`，`out28.txt`）：

```
DefaultMobileLoginFragment$6.onFail(ResponseMod)V
    access$300().dismissProcessView(getActivity())     ← 只关 loading 圈
    （结束，没有 showToast / 没有 dialog / 没有用 responseMod.msg）
DefaultMobileLoginFragment$6.onSuccess(ResponseMod)V
    access$200().dismissProcessView(getActivity())
```

⇒ **全链路没有任何一处把服务端 `Msg` 显示给用户。** 服务端 `Msg` 对"弹窗"这条链是**完全无效**的。想改弹窗文案只有两条路：
1. 让客户端从本地 `error_msg` 表读到（**§4.5，零 APK 改动**）
2. 改 APK（把 `handleErrorCode` 改成用 `msg`，或直接在 `loginFailedCallBack` 里加一句 `DialogUtils.showDialog(...)`）

### 4.5 ★ 零 APK 改动的文案控制通道：`/common/client-code`

```
InitManager.initAllErrorMsg()                                   out9.txt:16-29
  └─ NetClientManager.getSDKServiceApi().getClientCode(headerAuth, new NoBodyReq())
       └─ 回调 InitManager$4.onResponse(Call, Response)          out17.txt:31-45
            if response.code()==200 && body.Code==200:
               data = ((ErrorCodeEntity) body.Data).getData()   → ArrayList<DataBean>
               DbManager.replaceSdkErrorMsg(gameActivity, data)  → 线程池里整表替换
```

数据形状（DEX 字段名，`out17.txt:19-24`）：

```jsonc
// POST/GET /common/client-code
{
  "Code": 200,
  "Msg": "success",
  "Data": {                      // ← BaseResposeEntity.Data  (Object)
    "CodeList": [                // ← ErrorCodeEntity 的字段名就叫 CodeList
      { "Code": "101001", "Type": "toast", "Value": "公益卡密已过期，请更换" },
      { "Code": "101002", "Type": "none",  "Value": "" },
      { "Code": "200001", "Type": "dialog","Value": "账号已被封禁至 2026-11-25 23:59，请联系客服" }
    ]
  }
}
```

建表 SQL（**表结构已证实**，`DbManagerHelper.onCreate`，`out17.txt:52`）：

```sql
CREATE TABLE IF NOT EXISTS error_msg (
  _id  INTEGER PRIMARY KEY AUTOINCREMENT,
  code VARCHAR(255) UNIQUE,
  msg  TEXT,
  type TEXT
);
```

`Type` 取值语义（大小写不敏感）：`"toast"` → toast；`"none"` → 静默；**其它（含空字符串 / `"dialog"` / 任意值）→ 弹窗**。

**注意两个坑**：
1. **`initAllErrorMsg()` 只在"第一次要显示错误 UI"时才被调用**，而 `getCodeInfoByCode` 在那之前就读了表。
   ⇒ **开机后的第一次 `Code≠200` 一定显示「未知错误，请联系客服。」**；点掉退出、再登一次（第二次）才会用上我们给的文案。（`InitManager.init` 只调 `getSetting(...)`，**不调** `initAllErrorMsg`，见 `out18.txt:90-113`。）
2. **`sdkcard_v2.py` 目前根本没有 `/common/client-code` 的 handler** —— `Select-String` 只命中 `:699 if path == "/common/config"` 和 `:735 if path == "/common/geo-ip"`。所以 `error_msg` 表永远是空的 ⇒ **现在所有 `Code≠200` 都弹「提示 / 未知错误，请联系客服。/ 确定」**。

### 4.6 `/user/quick-login` 失败时会不会回到登录框

`/user/quick-login` 走 `sessionLogin` → `awaitUnit`（`out12.txt:216-219`），回调同样是 `HttpCallBack` 子类 ⇒ **同上：先弹 ErrorCodeHandler 的弹窗，再 onError**。

然后 `LoginManager$1.onFail` → `dismissProcessView` → `loginFailedCallBack(code, msg)` → **不 finish、不 closeAllFragment**。

**但"点确定"会关掉登录界面**：弹窗 OK 回调 → `ErrorCodeHandler.handleLoginData(...)`（`out7.txt:21-51`）：

```
SdkManager.switchAccount(errorCode, errorMsg)      // 内部：closeAllFragment() + setAutoLogin(false) + 给 Unity R_MSG/R_CODE
DataManager.removeLoginedUserByUid(ctx, uid)        // 视 isRemoveUserData
callback.onHandle(info)                            // → 协程失败 → onFail → loginFailedCallBack
```

`SdkManager.switchAccount`（`out8.txt:35-76`）里明确有 `BackgroundAct$Holder.closeAllFragment()`。

真机 logcat 也对得上（`work\ba\noroot\_logcat_phone2c_20261118.log`）：

```
11-18 00:14:57.580  wm_on_create_called: [80370964, com.airi.official.core.base.BackgroundAct, performCreate, 11]
11-18 00:14:58.924  wm_finish_activity:  [0, 80370964, 4096, ...BackgroundAct, app-request]      ← SDK 界面被自己 finish
11-18 00:14:58.988  wm_create_activity:  [... BackgroundAct ...]                                  ← 1.06 s 后又起一个（用户重试）
11-18 00:14:59.476  wm_finish_activity:  [... BackgroundAct, app-request]
```

⇒ **`quick-login` 失败 = 弹窗 → 点确定 → 清空并退出 SDK 界面 → 回标题 → 用户重新点登录**，**不是**"原地回到登录框"。
如果希望"点确定后回到卡密输入框"，必须在 DEX 里把 OK 回调改成 `FragmentCommonUtils.goDefaultLogin(...)`（约 1 个方法的 smali 改动）。

### 4.7 顺带：SDK 自己其实在打日志，只是以前的抓取没带上

```
MyLog.<clinit>:  isShowLog = true              ← const/4 v0, 1 ; sput-boolean MyLog->isShowLog
                 TAG = "AiriSDK"               ← const-string v0, 'AiriSDK' ; sput-object MyLog->TAG
```

`work\ba\noroot\*.log` 共 20 个文件，**`AiriSDK` 命中 0 次** —— 说明当初是 `logcat -s <别的tag>` 抓的，不是 SDK 不打日志。
⇒ 后续排障请用：`adb logcat -s AiriSDK`（能直接看到 `handleErrorCode_code: …`、`realShowUiByErrorCode …`、`loginFailedCallBack_code: …`、`executeMobileLogin: Step N`）。

### 4.8 ⚠️ 对正在做的「封禁文案」工作的直接影响

我核对时发现 `work\ba\server\deploy\_build_banexp\` 正在按下面的方式下发文案（`sdkcard.py:91-92,144,163,250`、`ban_message.py:41-42`）：

```python
DEVICE_BAN_CODE = 400101
DEVICE_BAN_MSG  = '设备已被限制'
BANEXP_CODE     = DEVICE_BAN_CODE
MSG_PERMANENT   = '封禁，请联系客服'
MSG_TIMED_TMPL  = '封号时间 %s 至 %s，请联系客服'
...
return {'Code': BANEXP_CODE, 'Msg': msg, 'Data': {}}      # ← 文案放在 Msg 里
```

**按本节的链路，这段文案玩家一个字都看不到**：`Code=400101 ≠ 200` → `handleErrorCode(400101, <封禁文案>)` → 文案只进 logcat，弹窗文案来自空的 `error_msg` 表 → 玩家实际看到的是

```
提示
未知错误，请联系客服。
[确定]
```

这对"封号时间"来说是**错的提示**。

**好消息（容量够）**：`封号时间 2026-11-18 20:00 至 2026-11-20 20:00，请联系客服` 共 46 字符，其中 32 个是 ASCII（数字/`-`/`:`/空格，只有汉字约一半宽）⇒ 折算约 26 个汉字宽 ⇒ 渲染 **2–3 行**，**不会**被 `maxLines=4` 截断。

**怎么让它真的显示出来（按成本排序）**

| 方案 | 做法 | 代价 | 首次是否生效 |
|---|---|---|---|
| **B1 零 APK** | 服务端实现 `/common/client-code`，把 `{"Code":"400101","Type":"dialog","Value":"<封禁文案>"}` 塞进 `CodeList` | 服务端 ~30 行 | ❌ **第一次报错仍是"未知错误"**（`getCodeInfoByCode` 在 `initAllErrorMsg()` 之前读表）；第二次起才对 |
| **B2 零 APK + 预热** | 先让某个**无害**请求返回一个"表里不存在 → `Type` 也为空 → 会弹窗"的错……**不可行**，因为首次弹的就是"未知错误"窗 | — | — |
| **B3 改 APK（最小）** | 把 `HttpCallBack.handleErrorCode` 改成用**入参 `msg`** 而不是 `getCodeInfoByCode(code)`，即 `new ErrorCodeInfo(code, msg, false, false)` | 需要 smali 汇编（插入指令，不是等长字节补丁）；约 1 人日 | ✅ 首次即生效，且以后所有服务端文案都能直接显示 |
| **B4 改 APK（更小）** | 只在 `DefaultMobileLoginFragment$6.onFail` 里加一句 `TipUtils.showToast(ctx, responseMod.msg)` | 同样是 smali 插入；约 0.5 人日 | ✅ 首次即生效（但是 **toast**，3.5 s 就消失，且没有"确定"按钮） |

> **建议**：封禁是"必须让玩家看清解封时间"的场景，**B1 的"第二次才正确"不可接受**。
> 要么走 **B3**（一次性把"服务端文案直达前端"的能力打通，之后所有业务错误都能自定义文案），
> 要么走 **B4** 快速止血（toast 里带完整封禁时间），两者都只需改一个方法。
> 若坚持零 APK，那就必须接受"玩家第一次看到的是未知错误、第二次才看到封号时间"。

---

## 5. 推荐方案 + 最小改动路径

### 5.1 推荐

**推荐：方案乙（改文案 + 三处数值/正则补丁），全部为"原位等长或更短替换"，不引入任何新工具链。**

理由：
1. 改的全部是**定长字节**（字符串池条目、u32、9 字节正则），**文件大小不变、偏移表不变**，风险可控且可回读校验；
2. 不需要补 AXML 重写器（方案甲的最大成本项）；
3. 不碰 DEX 结构，只换一个 `const-string` 的字面量（9→9 字节）；
4. 满足"游客/卡密"的**感知**需求（一个框 + 明确文案），符合 §3 的结论；
5. 出包用现成 `build_noroot_apk.py --asset-replace`，签名/对齐/v1v2v3 全部现成。

**如果产品坚持"两个可见按钮"**：在方案乙之上再补一个 AXML 保真重写器（只针对 `res/Q9.xml`），即方案甲；**但那两个按钮仍然只能做同一件事**（除非再改 DEX）。建议把这条留到第二期。

### 5.2 已算好的补丁清单（可直接照做）

> ⚠️ 下面是**目标状态**，本轮**没有执行任何写入**（只读约束）。所有偏移都是相对**该文件自身**的偏移。

#### 补丁 A — `res/Q9.xml`（7,292 B，`layout/fragment_default_mobile_code_login`）

| 目标 | 文件偏移 | 当前值 | 建议值 | 说明 |
|---|---|---|---|---|
| `@id/et_phone` 的 `maxLength` | **0xc88**（u32 LE） | `0x0000000B` (11) | `0x00000040` (64) | 放开长度，匹配 `gen_card_key` 的 `clamp(len,4,64)` |
| `@id/et_phone` 的 `inputType` | **0xc9c**（u32 LE） | `0x00000003` | `0x00000001` | 数字键盘 → 文本键盘（**需真机确认，见 §6**） |
| `@id/et_phone_code` 的 `maxLength` | 0xef0 | `0x00000006` | 保持不变 | 代码里 `code.length()!=6` 也要 6 位，一起改才有效 |
| `@id/et_phone_code` 的 `inputType` | 0xf04 | `0x00000002` | 保持不变 |  |

（`@id/et_phone` 的 `hint` 属性数据在 0xc60，指向 `@string` `0x7f0f0074` = 池 idx 1087；`id` 数据在 0xc10 = `0x7f080108`。 Attribute 记录布局：`ns(4)|name(4)|rawValue(4)|Res_value{size u16, res0 u8, dataType u8, data u32@+16}`。）

#### 补丁 B — `resources.arsc`（1,156,308 B）全局字符串池，UTF-8，`flags=0x100`

池结构：`ResStringPool_header{type u16, hdrSize u16(=28), size u32, count u32(=6726), stylesCount u32, flags u32(=0x100), stringsStart u32, stylesStart u32}`，紧跟 `count` 个 u32 偏移（相对 `pool_off+stringsStart`）。
每条 UTF-8 条目：`u8len(uleb128) | u16len(uleb128) | bytes | 0x00`。

| 资源 | 池 idx | 当前偏移 | 现值 | 建议值（长度必须 ≤） | 字节变化 |
|---|---|---|---|---|---|
| `hint_phone_number` = `please_input_phone` | **1087** | `0x0000c4c2` | `请输入手机号`（18 B） | `请输入卡密`（15 B）或 `卡密`（6 B） | ≤ 18 |
| `hint_phone_code` = `please_input_phone_code` | **1095** | `0x0000c579` | `请输入验证码`（18 B） | `验证码任填`（15 B）或 `6位任意`（10 B） | ≤ 18 |
| `get_phone_code` | 975 | — | `发送`（6 B） | `免填`（6 B） | ≤ 6 |
| `login` | 1052 | `0x0000bf60` | `登录`（6 B） | 保持 | — |
| `illegal_phone` | 待取 | — | `手机号格式不正确`（24 B） | `卡密格式不正确`（21 B） | ≤ 24 |
| `illegal_phone_code` | 待取 | — | `验证码格式不正确`（24 B） | `验证码需6位`（16 B） | ≤ 24 |

**改法**：`u8len`、`u16len` 各改写为新长度，正文改写，紧接一个 `0x00`；**剩余字节原样留着当日志空洞即可**（池偏移表指向条目起点，多余字节不会破坏解析）。
**必须校验**：文件总长不变、`count/stringsStart` 不变、改完用本报告的 ARSC 解析器回读全部 6726 条，确认除目标项外**逐条与改前一致**。

> 因为 1087 / 1095 被 **hint 和本地校验 toast 共用**，改一次两处同时生效，不会出现文案不一致。

#### 补丁 C — `classes.dex` 的校验正则（让它接受字母卡密）

```
strings[32792]  dataOff=0x70eb59  ulebLen=9  payload@0x70eb5a  raw = 5e 31 5c 64 7b 31 30 7d 24
                                          = "^1\d{10}$"   (9 bytes)
建议替换 = "^.{1,64}$"                                  (9 bytes)  ← 等长！
```

- **等长** ⇒ 只需把 `0x70eb5a..0x70eb62` 这 9 个字节换掉，**ulebLen、字符串池、方法体全部不动**。
- 收尾必须重算 DEX 头（否则某些加载路径会判 dex 损坏）：
  - `adler32` 校验和 → 写回文件偏移 **0x08**（覆盖 `bytes[12:]`）
  - `SHA-1` 签名 → 写回文件偏移 **0x0C**（覆盖 `bytes[32:]`）
- 若不想动正则：退一步只改 `res/Q9.xml` 的 `maxLength`/`inputType`，让用户**只能输 11 位数字**卡密（`^1\d{10}$` 天然满足），并把发卡规则限定为"1 开头的 11 位数字"。**这是最省事、零 DEX 改动的路线，强烈建议作为兜底。**

#### 补丁 D — 服务端（**不需要改 APK**）

`work\ba\sdk\sdkcard_v2.py` 增加 `/common/client-code`（GET + POST 都实现，见 §6），返回 §4.5 的 `CodeList`。
配合把 `/user/login` 的失败码改成我们自己的码（例如封禁 `200001` / 公益卡过期 `101001`），就能自定义弹窗文案与形态（弹窗/ toast / 静默）。

### 5.3 分步执行（每步都能单独验证，出问题只回退这一步）

| 步 | 动作 | 验证方法（不装真机也能做前 3 步） |
|---|---|---|
| **S0** | 备份基线：记 `BA_noroot_prod_20261118_v1.apk` 的 sha256；确认 `ba_private.keystore` 可用 | `Get-FileHash`；确认 keystore 存在且不被改动 |
| **S1** | 只做 **补丁 B**（arsc 文案），产出 `resources.arsc.new` | 用 `_sdkui_tmp\t_arsc.py` 的解析器回读 6726 条，diff 应"只有目标项变"；文件长度必须仍为 1,156,308 |
| **S2** | 只做 **补丁 A**（Q9.xml 两个 u32），产出 `res_Q9.xml.new` | 回读该 AXML，确认 `maxLength=64`、`inputType=1`，且**其余属性一字未变**、总长仍 7,292 |
| **S3** | 出包（不带 DEX）：`python build_noroot_apk.py --src <源> --out <新> --asset-replace resources.arsc=<新> --asset-replace res/Q9.xml=<新> --sdk-url <现网> --keystore ba_private.keystore --storepass baserver --alias ba` | 脚本自带 `verify_v1` / `verify` / `gmconfig_selfcheck` 必须全绿；退出码 0 |
| **S4** | 装真机，**只验 UI**：打开登录框，确认 hint 变成"请输入卡密"、能输入 16 位字母+数字（补丁 A 生效） | `adb logcat -s AiriSDK`；手输 16 位 alnum → 看是否还弹 toast「手机号格式不正确」 |
| **S5** | 若 S4 仍被正则拦（**预期会被拦**），再加 **补丁 C**（dex 正则 9 字节 + 重算头），重新出包 | `adb logcat -s AiriSDK \| findstr handleErrorCode`；提交后应能看到 `mobileLoginSuspend: rawType=…`，说明请求已发出 |
| **S6** | 服务端加 `/common/client-code` + 自定义失败码 | 第 1 次报错仍是"未知错误"（预期，见 §4.5 坑 1）；**第 2 次**应显示我们给的文案 |
| **S7** | （可选，二期）补 AXML 保真重写器 → 方案甲，在 `@id/ll_container_login` 里加两个 TextView | 真机目测布局不错位 |

**关键提醒**：S3 出的是 2.1 GB 包，`build_noroot_apk.py` 是纯 Python 的 `zipfile` 逐条重压缩，**单次出包会比较慢**（该脚本已有 `--align-mode raw` 与 1 MB 分块摘要，别中断）。

### 5.4 工作量估计

| 子项 | 人日 |
|---|---|
| S1 + S2 + S3 脚本（约 130–180 行 Python，含回读自检） | 0.5 |
| S4 真机回归（含两次出包等待） | 0.3 |
| S5 dex 补丁（同类脚本，+30 行） | 0.2 |
| S6 服务端 `/common/client-code` + 自定义错误码 | 0.5 |
| S7（可选）AXML 保真重写器 + 布局改造 | 1.5–2 |
| **合计（不含 S7）** | **≈ 1.5 人日** |
| **合计（含 S7）** | **≈ 3.5 人日** |

---

## 6. 我不确定的地方（直说）
1. **`inputType=0x3` 改成 `0x1` 后的键盘行为没验**。`0x3` 不是标准的 `TYPE_CLASS_*` 值（标准是 `TEXT=1` / `NUMBER=2`），`TextView.setInputType` 对未知 class 的处理我没在真机确认。稳妥做法：先只改 `maxLength`，看字母能不能输（很多输入法在 `TYPE_CLASS_NUMBER` 下仍可通过粘贴输入，但键盘上没有字母键）。**需要真机验证 + 具体办法：`adb shell ime list -s` 配合截图，或直接粘贴测试。**
2. **`ExtendEditText` 是否在代码里另加 `LengthFilter` 没查**。它是 `com.airi.official.core.widget.ExtendEditText`（自定义控件），我只确认了 XML 上的 `maxLength`，没反汇编它自己的 `init`。若它内部硬编码了 11，则补丁 A 无效，必须改类（= 改 DEX）。
3. **改资源到底会不会被 ACE 点名，没有实测**。`_dd4-integrity.md` 结论是"校验是**定点**的，不是整包签名"，已知被钉的是 `libunity.so` 与 `libtprt.so`；资源层没记录。但"历史上没人改过 `res/*.xml` 后跑通"这一点我**无法证伪**。**具体验证办法：S3 出包后先在真机跑一次冷启动到取昵称界面（约 45 s，参照 E38 的实测），确认不 SIGBUS。**
4. **`/common/client-code` 的 HTTP 方法解不出来**。Retrofit 注解（`@GET`/`@POST` + 路径）在 DEX 的 `annotations_directory` 里，我没写 encoded_value 解析器。**建议服务端 GET/POST 都实现**（只多 3 行），或者用 `adb logcat -s AiriSDK` 看 `InitManager_initAllErrorMsg` 之后是 200 还是 404 来定。
5. **`DbManager$1` 的 replace 语义只看到"走线程池"**，具体是 `DELETE FROM error_msg` + 逐条 `insert` 还是 `REPLACE INTO`，没逐条读完。若它是"先清空再插"，那么服务端返回空 `CodeList` 会把表清空——别在测试时返回空数组。
6. **"第一次报错必显示未知错误"是从反汇编顺序推出来的**（`getCodeInfoByCode` 在 `initAllErrorMsg()` 之前），**没有真机实测**。验证办法：S6 之后，冷启动第一次故意输错卡，看弹窗文案是"未知错误"还是自定义。
7. **`LoginPageType` 的完整 6 个取值只读到 4 个**（`NONE / QUICK_LOGIN / MOBILE_LOGIN / TAPTAP_LOGIN`，另有 `ONEKEY_LOGIN` 在 `onClick` 里出现）。剩下 1 个没读全，但不影响本报告结论。
8. **`R.string.UN_KNOW_ERROR` 等几条字符串的池 idx 没逐一取**（只取了 5 条关键项）。若 S1 要改 `illegal_phone` / `illegal_phone_code`，需先跑一遍 `_sdkui_tmp\run22.py` 把 idx 补上。
9. **`_err1.png` 那张真机截图的具体来源**（哪次构建、哪台机）没核，我只把它当"SDK 弹窗文字容量的视觉参照"，没有当"改资源后仍能跑"的证据。

---

## 附录 A：本轮自建工具与产物

全部在 `work\ba\plan\20261118\_sdkui_tmp\`（**新目录，未触碰任何既有文件**）：

| 文件 | 用途 |
|---|---|
| `classes.dex` / `classes2.dex` | 从 APK 里只读提取，供反汇编 |
| `dexlib.py` | 自写 DEX 解析 + 反汇编器（class_data / code_item / 指令长度表 / const-string / invoke / sget 解析） |
| `t_arsc.py` `t_arsc4.py` `t_str.py` | ARSC 解析（package / typeSpec / type / config / 全局池 / 值解析 / rid→名称→文件路径） |
| `t_axml.py` | AXML 解码器（含 resource-map，能把 `@string/xxx` 反解成原文） |
| `run*.py` + `out1..out27.txt` | 各步 dump 结果（类清单 / 方法列表 / 反汇编 / 布局树 / 字符串表 / 偏移） |

## 附录 B：本报告引用的关键反汇编原文位置

| 结论 | dump 文件 |
|---|---|
| `BackgroundAct` / 两个 Fragment 的 layout id | `out1.txt:20,47,105` |
| `loginFailedCallBack` / `loginSuccessCallBack` | `out3.txt:89-109`, `out3.txt:111-179` |
| `layout/*` 全表 + `act_background`/`activity_tips` 等 | `out14.txt`（另见正文 §1.4） |
| `TipsActivity` 全套 + `goTipsActivityDialog` | `out15.txt` |
| `HttpCallBack` 五个方法（含 `onResponse(Call,Response)`） | `out16.txt` |
| `ErrorCodeEntity` 字段 + `DbManagerHelper.onCreate` 建表 SQL | `out17.txt:19-24, 52` |
| `ErrorCodeHandler` 全套 + `realShowUiByErrorCode$1` 分支 | `out7.txt` + `out8.txt:122-246` |
| `SdkManager.queryErrorMsg/queryErrorType/switchAccount` | `out8.txt:3-76` |
| `LoginAsyncChainKt` 七步链 + `awaitResponse` 回调 | `out12.txt` + `out13.txt:2-25` |
| `DefaultMobileLoginFragment.handleLoginLink` 四条校验 | `out25.txt` |
| `isChinaPhoneLegal` 正则字面量 | `out26.txt` |
| DEX 字符串 `^1\d{10}$` 精确偏移 | `out27.txt` |
| ARSC UTF-8 池 + 目标字符串偏移 | `out21.txt` |
| `hint_phone_number` 与 `please_input_phone` 共用池 index | `out22.txt` |
| `res/Q9.xml` 属性数据偏移（maxLength/inputType） | `out23.txt` |
| Manifest `versionCode=73` | `out24.txt` |
