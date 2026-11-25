# 登录「同步账号信息时发生错误」· 根因与修复（2026-11-17 收口）

> 起点：用户在面板「道具 / 角色」页把 9 个快捷动作全按了一遍（目标 ServerId=2），之后重登报错。
> 终点：**2026-11-17 23:2x，用户实测「成功登录，所有角色全部解锁，羁绊 100 级、五星、90 级，完美解决」。**
> 用户指令全程：「先不要改代码，先检查一下问题」→「直接改我的存档」→「面板里的判定也都要做好」→「不需要改任何代码了」。

---

## 0. 根因（一句话）

**服务端与客户端用的不是同一套角色表。服务端 `CharacterExcelT` 有 257 个"可游玩且已上线"的角色，而安装的 CN 3.0.2 客户端只能解析其中 234 个。`!giveall` 把全部 257 个（减去用户已有的 4 个）写进了存档，客户端在登录同步时遇到无法解析的角色 id 直接中止加载。**

服务端源码里作者自己写下了这个判据（`AccountHandler.LoginSync`）：

> The client **aborts loading on a character id with no excel entry**

### 23 个不可发放的角色 id（最终定案）

```
10099
10127 10128 10129 10130 10131 10132 10133 10134 10135 10136 10137 10138
16018 16019
20050 20051 20052 20053 20054 20055 20056 20057
```

分两类：

| 类 | 数量 | 判据 |
|---|---|---|
| 客户端名单里压根没有 | 4（10099 / 10137 / 10138 / 20057） | 不在 `CharacterAcademyTagsDBSchema` |
| 客户端名单里有，但没有角色数据行 | 19 | 在 `CharacterAcademyTagsDBSchema`，但不在 `CharacterDBSchema` |

### 怎么算出来的（可复现，零猜测）

用客户端那份 `ExcelDB.db`（160,534,528 B，sha256 `c49096aa6fdafee3c7bb4d5293039e1dafe1521c09c033bd25566aefae2cc5a9`）做集合运算：

```python
acad     = {Id from CharacterAcademyTagsDBSchema}   # 253
cdb      = {Id from CharacterDBSchema}              # 7223
client_ok = acad & cdb                              # 234  ← 客户端真正能解析的
server    = giveall(253) ∪ 用户原生(4)              # 257  ← 服务端能发放的
bad       = server - client_ok                      # 23   ← 必须剔除
```

---

## 1. 决定性证据：每一次登录实验都对得上

| 角色数 | 含坏 id 数 | 副本/剧情 | LoginSync 响应体 | 结果 |
|---|---|---|---|---|
| 4 | 0 | 416 / 578 | 274,860 B | ✅ 进大厅 |
| 5（+uid=10000） | 0 | 416 / 578 | 275,244 B | ✅ 进大厅 |
| 129 | 0 | 416 / 578 | 324,184 B | ✅ 进大厅 |
| 191 | **12** | 416 / 578 | 348,652 B | ❌ 同步错误 |
| 191 | **12** | 0 / 0 | **88,344 B** | ❌ 同步错误 |
| 172（砍了 20000 段，但那 12 个还在） | **12** | 0 / 0 | — | ❌ 同步错误 |
| 253（原状） | **23** | 416 / 578 | 373,016 / 374,592 / 606,764 B | ❌ 同步错误 |
| **234（修复后）** | **0** | 416 / 578 | — | ✅ **进大厅，全部角色可用** |

**"含坏 id 数 > 0 就崩、= 0 就进"，一个例外都没有。**

---

## 2. 我（Lead）被推翻的四个假设 —— 必须写下来

这四个都曾被我当成"找到了"，然后被一次实测打掉。**每次代价是用户多登一次游戏。**

