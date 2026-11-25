# 黑屏取证 第二轮（PHONE_BLACKOUT2_20261117）

> 作者：phone-ops（本目录独占写入）
> 时间：2026-11-17 19:44–19:47 (+08:00)
> 设备：PLR110 / serial 3B661602DKU00000 / Android 17(SDK 37) / 1280x2800 横屏 2800x1272
> adb：`192.168.0.5:5555`（device，root 可用）
> 本次实例：**pid 27397**（ActivityRecord t452，`com.tech.sdk.bridge.TechSDKUnityPlayerActivity` 在前台）
> 全程只读：未点屏幕、未杀进程、未改任何设置

---

## 一句话结论（先给）

**截图仍是纯黑，且这次能用三条独立证据确认"不是截屏被禁止，而是真的没有新帧被合成"**：
`screencap` 纯黑（无 FLAG_SECURE）＋ 8 秒录屏 16 帧全黑 ＋ **SurfaceFlinger 对两个游戏图层连续两次采样都是 0 个帧时间戳**。
**没有任何 SYN-SENT**；但存在 **5 条 CLOSE_WAIT，其中 4 条接收队列里还有未读字节**（24 / 1 / 1 / 24 / 58）。

---

## 问题 1：画面上到底有没有东西？→ **没有（判定强度：高）**

### 1.1 截图（`/data/local/tmp/shot2.png`，17,788 B）
```
命令：adb shell su -c "screencap -p /data/local/tmp/shot2.png"
尺寸 2800x1272   max channel = 38   min = 0   mean = 0.002
非黑像素（任一通道 >8）= 336 px / 3,561,600 = 0.0094%
纯黑像素占比 = 99.990%
主色：100% 量化到 rgb(0,0,0)
```
那 336 个「非黑」像素极可能是状态栏图标/时钟的残影（max 只有 38，几乎不可见）。

### 1.2 录屏（`screenrecord --time-limit 8 --bit-rate 8000000`，8.3 秒，149,020 B）
ffmpeg 抽 16 帧（fps=2），逐帧统计：

| 帧 | max | nonblack px | pure black |
|---|---|---|---|
| frame_01 | 36 | 342 (0.0096%) | 99.860% |
| frame_02 | 36 | 342 | 99.934% |
| frame_03 | 36 | 342 | 99.934% |
| frame_04 | 36 | 342 | 99.934% |
| frame_05 | 36 | 561 (0.0158%) | 99.912% |
| frame_06–08 | 36 | 561 | 99.912% |
| frame_09–11 | 36 | 562 | 99.982% |
| frame_12 | 36 | 561 | 99.912% |
| frame_13–16 | 36 | 562 | 99.982% |

**⇒ 16 帧全部是「纯黑 + 少量极暗噪点」，没有任何一帧出现可辨认的画面内容。**
（变化只在 nonblack 342→561→562 之间，是亚像素级噪声，不是动画。）

### 1.3 ★ FLAG_SECURE 检查（决定旧证据作不作废）
```
命令：dumpsys window windows | grep -iE 'SECURE|mDisableSecureWindows'
输出：  mDisableSecureWindows=false
      （窗口 dump 里没有出现任何 SECURE / mHasSecureFlag / isSecure 标记）
```
**⇒ 没有开防截屏。`screencap` 拍到的就是真实画面，纯黑是真黑，不是被 FLAG_SECURE 抹掉的。**

### 1.4 ★★ 出帧统计（最决定性）
**A) gfxinfo（HWUI 计数器）**
```
命令：dumpsys gfxinfo com.RoamingStar.BlueArchive（间隔 10.1 秒采两次）
采样1：Total frames rendered: 0    Janky frames: 0 (0.00%)    Number Missed Vsync: 0
采样2：Total frames rendered: 0    Janky frames: 0 (0.00%)    Number Missed Vsync: 0
```
⚠️ **注意**：`gfxinfo` 统计的是 **HWUI**（Android View 层）的出帧。本作是 Unity + SurfaceView，渲染走 EGL/自己那条队列，**不经过 HWUI**，所以这里的 0 **不能单独作为"没渲染"的证据**。记录在此，只当参考。

