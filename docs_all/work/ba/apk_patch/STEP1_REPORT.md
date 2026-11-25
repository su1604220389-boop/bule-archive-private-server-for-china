# STEP 1 报告 — BA 客户端三改造：工具链 / 落点 / 风险

- 生成时间：2026-11-18 18:59 (+08:00)
- 状态：**第一步已完成，未产出任何成品 APK**（按要求停在这里等放行）
- 工作区：`work\ba\apk_patch\`（新建；未触碰 `work\ba\audit\` 及既有目录）
- 基线 APK：`work\ba\noroot\BA_noroot_prod_20261118_v1.apk`（2,127,971,177 B）

---

## 0. 结论先行（4 条）

1. **空改回编成功**。apktool 2.11.1 + aapt2：解码 43 s → 回编 5.9 s，`exit 0`。
2. **apktool 的 `resources.arsc` 不能直接用**（重编后 1,156,308 → 1,179,968 B，且 803 个 `res/*.xml` 全被改成 `res/layout/…` 长名）。→ **方案改为：`resources.arsc` 原封不动，只换 `res/Q9.xml` 与 `classes.dex` 两个 zip 条目**。
3. 已实测证明：用 aapt2 重编出来的 `res/layout/fragment_default_mobile_code_login.xml` 与原始 `res/Q9.xml` **逐属性完全一致**（归一化 `line=` 后 diff = 0 行）⇒ 它是**可原样顶替的 drop-in**。加完 RadioGroup 后再 diff，**差异只有新增的 25 行子树**，且 **`resources.arsc` 一个字节没变**。
4. 因此三改造全部落在 **2 个 zip 条目** 上：`res/Q9.xml`（结构 + `maxLength`/`inputType`）和 `classes.dex`（`handleErrorCode` 用服务端 msg、`isChinaPhoneLegal` 正则、`initView`/`onClick` 接线）。**`resources.arsc` / `AndroidManifest.xml` / `classes2.dex` / `lib*` / `assets` 全部保持原字节。**

---

## 1. WSL 工具链（实测）

```
发行版 Ubuntu 24.04.3 LTS，WSL2，root（sudo 免密）
nproc=24  RAM=23Gi  磁盘 / = 861 GiB 可用，/mnt/c = 1018 GiB 可用
```

### 1.1 探测时**本来什么都没有**

```
=== id ===            uid=0(root)
=== os ===            Ubuntu 24.04.3 LTS
=== java ===          NO_JAVA
=== javac ===         NO_JAVAC
java/javac/apktool/jadx/baksmali/smali/apksigner/zipalign/aapt/aapt2/unzip/zip/keytool/d8/dx  → 全部 MISSING
python3               /usr/bin/python3  (3.12.3，有 zipfile/lxml/cryptography/pycryptodome)
```

### 1.2 已装上（apt 全部可装）

| 工具 | 版本 | 来源 |
|---|---|---|
| `java` / `javac` | **OpenJDK 21.0.13** (`21.0.13.0.3-1-1-24.04.1-ubuntu`) | `apt install openjdk-21-jre-headless openjdk-21-jdk-headless` |
| `apktool`（apt 版） | 2.7.0-dirty | `apt install apktool`（**没用它**，见下） |
| `apktool.jar`（实际使用） | **2.11.1** | GitHub release `iBotPeaches/Apktool` → `/opt/ba-tools/apktool.jar`（24,562,875 B） |
| `jadx` / `jadx-gui` | **1.5.3** | GitHub release → `/opt/ba-tools/jadx/bin/jadx` |
| `apksigner` | 0.9（Debian 打包） | `apt install apksigner` |
| `zipalign` | Debian 打包 | `apt install zipalign` |
| `aapt` | v0.2-debian | `apt install aapt`（`dump xmltree` / `dump badging` 可用，见 §3） |
| `zip` / `unzip` / `file` / `curl` / `wget` / `git` | — | apt |

- **`aapt2` 独立可执行没装**。apktool 2.11.1 自带 aapt2（日志 `I: Building resources with aapt2...` 已跑通），所以回编不需要外部 aapt2。第二步若要做 `aapt2 dump badging` 我再从 Google Maven 取；目前用 `aapt dump badging` 已能读包名/版本（§3）。
- 网络：`github.com` 200、`ghproxy.net` 200、`dl.google.com` 可达（apt 走清华镜像）。
- 装的都是 apt/GitHub 公开包，**没有装不了的东西**。

### 1.3 ⚠️ 两个环境陷阱（第二步必须照做）

1. **`wsl.exe -e bash -c '<长脚本>'` 从 PowerShell 传参会撕裂输出**（第一次探测只回了 `===`；`whoami/id: -c: line 2: syntax error`）。可靠做法：把脚本写成 `.sh` 落盘，再 `wsl.exe -d Ubuntu-24.04 bash /mnt/c/.../xxx.sh`。本报告所有探测都用这个方式。
2. **`/mnt/c` 是大小写不敏感**：`cp -a` 把 WSL 里的 decode 树拷到 `work\ba\apk_patch\decode\` 时，`a.smali`/`A.smali`、`a0.smali`/`A0.smali` 这类同名文件互相覆盖，报了一串 `cp: cannot create ... File exists`。**所以 apktool 的 `d` / `b` 必须在 WSL ext4（`/root/ba_work/`）里跑，不能在 `/mnt/c` 里跑**，否则会少类。项目里的 `decode\` 只是**查阅副本**，不是构建输入。

---

## 2. 实际路径与 sha256

| 物件 | 路径 | 大小 | sha256 |
|---|---|---|---|
| **基线 APK** | `work\ba\noroot\BA_noroot_prod_20261118_v1.apk` | 2,127,971,177 B | `5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6` |
| **备份 APK** | `work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk` | 2,127,971,177 B | **同上（已逐字节校验一致）** |
| **keystore** | `work\ba\noroot\ba_private.keystore` | 2,568 B | `1e7669b1b87a27b50f1340c1103954250e2dd61709aaeb92a5261b27c99d4963` |
| 瘦身输入（apktool 用） | `work\ba\apk_patch\slim\slim.apk` | 15,828,657 B | `9285e7a8f0dd737632b5a188aa9b9b01572bafe7b648c6a10f45a6a1171a47ef` |
| 构建脚本 | `work\ba\noroot\build_noroot_apk.py` | 115,359 B | （未改动） |

- keystore 参数：**alias `ba` / storepass `baserver`**（与 `build_noroot_apk.py` 的 `--keystore/--storepass/--alias` 默认值一致）。
- 基线 APK：41,307 个 zip 条目，`versionCode=73` / `versionName=3.0.2` / `minSdk=24` / `targetSdk=33`（`aapt dump badging` 实测，见 §3）。
- 基线里 **`assets/__tpinfo.*` 已全部不存在**（5/5 命中为空）⇒ `--asset-replace` 重出包不会因为“删 tpinfo”再变一次。
- 基线 `assets/SDKConfigSettings.json` 里 `sdk_url = https://example.com/sdk`（第二步要原样回填，才能保证该条目字节不变）。
- 完整清单落在 `work\ba\apk_patch\BASELINE_MANIFEST.json`（含每个关键条目的 size/sha256/crc32/zip method）。

### 2.1 关键 zip 条目基线（第二步的 diff 对照表）

| 条目 | 原始大小 | crc32 | zip 方式 | 第二步会不会变 |
|---|---|---|---|---|
| `resources.arsc` | 1,156,308 | `3791194b` | STORED | **不变** |
| `res/Q9.xml` | 7,292 | `22a6215c` | STORED | **会变**（≈ +700 B） |
| `classes.dex` | 9,327,708 | `ce71d74e` | DEFLATE | **会变**（≈ +2.6 KB） |
| `classes2.dex` | 10,158,904 | `be3734c8` | DEFLATE | **不变** |
| `AndroidManifest.xml` | 50,552 | `503a5791` | STORED | **不变** |
| `res/nW.xml` `res/EQ.xml` `res/o4.xml` `res/Dk.xml` | 1240/4028/3356/560 | — | STORED | **不变** |
| `lib/**`（24 条，86.0 MB） | — | — | — | **不变** |
| `assets/**`（40,405 条，1,925.1 MB） | — | — | — | **不变** |
| `META-INF/**` | — | — | — | 旧 v1 签名整组剔除、重新生成 |

---

## 3. 解码 / 空改回编（这一步过了才谈后面）

### 3.1 输入怎么来

2.1 GB 里 **1,925 MB 是 `assets/audio`**，与本次无关。为了不让 apktool 拖着 1.9 GB 走，先做瘦身包：

```
slim.apk = 基线全部条目 减去 assets/ 与 lib/      → 878 条目 / 15,828,657 B
（保留 AndroidManifest.xml + resources.arsc + 全部 803 个 res/ + classes.dex + classes2.dex）
```

### 3.2 解码（WSL ext4 内）

```
$ java -jar /opt/ba-tools/apktool.jar d -f -o /root/ba_work/dec0 slim.apk
I: Using Apktool 2.11.1 on slim.apk with 8 threads
I: Baksmaling classes.dex...
I: Loading resource table...
I: Baksmaling classes2.dex...
I: Decoding file-resources...
I: Decoding values */* XMLs...
I: Decoding AndroidManifest.xml with resources...
I: Regular manifest package...
I: Copying original files...
I: Copying unknown files...
real 0m43.060s      → 无 error，无 warning
```

产物：`AndroidManifest.xml` 33 KB、`apktool.yml` 27 KB、`original/`、`res/`（187 个子目录）、`smali/`、`smali_classes2/`、`unknown/`。

**你问的那一点：`res/Q9.xml` 解码后是可读明文 XML** ✅ —— 落在 `res/layout/fragment_default_mobile_code_login.xml`，42 行，属性全部还原成 `@dimen/dp24`、`@drawable/login_edit_bg_fragment`、`android:maxLength="11"`、`android:inputType="phone"` 这种可读形式。`res/values/public.xml` 也在（4,600 行），4600 个资源 id 全被 pin 住。

### 3.3 空改回编

```
$ java -jar /opt/ba-tools/apktool.jar b -f -o /root/ba_work/slim_rebuild.apk /root/ba_work/dec0
I: Smaling smali folder into classes.dex...
I: Smaling smali_classes2 folder into classes2.dex...
I: Building resources with aapt2...
I: Building apk file...
I: Importing unknown files...
I: Built apk into: /root/ba_work/slim_rebuild.apk
real 0m5.865s   rc=0    输出 10,760,537 B
```

**空改回编成功。管线可用。**

### 3.4 但回编产物**不能**整包替换 —— 关键发现

| 对比项 | 原包 | 空改回编 | 结论 |
|---|---|---|---|
| `resources.arsc` | 1,156,308 B | **1,179,968 B（+23,660）** | ❌ 不能直接用 |
| `res/*.xml` 路径 | `res/Q9.xml`、`res/0C.xml`、`res/-5.xml` …（AndResGuard 扁平名，803 个） | `res/layout/fragment_default_mobile_code_login.xml`、`res/anim/abc_fade_in.xml` …（**全部改成 type/name 长名**） | ❌ 不能直接用 |
| `AndroidManifest.xml` | 50,552 B | 50,552 B，但 12,068 字节不同 | ❌ 不能直接用 |
| `classes.dex` | 9,327,708 | 9,330,304 | 备用（见 §4.2） |
| `classes2.dex` | 10,158,904 | 10,091,400 | ❌ 丢弃，用原件 |
| `META-INF/CERT.*` 等 | 有（5.1 MB 旧签名） | 被丢 | 本来就要重签 |

→ apktool 会**重建整张资源表**（资源文件改名 + arsc 重编）。这条路会把 diff 面积从“2 个条目”放大到“806 个条目”，而且**无法用现有 `build_noroot_apk.py` 的 `--asset-replace` 表达**。**放弃整包重编。**

### 3.5 ★ 决定性的 drop-in 验证（已实测通过）

既然只改一个布局，验证「aapt2 重编出来的那一个 AXML 能不能原样塞回原包」：

**测试 1（未改动）**：把原始 `res/Q9.xml` 与回编产物的 `res/layout/fragment_default_mobile_code_login.xml` 都用 `aapt dump xmltree` 展开，归一化 `(line=N)` 后 diff：

```
orig lines: 235   reb lines: 235
normalized diff lines: 0        ← 逐属性、逐资源 id 完全一致
```

**测试 2（真的插入 RadioGroup 后回编）**：在解码 XML 的 `tv_bind_phone_desc` 与输入区 ConstraintLayout 之间插入

```xml
<RadioGroup android:gravity="center" android:orientation="horizontal" ...>
    <RadioButton …/><RadioButton …/>
</RadioGroup>
```

回编 → `rc=0`，产物 `exp1.apk`。再 diff：

```
diff lines: 25
56a57,80
>       E: RadioGroup
>         A: android:gravity(…)=0x11
>         A: android:orientation(…)=0x0
>         …
>         E: RadioButton
>           …
>         E: RadioButton
>           …
```

**除了新增的 25 行子树，原有 235 行属性一个都没动。**

**测试 3（最关键）**：比较两次回编的 `resources.arsc` 大小

```
orig   (基线)              arsc = 1,156,308 B
reb0   (空改回编)          arsc = 1,179,968 B
exp1   (加了 RadioGroup)   arsc = 1,179,968 B   ← 和 reb0 完全相同
```

⇒ **在 Q9.xml 里加控件不会给资源表增加任何条目**（因为我们不给新控件分配 `@+id`、也不写字面量 `android:text`）。这就是三改造能压到“只换 2 个条目”的技术前提。

### 3.6 结论：第二步的文件流向

```
WSL ext4:  dec0 / dec1  ──apktool b──►  exp_final.apk
             │                              │
             │                              ├─ 抽出 res/layout/fragment_default_mobile_code_login.xml
             │                              │     → 改名 res/Q9.xml   （新，≈7,996 B）
             │                              └─ 抽出 classes.dex        （新，≈9.33 MB）
             ▼
Windows:   build_noroot_apk.py --src 基线.apk --out BlueArchive_cardlogin_v1.apk
                --asset-replace resources.arsc=…（不改，不传）
                --asset-replace res/Q9.xml=<新>
                --asset-replace classes.dex=<新>
                --sdk-url https://example.com/sdk
                --keystore ba_private.keystore --storepass baserver --alias ba
```

（`--asset-replace` 不限于 `assets/`：脚本第 1603–1624 行对任意 `NAME=PATH` 做「源包里必须有该条目 + 本地文件必须存在」的校验后整条替换。）

---

## 4. 三个改造的精确落点

### 4.1 改造 1 —— 登录界面拆两个入口（游客 / 卡密）

**落点 A：布局（`res/Q9.xml`，经 `res/layout/fragment_default_mobile_code_login.xml` 编辑后回编）**

- 插入位置：解码 XML 第 12 行 `tv_bind_phone_desc` 之后、第 13 行 `<androidx.constraintlayout.widget.ConstraintLayout android:paddingLeft="@dimen/dp24"…>` 之前。
- 在**根 `LinearLayout` 里成为第 3 个子节点（index 2）**——这是运行时定位它的唯一依据，**刻意不给它 `android:id`**。

```xml
<RadioGroup android:gravity="center" android:orientation="horizontal"
            android:layout_width="fill_parent" android:layout_height="wrap_content"
            android:layout_marginTop="@dimen/dp7" android:layout_marginBottom="@dimen/dp0">
    <RadioButton android:textSize="@dimen/sp14" android:textColor="@color/c_6a6a6a"
                 android:gravity="center" android:layout_weight="1.0"
                 android:layout_width="wrap_content" android:layout_height="wrap_content"/>
    <RadioButton …同上…/>
</RadioGroup>
```

- **不要**写 `android:checkedButton="@null"`（我试过，会编成 `@0x00000000`，`RadioGroup` 构造里 `mCheckedId=0`，纯属噪音）；**保留默认 radio 圆点**（不要 `android:button="@null"`），这样“选中态”有原生视觉反馈，且不需要新增任何 drawable / color-selector 资源。
- **不要**写 `android:text`（字面量）。两个按钮的文案从 DEX 里 `setText(const-string)` 设置 → **`resources.arsc` 零改动**（§3.5 测试 3 已证）。
- 结果：`res/Q9.xml` 从 **7,292 B → 7,996 B**（实测值，最终会因属性微调差 ±几十 B）。zip 方式仍 STORED。

**落点 B：`DefaultMobileLoginFragment`（`classes.dex` → `smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali`）**

B-1 `initView(Landroid/view/View;)V`（smali 495–1141 行，`.locals 11`）——
在 `.locals 11` 之后、`.line 96` 之前**插入**（此时 `p1` 还是根 View，`v0/v1/v2` 全部未活）：

```smali
    move-object v0, p1
    check-cast v0, Landroid/view/ViewGroup;
    const/4 v1, 0x2
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v0
    check-cast v0, Landroid/widget/RadioGroup;
    if-eqz v0, :bpk_sel_done

    const/4 v1, 0x0                                  # 第 0 个 = 游客登录
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v1
    check-cast v1, Landroid/widget/RadioButton;
    invoke-virtual {v1, p0}, Landroid/widget/RadioButton;->setOnClickListener(Landroid/view/View$OnClickListener;)V
    const-string v2, "游客登录"
    invoke-virtual {v1, v2}, Landroid/widget/RadioButton;->setText(Ljava/lang/CharSequence;)V
    const/4 v2, 0x1
    invoke-virtual {v1, v2}, Landroid/widget/CompoundButton;->setChecked(Z)V

    const/4 v1, 0x1                                  # 第 1 个 = 卡密登录
    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;
    move-result-object v1
    check-cast v1, Landroid/widget/RadioButton;
    invoke-virtual {v1, p0}, Landroid/widget/RadioButton;->setOnClickListener(Landroid/view/View$OnClickListener;)V
    const-string v2, "卡密登录"
    invoke-virtual {v1, v2}, Landroid/widget/RadioButton;->setText(Ljava/lang/CharSequence;)V
    :bpk_sel_done
```

依据：`DefaultMobileLoginFragment` 的类声明第 5 行就是
`.implements Landroid/view/View$OnClickListener;`，且 `initView` 里现成的 7 处
`setOnClickListener(Landroid/view/View$OnClickListener;)V` 传的都是 `p0`（本 Fragment），所以直接复用 `onClick`，**不需要造任何新类**。
`RadioGroup` 会让没 id 的 `RadioButton` 在 `PassThroughHierarchyChangeListener` 里自动 `generateViewId()`，所以 `check()/isChecked()` 全链路可用，**不需要给 RadioButton 分配 `@id`**。

B-2 `onClick(Landroid/view/View;)V`（smali 1143 行，`.locals 7`，**是 if-ne 链不是 switch 表**）——
在 `invoke-virtual {p1}, Landroid/view/View;->getId()I` / `move-result p1` 之后**插入**：

```smali
    invoke-virtual {p1}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v0
    instance-of v1, v0, Landroid/widget/RadioGroup;
    if-eqz v1, :bpk_not_sel

    check-cast v0, Landroid/widget/RadioGroup;
    invoke-virtual {v0, p1}, Landroid/view/ViewGroup;->indexOfChild(Landroid/view/View;)I
    move-result v0

    if-eqz v0, :bpk_sel_paid                # 0 = 游客
    const-string v0, "请输入公益卡密"
    goto :bpk_sel_apply
    :bpk_sel_paid
    const-string v0, "请输入付费卡密"
    :bpk_sel_apply
    iget-object v1, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;
    invoke-virtual {v1, v0}, Landroid/widget/TextView;->setHint(Ljava/lang/CharSequence;)V
    return-void
    :bpk_not_sel
```

- 用 `parent instanceof RadioGroup` + `indexOfChild` 判别是哪个按钮 → **完全不需要 id**。
- `return-void` 直接短路，不进入后面那串 `iv_close / iv_back / login / one_login / taptap_login / get_phone_code / iv_privacy_agreement_select` 分支（那些是 `if-ne p1, …` 比较，短路不影响它们）。
- `v0/v1` 在方法入口处必然未活（原方法第一条指令才 `move-result p1`），`.locals 7` 够用，**不用改 `.locals`**。

B-3 初始 hint —— 在 `initView` 末尾（`.line 242` 的 `invoke-virtual {p0}, …->addCodeListener()V` 之后、`return-void` 之前）**插入**：

```smali
    iget-object v0, p0, Lcom/airi/official/core/ui/fragment/DefaultMobileLoginFragment;->et_phone:Landroid/widget/EditText;
    const-string v1, "请输入公益卡密"
    invoke-virtual {v0, v1}, Landroid/widget/TextView;->setHint(Ljava/lang/CharSequence;)V
```

（放在末尾是因为 `et_phone` 字段在 `initView` 第 98 行才赋值；同时末尾 `p1` 已被复用成 String，**不能**再用 `p1`。）

> **不影响请求内容**：`handleLoginLink(Z)V`、`LoginReq{Type:"mobile", OpenID:卡密, Token:验证码}`、`loginWithLink` 一行都不碰。客户端这个二选一纯装饰 —— 与服务端 `cards.json` 的 `kind` 判断无关。

---

### 4.2 改造 2 —— 封禁弹窗显示服务端文案

**落点：`com/airi/official/core/http/net/HttpCallBack.smali` → `handleErrorCode(ILjava/lang/String;)V`**（`.method private`，`.locals 4`）

原始关键三行：

```smali
    .line 71
    invoke-static {p1}, Lcom/airi/official/core/http/net/ErrorCodeHandler;->getCodeInfoByCode(I)Lcom/airi/official/core/http/net/ErrorCodeInfo;
    move-result-object v1
```

**在第 71 行 `.line 71` 之后、上述 `invoke-static` 之后（也就是 `move-result-object v1` 的紧后面）插入 8 条指令：**

```smali
    invoke-static {p2}, Landroid/text/TextUtils;->isEmpty(Ljava/lang/CharSequence;)Z
    move-result v2
    if-eqz v2, :bpk_keep_local

    invoke-virtual {v1}, Lcom/airi/official/core/http/net/ErrorCodeInfo;->component3()Z       # isLogout
    move-result v2
    invoke-virtual {v1}, Lcom/airi/official/core/http/net/ErrorCodeInfo;->component4()Z       # isRemoveUserData
    move-result v3
    new-instance v1, Lcom/airi/official/core/http/net/ErrorCodeInfo;
    invoke-direct {v1, p1, p2, v2, v3}, Lcom/airi/official/core/http/net/ErrorCodeInfo;-><init>(ILjava/lang/String;ZZ)V
    :bpk_keep_local
```

为什么这是**最小且保真**的改法（逐条有 smali 依据）：

1. `ErrorCodeInfo` 是 Kotlin data class，4 个字段 `errorCode:I / errorMsg:String / isLogout:Z / isRemoveUserData:Z`；构造函数 `public <init>(ILjava/lang/String;ZZ)V`（`acc=0x10001`）。**字段是 `val`（final）⇒ 不能 `iput` 覆写，必须重造对象**。
2. `component3()/component4()` 是 data class 现成的 getter，把 `getCodeInfoByCode` 从本地表算出来的两个 flag **原样搬过来**，不硬编码（`getCodeInfoByCode` 里那两个 `const/4` 的语义我不猜）。
3. 插入点在 `move-result-object v1` 之后、`.line 72` 之前 ⇒ 后面 `new HttpCallBack$$ExternalSyntheticLambda0(this, v1)` 与 `showUiByErrorCodeInfo(activity, uid, v1, cb)` 拿到的都是**改后**的对象，不用动调用点。
4. `v2/v3` 此刻未活（`v0` 存 `isHandleErrorCode` 结果、`v1` 存 info），**`.locals 4` 不用改**。
5. **`p1` 此时仍是 int code**（原方法到 `.line 72` 才 `move-result-object p1` 把 p1 复用成 StringBuilder），所以 `new-instance` 里用 `p1` 作为 code 是对的。
6. 只加一个 `Landroid/text/TextUtils;` 类型引用（dex 里早已存在），无新类。

**效果链（已核对到底）**：

```
/user/login 失败 → HttpCallBack.onResponse(Call,Response)
  → body.Code != 200 → handleErrorCode(body.Code, body.Msg)      ← 服务端封禁文案从这里进
  → 【我们的补丁】info = ErrorCodeInfo(code, msg, flags)          ← 不再用本地表
  → ErrorCodeHandler.showUiByErrorCodeInfo(activity, uid, info, cb)
      → errorType = SdkManager.queryErrorType(ctx, code)
                     → DbManager.queryErrorMsg(...) 空表 → 返回 null
                     → SdkManager 里 `if-nez p1, :cond_0 → return-object v1`（v1 = ""）
                     ⇒ errorType = ""   （不是 null，安全）
      → realShowUiByErrorCode$1.invokeSuspend:
          msg = errMsg; if TextUtils.isEmpty(msg) → UN_KNOW_ERROR   ← 我们的 msg 非空，跳过
          StringsKt.equals(errorType, "toast", true) → false
          StringsKt.equals(errorType, "none",  true) → false
          else → FragmentCommonUtils.goTipsActivityDialog(
                     title=@string/tips="提示", content=msg,
                     cancel=""(隐藏), ok=@string/ok_btn="确定", okListener→handleLoginData)
```

**你要求“顺带确认”的那一条，已证实成立**：`SdkManager.queryErrorType` 在 `DbManager.queryErrorMsg` 返回 null 时**显式返回空串 `""`**（smali 里 `if-nez p1, :cond_0` → `return-object v1`，而 `v1` 是 `const-string v1, ""`），不是 null ⇒
- `StringsKt.equals("", "toast", true)` = false（常量是 receiver，null 安全）
- `StringsKt.equals("", "none", true)` = false
⇒ **落到 else 弹窗分支，对任意 code 都成立**。`showUiByErrorCodeInfo` 里那句 `Intrinsics.checkNotNull(queryErrorType(...))` 也不会炸。

**不会引入的问题 / 会引入的问题**

- ✅ 弹窗容器 `TipsActivity` + `res/o4.xml`，`@id/tv_tips_content`（`JustifyTextView`）`maxLines=4` / `ellipsize=end`，可用宽 312−24−24=264dp、sp14 ⇒ ≈52–64 汉字。「封号时间 2026-11-18 20:00 至 2026-11-20 20:00，请联系客服」46 字符里 32 个是 ASCII，折算约 2–3 行，**不会被再裁一次**。
- ⚠️ **副作用（唯一一处）**：`HttpCallBack.onResponse(Call,Response)` 在 `response.code()!=200` 时调的是 `handleErrorCode(101404, "unknown error")`（`const-string/jumbo v10, 'unknown error'`），`onFailure` 调 `handleErrorCode(101404, getString(R.string.net_error))`。打完补丁后，「HTTP 层非 200」这一支会把英文 `unknown error` 弹给玩家。
  - 选项 i（推荐，最省）：接受。这一支本来今天弹的是「未知错误，请联系客服。」，现在弹 `unknown error`，语义没差多少、且极少触发（正常业务错误都走 `body.Code`）。
  - 选项 ii（+3 条指令）：在 `handleErrorCode` 里加 `const v2, 101404 / if-ne p1, v2, :bpk_keep_local2`，让 101404 保留本地表文案。**但这会让 `onFailure` 的网络错误也丢掉 `net_error` 文案**。
  - 选项 iii（改动更大）：改 `onResponse` 那一支，把 `const-string/jumbo 'unknown error'` 换成资源串 —— 要多压 2 个寄存器，收益不值得。

---

### 4.3 改造 3 —— 卡密长度放开（最要紧的一条）

**(a) `et_phone` 的 `maxLength`** —— `res/Q9.xml` 解码 XML 第 14 行
| | 原值 | 新值 |
|---|---|---|
| XML | `android:maxLength="11"` | `android:maxLength="64"` |
| 二进制（原位 u32，**已实测核对**） | 文件偏移 **`0xc88`** = `0x0000000b` | `0x00000040` |
| 所在属性记录 | 记录起点 `0xc78`：ns=`-1`、name=`0x34`("maxLength")、rawValue=`-1`、`size=8`、`dataType=0x10`(INT_DEC) | dataType 不变 |

**(b) `et_phone` 的 `inputType`** —— 同一行
| | 原值 | 新值 |
|---|---|---|
| XML | `android:inputType="phone"` | `android:inputType="text"` |
| 二进制（原位 u32，**已实测核对**） | 文件偏移 **`0xc9c`** = `0x00000003` | `0x00000001` |
| 所在属性记录 | 起点 `0xc8c`：name=`0x1b`("inputType")、rawValue=`-1`、`size=8`、`dataType=0x11`(INT_HEX) | dataType 不变 |

> 更正研究文档 §6 的第 1 条疑虑：`0x3` **就是**合法的 `InputType.TYPE_CLASS_PHONE`（标准值 `0x00000003`），不是未知 class。改成 `TYPE_CLASS_TEXT`(`0x1`) 后是标准 QWERTY 键盘，字母可输入。

**(c) `isChinaPhoneLegal` 的匹配串** —— `classes.dex` → `smali/com/airi/common/utils/CommonUtil.smali`
| | 原值 | 新值 |
|---|---|---|
| smali（第 745 行） | `const-string v0, "^1\\d{10}$"` | `const-string v0, "^.{1,64}$"` |
| 物理字节（原位等长，**已实测**） | 9 字节 `5e 31 5c 64 7b 31 30 7d 24` | 9 字节 `5e 2e 7b 31 2c 36 34 7d 24` |
| 位置 | `strings[32792]`，`dataOff=0x70eb59`，ulebLen=9，payload 起 `0x70eb5a` | 不变 |
| 收尾 | `header.checksum`（`file+0x08`，adler32 over `bytes[12:]`）+ `header.signature`（`file+0x0c`，SHA-1 over `bytes[32:]`） | 必须重算 |

> 因为改造 2 本来就要 smali 重编 `classes.dex`，**优先走 smali 源改**（`const-string` 直接写新正则，长度自由，不用算偏移和重算头）。**原位 9 字节补丁作为备用路线**（若第二步发现 smali 往返有问题，就退回原位补丁：`classes.dex` 只动这 9 字节 + 两个头字段，其余 9.3 MB 逐字节不变）。
> `isPhoneLegal(String)`（第 914 行）只是 `invoke-static {p0}, CommonUtil->isChinaPhoneLegal(...)` 转发，**不用改**。

**(d) `et_phone_code` 保持不动（按你的要求）**
| 目标 | 文件偏移 | 现值 | 处置 |
|---|---|---|---|
| `et_phone_code` `maxLength` | `0xef0` | `0x00000006` | **保持 6** |
| `et_phone_code` `inputType` | `0xf04` | `0x00000002`（number） | **保持 2** |
| 代码里 `code.length() != 6` | `handleLoginLink(Z)V` 内 `const/4 v1, 0x6` | 6 | **保持 6** |

⇒ 用户随便填 6 位数字即可。**这个 6 位限制不会卡住流程**（服务端 `LoginReq.Token` 里给的就是这个 6 位数，服务端不看它），所以**不需要改成 `>=1`**。改 `>=1` 反而要多改一处指令、多一份风险。

**(e) 另一处 11 位门槛 —— 建议不动**
`onClick` 的 `@id/get_phone_code`（"发送"）分支里另有一条 `String.length()` 与 `const/16 v1, 11` 的比较（`out25.txt` 偏移 0x1dc/0x1e4）。它拦的是"点发送要 11 位手机号"，**与"登录"无关**（我们的卡密登录流程不点发送）。改了反而可能把语义弄反（>=11 vs <11 得看具体分支），**建议保持原样**，最多在真机上点一下确认它只弹个 toast、不崩。

---

## 5. 风险等级与回滚

### 改造 1（布局 + onClick 接线）——**中**

| 风险 | 说明 | 缓解 |
|---|---|---|
| 布局错位 / 控件看不见 | 根 `LinearLayout` 是 vertical，新 `RadioGroup` 是 `fill_parent × wrap_content`，高度自适应；但**没有 aapt 编译期校验**，只能看真机 | 已实测回编通过、属性逐条可读；真机目测一次即可 |
| `getChildAt(2)` 索引错位 | 运行时按根节点第 3 个子节点取 RadioGroup。若将来有人改布局顺序就失配 | 加了 `if-eqz v0, :bpk_sel_done` 空值保护：取不到就静默跳过，**不会崩**，只是不显示按钮 |
| 注册 `OnClickListener` 失败 | 若 `p0` 不是 `View.OnClickListener` | 已核实类声明 `.implements Landroid/view/View$OnClickListener;`；且 `initView` 里已有 7 处同样写法 |
| `RadioGroup` 自动生成 id 行为差异（OEM） | 依赖 `PassThroughHierarchyChangeListener` 给无 id 的 RadioButton 调 `generateViewId()` | API≥17，`minSdk=24`。且即使没生成，`setChecked(true)` + 我们自己的 `OnClickListener` 依然工作（我们**没有**依赖 `RadioGroup.getCheckedRadioButtonId()`） |
| **回滚** | 删掉 `res/Q9.xml` 与 `classes.dex` 两个 `--asset-replace` 参数即可；基线 APK 未变（sha256 `5f8b79dd…`），`backup\` 里有完整副本 | — |

### 改造 2（`handleErrorCode` 用服务端 msg）——**低**

| 风险 | 说明 | 缓解 |
|---|---|---|
| 弹窗文案过长被 `maxLines=4` 截 | 已核算 46 字符约 2–3 行 | 服务端压到 ~50 汉字内即可 |
| HTTP 层错误弹英文 `unknown error` | 唯一的语义副作用（§4.2 选项 i/ii/iii） | 建议接受；不接受就加 3 条指令 |
| 服务端若日后实现 `/common/client-code` 并给封禁码配 `Type:"toast"` | 会被 toast 分支吃掉，且 toast 前缀是 `"<code>:  "` | **封禁码不要配 Type，或配成 `dialog`/任意非 toast/none 值** |
| smali 指令写错 → 校验失败 | `new-instance` + `<init>(ILjava/lang/String;ZZ)V` 参数顺序错会 `VerifyError` | 参数顺序已按 §4.2 固定；`apktool b` 会做 smali 语法校验；装机后再看 `logcat -s AiriSDK` |
| **回滚** | 去掉 `classes.dex` 的 `--asset-replace` | 同上 |

### 改造 3（长度/键盘/正则）——**低**

| 风险 | 说明 | 缓解 |
|---|---|---|
| `ExtendEditText` 自带 `LengthFilter` 覆盖 XML | **已排除**：`grep LengthFilter\|setFilters\|maxLength\|InputFilter` 对 `ExtendEditText.smali` + `ExtendEditText$1.smali` **零命中**，它只处理清空按钮（`mClearButton/mClearStatus/mClearButtonMode`）⇒ `android:maxLength` 是唯一来源 | — |
| `TYPE_CLASS_TEXT` 键盘行为 | 标准 QWERTY，可输字母数字；`imeOptions=actionDone\|flagNoExtractUi` 未动 | 真机试一次输 16 位 alnum |
| 正则放宽后 `^.{1,64}$` 放行任意字符 | 连空格/中文都能过。对"卡密"场景无害（服务端自己判卡） | 若想更严可写 `^[A-Za-z0-9_-]{1,64}$`（19 B，smali 源改无长度限制） |
| 正则被别处共用 | `isPhoneLegal` 只被登录/发码两处用；绑手机流程也会一并放宽 | 可接受（本改造目的就是放宽） |
| **回滚** | 去掉 `res/Q9.xml` + `classes.dex` 替换 | — |

### 全局风险（三改造共有）

| 风险 | 评估 |
|---|---|
| **改资源会不会触发 ACE 定点校验** | 研究文档 §6 第 3 条已说明：ACE 已知钉死的是 `libunity.so` / `libtprt.so`，**资源层无任何校验点记录**；`assets/__tpinfo.*` 基线里已删除（我实测确认 5/5 不存在）。本方案**只动 `res/Q9.xml`（AXML 布局，运行期只被 `LayoutInflater` 读）+ `classes.dex`**，`resources.arsc` 一个字节不动 ⇒ **比"改 arsc 文案"风险更低**。但「改 res/*.xml 后跑通」**仍然没有一次真机实测记录**，这是本方案最大的未验证项 |
| 重签后装不上 | `build_noroot_apk.py` 自带 v1+v2+v3 签名，参数与现网一致（同一 keystore/alias/pass）⇒ 与现网包同签名，可直接覆盖安装 |
| 2.1 GB 出包时间 | 纯 Python 逐条重压缩，单次出包较慢（脚本已有 `--align-mode raw` + 1 MB 分块摘要），**别中断** |
| `/mnt/c` 大小写折叠 | §1.3 第 2 条，构建必须在 WSL ext4 |

---

## 6. 我没把握的地方（直说）

1. **「改 `res/*.xml` 后整机跑通」没有一次实测。** 已知校验点都在 native 层（`libunity.so` / `libtprt.so`），资源层无记录 —— 但"没记录"不等于"没有"。**验证办法**：第二步出包后先冷启动到取昵称界面（约 45 s），确认不 SIGBUS；再看 `adb logcat -s AiriSDK`。
2. **`android:id` 不能写裸 int**。我原想用合成 id（`0x7e000001`）省掉资源表改动，但 `TypedArray.getResourceId()` 对非 `TYPE_REFERENCE` 的值返回 `defValue`（= `View.NO_ID`），合成 id 大概率失效。所以最终方案改成**完全不要 id**（`getChildAt` + `indexOfChild`），这条路我推演过指令级但**没上真机**。
3. **`getChildAt(2)` 依赖布局节点顺序**。我加了空值保护（取不到就跳过），但"取错位置"这种失败模式不会崩、只会静默不显示 —— 真机上如果两个按钮没出现，第一个要查的就是这个索引。
4. **`RadioGroup` 给无 id 的 `RadioButton` 自动 `generateViewId()` 的行为**，我只从 AOSP 源码推断，**没有在 API 24–33 各版本真机验证**。缓解：我们不读 `getCheckedRadioButtonId()`，只 `setChecked(true)` + 自己挂 `OnClickListener`，所以即使不生成 id 也能工作。
5. **`classes.dex` 走 smali 往返（9,327,708 → 9,330,304，+2,596 B）后能否正常运行，没验证。** 空改回编的 dex 我只确认了"能编出来"，`baksmali`/`smali` 对这份混淆 dex 是否 100% 保真，只有真机能证。**备用路线已备好**：改造 3 的正则走原位 9 字节补丁；改造 2 若必须避免整 dex 重编，可改做 `code_item` 重定位（把 `handleErrorCode` 的 `code_item` 追加到 dex 尾部、把 `class_data_item` 里那个 4 字节 uleb 的 `code_off` 原地改指，再重算 adler32/sha1）—— 这条路**能把 `classes.dex` 的 diff 压到 ~150 字节**，但要多写 ~150 行 Python，第二步如果 smali 路线出问题我再上。
6. **`android:inputType="text"` 在真机输入法下的实际键盘**（是否带字母、是否会因 `textColorHint`/`clearButtonMode` 交互出怪）没验。研究文档 §6 第 1 条也把这条列为待验。**具体办法**：真机输入 16 位 alnum（如 `A1B2C3D4E5F6G7H8`）→ 看是否被截断、能否提交、`logcat -s AiriSDK` 里是否出现 `mobileLoginSuspend` / 拿到 200。
7. **服务端配合项未确认**：`/user/login` 失败时 `Msg` 必须非空（空则回落 `UN_KNOW_ERROR`）；`/common/client-code` 若实现了**不要**给封禁码配 `Type:"toast"`/`"none"`（否则盖掉弹窗分支）。这两条我在客户端侧只能"保证不吞"，管不了服务端配置。
8. **`aapt2` 独立可执行没装**（apktool 自带的那份够回编，但第二步若要 `aapt2 dump badging` 得从 Google Maven 补一个）。
9. **`work\ba\apk_patch\decode\` 是 192 MB 的查阅副本，且因 NTFS 大小写折叠丢了几个同名 smali**（§1.3）。**别拿它当构建输入**。

---

## 7. 第二步待批准的清单（等你放行）

| # | 动作 | 产物 |
|---|---|---|
| 1 | 改 `res/layout/fragment_default_mobile_code_login.xml`：加 RadioGroup + `et_phone` 的 `maxLength=64` / `inputType=text` | — |
| 2 | 改 3 个 smali（`DefaultMobileLoginFragment` ×3 处、`HttpCallBack` ×1 处、`CommonUtil` ×1 处） | — |
| 3 | `apktool b`（WSL ext4） → 抽 `res/layout/….xml` → 改名 `res/Q9.xml`；抽 `classes.dex` | 2 个替换件 |
| 4 | `build_noroot_apk.py --src 基线 --out BlueArchive_cardlogin_v1.apk --asset-replace res/Q9.xml=… --asset-replace classes.dex=… --sdk-url https://example.com/sdk --keystore ba_private.keystore --storepass baserver --alias ba` | **`BlueArchive_cardlogin_v1.apk`** |
| 5 | 自检：`aapt dump badging`（包名/版本/minSdk 不变）、`apksigner verify --print-certs`、zip 结构逐条目 diff（列出变了哪些、各变几字节）、sha256 + 字节数 | 自检报告 |
| 6 | 你决定是否同时出「仅原位 9 字节 dex 补丁」的保守版 | — |

**当前未产出任何 APK，等你确认 §4 的落点后再执行第二步。**
