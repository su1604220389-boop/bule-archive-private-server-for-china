# SELFTEST_v5 — `v5_login.apk`（v4 + 把「游客登录 / 卡密登录」两个入口加回来）

> 本文件由 `work\ba\apk_patch\v5\build_report_v5.py` 生成。下面每一段"原始输出"都是
> **从磁盘上的日志文件原样贴进来的**（`selftest_v5_out.txt` / `build_v5.log` /
> `make_layout_v5.log` / `ev_index_safety.txt` / `ev_xmltree.txt` / `zipdiff_v5.json`），
> 没有一个数字是手抄的。

## 0. 一句话结论

| 项 | 结果 |
|---|---|
| 产物 | `work\ba\apk_patch\out\v5_login.apk` |
| 体积 / SHA-256 | `2,127,972,945` B / `7ae11fd0bb31108dabf616662eb8f5314002b9882e29188007c25bced0303db7` |
| `resources.arsc` | sha256 `cd8943ae979fd434…` == 规范常量 ✅ |
| `classes.dex` | sha256 `56b3a73b3039db99…` == v4 ✅（**一个字节没动**） |
| `classes2.dex` / `AndroidManifest.xml` | == v4 逐字节 ✅ |
| `aapt dump badging` v5 vs v4 | **diff 0 行** ✅ |
| zip 条目 diff v5 vs v4 | 只有 `res/Q9.xml` + `META-INF/*` ✅ |
| `apksigner verify` | v1/v2/v3 全过，证书与 v4 同一张 `94FA997BE0DEBB69…` ✅ |
| 新控件 | `RadioGroup` + 2×`RadioButton`，**零 id、零新资源、只 XML 字面量** |
| 插入位置 | root child **index 1**（header 下 / 标题上）；消费方 **0 处 `getChildAt`** → 索引安全 |

## 1. 交付物

| # | 路径 | 大小 | sha256 |
|---|---|---|---|
| 1 | `work\ba\apk_patch\out\v5_login.apk` | 2,127,972,945 B | `7ae11fd0bb31108dabf616662eb8f5314002b9882e29188007c25bced0303db7` |
| 2 | `work\ba\apk_patch\v5\res_Q9_v5.axml`（`res/Q9.xml` 的 AXML 源） | 9,060 B | `e8096feacfdc5411c4ed65fce2bd75188ecd8dbb6db4dd92d48f551e52437918` |
| 3 | `work\ba\apk_patch\v5\preview_v5.png`（**近似图**） | 157,358 B | — |
| 4 | `work\ba\apk_patch\v5\SELFTEST_v5.md`（本文件） | — | — |

* 包里 `res/Q9.xml` 这一条与磁盘上的 `res_Q9_v5.axml` **同一个 sha256**（`e8096feacfdc5411c4ed65fce2bd75188ecd8dbb6db4dd92d48f551e52437918`），
  即"进包的就是我编译出来的那一份"，不是别的副本。

## 2. `resources.arsc` —— 逐字节不变（原始输出）

（`## 0)` 包体 SHA-256 / `## 1)` 四件套对比表的原始输出全文见 §12 附录 A。）

从附录 A 摘出的关键行：

> * v1     2,127,971,177 B  sha256 = `5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6`
> * v4     2,127,972,093 B  sha256 = `6490fcfc772f4dc6dd1773e7999a491775a646b08675591204b18212ee94eddb`
> * v5     2,127,972,945 B  sha256 = `7ae11fd0bb31108dabf616662eb8f5314002b9882e29188007c25bced0303db7`
> * v5 `resources.arsc` sha256 = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`
> * 规范常量                  = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`
> * => **一致 ✅**
> * `classes.dex` sha256 = `56b3a73b3039db99ade67faf42e471c8de4dcd7127ce9bef49d9f4d473c27651`
> * `classes2.dex` sha256 = `dca6f88a614fd7666842eed9d11d3f6bf9c842e381b80a63a330cbb78c93a7b4`
> * `AndroidManifest.xml` sha256 = `9a07ec83802b9b6fc08582b9429d9649775fe8627c35be419a3b851f1ffaca11`