**B) SurfaceFlinger 图层帧时间戳（真家伙）**
```
命令：
  dumpsys SurfaceFlinger --list | grep "SurfaceView[com.RoamingStar.BlueArchive"
  → f02687 SurfaceView[com.RoamingStar.BlueArchive/...TechSDKUnityPlayerActivity]#36286
  dumpsys SurfaceFlinger --list | grep "VRI-com.RoamingStar.BlueArchive"
  → VRI-com.RoamingStar.BlueArchive/...TechSDKUnityPlayerActivity#36282

  dumpsys SurfaceFlinger --latency "<上面两个图层>"（各采两次，间隔 6 秒）
结果：
  LAYER=...SurfaceView[...]#36286   latA_lines=2 nonzeroA=**0**   latB_lines=2 nonzeroB=**0**
  LAYER=VRI-...[#36282]             latA_lines=2 nonzeroA=**0**   latB_lines=2 nonzeroB=**0**
  唯一一行内容是 16666666（= 1/60 秒的刷新周期），**没有任何一帧的 present 时间戳**
```
**⇒ SurfaceFlinger 层面对这两个图层**没有任何已提交/已合成的帧**。**
**判定**：这一屏不是"渲染出黑色"，而是**根本没有新帧被提交到合成器**（图层保持在空/上一次内容状态 → 屏幕全黑）。

### 1.5 图层结构（有没有全屏遮罩）
```
204 层里属于本作的有：
  VRI-com.RoamingStar.BlueArchive/...TechSDKUnityPlayerActivity#36282        （窗口层，parentId 36281）
  86b1d76 ...TechSDKUnityPlayerActivity#36281                                （窗口 leash）
  f02687 SurfaceView[...]#36286  parentId=36285                              （SurfaceView 层）
  f02687 SurfaceView[...](BLAST)#36287                                       （BLAST 子层）
  Background for f02687 SurfaceView[...]#36288  z=-2147483648                （背景层）
  ActivityRecordInputSink ...#36280  z=-2147483648                           （输入 sink，正常）
  ActivityRecord{...TechSplashActivity t452}#36262 - rotation-leash#36279    （**启动页的 leash 还挂着**）
  Surface(name=e1702f4 …starting_reveal#34341) / (71abd0c …#33952) /
  (86b1d76 …#36289) / (f954d2f …#32793)                                      （4 个 starting_reveal 动画 leash）
```
**判读**：
- **没有**第三方全屏 overlay 盖在游戏上（抖音等应用的层在别的 task 里，且不在最上层）。
- 但注意有 **4 个 `starting_reveal` 动画 leash 和 1 个 `TechSplashActivity` rotation-leash 仍然存在** —— 这些是窗口打开动画留下的图层。
- 【推断·中】黑屏可能发生在「启动 reveal 动画结束后本应显示 SurfaceView 内容，但 SurfaceView 从未提交过一帧」这条路径上。

---

## 问题 2：它在等什么？→ **没有 SYN-SENT；有一堆"半关连接"带未读字节（判定强度：中）**

### 2.1 全量非 LISTEN 连接（`/proc/27397/net/tcp`，十六进制已解码）
| 本地 | 远端 | 状态 | tx:rx 队列 |
|---|---|---|---|
| 192.168.0.5:45194 | **111.230.195.253:8080** | ESTABLISHED | 00000000:00000000 |
| 127.0.0.1:10156 | 127.0.0.1:47028 | CLOSE_WAIT | 00000000:**00000037**(55 B) |
| 192.168.0.5:56582 | **112.13.210.86:443** | CLOSE_WAIT | 00000000:**00000018**(24 B) |
| 192.168.0.5:43856 | 36.156.168.72:443 | CLOSE_WAIT | 00000000:00000001(1 B) |
| 192.168.0.5:37716 | 36.155.131.35:443 | CLOSE_WAIT | 00000000:00000001(1 B) |
| 192.168.0.5:60096 | 111.2.79.11:443 | CLOSE_WAIT | 00000000:**00000018**(24 B) |
| 192.168.0.5:33626 | 8.141.97.200:443 | CLOSE_WAIT | 00000000:**0000003A**(58 B) |

