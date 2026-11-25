# official_decoded/ 说明

- 源 HAR：`C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\new0416.har`
- sha256：`071a0d622011baa66c3da82ed826ae0cacbbcb8da3bc9527be8b476e3304ed4c`
- 条目数：88
- 生成脚本：`work/ba/server/har_official_decode.py`

## 结论先行

**本 HAR 内 `POST /api/*`（游戏协议）条数 = 0。** 因此没有任何可解密的
`Account_Auth(1002)` / `Account_GetInfo` / `Academy_GetInfo(24000)` 信封。
这里存放的是**真实抓到的其余官方明文**，用于对齐我们的私服实现。

## 文件

| 文件 | 来源 | 条数 |
|---|---|---|
| `10_state-api_state.json` | `state-api.bluearchive-cn.com/api/state` | 1 |
| `11_gsqc-api_state.json` | `gsqc-api.bluearchive-cn.com/api/state` | 1 |
| `12_gs-api_health.json` | `gs-api.bluearchive-cn.com/api/health` | 4 |
| `20_sdk_user_login.json` | `sdk-api.yostar.cn/user/login` | 1 |
| `21_sdk_user_detail.json` | `sdk-api.yostar.cn/user/detail` | 1 |
| `22_sdk_send_sms.json` | `sdk-api.yostar.cn/send-sms` | 1 |
| `30_adjust_role_events.json` | `app.adjust.cn/event` | 2 |
| `40_bluearchive_hosts.json` | 全部 `*.bluearchive-cn.com` 条目 | 16 |
| `_timeline.txt` | 全部 88 条按时间排序 | 88 |
| `_summary.json` | 桶统计/_id 缺口/连接连续性 | - |

## 为什么没有游戏 RPC

见 `report/101-官方真服抓包分析.md` §2 的排除矩阵。
