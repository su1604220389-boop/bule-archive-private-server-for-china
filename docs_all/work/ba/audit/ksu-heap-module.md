# KSU 模块 heap1024（dalvik.vm.heapsize 512m → 1024m）交付报告

- 负责人：ksu-heap-module（第 1 层工程师）
- 时间：2026-11-11
- 设备基线（交付前后均只读确认）：`dalvik.vm.heapsize=512m`、`dalvik.vm.heapgrowthlimit=256m`，管理器为 **KernelSU**，`/data/adb/ksu/bin/resetprop -> /data/adb/ksud`
- 结论：**已交付，未安装、未重启、未改任何现网属性**

---

## 1. 交付物

| 文件 | 路径 | 大小 | SHA-256 |
|---|---|---|---|
| 模块 zip | 工作区 `$WS/Heap1024_v1.0.zip` | 1896 B | `eefcba66663d4c7ef3d91b79e3dc7c3397d4eb7bc57c998df4cf4058c7e24ced` |
| 模块 zip 副本 | `/storage/emulated/0/111/Heap1024_v1.0.zip` | 1896 B | 同上（`cmp` 字节一致） |
| 安装说明 | `/storage/emulated/0/111/Heap1024_安装说明.txt` | 3284 B | UTF-8（`file -bi` = `text/plain; charset=utf-8`，`iconv` 通过） |

工作区源文件：`$WS/KSU_Heap1024/{module.prop, post-fs-data.sh, uninstall.sh}`

## 2. 模块结构（KSU 规范，无 META-INF、无 system.prop）

```
Heap1024_v1.0.zip
├── module.prop        (190 B, 644)
├── post-fs-data.sh    (2573 B, 755)
└── uninstall.sh       (285 B, 755)
```

只做 `dalvik.vm.heapsize` 一项；**不设** `dalvik.vm.heapgrowthlimit`（那是普通 App 的堆增长上限，抬了会让所有 App 一起变胖）。

### module.prop

```
id=heap1024
name=Heap 1024 (dalvik.vm.heapsize)
version=v1.0
versionCode=1
author=AzusaBA
description=Raise dalvik.vm.heapsize to 1024m for largeHeap apps (Operit OOM fix). Reboot required.
```

`id` 仅含 `a-z0-9`，符合 KSU 要求。

### post-fs-data.sh（终态全文）

```sh
#!/system/bin/sh
# KernelSU module: heap1024
# Purpose: raise dalvik.vm.heapsize to 1024m at the post-fs-data stage,
#          i.e. before zygote/app_process forks, so the new value is inherited
#          by every app process from boot.
#
# Notes:
#  * KernelSU does NOT run update-binary and does NOT support system.prop overlay,
#    so the property must be written here with resetprop.
#  * dalvik.vm.heapgrowthlimit is intentionally left untouched (that is the
#    per-app growth limit; raising it would inflate memory of *all* apps).
#  * No `set -e`: a failure in this script must never abort the boot stage.

MODDIR="${MODDIR:-/data/adb/modules/heap1024}"
LOGFILE="$MODDIR/boot.log"

PROP_NAME="dalvik.vm.heapsize"
PROP_VALUE="1024m"

# ------------------------------------------------------------------ helpers
log() {
    TS=$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null)
    [ -n "$TS" ] || TS="unknown-time"
    echo "[$TS] $*" >> "$LOGFILE" 2>/dev/null
    echo "[$TS] $*"
}

# Keep boot.log bounded across many reboots.
if [ -f "$LOGFILE" ]; then
    LINES=$(wc -l < "$LOGFILE" 2>/dev/null | tr -d ' ')
    case "$LINES" in
        ''|*[!0-9]*) LINES=0 ;;
    esac
    if [ "$LINES" -gt 200 ]; then
        tail -n 100 "$LOGFILE" > "$LOGFILE.tmp" 2>/dev/null && mv -f "$LOGFILE.tmp" "$LOGFILE" 2>/dev/null
    fi
fi

log "===== heap1024: post-fs-data begin ====="
PROP_BEFORE=$(getprop "$PROP_NAME" 2>/dev/null)
log "before: ${PROP_NAME}=${PROP_BEFORE}"

# ------------------------------------------------------- locate resetprop
RESETPROP=""
if command -v resetprop >/dev/null 2>&1; then
    RESETPROP="$(command -v resetprop)"
elif [ -x /data/adb/ksu/bin/resetprop ]; then
    RESETPROP="/data/adb/ksu/bin/resetprop"
elif [ -x /data/adb/magisk/resetprop ]; then
    RESETPROP="/data/adb/magisk/resetprop"
fi

if [ -z "$RESETPROP" ]; then
    log "ERROR: resetprop not found (PATH, /data/adb/ksu/bin, /data/adb/magisk); ${PROP_NAME} left unchanged"
    log "===== heap1024: post-fs-data end (skipped) ====="
    exit 0
fi

log "resetprop: $RESETPROP"

# ------------------------------------------------------------------- apply
# The "m" suffix is mandatory: a bare number is parsed as bytes.
"$RESETPROP" "$PROP_NAME" "$PROP_VALUE" >> "$LOGFILE" 2>&1
RC=$?

if [ "$RC" -eq 0 ]; then
    log "OK: ${PROP_NAME}=${PROP_VALUE} (resetprop exit 0)"
else
    log "FAIL: '${RESETPROP} ${PROP_NAME} ${PROP_VALUE}' exit=${RC}"
fi

PROP_AFTER=$(getprop "$PROP_NAME" 2>/dev/null)
log "after: ${PROP_NAME}=${PROP_AFTER}"
log "===== heap1024: post-fs-data end ====="

exit 0
```