（`ss -tnp` 里同批：`112.13.210.86:443` 还有一条 ESTABLISHED；其余 9 条 CLOSE_WAIT 见 `D_ss.txt`）

**关键判读**：
- **SYN_SENT = 0 条** ⇒ 没有"卡在连不上的 TCP"。
- **CLOSE_WAIT = 5 条（游戏 uid 10577）**：服务器已经 FIN，客户端没有 close。
- 其中 **4 条 rx 队列非 0（24/1/1/24/58 字节）** ⇒ **服务器写完这些字节后发了 FIN，客户端从来没把它们 read 走**。
- 有 1 条 **ESTABLISHED 到 `111.230.195.253:8080`**（非 443、非我们服务器 `<SERVER_IP>`）—— 这是一个 8080 端口的明文/代理类连接，值得单独查是谁发起的（可能是某个 SDK 上报通道）。

### 2.2 DNS
```
getprop | grep -i dns →
  persist.device_config.connectivity.data_stall_consecutive_dns_timeout_threshold=5
  persist.sys.ocloud.url=https://httpdns.ocloud.oppomobile.com
  persist.sys.oplus.dns_customized_timeout=1
（都是系统配置项，没有逐个域名的解析结果）
/data/misc/net/ 未取到解析缓存（权限/格式未知）
⇒ **这一项分不清**：没有拿到 "bluearchive-cn.com 解析到哪个 IP" 的直接证据。
```

---

## 问题 3：下载缓存是不是被截断了？→ **没有发现截断痕迹（判定强度：中高）**

```
命令：ls -laR /sdcard/Android/data/com.RoamingStar.BlueArchive/files/ | head -300
      find files -type f \( -name '*.tmp' -o -name '*.download' -o -name '*.part' \)
      find files -type f -size 0
      find files -type f -newermt '-90 minutes'
```
结果：
```
=== tmp/download/part ===   （空，0 个）
=== zero-byte ===           （空，0 个）
=== 最近 90 分钟内写入 ===    （空，0 个）
```
顶层目录（19:42 有更新的只有这些）：
```
2071278565329732703   20,480   19:42
DeviceOption             285   19:42
TitleVideoAudioSaveData  116   19:42
catalog_Remote.hash       32   19:42
manifest.db       12,677,120   19:42
manifest_backup.db 12,677,120  19:42
```
⇒ **只有存档/清单类小文件在刷新，没有任何正在下载的中间文件，也没有 0 字节的残缺 bundle。**

---

## 问题 4：线程栈有没有变化？→ **没变（判定强度：高）**

本次 `debuggerd -b 27397`（19:46，424 KB）与旧 `report\_tmp\blackout\bt.txt` 对比：

```
"UnityMain" sysTid=27448
  #00 syscall
  #01 __futex_wait_ex
  #02 pthread_cond_wait
  #03 libunity.so+0x459344      ← 与旧 bt.txt 完全一致
  #04 libunity.so+0x451e54
  #05 libunity.so+0x2de768

"UnityGfxDeviceW" sysTid=27546
  #01 libunity.so+0xb5b0a8
  #02 libunity.so+0x1f54a4
  #03 libunity.so+0x37909c
  #04 libunity.so+0x9d9b44      ← 与之前一致

第二个 "UnityMain"（网络线程）sysTid=28282
  #00 __ppoll
  #01 poll
  #02 libil2cpp.so+0x63c2540    ← C# 网络层在等 socket 事件
```
**⇒ UnityMain 仍停在 `pthread_cond_wait`，网络线程仍停在 `poll`，状态没有演进，也没有出现新的阻塞形态。**

---

## 分不清的地方（明确标注，不替谁圆）

