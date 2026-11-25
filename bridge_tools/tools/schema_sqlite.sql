-- =============================================================================
--  schema_sqlite.sql —— 国服《蔚蓝档案》私服 · 多用户账号服务 DDL（SQLite 3.37+）
--  配套：account_service.py（唯一写入方）、report/93-多用户账号服务设计.md
--
--  用法 A（服务自建，推荐）：python account_service.py --init-db --db ba_accounts.sqlite3
--  用法 B（手工）          ：sqlite3 ba_accounts.sqlite3 < schema_sqlite.sql
--
--  与 schema_mysql.sql 的关系：
--    * 表名、列名、列顺序、约束语义**完全一致**，只差方言：
--        DATETIME -> TEXT（ISO 无时区字符串 'YYYY-MM-DDTHH:MM:SS'）
--        BIGINT   -> INTEGER（SQLite 整数是 64 位，够装 1e10）
--        AUTO_INCREMENT / ENGINE / COMMENT -> 无对应物
--    * 全部表用 STRICT（3.37+）：整数列塞 TEXT/REAL 会被拒绝，把「类型写错」提前到写入时报错，
--      逼近 MySQL 的严格模式。（注意：INTEGER 列的 NULL 在 rowid 别名主键上会被自动编号，
--      所以下面用 CHECK(server_id >= 10000000000) 兜底，小号一律拒绝。）
--    * 时间一律存无时区 ISO 字符串，不用 julianday/unixepoch，避免跨方言转换出错。
--
--  每个连接都要做的三件事（account_service.py 已做，手工用 sqlite3 CLI 时要自己来）：
--    PRAGMA foreign_keys = ON;      -- SQLite 默认关，不打开则外键形同虚设
--    PRAGMA journal_mode = WAL;     -- 多读一写并发（网关多线程时必需）
--    PRAGMA busy_timeout = 5000;    -- 拿不到写锁时等 5 秒而不是立刻 SQLITE_BUSY
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;

-- -----------------------------------------------------------------------------
-- schema_meta —— 结构版本与常量锚点
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_meta (
    k TEXT NOT NULL,
    v TEXT NOT NULL,
    PRIMARY KEY (k)
) STRICT;

INSERT INTO schema_meta (k, v) VALUES ('schema_version', '1') ON CONFLICT (k) DO NOTHING;
INSERT INTO schema_meta (k, v) VALUES ('server_id_base', '10000000000') ON CONFLICT (k) DO NOTHING;
INSERT INTO schema_meta (k, v) VALUES ('created_by', 'work/ba/server/schema_sqlite.sql') ON CONFLICT (k) DO NOTHING;

-- -----------------------------------------------------------------------------
-- id_alloc —— server_id 发号器（不用 AUTOINCREMENT：起始值要为 10000000000，
-- 且发号必须与「建账号 + 写 blob」同事务回滚，理由见 schema_mysql.sql 同段注释）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS id_alloc (
    name    TEXT    NOT NULL,
    next_id INTEGER NOT NULL,
    PRIMARY KEY (name)
) STRICT;

INSERT INTO id_alloc (name, next_id) VALUES ('server_id', 10000000000) ON CONFLICT (name) DO NOTHING;

