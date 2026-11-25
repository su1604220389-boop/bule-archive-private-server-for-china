# account_state 备份说明（2026-11-17 20:38:24 +0800）

## 这份备份是什么
把「删了就永久丢」的那一小块落盘（11.1 GB 资源备份 `BA_backup` 是另一份，不在这里）。

## 文件
| 文件 | 大小 | 说明 |
|---|---|---|
| `account_state_20261117_203809.tar` | **9,956,864 B (9.50 MiB)** | 主备份（tar，`-p` 保留权限与属主） |
| `account_state_20261117_203809.tar.sha256` | 116 B | tar 的 sha256 |
| `account_state_20261117_203809.files.sha256` | 51,913 B | **326 条**逐文件 sha256（原始绝对路径） |

## 校验
```
tar sha256 : b606f67092f21c7feb7ae0ea67b18f4de1fb3ef88a8f1f614ed26fbfdaaca703
手机侧与 PC 侧一致（adb pull 后 Get-FileHash 复核通过）
```

## 捕获元信息
```
捕获时间   : 2026-11-17 20:38:24 +0800
游戏状态   : **未运行**（pidof com.RoamingStar.BlueArchive = 空）
base.apk   : sha256 dd30a285b58508252df09a503b025850a27a73c89f1162454bee55a60d7f83bb
             （原厂官方包 3.0.2 / versionCode 73）
8080 服务  : 未运行（本轮未启动）
```

## tar 内容（390 个条目）
```
data/data/com.RoamingStar.BlueArchive/                                308 条（目录+文件）
data/media/0/Android/data/com.RoamingStar.BlueArchive/files/ClientSaveData/   82 条
```
**重点文件**：
```
data/data/com.RoamingStar.BlueArchive/shared_prefs/AUTH_APP_INFO.xml   2,299 B  ← 登录态
data/data/com.RoamingStar.BlueArchive/shared_prefs/AUTH_UT_DATA.xml    1,895 B
data/data/com.RoamingStar.BlueArchive/shared_prefs/*.xml               9 个
data/data/com.RoamingStar.BlueArchive/no_backup/ace_shell_di.dat          22 B  ← ACE 记账
data/data/com.RoamingStar.BlueArchive/databases/                       95.5 K
data/media/0/Android/data/…/files/ClientSaveData/*.save                52 个（含 10015354380* 24 个）
```

## 属主（重要）
```
tar 内 **390/390 条全部是 u0_a577（uid 10577 / gid 10577）**，**root 行数 = 0**
```
⚠️ **注意：不是 10489。** 10489 是 Operit（PRoot）的 uid；游戏包 `com.RoamingStar.BlueArchive`
在本机是 **uid 10577 (u0_a577)**。恢复时必须按目标安装后的实际 uid 决定 chown 值：
```bash
# 查目标包实际 uid
adb shell dumpsys package com.RoamingStar.BlueArchive | grep -m1 userId=
# 恢复（示例：包名不变、uid 仍为 10577）
adb shell su -c 'tar -xpf /data/local/tmp/account_state_20261117_203809.tar -C /'
adb shell su -c 'chown -R 10577:10577 /data/data/com.RoamingStar.BlueArchive'
adb shell su -c 'chown -R 10577:1077 /data/media/0/Android/data/com.RoamingStar.BlueArchive/files/ClientSaveData'
```
（`tar -xpf -C /` 是因为 tar 内是相对路径 `data/data/...` 与 `data/media/0/...`，解到根即可还原原位）

## 恢复步骤（完整）
```bash
# 1) 把 tar 推回手机
adb push account_state_20261117_203809.tar /data/local/tmp/
# 2) 校验
adb shell su -c 'sha256sum /data/local/tmp/account_state_20261117_203809.tar'
#    期望 b606f67092f21c7feb7ae0ea67b18f4de1fb3ef88a8f1f614ed26fbfdaaca703
# 3) 解包
adb shell su -c 'tar -xpf /data/local/tmp/account_state_20261117_203809.tar -C /'
# 4) 按目标包实际 uid 改属主（见上）
```

## 边界
```
✅ 只读打包：tar -cpf 直接读原文件，未修改、未删除任何东西
❌ 没有卸载、没有安装、没有启动 8080
```