| # | 假设 | 依据 | 怎么死的 |
|---|---|---|---|
| 1 | **那 4 个"客户端名单没有"的 id 就是全部** | 差集算出 4 个，与"253 vs 253"的巧合对上 | 剔除后**仍然崩**。差集只是候选，**没验证就当了结论** |
| 2 | **装备 1910 行形态错误**（`Tier` 应为 `TierInit`） | 正规创建路径都写 `Tier = TierInit` | 实测 `TierInit` 本来就分布 0..10；且搬走装备后**仍然崩** |
| 3 | **数值越界**（`max all` 写的 5★/90/好感100/潜能25） | 看起来"太满" | 253 行与能进的 4 个**逐字段完全相同** |
| 4 | **响应体太大**（606,764 B 撑爆客户端） | 39 倍暴涨，时间点吻合 | 191 行 + 零副本 = **88,344 B** 仍然崩（比能进那次小 73%） |

**教训（写进方法）：一个观察只支持一个观察。差集要验证、语义要读全、变量要单点。**

---

## 3. 另一个自伤：宝塔 WAF 把客户端封在门外

调查中途出现「连『点击进入游戏』都出不来，提示请确认网络连接状态后重试」，一度被误判成"数据问题不可能导致这个"。

**根因：宝塔免费 WAF（`free_waf`）的 CC 限流被我们自己的高频取证 curl 触发。**

```json
// /www/server/free_waf/config.json
"cc": {"status": 444, "limit": 120, "endtime": 300, "open": true}
```

```
nginx 访问日志：
  22:38:14  "GET /api/state HTTP/1.1"  444  0    ← free_waf 封禁码
  同刻      /sdk/common/config → 200（不同 location，未命中）
  同刻      80 端口的 /api/state → 200
```

`127.0.0.1` 在封禁名单里 14 条，来源是我们自己的 curl（含扫路径探测）。而 `/api/state` 正是客户端开游戏第一步要拿的东西。用户在面板手动解封后立即恢复。

**教训：取证探测一律避开客户端在用的路径（`/api/state`、`/sdk/*`），或 ≥1s 间隔 + 命中 444 立即停。**

---

## 4. 修复（两层保险）

### 第一层：服务端 —— 从「读表」这一层剔除

`Shittim-Server/Services/ExcelTableService.cs`，补丁标记 `BAPATCH-CLIENTROSTER v1`：

```csharp
private static readonly long[] DefaultClientUnsupportedCharacters = [ ...23 个 id... ];

// GetTable<T>() 里：缓存填充后过滤一次，过滤结果写回缓存；bypassCache 也走过滤
if (bypassCache || clientRosterFiltered.TryAdd(type, 0))
{
    var rosterFiltered = DropClientUnsupportedCharacters(unpacked);
    if (!ReferenceEquals(rosterFiltered, unpacked)) { caches[type] = rosterFiltered; unpacked = rosterFiltered; }
}
```

**为什么改在这里**：`!giveall` 遍历这张表、`!give` 从这张表找、邮件/卡池/商店/活动奖励都在 `ParcelResolver` 里按 id 查这张表 ⇒ **一处过滤，全链路生效**，不需要逐个命令打补丁。

**运行时后门**：`Resources/ClientUnsupportedCharacters.txt`，一行一个 id（`#` 注释），客户端更新后改文件即可，**不用重编译**。

### 第二层：面板 —— 提交前拦一道并提示

| 文件 | 改动 |
|---|---|
| `inc/players.php` | 新增 `ba_denied_character_ids()` / `ba_is_denied_character()` / `ba_validate_parcels()` / `ba_validate_command()`；名单可被 `state/character_denylist.txt` 覆盖 |
| `pages/mail.php` | 附件里 `Character` + 被排除 id → 拒绝发送并提示 |
| `pages/console.php` / `pages/items.php` / `pages/player_detail.php` | GM 命令含 `character` 且点名被排除 id → 拒绝执行并提示 |
| `pages/items.php` | 页首常驻提示，列出这 23 个 id |
| `pages/settings.php` | 「游戏服务端」区新增「角色排除名单」一行 + 覆盖文件路径 |

---

## 5. 上线记录

### 服务端 DLL

```
旧  adcb1e03bc82b8fcad97a27e2054483f75c0079dd80e799615a76b6b55229377  2,672,640 B
新  3ec7c46d2890dd5dae9184b0ecbf64fea386f968ec70676626d319da16180096  2,674,688 B

启动：tmux 会话 shittim，cwd=/root
      /root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2
备份：/root/panel_backup_20261117_230602/{Shittim-Server.dll, shittim.sqlite3}
```

