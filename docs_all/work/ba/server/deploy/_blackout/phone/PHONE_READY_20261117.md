# 手机取证通道就绪报告（PHONE_READY_20261117）

> 作者：phone-ops（本目录为我的独占写入范围）
> 时间：2026-11-17 19:37 (+08:00)
> 目标：为「任务界面右上角大厅按钮 → 全屏黑屏」这一瞬间准备可随时启动的 logcat 取证

---

## 1. 结论先行

**现在就能抓。** adb 通道已经打通（无线），脚本已在本目录、已实测 `start / mark / stop / pull` 四条命令全部可用。

- adb 地址：**`192.168.0.5:5555`**
- 状态：`adb devices` → `192.168.0.5:5555  device`（已授权，无需再点手机确认）
- adb 版本：`Android Debug Bridge 1.0.41 / 33.0.0-8141338`（PC）
- 设备：**PLR110（一加 Ace 2）**，serial **3B661602DKU00000**，Android **17 / SDK 37**，屏幕 **1272x2800**
- 权限：`adb shell su -c id` → `uid=0(root) … context=u:r:ksu:s0`（KernelSU root 可用）

---

## 2. 通道是怎么打通的（供复盘 / 重启后重现）

手机原状态：
```
init.svc.adbd = stopped        （adb 守护进程没在跑）
sys.usb.state = mtp           （USB 只给了 MTP，没有 adb）
5555 未监听                    （无线调试开关没开）
```
处理步骤（全程用现有的 root 反向 shell `192.168.0.5:18080` 执行）：

```sh
# 1) 用 root 起 adbd 并让它监听 TCP 5555
setprop persist.adb.tcp.port 5555
setprop service.adb.tcp.port 5555
setprop ctl.stop adbd ; sleep 2 ; setprop ctl.start adbd
#   -> adbd pid 起来了，`ss -ltn` 出现 LISTEN *:5555

# 2) adb 首次连接是 unauthorized（ro.adb.secure=1，需要 RSA 授权）
#    不想让用户去点手机，所以直接把 PC 的公钥写进授权表（追加，不覆盖原有）
mkdir -p /data/misc/adb && touch /data/misc/adb/adb_keys
grep -qF "<PC 的 adbkey.pub>" /data/misc/adb/adb_keys || echo "<PC 的 adbkey.pub>" >> /data/misc/adb/adb_keys
chown root:shell /data/misc/adb/adb_keys ; chmod 640 /data/misc/adb/adb_keys
restorecon /data/misc/adb/adb_keys
setprop ctl.stop adbd ; sleep 2 ; setprop ctl.start adbd
```
PC 侧：
```powershell
adb kill-server ; adb start-server
adb connect 192.168.0.5:5555      # -> connected to 192.168.0.5:5555
adb devices                       # -> 192.168.0.5:5555   device
```
**注意**：`/data/misc/adb/adb_keys` 里原来有 0 行（等于之前没授权过任何 PC），我只**追加**了一行，没有覆盖。

**重启后**：`persist.adb.tcp.port` 已写入，理论上重启仍会监听 5555；但 KernelSU/系统更新可能导致 adbd 恢复 stopped，若重启后 `adb devices` 为空，**重跑上面第 1、2 步即可**（root shell 在 18080）。

---

## 3. 取证脚本（本目录）

**`capture_logcat.cmd`** —— 已实测可用。

| 命令 | 作用 | 实测结果 |
|---|---|---|
| `capture_logcat.cmd info` | 设备/serial/系统版本/分辨率/游戏 pid/当前焦点窗口 | ✅ |
| `capture_logcat.cmd start` | 清空 logcat → 在**手机上后台**跑 `logcat -v threadtime -b all > /data/local/tmp/blackout_logcat.txt` | ✅ 文件 2 秒涨到 657 KB |
| `capture_logcat.cmd mark` | 打时间标记 + 截屏 + `dumpsys window` + `dumpsys meminfo` + `pidof` 全部落盘 | ✅ 生成 4 个文件 + 1 张 png |
| `capture_logcat.cmd stop` | `pkill -f 'logcat -v threadtime'`，并 `ls -l` 确认文件还在 | ✅ |
| `capture_logcat.cmd pull` | `adb pull` 到 `.\logs\logcat_blackout_<时间戳>.txt` | ✅ 3.9–8.6 MB/s |
| `capture_logcat.cmd all` | start → 暂停等用户复现 → stop + mark + pull | 未实测（需用户在手机上操作） |

