# 签名器「双向验证」记录（Lead 实测）

写于 2026-11-17 01:15。执行人：Lead（验证类工作，非修改）。

## 为什么要做这一轮

`8ca0aaa1` 的结论是「签名层已完整可验证，唯一硬缺口是没在真 `apksigner` 下独立验过（本机无 JVM）」。

本机实测确认：**整机无任何 JVM** —— `java` / `javaw` / `keytool` / `apksigner` / `gradle` 全部不存在，`JAVA_HOME` / `ANDROID_HOME` / `ANDROID_SDK_ROOT` 全空，`C:\Program Files\Java`、`Eclipse Adoptium`、`Android\Sdk` 均无，gradle 缓存里只有 `apksig-8.6.1.jar`（506,969 B）没处跑，`androguard` 未安装。

**但这个缺口可以用另一种办法补掉，而且比装 JVM 更有说服力：** 拿一个**真 `apksigner` 签出来的 APK** 当靶子，用**我们的校验器**去验；再把它篡改两份，验证必须被拒。

理由：单方向「能判 OK」不够 —— 旧产物 `BA_noroot_v1.apk` 的 v2/v3 也被判 OK。"能判 FAIL" 没被证明过，那校验器就有可能是老好人。

## 靶子

| 文件 | 大小 | sha256 |
|---|---|---|
| `work\ba\bapatch\lsp\build13\Probe13.apk`（**真 apksigner 产物**） | 21,078 B | `313135869049aa00127002a2a7a635b2d436574319cdc36d4e8115fc2ae000d6` |
| `work\ba\noroot\build_noroot_apk.py`（被测校验器） | 109,025 B | `24cb37705de6d6860f1f7925f3379196d9469c942cd323aeb44b0b92e3da8cfd` |
| 夹具生成器 `work\ba\noroot\_lead_negtest.py` | 4,559 B | `65c9c6bbcd585374fa4bf35b6fe1f8eaadda18e0f0c1599d0adbfc3a6934e259` |

## 结果一：接受真 apksigner 产物（exit 0）

```
python build_noroot_apk.py --verify-only <Probe13.apk>
```
```
APK Signing Block: OK @16384 (4088 B)
content digest = 112ec0a06acc43663f0446ed4a3909e3740c68e87309724424378ee689211a13
v2: OK
v3: OK
zip 完整性: OK
v2/v3 签名者证书 SHA-256 = ABD1FA978928F8BF9B665023B6AB19E27F62C957CC7C959111D646D2ED0E8701
v1: MANIFEST.MF 472 B, 5 个 Name 段
v1: 最长行 60 B, 超 72 B 的行 0 个（OK）
v1: 逐条摘要 5 条, 不符 0, 条目缺失 0 OK
v1: META-INF 签名文件 3 个 [BA.SF, BA.RSA, MANIFEST.MF]
v1: META-INF/BA.SF SHA-256-Digest-Manifest OK（5 个逐条段）
v1: X-Android-APK-Signed = '2, 3'（声明 [2, 3]，APK 实有 [2, 3]）
v1: META-INF/BA.RSA 对 .SF 的 PKCS#7 验签 OK
v1 与 v2/v3 证书一致: OK
v1 结论: OK
STORED 4 字节对齐: OK
resources.arsc: 第 2 条, STORED=True, 4 字节对齐=True
  [!] resources.arsc 不是第 1 条（非平台硬要求，但违背本工具约定）
__tpinfo 残留: 无（OK）
```
**exit = 0** ⇒ 我们的 PKCS#7 / v2 / v3 / 摘要实现与 Google 的 apksigner 在真实产物上一致。

## 结果二：篡改内容必须被拒（exit 1）

夹具：`_neg_content.apk` 21,078 B / `c722ab1837f1d110df677b50e4f229e74588de7b54b9ec77b4f8fc79b14537fc`
篡改点：`resources.arsc` 数据区偏移 **909**，`0x00 → 0xFF`（这是 Probe13 里唯一的 STORED 条目）

```
content digest = f5a32f9cc3642a7261c735a46cf94c87eadf5595d5d7db0f1ce936d8fb2c17cb   ← 已变
v2: FAIL 内容摘要不匹配
v3: FAIL 内容摘要不匹配
zip 完整性: 坏条目 resources.arsc
v1 结论: FAIL        （BadZipFile: Bad CRC-32 for file 'resources.arsc'）
```
**exit = 1**

## 结果三：只改签名块也必须被拒（exit 1）

夹具：`_neg_sigblock.apk` 21,078 B / `5a5dc6e90483c28f20573ccebf8f87b1c722716349906b24c6e2fb65d7b34ea0`
篡改点：APK Signing Block（start=16384, size_total=4096）内偏移 **18424**，`0x86 → 0x79`。**zip 结构与所有条目内容完全没动。**

```
content digest = 112ec0a0…   ← 不变（正确，内容真没变）
v2: OK
v3: FAIL
zip 完整性: OK
```
**exit = 1**

> `v2: OK / v3: FAIL` 是**正确**行为，不是漏判：翻的字节落在 v3 的 id-value pair 里，v3 的签名覆盖它而 v2 不覆盖。两套签名的覆盖范围本来就不同。

## 结论

校验器在**两个方向**都被证明有效：

| 方向 | 判据 |
|---|---|
| 接受真 apksigner 产物 | Probe13.apk → exit 0，全绿 |
| 拒绝内容篡改 | 改 arsc 1 字节 → v2/v3 双 FAIL，exit 1 |
| 拒绝签名篡改 | 改签名块 1 字节（内容不动）→ v3 FAIL，exit 1 |

因此「本机无 JVM」**不再是一个未验证的缺口** —— 靶子本身就是 apksigner 出的。装 JVM 再跑一遍 `apksigner verify -v --print-certs` 属于锦上添花，不是必要条件。

## 仍然唯一的真缺口

**没有真机装过。** 这是签名层之外的事（安装策略、`minSdk`、系统版本、厂商限制），只能上机验。分发前最低限度要做一次 `adb install`。

## 复现命令

```
cd work\noroot
<py> build_noroot_apk.py --verify-only ..\bapatch\lsp\build13\Probe13.apk                             # 期望 exit 0
<py> _lead_negtest.py ..\bapatch\lsp\build13\Probe13.apk                                              # 生成两份夹具
<py> build_noroot_apk.py --verify-only _neg_content.apk                                               # 期望 exit 1
<py> build_noroot_apk.py --verify-only _neg_sigblock.apk                                              # 期望 exit 1
```
`<py>` = `C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`
