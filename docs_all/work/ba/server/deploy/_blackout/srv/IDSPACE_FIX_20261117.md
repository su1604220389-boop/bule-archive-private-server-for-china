# ID SPACE FIX —— 代表角色（RepresentCharacterServerId）悬空修复

- 执行者：srv-ops
- 时间：2026-11-17 19:53（北京时间 UTC+8）
- 操作范围：只改 `/www/wwwroot/bapatch/data/accounts.db` 的 **1 行 2 个字段**（同一账号）
- 未重启任何服务、未改任何代码、未碰 `shittim.sqlite3`

---

## 结论（先说）

**CharacterDBs 的 ServerId 是 [210001, 210002, 210003, 210004]；已改成 rep=210001、lobby_mode=0；不会被自动改回。**

### ⚠️ 诚实标注：本轮是**双变量联合验证**，不是单变量

- `lobby_mode=0` 与 `represent_character_server_id=210001` 是在**同一条 UPDATE**（19:53:00）里一起改的。
- 随后 Lead 要求"只改 lobby_mode"，复审时该行 `lobby_mode` 已是 0，SQL 只是**幂等确认**（rows affected=1，值不变）。
- **因此，用户这次重登测到的是「lobby_mode=0 + rep=210001」的组合效果，不能归因到单一变量。**
- 归因实验（把 rep 退回 1100001，只留 lobby_mode=0）**留到用户确认"不卡了"之后**再做，届时一条 SQL + 一次重登即可，回滚备份就绪。

### 本轮验证口径（Lead 采纳）

| 判据 | 采集方式 | 通过标准 |
|---|---|---|
| ① `rep` 是否被客户端接受 | 下一次 `Account_Auth` 的 wire 全文 | `AccountDB.RepresentCharacterServerId == **210001**` |
| ② `LobbyMode` 是否生效 | 同上 | **判据是"键不在 AccountDB 的键列表里"**（值为 0 被 `DefaultValueHandling.Ignore` 省略），**不是**"值为 0" |
| ③ 卡顿是否消失 | `tcp-access.log` 里 8443 会话的 `session_time` | 从 **30 s 级**降到**秒级** |
| ④ 大厅背景是否恢复 | 手机侧抽帧（人眼判断） | **背景图/看板角色出现**；改前是「整片纯黑 + 中央一个蓝色光球、无背景图无看板角色」，**所以"画面非黑"不算通过** |

### 若仍卡 30 s / 背景仍空 —— 后续单变量阶梯（一轮一个）

1. **退回 rep**：`UPDATE accounts SET represent_character_server_id=1100001 WHERE server_id=10000000001;` —— 只留 `lobby_mode=0`，验是不是 rep 的锅。
2. 都不行 → 转查 `memory_lobby_unique_id`（当前 0）与「Shittim `MemoryLobbies = [(2,13010)]` 为何没送到客户端」。


---

## 1. 客户端实际收到的 `CharacterDBs`（第 1 步）

来源（Lead 指定，proto-analyst 落盘产物，未自行解密）：
`work\ba\server\deploy\_blackout\proto\_ours_loginsync_37060.json`

原始片段（4 个元素）：
```json
"CharacterDBs": [
  {"ServerId": 210001, "UniqueId": 13010, "StarGrade": 2, "Level": 1, ...},
  {"ServerId": 210002, "UniqueId": 16003, "StarGrade": 1, "Level": 1, ...},
  {"ServerId": 210003, "UniqueId": 13003, "StarGrade": 2, "Level": 1, ...},
  {"ServerId": 210004, "UniqueId": 26000, "StarGrade": 1, "Level": 1, ...}
]
```
**⇒ 客户端眼里的角色 ServerId 只有 **210001 / 210002 / 210003 / 210004**。**
**⇒ 原先 `represent_character_server_id = 1100001` 在这四个里**不存在** → 确认是悬空引用。**

（补充：账号 2 的 4 个 UniqueId 13010/16003/13003/26000 与 Shittim `Characters` 表一致（表内 ServerId 为 7/8/9/10），说明**客户端收到的是 Shittim 的角色被重新编号成 210001+ 之后的结果**。）

## 2. 备份（第 2 步）