**产物目录**：`work\ba\server\deploy\_blackout\phone\logs\`
示例（19:37 自测产物，可直接删）：
```
logcat_blackout_20261117_193738.txt   310,285 B
mark_20261117_193736.png            1,452,892 B
mark_20261117_193736_meminfo.txt        3,855 B
mark_20261117_193736_pidof.txt              6 B
mark_20261117_193736_window.txt         4,187 B
```

**设计取舍（为什么 logcat 写在手机上而不是 PC）**：PC 侧 `start /b` 起的后台进程容易在父窗口关闭时被带走；改成「手机端 setsid 后台写文件 + 事后 adb pull」，断线也不丢。

---

## 4. 复现黑屏时，需要用户做什么（一步一步）

**只要 3 步，用户不用碰电脑：**

1. **先告诉 phone-ops「我要复现了」**（我在 PC 上执行 `capture_logcat.cmd start` 清空并开始抓）。
2. **在手机上操作**：进游戏 → 到任务界面 → 点右上角「大厅」按钮 → 出现黑屏 → **停在这个黑屏画面等 30 秒**（不要杀进程、不要返回、不要切后台）。
   - 如果黑屏会自动恢复，**看到黑屏时立刻用另一只手轻点一下屏幕**（只为了在 logcat 里留一个触摸事件时间戳，不会改变状态）。
3. **再告诉 phone-ops「复现完了」**（我执行 `stop` + `mark` + `pull`，并附一张黑屏截图和 meminfo/window 快照）。

**如果用户想自己全程操作（不用等我）**：双击 `capture_logcat.cmd all`，按屏幕提示在手机上复现，然后回到命令行按任意键回车即可。

---

## 5. 当前现场状态（19:37）

```
游戏进程 pidof com.RoamingStar.BlueArchive = 9351   （第三次/第四次重启后的新实例）
当前前台窗口 = com.ss.android.ugc.aweme/.splash.SplashActivity   ← 用户此刻在刷抖音，不在游戏里
```
**⇒ 现在不是复现窗口，等用户把游戏切到前台再说。**

---

## 6. 已知限制 / 风险（先声明，免得白抓）

1. **release 包不打 Unity 日志**：之前 3 次取证（12,105 行全量 logcat）里，Unity 的 `AssetBundle`/`Failed to load`/`Exception` **一条都没有**。所以「黑屏原因」**大概率不会直接出现在 logcat 里**，可能只能看到：
   - Activity 生命周期变化（`onPause/onResume`、`TechSDKUnityPlayerActivity` 重建）
   - Surface/窗口变化（`relayoutWindow`、`state from NO_SURFACE` 之类）
   - 崩溃/ANR 前兆（`lowmemorykiller`、`Choreographer skipped frames`）
   - 触摸事件是否真的进到了 app（`dispatchTouchView`）
   **所以这次的重点是把「窗口还在不在、Surface 有没有、进程活不活」三件事固定下来**，脚本里的 `mark` 就是干这个的。
2. **黑屏那一刻如果进程被杀**，`mark` 会拿到 `NOT_RUNNING`，同时 meminfo 会失败 —— 这本身就是强证据（说明不是单纯渲染黑，而是进程没了）。
3. `logcat` 缓冲区大小有限（默认 256K×若干 buffer），**start 之后动作要快**，别在 start 和复现之间隔太久，否则早期日志会被冲掉。

---

## 7. 快速排障（如果 adb 又断了）

```powershell
adb devices                     # 空？
adb connect 192.168.0.5:5555    # 手动重连
Test-NetConnection 192.168.0.5 -Port 5555   # 端口不通 -> 回 §2 用 18080 重起 adbd
```
18080 的 root shell 若也断了，让用户在手机上执行：
```sh
su -c 'setsid /data/adb/ksu/bin/busybox nc -ll -p 18080 -e /system/bin/sh'
```