### 生效验证（三处独立口径，都是 −23）

```
CharacterExcelT 全表        7279 → 7256     （tmux 面板：dropped 23 character row(s); roster is now 7256）
static/characters（不筛 Release）293 → 270
giveall 可发放集合           257  → 234
```

> `roster is now 7256` 这个数字**含义不准**（它是整张 Excel 表的行数，含 NPC/敌方，不是可发放集合）。功能无影响，只是日志文案会误导后人 —— 下次编译时改成可发放集合的计数。

### 面板文件（6 个，已上线并冒烟）

```
05b678a8…  inc/players.php          20,661 B
2ed504c1…  pages/mail.php           16,792 B
080bad2c…  pages/console.php        10,204 B
51beeeca…  pages/items.php          15,629 B
740dd2fc…  pages/player_detail.php  21,032 B
ead9a400…  pages/settings.php       20,164 B
备份：/root/panel_backup_20261117_230642/php/
```

冒烟：4 页全 200、无 Fatal；`items.php` 出现「23 个角色无法解析」，`settings.php` 出现「角色排除名单」。

---

## 6. 最终状态（用户实测确认）

```
用户：成功登录，所有角色全部解锁，羁绊 100 级、五星、90 级

账号 2：Characters 234 / Equipments 1913 / CampaignStageHistories 416 /
        ScenarioHistories 578 / ScenarioGroupHistories 4
货币未动（Gem 1,101,000 / Gold 250,000 / AP 999）
三跳：/api/state 200 · /sdk/common/config 200 · / 200（无 444）
```

### 数据搬运留下的影子表（保留作回滚，确认无误后可清）

```
Characters_park_LOGINSYNC          253
Equipments_park_LOGINSYNC         1910
CampaignStages_park_LOGINSYNC      416
ScenarioHistories_park_LOGINSYNC   578
ScenarioGroup_park_LOGINSYNC         4
Characters_trim248_bak             248
Characters_batch62_bak              62
Characters_probe20000_bak           19
```

> **`giveallequip` 是有效的，不是 bug**：`GiveAllEquipCommand` 的既定语义是 "all equipment at all tiers"，`Tier` 取 1..10 是该命令的设计意图。曾误判为"结构性错误"，已撤销。

---

## 7. 回滚

```bash
# 服务端 DLL
cp -a /root/panel_backup_20261117_230602/Shittim-Server.dll /www/wwwroot/ba_srv/Shittim-Server.dll
tmux kill-session -t shittim
tmux new-session -d -s shittim -c /root
tmux send-keys -t shittim "/root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2" Enter

# 面板
cp -a /root/panel_backup_20261117_230642/php/* /www/wwwroot/ba_cardadmin/...   # 对照备份目录逐文件覆盖

# 数据库（回到任一时刻）
cp -a /root/panel_backup_<STAMP>/shittim.sqlite3 /root/shittim.sqlite3
```

---

## 8. 遗留 / 值得做但用户说不用

| 项 | 说明 |
|---|---|
| `roster is now 7256` 日志文案 | 改成可发放集合计数。**用户明确说不用改代码**，记录备查 |
| 装备 1910 行要不要精简 | 有效数据，用户没要求处理 |
| 影子表要不要清 | 建议确认无误后再清，现在留着随时可回滚 |
| 客户端更新流程 | 重新算 `acad ∩ cdb` 差集，写进 `Resources/ClientUnsupportedCharacters.txt`（服务端）与 `state/character_denylist.txt`（面板）即可，**不需要重编译** |

---

## 9. 一句话给后来的人

> **「发全部角色」这类"按服务端 Excel 枚举"的功能，在服务端与客户端 Excel 不同版本的私服环境里天然是雷。**
> 本服务器的 `Resources/Dumped/ExcelDB.db` 是 **311,083,008 B**，客户端的是 **160,534,528 B**，两者不是同一套表。
> 任何"把服务端认识的全发给客户端"的操作，都必须先跟客户端表求交集。