健壮性要点：
- 三级探测 `resetprop`：`command -v` → `/data/adb/ksu/bin/resetprop` → `/data/adb/magisk/resetprop`；全部失败时**只记日志并 `exit 0`**，绝不阻断开机。
- 全程 `>>` 写 `$MODDIR/boot.log`（同时回显 stdout，进 KSU 自己的日志），日志超 200 行自动截到最近 100 行。
- 无 `set -e`；所有变量引用加引号；`MODDIR` 用 `${MODDIR:-...}` 兜底。
- 写入值常量 `PROP_VALUE="1024m"`（**带 m 后缀**）。

### uninstall.sh

```sh
#!/system/bin/sh
# heap1024 removed: dalvik.vm.heapsize only takes effect at post-fs-data (before
# zygote), so it cannot be restored at runtime -- reboot to get the ROM default back.
echo "heap1024 uninstalled. dalvik.vm.heapsize falls back to the ROM default after the next reboot."
```

## 3. 过程中发现并修复的真实缺陷（引号奇数）

首版 `sh -n` 报：

```
post-fs-data.sh: 73: Syntax error: Unterminated quoted string
```

用 `head -n` 二分定位到第 22 行，`od -c` 取原始字节后发现该行单引号有 **3 个**（奇数）：

```
echo "[$(date '+%Y-%m-%d %H:%M:%S'2>/dev/null || echo unknown-time')] $*" >> "$LOGFILE" 2>/dev/null
#                             ↑ 已闭合          ↑ 多余的一个 '  ← 根因
```

即：`%S'` 已经把格式串闭合，`unknown-time` 后面那个 `'` 是孤立的开引号，导致一直读到 EOF 都未闭合。
不是 dash 的嵌套限制（单独用 `$(date '+%Y')` 嵌套在 `"..."` 里可正常解析，已用最小用例验证 `T1 OK`）。

修复方式：把时间戳先算到变量、去掉 `"$()"` 嵌套，同时把两处 `"$(getprop ...)"` 也拆成先赋值再拼接，降低解析风险：

```sh
log() {
    TS=$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null)
    [ -n "$TS" ] || TS="unknown-time"
    ...
}
PROP_BEFORE=$(getprop "$PROP_NAME" 2>/dev/null)
PROP_AFTER=$(getprop "$PROP_NAME" 2>/dev/null)
```

## 4. 验证记录（命令 + 实测输出）

### 4.1 语法校验

```
$ sh -n post-fs-data.sh && echo 'SYNTAX_OK: post-fs-data.sh'
SYNTAX_OK: post-fs-data.sh
$ sh -n uninstall.sh && echo 'SYNTAX_OK: uninstall.sh'
SYNTAX_OK: uninstall.sh
```

### 4.2 功能测试（Ubuntu 沙箱 + stub resetprop，**完全不碰真机**）

A) 有 resetprop（stub 打印收到的两个参数）：

```
[2026-11-11 09:11:44] ===== heap1024: post-fs-data begin =====
[2026-11-11 09:11:44] before: dalvik.vm.heapsize=
[2026-11-11 09:11:44] resetprop: /tmp/hm/stub/resetprop
[2026-11-11 09:11:44] OK: dalvik.vm.heapsize=1024m (resetprop exit 0)
[2026-11-11 09:11:44] after: dalvik.vm.heapsize=
[2026-11-11 09:11:44] ===== heap1024: post-fs-data end =====
EXIT=0
--- boot.log ---
stub-resetprop arg1=dalvik.vm.heapsize arg2=1024m      ← 参数正确，值带 m 后缀
```

