# 第二台测试机 装机前状态（20261118_0004）

> phone-ops ｜ 2026-11-18 00:04:22 (+08:00)
> serial = 192.168.0.6:42933

## 1) 三条只读确认（装机前基线）

### 1.1 base.apk 大小
```
pm path -> /data/app/~~IeV_8eix2r5HmKlKMmWBhA==/com.RoamingStar.BlueArchive-whJlwGJtqImFNdMzoWfE3A==/base.apk
ls -l   -> -rw-r--r-- 1 system system 2126400085 2026-11-11 00:55 .../base.apk
wc -c   -> 2126400085
```
对照：官方原包 cn_base.apk = 2,126,400,085 B（一致）；免root样本 v2 = 2,127,962,985 B（差 1,562,900）
**=> 装的是官方原包。**

### 1.2 装机签名
```
signatures=PackageSignatures{3174ce1 version:3, signatures:[46a91e98], past signatures:[]}
oplusSignaturesInfoPlus=[com.RoamingStar.BlueArchive] Fingerprint:20E318B91BCF6BD2484CDA05C011E915D2496F8FC6E8A6FAA27499D3C1CAB4CE SignatureAlgorithm:SHA1withRSA
```
我们的证书 work\ba\noroot\ba_private.cert.pem（1,126 B）：
```
sha256 Fingerprint = 94:FA:99:7B:E0:DE:BB:69:F1:C6:2D:76:66:64:FA:8A:87:98:39:DC:9F:71:0F:6E:EB:D0:C4:13:DE:E9:9E:BC
subject = C=CN, O=BA, OU=Private, CN=ba（自签）
```
**=> 两者不同 => 官方签名 => 同包名安装我们的包必须先 uninstall。**

### 1.3 外部数据目录
```
du -sh -> 4.6G
files/ 内容（15 项）：2071278565329732703, AssetBundles/, DeviceOption, GlobalConfig.json,
  LocalConfig.json, LocalizeConfig.txt, MediaPatch/, Patch/, PopupMessageWatchedOnce,
  TableBundles/, catalog_Remote.hash, catalog_Remote.json(81,410,263), catalog_Remote.zip(12,282,671),
  il2cpp/, manifest.db(6,639,616)
★ 没有 ClientSaveData 目录 => 该机无本地存档
```

## 2) 搬移尝试（失败，已放弃）

### 2.1 原始报错
```
mv: /sdcard/_ba_noroot_bak/files/il2cpp/Metadata/global-metadata.dat: Permission denied
mv: /sdcard/_ba_noroot_bak/files/il2cpp/Metadata: Permission denied
mv: /sdcard/_ba_noroot_bak/files/il2cpp/Resources/Antlr3.Runtime.dll-resources.dat: Permission denied
mv: /sdcard/_ba_noroot_bak/files/il2cpp/Resources/System.Data.dll-resources.dat: Permission denied
[exit code: 1]
```
原因：`files/il2cpp` 权限 `drwxr-s---`（组外无 rx），无 root 的 shell 无法读取/删除。

### 2.2 清理（一次尝试，成功）
```
rm -rf /sdcard/_ba_noroot_bak   -> RM_EXIT=0
ls /sdcard | grep _ba_noroot_bak -> NOT_FOUND
```

### 2.3 原目录复核（未被破坏）
```
du -sh -> 4.6G
ls files -> 2071278565329732703 AssetBundles DeviceOption GlobalConfig.json LocalConfig.json
            LocalizeConfig.txt MediaPatch Patch PopupMessageWatchedOnce TableBundles
            catalog_Remote.hash catalog_Remote.json catalog_Remote.zip il2cpp manifest.db
```

## 3) 机型指纹
```
ro.build.fingerprint = OnePlus/PYB110/OP64E1L1:17/CP2A.260605.016/C.3601857-f47121-f4775e:user/release-keys
ro.product.name       = PYB110
```

## 4) 装机前结论
```
- 官方包 + 官方签名 + 无本地存档 + 4.6 G 可重下资源
- /data 583 G 可用，空间不是问题
- 用户已批准卸载重装（接受 4.6 G 重下）
- 已放弃一切"保数据"手段（不 cp / 不 tar / 不 split / 不 mv 第二遍）
```

## 5) 装机流程（APK 到位后执行）
```
1. Get-FileHash 校验 sha256（不一致即停）
2. adb -s 192.168.0.6:42933 uninstall com.RoamingStar.BlueArchive
3. adb -s 192.168.0.6:42933 install -r "<APK>"      <- 不中途 Ctrl-C
4. adb -s ... shell "dumpsys package com.RoamingStar.BlueArchive | grep -E 'versionName|versionCode|lastUpdateTime'"
5. 回报，等用户自己点开游戏（不 am start、不点屏幕）
```
