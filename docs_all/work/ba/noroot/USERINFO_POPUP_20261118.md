# 「玩家信息」弹窗：进入时在等什么（静态分析）

> 只读。未改 APK、未碰服务器。
> 证据：il2cpp `md_deob.bin` 类型/方法表 + `libil2cpp.so` 反汇编（capstone）。
> 日期：2026-11-18

## 一句话

**「玩家信息」= `UIPopup_UserInfo`。它的入口链（`SetValues` / `SetData` / `SetMyData`）全部是同步方法，
没有任何协程 / await / Addressables 加载 / 网络等待 —— 所以它不是在"等"什么，而是在"做"什么的过程中失败了。
失败点在两个 Tab 里，而那两个类的方法全部在 ACE 密文区，静态看不到。**

---

## ① 界面类（实测，类型表）

```
UIPopup_UserInfo        type[6070]  2 字段: tabController, tabs
  ├ UIUserInfoTab            type[6071]  枚举: Profile / Record / Support
  ├ UIUserInfoTab_Base       type[6076]  0 字段  (SetData / SetMyData 为普通方法，非协程)
  ├ UIUserInfoTab_Profile    type[6077]  12 字段
  ├ UIUserInfoTab_Record     type[6080]  10 字段
  └ UIUserInfoTab_Assist     type[6075]  2 字段: scrollView, assistCharactersList
```

`UIUserInfoTab_Profile` 的 12 个字段（这是"玩家信息"主页签的全部渲染目标）：
```
representativeThumbnail  userName  friendCode  levelExp  maxLevel
clanName  friendCount  comment  emblemParcel  blockButton  accountId  location
```
`UIUserInfoTab_Record` 的方法里有一个 `SetMultiFloorRaidDifficulty` —— **多楼层攻坚（MultiFloorRaid）数据是该页签的强依赖**。

## ② 入口调用链（实测反汇编，全部 PLAIN）

```
UIAccountInfo.OnClickUserInfo   @0x0CCF2B94  (UIAccountInfo 第 31 字段 userInfoButton 的回调)
    → 打开 UIPopup_UserInfo
UIPopup_UserInfo.SetValues      @0x0A0321D0  ★ 同步
UIPopup_UserInfo.SetData        @0x0A032348  ★ 同步
UIPopup_UserInfo.SetMyData      @0x0A032460  ★ 同步
```

`SetValues`（`0x0A032268` 起）：
```asm
0x0A03226C  ldr  x8, [x20, #0xB0]!     ; this.tabController（懒创建）
0x0A032270  cbnz x8, #0xA0322D0        ; 已有 → 跳过
0x0A032290  bl   #0x66F36C4            ; ★ GetComponent/AddComponent 型（按类型取组件）
0x0A0322BC  bl   #0x9E60AD8            ; 初始化
```

`SetMyData`（`0x0A0324D8` 起）：
```asm
0x0A0324DC  bl   SetValues
0x0A0324E0  ldr  x0, [x19, #0xA8]      ; 子对象
0x0A0324E4  cbz  x0, #0xA032544        ; ★ null → 直接 return
0x0A0324F8  bl   #0xE979C50            ; SetActive 型
0x0A0324FC  ldr  x0, [x19, #0xB0]
0x0A032500  cbz  x0, #0xA032544        ; ★ null → 直接 return
```

## ③ 回答你的三问

### ① 它进入时加载/等待什么？—— **什么都不等**

| 候选项 | 判定 | 依据 |
|---|---|---|
| Addressables 场景/bundle | **否** | 三个入口方法里没有任何 `Addressables` / `LoadAssetAsync` / `InstantiateAsync` 调用；`SetValues` 只用 `GetComponent/AddComponent` 取**已在 prefab 里**的组件 |
| 一个 API 响应（协议） | **否** | 方法签名是 `void`，**没有回调参数**，没有发起请求的痕迹；且实测零请求 —— 与"同步路径"完全自洽 |
| 纯本地数据（AccountInfo / Excel） | **是** | `UIUserInfoTab_Profile` 的字段全是从 `MXAccount.AccountInfo` 与 Excel 直接取的值 |

**⇒ 关键推论：既然零请求 + 同步路径，那么"界面不出现"就不是"等不到数据"，而是"执行到一半就中断了"。**

### ② 有没有 await / 协程？—— **弹窗层完全没有**

* `UIPopup_UserInfo` 只有 6 个方法：`Awake` / `SetValues` / `SetData` / `SetMyData` / `.ctor` / `<>iFixBaseProxy_Awake`。
  **没有 `MoveNext`、没有 `d__NN` 迭代器类、没有 `AsyncTask`**。