B) 无 resetprop（回退分支）：

```
[..] ERROR: resetprop not found (PATH, /data/adb/ksu/bin, /data/adb/magisk); dalvik.vm.heapsize left unchanged
[..] ===== heap1024: post-fs-data end (skipped) =====
EXIT=0                                                ← 不阻断开机
```

C) 日志轮转（预置 250 行旧日志后跑一次）：

```
$ wc -l /tmp/hm/mod3/boot.log
107 /tmp/hm/mod3/boot.log                             ← 已截到 100 行 + 本轮 6 行
```

（`before/after` 为空是因为 Ubuntu 里没有 `getprop`，属预期；真机上会打印 512m / 1024m。）

### 4.3 打包

```
$ cd $WS/KSU_Heap1024 && zip -r9 $WS/Heap1024_v1.0.zip module.prop post-fs-data.sh uninstall.sh
  adding: module.prop
 (deflated 26%)
  adding: post-fs-data.sh
 (deflated 58%)
  adding: uninstall.sh
 (deflated 34%)
```

### 4.4 zip 结构 / 完整性

```
$ unzip -l Heap1024_v1.0.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
      190  2026-11-11 09:10   module.prop
     2573  2026-11-11 09:11   post-fs-data.sh
      285  2026-11-11 09:10   uninstall.sh
---------                     -------
     3048                     3 files

$ unzip -t Heap1024_v1.0.zip
    testing: module.prop              OK
    testing: post-fs-data.sh          OK
    testing: uninstall.sh             OK
No errors detected in compressed data.

$ unzip -Z1 Heap1024_v1.0.zip | grep '/' || echo 'NO_SLASH: 全部在根目录'
NO_SLASH: 全部在根目录                     ← module.prop 在 zip 根，无多套目录

$ unzip -p Heap1024_v1.0.zip module.prop     ← 内容完整未损坏
id=heap1024 ... Reboot required.

$ unzip -p Heap1024_v1.0.zip post-fs-data.sh > /tmp/from_zip.sh && sh -n /tmp/from_zip.sh
ZIP_CONTENT_SYNTAX_OK                     ← 包内脚本再校验一次
```

### 4.5 交付副本一致性

```
$ sha256sum $WS/Heap1024_v1.0.zip /storage/emulated/0/111/Heap1024_v1.0.zip
eefcba66663d4c7ef3d91b79e3dc7c3397d4eb7bc57c998df4cf4058c7e24ced  .../Heap1024_v1.0.zip
eefcba66663d4c7ef3d91b79e3dc7c3397d4eb7bc57c998df4cf4058c7e24ced  /storage/emulated/0/111/Heap1024_v1.0.zip
$ cmp $WS/Heap1024_v1.0.zip /storage/emulated/0/111/Heap1024_v1.0.zip
CMP_IDENTICAL
$ ls -l /storage/emulated/0/111/Heap1024_v1.0.zip /storage/emulated/0/111/Heap1024_安装说明.txt
-rw-rw---- 1 u0_a306 media_rw 1896 2026-11-11 17:12 .../Heap1024_v1.0.zip
-rw-rw---- 1 u0_a306 media_rw 3284 2026-11-11 17:12 .../Heap1024_安装说明.txt
$ file -bi .../Heap1024_安装说明.txt ; iconv -f UTF-8 -t UTF-8 ... >/dev/null
text/plain; charset=utf-8
UTF8_OK
$ unzip -t /storage/emulated/0/111/Heap1024_v1.0.zip      → No errors detected
```

### 4.6 「1024m」写法核对

`PROP_VALUE="1024m"` 是脚本里唯一传入 resetprop 的取值；4.2-A 的 stub 实测收到 `arg2=1024m`，说明实际调用的是 `resetprop dalvik.vm.heapsize 1024m`，不是裸 `1024`。

### 4.7 未越界核查（交付后复核）

```
$ getprop dalvik.vm.heapsize        → 512m     （与交付前一致）
$ getprop dalvik.vm.heapgrowthlimit → 256m     （与交付前一致）
$ ls /data/adb/modules
YH_YC fgetpriority ih8SecureLock magisk-brick-guardian oh_my_keymint
reqable-magisk zygisk-module-xfingerprint-pay-all zygisk_lsposed zygisksu
$ ls -d /data/adb/modules/heap1024 → NOT_INSTALLED_OK
```

