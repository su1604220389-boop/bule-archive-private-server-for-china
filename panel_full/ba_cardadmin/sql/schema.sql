-- =============================================================================
--  ba_cardadmin / sql/schema.sql
--  卡密管理后台 建表脚本（MySQL 5.6.5+ / 5.7 / 8.0 / MariaDB 10.2+）
--  由 install.php 逐条执行；全部 CREATE TABLE IF NOT EXISTS，可重复执行不丢数据。
--  引擎 InnoDB，字符集 utf8mb4。
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ---------------------------------------------------------------------------
-- 管理员
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `admins` (
  `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `username`      VARCHAR(32)  NOT NULL                COMMENT '登录名',
  `pass_hash`     VARCHAR(255) NOT NULL                COMMENT 'password_hash() 生成的 bcrypt',
  `salt`          VARCHAR(32)  NOT NULL DEFAULT ''     COMMENT '先做 hmac-sha256(pass,salt) 再 bcrypt',
  `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login_at` DATETIME     NULL     DEFAULT NULL,
  `last_login_ip` VARCHAR(45)  NULL     DEFAULT NULL,
  `enabled`       TINYINT(1)   NOT NULL DEFAULT 1      COMMENT '1 启用 / 0 禁用',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_admins_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员账号';

-- ---------------------------------------------------------------------------
-- 会话（自定义 token，不用 PHP 原生 session 存储，避免 session 目录不可写）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sessions` (
  `token`      CHAR(64)     NOT NULL                COMMENT '32 字节随机 hex',
  `admin_id`   INT UNSIGNED NOT NULL,
  `created_at` INT UNSIGNED NOT NULL DEFAULT 0      COMMENT 'unix ts',
  `expires_at` INT UNSIGNED NOT NULL DEFAULT 0      COMMENT 'unix ts',
  `ip`         VARCHAR(45)  NOT NULL DEFAULT '',
  `user_agent` VARCHAR(255) NOT NULL DEFAULT '',
  `csrf`       CHAR(32)     NOT NULL DEFAULT ''     COMMENT '本会话的 CSRF token',
  `flash`      TEXT         NULL     DEFAULT NULL   COMMENT '一次性提示消息(JSON)',
  PRIMARY KEY (`token`),
  KEY `idx_sessions_admin`   (`admin_id`),
  KEY `idx_sessions_expires` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录会话';

-- ---------------------------------------------------------------------------
-- 卡密（唯一真源）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `cards` (
  `id`                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `card_key`          VARCHAR(64)  NOT NULL              COMMENT '卡密字符串',
  `status`            ENUM('active','disabled') NOT NULL DEFAULT 'active',
  `expire_at`         INT UNSIGNED NOT NULL DEFAULT 0    COMMENT 'unix ts，0=永不过期',
  `bind_one`          TINYINT(1)   NOT NULL DEFAULT 1    COMMENT '1 只允许一台设备',
  `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by`        VARCHAR(64)  NOT NULL DEFAULT '',
  `note`              VARCHAR(255) NOT NULL DEFAULT '',
  `login_count`       INT UNSIGNED NOT NULL DEFAULT 0,
  `last_login_at`     DATETIME     NULL     DEFAULT NULL,
  `last_login_device` VARCHAR(64)  NULL     DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_cards_card_key` (`card_key`),
  KEY `idx_cards_status`     (`status`),
  KEY `idx_cards_expire`     (`expire_at`),
  KEY `idx_cards_created`    (`created_at`),
  KEY `idx_cards_last_login` (`last_login_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='卡密主表';

-- ---------------------------------------------------------------------------
-- 卡密 - 设备绑定（一对多）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `card_devices` (
  `id`           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `card_id`      INT UNSIGNED NOT NULL,
  `device_id`    VARCHAR(64)  NOT NULL,
  `bound_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_seen_at` DATETIME     NULL     DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_card_devices` (`card_id`, `device_id`),
  KEY `idx_card_devices_device` (`device_id`),
  CONSTRAINT `fk_card_devices_card` FOREIGN KEY (`card_id`) REFERENCES `cards` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='卡密绑定的设备';

-- ---------------------------------------------------------------------------
-- 登录日志（sdk.log 解析 + 平台记录）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `login_logs` (
  `id`        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `card_key`  VARCHAR(64) NOT NULL DEFAULT '',
  `device_id` VARCHAR(64) NOT NULL DEFAULT '',
  `result`    ENUM('ok','reject','expired','device_limit') NOT NULL DEFAULT 'ok',
  `source`    VARCHAR(32) NOT NULL DEFAULT 'sdk.log'  COMMENT 'sdk.log / sdk.log:quick / panel',
  `ts`        INT UNSIGNED NOT NULL DEFAULT 0         COMMENT 'unix ts',
  `raw`       VARCHAR(500) NOT NULL DEFAULT ''        COMMENT '原始日志行',
  `line_hash` CHAR(32)    NOT NULL DEFAULT ''         COMMENT 'md5(ts|raw)，用于去重',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_login_logs_hash`   (`line_hash`),
  KEY `idx_login_logs_ts`     (`ts`),
  KEY `idx_login_logs_card`   (`card_key`),
  KEY `idx_login_logs_device` (`device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录日志';

-- ---------------------------------------------------------------------------
-- 审计日志（所有写操作）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `audit_logs` (
  `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `admin_id`   INT UNSIGNED NULL DEFAULT NULL,
  `admin_name` VARCHAR(64)  NOT NULL DEFAULT '',
  `action`     VARCHAR(64)  NOT NULL DEFAULT ''   COMMENT '如 card.create / card.delete',
  `target`     VARCHAR(255) NOT NULL DEFAULT '',
  `detail`     TEXT         NULL DEFAULT NULL,
  `ip`         VARCHAR(45)  NOT NULL DEFAULT '',
  `ts`         INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_audit_ts`     (`ts`),
  KEY `idx_audit_admin`  (`admin_id`),
  KEY `idx_audit_action` (`action`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='审计日志';

-- ---------------------------------------------------------------------------
-- 设置（k-v）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `settings` (
  `k` VARCHAR(64) NOT NULL,
  `v` TEXT        NULL DEFAULT NULL,
  PRIMARY KEY (`k`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统设置 k-v';

-- ---------------------------------------------------------------------------
-- 登录失败记录（5 次锁 10 分钟，按 IP）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `login_attempts` (
  `id`       BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `ip`       VARCHAR(45) NOT NULL DEFAULT '',
  `username` VARCHAR(32) NOT NULL DEFAULT '',
  `ts`       INT UNSIGNED NOT NULL DEFAULT 0,
  `ok`       TINYINT(1)  NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_attempts_ip_ts`   (`ip`, `ts`),
  KEY `idx_attempts_user_ts` (`username`, `ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录失败/锁定计数';

SET FOREIGN_KEY_CHECKS = 1;