1. **「用户看到点屏幕有动画反应」 vs 「系统侧 0 新帧」矛盾**：
   我只能证明 **屏幕内容层面没有新帧、录屏全黑**。用户看到的"动画反应"可能是：
   - 音效 / 震动 / 系统手势返回的动画（那是 SystemUI 的层，不是游戏层）；
   - 或者发生在**用户点按的瞬间由别的组件画出来的**东西，而不是游戏 SurfaceView。
   **这一条我无法用现有手段分辨**，除非在点按那一刻同时录屏 + 抓 SystemUI 层帧。
2. **到底在等哪个响应**：CLOSE_WAIT 里那 4 条未读字节（24/1/1/24/58 B）很可疑，但**无法证明**它们就是卡住的原因（也可能是无关的遥测响应尾巴）。
3. **端口 8080 那条 ESTABLISHED（111.230.195.253）** 归属未查清。
4. **DNS 解析结果未取到**。

---

## 原始产物清单（都在 `report\_tmp\blackout2\`）

```
shot2.png            17,788 B   本轮截图（纯黑）
rec.mp4             149,020 B   8 秒录屏
frame_01..16.png    ~15-18 KB   抽帧
A_layers.txt          498 B     SurfaceView 图层
B_sum.txt              50 B     gfxinfo（两次都 0）
C_secure.txt           30 B     mDisableSecureWindows=false
D_ss.txt            2,437 B     ss -tnp（游戏连接）
D_tcp4.txt          1,050 B     /proc/27397/net/tcp
D_tcp6.txt          4,757 B     /proc/27397/net/tcp6
D_dns.txt             448 B     getprop dns
E_cache.txt         2,642 B     缓存目录 + 截断检查
F_stacks.txt      424,304 B     debuggerd -b 27397
```
手机侧对应文件：`/data/local/tmp/shot2.png`、`/data/local/tmp/rec.mp4`、`/data/local/tmp/probe3/`
（**未删除手机上的任何东西**）

---

# §60s 录屏（追加，2026-11-17 19:49:56–19:50:57）

> 命令：`adb shell su -c "screenrecord --time-limit 60 --bit-rate 8000000 /data/local/tmp/rec60.mp4"`
> 录制窗口：**19:49:56.8 → 19:50:57.2**（实测墙钟 60.4 s），用户在这 60 秒里持续点屏幕
> 产物：`rec60.mp4` **45,486,780 B**（对比上一轮 8 秒录屏只有 **149,020 B**）
> 抽帧：`ffmpeg -vf fps=0.5` → `r60_01.png … r60_30.png`（每 2 秒一帧）

## ★★ 结论（反转上一轮）

**黑屏不是全程的。这 60 秒里，前约 30 秒是纯黑，后约 30 秒游戏大厅正常渲染出来了。**

- 前 15 帧（t=0–30 s）：每帧 ~14–18 KB，max=36，非黑像素 342–562 px（**0.0096%–0.0158%**），纯黑 99.87%–99.98%
- 后 15 帧（t=30–60 s）：每帧 ~578–761 KB，max=**255**，非黑像素 **762,407–1,027,181 px（21.4%–28.8%）**
- 画面内容：**沙勒大厅**——左上「等级 1 老师0002 0/8」「等级奖励」，顶部「24/24」「10,000」「600」，
  底部「咖啡厅 / 日程 / 成员 / 编队 / 社交 / 制造 / 商店 / 招募」，右下「业务区」「活动一览」，右上活动横幅「我等乃神祕学研究会！」
- 帧 16 与帧 30 对比：同一大厅，只有**中央蓝色旋转光球**在转（r60_17 光球在右侧、r60_30 光球几乎熄灭/在中心），其余 UI 完全一致
  ⇒ **这是一直活着的渲染循环在画大厅 UI**，不是静止画面

**判定**：之前两轮"纯黑"采样（8 秒录屏 + 两次 screencap）是**黑屏窗口期内的采样**，
**黑屏会在约 30 秒后自行结束并进入大厅**。所以"任意界面点返回都黑屏"应改述为
**"点返回后会黑约 30 秒，然后回到大厅"** —— 除非用户观察到的是更长时间的黑屏（这 60 秒里我只看到一次恢复）。

## 逐帧统计表（摘要）