全程**没有**执行 `resetprop` / `setprop`（真机上只跑了 `getprop` 读取）、没有安装模块、没有重启、没有动 `/data/adb/modules` 下任何现有模块、没有改 `/system` 或 `/vendor`。
功能测试全部在 Ubuntu 的 `/tmp/hm/` 沙箱里用 stub 完成。

## 5. 安装 / 验证 / 卸载

**安装**：KSU 管理器 → 模块 → 从本地安装 → 选 `/storage/emulated/0/111/Heap1024_v1.0.zip` → **重启**（属性只在 post-fs-data / zygote 之前生效）。

**验证**（重启后）：

```sh
getprop dalvik.vm.heapsize          # 期望：1024m
cat /data/adb/modules/heap1024/boot.log
# 期望含：before: dalvik.vm.heapsize=512m
#         resetprop: /data/adb/ksu/bin/resetprop
#         OK: dalvik.vm.heapsize=1024m (resetprop exit 0)
#         after: dalvik.vm.heapsize=1024m
```

如果只有 `ERROR: resetprop not found`，说明环境里没有 resetprop，属性未被修改（脚本已安全退出）。

**卸载**：KSU 管理器 → 模块 → heap1024 → 停用/删除 → **重启**（运行时无法回滚，只能靠下次开机回到 512m）。

## 6. 风险与注意

1. 单 App Java 堆上限变 1GB，系统内存压力上升，LMK 会更积极杀后台（后台保活变差）。
2. 值必须带 `m`；写成裸 `1024` 会被当 1024 字节，zygote 起不来 → 开不了机。模块里写死 `1024m`。
3. 只对 Java 堆有效。若 OOM 发生在 native 分配（Bitmap/native heap），改这个没用——本模块不解决那一类。
4. 未改 `heapgrowthlimit`：普通 App 仍按 256m 增长，只有声明 `largeHeap` 的 App 才能吃到 1024m 上限。
5. 需用户自行在测试机安装验证；构建机未安装、未重启。

---

## 7. v1.5 追加验证：防变砖限制（512m~2048m）与 doSave 三情况（2026-11-11）

> §1–§6 是 v1.0 的交付记录；本节是 **v1.5 的只读验证**记录（未改任何源码、未重打 zip、未动 `/storage/emulated/0/111/`）。

### 7.1 交付物一致性（先证「验的就是要发的东西」）

| 项 | 值 |
|---|---|
| zip | `$WS/Heap1024_v1.5.zip`，14005 B |
| SHA-256 | `a904b8c0eecec219d3267fcb5020c98097c27f08e174c98b2278ad8a8a5654a3`（与 lead 给的 `a904b8c0` 前缀一致） |
| module.prop | `version=v1.5` / `versionCode=6` |

zip 内文件与工作区源文件逐字节一致（`unzip -p <zip> <f> | sha256sum` vs `sha256sum <src>`）：

```
SAME module.prop            daf103b129a2e72e444b8f2eea613f35275c02fa4f50a5d52666fed88a9ca964
SAME post-fs-data.sh        a4a00d531baed8b97e1a3207affc0968b6f187fd7eb338daaa2be9724bd115f5
SAME webroot/index.html     43bc7a33162bfa4ef52fdae204cfeef6c8ee82e99376f422887e095dfbf8db85
```

zip 权限（`unzip -Z`）：`post-fs-data.sh` / `uninstall.sh` = `-rwxr-xr-x`，`module.prop` / `webroot/index.html` = `-rw-r--r--`；5 个条目全部在 zip 根（`webroot/` 一层目录，无多套目录嵌套）。

### 7.2 开机脚本 is_safe_size 判定（六值 + 边界）

方法：从 `KSU_Heap1024/post-fs-data.sh` 第 39–60 行**原样抽取** `is_valid_size` 与 `is_safe_size`（不执行脚本其余部分：不调用 resetprop、不写文件、不读 /data/adb），用三个运行时跑同一套用例。

| 取值 | `is_valid_size`（`^[0-9]{3,5}m$`） | `is_safe_size`（512..2048） | 结论 |
|---|---|---|---|
| `4096m` | 0（格式通过） | 1 | **拒绝**（> 2048） |
| `1024m` | 0 | 0 | 通过 |
| `abc` | 1 | 1 | 拒绝（格式） |
| `512m` | 0 | 0 | 通过（下界） |
| `2048m` | 0 | 0 | 通过（上界） |
| `2049m` | 0 | 1 | **拒绝**（超上界 1m） |

