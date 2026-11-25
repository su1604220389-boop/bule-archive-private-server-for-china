# SELFTEST — `v2_layoutonly.apk` / `v3_dexpatch.apk`

- 生成器：`work/ba/apk_patch/v2v3/make_report.py`（把所有原始日志逐字嵌进来，不重打）
- 基线：`work/ba/apk_patch/backup/BA_noroot_prod_20261118_v1.apk`
  - 字节数 `2127971177`，sha256 `5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6`
- 结论：**两个包 5 项自检全部通过，可以交付**。dex 那一包是"结构不变、只换 6 个字符值"的对照实验。

## 0. 一页结论

| 项 | v2_layoutonly | v3_dexpatch |
|---|---|---|
| 路径 | `work\ba\apk_patch\out\v2_layoutonly.apk` | `work\ba\apk_patch\out\v3_dexpatch.apk` |
| 字节数 | **2127972169** | **2133473392** |
| sha256 | `562d528a951eaeb15ae3165ece4a7ceb91849bb21ef54c895c6f217f9a676d64` | `6e5dcfb0317db175cec1be0719fad8271f6cae9abb5f3da84b571a36f6d2de25` |
| resources.arsc sha256 | `cd8943ae…9eecb86` ✅与基线相同 | `cd8943ae…9eecb86` ✅与基线相同 |
| aapt badging 身份 diff | **0 行** | **0 行** |
| zip 变化条目 | **4** 条（res/Q9.xml + 3×META-INF） | **5** 条（res/Q9.xml + classes.dex + 3×META-INF） |
| 新增/删除条目 | 0 / 0 | 0 / 0 |
| apksigner verify | `Verifies`（v2+v3 方案，证书 `94fa997b…9eebc` 与基线同一张） | 同左 |
| classes.dex | 与基线**逐字节相同**（sha256 `56b3a73b…`） | 9 字节窗口覆盖，**大小不变 9,327,708**；全文件仅 **30 B** 不同（24 B 头 + 6 B 载荷） |

### 与上一版失败包（E43）的本质区别

| | `BlueArchive_cardlogin_v1.apk`（卡启动界面） | `v3_dexpatch.apk`（本次） |
|---|---|---|
| dex 怎么来的 | baksmali → smali → **重新汇编**成新 dex | 从基线包里**原样取出**，只做 9 字节窗口的字节覆盖 |
| dex 大小 | 9,327,708 → **9,330,900**（+3,192 B） | 9,327,708 → **9,327,708**（+0 B） |
| dex 内部结构 | string_ids/data 段/偏移表/指令编码全部重排 | **一个偏移都没动**：所有 section 偏移、file_size、map_list 原封不动 |
| 文件级差异 | 数十万字节 | **30 B**（`0x08..0x1f` 的 24 B 头 + `0x70eb5b..0x70eb60` 的 6 B） |
| 归因 | 启动链不接受 dex 结构变化（`_dd4-integrity.md:105/444`） | 结构未变 ⇒ 该归因不再适用；只剩"内容哈希校验"这一种可能被拒原因 |

> 换句话说：v2 验证"布局层能不能换"；v3 在 v2 之上把 E43 的变量从 **结构重建** 缩到 **6 个字符值**，如果 v3 也卡启动界面，那就不再是结构问题，而是内容哈希/签名类校验，排查方向完全不同。

---

## 1. 输入与工具链

```
基线 APK      work/ba/apk_patch/backup/BA_noroot_prod_20261118_v1.apk
              2,127,971,177 B   sha256 5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6
              41,307 zip 条目   package com.RoamingStar.BlueArchive  versionCode 73  versionName 3.0.2
                              minSdk 24  targetSdk 33
keystore      work/ba/noroot/ba_private.keystore   alias=ba storepass=baserver
              证书 SHA-256 94FA997BE0DEBB69F1C62D766664FA8A879839DC9F710F6EEBD0C413DEE99EBC（与基线同一张）
解码树        /root/ba_work/dec0   （WSL ext4；apktool 2.11.1 从 slim.apk 解码）
打包器        work/ba/noroot/build_noroot_apk.py  (--asset-replace NAME=PATH)
工具          java 21 / apktool 2.11.1 (/opt/ba-tools/apktool.jar) / aapt v0.2-debian / apksigner / python3 3.12
```

- 全程**没有**执行 `apktool b`（不带 `-s`）产出过 dex：包 1 的资源编译用 `apktool b -s`（`--no-src`，只编 res、不汇编 smali），其产物里的 `classes.dex / classes2.dex` 检查结果为 **不存在**（见 §3.0）。最终两个包的 `classes.dex` 都来自基线包本身（v2 原样、v3 打 9 字节补丁）。

---

## 2. 自检 5 项：原始输出

> 下面是 `python3 work/ba/apk_patch/v2v3/selftest.py` 的完整 stdout，未经编辑。

```
# SELF-TEST  v2_layoutonly.apk / v3_dexpatch.apk

baseline : /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/backup/BA_noroot_prod_20261118_v1.apk
v2       : /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/out/v2_layoutonly.apk
v3       : /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/out/v3_dexpatch.apk

## 5) package digest / size

| file | bytes | sha256 |
|---|---|---|
| BA_noroot_prod_20261118_v1.apk | 2127971177 | `5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6` |
| v2_layoutonly.apk | 2127972169 | `562d528a951eaeb15ae3165ece4a7ceb91849bb21ef54c895c6f217f9a676d64` |
| v3_dexpatch.apk | 2133473392 | `6e5dcfb0317db175cec1be0719fad8271f6cae9abb5f3da84b571a36f6d2de25` |

* baseline sha256 == spec `5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6` -> OK

## 1) resources.arsc  (must be byte-identical to baseline)

| entry | baseline | v2 | v3 |
|---|---|---|---|
| `resources.arsc` | `cd8943ae979fd434…` (1156308 B) | `cd8943ae979fd434…` (1156308 B) | `cd8943ae979fd434…` (1156308 B) |
| `classes.dex` | `56b3a73b3039db99…` (9327708 B) | `56b3a73b3039db99…` (9327708 B) | `0ed8bbf878170c02…` (9327708 B) |
| `classes2.dex` | `dca6f88a614fd766…` (10158904 B) | `dca6f88a614fd766…` (10158904 B) | `dca6f88a614fd766…` (10158904 B) |
| `AndroidManifest.xml` | `9a07ec83802b9b6f…` (50552 B) | `9a07ec83802b9b6f…` (50552 B) | `9a07ec83802b9b6f…` (50552 B) |
| `res/Q9.xml` | `cc12543bbb5b977e…` (7292 B) | `8907d9b258c918c0…` (8284 B) | `8907d9b258c918c0…` (8284 B) |

* v2_layoutonly resources.arsc sha256 = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`  -> OK
* v3_dexpatch resources.arsc sha256 = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`  -> OK
* expected (spec)            = `cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`

* AndroidManifest.xml unchanged in both packages: True
* classes2.dex unchanged in both packages: True
* v2 classes.dex == baseline classes.dex: True
* v3 classes.dex sha256 = `0ed8bbf878170c02d8d34dd9e974108b6268287b6d0dc897a8246a2634f141e2`

## 4) apksigner verify --print-certs

### BA_noroot_prod_20261118_v1.apk  -> exit 0
```
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
Signer #1 certificate DN: CN=ba, OU=Private, O=BA, C=CN
Signer #1 certificate SHA-256 digest: 94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc
Signer #1 certificate SHA-1 digest: b584e21cd77a635cc42e8ac5bed4b992e3610037
Signer #1 certificate MD5 digest: 1ce17d9b7b789a1d7c69297f3fa74ed5
Signer #1 key algorithm: RSA
Signer #1 key size (bits): 2048
Signer #1 public key SHA-256 digest: 97e2558ab1a0336accfa4c0bb0262b6a04791bbe99dbd62a2dd863a93ce7403a
Signer #1 public key SHA-1 digest: 4a2cf6efbca958df7aee6d4c15f8535cf8632267
Signer #1 public key MD5 digest: 865841a0227e10f1c9e508cce738f326
```

### v2_layoutonly.apk  -> exit 0
```
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
Signer #1 certificate DN: CN=ba, OU=Private, O=BA, C=CN
Signer #1 certificate SHA-256 digest: 94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc
Signer #1 certificate SHA-1 digest: b584e21cd77a635cc42e8ac5bed4b992e3610037
Signer #1 certificate MD5 digest: 1ce17d9b7b789a1d7c69297f3fa74ed5
Signer #1 key algorithm: RSA
Signer #1 key size (bits): 2048
Signer #1 public key SHA-256 digest: 97e2558ab1a0336accfa4c0bb0262b6a04791bbe99dbd62a2dd863a93ce7403a
Signer #1 public key SHA-1 digest: 4a2cf6efbca958df7aee6d4c15f8535cf8632267
Signer #1 public key MD5 digest: 865841a0227e10f1c9e508cce738f326
```

### v3_dexpatch.apk  -> exit 0
```
Verifies
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): true
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v4 scheme (APK Signature Scheme v4): false
Verified for SourceStamp: false
Number of signers: 1
Signer #1 certificate DN: CN=ba, OU=Private, O=BA, C=CN
Signer #1 certificate SHA-256 digest: 94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc
Signer #1 certificate SHA-1 digest: b584e21cd77a635cc42e8ac5bed4b992e3610037
Signer #1 certificate MD5 digest: 1ce17d9b7b789a1d7c69297f3fa74ed5
Signer #1 key algorithm: RSA
Signer #1 key size (bits): 2048
Signer #1 public key SHA-256 digest: 97e2558ab1a0336accfa4c0bb0262b6a04791bbe99dbd62a2dd863a93ce7403a
Signer #1 public key SHA-1 digest: 4a2cf6efbca958df7aee6d4c15f8535cf8632267
Signer #1 public key MD5 digest: 865841a0227e10f1c9e508cce738f326
```

## 2) aapt dump badging identity fields

### baseline
```
package: name='com.RoamingStar.BlueArchive' versionCode='73' versionName='3.0.2' platformBuildVersionName='13' platformBuildVersionCode='33' compileSdkVersion='33' compileSdkVersionCodename='13'
sdkVersion:'24'
targetSdkVersion:'33'
```

### v2_layoutonly.apk
```
package: name='com.RoamingStar.BlueArchive' versionCode='73' versionName='3.0.2' platformBuildVersionName='13' platformBuildVersionCode='33' compileSdkVersion='33' compileSdkVersionCodename='13'
sdkVersion:'24'
targetSdkVersion:'33'
```

* diff vs baseline = **0 line(s)** 

### v3_dexpatch.apk
```
package: name='com.RoamingStar.BlueArchive' versionCode='73' versionName='3.0.2' platformBuildVersionName='13' platformBuildVersionCode='33' compileSdkVersion='33' compileSdkVersionCodename='13'
sdkVersion:'24'
targetSdkVersion:'33'
```

* diff vs baseline = **0 line(s)** 

## 3) zip entry diff (per entry: size / crc32 / method / sha256)

### v2_layoutonly.apk

* entries: baseline 41307 / this 41307
* **changed entries (4)**:

| entry | old size | new size | old crc32 | new crc32 | old method | new method |
|---|---|---|---|---|---|---|
| `META-INF/CERT.RSA` | 1208 | 1208 | 164bde63 | 0e26fe6b | 0 | 0 |
| `META-INF/CERT.SF` | 156 | 156 | 759ecf8c | d156a581 | 0 | 0 |
| `META-INF/MANIFEST.MF` | 5151246 | 5151246 | 1fef5173 | c9adf0b7 | 0 | 0 |
| `res/Q9.xml` | 7292 | 8284 | 22a6215c | e90efac7 | 0 | 0 |

* only-in-baseline: none
* only-in-new: none

* `res/Q9.xml` content sha256: `22a6215c` -> `e90efac7`
* changed entries outside {res/Q9.xml + META-INF/*}: **none**

### v3_dexpatch.apk

* entries: baseline 41307 / this 41307
* **changed entries (5)**:

| entry | old size | new size | old crc32 | new crc32 | old method | new method |
|---|---|---|---|---|---|---|
| `META-INF/CERT.RSA` | 1208 | 1208 | 164bde63 | b7b37036 | 0 | 0 |
| `META-INF/CERT.SF` | 156 | 156 | 759ecf8c | 63deb21a | 0 | 0 |
| `META-INF/MANIFEST.MF` | 5151246 | 5151246 | 1fef5173 | 02552d57 | 0 | 0 |
| `classes.dex` | 9327708 | 9327708 | ce71d74e | 443c22ce | 8 | 0 |
| `res/Q9.xml` | 7292 | 8284 | 22a6215c | e90efac7 | 0 | 0 |

* only-in-baseline: none
* only-in-new: none

* `classes.dex` content sha256: `ce71d74e` -> `443c22ce`
* `res/Q9.xml` content sha256: `22a6215c` -> `e90efac7`
* changed entries outside {res/Q9.xml, classes.dex + META-INF/*}: **none**


---

raw log written to /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/v2v3/selftest_out.txt
```