**本轮（lobby_mode 幂等确认，19:53:22）**
```
/root/ba_db_backup/accounts.db.20261117_195322.lobby0.bak
118,784 B
sha256 00d08eeaf6bb82f90dd25ec775ec9b9b453d535152e1bef120e8331991cb9cf4
```

**上一轮（rep+lobby_mode 同时改之前，19:53:00）**
```
/root/ba_db_backup/accounts.db.20261117_195300.bak
118,784 B
sha256 7ef35289435a9374aec9d874b7752e5fc4c1860f661cfd212b162c345efccb9f
（用 sqlite3 backup API 做的在线一致快照，非裸 cp）
```

## 3. 改动（第 3 步）

改前：
```
(10000000000, '老师0001', lobby_mode=1, rep=1000001, memlo=0, next_entity=1000005)
(10000000001, '老师0002', lobby_mode=1, rep=**1100001**, memlo=0, next_entity=1100005)
```
SQL（原文）：
```sql
UPDATE accounts
   SET lobby_mode = 0,
       represent_character_server_id = 210001
 WHERE server_id = 10000000001;
```
```
rows affected = 1
```
改后：
```
(10000000000, '老师0001', lobby_mode=1, rep=1000001, memlo=0, next_entity=1000005)   ← 未动
(10000000001, '老师0002', lobby_mode=**0**, rep=**210001**, memlo=0, next_entity=1100005)
PRAGMA quick_check = ok
只读复核：target row = (10000000001, 0, 210001, 0)
```

## 4. 回滚（一行）

```bash
cp -a /root/ba_db_backup/accounts.db.20261117_195300.bak /www/wwwroot/bapatch/data/accounts.db
```
（桥每次请求重读该库，**无需重启**；若要更稳妥可 `pkill -f python3 account_auth_probe.py` 后按既有方式重启桥。）

## 5. 第 4 步判定：**不会被自动改回去**

`account_service.py` 的关键行：
```
988:        self._rewrite_identity(state, account, renumber_entities=True)      ← 只有这里会重设 rep
1081:            state['account']['RepresentCharacterServerId'] = next_entity if chars else 0
1088:        account.represent_character_server_id = state['account']['RepresentCharacterServerId']
```
调用链（唯一的续命路径）：
```
bootstrap_state()   (定义 979，内部调用 988 的 _rewrite_identity)
  └─ 唯一调用点：623  state = self.bootstrap_state(account)
       └─ 位于 _create_account()（新账号 INSERT 之后立即执行，596-629 行可见
          INSERT INTO accounts ... → bootstrap_state → _write_blobs → UPDATE next_entity_id）
```
**登录路径不经过它**：
```
Account_Auth(1002) → identify()(501) → get_or_create_account() / _stamp_login()(699 record_login)
                    → build_account_db_for()(886)          ← 只读 accounts 行拼 22 字段
                    → build_state_for()(942)              ← 只读 accounts 行 + blobs 拼 41 键
```
**⇒ 结论：`bootstrap_state()` 只在「新建账号」时跑；只要不删号重建，登录不会重写 `represent_character_server_id`。改库可持久生效。**

## 6. 遗留风险（只记录，未处理）

1. **桥自己的 `account_blobs(kind='characters')` 里，ServerId 仍是 1100001/1100002/1100003（3 个，UniqueId 10010/10000/10001）**，而客户端实际收到的 4 个角色是 210001~210004（UniqueId 13010/16003/13003/26000）。**两套编号并存**：
   - `AccountDB.RepresentCharacterServerId` ← 取 `accounts` 行（现已 =210001，与客户端一致）
   - `CharacterDBs` ← 实际由 Shittim 转发结果（210001~210004）
   - 桥 blobs 里那份 1100001~ 目前**没有**被直接发给客户端（否则会出现第二套），但它仍是潜在污染源。
2. `memory_lobby_unique_id = 0`（两账号都是 0）：如果"大厅要显示记忆大厅"，这个字段仍需另行处理（本次未动）。
3. 账号 1（`10000000000`）的 `lobby_mode` 仍是 **1**、`rep=1000001`：本次按"一次只改一个变量"未碰。

---

## 附：本次未改动
```
shittim.sqlite3        未动
account_auth_probe.py  未动
Shittim DLL            未动
nginx/证书/WAF         未动
服务重启               未做
```
