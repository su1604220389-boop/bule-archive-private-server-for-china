# SELFTEST_v4 — `v4_login.apk`（纯布局版：去掉验证码 / 手机号→卡密 / 真美化）

> 生成时间：2026-11-18 20:15 (CST)　|　生成脚本：`work/ba/apk_patch/v4/build_report_v4.py`
> 所有"原始输出"段落都是从证据文件里**原样内联**的，没有手工誊抄。

## 0. 结论

| # | 自检项 | 要求 | 实测 | 结果 |
|---|---|---|---|---|
| 1 | `resources.arsc` sha256 | `cd8943ae…eecb86` | `cd8943ae…eecb86` | ✅ |
| 2 | `classes.dex` 逐字节 | == v2 基线 == 原始包 | `56b3a73b…c27651`（三方相同） | ✅ |
| 3 | `classes2.dex` / `AndroidManifest.xml` | 不变 | 三方相同 | ✅ |
| 4 | `aapt dump badging` vs v2 | diff = 0 行 | 176 行对 176 行，diff **0** | ✅ |
| 5 | zip 条目 diff vs v2 | 只有 `res/Q9.xml` + `META-INF/*` | 4 条：`res/Q9.xml` + 3 个 `META-INF/*` | ✅ |
| 6 | 新条目 / 丢失条目 | 无 | 无 | ✅ |
| 7 | `apksigner verify` | 通过 | v2/v3 scheme 全过，exit 0 | ✅ |
| 8 | 签名证书 | 与原包同一张 | `94FA997B…99EBC` | ✅ |
| 9 | 包内 `res/Q9.xml` | == 喂给打包器的 AXML | sha256 完全一致 | ✅ |

**全部通过。** 唯一无法验证的是真机观感（本机 `adb devices` 为空）——见第 13 节与 `preview_v4.png`。

## 1. 产物

| 项 | 值 |
|---|---|
| 路径 | `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\out\v4_login.apk` |
| 字节数 | **2,127,972,093** |
| sha256 | **`6490fcfc772f4dc6dd1773e7999a491775a646b08675591204b18212ee94eddb`** |
| 基线 v2 sha256 | `562d528a951eaeb15ae3165ece4a7ceb91849bb21ef54c895c6f217f9a676d64` |
| 包内 `res/Q9.xml` | 8,208 B，sha256 `f614865a97955515e41e2248af0b6004f7eefdea3d2fbd0897285d226cb189b3` |
| 源 AXML（喂给打包器的那份） | `work\ba\apk_patch\v4\res_Q9_v4.axml`，同 sha256 |
| 改动规模 | 解码 XML 8,915 B → 9,777 B；AXML 7,292 B(原始) / 8,284 B(v2) → **8,208 B** |

## 2. `resources.arsc` —— 逐字节不变（原始输出）

```
## 1) resources.arsc —— 必须与原始包逐字节相同

| entry | v1 | v2 | v4 |
|---|---|---|---|
| `resources.arsc` | `cd8943ae979fd434…` (1156308 B) | `cd8943ae979fd434…` (1156308 B) | `cd8943ae979fd434…` (1156308 B) |
| `classes.dex` | `56b3a73b3039db99…` (9327708 B) | `56b3a73b3039db99…` (9327708 B) | `56b3a73b3039db99…` (9327708 B) |
| `classes2.dex` | `dca6f88a614fd766…` (10158904 B) | `dca6f88a614fd766…` (10158904 B) | `dca6f88a614fd766…` (10158904 B) |
| `AndroidManifest.xml` | `9a07ec83802b9b6f…` (50552 B) | `9a07ec83802b9b6f…` (50552 B) | `9a07ec83802b9b6f…` (50552 B) |
| `res/Q9.xml` | `cc12543bbb5b977e…` (7292 B) | `8907d9b258c918c0…` (8284 B) | `f614865a97955515…` (8208 B) |

* v4 `resources.arsc` sha256 = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`
* 规范常量                    = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`
* => **一致 ✅**
```


## 3. `classes.dex` / `classes2.dex` / `AndroidManifest.xml` —— 逐字节不变（原始输出）

```
## 2) classes.dex / classes2.dex / AndroidManifest.xml —— 逐字节不变

* `classes.dex`  sha256 = `56b3a73b3039db99ade67faf42e471c8de4dcd7127ce9bef49d9f4d473c27651`  (9327708 B)
  * v1 == v2 == v4 : **True**
* `classes2.dex`  sha256 = `dca6f88a614fd7666842eed9d11d3f6bf9c842e381b80a63a330cbb78c93a7b4`  (10158904 B)
  * v1 == v2 == v4 : **True**
* `AndroidManifest.xml`  sha256 = `9a07ec83802b9b6fc08582b9429d9649775fe8627c35be419a3b851f1ffaca11`  (50552 B)
  * v1 == v2 == v4 : **True**

* （对照）原始 `classes.dex` 前 16 位应为 `56b3a73b3039db99`：一致 ✅
```


> `classes.dex` sha256 = `56b3a73b3039db99ade67faf42e471c8de4dcd7127ce9bef49d9f4d473c27651`，在 **v1（原始重签包）/ v2（基线）/ v4（本次）** 三个包里完全相同。
> 也就是说本次改动 **一个 dex 字节都没碰**（红线：改 6 字节就 0.5 秒闪退）。

## 4. `aapt dump badging` —— 与 v2 基线 diff = 0 行（原始输出）

````
## 3) `aapt dump badging` —— 与 v2 基线 diff

* v2 行数 = 176, v4 行数 = 176
* **diff 行数 = 0**

* v4 badging 前 6 行：

```
package: name='com.RoamingStar.BlueArchive' versionCode='73' versionName='3.0.2' platformBuildVersionName='13' platformBuildVersionCode='33' compileSdkVersion='33' compileSdkVersionCodename='13'
install-location:'auto'
sdkVersion:'24'
targetSdkVersion:'33'
uses-permission: name='android.permission.INTERNET'
uses-permission: name='android.permission.VIBRATE'
```
````


## 5. zip 条目 diff（v4 vs v2，原始输出）