* **`resources.arsc` sha256 = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`**，与规范常量**一模一样** ✅
* 也就是说：`res/Q9.xml` 里既没有新增资源 id，也没有引用新的 `@drawable/@color/@style`，
  资源表连一个字节都没被重写（apktool 全程只在**一次性构建包**里折腾资源，
  最终包是拿**原包**做底、只替换 `res/Q9.xml` 这一条得到的）。

## 3. `classes.dex` / `classes2.dex` / `AndroidManifest.xml` —— 与 v4 逐字节相同

| entry | v4 sha256 | v5 sha256 | 相同 |
|---|---|---|---|
| `classes.dex` | `56b3a73b3039db99…` (9,327,708 B) | `56b3a73b3039db99…` (9,327,708 B) | ✅ |
| `classes2.dex` | `dca6f88a614fd766…` (10,158,904 B) | `dca6f88a614fd766…` (10,158,904 B) | ✅ |
| `AndroidManifest.xml` | `9a07ec83802b9b6f…` (50,552 B) | `9a07ec83802b9b6f…` (50,552 B) | ✅ |

* `classes.dex` 全量 sha256 = `56b3a73b3039db99ade67faf42e471c8de4dcd7127ce9bef49d9f4d473c27651`
  * 与 v4 常量**完全一致**，与最原始重签包 v1 也一致 → **v5 没有碰 dex，一个字节都没有**。
* `classes2.dex` 全量 sha256 = `dca6f88a614fd7666842eed9d11d3f6bf9c842e381b80a63a330cbb78c93a7b4`
* `AndroidManifest.xml` 全量 sha256 = `9a07ec83802b9b6fc08582b9429d9649775fe8627c35be419a3b851f1ffaca11`
* 三个值同时等于 v1 / v4 / v5（附录 A 表格里 `v1==v4==v5` 那一列全 ✅）。

## 4. `aapt dump badging` —— v5 vs v4，diff = 0 行

> aapt dump badging v4 -> exit 0, 176 行, 存 `badging_v4.txt`
> aapt dump badging v5 -> exit 0, 176 行, 存 `badging_v5.txt`
> diff 行数 = **0**  ✅

`badging_v4.txt` / `badging_v5.txt` 各 176 行，落在 `work\ba\apk_patch\v5\` 下可以自己 diff。
**资源表没变 → 任何 badging 字段都不可能变**，包括 versionCode / sdkVersion /
uses-permission / locales / launchable-activity。

## 5. zip 条目 diff（v5 vs v4）—— 只有 `res/Q9.xml` + `META-INF/*`

```
$ python selftest_v5.py   # 节选：zip 条目 diff 段
* v4 条目数 = 41307, v5 条目数 = 41307
* only in v4 : []
* only in v5 : []
* 内容有差异的条目 (4) :
    * `META-INF/CERT.RSA`: 1208 B (csize 1208, crc 1695B469) -> 1208 B (csize 1208, crc DFABF9FF)
    * `META-INF/CERT.SF`: 156 B (csize 156, crc 0F1F824B) -> 156 B (csize 156, crc 33751D4E)
    * `META-INF/MANIFEST.MF`: 5151246 B (csize 5151246, crc 66FC9768) -> 5151246 B (csize 5151246, crc A2A65A5E)
    * `res/Q9.xml`: 8208 B (csize 8208, crc 05500E69) -> 9060 B (csize 9060, crc AFFDF261)
* 只允许 `res/Q9.xml` + `META-INF/*` 变化 -> ✅
* v5 内 `res/Q9.xml` : 9060 B, sha256 = `e8096feacfdc5411c4ed65fce2bd75188ecd8dbb6db4dd92d48f551e52437918`（磁盘上的 res_Q9_v5.axml sha256 = `e8096feacfdc5411c4ed65fce2bd75188ecd8dbb6db4dd92d48f551e52437918`）
```

* 两包条目数都是 **41307**，没有多一条、少一条（`only in v4/v5 = []`）。
* 内容发生变化的只有 **4 条**：`res/Q9.xml`（本次要做的事）+ `META-INF/` 那 3 个签名文件
  （签名必然变，因为包体变了）。
* `res/Q9.xml` 在 v4/v5 里都是 **STORED**（`csize == size`），所以包体只涨 `9060-8208 = 852 B`，
  与实测 `+852 B` 对得上 —— 说明没有夹带任何压缩器层面的副作用。
* 机器结论：`✅ 通过`

## 6. `apksigner verify` —— 通过，并且和 v4 是同一张证书

### v5_login.apk

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

### v4_login.apk（对照）

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

* 两个包的证书 SHA-256 行**逐字符相同**：`94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc`
* 与 v1（原始重签包）也是同一张 → 覆盖安装不会因为"签名不一致"被系统拒绝。
* `Verified using v1 scheme: false` 与 v4 **完全一致**（原包本来就是这个形态：
  MANIFEST.MF 有、但没有 per-entry section，所以 apksigner 按 v2/v3 认定；
  v4 上机可用，v5 与它一致，不是本次引入的差异）。

## 7. 两个入口：最终位置 + 实现

### 7.1 位置

卡片（root `LinearLayout`，竖向）里的 **第 2 个子节点**（index 1），紧贴 header 行下方、
`卡密登录` 大标题上方 —— 视觉上就是"先选入口，再看内容"的分段条：

```
┌──────────────────────────────── 卡片 328dip ─┐
│ ‹        BLUE ARCHIVE              ✕        │  header（原包，未动）
│ ┌────────────────────────────────────────┐ │
│ │  ◉ 游客登录        ○ 卡密登录          │ │  ← 本次新增（#FFF1F5FC 底条，44dip 高）
│ └────────────────────────────────────────┘ │
│                卡密登录                      │  v4 标题（21sp 加粗，未动）
│        无需验证码，输入卡密直接登录            │  v4 副标题（12sp，未动）
│ ─────────────────────────────────────────── │  v4 分隔线（未动）
│ ┌────────────────────────────────────────┐ │
│ │ 请输入卡密                              │ │  v4 输入框（52dip 浅蓝实底，未动）
│ └────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────┐ │
│ │                 登 录                   │ │  v4 按钮（#FF2F6FED，52dip，未动）
│ └────────────────────────────────────────┘ │
│ ☐ 用户协议与隐私政策                        │
└──────────────────────────────────────────────┘
```

选择理由：用户给的第一建议就是"标题上方"；放在标题上方 = 分段条 + 页面标题的常规组合，
而且不用把 v4 的标题/副标题/分隔线拆掉（任务要求"美化部分全部保留"）。
v4 的每一个节点都原地保留，本次**只做加法**。

### 7.2 XML 片段（源形态，解码 XML 风格）

```xml
<RadioGroup android:orientation="horizontal" android:gravity="center_vertical"
    android:background="#FFF1F5FC"
    android:paddingLeft="4.0dip" android:paddingTop="2.0dip"
    android:paddingRight="4.0dip" android:paddingBottom="2.0dip"
    android:layout_width="fill_parent" android:layout_height="wrap_content"
    android:layout_marginLeft="24.0dip" android:layout_marginTop="10.0dip"
    android:layout_marginRight="24.0dip">
    <RadioButton android:textSize="15.0sp" android:textColor="#FF2B3445"
        android:gravity="center" android:buttonTint="#FF2F6FED"
        android:layout_width="0.0dip" android:layout_height="40.0dip"
        android:layout_weight="1.0" android:text="游客登录"
        android:checked="true" />
    <RadioButton android:textSize="15.0sp" android:textColor="#FF2B3445"
        android:gravity="center" android:buttonTint="#FF2F6FED"
        android:layout_width="0.0dip" android:layout_height="40.0dip"
        android:layout_weight="1.0" android:text="卡密登录" />
</RadioGroup>
```

实际写进文件时和 v4 一致是**单行**的（apktool 解码出来的 XML 本来就一行一个节点），
上面为了可读性换了行，标签与属性顺序完全没变。

### 7.3 逐条对照任务要求

| 要求 | 实现 | 证据 |
|---|---|---|
| 用 `RadioGroup` + 2×`RadioButton` | 就是这两个类，框架自带，dex 里没引用新的类 | AXML `E: RadioGroup` / `E: RadioButton` ×2（§8.2 原文） |
| `android:text` 写字面量 | `"游客登录"` / `"卡密登录"` | AXML 里就是明文字符串：`android:text(0x0101014f)="游客登录" (Raw: "游客登录")`，不是 `@string/…` |
| 默认选中第一个 | `android:checked="true"` 在**第 1 个** RadioButton 上 | `(type 0x12)0xffffffff` = true |
| 不写 `android:id` | 3 个新节点全都没有 `android:id` | `id=None`（脚本断言）+ AXML 里 0 个 `android:id` |
| 视觉上明显 | 280dip 宽浅蓝底条 + 15sp 深灰字 + `#FF2F6FED` 蓝色圆点/圆环 | `buttonTint=(type 0x1c)0xff2f6fed` |
| 不用代码切换提示 | 没有任何 dex 改动 | `classes.dex` sha256 == v4 |

* `buttonTint` 是**框架属性** `android.R.attr.buttonTint`（AXML 里 id `0x0101046f`，API 21+，
  本包 minSdk=24），只引用框架资源表，不需要在 `resources.arsc` 里新增任何条目 —— 这也是
  资源表 sha256 一点没变的原因之一。
* 静态 `buttonTint` 的副作用（已核对框架 drawable）：`btn_radio_off_mtrl` 只有外圈
  （`dot_group` 的 `scaleX/scaleY=0`），`btn_radio_on_mtrl` 才画出内点。所以
  **未选中 = 蓝色空圈，选中 = 蓝色圈 + 蓝色实心点**，两者能分辨。

## 8. 最终子节点顺序表 + 索引安全性判断

### 8.1 顺序表（root `LinearLayout` 的直接子节点）

| index | v5 节点 | 是什么 | v4 时的 index |
|---|---|---|---|
| 0 | `LinearLayout` | header 行：`@id/iv_back` + logo + `@id/iv_close` | 0 |
| **1** | **`RadioGroup`** | **本次新增：游客登录 / 卡密登录 二选一（无 id）** | —（不存在） |
| 2 | `TextView` | v4 标题「卡密登录」21sp 加粗 | 1 |
| 3 | `TextView` | v4 副标题「无需验证码，输入卡密直接登录」12sp | 2 |
| 4 | `View` | v4 分隔线 1dip `#FFE7ECF5` | 3 |
| 5 | `TextView` `@id/tv_bind_phone_desc` | 原包就有的绑定说明（`gone`） | 4 |
| 6 | `ConstraintLayout` | 输入区：`@id/et_phone`、`@id/layout_phone_code`(`gone`)、`@id/ll_container_login`(`@id/login`)、`@id/agreement_layout`、`@id/third_party_login` | 5 |

**净效果：v4 的 index 1..5 各 +1（因为 index 1 被新节点占了），index 0 不动。**

### 8.2 原始输出：从编译后的 AXML 里数出来的（不是从源码 XML 数的）

```
### v4 (throw-away build apk) -- root children, aapt dump xmltree
$ aapt dump xmltree v4_layout_build.apk res/layout/fragment_default_mobile_code_login.xml | grep "^      E: "
12:      E: LinearLayout (line=4)
47:      E: TextView (line=12)
58:      E: TextView (line=13)
68:      E: View (line=14)
75:      E: TextView (line=15)
86:      E: androidx.constraintlayout.widget.ConstraintLayout (line=16)

### v5 (throw-away build apk) -- root children
$ aapt dump xmltree v5_layout_build.apk res/layout/fragment_default_mobile_code_login.xml | grep "^      E: "
12:      E: LinearLayout (line=4)
47:      E: RadioGroup (line=12)
79:      E: TextView (line=16)
90:      E: TextView (line=17)
100:      E: View (line=18)
107:      E: TextView (line=19)
118:      E: androidx.constraintlayout.widget.ConstraintLayout (line=20)

### v5 -- the new RadioGroup block, raw attributes as compiled into the AXML
$ aapt dump xmltree v5_layout_build.apk res/layout/fragment_default_mobile_code_login.xml | sed -n "47,78p"
      E: RadioGroup (line=12)
        A: android:gravity(0x010100af)=(type 0x11)0x10
        A: android:orientation(0x010100c4)=(type 0x10)0x0
        A: android:background(0x010100d4)=(type 0x1c)0xfff1f5fc
        A: android:paddingLeft(0x010100d6)=(type 0x5)0x401
        A: android:paddingTop(0x010100d7)=(type 0x5)0x201
        A: android:paddingRight(0x010100d8)=(type 0x5)0x401
        A: android:paddingBottom(0x010100d9)=(type 0x5)0x201
        A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
        A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
        A: android:layout_marginLeft(0x010100f7)=(type 0x5)0x1801
        A: android:layout_marginTop(0x010100f8)=(type 0x5)0xa01
        A: android:layout_marginRight(0x010100f9)=(type 0x5)0x1801
        E: RadioButton (line=13)
          A: android:textSize(0x01010095)=(type 0x5)0xf02
          A: android:textColor(0x01010098)=(type 0x1c)0xff2b3445
          A: android:gravity(0x010100af)=(type 0x11)0x11
          A: android:layout_width(0x010100f4)=(type 0x5)0x1
          A: android:layout_height(0x010100f5)=(type 0x5)0x2801
          A: android:checked(0x01010106)=(type 0x12)0xffffffff
          A: android:text(0x0101014f)="游客登录" (Raw: "游客登录")
          A: android:layout_weight(0x01010181)=(type 0x4)0x3f800000
          A: android:buttonTint(0x0101046f)=(type 0x1c)0xff2f6fed
        E: RadioButton (line=14)
          A: android:textSize(0x01010095)=(type 0x5)0xf02
          A: android:textColor(0x01010098)=(type 0x1c)0xff2b3445
          A: android:gravity(0x010100af)=(type 0x11)0x11
          A: android:layout_width(0x010100f4)=(type 0x5)0x1
          A: android:layout_height(0x010100f5)=(type 0x5)0x2801
          A: android:text(0x0101014f)="卡密登录" (Raw: "卡密登录")
          A: android:layout_weight(0x01010181)=(type 0x4)0x3f800000
          A: android:buttonTint(0x0101046f)=(type 0x1c)0xff2f6fed
```

### 8.3 有没有代码按索引取子节点？—— 逐条查了，没有

这个布局只有一个消费方（`DefaultMobileLoginFragment`，`0x7f0b0044`），先把证据全文放这里：

```
### 1) which classes reference R.layout.fragment_default_mobile_code_login
$ grep -rn fragment_default_mobile_code_login smali smali_classes2
smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali:253:    sget v0, Lcom/airi/official/core/R$layout;->fragment_default_mobile_code_login:I
smali/com/airi/official/core/R$layout.smali:55:.field public static final fragment_default_mobile_code_login:I = 0x7f0b0044
smali/com/RoamingStar/BlueArchive/R$layout.smali:153:.field public static final fragment_default_mobile_code_login:I = 0x7f0b0044
smali_classes2/com/unity3d/player/R$layout.smali:153:.field public static final fragment_default_mobile_code_login:I = 0x7f0b0044

### 2) the consumer class itself
$ grep -n '^\.class\|^\.super' smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
1:.class public Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;
2:.super Lcom/airi/official/core/base/AbsFragment;
$ wc -l smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
1593 smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali

### 3) getChildAt / getChildCount in the consumer  (0 hits = no index dependency)
$ grep -c getChildAt smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
0
$ grep -c getChildCount smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
0
$ grep -n 'getChildAt\|getChildCount' smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali   # empty output = 0 hits

### 4) every view id the consumer touches (all id-based, no indices)
$ grep -o 'R$id;->[a-z_0-9]*' smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali | sort -u
R$id;->agreement_layout
R$id;->et_phone
R$id;->et_phone_code
R$id;->get_phone_code
R$id;->iv_back
R$id;->iv_close
R$id;->iv_privacy_agreement_select
R$id;->login
R$id;->login_helper
R$id;->one_login
R$id;->taptap_login
R$id;->third_party_login
R$id;->tv_bind_phone_desc
R$id;->tv_privacy_agreement

### 5) who instantiates the fragment (no subclass exists)
$ grep -rn "new-instance.*DefaultMobileLoginFragment;" smali smali_classes2
smali/com/airi/official/core/ui/fragment/FragmentCommonUtils.smali:94:    new-instance v0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;
$ grep -rn "extends.*DefaultMobileLoginFragment" smali smali_classes2   # empty = no subclass

### 6) every getChildAt caller inside the app packages (none of them touch this layout)
$ grep -rn getChildAt smali/com/airi smali/com/RoamingStar smali_classes2/com | grep -v "okhttp\|unity3d\|androidx"
smali/com/airi/common/utils/WebviewKeyboardUtils.smali:33:    invoke-virtual {p1, v0}, Landroid/widget/FrameLayout;->getChildAt(I)Landroid/view/View;
smali/com/airi/common/widget/ReboundScrollView.smali:458:    invoke-virtual {p0, v0}, Lcom/airi/common/widget/ReboundScrollView;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/PrivacyDialogActivity.smali:805:    invoke-virtual {v0, v3}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/LoginAuthActivity.smali:1366:    invoke-virtual {p1, v0}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/utils/m.smali:19:    invoke-virtual {p1, v0}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/utils/m.smali:80:    invoke-virtual {p0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/utils/m.smali:439:    invoke-virtual {v2, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/utils/m.smali:671:    invoke-virtual {v2, v3}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/TagFlowLayout.smali:385:    invoke-virtual {p0, v1}, Lcom/taptap/sdk/flowlayout/TagFlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/TagFlowLayout.smali:582:    invoke-virtual {p0, v1}, Lcom/taptap/sdk/flowlayout/TagFlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/TagFlowLayout.smali:684:    invoke-virtual {p0, v3}, Lcom/taptap/sdk/flowlayout/TagFlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/FlowLayout.smali:228:    invoke-virtual {p0, p4}, Lcom/taptap/sdk/flowlayout/FlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/FlowLayout.smali:646:    invoke-virtual {v0, v6}, Lcom/taptap/sdk/flowlayout/FlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/TagView.smali:54:    invoke-virtual {p0, v0}, Lcom/taptap/sdk/flowlayout/TagView;->getChildAt(I)Landroid/view/View;
smali_classes2/com/tencent/open/TDialog$1.smali:68:    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/tencent/connect/avatar/ImageActivity.smali:1117:    invoke-virtual {v0, v1}, Landroid/widget/LinearLayout;->getChildAt(I)Landroid/view/View;
```

结论三句话：

1. **消费方 0 处 `getChildAt` / `getChildCount`**（`grep -c` 都是 `0`），1593 行 smali 里
   所有视图访问都是 `R$id;->…` → `findViewById`，共 14 个 id，全是 id 寻址，跟顺序无关。
2. **没有子类**（`grep -rn "extends.*DefaultMobileLoginFragment"` 空），唯一实例化点是
   `FragmentCommonUtils.smali:94` 的 `new-instance`，没有第三方代码能绕进去按索引摸这个树。
3. 应用层其它 `getChildAt` 调用点（§8.3 第 6 段）分别属于 `WebviewKeyboardUtils`、
   `ReboundScrollView`、华为 `gatewayauth`、TapTap `flowlayout`、腾讯 open SDK —— 它们只
   操作自己 inflate 的视图树，**没有一处碰这个登录卡片的 root**。

**判断：这次插入位置是安全的。**

对照任务里提到的历史风险（"v2 时代曾有过 RadioGroup 在 index 2 的设计"）：v4 基线里没有
任何按索引取子节点的代码，v5 也没引入；即便将来有人写 `getChildAt(1)`，现在拿到的是
新增的 RadioGroup 而不是原来的标题 —— 这正是"只要有人按索引访问就危险"的原因，
所以我把这条写进 §11 的不确定性里：**改布局的人以后不能再加按索引的代码**。

## 9. 近似预览图

`work\ba\apk_patch\v5\preview_v5.png`（1326×986）—— **这是近似图，不是 Android 渲染**。

* 左：v4（当前包，没有入口）；右：v5（本次，两个入口回来了），带 4 个编号标注。
* 画法沿用 v4 的 `preview.py`（PIL 手绘），坐标按 AXML 里的 dp 值、字号按 sp 值、
  颜色按字面量 `#FFRRGGBB` 代入。
* 图上已写明「近似图：PIL 手绘，非 Android 真实渲染」。
* **不能证明**：真机字体度量、RadioButton 圆圈的实际尺寸（框架 vector 是 32dp 视口）、
  系统字体缩放、圆角阴影、以及被输入法顶起后的观感。

## 10. 复现命令（整条链路）

```bat
:: 0) 前提：WSL ext4 上有 /root/ba_work/dec0（apktool 从原包解出的资源树）

:: 1) 生成 v5 AXML：调 v4 的 edit() 原封不动重放，再插入新控件
wsl -e bash -lc "cd /root/ba_work && python3 '/mnt/c/.../v5/make_layout_v5.py' /root/ba_work/v5_layout.axml"

:: 2) 取 AXML 落到 Windows 侧
wsl -e bash -lc "cp /root/ba_work/v5_layout.axml '/mnt/c/.../v5/res_Q9_v5.axml'"

:: 3) 组包：原包做底，只替换 res/Q9.xml，重签 v1/v2/v3
python work\ba\noroot\build_noroot_apk.py ^
  --src    work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk ^
  --out    work\ba\apk_patch\out\v5_login.apk ^
  --keystore work\ba\noroot\ba_private.keystore --storepass baserver --alias ba ^
  --asset-replace res/Q9.xml=work\ba\apk_patch\v5\res_Q9_v5.axml

:: 4) 自检（Windows python，内部 shell 出去调 WSL 的 aapt / apksigner）
python work\ba\apk_patch\v5\selftest_v5.py

:: 5) 近似预览图（需要 Pillow）
python work\ba\apk_patch\v5\preview_v5.py

:: 6) 本报告
python work\ba\apk_patch\v5\build_report_v5.py
```

**没有用到的步骤**：没有 `apktool b` 出的 dex、没有 `zipalign`、没有 `jarsigner`、
没有重编译 `resources.arsc`、没有改 `AndroidManifest.xml`。

## 11. 我没把握的地方

### 11.1 主要一处：RadioGroup 不用 id 时，**第一次**点「卡密登录」可能两个都显示成选中

AOSP `RadioGroup` 的互斥是这么实现的（按 AOSP 源码写的，**没在本机核对这台 ROM 的 framework 实现**，所以下面对这条也只能算理论推断）：

```java
// 子控件没有 id 时，RadioGroup 会自动补一个 View.generateViewId()
public void onChildViewAdded(View parent, View child) {
    if (child instanceof RadioButton) {
        int id = child.getId();
        if (id == View.NO_ID) { id = View.generateViewId(); child.setId(id); }
        ((RadioButton) child).setOnCheckedChangeWidgetListener(mChildOnCheckedChangeListener);
    }
}
// 点击时"把上一个取消"依赖 mCheckedId
public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
    if (mProtectFromCheckedChange) return;
    mProtectFromCheckedChange = true;
    if (mCheckedId != -1) setCheckedStateForView(mCheckedId, false);   // <= 关键
    mProtectFromCheckedChange = false;
    setCheckedId(buttonView.getId());
}
```

问题在于：`android:checked="true"` 是在 **RadioButton 构造时**就生效的，那时它还没被
`addView` 进 RadioGroup，监听器还没挂上，所以 `mCheckedId` 一直是 `-1`；
`onFinishInflate()` 只在 `android:checkedButton`（需要 id）给了值时才补这一课。
⇒ **理论上**第一次点第二个选项时 `mCheckedId == -1`，前一个不会被取消，两个圆点会同时亮起；
再点一次就自己恢复正常（此后 `mCheckedId` 有值了）。

这台机器上没有真机/模拟器，**我没有实测**，所以只能如实说这是理论推断。
若你要彻底消掉它，代价是加两个**框架** id（不是 `@+id`、不新增资源条目）：

```xml
<!-- 只改这两行属性，资源表仍然不变 -->
<RadioGroup ... android:checkedButton="@android:id/text1">
    <RadioButton android:id="@android:id/text1" ... android:checked="true" />
    <RadioButton android:id="@android:id/text2" ... />
</RadioGroup>
```

我**没有**这么做，因为你明确要求"不要写 `android:id`"，而且 `@android:id/text1` 是框架
公共 id，`findViewById(android.R.id.text1)` 在某些框架代码里会被命中，属于另一种风险。
现在的选择是：**严格遵守"不写 id"，接受这个只影响第一次点击、且立刻自愈的显示瑕疵**。

### 11.2 次要几条（一并交代）

1. **卡片长高了 54dip**（v4 ≈ 352dip → v5 ≈ 406dip，含三方登录条）。小屏 + 输入法
   弹起（`adjustPan`）时被顶的幅度会比 v4 更明显，这一点只能上机看。
2. **`游客登录` 默认选中，但页面标题仍是「卡密登录」**、下面输入框 hint 还是「请输入卡密」——
   文字上有点自相矛盾。这是你给的两条硬要求直接撞出来的（默认选第一个 + 保留 v4 标题），
   不改 dex 无法让标题跟着选项变。想让默认选中变成「卡密登录」，只需把 `android:checked="true"`
   从左移到右边那个 RadioButton（一行改动，重新跑 §10 的 2~4 步）。
3. **两个选项点了不改变页面逻辑**：按你的要求它们纯展示。真要"切到游客登录就换页面"，
   必须有代码监听，也就是改 dex —— 红线内做不到。
4. **近似图不是渲染结果**（见 §9）。

## 12. 附录：原始输出全文

### 附录 A — `selftest_v5.py` 完整输出（`v5\selftest_v5_out.txt`）

```
# SELF-TEST v5_login.apk

* v5 (本次) : `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\out\v5_login.apk`
* v4 (基线) : `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\out\v4_login.apk`
* v1 (原包) : `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk`
* 布局源   : `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\v5\res_Q9_v5.axml`

## 0) 包体 SHA-256 / 字节数

* v1     2,127,971,177 B  sha256 = `5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6`
* v4     2,127,972,093 B  sha256 = `6490fcfc772f4dc6dd1773e7999a491775a646b08675591204b18212ee94eddb`
* v5     2,127,972,945 B  sha256 = `7ae11fd0bb31108dabf616662eb8f5314002b9882e29188007c25bced0303db7`

* v5 体积 = v4 2,127,972,093 B -> v5 2,127,972,945 B  (Δ +852 B)

## 1) `resources.arsc` / `classes.dex` / `classes2.dex` / `AndroidManifest.xml`

| entry | v1 sha256 | v4 sha256 | v5 sha256 | v1==v4==v5 |
|---|---|---|---|---|
| `resources.arsc` | `cd8943ae979fd434…` (1156308 B) | `cd8943ae979fd434…` (1156308 B) | `cd8943ae979fd434…` (1156308 B) | ✅ |
| `classes.dex` | `56b3a73b3039db99…` (9327708 B) | `56b3a73b3039db99…` (9327708 B) | `56b3a73b3039db99…` (9327708 B) | ✅ |
| `classes2.dex` | `dca6f88a614fd766…` (10158904 B) | `dca6f88a614fd766…` (10158904 B) | `dca6f88a614fd766…` (10158904 B) | ✅ |
| `AndroidManifest.xml` | `9a07ec83802b9b6f…` (50552 B) | `9a07ec83802b9b6f…` (50552 B) | `9a07ec83802b9b6f…` (50552 B) | ✅ |
| `res/Q9.xml` | `cc12543bbb5b977e…` (7292 B) | `f614865a97955515…` (8208 B) | `e8096feacfdc5411…` (9060 B) | ❌ |

* v5 `resources.arsc` sha256 = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`
* 规范常量                  = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`
* => **一致 ✅**

* `classes.dex` sha256 = `56b3a73b3039db99ade67faf42e471c8de4dcd7127ce9bef49d9f4d473c27651`
  * 与常量 `56b3a73b3039db99…` : 一致 ✅
* `classes2.dex` sha256 = `dca6f88a614fd7666842eed9d11d3f6bf9c842e381b80a63a330cbb78c93a7b4`
  * 与常量 `dca6f88a614fd766…` : 一致 ✅
* `AndroidManifest.xml` sha256 = `9a07ec83802b9b6fc08582b9429d9649775fe8627c35be419a3b851f1ffaca11`
  * 与常量 `9a07ec83802b9b6f…` : 一致 ✅

## 2) `aapt dump badging` —— v5 vs v4，diff 行数

* aapt dump badging v4 -> exit 0, 176 行, 存 `badging_v4.txt`
* aapt dump badging v5 -> exit 0, 176 行, 存 `badging_v5.txt`
* diff 行数 = **0**  ✅

## 3) zip 条目 diff（v5 vs v4）

* v4 条目数 = 41307, v5 条目数 = 41307
* only in v4 : []
* only in v5 : []
* 内容有差异的条目 (4) :
    * `META-INF/CERT.RSA`: 1208 B (csize 1208, crc 1695B469) -> 1208 B (csize 1208, crc DFABF9FF)
    * `META-INF/CERT.SF`: 156 B (csize 156, crc 0F1F824B) -> 156 B (csize 156, crc 33751D4E)
    * `META-INF/MANIFEST.MF`: 5151246 B (csize 5151246, crc 66FC9768) -> 5151246 B (csize 5151246, crc A2A65A5E)
    * `res/Q9.xml`: 8208 B (csize 8208, crc 05500E69) -> 9060 B (csize 9060, crc AFFDF261)
* 只允许 `res/Q9.xml` + `META-INF/*` 变化 -> ✅
* v5 内 `res/Q9.xml` : 9060 B, sha256 = `e8096feacfdc5411c4ed65fce2bd75188ecd8dbb6db4dd92d48f551e52437918`（磁盘上的 res_Q9_v5.axml sha256 = `e8096feacfdc5411c4ed65fce2bd75188ecd8dbb6db4dd92d48f551e52437918`）

## 4) `apksigner verify --verbose --print-certs`

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

### v5_login.apk  -> exit 0

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

* v5 证书 SHA-256 行 : `Signer #1 certificate SHA-256 digest: 94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc`
* v4 证书 SHA-256 行 : `Signer #1 certificate SHA-256 digest: 94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc`
* 与 v4 同一张证书 + 等于常量 94FA…EBC : ✅

---

**ALL CHECKS PASSED ✅**
```

### 附录 B — 组包原始日志（`v5\build_v5.log`，`build_noroot_apk.py` 的输出）

```
==========================================================================
 BA 国服免 root 改造
 src : work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk (1.98 GB)
 out : work\ba\apk_patch\out\v5_login.apk
==========================================================================
[*] 源包身份: package=com.RoamingStar.BlueArchive versionCode=73 versionName=3.0.2 minSdk=24 targetSdk=33 nsc=0x7F120001
[*] 签名证书 SHA-256 = 94FA997BE0DEBB69F1C62D766664FA8A879839DC9F710F6EEBD0C413DEE99EBC
[1] res/Dk.xml: 560 B -> 560 B  (ca_mode=user)
[2] 跳过（未给 --sdk-url）
[2b] 跳过 GameMainConfig（未给 --gmconfig-url / --asset-replace）
[2c] res/Q9.xml: 7292 B -> 9060 B  (--asset-replace work\ba\apk_patch\v5\res_Q9_v5.axml)
[6] 剔除旧签名 META-INF/MANIFEST.MF (5151246 B)
[6] 剔除旧签名 META-INF/CERT.SF (156 B)
[6] 剔除旧签名 META-INF/CERT.RSA (1208 B)
[5] resources.arsc 置第 1 条（align_mode=raw）
[5] resources.arsc: STORED 1156308 B，第 1 条
[*] 写入 41304 条目 -> work\ba\apk_patch\out\v5_login.apk.tmp
      8000/41304  593.20 MB
     16000/41304  981.57 MB
     24000/41304  1.30 GB
     32000/41304  1.58 GB
     40000/41304  1.85 GB
[6] v1: MANIFEST.MF 5151246 B / CERT.SF 156 B / CERT.RSA 1208 B
[*] 内容摘要 33f7db12da8570a171088d0c48be4af8f7f5aeb5ab7983b04ae9cafdf12ce40f
[6] v2 1418 B + v3 1434 B，签名块共 2908 B @2123836084
[*] 写完 24.9s，1.98 GB
[*] 校验 work\ba\apk_patch\out\v5_login.apk (1.98 GB)
  EOCD entries=41307 cd_size=4133931 cd_offset=2123838992 comment=0
  APK Signing Block: OK @2123836084 (2900 B)
  content digest = 33f7db12da8570a171088d0c48be4af8f7f5aeb5ab7983b04ae9cafdf12ce40f
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

 输出 work\ba\apk_patch\out\v5_login.apk (1.98 GB)
 结果：OK
```

### 附录 C — 布局编译原始日志（`v5\make_layout_v5.log`）

```
=== v4 baseline edits replayed (23) ===
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
  (v4 decoded xml 9777 B)
=== v5 additional edit ===
  radio strip                  inserted after header row (new root child #1)
  decoded xml 9777 B -> 10739 B (+962 B)
=== root children after v5 edit: 7
    [0] LinearLayout                                         
    [1] RadioGroup                                           
    [2] TextView                                             
    [3] TextView                                             
    [4] View                                                 
    [5] TextView                                             @id/tv_bind_phone_desc
    [6] androidx.constraintlayout.widget.ConstraintLayout    
=== new RadioGroup @ root child #1 ===
    RadioGroup children=2  id=None  bg=#FFF1F5FC
    [0] RadioButton      text=游客登录     checked=true  id=None buttonTint=#FF2F6FED
    [1] RadioButton      text=卡密登录     checked=None  id=None buttonTint=#FF2F6FED
  id @id/et_phone                     x1 OK
  id @id/et_phone_code                x1 OK
  id @id/get_phone_code               x1 OK
  id @id/layout_phone_code            x1 OK
  id @id/login                        x1 OK
  id @id/ll_container_login           x1 OK
  id @id/agreement_layout             x1 OK
  id @id/iv_close                     x1 OK
  id @id/iv_back                      x1 OK
  id @id/tv_bind_phone_desc           x1 OK
  id @id/tv_privacy_agreement         x1 OK
  id @id/third_party_login            x1 OK
  id @id/one_login                    x1 OK
  id @id/taptap_login                 x1 OK
  id @id/iv_privacy_agreement_select  x1 OK
  id @id/login_helper                 x1 OK
  android:checked="true" count = 1
  android:visibility="gone" count = 3
  et_phone_code text="000000" = True

=== java -jar /opt/ba-tools/apktool.jar b -s -f -o /root/ba_work/v5_layout_build.apk /root/ba_work/dec5 ===
I: Using Apktool 2.11.1 on v5_layout_build.apk with 8 threads
I: Building resources with aapt2...
I: Building apk file...
I: Importing unknown files...
I: Built apk into: /root/ba_work/v5_layout_build.apk

=== throw-away build apk: 872 entries
  has classes.dex   : False
  has classes2.dex  : False
  has resources.arsc: True
  res/layout/fragment_default_mobile_code_login.xml -> /root/ba_work/v5_layout.axml  9060 B  sha256=e8096feacfdc5411c4ed65fce2bd75188ecd8dbb6db4dd92d48f551e52437918
```

### 附录 D — 索引安全证据（`v5\ev_index_safety.txt`）

```
### 1) which classes reference R.layout.fragment_default_mobile_code_login
$ grep -rn fragment_default_mobile_code_login smali smali_classes2
smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali:253:    sget v0, Lcom/airi/official/core/R$layout;->fragment_default_mobile_code_login:I
smali/com/airi/official/core/R$layout.smali:55:.field public static final fragment_default_mobile_code_login:I = 0x7f0b0044
smali/com/RoamingStar/BlueArchive/R$layout.smali:153:.field public static final fragment_default_mobile_code_login:I = 0x7f0b0044
smali_classes2/com/unity3d/player/R$layout.smali:153:.field public static final fragment_default_mobile_code_login:I = 0x7f0b0044

### 2) the consumer class itself
$ grep -n '^\.class\|^\.super' smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
1:.class public Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;
2:.super Lcom/airi/official/core/base/AbsFragment;
$ wc -l smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
1593 smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali

### 3) getChildAt / getChildCount in the consumer  (0 hits = no index dependency)
$ grep -c getChildAt smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
0
$ grep -c getChildCount smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
0
$ grep -n 'getChildAt\|getChildCount' smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali   # empty output = 0 hits

### 4) every view id the consumer touches (all id-based, no indices)
$ grep -o 'R$id;->[a-z_0-9]*' smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali | sort -u
R$id;->agreement_layout
R$id;->et_phone
R$id;->et_phone_code
R$id;->get_phone_code
R$id;->iv_back
R$id;->iv_close
R$id;->iv_privacy_agreement_select
R$id;->login
R$id;->login_helper
R$id;->one_login
R$id;->taptap_login
R$id;->third_party_login
R$id;->tv_bind_phone_desc
R$id;->tv_privacy_agreement

### 5) who instantiates the fragment (no subclass exists)
$ grep -rn "new-instance.*DefaultMobileLoginFragment;" smali smali_classes2
smali/com/airi/official/core/ui/fragment/FragmentCommonUtils.smali:94:    new-instance v0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;
$ grep -rn "extends.*DefaultMobileLoginFragment" smali smali_classes2   # empty = no subclass

### 6) every getChildAt caller inside the app packages (none of them touch this layout)
$ grep -rn getChildAt smali/com/airi smali/com/RoamingStar smali_classes2/com | grep -v "okhttp\|unity3d\|androidx"
smali/com/airi/common/utils/WebviewKeyboardUtils.smali:33:    invoke-virtual {p1, v0}, Landroid/widget/FrameLayout;->getChildAt(I)Landroid/view/View;
smali/com/airi/common/widget/ReboundScrollView.smali:458:    invoke-virtual {p0, v0}, Lcom/airi/common/widget/ReboundScrollView;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/PrivacyDialogActivity.smali:805:    invoke-virtual {v0, v3}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/LoginAuthActivity.smali:1366:    invoke-virtual {p1, v0}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/utils/m.smali:19:    invoke-virtual {p1, v0}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/utils/m.smali:80:    invoke-virtual {p0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/utils/m.smali:439:    invoke-virtual {v2, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/mobile/auth/gatewayauth/utils/m.smali:671:    invoke-virtual {v2, v3}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/TagFlowLayout.smali:385:    invoke-virtual {p0, v1}, Lcom/taptap/sdk/flowlayout/TagFlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/TagFlowLayout.smali:582:    invoke-virtual {p0, v1}, Lcom/taptap/sdk/flowlayout/TagFlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/TagFlowLayout.smali:684:    invoke-virtual {p0, v3}, Lcom/taptap/sdk/flowlayout/TagFlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/FlowLayout.smali:228:    invoke-virtual {p0, p4}, Lcom/taptap/sdk/flowlayout/FlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/FlowLayout.smali:646:    invoke-virtual {v0, v6}, Lcom/taptap/sdk/flowlayout/FlowLayout;->getChildAt(I)Landroid/view/View;
smali_classes2/com/taptap/sdk/flowlayout/TagView.smali:54:    invoke-virtual {p0, v0}, Lcom/taptap/sdk/flowlayout/TagView;->getChildAt(I)Landroid/view/View;
smali_classes2/com/tencent/open/TDialog$1.smali:68:    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
smali_classes2/com/tencent/connect/avatar/ImageActivity.smali:1117:    invoke-virtual {v0, v1}, Landroid/widget/LinearLayout;->getChildAt(I)Landroid/view/View;
```

### 附录 E — AXML 证据（`v5\ev_xmltree.txt`）

```
### v4 (throw-away build apk) -- root children, aapt dump xmltree
$ aapt dump xmltree v4_layout_build.apk res/layout/fragment_default_mobile_code_login.xml | grep "^      E: "
12:      E: LinearLayout (line=4)
47:      E: TextView (line=12)
58:      E: TextView (line=13)
68:      E: View (line=14)
75:      E: TextView (line=15)
86:      E: androidx.constraintlayout.widget.ConstraintLayout (line=16)

### v5 (throw-away build apk) -- root children
$ aapt dump xmltree v5_layout_build.apk res/layout/fragment_default_mobile_code_login.xml | grep "^      E: "
12:      E: LinearLayout (line=4)
47:      E: RadioGroup (line=12)
79:      E: TextView (line=16)
90:      E: TextView (line=17)
100:      E: View (line=18)
107:      E: TextView (line=19)
118:      E: androidx.constraintlayout.widget.ConstraintLayout (line=20)

### v5 -- the new RadioGroup block, raw attributes as compiled into the AXML
$ aapt dump xmltree v5_layout_build.apk res/layout/fragment_default_mobile_code_login.xml | sed -n "47,78p"
      E: RadioGroup (line=12)
        A: android:gravity(0x010100af)=(type 0x11)0x10
        A: android:orientation(0x010100c4)=(type 0x10)0x0
        A: android:background(0x010100d4)=(type 0x1c)0xfff1f5fc
        A: android:paddingLeft(0x010100d6)=(type 0x5)0x401
        A: android:paddingTop(0x010100d7)=(type 0x5)0x201
        A: android:paddingRight(0x010100d8)=(type 0x5)0x401
        A: android:paddingBottom(0x010100d9)=(type 0x5)0x201
        A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
        A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
        A: android:layout_marginLeft(0x010100f7)=(type 0x5)0x1801
        A: android:layout_marginTop(0x010100f8)=(type 0x5)0xa01
        A: android:layout_marginRight(0x010100f9)=(type 0x5)0x1801
        E: RadioButton (line=13)
          A: android:textSize(0x01010095)=(type 0x5)0xf02
          A: android:textColor(0x01010098)=(type 0x1c)0xff2b3445
          A: android:gravity(0x010100af)=(type 0x11)0x11
          A: android:layout_width(0x010100f4)=(type 0x5)0x1
          A: android:layout_height(0x010100f5)=(type 0x5)0x2801
          A: android:checked(0x01010106)=(type 0x12)0xffffffff
          A: android:text(0x0101014f)="游客登录" (Raw: "游客登录")
          A: android:layout_weight(0x01010181)=(type 0x4)0x3f800000
          A: android:buttonTint(0x0101046f)=(type 0x1c)0xff2f6fed
        E: RadioButton (line=14)
          A: android:textSize(0x01010095)=(type 0x5)0xf02
          A: android:textColor(0x01010098)=(type 0x1c)0xff2b3445
          A: android:gravity(0x010100af)=(type 0x11)0x11
          A: android:layout_width(0x010100f4)=(type 0x5)0x1
          A: android:layout_height(0x010100f5)=(type 0x5)0x2801
          A: android:text(0x0101014f)="卡密登录" (Raw: "卡密登录")
          A: android:layout_weight(0x01010181)=(type 0x4)0x3f800000
          A: android:buttonTint(0x0101046f)=(type 0x1c)0xff2f6fed
```

### 附录 F — `zipdiff_v5.json`

```json
{
  "changed": [
    "META-INF/CERT.RSA",
    "META-INF/CERT.SF",
    "META-INF/MANIFEST.MF",
    "res/Q9.xml"
  ],
  "only_v4": [],
  "only_v5": [],
  "badging_diff_lines": 0,
  "ok": true
}
```

### 附录 G — 文件清单（本目录）

- `work\ba\apk_patch\v5\make_layout_v5.py` — 8,990 B
- `work\ba\apk_patch\v5\make_layout_v5.log` — 5,104 B
- `work\ba\apk_patch\v5\res_Q9_v5.axml` — 9,060 B
- `work\ba\apk_patch\v5\build_v5.log` — 6,098 B
- `work\ba\apk_patch\v5\selftest_v5.py` — 9,875 B
- `work\ba\apk_patch\v5\selftest_v5_out.txt` — 4,936 B
- `work\ba\apk_patch\v5\selftest_console.txt` — 9,654 B
- `work\ba\apk_patch\v5\badging_v4.txt` — 8,653 B
- `work\ba\apk_patch\v5\badging_v5.txt` — 8,653 B
- `work\ba\apk_patch\v5\sig_v4.txt` — 888 B
- `work\ba\apk_patch\v5\sig_v5.txt` — 888 B
- `work\ba\apk_patch\v5\zipdiff_v5.json` — 202 B
- `work\ba\apk_patch\v5\ev_index_safety.sh` — 1,913 B
- `work\ba\apk_patch\v5\ev_index_safety.txt` — 5,133 B
- `work\ba\apk_patch\v5\ev_xmltree.sh` — 1,096 B
- `work\ba\apk_patch\v5\ev_xmltree.txt` — 2,938 B
- `work\ba\apk_patch\v5\preview_v5.py` — 11,997 B
- `work\ba\apk_patch\v5\preview_v5.png` — 157,358 B
- `work\ba\apk_patch\v5\build_report_v5.py` — 24,457 B
- `work\ba\apk_patch\v5\SELFTEST_v5.md` — 52,365 B