| 帧 | 约 t(s) | PNG 大小 | max | 非黑 px | 非黑占比 | 纯黑占比 |
|---|---|---|---|---|---|---|
| r60_01 | 0–2 | 18,116 | 36 | 342 | 0.0096% | 99.869% |
| r60_02 | 2–4 | 14,523 | 36 | 562 | 0.0158% | 99.982% |
| r60_03 | 4–6 | 17,563 | 36 | 561 | 0.0158% | 99.912% |
| r60_04 | 6–8 | 17,563 | 36 | 561 | 0.0158% | 99.912% |
| r60_05 | 8–10 | 14,523 | 36 | 562 | 0.0158% | 99.982% |
| r60_06 | 10–12 | 14,523 | 36 | 562 | 0.0158% | 99.982% |
| r60_07 | 12–14 | 17,563 | 36 | 561 | 0.0158% | 99.912% |
| r60_08 | 14–16 | 17,563 | 36 | 561 | 0.0158% | 99.912% |
| r60_09 | 16–18 | 17,563 | 36 | 561 | 0.0158% | 99.912% |
| r60_10 | 18–20 | 14,523 | 36 | 562 | 0.0158% | 99.982% |
| r60_11 | 20–22 | 14,523 | 36 | 562 | 0.0158% | 99.982% |
| r60_12 | 22–24 | 17,563 | 36 | 561 | 0.0158% | 99.912% |
| r60_13 | 24–26 | 17,563 | 36 | 561 | 0.0158% | 99.912% |
| r60_14 | 26–28 | 17,563 | 36 | 561 | 0.0158% | 99.912% |
| r60_15 | 28–30 | 14,523 | 36 | 562 | 0.0158% | 99.982% |
| **r60_16** | 30–32 | **761,286** | **255** | **1,006,274** | **28.2534%** | 65.007% |
| **r60_17** | 32–34 | 708,388 | 255 | 1,007,445 | 28.2863% | 66.472% |
| **r60_18** | 34–36 | 712,989 | 255 | 1,007,925 | 28.2998% | 64.524% |
| **r60_19** | 36–38 | 689,931 | 255 | 999,563 | 28.0650% | 65.763% |
| **r60_20** | 38–40 | 669,365 | 255 | 893,645 | 25.0911% | 68.403% |
| **r60_21** | 40–42 | 710,875 | 255 | 1,027,181 | 28.8404% | 65.166% |
| **r60_22** | 42–44 | 579,361 | 255 | 762,407 | 21.4063% | 77.682% |
| **r60_23** | 44–46 | 592,561 | 255 | 776,732 | 21.8085% | 77.222% |
| **r60_24** | 46–48 | 586,654 | 255 | 776,701 | 21.8076% | 77.269% |
| **r60_25** | 48–50 | 578,830 | 255 | 762,478 | 21.4083% | 77.684% |
| **r60_26** | 50–52 | 595,762 | 255 | 776,752 | 21.8091% | 77.148% |
| **r60_27** | 52–54 | 589,461 | 255 | 776,679 | 21.8070% | 77.209% |
| **r60_28** | 54–56 | 582,037 | 255 | 762,461 | 21.4078% | 77.605% |
| **r60_29** | 56–58 | 592,467 | 255 | 776,724 | 21.8083% | 77.227% |
| **r60_30** | 58–60 | 615,250 | 255 | 809,463 | 22.7275% | 73.656% |

## 非黑占比 > 0.05% 的帧（"有画面"候选帧）—— 共 **15 帧**

