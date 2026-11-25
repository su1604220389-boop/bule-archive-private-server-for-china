#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_nick.py -- Account_Nickname (1001) response + AccountDB(22 fields) builder.

Facts (verified 2026-11-14 05:26 from the decrypted client request):
  request plaintext = ,"Nickname":"111","Resendable":false,"Hash":4299262263303,
                       "IsTest":false,"SessionKey":null,"AccountId":0,"OSType":2}
  Hash = (protocol << 32) | counter  ->  4299262263303 >> 32 = 1001  => protocol 1001 CONFIRMED
  Nickname bytes in the request are plain ASCII/UTF-8 (111 -> 31 31 31)

Response body (per lead: type[11900] MX.GameLogic.DBModel.AccountDB, 22 fields):
  long  : ServerId, Exp, RepresentCharacterServerId, MemoryLobbyUniqueId, PublisherAccountId
  DateTime (no tz, ISO): LastConnectTime, BirthDay, CallNameUpdateTime, CreateDate
  omitted (nullable / unknown type): LinkRewardDate, LastReturningDate, Location
"""
import json
from datetime import datetime


def _now_iso():
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def build_accountdb(nickname, callname=None, publisher_account_id=314816420, server_id=2, create_date="2026-01-01T00:00:00"):
    now = _now_iso()
    return {
        "ServerId": server_id,
        "Nickname": nickname,
        "CallName": (callname if callname else nickname),
        "DevId": str(publisher_account_id),
        "State": 1,
        "Level": 1,
        "Exp": 0,
        "Comment": "",
        "LobbyMode": 0,
        "RepresentCharacterServerId": 0,
        "MemoryLobbyUniqueId": 0,
        "LastConnectTime": now,
        "BirthDay": "1970-01-01T00:00:00",
        "CallNameUpdateTime": now,
        "PublisherAccountId": publisher_account_id,
        "RetentionDays": 0,
        "VIPLevel": 0,
        "CreateDate": create_date,
        "UnReadMailCount": 0,
    }


def build_nickname_response(nickname, protocol=1001):
    return {"Protocol": protocol, "AccountDB": build_accountdb(nickname)}


def build_callname_response(callname, nickname="111", protocol=1010):
    return {"Protocol": protocol, "AccountDB": build_accountdb(nickname, callname=callname)}


def build_min_response(protocol):
    """Fallback for protocols we do not implement: same protocol number, valid packet, no 404/empty body."""
    return {"Protocol": int(protocol)}


if __name__ == '__main__':
    print(json.dumps(build_nickname_response("111"), ensure_ascii=False, indent=2))
    print()
    print('fields =', len(build_accountdb("111")))