-- -----------------------------------------------------------------------------
-- accounts —— 一个玩家一行：身份 + AccountDB 22 字段 + 发号游标
-- 唯一键 dev_id；device_unique_id / sdk_token 只做辅助（Token 会轮换，DUID 会随重装变）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounts (
    server_id               INTEGER NOT NULL,           -- 账号主键（= SessionKey.AccountServerId）
    dev_id                  TEXT    NOT NULL,           -- Account_Auth.DevId，主身份键
    device_unique_id        TEXT        NULL,           -- Account_Auth.DeviceUniqueId
    sdk_token               TEXT        NULL,           -- Account_Auth.Token（轮换，不鉴权）
    publisher_account_id    INTEGER NOT NULL DEFAULT 0, -- AccountDB.PublisherAccountId
    nickname                TEXT    NOT NULL DEFAULT '',
    call_name               TEXT    NOT NULL DEFAULT '',
    state                   INTEGER NOT NULL DEFAULT 1, -- AccountDB.State（枚举→int）
    level                   INTEGER NOT NULL DEFAULT 1,
    exp                     INTEGER NOT NULL DEFAULT 0,
    comment                 TEXT    NOT NULL DEFAULT '',
    lobby_mode              INTEGER NOT NULL DEFAULT 1,
    represent_character_server_id INTEGER NOT NULL DEFAULT 0,
    memory_lobby_unique_id  INTEGER NOT NULL DEFAULT 0,
    location                TEXT    NOT NULL DEFAULT '',
    birthday                TEXT        NULL,          -- NULL = 未设置 → 出包 1970-01-01T00:00:00
    call_name_update_time   TEXT        NULL,          -- NULL → 出包用 created_at
    link_reward_date        TEXT        NULL,
    last_returning_date     TEXT        NULL,
    retention_days          INTEGER     NULL DEFAULT 1,
    vip_level               INTEGER     NULL DEFAULT 0,
    unread_mail_count       INTEGER     NULL DEFAULT 0,
    next_entity_id          INTEGER NOT NULL DEFAULT 1000001, -- 本账号实体 id 发号游标
    created_at              TEXT    NOT NULL,
    last_login_at           TEXT        NULL,
    token_seen_at           TEXT        NULL,
    login_count             INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (server_id),
    CHECK (server_id >= 10000000000),          -- 「不许从 1 开始」的库侧兜底
    CHECK (level >= 1),
    CHECK (login_count >= 0)
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS uk_accounts_dev_id            ON accounts (dev_id);
CREATE INDEX        IF NOT EXISTS idx_accounts_device_unique_id ON accounts (device_unique_id);
CREATE INDEX        IF NOT EXISTS idx_accounts_publisher_account_id ON accounts (publisher_account_id);
CREATE INDEX        IF NOT EXISTS idx_accounts_last_login_at    ON accounts (last_login_at);
CREATE INDEX        IF NOT EXISTS idx_accounts_nickname         ON accounts (nickname);

-- -----------------------------------------------------------------------------
-- sessions —— MxToken 会话（36 字符 GUID 小写为主键；大小写不敏感靠「写读前归一化 + 主键等值」）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    mx_token   TEXT    NOT NULL,
    server_id  INTEGER NOT NULL,
    issued_at  TEXT    NOT NULL,
    expires_at TEXT    NOT NULL,
    last_seen  TEXT        NULL,
    revoked    INTEGER NOT NULL DEFAULT 0,
    client_ip  TEXT        NULL,
    note       TEXT        NULL,
    PRIMARY KEY (mx_token),
    CHECK (revoked IN (0, 1)),
    FOREIGN KEY (server_id) REFERENCES accounts (server_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS idx_sessions_server_id  ON sessions (server_id, revoked);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at);

-- -----------------------------------------------------------------------------
-- account_blobs —— 每用户子系统状态（40 个状态块 → 21 个 kind），payload = JSON 对象文本
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS account_blobs (
    server_id  INTEGER NOT NULL,
    kind       TEXT    NOT NULL,
    payload    TEXT    NOT NULL,
    revision   INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT    NOT NULL,
    updated_by TEXT        NULL,
    PRIMARY KEY (server_id, kind),
    CHECK (revision >= 1),
    FOREIGN KEY (server_id) REFERENCES accounts (server_id) ON DELETE CASCADE
) STRICT;

CREATE INDEX IF NOT EXISTS idx_account_blobs_updated_at ON account_blobs (updated_at);

-- 可选收紧（SQLite 3.38+ 的 json_valid 在 3.45 前对 blob 返回 NULL，故不默认启用）：
--   ALTER TABLE account_blobs ADD COLUMN ... 不支持加 CHECK，只能建表时写；需要就改本文件。

-- -----------------------------------------------------------------------------
-- protocol_log —— 每请求一行（可选但建议）；id 走 rowid 自增，其它列与 MySQL 一致
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS protocol_log (
    id          INTEGER NOT NULL PRIMARY KEY,   -- rowid 别名，自动递增
    server_id   INTEGER NOT NULL DEFAULT 0,
    protocol    INTEGER NOT NULL,
    started_at  TEXT    NOT NULL,               -- 'YYYY-MM-DDTHH:MM:SS.mmm'
    duration_ms INTEGER NOT NULL DEFAULT 0,
    resp_bytes  INTEGER NOT NULL DEFAULT 0,
    status      INTEGER NOT NULL DEFAULT 0,
    note        TEXT        NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_protocol_log_server_time ON protocol_log (server_id, started_at);
CREATE INDEX IF NOT EXISTS idx_protocol_log_proto_time  ON protocol_log (protocol, started_at);