```
r60_16.png  28.2534%   report\_tmp\blackout2\r60_16.png   (761,286 B)
r60_17.png  28.2863%   report\_tmp\blackout2\r60_17.png   (708,388 B)
r60_18.png  28.2998%   report\_tmp\blackout2\r60_18.png   (712,989 B)
r60_19.png  28.0650%   report\_tmp\blackout2\r60_19.png   (689,931 B)
r60_20.png  25.0911%   report\_tmp\blackout2\r60_20.png   (669,365 B)
r60_21.png  28.8404%   report\_tmp\blackout2\r60_21.png   (710,875 B)
r60_22.png  21.4063%   report\_tmp\blackout2\r60_22.png   (579,361 B)
r60_23.png  21.8085%   report\_tmp\blackout2\r60_23.png   (592,561 B)
r60_24.png  21.8076%   report\_tmp\blackout2\r60_24.png   (586,654 B)
r60_25.png  21.4083%   report\_tmp\blackout2\r60_25.png   (578,830 B)
r60_26.png  21.8091%   report\_tmp\blackout2\r60_26.png   (595,762 B)
r60_27.png  21.8070%   report\_tmp\blackout2\r60_27.png   (589,461 B)
r60_28.png  21.4078%   report\_tmp\blackout2\r60_28.png   (582,037 B)
r60_29.png  21.8083%   report\_tmp\blackout2\r60_29.png   (592,467 B)
r60_30.png  22.7275%   report\_tmp\blackout2\r60_30.png   (615,250 B)
```
**推荐先看的 3 帧**：`r60_17.png`（大厅+中央蓝色光球在右侧）、`r60_30.png`（同一大厅+光球几乎熄灭）、`r60_16.png`（刚恢复的第一帧）

## 焦点窗口（录制之后 19:52 查）

```
命令：dumpsys window | grep -iE 'mCurrentFocus|mFocusedApp'
输出：
  mCurrentFocus=null                                   ← 这是 display 264（副显示/空 display）那一条
  mFocusedApp=null
  mCurrentFocus=Window{86b1d76 u0 com.RoamingStar.BlueArchive/com.tech.sdk.bridge.TechSDKUnityPlayerActivity}
  mFocusedApp=ActivityRecord{115284661 u0 com.RoamingStar.BlueArchive/com.tech.sdk.bridge.TechSDKUnityPlayerActivity t452}
```
**判定**：
- **焦点窗口就是游戏自己**（`TechSDKUnityPlayerActivity`，窗 id `86b1d76`，ActivityRecord `t452`）。
- `grep -iE 'Splash|Starting'` 在 `dumpsys window` 全文里 **零命中** ⇒ **没有处于 Starting 状态的窗口**。
- 之前 SurfaceFlinger 层列表里那个 `ActivityRecord{…TechSplashActivity t452}#36262 - rotation-leash#36279`
  是**启动页窗口残留的动画 leash 图层**，但它**不是焦点、也不在 Starting 队列**（`dumpsys window` 里查不到 Splash 窗口）。
- **⇒ 不是"启动页窗口一直没换成游戏窗口"那条线**：焦点、窗口、Activity 都已经是游戏，且现在画面就是大厅。
- 另注：`Window #` 总数 **24**，属本作的只有 `Window #19 Window{86b1d76 …TechSDKUnityPlayerActivity}`，**没有第二层全屏覆盖窗口**。

## 与本轮其他证据的关系（避免误读）

- 19:44 的 `screencap`（纯黑）与 8 秒录屏（16 帧全黑）→ **落在黑屏窗口期内**，结论仍然成立（那时确实没有帧）。
- 19:52 的 `screencap`（`shot3.png` **612,964 B**）→ 已有画面，与 r60_30 一致。
- 所以「SurfaceFlinger 0 帧时间戳」只在**黑屏那一段**为真；一旦恢复，帧就正常提交。
  **上一轮"根本没有新帧提交"的判断，应限定为"黑屏期间"**，不能外推到整个进程生命周期。

## 仍然分不清

1. **黑屏是"必然 30 秒后自恢复"还是"用户点屏幕把它点醒了"** —— 这 60 秒里两种解释都成立，需要一次"不点屏幕"的对照录屏才能分开。
2. 用户描述的"点屏幕有动画"在黑屏的 30 秒里**没有在录屏中体现**（那 15 帧全黑，非黑像素只有 342–562 个），
   所以那个"动画"更可能是**音效/震动**，或者是**恢复之后的**反馈。
3. 恢复瞬间前后（r60_15 → r60_16）有没有伴随网络请求，**这一节没查**（rec60 期间没抓 DNAT 计数）。
