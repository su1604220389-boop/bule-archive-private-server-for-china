#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ban_message.py —— 封禁文案（Python 侧唯一实现，SDK 用）。

与 PHP 侧 `inc/bans.php` 的 ban_msg() / ban_msg_time() 必须逐字一致
（对照表与机器校验见 CHECK.md §3、selftest_banexp.py 的 T-PARITY 组）：

    永久（bans.until_epoch IS NULL） ->  封禁，请联系客服
    限时（bans.until_epoch = 整数）  ->  封号时间 2026-11-18 20:00 至 2026-11-20 20:00，请联系客服

规则（两端共同约定，改一处必须同时改另一处）：
  1. 时区固定 Asia/Shanghai。它不是"读系统时区"，而是**写死 UTC+8**：
     1991-09-15 之后中国不再有夏令时，所以 2026 年任意时刻
     `timezone(timedelta(hours=8))` 与 `ZoneInfo('Asia/Shanghai')` 逐秒等价，
     但固定偏移不依赖 tzdata（生产机 / 容器里 zoneinfo 常常没有 tzdata 包）。
     PHP 侧对应 `date_default_timezone_set('Asia/Shanghai')` + `date()`。
  2. 时间格式 `%Y-%m-%d %H:%M`（分钟精度）。秒**直接截断**，不四舍五入：
     21:00:59 显示 21:00，21:01:00 显示 21:01。
  3. 起止时间都按绝对时间戳格式化：起点 = bans.created_at（'Y-m-d H:i:s'，Asia/Shanghai），
     终点 = bans.until_epoch。起点缺失/不可解析时，Python 与 PHP 都退化成"起点 = 终点"
     （形状不变，绝不出现空串或 '1970-01-01 08:00'）。
  4. 只依赖标准库；不 import 任何业务模块；任何异常都被吞掉并返回永久文案（绝不抛）。

本模块同时提供 `SdkAdapter` 需要的最小接口：
    ban_message(until_epoch, start_epoch=None) -> str
    ban_message_for_row(row)                   -> str        # row 是 bans 表的一行
    is_active(until_epoch, now=None)           -> bool       # 读侧过期判定
"""

import datetime
import time

# ---------------------------------------------------------------- 常量（两端一致）
TZ_NAME = 'Asia/Shanghai'
TZ_OFFSET_HOURS = 8
TZ_CST = datetime.timezone(datetime.timedelta(hours=TZ_OFFSET_HOURS), TZ_NAME)

TIME_FMT = '%Y-%m-%d %H:%M'          # 只给"封号时间 … 至 …"用
CREATED_FMT = '%Y-%m-%d %H:%M:%S'    # bans.created_at 的落盘格式

MSG_PERMANENT = '封禁，请联系客服'
MSG_TIMED_TMPL = '封号时间 %s 至 %s，请联系客服'


def now_epoch():
    """当前 epoch 秒（整数）。单独抽出来是为了自测能打桩。"""
    try:
        return int(time.time())
    except Exception:
        return 0


def fmt_time(epoch):
    """epoch 秒 -> 'YYYY-MM-DD HH:MM'（Asia/Shanghai / UTC+8，截断到分钟）。绝不抛。"""
    try:
        n = int(epoch)
    except Exception:
        return ''
    try:
        dt = datetime.datetime.fromtimestamp(n, TZ_CST)
    except Exception:
        return ''
    return dt.strftime(TIME_FMT)


def parse_created(value):
    """bans.created_at -> epoch 秒。认三种写法，认不出返回 None（绝不抛）：

      'YYYY-MM-DD HH:MM:SS' / 'YYYY-MM-DDTHH:MM:SS'  -> 按 Asia/Shanghai 解释
      纯数字（字符串或 int）                          -> 直接当 epoch
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except Exception:
            return None
    try:
        s = str(value).strip()
    except Exception:
        return None
    if s == '':
        return None
    if s.isdigit():
        try:
            return int(s)
        except Exception:
            return None
    s2 = s.replace('T', ' ')
    if s2.endswith('Z'):
        s2 = s2[:-1].strip()
    for fmt in (CREATED_FMT, '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S.%f'):
        try:
            dt = datetime.datetime.strptime(s2, fmt).replace(tzinfo=TZ_CST)
            return int(dt.timestamp())
        except Exception:
            continue
    return None


def is_permanent(until_epoch):
    """until_epoch 为空即永久封禁（NULL / '' / 非数字 都算永久）。"""
    if until_epoch is None:
        return True
    if isinstance(until_epoch, bool):
        return True
    if isinstance(until_epoch, str) and until_epoch.strip() == '':
        return True
    try:
        int(until_epoch)
    except Exception:
        return True
    return False


def is_active(until_epoch, now=None):
    """读侧过期判定（与 PHP banexp_is_active / SDK / 桥完全同一条规则）。

        until_epoch IS NULL          -> 永久  -> 封禁中
        until_epoch  > now           -> 限时  -> 封禁中
        until_epoch <= now           -> 已到期 -> **不再封禁**（边界：等于 now 也算过期）
    """
    if is_permanent(until_epoch):
        return True
    try:
        until = int(until_epoch)
    except Exception:
        return True
    cur = now_epoch() if now is None else int(now)
    return until > cur


def ban_message(until_epoch, start_epoch=None):
    """生成给客户端弹窗的封禁文案。绝不抛。

    永久  -> '封禁，请联系客服'
    限时  -> '封号时间 2026-11-18 20:00 至 2026-11-20 20:00，请联系客服'
    """
    try:
        if is_permanent(until_epoch):
            return MSG_PERMANENT
        end = fmt_time(until_epoch)
        if end == '':
            return MSG_PERMANENT
        beg = fmt_time(start_epoch) if start_epoch is not None else ''
        if beg == '':
            beg = end                      # 起点缺失 -> 退化成"起点 = 终点"（与 PHP 一致）
        return MSG_TIMED_TMPL % (beg, end)
    except Exception:
        return MSG_PERMANENT


def ban_message_for_row(row):
    """bans 表的一行（dict / sqlite3.Row / 类似映射）-> 文案。绝不抛。"""
    try:
        until = row['until_epoch'] if row is not None else None
    except Exception:
        until = None
    try:
        created = row['created_at'] if row is not None else None
    except Exception:
        created = None
    return ban_message(until, parse_created(created))


# 语义别名：SDK 里读起来更顺
ban_text = ban_message

__all__ = [
    'TZ_NAME', 'TZ_OFFSET_HOURS', 'TZ_CST', 'TIME_FMT', 'CREATED_FMT',
    'MSG_PERMANENT', 'MSG_TIMED_TMPL',
    'now_epoch', 'fmt_time', 'parse_created', 'is_permanent', 'is_active',
    'ban_message', 'ban_text', 'ban_message_for_row',
]