* `UIUserInfoTab_Base.SetData`(mdef 39155) / `SetMyData`(39156) 都是 `void` 普通方法（PLAIN）。
* `UIUserInfoTab_Assist` 的 8 个方法（`Awake`/`OnDestroy`/`SetData`/`SetMyData`/`OnEnable`/`AlignScrollViewOnClickParcel`）**全是普通方法，无迭代器**。

**⇒ 不存在"条件不满足就一直等"的协程。** 若中断，只可能是**同步抛异常**或**同步死循环**。

### ③ 哪些解引用可能为 null？

**弹窗层已经做了统一防护**：`SetMyData` 里每一个 `ldr x0,[x19,#imm]` 后面都紧跟
`cbz x0, #0xA032544`（返回），`SetValues` 里 `tabController` 是**懒创建**（null 就现取组件）。
⇒ **弹窗自身的字段为 null 不会崩。**

**真正的风险区 = 两个 Tab 的 `SetMyData`，而它们全部是密文：**

| 类 | 方法 | vaddr | 状态 |
|---|---|---|---|
| `UIUserInfoTab_Profile` | `Awake` / `OnClickBlock` / `SetData` / `SetMyData` / `.ctor` | `0x0A0333D8` / `3B590` / `3B6D0` / `3C04` | **ENC（可解率 0）** |
| `UIUserInfoTab_Record` | `SetData` / `SetMultiFloorRaidDifficulty` / `SetMyData` / `.ctor` | `0x0A0341EC` / `347C0` / `3494C` / `35500` | **ENC（可解率 0）** |

这两个类合计 22 个字段的渲染逻辑**无法静态验证**。它们是"玩家信息"能否出现的关键。

## ④ 对你判据的回答（一句话）

```
· 不是在 await Addressables → ✗
· 不是在 await API（否则会有请求；实测 0 条）→ ✗
· 同步构造过程中失败（异常或死循环）→ ✓ 最符合现有观测
```

**但"失败在哪一行"静态拿不到**，因为承载 22 个字段渲染的两个 Tab 类整块在 ACE 密文里。

## ⑤ 最可疑的具体点（推断，中）

1. **`UIUserInfoTab_Assist.assistCharactersList`** —— 助战角色列表。该页签的 `SetMyData` 是 PLAIN（`0x0A0329E8`），
   需要好友/社团助战数据；若列表为空且代码里有 `while (... == null) yield` 之外的**同步**遍历（如 `[0]` 直接索引），
   会立刻抛 `IndexOutOfRange` / `NullReference`。**未验证（时间未及）。**
2. **`UIUserInfoTab_Record.SetMultiFloorRaidDifficulty`** —— 多楼层攻坚数据。
   你之前提过 `MultiFloorRaid` 相关对象可能为空；这个方法名直指它。
3. **`UIUserInfoTab_Profile.clanName` / `friendCount`** —— 社团/好友模块未初始化时可能为 null。
   但 `Profile.SetMyData` 是 ENC，无法确认它有没有做判空。

## ⑥ 建议的下一步（一条命令级的验证）

**看 logcat**：点「玩家信息」的瞬间有没有 `NullReferenceException` / `IndexOutOfRangeException` 刷屏。

* 有 → 把异常栈里的**类名+方法名**发我，我能直接定位到 ENC 方法的具体失败分支（栈里会带 `UIUserInfoTab_Profile.SetMyData` 之类）；
* 没有 → 那更可能是 **ENC 层里的同步死循环**（例如 `while (list.Count == 0) { }` 这种），需要 IL2CPP 层 hook 才能定；
* 也可以查 `Player.log`（Unity 自己的日志），路径通常在 `/sdcard/Android/data/com.RoamingStar.BlueArchive/files/Player.log`。

## ⑦ 拿不到的

| 项 | 原因 |
|---|---|
| `UIUserInfoTab_Profile` / `_Record` 的**方法体** | ACE 密文（`0x0A033xxx` / `0x0A034xxx`，可解率 0.00） |
| `UIUserInfoTab_Assist.SetMyData` 的完整逻辑 | 明文可达（`0x0A0329E8`），但本轮时间未及，**未分析** |
| 崩点行号 | 需要运行期异常栈 |

---

# 追加：日志为什么是空的 / 能不能不改 APK 拿异常

## Q1 这个 build 有没有关掉 Unity 日志？

