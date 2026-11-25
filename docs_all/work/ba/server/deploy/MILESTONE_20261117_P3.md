# 里程碑：协议 3 打通，客户端成功进入游戏

记录时间：2026-11-17 01:2x。作者：Lead。

## 结果

**Blue Archive 国服 3.0.2 (vc73) 客户端 —— 用我们自己的服务端 —— 成功越过登录、进入游戏、到达新手教程。**

这是本项目第一次越过协议 3。

## 完整登录链（客户端实际发出的请求）

```
1002  api/account/auth        req 1,138 → 200 / 3,520    gen_kind=-
24000 api/academy/getinfo     req   882 → 200 / 1,772    gen_kind=academy-24000-v3
1017  api/account/loginsync   req 1,138 → 200 / 122,968  gen_kind=loginsync-1017-dynamic
4000  api/item/list           req   882 → 200 / 640      gen_kind=simple-4000
  3   api/networktime/sync    req   882 → 200 / **620**  gen_kind=networktime-3   ← 本次打通
之后客户端继续推进 → 进入游戏 → 新手教程
```

## 卡了 17 小时的根因

**协议 3 的两个 tick 必须是真值，且 `ReceiveTick == EchoSendTick`。**

此前协议 3 一直走「通用空构造」(`min+base`)，返回 536 B，两个 tick 缺失。客户端因此算不出正确的时钟偏移 —— 它不会报错，只是**静默停住**。日志显示 00:58:37 之后零新请求，持续 17 小时都表现为"200 但客户端不动"。

> 注意：这是**静默失败**，不是错误码。HTTP 200、解密成功、JSON 合法、键名齐全，但语义上时钟是错的。这类 bug 只能靠"和官方响应逐字节对齐"发现。

官方对照：`report\_tmp\official_decoded_201\04_3_api_networktime_sync.response.json`
- `meta.resp_bytes = 620`
- 7 键顺序：`Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, ReceiveTick, EchoSendTick`
- `ReceiveTick == EchoSendTick = 639304002554622693`
- `ServerTimeTicks - ReceiveTick = 12 ticks (1.2 µs)`
- `ServerTimeTicks` 是 .NET ticks（100 ns 自 0001-01-01），官方存 **UTC+8 墙钟**，不是 UTC

## 上线记录

| 项 | 值 |
|---|---|
| 补丁 | `patch_3.py` 63,870 B / sha256 `09584f25fc93777ae795eb2acf6f40e3a2af4cebf9988b3a2506b978ea1f7ef4` |
| 上线时刻 | 2026-11-17 01:23:49 |
| 桥（改前） | 90,585 B / 2,212 行 / sha256 `368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a` |
| 桥（改后） | **103,900 B / 2,546 行 / sha256 `563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8`** |
| 备份 | `/www/wwwroot/bapatch/tools/account_auth_probe.py.p3.pre.20261117-012349`（90,585 B / `368aa5e7…`） |
| 开关 | `/www/wwwroot/bapatch/cn_3.txt` = `1`（落在**上一层**；`p3_read_file` 的查找顺序包含父目录，实测生效） |
| 进程 | 旧 pid 2538845 → 新 pid 2569402，`127.0.0.1:9097` LISTEN |
| 冒烟 | 01:24:08 `/api/networktime/sync` → **200 / 620 B**，`gen_kind=networktime-3`，`p3_err=None`，7 键齐备，`ReceiveTick == EchoSendTick`，`ServerTimeTicks - ReceiveTick = 190 ticks` |

## 补丁设计（三层 hook）

| hook | 位置 | 作用 |
|---|---|---|
| `HOOK-E` | `_bridge()` 协议名解析完、`if exp == 'experror':` 之前（原 L1677） | 按协议名最早接管，**实际命中的就是这层** |
| `HOOK-D` | `_bridge()` path D，`if proto_int:` 之前（原 L1827） | 上层被摘掉时的兜底 |
| `HOOK-G` | `_generic_protocol_response()` 里 `if num == 90004:` 之前（原 L1353） | 通用构造层的最后一道 |
| `PAYLOAD` | 顶层 `if __name__ == '__main__':` 之前（原 L2206） | 生成器与钩子正文，296 行 |

三层各带独立标记、可单独回滚；生成器抛异常时只写 `rec['p3_err']` 后原路返回，不产生 500。

## 回滚（两条路，都实测过）

```bash
# 秒级、免重启（推荐先试这个）
echo 0 > /www/wwwroot/bapatch/cn_3.txt

# 代码级回滚（实测能逐字节回到 368aa5e7…）
python3 /www/wwwroot/bapatch/tools/patch_3.py \
        --src /www/wwwroot/bapatch/tools/account_auth_probe.py --rollback
```

## 上线前的本地验证（Lead 亲手跑，全绿）

| 步骤 | 结果 |
|---|---|
| `--verify` | 基线 `368aa5e7…` 命中，四锚点各唯一命中 1 次 |
| `--apply` | 103,900 B / `563c1942…`，与交付方产出**逐字节相同** |
| `py_compile` | OK |
| `_p3_replay.py` | **22 项断言 / 0 FAIL**：wire 恰好 620 B、`raw 464 = ct 432 + key 32`、7 键序 == `official_spec.json protocols["3"]`、tick 解回墙钟与现在差 0.0 s |
| `--prove-dispatch` | 全绿，三层 hook 逐层可达 |
| 异常隔离 | 抛错 → 200 / 448 B，不 500，`p3_err` 留痕 |
| 不误伤 | 对 4000/1017/24000/8000/90004/1005/26000 全部返回 `None` |
| `--rollback` | 还原 `368aa5e7…`，零残留标记 |

## 下一步的风险点（待日志确认）

客户端现在会开始请求大量此前没被走过的协议。桥里凡是用 `min` / `min+base` / 空构造兜底的协议，都会在客户端推进到对应界面时**静默卡住**。

已备好但**尚未 apply**的补丁：`patch_8000.py`（42,964 B）、`patch_90004.py`（30,946 B）—— 两者都已上传并校验 sha256，按序排在 `patch_3` 之后，随时可以打。

待办清单以 `srv-ops` 抓到的「降级清单」为准（哪些协议仍在用假响应）。
