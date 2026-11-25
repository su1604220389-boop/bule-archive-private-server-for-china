# 外部可改数据盘点（EDITABLE DATA INVENTORY）

> 目的：给「管理站可编辑项」做设计底稿 —— 列出所有**改完立刻影响线上、且不需要重新编译**的文件 / 配置 / 接口数据。
> 性质：**只读盘点**。未联网、未连服务器（<SERVER_IP>）、未改任何文件，只写本报告。
> 时间：2026-11-19 02:30–03:0x（Asia/Shanghai）
> 取值口径：**本地副本的 size/sha256 一律实算**；线上值优先取自有实测记录的文档（会标 `[文档实测]`）；本地没有的标 `—（未取证）`，不臆造。

---

## 0. 一页结论

- **盘出 92 项**外部可改数据：**30 项适合直接进管理站**、**37 项需分级/二次确认后才适合**、**25 项不适合**（死文件、机器写、含密钥、或当前构建根本没有读者）。
- 五个域的「读者」分布很干净：**nginx 静态文件**（state 系）、**Python 桥**（`cn_*.txt` + `_ba_state`）、**Python SDK**（`resp/*.json`）、**Shittim .NET**（`Data/` + `Config/` + 根目录 4 个 json）、**PHP 面板**（MySQL + `cards.json`）。
- **最危险的认知差**：桥的「开关」不是一两个，而是 **37 个单值文件**，全部**每请求读一次**、改完**不用重启**。做管理站时最大的价值不是"能改"，而是"**改之前能看清当前值 + 一键回到上一个值**"。
- **3 个"看起来能改、其实没用"的项**（做管理站时最容易被误当成开关）：
  - `/www/wwwroot/bapatch/tools/protocol_names.txt` —— 内容是 **159 行 IRC/Redis 常量**（`API_URL`、`ERR_*`、`RPL_*`），不是 BA 协议名；桥读它，但真实协议名来自代码里的 58 条 `BUILTIN_NAMES` + 路径兜底；
  - `/www/wwwroot/bapatch/tools/8000_switch.json` —— 当前线上桥**没有** `_BA8000_SWITCH_FILE` 这个符号（真开关，假读者）；
  - `/www/wwwroot/ba_srv/Data/Excel/MultiFloorRaidSeasonManageExcelT.json` —— 服务端读的是 `ExcelDB.db`，没有任何代码读这个 `Data/Excel/*.json`。
- **本地副本 ≠ 线上字节**（做基线时必须注意）：`noroot_payloads/state1.json` 本地 68 B（`Servers` 里带 `www.`），线上 64 B（不带 `www.`）。拿本地当"恢复默认"会**悄悄改掉域名**。

---

## 1. 判定图例

| 标记 | 含义 |
|---|---|
| ✅ | 适合进管理站直接编辑（结构可控 / 失败可回滚 / 无密钥） |
| 🟡 | 条件适合：只读展示 + 二次确认 + 灰度；或必须配强校验/重启流程 |
| ❌ | 不适合：无读者、机器生成、含密钥、二进制、或一改就绕开主链路 |

「重启?」列：**热** = 读者每请求/定时重读文件；**重启** = 进程启动时缓存一次；**无读者** = 改了也没人看。
sha256 一律为**本地副本实算**，表内按 `前缀…后缀` 省略中段，**完整 64 位见附录 A**。

---

## 2. 主表

### A. 桥 / bapatch 运营数据（13 项）