### 2.1 打包器自带校验（v2）

```
��= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = 
 
   B A   �V
gMQ  r o o t   9e �
 
   s r c   :   w o r k \ b a \ a p k _ p a t c h \ b a c k u p \ B A _ n o r o o t _ p r o d _ 2 0 2 6 1 1 1 8 _ v 1 . a p k   ( 1 . 9 8   G B ) 
 
   o u t   :   w o r k \ b a \ a p k _ p a t c h \ o u t \ v 2 _ l a y o u t o n l y . a p k 
 
 = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = 
 
 [ * ]   �nS���N:   p a c k a g e = c o m . R o a m i n g S t a r . B l u e A r c h i v e   v e r s i o n C o d e = 7 3   v e r s i o n N a m e = 3 . 0 . 2   m i n S d k = 2 4   t a r g e t S d k = 3 3   n s c = 0 x 7 F 1 2 0 0 0 1 
 
 [ * ]   ~{
T��fN  S H A - 2 5 6   =   9 4 F A 9 9 7 B E 0 D E B B 6 9 F 1 C 6 2 D 7 6 6 6 6 4 F A 8 A 8 7 9 8 3 9 D C 9 F 7 1 0 F 6 E E B D 0 C 4 1 3 D E E 9 9 E B C 
 
 [ 1 ]   r e s / D k . x m l :   5 6 0   B   - >   5 6 0   B     ( c a _ m o d e = u s e r ) 
 
 [ 2 ]   �Ǐ�*g�~  - - s d k - u r l 	�
 
 [ 2 b ]   �Ǐ  G a m e M a i n C o n f i g �*g�~  - - g m c o n f i g - u r l   /   - - a s s e t - r e p l a c e 	�
 
 [ 2 c ]   r e s / Q 9 . x m l :   7 2 9 2   B   - >   8 2 8 4   B     ( - - a s s e t - r e p l a c e   w o r k \ b a \ a p k _ p a t c h \ v 2 v 3 \ r e s _ Q 9 _ n e w . a x m l ) 
 
 [ 6 ]   TRd��e~{
T  M E T A - I N F / M A N I F E S T . M F   ( 5 1 5 1 2 4 6   B ) 
 
 [ 6 ]   TRd��e~{
T  M E T A - I N F / C E R T . S F   ( 1 5 6   B ) 
 
 [ 6 ]   TRd��e~{
T  M E T A - I N F / C E R T . R S A   ( 1 2 0 8   B ) 
 
 [ 5 ]   r e s o u r c e s . a r s c   n,{  1   ag�a l i g n _ m o d e = r a w 	�
 
 [ 5 ]   r e s o u r c e s . a r s c :   S T O R E D   1 1 5 6 3 0 8   B �,{  1   ag
 
 [ * ]   �QeQ  4 1 3 0 4   ag�v  - >   w o r k \ b a \ a p k _ p a t c h \ o u t \ v 2 _ l a y o u t o n l y . a p k . t m p 
 
             8 0 0 0 / 4 1 3 0 4     5 9 3 . 2 0   M B 
 
           1 6 0 0 0 / 4 1 3 0 4     9 8 1 . 5 7   M B 
 
           2 4 0 0 0 / 4 1 3 0 4     1 . 3 0   G B 
 
           3 2 0 0 0 / 4 1 3 0 4     1 . 5 8   G B 
 
           4 0 0 0 0 / 4 1 3 0 4     1 . 8 5   G B 
 
 [ 6 ]   v 1 :   M A N I F E S T . M F   5 1 5 1 2 4 6   B   /   C E R T . S F   1 5 6   B   /   C E R T . R S A   1 2 0 8   B 
 
 [ * ]   �Q�[Xd��  b 9 3 7 0 d f 5 b 1 0 f 5 3 c 1 e 7 5 5 f 9 d 6 1 7 d e f f e a f a 7 d d 0 4 a 7 4 d 0 6 d c c f 0 9 c c b 1 f a 9 1 a 5 7 d 3 
 
 [ 6 ]   v 2   1 4 1 8   B   +   v 3   1 4 3 4   B �~{
TWWqQ  2 9 0 8   B   @ 2 1 2 3 8 3 5 3 0 8 
 
 [ * ]   �Q�[  2 4 . 6 s �1 . 9 8   G B 
 
 [ * ]   !h��  w o r k \ b a \ a p k _ p a t c h \ o u t \ v 2 _ l a y o u t o n l y . a p k   ( 1 . 9 8   G B ) 
 
     E O C D   e n t r i e s = 4 1 3 0 7   c d _ s i z e = 4 1 3 3 9 3 1   c d _ o f f s e t = 2 1 2 3 8 3 8 2 1 6   c o m m e n t = 0 
 
     A P K   S i g n i n g   B l o c k :   O K   @ 2 1 2 3 8 3 5 3 0 8   ( 2 9 0 0   B ) 
 
     c o n t e n t   d i g e s t   =   b 9 3 7 0 d f 5 b 1 0 f 5 3 c 1 e 7 5 5 f 9 d 6 1 7 d e f f e a f a 7 d d 0 4 a 7 4 d 0 6 d c c f 0 9 c c b 1 f a 9 1 a 5 7 d 3 
 
     v 2 :   O K 
 
     v 3 :   O K 
 
     z i p   �[te'`:   O K 
 
     v 2 / v 3   ~{
T���fN  S H A - 2 5 6   =   9 4 F A 9 9 7 B E 0 D E B B 6 9 F 1 C 6 2 D 7 6 6 6 6 4 F A 8 A 8 7 9 8 3 9 D C 9 F 7 1 0 F 6 E E B D 0 C 4 1 3 D E E 9 9 E B C 
 
     v 1 :   M A N I F E S T . M F   5 1 5 1 2 4 6   B ,   4 1 3 0 4   *N  N a m e   �k
 
     v 1 :    g�L�  7 0   B ,   ��  7 2   B   �vL�  0   *N�O K 	�
 
             . . . �]��  2 0 0 0 0   ag
 
             . . . �]��  4 0 0 0 0   ag
 
     v 1 :   �agXd��  4 1 3 0 4   ag,   
