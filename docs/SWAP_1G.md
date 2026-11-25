# 1 GB swap 添加任务 —— 前置检查结果：**已存在 1 GB swap，按红线停止，未做任何改动**

- 时间：2026-11-20 01:46（Asia/Shanghai）｜ 执行：srv-ops
- 任务：给磁盘加 1 GB swapfile
- **结果：前置检查发现系统已经有 1 GB swap（`/www/swap`），按「本来就有 swap ⇒ 停下回报，不要叠加」的红线，立即停止。**
- **本次零改动**：未创建任何文件、未改 `/etc/fstab`、未执行 `swapon`、未改 `vm.swappiness`、未装 zram、未重启任何服务

---

## 1. 现有 swap（决策依据）

```
$ free -h
               total        used        free      shared  buff/cache   available
Mem:           1.6Gi       847Mi        78Mi        94Mi       683Mi       503Mi
Swap:          **1.0Gi**      0B         1.0Gi

$ swapon --show
NAME      TYPE SIZE USED PRIO
**/www/swap  file   1G   0B   -2**

$ cat /proc/swaps
Filename				Type		Size		Used		Priority
**/www/swap**                           file		1049596		0		-2

$ grep -n -iE 'swap' /etc/fstab
**12:/www/swap    swap    swap    defaults    0 0**
```
⇒ **已有 1 GB swapfile `/www/swap`，且已写入 fstab（12 行）、已启用（PRIO -2）**。
若再加一个 `/swapfile` 会变成 2 GB 叠加 swap —— 违反红线，故**未执行**。

## 2. 其余前置检查（只读，均已采集）

| 检查项 | 实际值 | 是否满足 |
|---|---|---|
| 磁盘剩余 | `/dev/vda3  40G  25G  **13G**  66%  /` | ✅ ≥ 2 GB |
| inode | `2608144 total / 409061 used / 2199083 free / 16%` | ✅ 充足 |
| 根分区文件系统 | **ext4**（`/dev/vda3`） | ✅ 支持 fallocate |
| `vm.swappiness`（只记录） | **0** | — 未改动 |
| `/swapfile` 是否存在 | **不存在**（`ls: cannot access '/swapfile'`） | — 未创建 |
| zram | `lsmod | grep zram` → **无 zram 模块**；`systemd-zram-setup@zram0.service` → **Unit could not be found** | ✅ 确实没有 zram（本任务也不会加） |
| 服务状态 | `ba-shittim ba-bridge nginx php-fpm-82 mysqld` → **全部 active** | ✅ 未受影响 |

## 3. 值得你注意的两个事实（只陈述，未改动）

1. **swap 早就有，但 `vm.swappiness = 0`。**
   swappiness=0 表示内核**极力避免**把匿名页换出（只有在"内存+swap 都快满"的极端情况下才会用 swap）。
   这与今天凌晨"内存耗尽"的现象是相容的：**有 1 GB swap 却几乎不会被用上**，压力直接落到物理内存 → 触发 OOM/整机异常。
   > 你明确要求**不动 swappiness**，所以我只记录、未改。若后续想真正让 swap 起缓冲作用，需要另行授权调整（典型值 10–60）。

2. **已有 swap 的位置是 `/www/swap`（不是 `/swapfile`）**，且写在 `/etc/fstab:12`。
   如果将来要"加到 2 GB"，正确做法是把 `/www/swap` 扩到 2 GB（或替换），而不是新增一个 `/swapfile` 与它并存——否则两条 swap 会同时生效、优先级都为默认，行为不直观。

## 4. 本次未做的事（逐条确认）

- ❌ 未 `fallocate`/`dd` 创建 `/swapfile`
- ❌ 未 `mkswap` / `swapon`
- ❌ 未修改 `/etc/fstab`（**没有任何备份/追加**，因为不需要）
- ❌ 未改 `vm.swappiness`（现值仍是 0）
- ❌ 未安装/未修改 zram
- ❌ 未重启任何服务、未重启机器
- ✅ 未创建 `/root/SWAP1G_*` 目录（因为未进入执行阶段）

## 5. 结论

**任务未执行，原因是"已有 swap"，属红线要求停止的情形。**
当前状态：`swap 1.0 GiB（/www/swap，已启用，fstab 已配置，用量 0B）`，`swappiness = 0`，无 zram，服务全部 active。

如果你确认仍然希望**把 swap 从 1 GB 扩到 2 GB**，请明确授权，我再按「备份 fstab → 关闭并移除 /www/swap → 新建 2 GB → 验证 → 回滚脚本」的流程执行；
如果你其实想要的是**让 swap 真正被用上**，那是 `vm.swappiness` 的调整（你当前红线禁止），需要单独授权。

---
**本次仅执行只读检查命令；未产生任何写操作。**