```
## 4) zip 条目 diff（v4 vs v2，按 name + size + crc32 + method）

* 条目数：v2 = 41307, v4 = 41307
* **变化条目 (4)**：

| entry | v2 size | v4 size | v2 crc32 | v4 crc32 | v2 method | v4 method |
|---|---|---|---|---|---|---|
| `META-INF/CERT.RSA` | 1208 | 1208 | 0e26fe6b | 1695b469 | 0 | 0 |
| `META-INF/CERT.SF` | 156 | 156 | d156a581 | 0f1f824b | 0 | 0 |
| `META-INF/MANIFEST.MF` | 5151246 | 5151246 | c9adf0b7 | 66fc9768 | 0 | 0 |
| `res/Q9.xml` | 8284 | 8208 | e90efac7 | 05500e69 | 0 | 0 |

* 只在 v2：无
* 只在 v4：无

* 允许集合 = {`res/Q9.xml`} ∪ `META-INF/*`
* 超出允许集合的条目：**无**

* META-INF 变化条目明细：

  * `META-INF/CERT.RSA`  1208 B -> 1208 B
  * `META-INF/CERT.SF`  156 B -> 156 B
  * `META-INF/MANIFEST.MF`  5151246 B -> 5151246 B

* `res/Q9.xml` in package : 8208 B  sha256=`f614865a97955515e41e2248af0b6004f7eefdea3d2fbd0897285d226cb189b3`
* fed AXML file           : 8208 B  sha256=`f614865a97955515e41e2248af0b6004f7eefdea3d2fbd0897285d226cb189b3`
* 一致：**True**
```


## 6. `apksigner verify --print-certs`（原始输出）

````
## 5) `apksigner verify --print-certs`

### BA_noroot_prod_20261118_v1.apk  -> exit 0

```
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v4 scheme (APK Signature Scheme v4): false
Number of signers: 1
Signer #1 certificate DN: CN=ba, OU=Private, O=BA, C=CN
Signer #1 certificate SHA-256 digest: 94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc
Signer #1 certificate SHA-1 digest: b584e21cd77a635cc42e8ac5bed4b992e3610037
Signer #1 certificate MD5 digest: 1ce17d9b7b789a1d7c69297f3fa74ed5
```

### v2_layoutonly.apk  -> exit 0

```
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v4 scheme (APK Signature Scheme v4): false
Number of signers: 1
Signer #1 certificate DN: CN=ba, OU=Private, O=BA, C=CN
Signer #1 certificate SHA-256 digest: 94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc
Signer #1 certificate SHA-1 digest: b584e21cd77a635cc42e8ac5bed4b992e3610037
Signer #1 certificate MD5 digest: 1ce17d9b7b789a1d7c69297f3fa74ed5
```

### v4_login.apk  -> exit 0

```
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v4 scheme (APK Signature Scheme v4): false
Number of signers: 1
Signer #1 certificate DN: CN=ba, OU=Private, O=BA, C=CN
Signer #1 certificate SHA-256 digest: 94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc
Signer #1 certificate SHA-1 digest: b584e21cd77a635cc42e8ac5bed4b992e3610037
Signer #1 certificate MD5 digest: 1ce17d9b7b789a1d7c69297f3fa74ed5
```

* v4 签名证书 == 原签名证书 `94FA997BE0DEBB69F1C62D766664FA8A879839DC9F710F6EEBD0C413DEE99EBC` : **yes**
````


## 7. 改了哪些属性（原值 → 新值）

### 7.1 改值（24 处，全部是 XML 字面量，没有一条新资源引用）

| # | 控件 / 元素 | 属性 | 原值 | 新值 | 视觉效果 |
|---|---|---|---|---|---|
| 1 | 根 `LinearLayout`（白卡片） | `paddingTop` | （无） | `8.0dip` | 卡片顶部留白，别顶到圆角边 |
| 2 | 根 `LinearLayout` | `paddingBottom` | `@dimen/dp12` | `24.0dip` | 底部留白加倍，整体更松弛 |
| 3 | 输入区 `ConstraintLayout` | `layout_marginTop` | `@dimen/dp7` | `8.0dip` | 分隔线→输入框的间距 |
| 4 | `@id/et_phone` | `textSize` | `@dimen/sp14` | `16.0sp` | 输入文字更大 |
| 5 | `@id/et_phone` | `textColor` | `@color/c_000000` | `#FF16213A` | 深蓝黑，比纯黑柔和 |
| 6 | `@id/et_phone` | `textColorHint` | `@color/disable_text`(#FFB9B9B9) | `#FF9AA3B2` | 占位文字更清楚 |
| 7 | `@id/et_phone` | `background` | `@drawable/login_edit_bg_fragment`（透明填充 + 1dip灰描边 + 圆角） | `#FFEAF0FB` | **输入框变浅蓝色块**（最显眼之一），代价：丢圆角与描边 |
| 8 | `@id/et_phone` | `layout_height` | `@dimen/dp40` | `52.0dip` | 输入框高 +12dip，更好戳 |
| 9 | `@id/et_phone` | `hint` | `@string/hint_phone_number`（"请输入手机号"） | `"请输入卡密"` | **需求②：手机号→卡密** |
| 10 | `@id/et_phone` | `maxLength` | `11` | `64` | 卡密最长 64 字符（沿用 v2） |
| 11 | `@id/et_phone` | `inputType` | `phone` | `text` | 全键盘，能输字母数字卡密 |
| 12 | `@id/et_phone` | `paddingStart` | `@dimen/dp12` | `16.0dip` | 光标不贴边 |
| 13 | `@id/layout_phone_code`（验证码整行） | `visibility` | （无 = visible） | `gone` | **需求①：验证码整行消失** |
| 14 | `@id/et_phone_code` | `text` | （无） | `"000000"` | 看不见（父容器 gone），但给 `code.length()` 喂 6 个字符 |
| 15 | `@id/et_phone_code` | `textColor` | `@color/c_000000` | `#FF16213A` | 与上面统一（肉眼看不出） |
| 16 | `@id/ll_container_login`（按钮容器） | `paddingTop` | （无） | `8.0dip` | 按钮上方多 8dip 空气（原因见 12.3 坑 A） |
| 17 | `@id/login`（登录按钮） | `textSize` | `@dimen/sp16` | `18.0sp` | 按钮字更大 |
| 18 | `@id/login` | `textColor` | `@color/bt_text` | `#FFFFFFFF` | 纯白字 |
| 19 | `@id/login` | `background` | `@drawable/login_btn_selector`（#CC000000+圆角+按下态） | `#FF2F6FED` | **实色蓝按钮**（最显眼），代价：丢按下态与圆角 |
| 20 | `@id/login` | `textStyle` | （无） | `bold` | 加粗 |
| 21 | `@id/login` | `layout_height` | `@dimen/dp40` | `52.0dip` | 按钮加高 +12dip |
| 22 | `@id/login` | `text` | `@string/login`（"登录"） | `"登 录"` | 字间空格，按钮上更大气 |
| 23 | `@id/agreement_layout` | `layout_marginTop` | `@dimen/dp12` | `16.0dip` | 协议行下移 |
| 24 | `@id/tv_privacy_agreement` | `textColor` | `@color/c_a3a3a3` | `#FF9AA3B2` | 协议文字换蓝灰（运行时会再被 span 覆盖，见 12.3 坑 D） |

### 7.2 新增 3 个无 id 装饰控件（根 `LinearLayout` 第 3/4/5 个子节点）

```xml
<TextView android:textSize="21.0sp" android:textColor="#FF12203A" android:textStyle="bold"
    android:gravity="center" android:paddingLeft="24.0dip" android:paddingRight="24.0dip"
    android:layout_width="fill_parent" android:layout_height="wrap_content"
    android:layout_marginTop="6.0dip" android:text="卡密登录" />

<TextView android:textSize="12.0sp" android:textColor="#FF8A94A6" android:gravity="center"
    android:paddingLeft="24.0dip" android:paddingRight="24.0dip"
    android:layout_width="fill_parent" android:layout_height="wrap_content"
    android:layout_marginTop="5.0dip" android:text="无需验证码，输入卡密直接登录" />

<View android:layout_width="fill_parent" android:layout_height="1.0dip"
    android:layout_marginLeft="24.0dip" android:layout_marginTop="14.0dip"
    android:layout_marginRight="24.0dip" android:background="#FFE7ECF5" />
```

- 三个都是**框架自带类**（`TextView` / `View`），**没有 id**（所以不写 `@+id`）；`android:text` 是**字符串字面量**，`android:background` 是**颜色字面量**（`View` 直接上色，不引 drawable 资源）。
- 追加位置：根 `LinearLayout` 的 header（返回/logo/关闭）之后、`@id/tv_bind_phone_desc` 之前。外层是**纵向 LinearLayout**，加子节点不涉及任何 constraint，是最稳的加法（v2 往同一层塞 RadioGroup 已在真机验证"加子节点不会崩"）。
- 这 3 个节点**没有任何代码引用**（`initView()` 只按 id 找控件），运行时不会被改掉。

### 7.3 故意没动的

- `@drawable/login_bg_fragment`（白底 + `@dimen/radius_common_dialog` 圆角 + `@color/c_ffffff`）：**保留**。圆角是这张卡片自带的，改了反而更丑；而且这个 drawable 被 20+ 个布局共用（见 13.7），不能动。
- 所有 `@id`、控件类名、`app:*` 约束、`@id/layout_phone_code` 整棵子树的结构：**原样**。
- `@id/third_party_login`（一键登录/TapTap 那条）：**故意不设 gone**，原因见 12.3 坑 B。
- 任何 dex、`resources.arsc`、`AndroidManifest.xml`、其它资源条目：**没碰**。

## 8. 解码 XML diff（`dec0` 原始 → `dec4` 改后）

```diff
--- /root/ba_work/dec0/res/layout/fragment_default_mobile_code_login.xml	2026-11-18 18:51:09.470517918 +0800
+++ /root/ba_work/dec4/res/layout/fragment_default_mobile_code_login.xml	2026-11-18 20:13:39.861946333 +0800
@@ -1,5 +1,5 @@
 <?xml version="1.0" encoding="utf-8"?>
-<LinearLayout android:gravity="center_horizontal" android:layout_gravity="center" android:orientation="vertical" android:background="@drawable/login_bg_fragment" android:paddingBottom="@dimen/dp12" android:layout_width="@dimen/dp328" android:layout_height="wrap_content"
+<LinearLayout android:gravity="center_horizontal" android:layout_gravity="center" android:orientation="vertical" android:background="@drawable/login_bg_fragment" android:paddingTop="8.0dip" android:paddingBottom="24.0dip" android:layout_width="@dimen/dp328" android:layout_height="wrap_content"
   xmlns:android="http://schemas.android.com/apk/res/android" xmlns:app="http://schemas.android.com/apk/res-auto">
     <LinearLayout android:gravity="center_vertical" android:paddingLeft="@dimen/dp12" android:paddingTop="@dimen/dp12" android:paddingRight="@dimen/dp12" android:paddingBottom="@dimen/dp7" android:layout_width="fill_parent" android:layout_height="wrap_content">
         <ImageView android:id="@id/iv_back" android:background="@drawable/back" android:layout_width="@dimen/dp24" android:layout_height="@dimen/dp24" android:scaleType="centerCrop" />
@@ -9,22 +9,25 @@
         </LinearLayout>
         <ImageView android:id="@id/iv_close" android:background="@drawable/close" android:layout_width="@dimen/dp24" android:layout_height="@dimen/dp24" android:scaleType="centerCrop" />
     </LinearLayout>
+    <TextView android:textSize="21.0sp" android:textColor="#FF12203A" android:textStyle="bold" android:gravity="center" android:paddingLeft="24.0dip" android:paddingRight="24.0dip" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="6.0dip" android:text="卡密登录" />
+    <TextView android:textSize="12.0sp" android:textColor="#FF8A94A6" android:gravity="center" android:paddingLeft="24.0dip" android:paddingRight="24.0dip" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="5.0dip" android:text="无需验证码，输入卡密直接登录" />
+    <View android:layout_width="fill_parent" android:layout_height="1.0dip" android:layout_marginLeft="24.0dip" android:layout_marginTop="14.0dip" android:layout_marginRight="24.0dip" android:background="#FFE7ECF5" />
     <TextView android:textSize="@dimen/sp12" android:textColor="@color/c_6a6a6a" android:gravity="center" android:id="@id/tv_bind_phone_desc" android:visibility="gone" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginLeft="@dimen/dp32" android:layout_marginRight="@dimen/dp32" android:text="@string/bind_phone_desc" />
-    <androidx.constraintlayout.widget.ConstraintLayout android:paddingLeft="@dimen/dp24" android:paddingRight="@dimen/dp24" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="@dimen/dp7">
-        <com.airi.official.core.widget.ExtendEditText android:textSize="@dimen/sp14" android:textColor="@color/c_000000" android:textColorHint="@color/disable_text" android:id="@id/et_phone" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:hint="@string/hint_phone_number" android:singleLine="true" android:maxLength="11" android:inputType="phone" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="@dimen/dp12" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toTopOf="parent" />
-        <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/layout_phone_code" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:layout_marginTop="@dimen/dp12" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/et_phone">
-            <com.airi.official.core.widget.ExtendEditText android:textSize="@dimen/sp14" android:textColor="@color/c_000000" android:textColorHint="@color/disable_text" android:id="@id/et_phone_code" android:background="@null" android:layout_width="0.0dip" android:layout_height="@dimen/dp40" android:hint="@string/hint_phone_code" android:singleLine="true" android:maxLength="6" android:inputType="number" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="@dimen/dp12" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toLeftOf="@id/divide" app:layout_constraintTop_toTopOf="parent" />
+    <androidx.constraintlayout.widget.ConstraintLayout android:paddingLeft="@dimen/dp24" android:paddingRight="@dimen/dp24" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="8.0dip">
+        <com.airi.official.core.widget.ExtendEditText android:textSize="16.0sp" android:textColor="#FF16213A" android:textColorHint="#FF9AA3B2" android:id="@id/et_phone" android:background="#FFEAF0FB" android:layout_width="fill_parent" android:layout_height="52.0dip" android:hint="请输入卡密" android:singleLine="true" android:maxLength="64" android:inputType="text" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="16.0dip" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toTopOf="parent" />
+        <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/layout_phone_code" android:visibility="gone" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:layout_marginTop="@dimen/dp12" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/et_phone">
+            <com.airi.official.core.widget.ExtendEditText android:textSize="@dimen/sp14" android:textColor="#FF16213A" android:textColorHint="@color/disable_text" android:id="@id/et_phone_code" android:text="000000" android:background="@null" android:layout_width="0.0dip" android:layout_height="@dimen/dp40" android:hint="@string/hint_phone_code" android:singleLine="true" android:maxLength="6" android:inputType="number" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="@dimen/dp12" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toLeftOf="@id/divide" app:layout_constraintTop_toTopOf="parent" />
             <TextView android:id="@id/divide" android:background="@color/divider_common" android:layout_width="@dimen/dp1" android:layout_height="@dimen/dp20" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintRight_toLeftOf="@id/get_phone_code" app:layout_constraintTop_toTopOf="parent" />
             <TextView android:textSize="@dimen/sp14" android:textColor="@color/disable_text" android:ellipsize="end" android:gravity="center" android:layout_gravity="center_horizontal" android:id="@id/get_phone_code" android:layout_width="@dimen/dp60" android:layout_height="wrap_content" android:text="@string/get_phone_code" android:singleLine="true" android:includeFontPadding="false" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toTopOf="parent" />
         </androidx.constraintlayout.widget.ConstraintLayout>
-        <LinearLayout android:orientation="vertical" android:id="@id/ll_container_login" android:layout_width="fill_parent" android:layout_height="wrap_content" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/layout_phone_code">
-            <Button android:textSize="@dimen/sp16" android:textColor="@color/bt_text" android:id="@id/login" android:background="@drawable/login_btn_selector" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:layout_marginTop="@dimen/dp12" android:text="@string/login" />
+        <LinearLayout android:orientation="vertical" android:paddingTop="8.0dip" android:id="@id/ll_container_login" android:layout_width="fill_parent" android:layout_height="wrap_content" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/layout_phone_code">
+            <Button android:textSize="18.0sp" android:textColor="#FFFFFFFF" android:id="@id/login" android:textStyle="bold" android:background="#FF2F6FED" android:layout_width="fill_parent" android:layout_height="52.0dip" android:layout_marginTop="@dimen/dp12" android:text="登 录" />
             <View android:id="@id/login_helper" android:visibility="gone" android:layout_width="fill_parent" android:layout_height="@dimen/dp12" />
         </LinearLayout>
-        <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/agreement_layout" android:layout_width="fill_parent" android:layout_height="fill_parent" android:layout_marginTop="@dimen/dp12" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/ll_container_login">
+        <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/agreement_layout" android:layout_width="fill_parent" android:layout_height="fill_parent" android:layout_marginTop="16.0dip" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/ll_container_login">
             <LinearLayout android:orientation="horizontal" android:layout_width="wrap_content" android:layout_height="wrap_content" app:layout_constraintEnd_toEndOf="parent" app:layout_constraintStart_toStartOf="parent" app:layout_constraintTop_toTopOf="parent">
                 <ImageView android:id="@id/iv_privacy_agreement_select" android:background="@drawable/disagree" android:layout_width="@dimen/dp14" android:layout_height="@dimen/dp14" android:layout_marginTop="@dimen/dp2" />
-                <TextView android:textSize="@dimen/sp12" android:textColor="@color/c_a3a3a3" android:id="@id/tv_privacy_agreement" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginLeft="@dimen/dp6" android:text="@string/privacy_agreement" android:textAlignment="center" />
+                <TextView android:textSize="@dimen/sp12" android:textColor="#FF9AA3B2" android:id="@id/tv_privacy_agreement" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginLeft="@dimen/dp6" android:text="@string/privacy_agreement" android:textAlignment="center" />
             </LinearLayout>
         </androidx.constraintlayout.widget.ConstraintLayout>
         <FrameLayout android:id="@id/third_party_login" android:layout_width="fill_parent" android:layout_height="@dimen/dp26" android:layout_marginTop="@dimen/dp14" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/agreement_layout">
```


## 9. 打进包的 AXML 结构（自研独立解析器 `axml_dump.py`，不经过 aapt/apktool）

```
# AXML /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/v4/res_Q9_v4.axml
# size=8208 strings=59 utf8=True resmap=42 chunks=66 sha256=f614865a97955515e41e2248af0b6004f7eefdea3d2fbd0897285d226cb189b3
NS android -> http://schemas.android.com/apk/res/android
NS app -> http://schemas.android.com/apk/res-auto
E: LinearLayout
  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000001 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:layout_gravity(0x010100b3) 0x00000011 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:orientation(0x010100c4) 1 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f0700b2 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingTop(0x010100d7) 8dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:paddingBottom(0x010100d9) 24dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f060136 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
E: LinearLayout
  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000010 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:paddingLeft(0x010100d6) @0x7f0600a9 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingTop(0x010100d7) @0x7f0600a9 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingRight(0x010100d8) @0x7f0600a9 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingBottom(0x010100d9) @0x7f06016c [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
E: ImageView
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f08015d [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f070069 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f060103 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060103 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:scaleType(0x0101011d) 6 [INT_DEC]
/E: ImageView
E: LinearLayout
  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000011 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:orientation(0x010100c4) 1 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 0dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_weight(0x01010181) 1.0 [FLOAT]
E: View
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060144 [REFERENCE]
/E: View
E: ImageView
  A: http://schemas.android.com/apk/res/android:layout_gravity(0x010100b3) 0x00000001 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f080164 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f070092 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f0600aa [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060122 [REFERENCE]
/E: ImageView
/E: LinearLayout
E: ImageView
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f08015e [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f07007a [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f060103 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060103 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:scaleType(0x0101011d) 6 [INT_DEC]
/E: ImageView
/E: LinearLayout
E: TextView
  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) 21sp [DIMENSION]
  A: http://schemas.android.com/apk/res/android:textStyle(0x01010097) 0x00000001 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) #ff12203a [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000011 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:paddingLeft(0x010100d6) 24dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:paddingRight(0x010100d8) 24dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) 6dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:text(0x0101014f) '卡密登录' [STRING]
/E: TextView
E: TextView
  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) 12sp [DIMENSION]
  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) #ff8a94a6 [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000011 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:paddingLeft(0x010100d6) 24dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:paddingRight(0x010100d8) 24dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) 5dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:text(0x0101014f) '无需验证码，输入卡密直接登录' [STRING]
/E: TextView
E: View
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) #ffe7ecf5 [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 1dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_marginLeft(0x010100f7) 24dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) 14dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_marginRight(0x010100f9) 24dip [DIMENSION]
/E: View
E: TextView
  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) @0x7f06029c [REFERENCE]
  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) @0x7f05003d [REFERENCE]
  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000011 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f0802bc [REFERENCE]
  A: http://schemas.android.com/apk/res/android:visibility(0x010100dc) 2 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_marginLeft(0x010100f7) @0x7f060133 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_marginRight(0x010100f9) @0x7f060133 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:text(0x0101014f) @0x7f0f0038 [REFERENCE]
/E: TextView
E: androidx.constraintlayout.widget.ConstraintLayout
  A: http://schemas.android.com/apk/res/android:paddingLeft(0x010100d6) @0x7f060103 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingRight(0x010100d8) @0x7f060103 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) 8dip [DIMENSION]
E: com.airi.official.core.widget.ExtendEditText
  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) 16sp [DIMENSION]
  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) #ff16213a [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:textColorHint(0x0101009a) #ff9aa3b2 [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f080108 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) #ffeaf0fb [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 52dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:hint(0x01010150) '请输入卡密' [STRING]
  A: http://schemas.android.com/apk/res/android:singleLine(0x0101015d) true [INT_BOOLEAN]
  A: http://schemas.android.com/apk/res/android:maxLength(0x01010160) 64 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:inputType(0x01010220) 0x00000001 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:imeOptions(0x01010264) 0x10000006 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:paddingStart(0x010103b3) 16dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:paddingEnd(0x010103b4) @0x7f060090 [REFERENCE]
  A: http://schemas.android.com/apk/res-auto:clearButtonMode(0x7f0300be) 2 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintLeft_toLeftOf(0x7f03021a) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintRight_toRightOf(0x7f03021e) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintTop_toTopOf(0x7f030224) 0 [INT_DEC]
/E: com.airi.official.core.widget.ExtendEditText
E: androidx.constraintlayout.widget.ConstraintLayout
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f08016f [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f0700b7 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:visibility(0x010100dc) 2 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060145 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) @0x7f0600a9 [REFERENCE]
  A: http://schemas.android.com/apk/res-auto:layout_constraintLeft_toLeftOf(0x7f03021a) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintRight_toRightOf(0x7f03021e) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintTop_toBottomOf(0x7f030223) @0x7f080108 [REFERENCE]
E: com.airi.official.core.widget.ExtendEditText
  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) @0x7f06029e [REFERENCE]
  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) #ff16213a [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:textColorHint(0x0101009a) @0x7f050091 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f080109 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x00000000 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 0dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060145 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:text(0x0101014f) '000000' [STRING]
  A: http://schemas.android.com/apk/res/android:hint(0x01010150) @0x7f0f0073 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:singleLine(0x0101015d) true [INT_BOOLEAN]
  A: http://schemas.android.com/apk/res/android:maxLength(0x01010160) 6 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:inputType(0x01010220) 0x00000002 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:imeOptions(0x01010264) 0x10000006 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:paddingStart(0x010103b3) @0x7f0600a9 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingEnd(0x010103b4) @0x7f060090 [REFERENCE]
  A: http://schemas.android.com/apk/res-auto:clearButtonMode(0x7f0300be) 2 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintBottom_toBottomOf(0x7f030206) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintLeft_toLeftOf(0x7f03021a) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintRight_toLeftOf(0x7f03021d) @0x7f0800ec [REFERENCE]
  A: http://schemas.android.com/apk/res-auto:layout_constraintTop_toTopOf(0x7f030224) 0 [INT_DEC]
/E: com.airi.official.core.widget.ExtendEditText
E: TextView
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f0800ec [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f050092 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f060092 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f0600e9 [REFERENCE]
  A: http://schemas.android.com/apk/res-auto:layout_constraintBottom_toBottomOf(0x7f030206) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintRight_toLeftOf(0x7f03021d) @0x7f08012e [REFERENCE]
  A: http://schemas.android.com/apk/res-auto:layout_constraintTop_toTopOf(0x7f030224) 0 [INT_DEC]
/E: TextView
E: TextView
  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) @0x7f06029e [REFERENCE]
  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) @0x7f050091 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:ellipsize(0x010100ab) 3 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000011 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:layout_gravity(0x010100b3) 0x00000001 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f08012e [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f060162 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:text(0x0101014f) @0x7f0f006a [REFERENCE]
  A: http://schemas.android.com/apk/res/android:singleLine(0x0101015d) true [INT_BOOLEAN]
  A: http://schemas.android.com/apk/res/android:includeFontPadding(0x0101015f) false [INT_BOOLEAN]
  A: http://schemas.android.com/apk/res-auto:layout_constraintBottom_toBottomOf(0x7f030206) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintRight_toRightOf(0x7f03021e) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintTop_toTopOf(0x7f030224) 0 [INT_DEC]
/E: TextView
/E: androidx.constraintlayout.widget.ConstraintLayout
E: LinearLayout
  A: http://schemas.android.com/apk/res/android:orientation(0x010100c4) 1 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f08017a [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingTop(0x010100d7) 8dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintLeft_toLeftOf(0x7f03021a) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintRight_toRightOf(0x7f03021e) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintTop_toBottomOf(0x7f030223) @0x7f08016f [REFERENCE]
E: Button
  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) 18sp [DIMENSION]
  A: http://schemas.android.com/apk/res/android:textStyle(0x01010097) 0x00000001 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) #ffffffff [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f080182 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) #ff2f6fed [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 52dip [DIMENSION]
  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) @0x7f0600a9 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:text(0x0101014f) '登 录' [STRING]
/E: Button
E: View
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f080183 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:visibility(0x010100dc) 2 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f0600a9 [REFERENCE]
/E: View
/E: LinearLayout
E: androidx.constraintlayout.widget.ConstraintLayout
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f08004e [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) 16dip [DIMENSION]
  A: http://schemas.android.com/apk/res-auto:layout_constraintLeft_toLeftOf(0x7f03021a) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintRight_toRightOf(0x7f03021e) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintTop_toBottomOf(0x7f030223) @0x7f08017a [REFERENCE]
E: LinearLayout
  A: http://schemas.android.com/apk/res/android:orientation(0x010100c4) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintEnd_toEndOf(0x7f03020c) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintStart_toStartOf(0x7f030220) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintTop_toTopOf(0x7f030224) 0 [INT_DEC]
E: ImageView
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f080166 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f070087 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f0600bb [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f0600bb [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) @0x7f0600e8 [REFERENCE]
/E: ImageView
E: TextView
  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) @0x7f06029c [REFERENCE]
  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) #ff9aa3b2 [INT_COLOR_ARGB8]
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f0802ce [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_marginLeft(0x010100f7) @0x7f060161 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:text(0x0101014f) @0x7f0f0111 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:textAlignment(0x010103b1) 4 [INT_DEC]
/E: TextView
/E: LinearLayout
/E: androidx.constraintlayout.widget.ConstraintLayout
E: FrameLayout
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f0802a7 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060113 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) @0x7f0600bb [REFERENCE]
  A: http://schemas.android.com/apk/res-auto:layout_constraintLeft_toLeftOf(0x7f03021a) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintRight_toRightOf(0x7f03021e) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res-auto:layout_constraintTop_toBottomOf(0x7f030223) @0x7f08004e [REFERENCE]
E: LinearLayout
  A: http://schemas.android.com/apk/res/android:layout_gravity(0x010100b3) 0x00000011 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:orientation(0x010100c4) 0 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967295 [INT_DEC]
E: LinearLayout
  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000010 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f0801e1 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f0700b9 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingLeft(0x010100d6) @0x7f0600dc [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingTop(0x010100d7) @0x7f060153 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingRight(0x010100d8) @0x7f0600dc [REFERENCE]
  A: http://schemas.android.com/apk/res/android:paddingBottom(0x010100d9) @0x7f060153 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967295 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_marginRight(0x010100f9) @0x7f060103 [REFERENCE]
E: ImageView
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f0801fe [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f060177 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f0600a9 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:src(0x01010119) @0x7f0700e2 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:scaleType(0x0101011d) 6 [INT_DEC]
/E: ImageView
E: TextView
  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) @0x7f06029c [REFERENCE]
  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) @0x7f05002d [REFERENCE]
  A: http://schemas.android.com/apk/res/android:ellipsize(0x010100ab) 3 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
  A: http://schemas.android.com/apk/res/android:layout_marginLeft(0x010100f7) @0x7f060177 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:text(0x0101014f) @0x7f0f00ec [REFERENCE]
  A: http://schemas.android.com/apk/res/android:singleLine(0x0101015d) true [INT_BOOLEAN]
/E: TextView
/E: LinearLayout
E: FrameLayout
  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f080290 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f0700f7 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f0600bc [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967295 [INT_DEC]
E: ImageView
  A: http://schemas.android.com/apk/res/android:layout_gravity(0x010100b3) 0x00000011 [INT_HEX]
  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) @0x7f060168 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f0600a9 [REFERENCE]
  A: http://schemas.android.com/apk/res/android:src(0x01010119) @0x7f07009b [REFERENCE]
  A: http://schemas.android.com/apk/res/android:scaleType(0x0101011d) 6 [INT_DEC]
/E: ImageView
/E: FrameLayout
/E: LinearLayout
/E: FrameLayout
/E: androidx.constraintlayout.widget.ConstraintLayout
/E: LinearLayout
# NS_END
# NS_END
```


## 10. 第三方工具独立读回（`aapt dump xmltree` 直接读产物里的 `res/Q9.xml`）

```
N: android=http://schemas.android.com/apk/res/android
  N: app=http://schemas.android.com/apk/res-auto
    E: LinearLayout (line=2)
      A: android:gravity(0x010100af)=(type 0x11)0x1
      A: android:layout_gravity(0x010100b3)=(type 0x11)0x11
      A: android:orientation(0x010100c4)=(type 0x10)0x1
      A: android:background(0x010100d4)=@0x7f0700b2
      A: android:paddingTop(0x010100d7)=(type 0x5)0x801
      A: android:paddingBottom(0x010100d9)=(type 0x5)0x1801
      A: android:layout_width(0x010100f4)=@0x7f060136
      A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
      E: LinearLayout (line=4)
        A: android:gravity(0x010100af)=(type 0x11)0x10
        A: android:paddingLeft(0x010100d6)=@0x7f0600a9
        A: android:paddingTop(0x010100d7)=@0x7f0600a9
        A: android:paddingRight(0x010100d8)=@0x7f0600a9
        A: android:paddingBottom(0x010100d9)=@0x7f06016c
        A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
        A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
        E: ImageView (line=5)
          A: android:id(0x010100d0)=@0x7f08015d
          A: android:background(0x010100d4)=@0x7f070069
          A: android:layout_width(0x010100f4)=@0x7f060103
          A: android:layout_height(0x010100f5)=@0x7f060103
          A: android:scaleType(0x0101011d)=(type 0x10)0x6
        E: LinearLayout (line=6)
          A: android:gravity(0x010100af)=(type 0x11)0x11
          A: android:orientation(0x010100c4)=(type 0x10)0x1
          A: android:layout_width(0x010100f4)=(type 0x5)0x1
          A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
          A: android:layout_weight(0x01010181)=(type 0x4)0x3f800000
          E: View (line=7)
            A: android:layout_width(0x010100f4)=(type 0x10)0xfffffffe
            A: android:layout_height(0x010100f5)=@0x7f060144
          E: ImageView (line=8)
            A: android:layout_gravity(0x010100b3)=(type 0x11)0x1
            A: android:id(0x010100d0)=@0x7f080164
            A: android:background(0x010100d4)=@0x7f070092
            A: android:layout_width(0x010100f4)=@0x7f0600aa
            A: android:layout_height(0x010100f5)=@0x7f060122
        E: ImageView (line=10)
          A: android:id(0x010100d0)=@0x7f08015e
          A: android:background(0x010100d4)=@0x7f07007a
          A: android:layout_width(0x010100f4)=@0x7f060103
          A: android:layout_height(0x010100f5)=@0x7f060103
          A: android:scaleType(0x0101011d)=(type 0x10)0x6
      E: TextView (line=12)
        A: android:textSize(0x01010095)=(type 0x5)0x1502
        A: android:textStyle(0x01010097)=(type 0x11)0x1
        A: android:textColor(0x01010098)=(type 0x1c)0xff12203a
        A: android:gravity(0x010100af)=(type 0x11)0x11
        A: android:paddingLeft(0x010100d6)=(type 0x5)0x1801
        A: android:paddingRight(0x010100d8)=(type 0x5)0x1801
        A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
        A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
        A: android:layout_marginTop(0x010100f8)=(type 0x5)0x601
        A: android:text(0x0101014f)="卡密登录" (Raw: "卡密登录")
      E: TextView (line=13)
        A: android:textSize(0x01010095)=(type 0x5)0xc02
        A: android:textColor(0x01010098)=(type 0x1c)0xff8a94a6
        A: android:gravity(0x010100af)=(type 0x11)0x11
        A: android:paddingLeft(0x010100d6)=(type 0x5)0x1801
        A: android:paddingRight(0x010100d8)=(type 0x5)0x1801
        A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
        A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
        A: android:layout_marginTop(0x010100f8)=(type 0x5)0x501
        A: android:text(0x0101014f)="无需验证码，输入卡密直接登录" (Raw: "无需验证码，输入卡密直接登录")
      E: View (line=14)
        A: android:background(0x010100d4)=(type 0x1c)0xffe7ecf5
        A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
        A: android:layout_height(0x010100f5)=(type 0x5)0x101
        A: android:layout_marginLeft(0x010100f7)=(type 0x5)0x1801
        A: android:layout_marginTop(0x010100f8)=(type 0x5)0xe01
        A: android:layout_marginRight(0x010100f9)=(type 0x5)0x1801
      E: TextView (line=15)
        A: android:textSize(0x01010095)=@0x7f06029c
        A: android:textColor(0x01010098)=@0x7f05003d
        A: android:gravity(0x010100af)=(type 0x11)0x11
        A: android:id(0x010100d0)=@0x7f0802bc
        A: android:visibility(0x010100dc)=(type 0x10)0x2
        A: android:layout_width(0x010100f4)=(type 0x10)0xfffffffe
        A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
        A: android:layout_marginLeft(0x010100f7)=@0x7f060133
        A: android:layout_marginRight(0x010100f9)=@0x7f060133
        A: android:text(0x0101014f)=@0x7f0f0038
      E: androidx.constraintlayout.widget.ConstraintLayout (line=16)
        A: android:paddingLeft(0x010100d6)=@0x7f060103
        A: android:paddingRight(0x010100d8)=@0x7f060103
        A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
        A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
        A: android:layout_marginTop(0x010100f8)=(type 0x5)0x801
        E: com.airi.official.core.widget.ExtendEditText (line=17)
          A: android:textSize(0x01010095)=(type 0x5)0x1002
          A: android:textColor(0x01010098)=(type 0x1c)0xff16213a
          A: android:textColorHint(0x0101009a)=(type 0x1c)0xff9aa3b2
          A: android:id(0x010100d0)=@0x7f080108
          A: android:background(0x010100d4)=(type 0x1c)0xffeaf0fb
          A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
          A: android:layout_height(0x010100f5)=(type 0x5)0x3401
          A: android:hint(0x01010150)="请输入卡密" (Raw: "请输入卡密")
          A: android:singleLine(0x0101015d)=(type 0x12)0xffffffff
          A: android:maxLength(0x01010160)=(type 0x10)0x40
          A: android:inputType(0x01010220)=(type 0x11)0x1
          A: android:imeOptions(0x01010264)=(type 0x11)0x10000006
          A: android:paddingStart(0x010103b3)=(type 0x5)0x1001
          A: android:paddingEnd(0x010103b4)=@0x7f060090
          A: app:clearButtonMode(0x7f0300be)=(type 0x10)0x2
          A: app:layout_constraintLeft_toLeftOf(0x7f03021a)=(type 0x10)0x0
          A: app:layout_constraintRight_toRightOf(0x7f03021e)=(type 0x10)0x0
          A: app:layout_constraintTop_toTopOf(0x7f030224)=(type 0x10)0x0
        E: androidx.constraintlayout.widget.ConstraintLayout (line=18)
          A: android:id(0x010100d0)=@0x7f08016f
          A: android:background(0x010100d4)=@0x7f0700b7
          A: android:visibility(0x010100dc)=(type 0x10)0x2
          A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
          A: android:layout_height(0x010100f5)=@0x7f060145
          A: android:layout_marginTop(0x010100f8)=@0x7f0600a9
          A: app:layout_constraintLeft_toLeftOf(0x7f03021a)=(type 0x10)0x0
          A: app:layout_constraintRight_toRightOf(0x7f03021e)=(type 0x10)0x0
          A: app:layout_constraintTop_toBottomOf(0x7f030223)=@0x7f080108
          E: com.airi.official.core.widget.ExtendEditText (line=19)
            A: android:textSize(0x01010095)=@0x7f06029e
            A: android:textColor(0x01010098)=(type 0x1c)0xff16213a
            A: android:textColorHint(0x0101009a)=@0x7f050091
            A: android:id(0x010100d0)=@0x7f080109
            A: android:background(0x010100d4)=@0x00000000
            A: android:layout_width(0x010100f4)=(type 0x5)0x1
            A: android:layout_height(0x010100f5)=@0x7f060145
            A: android:text(0x0101014f)="000000" (Raw: "000000")
            A: android:hint(0x01010150)=@0x7f0f0073
            A: android:singleLine(0x0101015d)=(type 0x12)0xffffffff
            A: android:maxLength(0x01010160)=(type 0x10)0x6
            A: android:inputType(0x01010220)=(type 0x11)0x2
            A: android:imeOptions(0x01010264)=(type 0x11)0x10000006
            A: android:paddingStart(0x010103b3)=@0x7f0600a9
            A: android:paddingEnd(0x010103b4)=@0x7f060090
            A: app:clearButtonMode(0x7f0300be)=(type 0x10)0x2
            A: app:layout_constraintBottom_toBottomOf(0x7f030206)=(type 0x10)0x0
            A: app:layout_constraintLeft_toLeftOf(0x7f03021a)=(type 0x10)0x0
            A: app:layout_constraintRight_toLeftOf(0x7f03021d)=@0x7f0800ec
            A: app:layout_constraintTop_toTopOf(0x7f030224)=(type 0x10)0x0
          E: TextView (line=20)
            A: android:id(0x010100d0)=@0x7f0800ec
            A: android:background(0x010100d4)=@0x7f050092
            A: android:layout_width(0x010100f4)=@0x7f060092
            A: android:layout_height(0x010100f5)=@0x7f0600e9
            A: app:layout_constraintBottom_toBottomOf(0x7f030206)=(type 0x10)0x0
            A: app:layout_constraintRight_toLeftOf(0x7f03021d)=@0x7f08012e
            A: app:layout_constraintTop_toTopOf(0x7f030224)=(type 0x10)0x0
          E: TextView (line=21)
            A: android:textSize(0x01010095)=@0x7f06029e
            A: android:textColor(0x01010098)=@0x7f050091
            A: android:ellipsize(0x010100ab)=(type 0x10)0x3
            A: android:gravity(0x010100af)=(type 0x11)0x11
            A: android:layout_gravity(0x010100b3)=(type 0x11)0x1
            A: android:id(0x010100d0)=@0x7f08012e
            A: android:layout_width(0x010100f4)=@0x7f060162
            A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
            A: android:text(0x0101014f)=@0x7f0f006a
            A: android:singleLine(0x0101015d)=(type 0x12)0xffffffff
            A: android:includeFontPadding(0x0101015f)=(type 0x12)0x0
            A: app:layout_constraintBottom_toBottomOf(0x7f030206)=(type 0x10)0x0
            A: app:layout_constraintRight_toRightOf(0x7f03021e)=(type 0x10)0x0
            A: app:layout_constraintTop_toTopOf(0x7f030224)=(type 0x10)0x0
        E: LinearLayout (line=23)
          A: android:orientation(0x010100c4)=(type 0x10)0x1
          A: android:id(0x010100d0)=@0x7f08017a
          A: android:paddingTop(0x010100d7)=(type 0x5)0x801
          A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
          A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
          A: app:layout_constraintLeft_toLeftOf(0x7f03021a)=(type 0x10)0x0
          A: app:layout_constraintRight_toRightOf(0x7f03021e)=(type 0x10)0x0
          A: app:layout_constraintTop_toBottomOf(0x7f030223)=@0x7f08016f
          E: Button (line=24)
            A: android:textSize(0x01010095)=(type 0x5)0x1202
            A: android:textStyle(0x01010097)=(type 0x11)0x1
            A: android:textColor(0x01010098)=(type 0x1c)0xffffffff
            A: android:id(0x010100d0)=@0x7f080182
            A: android:background(0x010100d4)=(type 0x1c)0xff2f6fed
            A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
            A: android:layout_height(0x010100f5)=(type 0x5)0x3401
            A: android:layout_marginTop(0x010100f8)=@0x7f0600a9
            A: android:text(0x0101014f)="登 录" (Raw: "登 录")
          E: View (line=25)
            A: android:id(0x010100d0)=@0x7f080183
            A: android:visibility(0x010100dc)=(type 0x10)0x2
            A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
            A: android:layout_height(0x010100f5)=@0x7f0600a9
        E: androidx.constraintlayout.widget.ConstraintLayout (line=27)
          A: android:id(0x010100d0)=@0x7f08004e
          A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
          A: android:layout_height(0x010100f5)=(type 0x10)0xffffffff
          A: android:layout_marginTop(0x010100f8)=(type 0x5)0x1001
          A: app:layout_constraintLeft_toLeftOf(0x7f03021a)=(type 0x10)0x0
          A: app:layout_constraintRight_toRightOf(0x7f03021e)=(type 0x10)0x0
          A: app:layout_constraintTop_toBottomOf(0x7f030223)=@0x7f08017a
          E: LinearLayout (line=28)
            A: android:orientation(0x010100c4)=(type 0x10)0x0
            A: android:layout_width(0x010100f4)=(type 0x10)0xfffffffe
            A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
            A: app:layout_constraintEnd_toEndOf(0x7f03020c)=(type 0x10)0x0
            A: app:layout_constraintStart_toStartOf(0x7f030220)=(type 0x10)0x0
            A: app:layout_constraintTop_toTopOf(0x7f030224)=(type 0x10)0x0
            E: ImageView (line=29)
              A: android:id(0x010100d0)=@0x7f080166
              A: android:background(0x010100d4)=@0x7f070087
              A: android:layout_width(0x010100f4)=@0x7f0600bb
              A: android:layout_height(0x010100f5)=@0x7f0600bb
              A: android:layout_marginTop(0x010100f8)=@0x7f0600e8
            E: TextView (line=30)
              A: android:textSize(0x01010095)=@0x7f06029c
              A: android:textColor(0x01010098)=(type 0x1c)0xff9aa3b2
              A: android:id(0x010100d0)=@0x7f0802ce
              A: android:layout_width(0x010100f4)=(type 0x10)0xfffffffe
              A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
              A: android:layout_marginLeft(0x010100f7)=@0x7f060161
              A: android:text(0x0101014f)=@0x7f0f0111
              A: android:textAlignment(0x010103b1)=(type 0x10)0x4
        E: FrameLayout (line=33)
          A: android:id(0x010100d0)=@0x7f0802a7
          A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
          A: android:layout_height(0x010100f5)=@0x7f060113
          A: android:layout_marginTop(0x010100f8)=@0x7f0600bb
          A: app:layout_constraintLeft_toLeftOf(0x7f03021a)=(type 0x10)0x0
          A: app:layout_constraintRight_toRightOf(0x7f03021e)=(type 0x10)0x0
          A: app:layout_constraintTop_toBottomOf(0x7f030223)=@0x7f08004e
          E: LinearLayout (line=34)
            A: android:layout_gravity(0x010100b3)=(type 0x11)0x11
            A: android:orientation(0x010100c4)=(type 0x10)0x0
            A: android:layout_width(0x010100f4)=(type 0x10)0xfffffffe
            A: android:layout_height(0x010100f5)=(type 0x10)0xffffffff
            E: LinearLayout (line=35)
              A: android:gravity(0x010100af)=(type 0x11)0x10
              A: android:id(0x010100d0)=@0x7f0801e1
              A: android:background(0x010100d4)=@0x7f0700b9
              A: android:paddingLeft(0x010100d6)=@0x7f0600dc
              A: android:paddingTop(0x010100d7)=@0x7f060153
              A: android:paddingRight(0x010100d8)=@0x7f0600dc
              A: android:paddingBottom(0x010100d9)=@0x7f060153
              A: android:layout_width(0x010100f4)=(type 0x10)0xfffffffe
              A: android:layout_height(0x010100f5)=(type 0x10)0xffffffff
              A: android:layout_marginRight(0x010100f9)=@0x7f060103
              E: ImageView (line=36)
                A: android:id(0x010100d0)=@0x7f0801fe
                A: android:layout_width(0x010100f4)=@0x7f060177
                A: android:layout_height(0x010100f5)=@0x7f0600a9
                A: android:src(0x01010119)=@0x7f0700e2
                A: android:scaleType(0x0101011d)=(type 0x10)0x6
              E: TextView (line=37)
                A: android:textSize(0x01010095)=@0x7f06029c
                A: android:textColor(0x01010098)=@0x7f05002d
                A: android:ellipsize(0x010100ab)=(type 0x10)0x3
                A: android:layout_width(0x010100f4)=(type 0x10)0xfffffffe
                A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
                A: android:layout_marginLeft(0x010100f7)=@0x7f060177
                A: android:text(0x0101014f)=@0x7f0f00ec
                A: android:singleLine(0x0101015d)=(type 0x12)0xffffffff
            E: FrameLayout (line=39)
              A: android:id(0x010100d0)=@0x7f080290
              A: android:background(0x010100d4)=@0x7f0700f7
              A: android:layout_width(0x010100f4)=@0x7f0600bc
              A: android:layout_height(0x010100f5)=(type 0x10)0xffffffff
              E: ImageView (line=40)
                A: android:layout_gravity(0x010100b3)=(type 0x11)0x11
                A: android:layout_width(0x010100f4)=@0x7f060168
                A: android:layout_height(0x010100f5)=@0x7f0600a9
                A: android:src(0x01010119)=@0x7f07009b
                A: android:scaleType(0x0101011d)=(type 0x10)0x6
```


## 11. 构建日志

### 11.1 布局编译（`apktool b -s`：只编 res，产物里没有 dex）

```
=== decoded-XML edits (23) ===
  root.padding                 android:paddingBottom="@dimen/dp12"            -> android:paddingTop="8.0dip" android:paddingBottom="24.0dip"
  title block                  inserted after header row (root child #3/#4/#5)
  inputbox.marginTop           android:layout_marginTop="@dimen/dp7"          -> android:layout_marginTop="8.0dip"
  et_phone.textSize            android:textSize="@dimen/sp14"                 -> android:textSize="16.0sp"
  et_phone.textColor           android:textColor="@color/c_000000"            -> android:textColor="#FF16213A"
  et_phone.hintColor           android:textColorHint="@color/disable_text"    -> android:textColorHint="#FF9AA3B2"
  et_phone.background          android:background="@drawable/login_edit_bg_fragment" -> android:background="#FFEAF0FB"
  et_phone.height              android:layout_height="@dimen/dp40"            -> android:layout_height="52.0dip"
  et_phone.hint                android:hint="@string/hint_phone_number"       -> android:hint="请输入卡密"
  et_phone.maxLength           android:maxLength="11"                         -> android:maxLength="64"
  et_phone.inputType           android:inputType="phone"                      -> android:inputType="text"
  et_phone.paddingStart        android:paddingStart="@dimen/dp12"             -> android:paddingStart="16.0dip"
  layout_phone_code.visibility android:id="@id/layout_phone_code"             -> android:id="@id/layout_phone_code" android:visibility="gone"
  et_phone_code.text           android:id="@id/et_phone_code"                 -> android:id="@id/et_phone_code" android:text="000000"
  et_phone_code.textColor      android:textColor="@color/c_000000"            -> android:textColor="#FF16213A"
  loginbox.paddingTop          android:orientation="vertical" android:id="@id/ll_container_login" -> android:orientation="vertical" android:paddingTop="8.0dip" android:id="@id/ll_container_login"
  login.textSize               android:textSize="@dimen/sp16"                 -> android:textSize="18.0sp"
  login.textColor              android:textColor="@color/bt_text"             -> android:textColor="#FFFFFFFF"
  login.background+style       android:background="@drawable/login_btn_selector" -> android:textStyle="bold" android:background="#FF2F6FED"
  login.height                 android:layout_height="@dimen/dp40"            -> android:layout_height="52.0dip"
  login.text                   android:text="@string/login"                   -> android:text="登 录"
  agreement.marginTop          android:layout_marginTop="@dimen/dp12"         -> android:layout_marginTop="16.0dip"
  privacy.textColor            android:textColor="@color/c_a3a3a3"            -> android:textColor="#FF9AA3B2"
  decoded xml 8915 B -> 9777 B
=== root children after edit: 6
    LinearLayout                                         
    TextView                                             
    TextView                                             
    View                                                 
    TextView                                             @id/tv_bind_phone_desc
    androidx.constraintlayout.widget.ConstraintLayout    
  id @id/et_phone               x1 OK
  id @id/et_phone_code          x1 OK
  id @id/get_phone_code         x1 OK
  id @id/layout_phone_code      x1 OK
  id @id/login                  x1 OK
  id @id/ll_container_login     x1 OK
  id @id/agreement_layout       x1 OK
  id @id/iv_close               x1 OK
  id @id/iv_back                x1 OK

=== java -jar /opt/ba-tools/apktool.jar b -s -f -o /root/ba_work/v4_layout_build.apk /root/ba_work/dec4 ===
I: Using Apktool 2.11.1 on v4_layout_build.apk with 8 threads
I: Building resources with aapt2...
I: Building apk file...
I: Importing unknown files...
I: Built apk into: /root/ba_work/v4_layout_build.apk

=== throw-away build apk: 872 entries
  has classes.dex   : False
  has classes2.dex  : False
  has resources.arsc: True
  res/layout/fragment_default_mobile_code_login.xml -> /root/ba_work/v4_layout.axml  8208 B  sha256=f614865a97955515e41e2248af0b6004f7eefdea3d2fbd0897285d226cb189b3
```


### 11.2 组包 + 重签（`build_noroot_apk.py`）

```
==========================================================================
 BA 国服免 root 改造
 src : work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk (1.98 GB)
 out : work\ba\apk_patch\out\v4_login.apk
==========================================================================
[*] 源包身份: package=com.RoamingStar.BlueArchive versionCode=73 versionName=3.0.2 minSdk=24 targetSdk=33 nsc=0x7F120001
[*] 签名证书 SHA-256 = 94FA997BE0DEBB69F1C62D766664FA8A879839DC9F710F6EEBD0C413DEE99EBC
[1] res/Dk.xml: 560 B -> 560 B  (ca_mode=user)
[2] 跳过（未给 --sdk-url）
[2b] 跳过 GameMainConfig（未给 --gmconfig-url / --asset-replace）
[2c] res/Q9.xml: 7292 B -> 8208 B  (--asset-replace work\ba\apk_patch\v4\res_Q9_v4.axml)
[6] 剔除旧签名 META-INF/MANIFEST.MF (5151246 B)
[6] 剔除旧签名 META-INF/CERT.SF (156 B)
[6] 剔除旧签名 META-INF/CERT.RSA (1208 B)
[5] resources.arsc 置第 1 条（align_mode=raw）
[5] resources.arsc: STORED 1156308 B，第 1 条
[*] 写入 41304 条目 -> work\ba\apk_patch\out\v4_login.apk.tmp
      8000/41304  593.20 MB
     16000/41304  981.57 MB
     24000/41304  1.30 GB
     32000/41304  1.58 GB
     40000/41304  1.85 GB
[6] v1: MANIFEST.MF 5151246 B / CERT.SF 156 B / CERT.RSA 1208 B
[*] 内容摘要 bab06e9f9153e6b40b879accca8a714265f3f133b3e093b9ff655b4d916edbde
[6] v2 1418 B + v3 1434 B，签名块共 2908 B @2123835232
[*] 写完 25.8s，1.98 GB
[*] 校验 work\ba\apk_patch\out\v4_login.apk (1.98 GB)
  EOCD entries=41307 cd_size=4133931 cd_offset=2123838140 comment=0
  APK Signing Block: OK @2123835232 (2900 B)
  content digest = bab06e9f9153e6b40b879accca8a714265f3f133b3e093b9ff655b4d916edbde
  v2: OK
  v3: OK
  zip 完整性: OK
  v2/v3 签名者证书 SHA-256 = 94FA997BE0DEBB69F1C62D766664FA8A879839DC9F710F6EEBD0C413DEE99EBC
  v1: MANIFEST.MF 5151246 B, 41304 个 Name 段
  v1: 最长行 70 B, 超 72 B 的行 0 个（OK）
      ...已验 20000 条
      ...已验 40000 条
  v1: 逐条摘要 41304 条, 不符 0, 条目缺失 0 OK
  v1: 未被 MANIFEST 覆盖的条目 0 个
  v1: META-INF 签名文件 3 个 [MANIFEST.MF, CERT.SF, CERT.RSA]
  v1: META-INF/CERT.SF SHA-256-Digest-Manifest OK（0 个逐条段）
  v1: X-Android-APK-Signed = '2, 3'（声明 [2, 3]，APK 实有 [2, 3]）
  v1: META-INF/CERT.RSA 对 .SF 的 PKCS#7 验签 OK
  v1: 签名者证书 SHA-256 = 94FA997BE0DEBB69F1C62D766664FA8A879839DC9F710F6EEBD0C413DEE99EBC
  v1: 签名者证书 SPKI 294 B
  v1 与 v2/v3 证书一致: OK
  v1 结论: OK
  STORED 4 字节对齐: OK
  重复条目: 无（OK）
  resources.arsc: 第 1 条, STORED=True, 4 字节对齐=True
  __tpinfo 残留: 无（OK）
  GameMainConfig: 5212 B, m_Script=1090 B, 字段 6/6
    SkipTutorial       = 'False'
    ServerInfoDataUrl  = '["https://example.com/api/state"]'
    ServerName         = 'prod'
    VersionCode        = '73'
    PlatformID         = '1'
    ChannelID          = '1'
  res/Dk.xml 解析：
    <network-security-config>
      <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
          <certificates src="system">
          </certificates>
          <certificates src="user">
          </certificates>
        </trust-anchors>
      </base-config>
    </network-security-config>

 输出 work\ba\apk_patch\out\v4_login.apk (1.98 GB)
 结果：OK
```


## 12. 运行时行为推理（为什么这样改还能登录）

### 12.1 需求① —— `code.length() != 6` 为什么能过

`DefaultMobileLoginFragment.handleLoginLink(Z)V` 的校验链（原始 dex，v4 未改；下面是**摘录**，省略了 `.line` 与空行）：

```smali
    # v3 = 卡密输入框的 trim 结果，v4 = 验证码输入框的 trim 结果
    iget-object v0, p0, ...->et_phone:Landroid/widget/EditText;
    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;
    move-result-object v0  -> toString() -> trim()  => v3

    iget-object v0, p0, ...->et_phone_code:Landroid/widget/EditText;
    invoke-virtual {v0}, Landroid/widget/EditText;->getText()Landroid/text/Editable;
    move-result-object v0  -> toString() -> trim()  => v4

    invoke-static {v3}, Landroid/text/TextUtils;->isEmpty(...)Z                # 空 -> "请输入手机号"
    invoke-static {v3}, Lcom/airi/common/utils/CommonUtil;->isPhoneLegal(...)Z
    invoke-static {v4}, Landroid/text/TextUtils;->isEmpty(...)Z                # 空 -> "请输入验证码"
    invoke-virtual {v4}, Ljava/lang/String;->length()I
    const/4 v1, 0x6
    if-eq v0, v1, :cond_3                                                     # !=6 -> "验证码格式不正确"
```

推理：

1. `android:text="000000"` 是 `TextView` 的**构造期属性** —— `EditText` 在 **inflate 时**就调用 `setText("000000")`，不需要用户操作，文本在 `initView()` 跑之前就已经在 `Editable` 里。
2. `handleLoginLink` 取的是 `et_phone_code.getText().toString().trim()`；`"000000".trim()` 还是 `"000000"`，`length()` = **6**，`0x6 == 0x6` → `if-eq` **不跳转** → 继续往下走。
3. `visibility="gone"` 只是"不画、不占位"，View 对象还在、`EditText` 实例还在，`getText()` 照样返回 `"000000"`。`gone` 不是 `removeView`，不影响 `findViewById`。
4. 我核对过**没有任何代码会清空这个字段**：整个 `DefaultMobileLoginFragment` 里 `setText` 只出现 **1 次**，是 `tv_privacy_agreement.setText(spannable)`；`et_phone_code` 只在 `initView` 里 `findViewById` 赋值、在 `addCodeListener()` 里挂了个 `OnEditorActionListener`（回车监听），**没有** `setText("")`、**没有** `TextWatcher`。（`ExtendEditText` 自身的 `setText` 只在"点清空按钮"时被调用。）
5. `maxLength="6"` 保留，`"000000"` 正好 6 位，`InputFilter.LengthFilter(6)` 不会截断；`inputType="number"` 也不会拒绝已有文本。

**结论：字段里真的躺着 6 个字符 `000000`，所以 `code.length()!=6` 这条永远不成立，链路能走到 `LoginManager.loginWithLink("mobile", 卡密, "000000", "", cb)`。**

### 12.2 需求② —— 界面文案

| 位置 | 原来 | 现在 |
|---|---|---|
| 卡密输入框 hint | `@string/hint_phone_number` = "请输入手机号" | **字面量 `"请输入卡密"`** |
| 页面标题 | 没有 | **新增 `"卡密登录"`**（21sp 加粗深色） |
| 页面副标题 | 没有 | **新增 `"无需验证码，输入卡密直接登录"`** |
| 验证码行 | "请输入验证码" + "发送" | 整行 `gone`（控件还在，只是不显示） |
| 登录按钮 | `@string/login` = "登录" | **字面量 `"登 录"`** |

### 12.3 需求③ —— 美化，以及四个"看着改了其实会被代码改回去"的坑

**坑 A：登录按钮的 `layout_marginTop` 会被 `initView()` 覆盖。** 原始代码（`initView`，`.line 106`~`.line 128`）：

```smali
    iget-object v0, p0, ...->login:Landroid/widget/Button;
    invoke-virtual {v0}, Landroid/widget/Button;->getLayoutParams()Landroid/view/ViewGroup$LayoutParams;
    ... check-cast MarginLayoutParams ...
    sget v4, Lcom/airi/common/R$dimen;->dp12:I            # 普通登录模式 -> 12dp（bind 模式 -> dp54）
    iput v1, v0, Landroid/view/ViewGroup$MarginLayoutParams;->topMargin:I
    invoke-virtual {v1, v0}, Landroid/widget/Button;->setLayoutParams(...)
```

也就是说：**XML 里给 Button 写多少 `layout_marginTop`，运行时都会被改成 `dp12`。** 所以"按钮上方多留空气"改成给父容器 `@id/ll_container_login` 加 `paddingTop="8.0dip"` —— 这个 View 在**全部 smali 里一次都没被引用**（`grep -rn ll_container_login` 只命中 `R$id` 常量），padding 不会被改。最终间距 = 8dip(padding) + 12dip(代码设的 margin) = 20dip。

**坑 B：`third_party_login` 的 `visibility` 由代码决定，XML 写 `gone` 没用。**

```smali
    .line 136
    iget-object v0, p0, ...->third_party_login:Landroid/view/ViewGroup;
    invoke-direct {p0}, ...->isHideAllBottomTap()Z
    if-eqz v1, :cond_8            # false -> cond_8 -> v2=VISIBLE(0)
    ...
    invoke-virtual {v0, v2}, Landroid/view/ViewGroup;->setVisibility(I)V
```

`one_login` / `taptap_login` 同理（`.line 134` / `.line 135`，按 `params.leftType/rightType` 设）。所以我**没有**给这条写 `gone`——写了也会被几毫秒后的 `initView()` 覆盖，只会让报告说谎。真要藏掉只有两条路：① 改 dex（红线禁止）；② 给 `third_party_login` 写 `layout_height="0.0dip"` 把高度压成 0（代码不碰它的 layout 参数）。这招我没用（不在需求里，且属于"结构把戏"），需要的话可以出 v5。

**坑 C：toast 文案改不了。** `"请输入手机号"` / `"验证码格式不正确"` 是 `R$string`，在 `resources.arsc` 里，按红线不许动。所以**页面**上写"卡密"，但用户手滑留空时弹的仍是"请输入手机号"。

**坑 D：`tv_privacy_agreement` 的颜色/重力会在运行时被代码覆盖。** `.line 238~240` 做了 `setText(spannable)` + `setGravity(0x11)` + `ForegroundColorSpan`，所以我这条 `@color/c_a3a3a3 → #FF9AA3B2` **大概率看不到效果**，留着无害。

### 12.4 ⚠️ 必须知道的硬约束：卡密仍然必须是"1 开头的 11 位数字"

`handleLoginLink` 第一道格式检查调 `CommonUtil.isPhoneLegal()`，它直接转调 `isChinaPhoneLegal()`：

```smali
.method public static isChinaPhoneLegal(Ljava/lang/String;)Z
    const-string v0, "^1\d{10}$"        # <= 就是这条正则
    invoke-static {v0}, Ljava/util/regex/Pattern;->compile(Ljava/lang/String;)Ljava/util/regex/Pattern;
    ... matcher(p0).matches()
.end method
```

这条正则**在 dex 里**，v4 不许改（红线）。所以：

- 卡密是 `1` 开头的 11 位纯数字 → 64 字符上限 + 格式校验都能过，登录链路正常。
- 卡密是 16 位字母数字 → 会弹 **"手机号格式不正确"** 并 `return`，**永远登不进去**。（v3 的 dex 补丁把这条改成 `^.{1,64}$`，那正是 v3 干的活；v4 是纯布局包，拿不到这个放宽。）
- 所以：如果你们的卡密不是手机号形状，v4 只能"看起来变了"，登录仍然过不去，那种情况必须回到 v3 路线。

## 13. 没把握的地方

1. **"真的变好看了"我无法证明**：本机没有真机/模拟器，`preview_v4.png` 是我用 PIL 按 dp 数值手绘的近似图（不是 Android 渲染），只能证明"几何关系和颜色是这些"，不能证明在你手机屏幕上好看。
2. **实色背景会丢圆角**：`android:background` 写颜色 → `ColorDrawable` → 直角矩形。所以输入框（浅蓝）和按钮（蓝）现在是**直角**，而卡片是圆角。要圆角必须新增/替换 drawable 资源（红线禁止）。
3. **按钮没有按下态了**：`@drawable/login_btn_selector` 被颜色替换，按下不变色、无涟漪。
4. **输入框的清空按钮仍在**：`app:clearButtonMode="whileEditing"` 是 `ExtendEditText` 自绘的，原来叠在白底+描边框里，现在背景变纯色块，图标对比度可能变差（无法目测）。
5. **纵向空间变紧**：卡片总高从 ~275dip 涨到 ~352dip（含 3rd-party 那条）。`layout_gravity="center"` 居中的卡片在 720p 及以下小屏应该仍能完整显示，但弹出输入法后（`adjustPan`）被顶的幅度会比原来大。
6. **`000000` 这个假验证码会被发给服务端**：`loginWithLink("mobile", 卡密, "000000", "", cb)`。如果私服后端只是忽略 `code`（或只判长度）就没问题；如果后端真拿它和短信验证码比对，就会登录失败。这一点客户端侧无法证明。
7. **`login_bg_fragment` 不能换**：它是 `res/drawable/login_bg_fragment.xml`（shape：`@color/c_ffffff` + `@dimen/radius_common_dialog` 圆角），被 `fragment_user_center` / `fragment_pay` / `fragment_net_check` 等 20+ 个布局共用。所以"可选加分项：换登录页背景图"我**没有做**——它不是图片（是 shape），且替换会连带改掉其它页面。
8. **会不会"一眼看出不一样"**：我赌的是 ①标题区（21sp 加粗深蓝 + 副标题 + 细分割线）②只剩一个输入框③一颗 52dip 的亮蓝实色按钮。这三点与 v2 的"只改字号间距"是量级差别；但最终观感只有你上机说了算。

## 14. 复现命令

```bash
# 0) 前提：WSL ext4 上有 /root/ba_work/dec0（apktool 从原包解出的资源树）
# 1) 改解码 XML -> apktool b -s（不汇编 smali，产物里没有 dex）-> 只取那一份 AXML
wsl -e bash -lc 'cd /root/ba_work && python3 /mnt/c/.../v4/make_layout_v4.py /root/ba_work/v4_layout.axml'
cp /root/ba_work/v4_layout.axml "work\ba\apk_patch\v4\res_Q9_v4.axml"
# 2) 组包（基线原包 + 只替换 res/Q9.xml，重签 v1/v2/v3）
python work\ba\noroot\build_noroot_apk.py \
  --src    work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk \
  --out    work\ba\apk_patch\out\v4_login.apk \
  --keystore work\ba\noroot\ba_private.keystore --storepass baserver --alias ba \
  --asset-replace res/Q9.xml=work\ba\apk_patch\v4\res_Q9_v4.axml
# 3) 自检
wsl -e bash -lc 'cd "/mnt/c/.../v4" && python3 selftest_v4.py'
# 4) 近似预览图（需要带 Pillow 的 python）
python work\ba\apk_patch\v4\preview.py
```

## 15. 证据文件清单

- `work\ba\apk_patch\v4\make_layout_v4.py`
- `work\ba\apk_patch\v4\make_layout_v4.log`
- `work\ba\apk_patch\v4\res_Q9_v4.axml`
- `work\ba\apk_patch\v4\build_v4.log`
- `work\ba\apk_patch\v4\selftest_v4.py`
- `work\ba\apk_patch\v4\selftest_console.txt`
- `work\ba\apk_patch\v4\selftest_v4_out.txt`
- `work\ba\apk_patch\v4\zipdiff_v4.json`
- `work\ba\apk_patch\v4\layout_xml.diff`
- `work\ba\apk_patch\v4\v4_axml_dump.txt`
- `work\ba\apk_patch\v4\aapt_xmltree_v4.txt`
- `work\ba\apk_patch\v4\preview.py`
- `work\ba\apk_patch\v4\preview_v4.png`
- `work\ba\apk_patch\v4\build_report_v4.py`
