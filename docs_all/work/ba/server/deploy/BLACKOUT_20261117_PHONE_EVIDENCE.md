# 黑屏事件：手机侧硬证据（2026-11-17 19:39 复现）

## 结论摘要

服务端在整段时间内 **完全干净**（零请求、零错误）。手机侧证据显示：
**画面是真的没有画出来**（帧缓冲纯黑，不是被黑色遮罩盖住），且 Unity 主线程在等待。

## 一、复现过程

- 19:39:25 全新启动（`Account_Auth` → `Account_LoginSync` 122,968 B）
- 19:39:26~28 大厅启动期预取（`Mission_List` ×3、`Mission_GuideMissionSeasonList`、`MiniGame_MissionList`、`Toast_List` 等）
- 19:39:31~32 邮件领取（`Mail_ListSemiPermanent` → `Mail_List` → `Mail_Receive` 3,224 B → `Mail_List`）
- 19:39:35 最后一条请求：`Event_RewardIncrease`（384 B，注意比平常的 408 B 小）
- **此后到 19:42 无任何请求**。用户从任务界面点左上角「返回」和右上角「大厅」**均黑屏**。

## 二、手机侧证据（全部原始文件在 `report\_tmp\blackout\`）

### 1. 截图 → 纯黑
```
adb shell su -c "screencap -p /data/local/tmp/shot.png" ; adb pull
文件: report\_tmp\blackout\shot.png (17,788 B)
尺寸: 2800 x 1272 (横屏)
采样: 每 4 像素取 1，共 222,606 个采样点
  RGB(0,0,0)        : 222,594  (100.00%)
  max channel value : 33
  nonblack(>8) ratio: 0.0027%   (6 个点，属于压缩噪声)
```
⇒ **没有任何极暗的 UI 轮廓、没有转圈、没有动画残留**。

### 2. logcat → 游戏进程零异常
```
adb shell su -c "logcat -d -b all -v threadtime" > logcat_now.txt
总行数: 14,177
grep -i 'Exception|il2cpp|NullReference|Failed to|FATAL|ANR'
游戏进程 (pid 24419) 命中: 仅 3 条无关行
  Failed to find provider info for com.meizu.flyme.openidsdk
  Failed to find provider info for cn.nubia.identity
  Failed to find provider info for com.vivo.vms.IdProvider
```
⇒ **release 包不打 Unity 日志这一点被证实**。无法从 logcat 得到异常栈。

### 3. 全线程 native backtrace → 主线程在等
```
adb shell su -c "debuggerd -b 24419" > bt.txt   (2,601 行)
```
UnityMain (sysTid=24493) 栈顶：
```
#00 libc.so (syscall)
#01 libc.so (__futex_wait_ex)
#02 libc.so (pthread_cond_wait+76)
#03 libunity.so
#04 libunity.so
#05 libunity.so
#06 libunity.so
#07 libunity.so
#08 libunity.so
#09 boot.oat (art_jni_trampoline)
#10 base.odex (com.unity3d.player.K0.handleMessage+888)
#11 boot-framework.oat (android.os.Handler.dispatchMessage)
```
⇒ **UnityMain 停在 `pthread_cond_wait`，不是死循环**（对比：死循环会是持续 Running 且 CPU 打满）。

线程表里还有 6 个 `AssetGarbageCol`（Unity 资源 GC 工作线程），没有出现 UnityGfx/RenderThread 级 GPU 线程卡在 `eglSwapBuffers` 的证据。

## 三、服务端时间线（同一时刻，零异常）

```
19:39:25 /api/account/auth                       200  len 3500
19:39:26 /api/account/loginsync                  200  len 122968
19:39:26 /api/mission/list                       200  len 1260   ← 极小
19:39:26 /api/mission/guidemissionseasonlist     200  len 448    ← GuideMissionSeasonDBs:[] / MissionProgressDBs:[]
19:39:27 /api/mission/list                       200  len 1260
19:39:27 /api/mission/list                       200  len 1304   ← 三次调用两次长度不同
19:39:27 /api/minigame/missionlist               200  len 428
19:39:32 /api/mail/receive                       200  len 3224
19:39:35 /api/event/rewardincrease               200  len 384    ← 最后一条
（之后到 19:42 完全空白）
```

`Mission_GuideMissionSeasonList` 的明文已解密成功，内容：
```json
{"Protocol":8006,"GuideMissionSeasonDBs":[],"ServerTimeTicks":639305411670000000,
 "ServerNotification":8,"RequestId":"b1dd0cee-...","MissionProgressDBs":[]}
```
对应 `MissionHandler.cs:259-272` 的硬编码空数组。

## 四、已撤销的错误结论（留档，别重犯）

| # | 错误结论 | 提出者 | 为什么错 | 撤销时间 |
|---|---|---|---|---|
| 1 | 「34 次领奖、重复领 15 个章节，导致库里重复行」 | Lead | 精确统计是 **29 次请求 / 29 个不同章节 / 29 行记录**，1:1:1。我扫日志目测数错了 | 19:38 |
| 2 | 「19:31:53 那条 TLS 连接没有 HTTP 日志，是嫌疑现场」 | Lead | `$session_time=73.487` 单位是**秒**，那是 19:30:40 打开、19:31:53 关闭的长连接，上行 32,423 B ≈ 29×946 + 开销，就是那批领奖请求本身 | 19:38 |

## 五、仍然成立的事实

1. **`CampaignManager.cs:217-236` 不查重**（代码缺陷客观存在，本轮未被触发）。
2. **`/unlockall campaign` 会让 29 个章节奖励同时可领**，这是官方服务器不会出现的状态。
3. **退出「任务/战役」子界面时，客户端不发任何请求**（19:28 从战斗结算回大厅是正常的，说明客户端本身能回大厅）。

## 六、下一步：控制实验（需要用户点击）

| 实验 | 操作 | 预期 |
|---|---|---|
| A | 大厅 → 「编队」→ 返回 | ? |
| B | 大厅 → 「咖啡厅」→ 返回 | ? |
| C | 大厅 → 「任务」→ 返回 | 黑（已证实） |

- 只有 C 黑 ⇒ 任务界面专属，重点查 `Mission_List` / `MissionProgressDBs` 为空。
- 全黑 ⇒ 客户端自身问题，与我们的数据无关，记成已知问题。

## 七、原始文件

```
report\_tmp\blackout\shot.png            截图（纯黑）
report\_tmp\blackout\shot_small.png       缩略图
report\_tmp\blackout\logcat_now.txt       logcat 全量 14,177 行
report\_tmp\blackout\bt.txt               debuggerd 全线程栈 2,601 行
report\_tmp\blackout\px.py                像素统计脚本
```