| ID | 路径（线上 → 本地副本） | 作用 | 谁在读 | 大小 + sha256 | 重启? | 备份/回滚点 | 判定 |
|---|---|---|---|---|---|---|---|
| A1 | `/www/wwwroot/bapatch/_ba_state/90004_ops.json` → `server\deploy\_p90004\90004_ops.json` | 90004 大厅运营数据：Notices 6 / Events 14 / Issues 0 / Banners 7 / GachaProbabilityDisplay 12 / GuidePopup 0，另 3 键恒 null | 桥 `load_90004_ops()` → `build_90004_management_data()`，**每请求** | 10,883 B<br>`938ae908…c06107fb` **[文档实测,与本地一致]** | 热 | `/root/D90004_20261119_021229/`（含 ROLLBACK.sh；改前该文件不存在，回滚会删除） | ✅ **首选**。四层白名单（键/字段/类型/键序）已在桥里，脏数据只会变空列表，不会崩 |
| A2 | `/www/wwwroot/bapatch/noroot_payloads/state1.json` → `server\deploy\noroot_payloads\state1.json` | 客户端 `/api/state`：`Servers` + 资源根 + 4 个版本号 + `IsOpenPreDownload` | nginx `location = /api/state { root …/noroot_payloads; rewrite ^ /state1.json break; }` | 线上 64 B `2a150b40…a582bd` **[文档实测]**<br>本地 68 B `18978364…f4709c`（多 `www.`） | 热 | `/root/ba_state1_backup_20261117_211746.json`（64 B 基线） | ✅ 但**必须严格校验字段集**：补 `ResourceVersion` 会触发客户端更新流程（历史上曾整机冻结） |
| A3 | `/www/wwwroot/bapatch/noroot_payloads/state2.json` → 同上目录 | 官方完整 state 样本（676 B，10 字段） | **无读者**（当前 rewrite 目标是 state1；仅作人工替换素材） | 676 B<br>`80127f6d…719913af` | 无读者 | 与 A2 同目录 | 🟡 只做「对照/回滚素材」，不做独立编辑入口 |
| A4 | `/www/wwwroot/_ba_state/gw/api-state.json` | gsqc-api/gs-api 主机的 `/api/state`（完整 676 B 版） | `tools/gwstate_probe.py`（127.0.0.1:9098）**每请求读** | 676 B（与 A3 同源；sha 未取证） | 热 | `bapatch/state/gw/api-state.bak` + 模板 | ✅ 与 A2/A6 合并成**一个 state 编辑器**（三处一份 schema） |
| A5 | `/www/wwwroot/bapatch/state/gw/api-state.template.json` | 24 字段完整模板（Addressables/ApiUrls/…/CDNLineCount/Msg） | `tools/set_gw_dto.py`（改前必读模板，按模板类型强转） | —（本地无副本） | 热 | 模板自身即基线；`set_gw_dto.py --restore` | ✅ 当作 A2/A4/A6 的 **JSON Schema 来源**，不直接给运营改 |
| A6 | `/www/wwwroot/_ba_state/state-api/api-state.json` | state-api / stateqc-api 的 `/api/state`：只有 `Servers`（3 条官方 API）+ `State/Msg`，**116 B 残缺版** | nginx `alias`（state-api / stateqc-api vhost） | 116 B **[文档实测]** | 热 | `/www/wwwroot/_ba_state/state-api/` 下 5 个历史变体（`m4probe/m5state/m6msg/msgprobe2/bak`） | ✅ 但**风险最高**：补版本号 = 告诉客户端"该更新了"，可能触发下载 |
| A7 | `/www/wwwroot/bapatch/academy_24000_config.json` | 24000 学院：`locations`（1 条 vs 9 条）/`zone_scope`/`request_id_mode` | 桥 `_ba24000_config()`，按 **mtime 缓存** | —（线上内容未找到，默认值生效） | 热 | 无（文件不存在 = 全默认） | ✅ 结构化编辑器（地点数组），校验 `LocationId` 在 1..9 内 |
| A8 | `/www/wwwroot/bapatch/tools/shittim_name_tokens.json` → `srv_live\20261118_0059\bapatch\tools\` | token(base32 md5 UTF-16LE 真名) → 权威协议名，501 条 | 桥 `nametoken_map()`，**首次调用后进程内缓存** | 27,598 B `28ebf459…413a0b35`（501 条） | 重启 | 本地副本 + 生成脚本 | ❌ 生成物；手改会让 `name_fix_resolve` 把协议名改错 |
| A9 | `/www/wwwroot/bapatch/tools/protocol_names.txt` → 同上 | **本意**协议名表；实际 159 行 IRC/Redis 常量（`API_URL`/`ERR_*`/`RPL_*`） | 桥 `load_names()`，启动一次 | 2,434 B `c6981dce…4aea78c6` | 重启 | 无 | ❌ 脏文件。桥用「路径兜底」绕过了它；建议**删除或替换**，不进管理站 |
| A10 | `/www/wwwroot/bapatch/tools/8000_switch.json` | Mission_List(8000) 开关（`enabled/profile/reset_hour/daily_sudden_id/max_progress`） | **当前桥无读者**（最接近线上的构建里搜不到 `_BA8000_SWITCH_FILE`） | 207 B `16f1a1f1…a2a3905b` | 无读者 | — | ❌ 孤儿。要么补回 8000 补丁，要么删掉，别做成开关（会骗人） |
| A11 | `/www/wwwroot/ba_sdk/cards.json` → `srv_live\20261118_0059\ba_sdk\cards.json` | 卡密库：`{cards:{key:{devices[],expire,bind_one}}}` | `sdkcard.py load_cards()`，**每登录请求**；绑设备时回写 | 快照 225 B `469df643…96fa6b` | 热 | MySQL 为唯一真源 + cron 每分钟重建 + 面板审计 | 🟡 **禁止直编**。只走面板/数据库；直编会被 cron 覆盖或产生孤儿 |
| A12 | `/www/wwwroot/bapatch/data/accounts.db` | 桥接库：`accounts`（发布者↔设备↔ServerId 镜像）；封禁数据 `bans` 见 G4 | 桥 `account_service.py`；PHP 面板（`inc/players.php` 只读镜像） | —（未取证） | 热（SQLite） | `/root/ba_db_backup/` | ❌ 库，不是"配置"。运营改动一律走面板，不手改文件 |
| A13 | `/www/wwwroot/_ba_state/cn_real_capture/resp_1.body` | 官方 1002 响应原始体；`wrap_mode=real_captured`/`e0_proto_swap` 时**原样回放** | 桥 `cn_wrap_mode()` 两个实验分支 | —（未取证） | 热 | 无 | 🟡 只在实验模式下有读者；做成只读展示 + 明确标注"仅排障" |

### B. 桥开关文件（`cn_*.txt`，37 个在役 + 2 个遗留 = 39 项）

> 全部位于 `/www/wwwroot/bapatch/` 或 `/www/wwwroot/bapatch/tools/`（查找顺序：bridge 目录 → `tools/` → `bapatch/`）。
> **全部每请求 `open().read()`，改完立刻生效、不用重启**（例外：`cn_nametoken.txt` 的表是进程内缓存）。
> 这些文件是 **0–8 B 单值**，sha256 没有信息量，下表给「内容」更有用。样本：`cn_1005.txt`=`1`（2 B，`4355a46b…`，含换行）。

| ID | 文件 | 取值 / 语义 | 谁在读 | 风险 | 判定 |
|---|---|---|---|---|---|
| B1 | `cn_account_svc.txt` | `1`=启用动态账号库（默认，缺失也算 true）；`0`=关 | `acct_svc_on()` | 关掉＝回退到硬编码单账号 | 🟡 |
| B2 | `cn_bridge_mode.txt` | `bridge`（默认）/`forward`（原样透传 5000） | `mode()` | 总模式开关，改错全服登不上 | 🟡 |
| B3 | `cn_bridge_force_reauth.txt` | 文件**存在**＝强制重铸会话，处理后 `os.remove` | `want_force_reauth()` | 只影响下一次登录 | 🟡 |
| B4 | `cn_bridge_exp.txt` | 实验总闸：`decrypt+plain`/`+http200`/`+http500`/`encresp1-3`/`resultstate0/1`… | `exp_flag()`/`http_override()` | 排障专用；线上现为 `decrypt+plain+http200` | 🟡 |
| B5 | `cn_resp_format.txt` | `shittim`（默认）/`cn_envelope` | `cn_resp_format()` | 换线格式，改错全员解不出包 | 🟡 |
| B6 | `cn_field_patch.txt` | `off`/`on`(FunctionClose=`{}`)/`on_alt`(`[]`) | `apply_field_patch()` | 补 CN 独有字段 | 🟡 |
| B7 | `cn_canary.txt` | `on`=外层明文注入 canary | `cn_canary_on()` | 排障 | 🟡 |
| B8 | `cn_hash_mode.txt` | `request`（默认，回显客户端 Hash）/`off` | `cn_hash_mode()` | 排障 | 🟡 |
| B9 | `cn_proto_val.txt` | `token`（默认 base32 md5）/`name` | `cn_proto_val()` | 换协议名表示法 | 🟡 |
| B10 | `cn_flatten_keys.txt` | `on`=把 `SessionKey.MxToken/AccountServerId`、`ServerId` 平铺到顶层 | `apply_flatten()` | 结构实验 | 🟡 |
| B11 | `cn_packet_wrap.txt` | `raw_gzip`（默认）/`json_string` | `cn_packet_wrap()` | 封包形态 | 🟡 |
| B12 | `cn_wrap_mode.txt` | `existing`（默认）/`cn_enc_b64`/`cn_enc_b64_probe`/`real_captured`/`e0_proto_swap`/`r01_update`/`e1_token`/`e2_nickname`/`e3_bare_dto`/`e4_strict_dto`/`a_proto_int`/`b_proto_str`（12 种取值） | `cn_wrap_mode()` | **最高危**：换线格式 | 🟡 |
| B13 | `cn_inner_min.txt` | `on`=内层只留 `MIN_KEEP` 白名单键（23 个） | `apply_min_inner()` | 裁剪内层 | 🟡 |
| B14 | `cn_inner_src.txt` | `shittim`（默认）/`spec26` | `cn_inner_src()` | 内层构造源 | 🟡 |
| B15 | `cn_requestid_mode.txt` | `random`（默认）/`echo`（复用请求里的 UUID） | `pick_requestid()` | RequestId 对齐 | 🟡 |
| B16 | `cn_nametoken.txt` | `1/on`=启用 token→真名权威映射 | `nametoken_on()` | 关掉＝退回路径机械转换（会大小写错名） | 🟡 |
| B17 | `cn_billing_block.txt` | `1/on`=拦 `Billing_TransactionStartByYostar(29000)` | `billing_block_on()` | **止血阀**：防止真实支付 | ✅ |
| B18 | `cn_1017_relay.txt` | `1/on`=1017 转发 relay2（真数据），`0`=旧 492 B 桩 | `relay1017_on()` | 登录同步链路 | ✅ |
| B19 | `cn_1017_mode.txt` | `dynamic`（默认）/`legacy`；环境变量 `CN_1017_MODE` 优先 | `cn_1017_mode()` | 回旧实现 | 🟡 |
| B20 | `cn_devid.txt` | `1/on`=把请求的 `DevId`/`DeviceUniqueId` 抄进日志 | `devid_on()` | 隐私采集 | ✅ |
| B21 | `cn_dedup.txt` | `1/on`=`Billing_TransactionEndByYostar` 窗口去重 | `dedup_on()` | 计费重复 | ✅ |
| B22 | `cn_dedup_window.txt` | 整数秒，默认 900 | `dedup_window()` | 去重窗口 | 🟡 |
| B23 | `cn_1005.txt` | `1`=启用 1005 桩（`Account_GetTutorial`） | `simple_switch_on()` | 三件套之一 | ✅ |
| B24 | `cn_4000.txt` | `1`=启用 4000 桩（`Item_List`） | 同上 | 三件套之一 | ✅ |
| B25 | `cn_26000.txt` | `1`=启用 26000 桩（`ContentSave_Get`） | 同上 | 三件套之一 | ✅ |
| B26 | `cn_simple_account.txt` | 三个桩用的账号号（覆盖默认 10015354380） | `simple_account()` | 调试值 | 🟡 |
| B27 | `cn_simple_ticks.txt` | 三个桩用的 `ServerTimeTicks` 覆盖 | `simple_ticks()` | 调试值 | 🟡 |
| B28 | `cn_3.txt` | `1`=启用协议 3 桩（`NetworkTime_Sync`） | `p3_switch_on()` | 时间同步桩 | ✅ |
| B29 | `cn_3_ticks.txt` | 协议 3 的时间戳覆盖 | `p3_ticks()` | 调试值 | 🟡 |
| B30 | `cn_relay_unknown.txt` | `1/on`=**未知协议**解包后转发给 5000 | `relay_route()` | 开＝多一条真实路径 | 🟡 |
| B31 | `cn_relay_known.txt` | `1/on`=**已知协议**也转发 relay2 | `relay2_route()` | 关掉＝大量协议回退到桩 | 🟡 |
| B32 | `cn_multiacct.txt` | `1/on`=按 publisher 分桶会话/票据（多玩家） | `cn_multiacct_on()` | 多账号核心开关 | 🟡 |
| B33 | `cn_session_ttl.txt` | 整数秒，默认 **120**；`<=0` 关闭 TTL | `cn_session_ttl()` | 会话复用时长 | ✅ |
| B34 | `cn_banreply.txt` | `1/on`=封禁回包（读 `bans` 表，命中登录握手） | banreply 分支 | 封禁体验 | ✅ |
| B35 | `cn_banreply_code.txt` | 整数，覆盖 `ErrorCode`（线上定案 **27000** `AccountBanned`；1025 已证伪） | `banreply_code_override()` | 改错＝封禁弹窗变兜底文案 | 🟡 |
| B36 | `cn_banreply_shape.txt` | `err`/`auth`/`forbid`（空=官方 `AccountBanErrorPacket`） | `banreply_shape()` | A/B 探测 | 🟡 |
| B37 | `cn_banreply_heat.txt` | `1:errcode=1025;2:shape=err;…` 按命中序号切变体 | `banreply_heat_plan()` | 一次开机多实验，危险 | 🟡 |
| B38 | `cn_preempt.txt` | 历史"抢占白名单"（旧补丁线） | **当前构建无读者** | — | ❌ |
| B39 | `cn_inner_requestid.txt` | 历史"内层 RequestId 同步"总闸 | **当前构建无读者**（现为 `cn_requestid_mode.txt`） | — | ❌ |

> 附：封禁文案（`封禁，请联系客服` / `封号时间 A 至 B，请联系客服`）**写死在代码里**，Python `ban_message.py` 与 PHP `inc/bans.php::ban_msg()` 必须逐字一致 —— 属"代码"不属"数据"，任何单边编辑都会两端漂移。

### C. SDK 静态响应（`/www/wwwroot/ba_sdk/resp/`，11 项）

> 读者全部是 `sdkcard.py`（127.0.0.1:8080）。目录本地快照：`work\ba\srv_live\20261118_0059\ba_sdk\`。

| ID | 文件 | 作用 | 谁在读 | 大小 + sha256 | 重启? | 备份 | 判定 |
|---|---|---|---|---|---|---|---|
| C1 | `resp/common_config.json` | 客户端 SDK 总配置（检测地址/登录方式/协议版本/分享/推送…） | `json.load(open(CFG))`，**每请求**；服务时把 `static/gs-api/sdk-api/baidu` 域名替换成 `example.com` | 7,873 B `ca6c98df…37289ee` | 热 | `common_config.json.bak.20261117-203121` | 🟡 **含密钥**（SLS AccessKey、OneKeyLoginSecret、微信/QQ AppID）。只放白名单字段，密钥字段只读 |
| C2 | `resp/user_quick-login.json` | 登录成功模板（`Data.User/Pass`，Token/ID/NickName 由代码注入） | `user_payload()`，每次登录 | 787 B `9085563c…f689468` | 热 | 无 | ✅ 但必须与 `user_payload()` 的注入键对齐，改结构会 500 |
| C3 | `resp/common_agreement.json` | 用户协议/隐私政策全文（1.15 MB） | **无路由**（当前落兜底空对象） | 1,157,396 B `a5794668…1e449c7` | 无读者 | 无 | ❌ 想上就得先给 `/common/agreement` 补路由 |
| C4 | `resp/common_client-code.json` | 错误码→文案表 | **无路由**（客户端请求过，返回空表） | 23,731 B `76be839a…4e8376` | 无读者 | 无 | ❌ 同上，先补 `/common/client-code` 路由 |
| C5 | `resp/common_geo-ip.json` | `{"Prov":"浙江省"}` | **代码写死**（`sdkcard.py` 直接返回） | 51 B `4a2f55a6…33a2b14` | 无读者 | — | ❌ 死文件 |
| C6 | `resp/health-game_duration.json` | `110170 用户已成年` | 代码写死 | 65 B `fdf760ca…956a16b` | 无读者 | — | ❌ 死文件 |
| C7 | `resp/heartbeat_pulse.json` | `{"Delay":3600}` | 代码写死 | 45 B `5ae8658d…6a08a04` | 无读者 | — | ❌ 死文件 |
| C8 | `resp/user_detail.json` | 详情模板 | 代码用 C2 模板，不读它 | 787 B `9085563c…f689468` | 无读者 | — | ❌ 死文件 |
| C9 | `resp/user_login.json` | 登录响应（76 B） | 无读者 | 76 B `cd573dd1…aed04972` | 无读者 | — | ❌ 死文件 |
| C10 | `pay.json`（SDK 根目录） | 支付行为：`PayState/DeliveryState/Amount` + `products/allow_pay` 等 | `_order_cfg()`，每 `/order/*` 请求 | 47 B `4461167…c398a54` | 热 | `sdkcard.py.order_ep.bak.*` | ✅ 但涉及钱，必须双人确认 + 审计 |
| C11 | `orders.jsonl` / `order_probe.log` | 订单流水 / 探测日志（追加写） | 代码追加 | — | 无读者 | 无 | ❌ 流水，不是配置 |

### D. Shittim `Data/`（7 项）

| ID | 路径 | 作用 | 谁在读 | 大小 + sha256 | 重启? | 备份 | 判定 |
|---|---|---|---|---|---|---|---|
| D1 | `Data/GachaRecruitBanners.cn.json` | **529 条**卡池清单覆盖层（`Id/From/To`，官方 CN 号段）→ `Shop_List` + `LoginSync` 的 `ShopRecruits` | `ShopHandler.BuildRecruitBanners()`，**每次** Shop_GachaRecruitList/LoginSync | 40,739 B `3ac8385d…c423c77` **[文档实测,与本地一致]** | 热 | `BANNER1_DEPLOY` 备份 + `/root` 备份；`clean5` 事故已回滚过 | ✅ **影响面最大**。必须校验：529 条、Id 号段、日期可解析（整体解析失败会**退化为 Excel 兜底号段**，客户端多半不认） |
| D2 | `Data/GachaRecruitBanners.cn.clean5.json` | 5 条精简版（曾误上线 6 分钟 → `Shop_List` NRE，已回滚） | 无读者（按名读的是 D1） | 480 B `ed3a3d86…da54834` | 无读者 | 自身 | ❌ 事故样本，别做成"模式切换" |
| D3 | `Data/Excel/MultiFloorRaidSeasonManageExcelT.json` | 多人战赛季（1 条） | **无读者**（读的是 `Resources/Dumped/Excel` 里的 `ExcelDB.db`） | 409 B `f9c61295…3673d5e` | 无读者 | 无 | ❌ 孤儿 |
| D4 | `Data/ProhibitedWord/blacklist.zip` | 屏蔽词 | `ProhibitedWordController`（`Results.File`），每请求 | 79,079 B `ce1dac87…34b6e71` | 热 | 无 | ✅ 但需 zip 构建器（PKZIP 加密、密码=`base64(TableService.CreatePassword(路由名))`） |
| D5 | `Data/ProhibitedWord/chattingblacklist.zip` | 聊天屏蔽词 | 同上 | 83,607 B `d7faf8d2…e17b20d` | 热 | 无 | ✅ 同上 |
| D6 | `Data/ProhibitedWord/whitelist.zip` | 白名单 | 同上 | 157 B `45a6e66e…f94964f5` | 热 | 无 | ✅ 同上 |
| D7 | `Data/Koyuki/koyuki.png` | 大厅横幅图（`/banner/{**path}` 全兜底） | `BannerController`，每请求 | 124,533 B `8c4a4728…48df6ec6` | 热 | 无 | 🟡 图片上传（限尺寸/类型），且只在 `KoyukiIncident=true` 时有意义 |

### E. Shittim `Resources/`（5 项）

| ID | 路径 | 作用 | 谁在读 | 大小 + sha256 | 重启? | 备份 | 判定 |
|---|---|---|---|---|---|---|---|
| E1 | `Resources/ClientItemIds.txt` | 客户端可解析道具白名单（**1803** 个 id）→ 出口过滤 | `ClientItemFilter.Warmup()`（启动）+ 首次缓存 | 12,659 B `48af0fd9…eb5ac6` **[文档实测,一致]** | **重启** | `_build_exportfilter/Resources/…`、`/root/panel_backup_*` | 🟡 只读展示 + "上传→校验→重启"流程；错一个 id 就是登录循环 |
| E2 | `Resources/ClientUnsupportedCharacters.txt` | 额外屏蔽的角色 id（一行一个，`#` 注释） | `ExcelTableService` 首次加载表时读，进程内缓存 | 不存在（用内置 23 个） | **重启** | 无 | 🟡 同上；文件不存在是正常态 |
| E3 | `Resources/original_version.txt` / `custom_version.txt` | 资源版本哨兵（机器写，比对是否要重下） | `ResourceService.LoadResources()`，启动 | — | 重启 | 无 | ❌ 机器写 |
| E4 | `Resources/Custom/`（目录） | 自定义资源覆盖（`ExcelDB.db` 等二进制） | `ResourceService`（`useCustomFile=true`） | — | 重启 | 无 | ❌ 二进制/体积过大 |
| E5 | `Resources/Dumped/ExcelDB.db` | 311 MB 日服 Excel 表（服务端读） | `ExcelTableService` | 311,083,008 B | 重启 | — | ❌ 二进制/改表要走 Excel 工具链 |

### F. Shittim 配置与运行时状态（9 项）

| ID | 路径（运行时根 = `/www/wwwroot/ba_srv/`） | 作用 | 谁在读 | 大小 + sha256 | 重启? | 备份 | 判定 |
|---|---|---|---|---|---|---|---|
| F1 | `Config/Config.json` | 主配置：`VersionId/OverrideVersionId/OverrideCdnBaseUrl`、`HostPort/GatewayPort`、`UseEncryption`、`BypassAuthentication`、`SelectedAccountId`、`EnforceTicketToken`、`SessionTtlMinutes`、`AdminApiKey`、`WorldRaidCoordinatorUrl`、`KoyukiIncident`、`ExcelDbSqlCipherKey`、`PacketLogging`… | `Config.Load()`（启动）；`SelectedAccountId` 由 API 即时改+`Save()` | 线上 ~2.6 KB（文档）；本地无副本 | **重启**（除 `SelectedAccountId`） | `/root/ba_db_backup/Config.json.pre-*` | 🟡 **只暴露白名单键**（区服名/端口/开关类）；`AdminApiKey`、`ExcelDbSqlCipherKey`、`ConnectionString` 只读 |
| F2 | `Config/ServerInfoConfig.json` | 客户端连接组（`DefaultConnectionGroup`/`ConnectionGroupsJson`/`Desc`/`DefaultConnectionMode`） | `Config.GetServerInfoConfig()`，启动时**自动重生成** | — | 重启 | 自动生成 | ❌ 机器生成，手改会被覆盖 |
| F3 | `Config/sessions.json`、`Config/gateway_aes_sessions.json` | 会话 / 网关 AES 会话持久化 | `SessionKeyService` / `GatewaySessionCrypto` | — | 重启 | — | ❌ 运行态 |
| F4 | `config/ba_version_cache.json` | 版本解析缓存：`VersionId`/`CdnBaseUrl`/`SourceBuildVersion`/`LastUpdatedUtc` | `BlueArchiveVersionResolver`，启动 | 215 B `a39d7b7a…582634b9` | 重启 | 无 | ❌ 缓存，删掉会自动重建 |
| F5 | `appsettings.json` | 日志级别、`ConnectionStrings`、`ServerConfiguration.VersionId/UseCustomExcel/DownloadExcelTables` | 框架（`reloadOnChange: true`） | 398 B `437ef6cc…08860c42` | 日志级别**热**；连接串/EF **重启** | 无 | 🟡 只给"日志级别"；其他键灰掉 |
| F6 | `gacha_config.json` | 抽卡概率 `custom_rates{ssr,sr,r}` + `guaranteed_character` | `GachaCommand.LoadConfigIfNeeded()`，**每 5 秒** | 不存在（=官方概率） | 热（≤5 s） | `POST /api/admin/gacha/config` 可覆盖/清空 | ✅ **首选**。已有读写 API |
| F7 | `server_notice.json` | `flags`（ServerNotification 位）+ `gate_error`/`gate_message`（维护门；除 `Queuing_GetCryptoKeys` 外全部拒答） | `ServerNoticeService.Load()` 启动；`POST /api/admin/notice` 即时 | 不存在（=不拦） | 直编**重启**；走 API **热** | API 会整份重写；建议加 `.bak` | ✅ **首选**（=一键维护/一键停服） |
| F8 | `event_schedule.json` | `{"enabled":[eventContentId…]}` 强制开放活动（改客户端 Excel 日期） | `EventScheduleService.Load()` 启动；`POST /api/admin/events/schedule` 即时 | 不存在 | 直编**重启**；走 API **热** | 同上 | ✅ 活动运营主轴（但会改客户端表，需灰度） |
| F9 | `worldraid_manifest.json` / `worldraid_state.json` / `worldraid_pending.json` / `worldraid_id` | 世界王协调器缓存与提交队列 | `WorldRaidService.Load()` | — | 重启 | — | ❌ 协调器写的，不是运营配置 |

### G. 管理站自己的库/配置（6 项）

> 线上：`https://<SERVER_IP>` → `/www/wwwroot/ba_cardadmin`，PHP 8.1 + MySQL 5.7 库 `ba_cardadmin`。
> 注意：本地 `work\ba\cardadmin_php\` 是**旧子集**（缺线上已部署的 `inc/bans.php`、`pages/bans.php`、`pages/players.php` 等）。

| ID | 表/文件 | 作用 | 谁在读 | 当前量 | 重启? | 备份 | 判定 |
|---|---|---|---|---|---|---|---|
| G1 | `cards` + `card_devices` | 卡密主表 + 设备绑定（`card_key/status/expire_at/bind_one`…） | 面板 + `cron/sync_cards.php` → `cards.json` | 1 行（11-17 文档快照，实际以线上为准） | 热（≤60 s 生效） | MySQL 备份 + `audit_logs` + `state/` | ✅ **已有页面** |
| G2 | `settings`（k-v） | `auto_gen_len/auto_gen_charset/auto_gen_prefix/page_size/cards_json_path/sdk_log_path/ba_admin_base/ba_admin_key/ba_accounts_db` | 面板 `pages/settings.php` + `inc/sync.php` | — | 热 | 审计 | ✅ **已有页面** |
| G3 | `card_players` + `panel_ops` | 卡密↔玩家绑定 / 玩家域写操作批次 | 面板 `inc/players.php` | — | 热 | 审计 | ✅ **已有页面** |
| G4 | `bans` 表（在 `data/accounts.db` 里） | 封禁三维目标 + `until_epoch` + `reason`；面板 `inc/bans.php` 是唯一写入口 | 面板写；桥只读（`cn_banreply.txt` 打开时） | — | 热 | 审计 | ✅ **已有页面**（`bans.php` 线上 105 KB） |
| G5 | `config.php` | DB 账号密码 + `APP_SECRET` | `inc/db.php` | — | 改后 php-fpm 即时 | 无 | ❌ 含密码/密钥 |
| G6 | `state/`（同步锁、备份、请求标记）+ `logs/` | 运行期状态 | cron / 面板 | — | — | 自动 | ❌ 运行态 |

### H. 客户端侧（我们只能间接影响，2 项）

| ID | 数据 | 在哪儿 | 作用 | 改它的后果 | 判定 |
|---|---|---|---|---|---|
| H1 | `ResourceVersion` / `TableVersion` / `MediaVersion` / `PatchVersion` / `IsOpenPreDownload` | 由 A2/A4/A6 三个 state 文件下发（**不可直接改客户端**） | 决定客户端"要不要更新、要不要预下载" | 给非空版本号 = 触发更新检查；CDN 上 `catalog_Remote.*` 实测 404 → 最坏进"更新失败"死循环 | ✅ 受控（必须灰度 + 手机侧备份 `files/`） |
| H2 | `AddressablesCatalogUrlRoots` / `CallbackUrl` / `CustomerServiceUrl` | 同上 | 资源从哪拉、回调去哪 | 改错 = 资源 404 / 黑屏；`CallbackUrl` 指向官方 `gs-inter…:4000` | 🟡 只读展示，改动需人工审批 |

---

## 3. 两栏：适合进管理站 / 不适合

### 3.1 适合进管理站（✅ 30 项）

**A（6）**：A1 `90004_ops`、A2 `state1`、A4 `_ba_state/gw/api-state`、A5 `api-state.template`（schema）、A6 `_ba_state/state-api/api-state`、A7 `academy_24000_config`
**B（10）**：B17 支付拦截、B18 1017 转发、B20 设备号采集、B21 计费去重、B23/B24/B25 三件套桩、B28 NetworkTime 桩、B33 会话 TTL、B34 封禁回包
**C（2）**：C2 `user_quick-login` 模板、C10 `pay.json`
**D（4）**：D1 卡池清单、D4/D5/D6 屏蔽词三件
**E（0）**：—
**F（3）**：F6 `gacha_config`、F7 `server_notice`、F8 `event_schedule`
**G（4）**：G1 卡密、G2 settings、G3 绑定/批次、G4 封禁
**H（1）**：H1 版本号/预下载

### 3.2 条件适合（🟡 37 项，需分级/二次确认/重启流程）

A3、A11、A13；B1–B3、B4–B16、B19、B22、B26、B27、B29、B30–B32、B35–B37；C1；D7；E1、E2；F1、F5；H2。
典型做法：**只读展示 + 复制到剪贴板 + 二次确认 + 差异预览**，不提供"直接保存"；或保存后强制走"灰度/重启"工单。

### 3.3 不适合（❌ 25 项）

A8、A9、A10、A12；B38、B39；C3–C9、C11；D2、D3；E3、E4、E5；F2、F3、F4、F9；G5、G6。
理由归类：**无读者（死文件）12 项**（A10、B38、B39、C3–C9、D2、D3）、**机器生成/运行态 8 项**（A12、C11、E3、F2、F3、F4、F9、G6）、**二进制/超大 2 项**（E4、E5）、**生成物/手改必错 2 项**（A8、A9）、**含密钥 1 项**（G5）。

---

## 4. 进管理站优先级（按影响面）

| # | 目标 | 影响面 | 为什么先做 | 落地成本 |
|---|---|---|---|---|
| 1 | **`/api/state` 三处**（A2/A4/A6） | **全服**：登不上 / 触发大更新 / 黑屏 | 一次改错等于全服不可玩；但 schema 简单、可灰度、可 30 秒回滚 | 低（一个 JSON 编辑器 + 三处同源 + 版本号单独锁） |
| 2 | **`GachaRecruitBanners.cn.json`**（D1） | **全服**：招募不可用 / `Shop_List` NRE / 登录同步失败 | 历史上已出过 2 次事故（529→5 条）；改错直接把登录链路打断 | 中（需校验 529/号段/日期 + 备份 + 一键回滚） |
| 3 | **`90004_ops.json`**（A1） | **全服**：公告/活动/横幅/概率公示 | 纯内容、零副作用、桥侧四层白名单兜底；运营价值最高、风险最低 | 低（表单化：公告 6 条 + 活动 14 条 + 横幅 7 条 + 概率 12 条） |
| 4 | **`server_notice.json`**（F7） | **全服可达性**：维护门 + 通知位 | 一键停服/维护公告，是唯一"合法断服"手段；已有 API | 低（复用 `POST /api/admin/notice`） |
| 5 | **`gacha_config.json`**（F6） | 抽卡经济：概率/保底 | 直接决定营收与玩家体验；5 秒热更、已有 API | 低（复用 `POST /api/admin/gacha/config`） |

> 次优批次：`event_schedule`（活动）→ 屏蔽词三件 → 卡密/封禁已有页 → SDK `common_config` 白名单字段。

---

## 5. 给管理站的 6 条硬约束（从这次盘点直接推出来）

1. **先做"读"再做"写"**：37 个 `cn_*.txt` + 9 个 Shittim 状态文件，**大部分线上并不存在**（缺失=默认）。管理站第一版应该展示「实际生效值 vs 默认值 vs 文件是否存在」，而不是展示一个空白输入框。
2. **三处 state 必须共用一份 schema**，且 `version` 字段单独上锁（改 `Servers` 和改 `ResourceVersion` 是两种风险等级）。
3. **每写必留前值**：这些文件的回滚点是 `/root/*.bak` 或 `.bak.<TS>`，不是版本库。管理站要用一张 `file_snapshots(path, sha256, blob, actor, ts)` 表，写入前自动快照（与本项目现有的 `panel_ops` 模式一致）。
4. **写后自检**（这是本项目的既有纪律）：`90004_ops` 写后跑 `data_key_report()` 对条数；`GachaRecruitBanners` 写后核对 529/号段/日期；`state` 写后 `json.load` + 字段集比对；`ClientItemIds` 写后核对 1803。
5. **"需要重启"的项单独一栏**（E1/E2/F1/F5/A8/A9）：管理站只能"上传 + 排队 + 提示需重启"，不能假装热更。
6. **含密钥的 3 个文件**（`common_config.json`、`Config/Config.json`、`config.php`）一律**字段级白名单**：密钥字段只显示 `已配置/未配置` + `sha8`，不显示明文。

---

## 6. 风险与未取证清单

| # | 事项 | 状态 |
|---|---|---|
| 1 | 线上桥现为 **222,539 B（改前）→ 02:12 打 90004 补丁后 md5 `891178d6…`**；本地 `_p90004/account_auth_probe.py` 是 **167,430 B 的旧构建线**，`_build_banreply2/` 是 222,486 B（差 53 B）。开关清单以 222,486 那条为准，**逐字节一致性未验证** | ⚠️ 未取证 |
| 2 | `_ba_state/` 目录下的 `gw/api-state.json`、`state-api/api-state.json`、`cn_real_capture/resp_1.body` 的大小/sha 来自文档转述，**本地无副本** | ⚠️ 未取证 |
| 3 | `Config/Config.json` 线上 2,639 B（11-17 22:07），此后被面板改过 `SelectedAccountId`/`AdminApiKey`，**当前内容未知** | ⚠️ 未取证 |
| 4 | `academy_24000_config.json` 线上是否存在未知；`Data/Excel/*.json`、`8000_switch.json`、`protocol_names.txt` 三个 **无读者**已从代码侧确证，但"线上是否还有人手工依赖"无法只读证明 | ⚠️ 未取证 |
| 5 | 本地 `cardadmin_php/` 缺 `inc/bans.php`、`pages/bans.php`、`pages/players.php`（线上已部署），**面板表结构以线上为准** | ⚠️ 已知缺口 |
| 6 | `cards.json` 线上路径存在两个候选：`/www/wwwroot/ba_sdk/cards.json`（`sdkcard.py:13`）与 `/root/bapatch/cards.json`（`config.php.example:53`）；面板 `cards_json_path` 实际值需线上核对，**配错就是"改了卡密没反应"** | ⚠️ 需核对 |

---

## 附录 A：完整 sha256（本地副本实算）

> 用于建基线/做校验。带 `*` 的是**本地副本**，与线上未必字节相同（A2 已知不同）。

```
A1  _p90004\90004_ops.json                    10883  938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb
A2  deploy\noroot_payloads\state1.json           68  18978364c260b254037cdedf7e2f4f2ae28d8dd06b39352e4e48a6ef34f4709c  *
A3  deploy\noroot_payloads\state2.json          676  80127f6d10f7bb85e1fb6b292b828c28e56fe39bc746f7905c0d6029719913af
A8  srv_live\…\tools\shittim_name_tokens.json 27598  28ebf45914bfbe13693a57b83e90da1296866540338180fc6b48df19413a0b35  *
A9  srv_live\…\tools\protocol_names.txt        2434  c6981dced6126156e0cd5ffc3112d0de0cf4657e41bc559859a02e6e4aea78c6  *
A10 _compat_check\full\8000_switch.json         207  16f1a1f167ebd9acd24d81e4b23bc24790357f9267cab7c07a923454a2a3905b  *
A11 srv_live\…\ba_sdk\cards.json                225  469df6435de855f8cf1171d9f3e7c392dc8ad3909f8c89b6f86b8192b096fa6b  *
B   deploy\_verify_rig\cn_1005.txt (=4000=26000)  2  4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865  *  ("1\n")
C1  ba_sdk\resp\common_config.json             7873  ca6c98dff20def8f3b6929348ff505124f775b6a0a305aebf0837551c37289ee
C2  ba_sdk\resp\user_quick-login.json           787  9085563cdebd0ef435f5191d934b72bd9bd1ae062f3f03c716e815d12e689468
C3  ba_sdk\resp\common_agreement.json       1157396  a5794668e96fe6e74067a1451142c5cb2d4df20e696d6eefb7e23719f1e449c7
C4  ba_sdk\resp\common_client-code.json       23731  76be839a81e6e61430428d08647f8d30c455865c1aaacf0df6bfdbae114e8376
C5  ba_sdk\resp\common_geo-ip.json              51  4a2f55a6616baf7cfc7191a1da0387b1e6f0807ce56b0a5d56f57dac633a2b14
C6  ba_sdk\resp\health-game_duration.json       65  fdf760ca6e4280a335f27bf086b6bd54af3b447d1949a8bd8d5002be5956a16b
C7  ba_sdk\resp\heartbeat_pulse.json            45  5ae8658d7694699afca9736dc7bc1fe9f7e52cf6a78f26d35ed7794ce6a08a04
C8  ba_sdk\resp\user_detail.json               787  9085563cdebd0ef435f5191d934b72bd9bd1ae062f3f03c716e815d12e689468
C9  ba_sdk\resp\user_login.json                 76  cd573dd14b432083bfe1bd5dbef2062fa4fecd523af1a1258a7a6891aed04972
C10 ba_sdk\pay.json                             47  4461167078cef3a9766f6728a22a5496ea22bcf974ea34b6d2aa31ad9c398a54
D1  Data\GachaRecruitBanners.cn.json          40739  3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77
D2  Data\GachaRecruitBanners.cn.clean5.json     480  ed3a3d867517f90b4cac97cfc4d39045bed38f8c36fa80ac280324708da54834
D3  Data\Excel\MultiFloorRaid…ExcelT.json       409  f9c612957fc77c0492ed5e0d18986ac68e721e56f900f958fa79f9df63673d5e
D4  Data\ProhibitedWord\blacklist.zip          79079  ce1dac8751e6d15437c721580eda8cda434ffe35ec4ac7f5f6611f10c34b6e71
D5  Data\ProhibitedWord\chattingblacklist.zip  83607  d7faf8d23e22122e44601d47b4fee6ad58df3918472f2b9b11e3767a1e17b20d
D6  Data\ProhibitedWord\whitelist.zip            157  45a6e66e2c6bfa92fdd655bc1227bb5c02e014792775ae4ec60c3930f94964f5
D7  Data\Koyuki\koyuki.png                    124533  8c4a47280ed47b2c90ffc7144319839f51b2eb2128b7b91ee862725748df6ec6
E1  Resources\ClientItemIds.txt                12659  48af0fd945fbd2dfaca0afa022b9cafb7095514bfd578b85a09dca17bbeb5ac6
F4  config\ba_version_cache.json                 215  a39d7b7af5213d509321d9ae95bf791e9c95cfad452ed5451e4f2415582634b9
F5  appsettings.json                             398  437ef6cc7d7641567fc92029ef573e3329e223c65c8bc03c12ebaa0308860c42
```

线上已实测的关键值（取自既有报告，非本次实算）：
```
A2  /api/state (state1, 64 B)        2a150b40cc1dde80bf5929d60dff5367a8f2bedc96709b213a29e71d21a582bd
A1  90004_ops.json (10,883 B)       938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb  (与本地一致)
D1  GachaRecruitBanners.cn.json      3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77  (与本地一致)
E1  ClientItemIds.txt (12,659 B)    48af0fd945fbd2dfaca0afa022b9cafb7095514bfd578b85a09dca17bbeb5ac6  (与本地一致)
```

> 说明：`90004_ops.json` / `GachaRecruitBanners.cn.json` / `ClientItemIds.txt` 三项的本地副本与线上 sha256 **逐字节一致**，可以直接当基线；`state1.json` **不行**（本地 68 B 带 `www.`，线上 64 B 不带）。

---

## 7. 本轮未做

```
未联网、未 SSH、未 curl、未改任何服务器文件
未改 work\ba 下任何源码/配置/数据
未新增除本报告外的任何文件
所有 size/sha256 来自本地副本实算或本文档标注的既有实测记录
```
