# BA Prober Kit v1 —— 一次性验证包

> 2026-11-13 | 配套文档：`report/00-下一步总方案.md`
> **这不是 APK。** 我这边没有那份 2.1 GB 的原始 APK（归档里只有 7.9 MB 的 stripped `slim.apk`），所以没法给你打一个完整可装的包。
> 但你需要验证的三件事，**两件完全不用改包，一件只改 4 个字节**——都在这份包里。

---

## 0. 包里有什么

```
BA_probe_kit_v1/
├─ README.md                  ← 本文件
├─ pc/
│  ├─ make_certs.ps1          ← 生成自签 CA + *.bluearchive-cn.com 叶子证书
│  ├─ state_gw.py             ← CONNECT 代理 + TLS 终止 + 假 /api/state（纯标准库）
│  └─ run.ps1                 ← 一键：证书→起服务→adb reverse→打印手机该填的地址
└─ phone/
   ├─ 00_collect.sh           ← 只读采集：包信息 / so 哈希 / Hosts 十六进制 / ACE 记账 / maps / logcat
   ├─ 01_fix_got_slot.sh      ← 4 字节补丁：把钩错的 gettimeofday 槽改回 getaddrinfo
   └─ 02_net_watch.sh         ← 纯观测：记录游戏连了哪些 IP:端口（不 hook、不改任何东西）
```

---

## 1. 先说结论：你那版钩错了函数（4 字节的事）

我把 `libil2cpp.bin` 和 `libil2cpp_patched.bin` 逐字节差分，只差 3 簇，其中洞内那 1112 字节里，写 GOT 的是这两条：

```
file 0xf2c2540 : d2929a09   movz  x9, #0x94d0
file 0xf2c2544 : f2a027a9   movk  x9, #0x13d, lsl #16      →  x9 = 0x13d94d0
file 0xf2c2550 : 8b0902a9   add   x9, x21, x9               （x21 = libunity base）
file 0xf2c2558 : f900012a   str   x10, [x9]                 ← 把桩地址写进 GOT
```

而 libunity 的实际槽位是：

| 偏移 | 真实符号 | 被你这版写入了 |
|---|---|---|
| `0x13d94d0` | **`gettimeofday`** | ← 写的就是这里（错） |
| `0x13d94d8` | **`getaddrinfo`** | 正确的目标 |
| `0x13d95d8` | `connect` | 没动 |

**所以现役补丁把游戏的取时间函数劫持成了 getaddrinfo**：timeval 不填、时间基准崩坏。
这极可能就是你记的 **E64「从被官方拒绝变成超时」** 的真正原因——不是链路变了，是时间函数被拆了。

修法只有 4 个字节：

```
0xf2c2540:  09 9a 92 d2   →   09 9b 92 d2      (movz x9,#0x94d0 → #0x94d8)
```

`phone/01_fix_got_slot.sh` 就是干这个的，带备份和回滚。

> ⚠️ 注意：修好之后这个桩**仍然只是"记录 + 调原函数"**，不会重定向（它的 `str x10,[x9]` 写的是自己的桩地址，桩里没有改 sockaddr 的代码）。**但它能把"客户端到底解析了哪些主机名"打出来**——那正是我们要的答案。

---

## 2. 三条线，按顺序做

### Track C（先做，5 分钟，零风险）：采集基线

手机上跑：

```sh
sh 00_collect.sh
```

产物在 `/sdcard/ba_collect_<时间戳>/`，把这个文件夹整个发给我。

**我要的东西里，最关键的是 `runtime_files.txt` 里的 `Hosts` 十六进制。**
原因：你现在 `Hosts` 实验失败，很可能只是**格式写错**（官方条目是带 scheme 的完整 URL `https://gsqc-api.bluearchive-cn.com:443`，你写的是裸 `127.0.0.1:9443`）。拿到真实字节，我就能生成一个格式完全一致的替换文件，让"飞行模式 + Hosts"这个实验真正成立。

同时它会告诉我：现在装的到底是原厂 so 还是打过补丁的那版、ACE 记账状态、`bainj.txt` 有没有内容。

---

### Track B（10 分钟，1 次 force-stop）：4 字节修复

```sh
sh 01_fix_got_slot.sh --check     # 先看状态，不动任何东西
sh 01_fix_got_slot.sh             # 再打（会自动 force-stop 游戏）
```

判定成功：脚本最后打印 `OK patched`，`readback : 099b92d2`。
回滚：`sh 01_fix_got_slot.sh --rollback`

然后：

1. 手动点图标启动游戏（别用 monkey，避免小窗被回收）
2. `sh 02_net_watch.sh 180` （或者先启动它再开游戏）
3. 等它停在「认证服务器拒绝了请求」或「网络异常」
4. 再跑一次 `sh 00_collect.sh`

**要发给我**：新的 `cave.txt`、`runtime_files.txt`（里面会有 `bainj.txt` 的内容）、`ba_net_*.log`。

这一轮能回答：客户端**到底解析了什么域名**、连的是哪个 IP、修好时间之后 E64 的"超时"是否消失。

---

### Track A（15 分钟，零改动）：假网关，直接看客户端拒不拒自签证书

PC 上：