### 实测 1：`boot.config` **没有** 关闭日志
从 `BA_noroot_prod_20261118_v1.apk` 里直接读出 `assets/bin/Data/boot.config`（**151 字节，全文**）：

```
max-chunks-per-shader=1
wait-for-native-debugger=0
hdr-display-enabled=0
gc-max-time-slice=3
androidStartInFullscreen=1
androidRenderOutsideSafeArea=1
```

**⇒ 没有任何 `nolog` / `-nolog` / 日志级别项。日志不是被 boot.config 关掉的。**
（`BA_noroot_v1.apk` 里的同名文件内容完全相同。）

### 实测 2：日志 API 存在，但**无法确认是否被调用**
`global-metadata.dat` 里能找到：

```
mdef=215652  SetLogCallbackDefined
mdef=215659  add_logMessageReceived
mdef=215660  remove_logMessageReceived
mdef=215661  CallLogCallback
mdef=218251  get_unityLogger
mdef=218298/218308  get_logHandler
mdef=218299/218310  get_logEnabled
mdef=218309          set_logHandler
mdef=218311          set_logEnabled
```

字符串池里也有 `logEnabled`(@0x6E9DD1) 与 `logMessageReceived`(@0x6DDB09)。

**但**：这些方法属于 **`UnityEngine.CoreModule`**，而我们的方法指针表 `ba_ptrs.bin`
只有 **154,173 条 = BlueArchive.dll 的方法**（mdef 218311 > 154173）。
⇒ **拿不到它们的 vaddr ⇒ 无法做 BL xref ⇒ 无法确认项目代码是否调用了 `set_logEnabled(false)`。**

**结论（Q1）：`boot.config` 清白（实测）；"代码里关日志"这条**存疑**，
缺的证据是「全程序集 methodPointers 表」——有了它我就能 xref `set_logEnabled` 和 `add_logMessageReceived`。**

## Q2 有没有不改 APK 就能拿异常的办法？

### 机制说明（Unity + IL2CPP on Android）
未捕获的托管异常在 Unity 里最终走 `Debug.LogException` → `Application.CallLogCallback`
→ **受 `Logger.logEnabled` 门控**。所以：

* 若 `logEnabled == true`（默认）⇒ 异常**必然**以 `E Unity` tag 出现在 logcat；
* 若 `logEnabled == false` ⇒ **连未捕获异常也一起消失**，logcat 干净但异常照抛。

**这与"每帧抛异常 + logcat 0 行"完全自洽** —— 但要坐实需要上面缺的那张指针表。

### 可以不改 APK 试的三招（按性价比）
1. **`adb shell setprop log.tag.Unity VERBOSE`** —— 只改系统属性，不动 APK。
   若日志只是被 tag 过滤掉的，这一条就能让它们出来。**建议先试这个，成本 5 秒。**
2. **`logcat -b all -v threadtime` 不过滤 tag**，抓全缓冲区，再按**进程 UID**（不是 tag）grep。
   如果按 UID 搜都是 0 行，才说明进程真的什么都没打印。
3. **`adb shell dumpsys gfxinfo <pkg> framestats`** / `dumpsys window` —— 不改 APK，
   能看主线程每帧耗时是否均匀（均匀=每帧一次异常处理；暴涨=卡循环）。

### 一个我之前没排除的竞争假设（建议一并验证）
"帧在出 + 零请求 + 无遮罩 + 主线程持续吃 CPU" **也符合**：
**打开了一个透明的全屏阻挡层**（`CanvasGroup.blocksRaycasts = true` 的空面板 / 全屏 Image raycast target）。
`UIPopup_UserInfo.SetValues` 里就有对 `[+0xA8]` / `[+0xB0]` 若干子对象的 `SetActive` 调用。
若某个 tab 面板被 `SetActive(true)` 但内容全空，表现为：**画面在动、点哪都没反应、看不到任何东西**。
**这个假设不需要异常，也不需要日志。**

## `UIUserInfoTab_Assist.SetMyData` @0x0A0329E8 的初步结论（明文，已看前 0x140 字节）
```asm
0x0A032A7C  ldr  x19, [x19, #0x20]     ; this.<+0x20>（assistCharactersList 或基类字段）
0x0A032A98  ldr  x20, [x8, #8]
0x0A032A9C  cbnz x20, #0xA032AFC       ; ★ 有判空分支
```
**⇒ 至少入口处有 null 防护，不是"直接拿 [0] 索引"那种写法。**
但方法更长（>0x140 字节），**后续循环体未看完，不能排除越界索引** —— **存疑**。
