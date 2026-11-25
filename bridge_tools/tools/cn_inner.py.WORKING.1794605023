#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_inner.py -- Account_Auth inner JSON, 26-key spec (report/49).

Outer envelope (handled by cn_wire):  {"protocol":"Account_Auth","packet":"<this inner, serialised>","requestid":"<guid>"}
Inner (this module):                 {"Protocol":1002, ...20 CN DTO props..., ...6 ResponsePacket base..., "_probe":...}

Note the two-layer casing difference:
  outer "protocol" : lowercase, string NAME   ("Account_Auth")
  inner "Protocol" : uppercase, integer       (1002; the real Error sample used -1)
"""
import json
import os
from datetime import datetime

CANARY = 'ZZCANARY7391QKVB'

STATIC_OPEN_CONDITIONS = {
    "Academy": 0, "Arena": 0, "Billing": 0, "Cafe": 0, "Cafe_2": 0,
    "Cafe_Invite": 0, "Cafe_Invite_2": 0, "Campaign": 0, "Clan": 0, "Craft": 0,
    "Echelon": 0, "EliminateRaid": 0, "Equip": 0, "EventContent": 0, "EventMiniGame_1": 0,
    "EventPermanent": 0, "EventStage_1": 0, "EventStage_2": 0, "Gacha": 0, "GuideMission": 0,
    "Item": 0, "LobbyIllust": 0, "Main_L_1_2": 0, "Main_L_1_3": 0, "Main_L_1_4": 0,
    "Main_L_1_5": 0, "MiniGameCCG": 0, "MiniGameDefense": 0, "MinigameDreamMaker": 0, "Mission": 0,
    "Mulligan": 0, "MultiFloorRaid": 0, "None": 0, "Raid": 0, "Schedule": 0,
    "SchoolDungeon": 0, "ShiftingCraft": 0, "Shop": 0, "Shop_Gem": 0, "Story": 0,
    "Story_Replay": 0, "Story_Sub": 0, "StrategySkip": 0, "Student": 0, "Tactic_Skip": 0,
    "Tactic_Speed": 0, "Talk": 0, "TimeAttackDungeon": 0, "Unit_Growth_LevelUp": 0, "Unit_Growth_Skill": 0,
    "Unit_Growth_Transcendence": 0, "WeekDungeon": 0, "WeekDungeon_Chase": 0,
    "__Deprecated_WeekDungeon_Blood": 0, "__Deprecated_WeekDungeon_FindGift": 0,
}


def ticks(dt=None):
    """C# DateTime.Ticks: 100ns units since 0001-01-01, server local time (UTC+8)."""
    dt = dt or datetime.now()
    return int((dt - datetime(1, 1, 1)).total_seconds()) * 10_000_000 + dt.microsecond * 10


def iso(dt=None):
    """Real-sample format: yyyy-MM-ddTHH:mm:ss (no tz, no millis)."""
    return (dt or datetime.now()).strftime("%Y-%m-%dT%H:%M:%S")


def build(publisher_account_id=314816420, server_id=2, with_canary=True):
    now = datetime.now()
    inner = {
        # packet header
        "Protocol": 1002,
        # ResponsePacket base (6)
        "ServerTimeTicks": ticks(now),
        "ServerNotification": 0,
        "MissionProgressDBs": [],
        "EventMissionProgressDBDict": {},
        "BattlePassMissionProgressDBDict": {},
        "StaticOpenConditions": dict(STATIC_OPEN_CONDITIONS),
        # AccountAuthResponse own props (20 minus FunctionClose which is intentionally omitted)
        "CurrentVersion": 446690,
        "MinimumVersion": 0,
        "IsDevelopment": False,
        "BattleValidation": False,
        "UpdateRequired": False,
        "TTSCdnUri": "https://ba.dn.nexoncdn.co.kr/tts/version2/",
        "AccountDB": {
            "ServerId": server_id,
            "Nickname": "",
            "State": 1,
            "Level": 1,
            "RepresentCharacterServerId": 9,
            "LastConnectTime": iso(now),
            "PublisherAccountId": publisher_account_id,
            "RetentionDays": 0,
            "CreateDate": iso(now),
        },
        "RepurchasableMonthlyProductCountDBs": [],
        "MonthlyProductParcel": [],
        "MonthlyProductMail": [],
        "BiweeklyProductParcel": [],
        "BiweeklyProductMail": [],
        "WeeklyProductParcel": [],
        "WeeklyProductMail": [],
        "IssueAlertInfos": [],
        "DailyRecordDBs": [],
        "OptionDB": {},
        "AccountLimitedFlashSaleDBs": [],
        "Desc": "",
        # FunctionClose intentionally NOT written (type unknown; wrong type breaks the whole object)
    }
    if with_canary:
        inner["_probe"] = CANARY
    return inner


if __name__ == '__main__':
    d = build()
    s = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
    print('keys      =', len(d))
    print('json len  =', len(s.encode('utf-8')))
    print('has _probe=', d.get('_probe'))
    print('FunctionClose present =', 'FunctionClose' in d)
    print('SessionKey present    =', 'SessionKey' in d)
    print('EncryptedUID present  =', 'EncryptedUID' in d)
    print('ServerTimeTicks       =', d['ServerTimeTicks'])
    print('--- json ---')
    print(s)