补充边界：`511m` → 拒绝、`0512m` → 通过、`768m` → 通过、`0m` → 拒绝、`99999m` → 拒绝、`1024`（无 m 后缀）→ 拒绝、空串 → 拒绝。

运行时一致性（三份输出逐行相同）：

```
dash (/usr/bin/dash)   ：上表 + 全部边界一致
bash --posix           ：上表 + 全部边界一致
设备 /system/bin/sh    ：SHELL_TAG=@(#)MIRBSD KSH R59 2020/10/31 Android → 上表 + 全部边界一致
```

语法：`dash -n post-fs-data.sh`、`bash -n post-fs-data.sh` 均 `SYNTAX_OK`。

**结论**：即使有人手改 `heapsize.txt` 为 `4096m`，post-fs-data.sh 的 `is_valid_size && is_safe_size` 也会拒绝并回落到默认 `1024m`（脚本 111 行 WARN 分支），不会把 zygote 写死成开机循环。

### 7.3 WebUI doSave 三情况（node 函数级自测）

方法：把 index.html `<script>` 里的 IIFE **原样抽出** → 把末尾 `boot();` 替换成 `window.__t={doSave:doSave,state:state};`（**不改源文件**）→ vm 沙箱 + 假 DOM（`getElementById` / `createElement` / `classList` / `parentNode` 桩）+ 假桥 `window.ksu`；20s 定时器收集后由测试主动触发（否则测不到 TIMEOUT 分支）。
runner（工作区留档）：`$WS/.tmp_heap1024/harness/v15-verify-lead/v15_dosave.mjs`。

| # | 假桥返回 | 实测 toast（原文） | toast class | state.cfgHeap | 判定 |
|---|---|---|---|---|---|
| 1 | `{errno:0, stdout:'', stderr:''}` | `已保存，重启后生效` | `toast show ok` | `1024m` | **PASS**（「读回空」不再误报失败） |
| 2 | 永不回调 → 20s TIMEOUT | `保存失败：写入失败（errno=0 / TIMEOUT）` | `toast show err` | 未改 | **PASS** |
| 3 | `{errno:13, stdout:'', stderr:'Permission denied'}` | `保存失败：写入失败（errno=13 / Permission denied）` | `toast show err` | 未改 | **PASS** |

`SUMMARY 12/12 ALL_PASS`（3 情况 × 主/辅断言 + 六值 6 条）。

说明：case2 里 `execCalls=2` 是 `sh()` 的兼容设计——同步返回值拿不到时，再按老的 `ksu.exec(cmd, cb)` 形态派发一次（命令都是 `mkdir/printf/rm` 幂等操作），不是重复写文件；最终仍走 20s 超时分支。

### 7.4 WebUI 侧 512~2048 硬限（doSave 内联 gate）

同一 runner 把 `state.heap` 直接置成六值后调 `doSave()`：

| 取值 | 拦截位置 | toast（原文） | exec 被调用 |
|---|---|---|---|
| `4096m` | doSave 853–858 硬限 | `堆上限必须在 512m ~ 2048m 之间（更大会让 zygote 启不来，直接开机循环）` | 0 |
| `1024m` | — | `已保存，重启后生效` | 1 |
| `abc` | syncFromInputs 831 行 SIZE_RE | `堆大小必须是 3–5 位数字 + m` | 0 |
| `512m` | — | `已保存，重启后生效` | 1 |
| `2048m` | — | `已保存，重启后生效` | 1 |
| `2049m` | doSave 853–858 硬限 | 同 `4096m` 文案 | 0 |

（`abc` 先被 3–5 位数字格式校验拦下，走不到区间 gate，属预期顺序，不是漏拦。）

### 7.5 结论

- **双端一致**：WebUI 与开机脚本都拒绝 `4096m` / `2049m`，都接受 `512m` / `1024m` / `2048m`；WebUI 是「提示 + 不写文件」，开机脚本是最后一道闸（配置文件被手改也回落 1024m）。
- 保存链路三种真实返回形态（拿不到 stdout / 超时 / EACCES）的文案与状态全部符合预期，v1.3 的「读回空误报失败」回归点没有回退。
- 本次全程只读：验证前后 `index.html` md5 `c5da863290751cd413a1205d0e9bb231`、`post-fs-data.sh` md5 `7e3aaf1702b71a044b6a59e165d36c7b`、`Heap1024_v1.5.zip` md5 `86c0ef039311d3b19df9721dd73c0b08` 均未变；未改 `/storage/emulated/0/111/` 任何文件；未安装模块、未重启、未执行 resetprop。