```powershell
cd pc
.\run.ps1 -Mode logonly          # 第一遍：只记录 CONNECT 目标，立刻 502，不隧道、不吃带宽
```

然后手机 **Wi-Fi 代理** 填 `run.ps1` 打印出来的地址（有 adb 时是 `127.0.0.1:7890`，没有就是 `192.168.x.x:7890`）。
开游戏，看 PC 控制台。

- 如果看到 `CONNECT state-api.bluearchive-cn.com:443` → **代理链路通了，域名清单到手**
- 如果一条都没有 → 客户端没走系统代理，Track A 作废，回 Track B

> `logonly` 会让游戏立刻报「网络异常」——这是预期的，我们只要那行 CONNECT。
> 想让它正常跑通，用 `-Mode passthrough`（会把流量原样转给真服务器，**要求这台 PC 能上网**）。

看到域名之后，换成 TLS 模式再跑一遍：

```powershell
.\run.ps1 -Mode tls -Servers "http://127.0.0.1:5000/api/" -State 0
```

这一遍是**决定性实验（E4）**，只看控制台里出现哪一种：

| 控制台出现 | 含义 | 下一步 |
|---|---|---|
| `TLS-OK` + `REQUEST GET /api/state` | **客户端不校验证书**——路全通了 | 它接着会去连 `Servers` 里的地址，我们只要把 Shittim 起起来 |
| `TLS-REJECT ... client refused our cert` | 证书是硬墙 | 走 A4：`CustomCertificateHandler.ValidateCertificate` 补丁 |
| 完全没有反应 | 客户端没走代理 / 走了但直连 | 回 Track B |

`state_gw.py` 的假 `/api/state` 返回：

```json
{"Servers":["http://127.0.0.1:5000/api/"],
 "State":0,"Msg":"",
 "CallbackUrl":"","CustomerServiceUrl":"",
 "AddressablesCatalogUrlRoots":["https://static.bluearchive-cn.com/prodm39"]}
```

`Servers[0]` 用 `http://` 是故意的：`res/Dk.xml` 里 `cleartextTrafficPermitted=true`，只要这里是 http，**后面整条链路都是明文，TLS 就只剩 state 这一个请求要过**。`AddressablesCatalogUrlRoots` 指官方 CDN（无鉴权），资源不用重做。

---

## 3. 安全 / 回滚

| 动作 | 可回滚方式 |
|---|---|
| `01_fix_got_slot.sh` | `sh 01_fix_got_slot.sh --rollback`（备份在 `/sdcard/ba_slot_backup.bin`） |
| Wi-Fi 代理 | 手动改回「无」 |
| `00_collect.sh` / `02_net_watch.sh` | 只读，无副作用 |
| 自签证书 | PC 本地文件，删掉即可 |

**不会碰你的 APK、不会重打包、不会动 `res/`、不会删 `__tpinfo`、不会写 `/data/data`。**
唯一会写的是 libil2cpp.so 里那 4 个字节（Track B，可选）。

---

## 4. 如果三条线都失败

那就确认了：国服这个标的必须走 A4（托管层证书补丁）或 C1（换 Steam/国际服标的）。
**但无论哪条，Track C 的采集结果都是必须的**，因为：
- `Hosts` 的字节格式决定 E2 能不能成立
- `bainj.txt` 决定注入链是否真的在跑
- `maps.txt` 决定 libunity 的 `.got` 到底是 `r--p`（RELRO）还是 `rw-p`（你记的）——**这条直接决定 Track B 之后能不能写 GOT**

---

## 5. 附：为什么我判断这 4 个字节值得先修

**补丁本身我已经在 `libil2cpp_patched.bin` 的副本上跑过一遍（不是纸上推演）：**

```
[*] cave head  : f353b6a9        <- 确认是打过补丁的 g20 构建
[*] slot before: 099a92d2        <- movz x9,#0x94d0  (gettimeofday, 错)
[*] printf bytes:  09 9b 92 d2
[*] slot after : 099b92d2        <- movz x9,#0x94d8  (getaddrinfo, 对)
[*] context 24B:  10 02 11 cb 00 02 3f d6 09 9b 92 d2 a9 27 a0 f2 09 00 c0 f2 09 00 e0 f2
                  └─ blr x16 ─┘ └─ movz ─┘ └─ movk #0x13d ┘ └── movk 0,32 ──┘
                  => x9 = 0x13d94d8  ✓
```

| 证据 | 来源 |
|---|---|
| `libunity` 的 GOT 偏移三重验证：`.rela.plt` 符号表、`unity_full.asm` 里 PLT 的 `#0x4d0` vs `#0x4d8`、洞内 `movz/movk` 立即数 | `report/02-注入链审计.md` |
| `0x13d94d0` 在 libc 里是 `gettimeofday`，不是 README 说的 getaddrinfo | 同上 |
| libil2cpp 全段 346 万条 BL 里，跳 `getaddrinfo@plt`/`connect@plt` 的是 **0** 条 → 改 libil2cpp 的 PLT 从原理上就不可能生效 | 同上 |
| libunity 侧 `getaddrinfo` 1 个调用点、`connect` 3 个 + 1 处直读 GOT → 真正活的落点 | 同上 |
| 现役 `patched.bin` 就在 `0xf2c2540` 写 `0x13d94d0` | 本包实测差分 |
