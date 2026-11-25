# 蔚蓝档案（国服）私服改造 — **完整版归档** 2026-11-13

> 本包内所有文件都是**副本（硬链接拷贝）**，原目录文件未被修改、未被移动。
> 这是「完整版」：连解包出来的 APK 目录、原厂/已改的 so 一起打包。

## 包内结构
```
ba/
├── README_归档说明.md        ← 本文件
├── audit/                    ← 全部审计文档 + 证据 + 解包产物
│   ├── ba-pitfalls.md        ★ 踩坑总账（§4.9 注入触发点 / §4.10 GOT 实测值 / §4.11 adr 全局符号取 0）
│   ├── anticheat-full.md  anti-detection.md  ba-hook-survey.md  ba-java.md
│   ├── AzusaBA-bug-report.md  fix-java.md  ksu-heap-module.md  ba-pentest.md  api-probe.md …
│   ├── _parts/  cfgtest/  orig_backup/     ← 小体积证据与配置备份
│   ├── ba-apk/                             ← 解包出来的 APK 目录（约 410 MB）
│   └── ba-work/                            ← 解包工作目录（约 345 MB，含 lib/arm64-v8a）
├── bapatch/                  ← 全部脚本与中间产物（约 630 MB）
│   ├── libil2cpp.bin         ← 原厂 libil2cpp.so（270,927,056 B）
│   ├── libil2cpp_patched.bin ← 已注入版（同上大小）
│   ├── libunity.bin          ← 原厂 libunity.so（20,950,552 B）
│   ├── cave/                 ← 注入桩汇编源码 .S 与历史 .o
│   ├── sdk_resp/             ← 伪造的 SDK 响应模板
│   ├── patch_init5.py  patch_min2.py  patch_ga.py  patch_hit2.py  patch_dl.py   ← 注入主线
│   ├── patch_got*.py  patch_maps*.py  patch_reloc*.py  patch_verify*.py          ← 已证伪，留作对照
│   ├── mkstub.py  elf_*.py  got_scan.py  find_host.py  parse_excel.py            ← 工具
│   ├── sdkcard.py  relay8080.py  tlsproxy.py  connectproxy.py  cdnproxy.py       ← 服务
│   ├── cards.json            ← 卡密库（11111111111 绑定设备 09a4d0ab0ee93616）
│   └── *.log / *.out         ← 运行日志
└── 服务器侧脚本
    ba_mitm.conf（443 SNI 分流）  add_sdk_loc.py（插入 /sdk/ 反代）
    deploy.sh  deploy2.sh  deploy3.sh  patch_nginx.sh  patch_nginx2.sh  run_srv.sh
```

## 关键实测结论（详见 audit/ba-pitfalls.md）
- **ACE 判定**：`exit-info reason=2 status=7`（SIGBUS）才是 ACE；`9`=系统回收，`11`=原生崩溃。判定会持久化（`ace_shell_di.dat`、`shell_cache`），需删除复位。
- **可改/不可改**：`libil2cpp` 可改（代码洞、`DT_INIT`、运行时写 `libunity` GOT 都活）；`libunity` / `libmain` / 新增 so / 新增或重编 dex 一律死或卡启动。
- **正确 GOT 偏移**：`connect = 0x13d95d8`、`getaddrinfo = 0x13d94d0`。旧值 `0x13d94d8` 实际是 libc 的 **`basename`**——这是此前所有注入崩溃的根因。
- **设备侧 `iptables` NAT（DNAT）在本机不生效**（做过对照实验），不能靠路由劫持。
- **系统证书方案需要 root**，与「单 APK、零 root」交付要求冲突，已否决。
- **注入链路的两个致命细节**：`adr` 指向 `.globl` 符号在未链接的 `.o` 里会取到 0（必须用局部标签 `Lb0`）；桩内 `blr` 会踩掉 `LR`（尾调用前必须保存 `x29/x30`）。

## 当前进度
- 服务器侧：Shittim 服务端、宝塔面板反代、443 SNI 分流、云端卡密 SDK（pm2 `ba_sdk`）均已完成；**进程已按要求停掉**，仅保留面板 nginx 配置。
- 客户端侧：注入链路已稳定（校正偏移后的钩子可跑且不触发 ACE），剩下「把网关请求导到我们服务器」最后一步未打通。
- **尚未达到「进大厅」的交付标准**。