N&{  0 ,   ag�v:1Y  0   O K 
 
     v 1 :   *g��  M A N I F E S T   ���v�vag�v  0   *N
 
     v 1 :   M E T A - I N F   ~{
T�e�N  3   *N  [ M A N I F E S T . M F ,   C E R T . S F ,   C E R T . R S A ] 
 
     v 1 :   M E T A - I N F / C E R T . S F   S H A - 2 5 6 - D i g e s t - M a n i f e s t   O K �0   *N�ag�k	�
 
     v 1 :   X - A n d r o i d - A P K - S i g n e d   =   ' 2 ,   3 ' ��Xf  [ 2 ,   3 ] �A P K   �[	g  [ 2 ,   3 ] 	�
 
     v 1 :   M E T A - I N F / C E R T . R S A   �[  . S F   �v  P K C S # 7   ��~{  O K 
 
     v 1 :   ~{
T���fN  S H A - 2 5 6   =   9 4 F A 9 9 7 B E 0 D E B B 6 9 F 1 C 6 2 D 7 6 6 6 6 4 F A 8 A 8 7 9 8 3 9 D C 9 F 7 1 0 F 6 E E B D 0 C 4 1 3 D E E 9 9 E B C 
 
     v 1 :   ~{
T���fN  S P K I   2 9 4   B 
 
     v 1   N  v 2 / v 3   ��fN N�:   O K 
 
     v 1   �~��:   O K 
 
     S T O R E D   4   W[���[P�:   O K 
 
     ͑
Yag�v:   �e�O K 	�
 
     r e s o u r c e s . a r s c :   ,{  1   ag,   S T O R E D = T r u e ,   4   W[���[P�= T r u e 
 
     _ _ t p i n f o   �kYu:   �e�O K 	�
 
     G a m e M a i n C o n f i g :   5 2 1 2   B ,   m _ S c r i p t = 1 0 9 0   B ,   W[�k  6 / 6 
 
         S k i p T u t o r i a l               =   ' F a l s e ' 
 
         S e r v e r I n f o D a t a U r l     =   ' [ " h t t p s : / / x u l i e h a o c h a x u . c n / a p i / s t a t e " ] ' 
 
         S e r v e r N a m e                   =   ' p r o d ' 
 
         V e r s i o n C o d e                 =   ' 7 3 ' 
 
         P l a t f o r m I D                   =   ' 1 ' 
 
         C h a n n e l I D                     =   ' 1 ' 
 
     r e s / D k . x m l   ㉐g�
 
         < n e t w o r k - s e c u r i t y - c o n f i g > 
 
             < b a s e - c o n f i g   c l e a r t e x t T r a f f i c P e r m i t t e d = " t r u e " > 
 
                 < t r u s t - a n c h o r s > 
 
                     < c e r t i f i c a t e s   s r c = " s y s t e m " > 
 
                     < / c e r t i f i c a t e s > 
 
                     < c e r t i f i c a t e s   s r c = " u s e r " > 
 
                     < / c e r t i f i c a t e s > 
 
                 < / t r u s t - a n c h o r s > 
 
             < / b a s e - c o n f i g > 
 
         < / n e t w o r k - s e c u r i t y - c o n f i g > 
 
 
 
   ���Q  w o r k \ b a \ a p k _ p a t c h \ o u t \ v 2 _ l a y o u t o n l y . a p k   ( 1 . 9 8   G B ) 
 
   �~�g�O K 
 
 
```

### 2.2 打包器自带校验（v3）

```
��= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = 
 
   B A   �V
gMQ  r o o t   9e �
 
   s r c   :   w o r k \ b a \ a p k _ p a t c h \ b a c k u p \ B A _ n o r o o t _ p r o d _ 2 0 2 6 1 1 1 8 _ v 1 . a p k   ( 1 . 9 8   G B ) 
 
   o u t   :   w o r k \ b a \ a p k _ p a t c h \ o u t \ v 3 _ d e x p a t c h . a p k 
 
 = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = 
 
 [ * ]   �nS���N:   p a c k a g e = c o m . R o a m i n g S t a r . B l u e A r c h i v e   v e r s i o n C o d e = 7 3   v e r s i o n N a m e = 3 . 0 . 2   m i n S d k = 2 4   t a r g e t S d k = 3 3   n s c = 0 x 7 F 1 2 0 0 0 1 
 
 [ * ]   ~{
T��fN  S H A - 2 5 6   =   9 4 F A 9 9 7 B E 0 D E B B 6 9 F 1 C 6 2 D 7 6 6 6 6 4 F A 8 A 8 7 9 8 3 9 D C 9 F 7 1 0 F 6 E E B D 0 C 4 1 3 D E E 9 9 E B C 
 
 [ 1 ]   r e s / D k . x m l :   5 6 0   B   - >   5 6 0   B     ( c a _ m o d e = u s e r ) 
 
 [ 2 ]   �Ǐ�*g�~  - - s d k - u r l 	�
 
 [ 2 b ]   �Ǐ  G a m e M a i n C o n f i g �*g�~  - - g m c o n f i g - u r l   /   - - a s s e t - r e p l a c e 	�
 
 [ 2 c ]   r e s / Q 9 . x m l :   7 2 9 2   B   - >   8 2 8 4   B     ( - - a s s e t - r e p l a c e   w o r k \ b a \ a p k _ p a t c h \ v 2 v 3 \ r e s _ Q 9 _ n e w . a x m l ) 
 
 [ 2 c ]   c l a s s e s . d e x :   9 3 2 7 7 0 8   B   - >   9 3 2 7 7 0 8   B     ( - - a s s e t - r e p l a c e   w o r k \ b a \ a p k _ p a t c h \ v 2 v 3 \ c l a s s e s _ p a t c h e d . d e x ) 
 
 [ 6 ]   TRd��e~{
T  M E T A - I N F / M A N I F E S T . M F   ( 5 1 5 1 2 4 6   B ) 
 
 [ 6 ]   TRd��e~{
T  M E T A - I N F / C E R T . S F   ( 1 5 6   B ) 
 
 [ 6 ]   TRd��e~{
T  M E T A - I N F / C E R T . R S A   ( 1 2 0 8   B ) 
 
 [ 5 ]   r e s o u r c e s . a r s c   n,{  1   ag�a l i g n _ m o d e = r a w 	�
 
 [ 5 ]   r e s o u r c e s . a r s c :   S T O R E D   1 1 5 6 3 0 8   B �,{  1   ag
 
 [ * ]   �QeQ  4 1 3 0 4   ag�v  - >   w o r k \ b a \ a p k _ p a t c h \ o u t \ v 3 _ d e x p a t c h . a p k . t m p 
 
             8 0 0 0 / 4 1 3 0 4     5 9 8 . 4 4   M B 
 
           1 6 0 0 0 / 4 1 3 0 4     9 8 6 . 8 2   M B 
 
           2 4 0 0 0 / 4 1 3 0 4     1 . 3 0   G B 
 
           3 2 0 0 0 / 4 1 3 0 4     1 . 5 8   G B 
 
           4 0 0 0 0 / 4 1 3 0 4     1 . 8 5   G B 
 
 [ 6 ]   v 1 :   M A N I F E S T . M F   5 1 5 1 2 4 6   B   /   C E R T . S F   1 5 6   B   /   C E R T . R S A   1 2 0 8   B 
 
 [ * ]   �Q�[Xd��  9 f 0 e 8 2 3 c 5 f 0 7 1 1 d 4 b a e f 1 c 2 8 f 3 1 8 6 4 3 3 d b 7 6 6 5 6 3 e 6 8 d 2 3 2 d e 7 e 9 b 5 f 3 d 5 f 3 c 3 9 7 
 
 [ 6 ]   v 2   1 4 1 8   B   +   v 3   1 4 3 4   B �~{
TWWqQ  2 9 0 8   B   @ 2 1 2 9 3 3 6 5 2 8 
 
 [ * ]   �Q�[  2 6 . 4 s �1 . 9 9   G B 
 
 [ * ]   !h��  w o r k \ b a \ a p k _ p a t c h \ o u t \ v 3 _ d e x p a t c h . a p k   ( 1 . 9 9   G B ) 
 
     E O C D   e n t r i e s = 4 1 3 0 7   c d _ s i z e = 4 1 3 3 9 3 4   c d _ o f f s e t = 2 1 2 9 3 3 9 4 3 6   c o m m e n t = 0 
 
     A P K   S i g n i n g   B l o c k :   O K   @ 2 1 2 9 3 3 6 5 2 8   ( 2 9 0 0   B ) 
 
     c o n t e n t   d i g e s t   =   9 f 0 e 8 2 3 c 5 f 0 7 1 1 d 4 b a e f 1 c 2 8 f 3 1 8 6 4 3 3 d b 7 6 6 5 6 3 e 6 8 d 2 3 2 d e 7 e 9 b 5 f 3 d 5 f 3 c 3 9 7 
 
     v 2 :   O K 
 
     v 3 :   O K 
 
     z i p   �[te'`:   O K 
 
     v 2 / v 3   ~{
T���fN  S H A - 2 5 6   =   9 4 F A 9 9 7 B E 0 D E B B 6 9 F 1 C 6 2 D 7 6 6 6 6 4 F A 8 A 8 7 9 8 3 9 D C 9 F 7 1 0 F 6 E E B D 0 C 4 1 3 D E E 9 9 E B C 
 
     v 1 :   M A N I F E S T . M F   5 1 5 1 2 4 6   B ,   4 1 3 0 4   *N  N a m e   �k
 
     v 1 :    g�L�  7 0   B ,   ��  7 2   B   �vL�  0   *N�O K 	�
 
             . . . �]��  2 0 0 0 0   ag
 
             . . . �]��  4 0 0 0 0   ag
 
     v 1 :   �agXd��  4 1 3 0 4   ag,   
N&{  0 ,   ag�v:1Y  0   O K 
 
     v 1 :   *g��  M A N I F E S T   ���v�vag�v  0   *N
 
     v 1 :   M E T A - I N F   ~{
T�e�N  3   *N  [ M A N I F E S T . M F ,   C E R T . S F ,   C E R T . R S A ] 
 
     v 1 :   M E T A - I N F / C E R T . S F   S H A - 2 5 6 - D i g e s t - M a n i f e s t   O K �0   *N�ag�k	�
 
     v 1 :   X - A n d r o i d - A P K - S i g n e d   =   ' 2 ,   3 ' ��Xf  [ 2 ,   3 ] �A P K   �[	g  [ 2 ,   3 ] 	�
 
     v 1 :   M E T A - I N F / C E R T . R S A   �[  . S F   �v  P K C S # 7   ��~{  O K 
 
     v 1 :   ~{
T���fN  S H A - 2 5 6   =   9 4 F A 9 9 7 B E 0 D E B B 6 9 F 1 C 6 2 D 7 6 6 6 6 4 F A 8 A 8 7 9 8 3 9 D C 9 F 7 1 0 F 6 E E B D 0 C 4 1 3 D E E 9 9 E B C 
 
     v 1 :   ~{
T���fN  S P K I   2 9 4   B 
 
     v 1   N  v 2 / v 3   ��fN N�:   O K 
 
     v 1   �~��:   O K 
 
     S T O R E D   4   W[���[P�:   O K 
 
     ͑
Yag�v:   �e�O K 	�
 
     r e s o u r c e s . a r s c :   ,{  1   ag,   S T O R E D = T r u e ,   4   W[���[P�= T r u e 
 
     _ _ t p i n f o   �kYu:   �e�O K 	�
 
     G a m e M a i n C o n f i g :   5 2 1 2   B ,   m _ S c r i p t = 1 0 9 0   B ,   W[�k  6 / 6 
 
         S k i p T u t o r i a l               =   ' F a l s e ' 
 
         S e r v e r I n f o D a t a U r l     =   ' [ " h t t p s : / / x u l i e h a o c h a x u . c n / a p i / s t a t e " ] ' 
 
         S e r v e r N a m e                   =   ' p r o d ' 
 
         V e r s i o n C o d e                 =   ' 7 3 ' 
 
         P l a t f o r m I D                   =   ' 1 ' 
 
         C h a n n e l I D                     =   ' 1 ' 
 
     r e s / D k . x m l   ㉐g�
 
         < n e t w o r k - s e c u r i t y - c o n f i g > 
 
             < b a s e - c o n f i g   c l e a r t e x t T r a f f i c P e r m i t t e d = " t r u e " > 
 
                 < t r u s t - a n c h o r s > 
 
                     < c e r t i f i c a t e s   s r c = " s y s t e m " > 
 
                     < / c e r t i f i c a t e s > 
 
                     < c e r t i f i c a t e s   s r c = " u s e r " > 
 
                     < / c e r t i f i c a t e s > 
 
                 < / t r u s t - a n c h o r s > 
 
             < / b a s e - c o n f i g > 
 
         < / n e t w o r k - s e c u r i t y - c o n f i g > 
 
 
 
   ���Q  w o r k \ b a \ a p k _ p a t c h \ o u t \ v 3 _ d e x p a t c h . a p k   ( 1 . 9 9   G B ) 
 
   �~�g�O K 
 
 
```

---

## 3. 包 1：布局层证据

### 3.0 包 1 用的 AXML 是怎么来的（关键：没有 dex 参与）

```
=== decoded XML edits ===
  - RadioGroup+2xRadioButton inserted after tv_bind_phone_desc (root child index 2)
  - input ConstraintLayout: marginTop dp7 -> 10.0dip
  - et_phone: 6 attrs changed
  - layout_phone_code: height dp40 -> 44.0dip (et_phone_code untouched)
  - login button: height 46.0dip, marginTop 16.0dip
  decoded xml 8915 B -> 10037 B

=== java -jar /opt/ba-tools/apktool.jar b -s -f -o /root/ba_work/v2_layout_build.apk /root/ba_work/decL ===
I: Using Apktool 2.11.1 on v2_layout_build.apk with 8 threads
I: Building resources with aapt2...
I: Building apk file...
I: Importing unknown files...
I: Built apk into: /root/ba_work/v2_layout_build.apk


=== throw-away build apk: 872 entries ===
  has classes.dex     : False
  has classes2.dex    : False
  has resources.arsc  : True
  res/layout/fragment_default_mobile_code_login.xml -> /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/v2v3/res_Q9_new.axml  8284 B  sha256=8907d9b258c918c057046ff267d86f1128a13153ece8e32bcfec9ec70a67559c
  (checked separately by selftest)
```

### 3.1 `res/Q9.xml` ↔ `R.layout.fragment_default_mobile_code_login` (0x7f0b0044)

```
$ aapt dump --values resources <基线>.apk | grep -A4 "resource 0x7f0b0044 "
      spec resource 0x7f0b0044 com.RoamingStar.BlueArchive:layout/fragment_default_mobile_code_login
        resource 0x7f0b0044 com.RoamingStar.BlueArchive:layout/fragment_default_mobile_code_login: t=0x03 d=0x000000bd
          (string8) "res/Q9.xml"

$ DefaultMobileLoginFragment.smali:253
    sget v0, Lcom/airi/official/core/R$layout;->fragment_default_mobile_code_login:I
$ R$layout.smali:55
.field public static final fragment_default_mobile_code_login:I = 0x7f0b0044
```

⇒ 登录页 inflate 的就是 `res/Q9.xml` 这一个 zip 条目，换它即可生效，不需要动 arsc。

### 3.2 改了哪些属性（解码 XML 层，人读版）

> `dec0` = 基线解码树，`decL` = 修改后交给 aapt2 的那一份。diff 里可见全部改动：

```diff
--- dec0/res/layout/fragment_default_mobile_code_login.xml
+++ decL/res/layout/fragment_default_mobile_code_login.xml
@@ -10,15 +10,19 @@
         <ImageView android:id="@id/iv_close" android:background="@drawable/close" android:layout_width="@dimen/dp24" android:layout_height="@dimen/dp24" android:scaleType="centerCrop" />
     </LinearLayout>
     <TextView android:textSize="@dimen/sp12" android:textColor="@color/c_6a6a6a" android:gravity="center" android:id="@id/tv_bind_phone_desc" android:visibility="gone" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginLeft="@dimen/dp32" android:layout_marginRight="@dimen/dp32" android:text="@string/bind_phone_desc" />
-    <androidx.constraintlayout.widget.ConstraintLayout android:paddingLeft="@dimen/dp24" android:paddingRight="@dimen/dp24" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="@dimen/dp7">
-        <com.airi.official.core.widget.ExtendEditText android:textSize="@dimen/sp14" android:textColor="@color/c_000000" android:textColorHint="@color/disable_text" android:id="@id/et_phone" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:hint="@string/hint_phone_number" android:singleLine="true" android:maxLength="11" android:inputType="phone" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="@dimen/dp12" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toTopOf="parent" />
-        <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/layout_phone_code" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:layout_marginTop="@dimen/dp12" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/et_phone">
+    <RadioGroup android:orientation="horizontal" android:gravity="center_vertical" android:background="#FFF5F6F8" android:paddingLeft="6.0dip" android:paddingTop="2.0dip" android:paddingRight="6.0dip" android:paddingBottom="2.0dip" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginLeft="@dimen/dp24" android:layout_marginTop="10.0dip" android:layout_marginRight="@dimen/dp24">
+        <RadioButton android:id="@android:id/text1" android:textSize="14.0sp" android:textColor="#FF2B3445" android:gravity="center" android:buttonTint="#FF2F6FED" android:paddingTop="8.0dip" android:paddingBottom="8.0dip" android:layout_width="0.0dip" android:layout_height="wrap_content" android:layout_weight="1.0" android:text="游客登录" android:checked="true" />
+        <RadioButton android:id="@android:id/text2" android:textSize="14.0sp" android:textColor="#FF2B3445" android:gravity="center" android:buttonTint="#FF2F6FED" android:paddingTop="8.0dip" android:paddingBottom="8.0dip" android:layout_width="0.0dip" android:layout_height="wrap_content" android:layout_weight="1.0" android:text="卡密登录" />
+    </RadioGroup>
+    <androidx.constraintlayout.widget.ConstraintLayout android:paddingLeft="@dimen/dp24" android:paddingRight="@dimen/dp24" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="10.0dip">
+        <com.airi.official.core.widget.ExtendEditText android:textSize="15.0sp" android:textColor="@color/c_000000" android:textColorHint="#FF9AA3B2" android:id="@id/et_phone" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="44.0dip" android:hint="@string/hint_phone_number" android:singleLine="true" android:maxLength="64" android:inputType="text" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="14.0dip" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toTopOf="parent" />
+        <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/layout_phone_code" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="44.0dip" android:layout_marginTop="@dimen/dp12" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/et_phone">
             <com.airi.official.core.widget.ExtendEditText android:textSize="@dimen/sp14" android:textColor="@color/c_000000" android:textColorHint="@color/disable_text" android:id="@id/et_phone_code" android:background="@null" android:layout_width="0.0dip" android:layout_height="@dimen/dp40" android:hint="@string/hint_phone_code" android:singleLine="true" android:maxLength="6" android:inputType="number" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="@dimen/dp12" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toLeftOf="@id/divide" app:layout_constraintTop_toTopOf="parent" />
             <TextView android:id="@id/divide" android:background="@color/divider_common" android:layout_width="@dimen/dp1" android:layout_height="@dimen/dp20" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintRight_toLeftOf="@id/get_phone_code" app:layout_constraintTop_toTopOf="parent" />
             <TextView android:textSize="@dimen/sp14" android:textColor="@color/disable_text" android:ellipsize="end" android:gravity="center" android:layout_gravity="center_horizontal" android:id="@id/get_phone_code" android:layout_width="@dimen/dp60" android:layout_height="wrap_content" android:text="@string/get_phone_code" android:singleLine="true" android:includeFontPadding="false" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toTopOf="parent" />
         </androidx.constraintlayout.widget.ConstraintLayout>
         <LinearLayout android:orientation="vertical" android:id="@id/ll_container_login" android:layout_width="fill_parent" android:layout_height="wrap_content" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/layout_phone_code">
-            <Button android:textSize="@dimen/sp16" android:textColor="@color/bt_text" android:id="@id/login" android:background="@drawable/login_btn_selector" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:layout_marginTop="@dimen/dp12" android:text="@string/login" />
+            <Button android:textSize="@dimen/sp16" android:textColor="@color/bt_text" android:id="@id/login" android:background="@drawable/login_btn_selector" android:layout_width="fill_parent" android:layout_height="46.0dip" android:layout_marginTop="16.0dip" android:text="@string/login" />
             <View android:id="@id/login_helper" android:visibility="gone" android:layout_width="fill_parent" android:layout_height="@dimen/dp12" />
         </LinearLayout>
         <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/agreement_layout" android:layout_width="fill_parent" android:layout_height="fill_parent" android:layout_marginTop="@dimen/dp12" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/ll_container_login">
@@ -40,3 +44,4 @@
         </FrameLayout>
     </androidx.constraintlayout.widget.ConstraintLayout>
 </LinearLayout>
+
```

### 3.3 根 LinearLayout 子节点顺序（新节点必须在 index 2）

```
=== root LinearLayout children, ORIGINAL res/Q9.xml (3) ===
  [0] LinearLayout
  [1] TextView
  [2] androidx.constraintlayout.widget.ConstraintLayout

=== root LinearLayout children, NEW res/Q9.xml (4) ===
  [0] LinearLayout
  [1] TextView
  [2] RadioGroup   <== NEW NODE
  [3] androidx.constraintlayout.widget.ConstraintLayout

RadioGroup index in the new tree      = 2
original order preserved (minus new)  = True
ids of the original children all still present in the new tree: checked by own_diff.txt: no android:id line changed

=== decoded XML diff (=what was edited before aapt2 compiled it) ===
--- dec0/res/layout/fragment_default_mobile_code_login.xml
+++ decL/res/layout/fragment_default_mobile_code_login.xml
@@ -10,15 +10,19 @@
         <ImageView android:id="@id/iv_close" android:background="@drawable/close" android:layout_width="@dimen/dp24" android:layout_height="@dimen/dp24" android:scaleType="centerCrop" />
     </LinearLayout>
     <TextView android:textSize="@dimen/sp12" android:textColor="@color/c_6a6a6a" android:gravity="center" android:id="@id/tv_bind_phone_desc" android:visibility="gone" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginLeft="@dimen/dp32" android:layout_marginRight="@dimen/dp32" android:text="@string/bind_phone_desc" />
-    <androidx.constraintlayout.widget.ConstraintLayout android:paddingLeft="@dimen/dp24" android:paddingRight="@dimen/dp24" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="@dimen/dp7">
-        <com.airi.official.core.widget.ExtendEditText android:textSize="@dimen/sp14" android:textColor="@color/c_000000" android:textColorHint="@color/disable_text" android:id="@id/et_phone" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:hint="@string/hint_phone_number" android:singleLine="true" android:maxLength="11" android:inputType="phone" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="@dimen/dp12" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toTopOf="parent" />
-        <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/layout_phone_code" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:layout_marginTop="@dimen/dp12" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/et_phone">
+    <RadioGroup android:orientation="horizontal" android:gravity="center_vertical" android:background="#FFF5F6F8" android:paddingLeft="6.0dip" android:paddingTop="2.0dip" android:paddingRight="6.0dip" android:paddingBottom="2.0dip" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginLeft="@dimen/dp24" android:layout_marginTop="10.0dip" android:layout_marginRight="@dimen/dp24">
+        <RadioButton android:id="@android:id/text1" android:textSize="14.0sp" android:textColor="#FF2B3445" android:gravity="center" android:buttonTint="#FF2F6FED" android:paddingTop="8.0dip" android:paddingBottom="8.0dip" android:layout_width="0.0dip" android:layout_height="wrap_content" android:layout_weight="1.0" android:text="游客登录" android:checked="true" />
+        <RadioButton android:id="@android:id/text2" android:textSize="14.0sp" android:textColor="#FF2B3445" android:gravity="center" android:buttonTint="#FF2F6FED" android:paddingTop="8.0dip" android:paddingBottom="8.0dip" android:layout_width="0.0dip" android:layout_height="wrap_content" android:layout_weight="1.0" android:text="卡密登录" />
+    </RadioGroup>
+    <androidx.constraintlayout.widget.ConstraintLayout android:paddingLeft="@dimen/dp24" android:paddingRight="@dimen/dp24" android:layout_width="fill_parent" android:layout_height="wrap_content" android:layout_marginTop="10.0dip">
+        <com.airi.official.core.widget.ExtendEditText android:textSize="15.0sp" android:textColor="@color/c_000000" android:textColorHint="#FF9AA3B2" android:id="@id/et_phone" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="44.0dip" android:hint="@string/hint_phone_number" android:singleLine="true" android:maxLength="64" android:inputType="text" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="14.0dip" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toTopOf="parent" />
+        <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/layout_phone_code" android:background="@drawable/login_edit_bg_fragment" android:layout_width="fill_parent" android:layout_height="44.0dip" android:layout_marginTop="@dimen/dp12" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/et_phone">
             <com.airi.official.core.widget.ExtendEditText android:textSize="@dimen/sp14" android:textColor="@color/c_000000" android:textColorHint="@color/disable_text" android:id="@id/et_phone_code" android:background="@null" android:layout_width="0.0dip" android:layout_height="@dimen/dp40" android:hint="@string/hint_phone_code" android:singleLine="true" android:maxLength="6" android:inputType="number" android:imeOptions="actionDone|flagNoExtractUi" android:paddingStart="@dimen/dp12" android:paddingEnd="@dimen/dp0" app:clearButtonMode="whileEditing" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toLeftOf="@id/divide" app:layout_constraintTop_toTopOf="parent" />
             <TextView android:id="@id/divide" android:background="@color/divider_common" android:layout_width="@dimen/dp1" android:layout_height="@dimen/dp20" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintRight_toLeftOf="@id/get_phone_code" app:layout_constraintTop_toTopOf="parent" />
             <TextView android:textSize="@dimen/sp14" android:textColor="@color/disable_text" android:ellipsize="end" android:gravity="center" android:layout_gravity="center_horizontal" android:id="@id/get_phone_code" android:layout_width="@dimen/dp60" android:layout_height="wrap_content" android:text="@string/get_phone_code" android:singleLine="true" android:includeFontPadding="false" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toTopOf="parent" />
         </androidx.constraintlayout.widget.ConstraintLayout>
         <LinearLayout android:orientation="vertical" android:id="@id/ll_container_login" android:layout_width="fill_parent" android:layout_height="wrap_content" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/layout_phone_code">
-            <Button android:textSize="@dimen/sp16" android:textColor="@color/bt_text" android:id="@id/login" android:background="@drawable/login_btn_selector" android:layout_width="fill_parent" android:layout_height="@dimen/dp40" android:layout_marginTop="@dimen/dp12" android:text="@string/login" />
+            <Button android:textSize="@dimen/sp16" android:textColor="@color/bt_text" android:id="@id/login" android:background="@drawable/login_btn_selector" android:layout_width="fill_parent" android:layout_height="46.0dip" android:layout_marginTop="16.0dip" android:text="@string/login" />
             <View android:id="@id/login_helper" android:visibility="gone" android:layout_width="fill_parent" android:layout_height="@dimen/dp12" />
         </LinearLayout>
         <androidx.constraintlayout.widget.ConstraintLayout android:id="@id/agreement_layout" android:layout_width="fill_parent" android:layout_height="fill_parent" android:layout_marginTop="@dimen/dp12" app:layout_constraintLeft_toLeftOf="parent" app:layout_constraintRight_toRightOf="parent" app:layout_constraintTop_toBottomOf="@id/ll_container_login">
@@ -40,3 +44,4 @@
         </FrameLayout>
     </androidx.constraintlayout.widget.ConstraintLayout>
 </LinearLayout>
+

decoded-xml diff lines: 31
```

### 3.4 自己写的 AXML 解析器：二进制层 diff（两份文件都不经 aapt）

> `axml_dump.py` 直接按 ResChunk 结构解析：字符串池 / 资源映射表 / 每个属性节点。它同时断言了"所有带 namespace 的属性都有非 0 资源 id"（`attrs-with-ns-but-no-resid: 0`）。

```diff
--- "/mnt/c/Users/su/Desktop/\345\244\247\350\202\245\351\261\274\351\241\271\347\233\256/BAServer/work/ba/apk_patch/v2v3/own_dump_orig.txt"	2026-11-18 19:43:41.317729500 +0800
+++ "/mnt/c/Users/su/Desktop/\345\244\247\350\202\245\351\261\274\351\241\271\347\233\256/BAServer/work/ba/apk_patch/v2v3/own_dump_new.txt"	2026-11-18 19:43:41.341808000 +0800
@@ -1,5 +1,5 @@
-# AXML /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/v2v3/res_Q9_orig.axml
-# size=7292 strings=53 utf8=True resmap=41 chunks=60 sha256=cc12543bbb5b977ebc229dfae334d9f10f9514b02f71b25d8e61b72d9a043dfd
+# AXML /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/v2v3/res_Q9_new.axml
+# size=8284 strings=59 utf8=True resmap=43 chunks=66 sha256=8907d9b258c918c057046ff267d86f1128a13153ece8e32bcfec9ec70a67559c
 NS android -> http://schemas.android.com/apk/res/android
 NS app -> http://schemas.android.com/apk/res-auto
 E: LinearLayout
@@ -63,26 +63,67 @@
   A: http://schemas.android.com/apk/res/android:layout_marginRight(0x010100f9) @0x7f060133 [REFERENCE]
   A: http://schemas.android.com/apk/res/android:text(0x0101014f) @0x7f0f0038 [REFERENCE]
 /E: TextView
+E: RadioGroup
+  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000010 [INT_HEX]
+  A: http://schemas.android.com/apk/res/android:orientation(0x010100c4) 0 [INT_DEC]
+  A: http://schemas.android.com/apk/res/android:background(0x010100d4) #fff5f6f8 [INT_COLOR_ARGB8]
+  A: http://schemas.android.com/apk/res/android:paddingLeft(0x010100d6) 6dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:paddingTop(0x010100d7) 2dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:paddingRight(0x010100d8) 6dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:paddingBottom(0x010100d9) 2dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
+  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
+  A: http://schemas.android.com/apk/res/android:layout_marginLeft(0x010100f7) @0x7f060103 [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) 10dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:layout_marginRight(0x010100f9) @0x7f060103 [REFERENCE]
+E: RadioButton
+  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) 14sp [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) #ff2b3445 [INT_COLOR_ARGB8]
+  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000011 [INT_HEX]
+  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x01020014 [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:paddingTop(0x010100d7) 8dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:paddingBottom(0x010100d9) 8dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 0dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
+  A: http://schemas.android.com/apk/res/android:checked(0x01010106) true [INT_BOOLEAN]
+  A: http://schemas.android.com/apk/res/android:text(0x0101014f) '游客登录' [STRING]
+  A: http://schemas.android.com/apk/res/android:layout_weight(0x01010181) 1.0 [FLOAT]
+  A: http://schemas.android.com/apk/res/android:buttonTint(0x0101046f) #ff2f6fed [INT_COLOR_ARGB8]
+/E: RadioButton
+E: RadioButton
+  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) 14sp [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:textColor(0x01010098) #ff2b3445 [INT_COLOR_ARGB8]
+  A: http://schemas.android.com/apk/res/android:gravity(0x010100af) 0x00000011 [INT_HEX]
+  A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x01020015 [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:paddingTop(0x010100d7) 8dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:paddingBottom(0x010100d9) 8dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 0dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
+  A: http://schemas.android.com/apk/res/android:text(0x0101014f) '卡密登录' [STRING]
+  A: http://schemas.android.com/apk/res/android:layout_weight(0x01010181) 1.0 [FLOAT]
+  A: http://schemas.android.com/apk/res/android:buttonTint(0x0101046f) #ff2f6fed [INT_COLOR_ARGB8]
+/E: RadioButton
+/E: RadioGroup
 E: androidx.constraintlayout.widget.ConstraintLayout
   A: http://schemas.android.com/apk/res/android:paddingLeft(0x010100d6) @0x7f060103 [REFERENCE]
   A: http://schemas.android.com/apk/res/android:paddingRight(0x010100d8) @0x7f060103 [REFERENCE]
   A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
   A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 4294967294 [INT_DEC]
-  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) @0x7f06016c [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) 10dip [DIMENSION]
 E: com.airi.official.core.widget.ExtendEditText
-  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) @0x7f06029e [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:textSize(0x01010095) 15sp [DIMENSION]
   A: http://schemas.android.com/apk/res/android:textColor(0x01010098) @0x7f05002d [REFERENCE]
-  A: http://schemas.android.com/apk/res/android:textColorHint(0x0101009a) @0x7f050091 [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:textColorHint(0x0101009a) #ff9aa3b2 [INT_COLOR_ARGB8]
   A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f080108 [REFERENCE]
   A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f0700b7 [REFERENCE]
   A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
-  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060145 [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 44dip [DIMENSION]
   A: http://schemas.android.com/apk/res/android:hint(0x01010150) @0x7f0f0074 [REFERENCE]
   A: http://schemas.android.com/apk/res/android:singleLine(0x0101015d) true [INT_BOOLEAN]
-  A: http://schemas.android.com/apk/res/android:maxLength(0x01010160) 11 [INT_DEC]
-  A: http://schemas.android.com/apk/res/android:inputType(0x01010220) 0x00000003 [INT_HEX]
+  A: http://schemas.android.com/apk/res/android:maxLength(0x01010160) 64 [INT_DEC]
+  A: http://schemas.android.com/apk/res/android:inputType(0x01010220) 0x00000001 [INT_HEX]
   A: http://schemas.android.com/apk/res/android:imeOptions(0x01010264) 0x10000006 [INT_HEX]
-  A: http://schemas.android.com/apk/res/android:paddingStart(0x010103b3) @0x7f0600a9 [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:paddingStart(0x010103b3) 14dip [DIMENSION]
   A: http://schemas.android.com/apk/res/android:paddingEnd(0x010103b4) @0x7f060090 [REFERENCE]
   A: http://schemas.android.com/apk/res-auto:clearButtonMode(0x7f0300be) 2 [INT_DEC]
   A: http://schemas.android.com/apk/res-auto:layout_constraintLeft_toLeftOf(0x7f03021a) 0 [INT_DEC]
@@ -93,7 +134,7 @@
   A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f08016f [REFERENCE]
   A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f0700b7 [REFERENCE]
   A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
-  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060145 [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 44dip [DIMENSION]
   A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) @0x7f0600a9 [REFERENCE]
   A: http://schemas.android.com/apk/res-auto:layout_constraintLeft_toLeftOf(0x7f03021a) 0 [INT_DEC]
   A: http://schemas.android.com/apk/res-auto:layout_constraintRight_toRightOf(0x7f03021e) 0 [INT_DEC]
@@ -159,8 +200,8 @@
   A: http://schemas.android.com/apk/res/android:id(0x010100d0) @0x7f080182 [REFERENCE]
   A: http://schemas.android.com/apk/res/android:background(0x010100d4) @0x7f0700b6 [REFERENCE]
   A: http://schemas.android.com/apk/res/android:layout_width(0x010100f4) 4294967295 [INT_DEC]
-  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) @0x7f060145 [REFERENCE]
-  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) @0x7f0600a9 [REFERENCE]
+  A: http://schemas.android.com/apk/res/android:layout_height(0x010100f5) 46dip [DIMENSION]
+  A: http://schemas.android.com/apk/res/android:layout_marginTop(0x010100f8) 16dip [DIMENSION]
   A: http://schemas.android.com/apk/res/android:text(0x0101014f) @0x7f0f009f [REFERENCE]
 /E: Button
 E: View
```

### 3.5 aapt 独立解析：归一化 diff

> `aapt dump xmltree` 对原/新 AXML 各 dump 一次，只把 `(line=N)` 归一化（行号必然变），其余逐字比对。aapt 能 rc=0 解析新文件本身也说明它的 chunk 结构是合法的。

```diff
--- "/mnt/c/Users/su/Desktop/\345\244\247\350\202\245\351\261\274\351\241\271\347\233\256/BAServer/work/ba/apk_patch/v2v3/aapt_dump_orig_norm.txt"	2026-11-18 19:43:41.420410700 +0800
+++ "/mnt/c/Users/su/Desktop/\345\244\247\350\202\245\351\261\274\351\241\271\347\233\256/BAServer/work/ba/apk_patch/v2v3/aapt_dump_new_norm.txt"	2026-11-18 19:43:41.427916500 +0800
@@ -54,26 +54,64 @@
         A: android:layout_marginLeft(0x010100f7)=@0x7f060133
         A: android:layout_marginRight(0x010100f9)=@0x7f060133
         A: android:text(0x0101014f)=@0x7f0f0038
+      E: RadioGroup (line=?)
+        A: android:gravity(0x010100af)=(type 0x11)0x10
+        A: android:orientation(0x010100c4)=(type 0x10)0x0
+        A: android:background(0x010100d4)=(type 0x1c)0xfff5f6f8
+        A: android:paddingLeft(0x010100d6)=(type 0x5)0x601
+        A: android:paddingTop(0x010100d7)=(type 0x5)0x201
+        A: android:paddingRight(0x010100d8)=(type 0x5)0x601
+        A: android:paddingBottom(0x010100d9)=(type 0x5)0x201
+        A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
+        A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
+        A: android:layout_marginLeft(0x010100f7)=@0x7f060103
+        A: android:layout_marginTop(0x010100f8)=(type 0x5)0xa01
+        A: android:layout_marginRight(0x010100f9)=@0x7f060103
+        E: RadioButton (line=?)
+          A: android:textSize(0x01010095)=(type 0x5)0xe02
+          A: android:textColor(0x01010098)=(type 0x1c)0xff2b3445
+          A: android:gravity(0x010100af)=(type 0x11)0x11
+          A: android:id(0x010100d0)=@0x01020014
+          A: android:paddingTop(0x010100d7)=(type 0x5)0x801
+          A: android:paddingBottom(0x010100d9)=(type 0x5)0x801
+          A: android:layout_width(0x010100f4)=(type 0x5)0x1
+          A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
+          A: android:checked(0x01010106)=(type 0x12)0xffffffff
+          A: android:text(0x0101014f)="游客登录" (Raw: "游客登录")
+          A: android:layout_weight(0x01010181)=(type 0x4)0x3f800000
+          A: android:buttonTint(0x0101046f)=(type 0x1c)0xff2f6fed
+        E: RadioButton (line=?)
+          A: android:textSize(0x01010095)=(type 0x5)0xe02
+          A: android:textColor(0x01010098)=(type 0x1c)0xff2b3445
+          A: android:gravity(0x010100af)=(type 0x11)0x11
+          A: android:id(0x010100d0)=@0x01020015
+          A: android:paddingTop(0x010100d7)=(type 0x5)0x801
+          A: android:paddingBottom(0x010100d9)=(type 0x5)0x801
+          A: android:layout_width(0x010100f4)=(type 0x5)0x1
+          A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
+          A: android:text(0x0101014f)="卡密登录" (Raw: "卡密登录")
+          A: android:layout_weight(0x01010181)=(type 0x4)0x3f800000
+          A: android:buttonTint(0x0101046f)=(type 0x1c)0xff2f6fed
       E: androidx.constraintlayout.widget.ConstraintLayout (line=?)
         A: android:paddingLeft(0x010100d6)=@0x7f060103
         A: android:paddingRight(0x010100d8)=@0x7f060103
         A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
         A: android:layout_height(0x010100f5)=(type 0x10)0xfffffffe
-        A: android:layout_marginTop(0x010100f8)=@0x7f06016c
+        A: android:layout_marginTop(0x010100f8)=(type 0x5)0xa01
         E: com.airi.official.core.widget.ExtendEditText (line=?)
-          A: android:textSize(0x01010095)=@0x7f06029e
+          A: android:textSize(0x01010095)=(type 0x5)0xf02
           A: android:textColor(0x01010098)=@0x7f05002d
-          A: android:textColorHint(0x0101009a)=@0x7f050091
+          A: android:textColorHint(0x0101009a)=(type 0x1c)0xff9aa3b2
           A: android:id(0x010100d0)=@0x7f080108
           A: android:background(0x010100d4)=@0x7f0700b7
           A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
-          A: android:layout_height(0x010100f5)=@0x7f060145
+          A: android:layout_height(0x010100f5)=(type 0x5)0x2c01
           A: android:hint(0x01010150)=@0x7f0f0074
           A: android:singleLine(0x0101015d)=(type 0x12)0xffffffff
-          A: android:maxLength(0x01010160)=(type 0x10)0xb
-          A: android:inputType(0x01010220)=(type 0x11)0x3
+          A: android:maxLength(0x01010160)=(type 0x10)0x40
+          A: android:inputType(0x01010220)=(type 0x11)0x1
           A: android:imeOptions(0x01010264)=(type 0x11)0x10000006
-          A: android:paddingStart(0x010103b3)=@0x7f0600a9
+          A: android:paddingStart(0x010103b3)=(type 0x5)0xe01
           A: android:paddingEnd(0x010103b4)=@0x7f060090
           A: app:clearButtonMode(0x7f0300be)=(type 0x10)0x2
           A: app:layout_constraintLeft_toLeftOf(0x7f03021a)=(type 0x10)0x0
@@ -83,7 +121,7 @@
           A: android:id(0x010100d0)=@0x7f08016f
           A: android:background(0x010100d4)=@0x7f0700b7
           A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
-          A: android:layout_height(0x010100f5)=@0x7f060145
+          A: android:layout_height(0x010100f5)=(type 0x5)0x2c01
           A: android:layout_marginTop(0x010100f8)=@0x7f0600a9
           A: app:layout_constraintLeft_toLeftOf(0x7f03021a)=(type 0x10)0x0
           A: app:layout_constraintRight_toRightOf(0x7f03021e)=(type 0x10)0x0
@@ -145,8 +183,8 @@
             A: android:id(0x010100d0)=@0x7f080182
             A: android:background(0x010100d4)=@0x7f0700b6
             A: android:layout_width(0x010100f4)=(type 0x10)0xffffffff
-            A: android:layout_height(0x010100f5)=@0x7f060145
-            A: android:layout_marginTop(0x010100f8)=@0x7f0600a9
+            A: android:layout_height(0x010100f5)=(type 0x5)0x2e01
+            A: android:layout_marginTop(0x010100f8)=(type 0x5)0x1001
             A: android:text(0x0101014f)=@0x7f0f009f
           E: View (line=?)
             A: android:id(0x010100d0)=@0x7f080183
```

---

## 4. 包 2：dex 字节补丁的证据

### 4.1 补丁本身 + 字节级 diff 证明

```
=== input classes.dex ===
  size          = 9327708
  sha256        = 56b3a73b3039db99ade67faf42e471c8de4dcd7127ce9bef49d9f4d473c27651
  string_ids[32792] data_off = 0x70eb59  uleb128 len = 9  payload = b'^1\\d{10}$'

=== after patch ===
  string_ids[32792] payload = b'^.{1,64}$'
  +0x08 checksum  0x60c569a0 -> 0x479c6610
  +0x0c signature f48639cbd34bb2df88e230de3fb9a2b664d3a945 -> 8103933ca17aa30c56f52ce847ba0777854960be
  adler32(bytes[12:])  = 0x479c6610 (matches header)
  sha1(bytes[32:])     = 8103933ca17aa30c56f52ce847ba0777854960be (matches header)
  size unchanged       = True (9327708)
  sha256(new)      = 0ed8bbf878170c02d8d34dd9e974108b6268287b6d0dc897a8246a2634f141e2

=== byte diff vs original ===
  total bytes        = 9327708
  differing bytes    = 30
  identical bytes    = 9327678
  differing offsets  = 0x8 0x9 0xa 0xb 0xc 0xd 0xe 0xf 0x10 0x11 0x12 0x13 0x14 0x15 0x16 0x17 0x18 0x19 0x1a 0x1b 0x1c 0x1d 0x1e 0x1f 0x70eb5b 0x70eb5c 0x70eb5d 0x70eb5e 0x70eb5f 0x70eb60
  contiguous ranges  = 0x8..0x1f(24), 0x70eb5b..0x70eb60(6)
  payload window 0x70eb5a..0x70eb62  old 5e 31 5c 64 7b 31 30 7d 24
                             new 5e 2e 7b 31 2c 36 34 7d 24
  bytes inside the payload window that changed value: 6/9  (offsets 0x70eb5b 0x70eb5c 0x70eb5d 0x70eb5e 0x70eb5f 0x70eb60)
  bytes outside payload window in 0x70eb5a..0x70eb62: 3
  header region 0x08..0x1f differs in 24/24 bytes
  bytes outside those two regions untouched: 9327678

  wrote /mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/v2v3/classes_patched.dex (9327708 B)
```

要点：

- 替换窗口：`classes.dex` 文件偏移 **`0x70eb5a..0x70eb62`**（9 字节），取自 `string_ids[32792]` 的 MUTF-8 payload。
  - 旧 `5e 31 5c 64 7b 31 30 7d 24` = `^1\d{10}$`
  - 新 `5e 2e 7b 31 2c 36 34 7d 24` = `^.{1,64}$`（**等长 9 字节**，uleb128 长度前缀 `09` 不变，后续数据不挪位）
- 头两个字段：
  - `file+0x08` adler32：`0x60c569a0` → **`0x479c6610`**
  - `file+0x0c` SHA-1：`f48639cbd34bb2df88e230de3fb9a2b664d3a945` → **`8103933ca17aa30c56f52ce847ba0777854960be`**
- 差异统计：**30 B 不同 / 9,327,678 B 相同**，全部落在两个允许区间内，无第三处差异：
  - `0x08..0x1f` 共 24 B（adler32 4 + SHA-1 20，全变）
  - `0x70eb5a..0x70eb62` 窗口内 6 B 变值（`^`、`}`、`$` 三个字节新旧相同，所以不是 9）
- 文件大小、`file_size(0x20)`、`header_size`、`endian_tag`、`string_ids_off/type_ids_off` 等全部不变。

### 4.2 结构有效性：用 apktool(dexlib2) 反汇编两份 dex 再 diff

> dexlib2 载入损坏 dex 会直接报错；两份都 `I: Baksmaling classes.dex...` 成功、各产出 8,313 个文件，整棵树 diff 只有 **1 行 smali** 不同（另 2 行是 apktool.yml 里记录的输入文件名）。

```
[apktool d orig] rc=0  files=8313
    I: Using Apktool 2.11.1 on mini_orig.apk with 8 threads | I: Loading resource table... | I: Baksmaling classes.dex... | I: Decoding file-resources... | I: Decoding values */* XMLs... | I: Loading resource table from file: /root/.local/share/apktool/framework/1.apk | I: Decoding AndroidManifest.xml with resources... | I: Regular manifest package... | I: Copying original files... | I: Copying unknow
[apktool d new] rc=0  files=8313
    I: Using Apktool 2.11.1 on mini_new.apk with 8 threads | I: Loading resource table... | I: Baksmaling classes.dex... | I: Decoding file-resources... | I: Decoding values */* XMLs... | I: Loading resource table from file: /root/.local/share/apktool/framework/1.apk | I: Decoding AndroidManifest.xml with resources... | I: Regular manifest package... | I: Copying original files... | I: Copying unknown

=== smali tree diff (orig dex vs patched dex) ===
diff -r /root/ba_work/mini/dec_orig/apktool.yml /root/ba_work/mini/dec_new/apktool.yml
2c2
< apkFileName: mini_orig.apk
---
> apkFileName: mini_new.apk
diff -r /root/ba_work/mini/dec_orig/smali/com/airi/common/utils/CommonUtil.smali /root/ba_work/mini/dec_new/smali/com/airi/common/utils/CommonUtil.smali
745c745
<     const-string v0, "^1\\d{10}$"
---
>     const-string v0, "^.{1,64}$"

changed smali lines: 4

=== patched CommonUtil.smali :: isChinaPhoneLegal ===
.method public static isChinaPhoneLegal(Ljava/lang/String;)Z
    .locals 1
    .annotation system Ldalvik/annotation/Throws;
        value = {
            Ljava/util/regex/PatternSyntaxException;
        }
    .end annotation

    const-string v0, "^.{1,64}$"

    .line 139
    invoke-static {v0}, Ljava/util/regex/Pattern;->compile(Ljava/lang/String;)Ljava/util/regex/Pattern;

    move-result-object v0

    invoke-virtual {v0, p0}, Ljava/util/regex/Pattern;->matcher(Ljava/lang/CharSequence;)Ljava/util/regex/Matcher;

    move-result-object p0

    invoke-virtual {p0}, Ljava/util/regex/Matcher;->matches()Z

    move-result p0

    re
```

### 4.3 交付物回读终检（不是读本地中间文件，而是从两个 .apk 里读回来）

```
=== delivered package acceptance (values read back from the .apk) ===

--- v2_layoutonly = v2_layoutonly.apk
    bytes  = 2127972169
    sha256 = 562d528a951eaeb15ae3165ece4a7ceb91849bb21ef54c895c6f217f9a676d64
    entries = 41307
    resources.arsc sha256 = cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86 -> OK == baseline
    res/Q9.xml  8284 B sha256=8907d9b258c918c057046ff267d86f1128a13153ece8e32bcfec9ec70a67559c
    res/Q9.xml  elements = 31, RadioGroup=1 RadioButton=2
    literal text "游客登录" = True, "卡密登录" = True
    maxLength attrs: A: http://schemas.android.com/apk/res/android:maxLength(0x01010160) 64 [INT_DEC]; A: http://schemas.android.com/apk/res/android:maxLength(0x01010160) 6 [INT_DEC]
    inputType attrs: A: http://schemas.android.com/apk/res/android:inputType(0x01010220) 0x00000001 [INT_HEX]; A: http://schemas.android.com/apk/res/android:inputType(0x01010220) 0x00000002 [INT_HEX]
    checked attrs  : A: http://schemas.android.com/apk/res/android:checked(0x01010106) true [INT_BOOLEAN]
    classes.dex 9327708 B sha256=56b3a73b3039db99ade67faf42e471c8de4dcd7127ce9bef49d9f4d473c27651
      file_size(0x20)==len : True
      adler32(0x08)       : True (0x60c569a0)
      sha1(0x0c)          : True (f48639cbd34bb2df88e230de3fb9a2b664d3a945)
      string_ids[32792]   : b'^1\\d{10}$'   (data_off 0x70eb59, uleb128 9)
      string count        : 71655

--- v3_dexpatch = v3_dexpatch.apk
    bytes  = 2133473392
    sha256 = 6e5dcfb0317db175cec1be0719fad8271f6cae9abb5f3da84b571a36f6d2de25
    entries = 41307
    resources.arsc sha256 = cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86 -> OK == baseline
    res/Q9.xml  8284 B sha256=8907d9b258c918c057046ff267d86f1128a13153ece8e32bcfec9ec70a67559c
    res/Q9.xml  elements = 31, RadioGroup=1 RadioButton=2
    literal text "游客登录" = True, "卡密登录" = True
    maxLength attrs: A: http://schemas.android.com/apk/res/android:maxLength(0x01010160) 64 [INT_DEC]; A: http://schemas.android.com/apk/res/android:maxLength(0x01010160) 6 [INT_DEC]
    inputType attrs: A: http://schemas.android.com/apk/res/android:inputType(0x01010220) 0x00000001 [INT_HEX]; A: http://schemas.android.com/apk/res/android:inputType(0x01010220) 0x00000002 [INT_HEX]
    checked attrs  : A: http://schemas.android.com/apk/res/android:checked(0x01010106) true [INT_BOOLEAN]
    classes.dex 9327708 B sha256=0ed8bbf878170c02d8d34dd9e974108b6268287b6d0dc897a8246a2634f141e2
      file_size(0x20)==len : True
      adler32(0x08)       : True (0x479c6610)
      sha1(0x0c)          : True (8103933ca17aa30c56f52ce847ba0777854960be)
      string_ids[32792]   : b'^.{1,64}$'   (data_off 0x70eb59, uleb128 9)
      string count        : 71655
```

---

## 5. 包 1 改了什么 / 砍了什么

### 5.1 做进去的（全部字面量，无新资源条目）

| # | 位置 | 改动 | 手法 |
|---|---|---|---|
| 1 | 根 LinearLayout 的 **index 2** | 新增 `RadioGroup`（水平、浅灰底 `#FFF5F6F8`、左右 `@dimen/dp24`、上下 `10dip`、左右内边距 `6dip`） | 新节点 |
| 2 | RadioGroup 内 | 两个 `RadioButton`：`android:text="游客登录"` / `"卡密登录"`（**字面量**）、14sp、`#FF2B3445`、居中、`buttonTint #FF2F6FED`、上下 8dip 点击区、`layout_weight=1` 各占一半 | 新节点 |
| 3 | 第一个 RadioButton | `android:checked="true"`（默认勾选"游客登录"） | 新属性 |
| 4 | `et_phone` | `maxLength 11 → 64` | 值替换 |
| 5 | `et_phone` | `inputType phone → text`（0x3 → 0x1） | 值替换 |
| 6 | `et_phone` | 字号 `@dimen/sp14 → 15.0sp`、高度 `@dimen/dp40 → 44.0dip`、左内边距 `dp12 → 14.0dip` | 值替换 |
| 7 | `et_phone` | hint 颜色 `@color/disable_text → #FF9AA3B2` | 值替换 |
| 8 | `layout_phone_code`（验证码框**容器**） | 高度 `dp40 → 44.0dip`，与手机号框等高 | 值替换（`et_phone_code` 自身属性一个没动） |
| 9 | 登录按钮 `@id/login` | 高度 `dp40 → 46.0dip`、上间距 `dp12 → 16.0dip` | 值替换 |
| 10 | 输入区容器 ConstraintLayout | `layout_marginTop dp7 → 10.0dip`（和"分段选择条"之间留白） | 值替换 |

### 5.2 砍掉的，以及为什么

| 砍掉的 | 原因 |
|---|---|
| **新面板的圆角** | 圆角只能靠 shape/selector drawable（=新增/修改 res 条目 → 破坏"arsc 一字节不变 + 只改 Q9.xml"）或代码 `ViewOutlineProvider`（=动 dex）。所以新面板用的是**直角色块** `#FFF5F6F8`。**已有输入框/按钮的圆角仍然保留**——它们本来就用 `@drawable/login_edit_bg_fragment`，我们没碰它的 background。 |
| 给新控件分配 `@+id/…` | 会在资源表里引入新 id；即使 aapt2 现场给了号，进了基线包也是**悬空 id**（基线 arsc 里没有）。改用 framework 的 `@android:id/text1` / `@android:id/text2`（`0x01020014/15`，framework 包自带，不算本项目资源）。 |
| 用 `@color/*` 取现成颜色 | 为了守住"全部字面量、零新条目"，颜色一律写死 ARGB 字面量。 |
| 底部第三方登录区重排 / 分割线 / 阴影(elevation) | 重排要改原有节点的 layout_* 属性；分割线要新 drawable；elevation 需要 outline+背景。风险 vs 收益不划算，砍。 |
| 换字体 / 渐变 / 自定义 shape | 都需要新资源。 |
| 给 `et_phone` 换新的圆角描边背景 | 同上（新 drawable）。 |

### 5.3 刻意没动的

- `et_phone_code` 的**每一个**属性（`maxLength=6`、`inputType=number`、`textColorHint=@color/disable_text`、`layout_height=@dimen/dp40` …）——二进制层可见它逐条未变。
- 所有既有 `android:id`（`iv_back`/`iv_logo`/`iv_close`/`tv_bind_phone_desc`/`et_phone`/`layout_phone_code`/`et_phone_code`/`divide`/`get_phone_code`/`ll_container_login`/`login`/`login_helper`/`agreement_layout`/…）：`own_diff.txt` 里没有任何 `android:id` 行变化。
- 根 LinearLayout 的既有子节点顺序：`LinearLayout, TextView, [新 RadioGroup,] ConstraintLayout`。

### 5.4 为什么说包 1 是"低风险面"（项目自己的历史证据）

`work/ba/noroot/_dd4-integrity.md` 的 Q4 失败面表里，`res/*` + `resources.arsc` 那一行是 **✅ 均能启动（E32/E34/E42，"安全改动面"）**；而失败的三条全是 `libunity.so`、新增 `.so`、新增/重编 `.dex`。
所以"换布局"是项目里**唯一被反复观测过、且都活着**的改动面；包 1 正好压在这个面上（而且比 E32/E34/E42 更保守：连 arsc 都不动）。

反过来注意：`_dd4-integrity.md:105` 有一句 **推断**（不是观测）——"ACE 禁止加载布局变化"。如果那句成立，包 1 就该挂；但 E32/E34/E42 三次都跑起来了，所以更可能它不成立。**包 1 顺带也就是对这个推断的一次干净反证实验。**

---

## 6. 安装顺序与回滚

两个包 `versionCode` 都是 73，包名都是 `com.RoamingStar.BlueArchive`，签名证书与基线同一张 (`94fa997b…`)，所以 **基线 ↔ v2 ↔ v3 三者可以互相 `-r` 覆盖安装**，不需要卸载。

> ⚠️ 两个前提（来自 `work/ba/noroot/_dd4-integrity.md`）：
> - **R7**「实验前先复位 ACE 记账，否则任何失败都可能是上次的连坐」⇒ 每个实验包之前先 `pm clear` 或彻底重装一次，保证两个包面对的是同一个初始态，否则 v2 失败会把脏状态带进 v3，二分就白做了。
> - **R8**「签名变了必须 uninstall + install」⇒ 如果手机里现在是**官方原厂包**（不是我们这个基线包），装 v2/v3 前必须先卸载（UID 变 ⇒ `/data/data` 全丢，卡密登录态在里面）。若手机里已经是基线包，则直接 `-r`。

```bat
:: 0) 先确认设备
adb devices
adb shell getprop ro.build.version.release
adb logcat -c
::   R7：每次实验前把 ACE 记账复位，避免"上一次的连坐"污染本次结论
adb shell pm clear com.RoamingStar.BlueArchive

:: 1) 装包 1（只换布局）—— 这一步专门用来二分定位
adb install -r "work\ba\apk_patch\out\v2_layoutonly.apk"
::   ✔ 能起来 + 登录页出现"游客登录/卡密登录"分段条  ->  布局层安全，进第 2 步
::   [X] 卡启动界面 / 登录页崩 -> 抓日志后回滚（见下），并且说明"连纯布局替换都不行"
adb logcat -b crash -d > log_crash_v2.txt
adb logcat -d | findstr /i "AndroidRuntime InflateException Resources$NotFoundException" > log_v2.txt

:: 2) 装包 2（在包 1 基础上 + 9 字节 dex 补丁）
adb install -r "work\ba\apk_patch\out\v3_dexpatch.apk"
::   ✔ 能起来 -> 启动链接受"结构不变的内容修改"，卡密登录可输入 1~64 字符
::   ✗ 卡启动界面 -> 说明是 dex 内容哈希/完整性校验，不是结构问题，立刻回滚
adb logcat -b crash -d > log_crash_v3.txt

:: 3) 回滚（任意时刻）
adb install -r "work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk"
:: 版本号相同，-r 即可覆盖；不需要 -d。卸载会丢本地数据，非必要不要用。
:: 万不得已： adb uninstall com.RoamingStar.BlueArchive
```

- 建议顺序：**先 v2，再 v3**。理由：v2 只动布局，v3 再叠 dex；一旦出问题能立刻判断是新引入的那层。
- 回滚目标就是**基线备份包本身**（同一张证书、同 versionCode，覆盖安装即可，无损）。
- 想两个包并存对比的话：先用 `build_noroot_apk.py --rename-package` 出不同包名的 v2（本次没做）。

---

## 7. 复现命令

```bash
# 1) 布局：改解码 XML -> apktool b -s（不汇编 smali，产物里没有 dex）-> 只取那一份 AXML
python3 work/ba/apk_patch/v2v3/make_layout.py  work/ba/apk_patch/v2v3/res_Q9_new.axml
# 2) dex：9 字节窗口覆盖 + 重算 adler32/SHA-1 + 字节级 diff 断言
python3 work/ba/apk_patch/v2v3/patch_dex.py
# 3) 组包（基线 + 替换条目，重签 v1/v2/v3）
python work\ba\noroot\build_noroot_apk.py --src work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk \
  --out work\ba\apk_patch\out\v2_layoutonly.apk --keystore work\ba\noroot\ba_private.keystore \
  --storepass baserver --alias ba --asset-replace res/Q9.xml=work\ba\apk_patch\v2v3\res_Q9_new.axml
python work\ba\noroot\build_noroot_apk.py --src work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk \
  --out work\ba\apk_patch\out\v3_dexpatch.apk --keystore work\ba\noroot\ba_private.keystore \
  --storepass baserver --alias ba \
  --asset-replace res/Q9.xml=work\ba\apk_patch\v2v3\res_Q9_new.axml \
  --asset-replace classes.dex=work\ba\apk_patch\v2v3\classes_patched.dex
# 4) 自检 + 证据
python3 work/ba/apk_patch/v2v3/selftest.py
python3 work/ba/apk_patch/v2v3/cmp_axml.py      # 自研解析器 + aapt 双读
python3 work/ba/apk_patch/v2v3/root_order.py    # 根节点子序 + 解码 XML diff
python3 work/ba/apk_patch/v2v3/smali_proof.py   # dexlib2 反汇编对照
python3 work/ba/apk_patch/v2v3/make_report.py   # 生成本文件
```

---

## 8. 没把握的地方（照实说）

1. **两包都没上真机**：本机 `adb devices` 是空列表。所有"通过"都是静态可验证项（字节/结构/签名/条目），不等于真机一定起得来。
2. **"游客登录/卡密登录"只是视觉分段条**：没有接任何代码（任务要求不写代码）。点它会切换选中态，但**不会改变登录逻辑**；真正放开卡密登录靠的是 v3 里 `isChinaPhoneLegal` 的正则放宽。如果还要在 Java 层区分两种模式，得另开工单（必然要动 dex）。
3. **新控件用的 framework id**（`@android:id/text1` / `text2`）：这样不新增资源条目，`RadioGroup` 的互斥切换也正常；但个别 ROM 若对这些 id 有特殊处理（几乎不会），最坏是"选中态不互斥"，不会崩。
4. **`buttonTint` 是 API 21+ 属性**，minSdk=24，安全。
5. **v3 把 classes.dex 从 DEFLATE 改成了 STORED**（`--asset-replace` 的统一行为，v1 也是这么打的）。这属于打包层变化而非 dex 变化，正常不影响运行，但严格说它是 v3 与基线在 zip 层的第 2 处差异。
6. **v3 是否真的能被启动链接受，无法从静态层面回答**。我能证明的是：dex 结构与基线逐字节同构（只 6 B 载荷 + 24 B 头不同）、dexlib2 能完整反汇编、以及"E43 的结构变化归因"在这个包里不成立。如果真机仍卡启动界面，下一步应查 `_dd4-integrity.md` 里的内容完整性/哈希校验线索，而不是再折腾 dex 结构。
   - 顺带提醒一条**冲突记载**：`_dd4-integrity.md` 里 E44（重编 `classes2.dex` 只改一个 `const-string`）有**两处互相矛盾的记录**——一处"首次成功、之后同批全卡"，另一处"正常启动、SDK 登录成功"。也就是说"改 dex 里的一个字符串"这件事本身在历史上就是**未定论**的；v3 把变量进一步压到"不重编、不挪位、只改 6 个字节值"，是这条线上能做出的最干净的一次实验。
7. **`isChinaPhoneLegal` 放宽到 `^.{1,64}$`** 会同时放行空字符串以外的任意 1~64 字符（含空格、表情、纯符号）。这是按任务给定的正则照做的；如果后端对"手机号"字段另有格式要求，登录仍可能被服务端拒。
8. **布局美化里的"间距/高度"是经验值**（44dip/46dip/15sp/16dip 等），没在真机上目视校对过；数字都写在 `make_layout.py` 的 `RADIO_BLOCK` 和 `edit()` 里，要微调改这几行即可重出包。
9. `res/Q9.xml` 从 7,292 B 长到 8,284 B（+992 B），因为多了 6 个 chunk 节点 + 6 条字符串。包 1 相对基线的字节差（+992 B）几乎全是这一项；包 2 的 +5,502,215 B 主要是 classes.dex 由 DEFLATE 改 STORED（9,327,708 − 3,826,491 = 5,501,217 B），不是布局膨胀。
