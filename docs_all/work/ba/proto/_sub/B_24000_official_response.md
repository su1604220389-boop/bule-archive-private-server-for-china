# B — Official `Academy_GetInfo` (24000) response: byte-exact field characterization

Status: **verified against the official live capture** (国服 `gsqc-api.bluearchive-cn.com`).
Read-only analysis. Nothing outside `work/ba/proto/_sub/` was written.

| item | value |
|---|---|
| primary source | `report\_tmp\official_decoded_201\01_24000_api_academy_getinfo.response.json` |
| second observation | `report\_tmp\official_decoded_201\96_24000_api_academy_getinfo.response.json` |
| raw HAR | `report\_tmp\official201.har` (201 entries, Reqable 3.0.39) |
| capture wall clock | 2026-11-15T20:30:54.980Z = `04:30:54.980` (UTC+8) |
| on-the-wire size (`meta.resp_bytes`) | **17560 B** |
| decrypted inner JSON | **11685 chars / 11685 UTF-8 bytes, pure ASCII** |
| transport wrapper `plain` | 13128 chars, keys `{"protocol","packet","requestid"}` |
| official observations available | **2**, structurally identical, `AcademyDB` payload **byte-identical** |

---

## 1. Top-level structure — exact key order and types

The decrypted inner payload is **exactly 7 top-level keys in this order**:

```
{
  "Protocol"           : int    = 24000
  "SessionKey"         : object {AccountServerId:int, MxToken:str}      # 2 keys, order fixed
  "ServerTimeTicks"    : int    = 639304002548158993                    # .NET ticks
  "ServerNotification" : int    = 0                                     # enum ServerNotificationFlag
  "RequestId"          : str    = "3770c1bc-a631-46fb-a9b6-0421ae2601fe" # uuid v4, lowercase
  "AcademyDB"          : object {AccountId, LastUpdate, ZoneVisitCharacterDBs, ZoneScheduleGroupRecords}  # 4 keys
  "AcademyLocationDBs" : array  [9 x {AccountId, LocationId, Rank, Exp}]
}
```

Verbatim head and tail of the official inner payload:

```json
{"Protocol":24000,"SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"},"ServerTimeTicks":639304002548158993,"ServerNotification":0,"RequestId":"3770c1bc-a631-46fb-a9b6-0421ae2601fe","AcademyDB":{"AccountId":10015354380,"LastUpdate":"2026-11-16T04:00:06.479","ZoneVisitCharacterDBs":{"1":[],"10":[{"UniqueId":10043,"ServerId":3043301,"LastInteractTime":"0001-01-
...
5,"Rank":1,"Exp":0},{"AccountId":10015354380,"LocationId":16,"Rank":2,"Exp":0},{"AccountId":10015354380,"LocationId":17,"Rank":2,"Exp":0},{"AccountId":10015354380,"LocationId":19,"Rank":2,"Exp":200}]}
```

### 1.1 Envelope prefix rule (reusable across all protocols, 109/109 verified)

```
normal response prefix : Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId
Account_Auth (1002)    : Protocol, ServerTimeTicks, ServerNotification, RequestId, SessionKey   <-- SessionKey moved AFTER RequestId
```

108 of 109 decoded responses use the normal prefix; `00_1002_api_account_auth.response.json` is the only
exception (that response *creates* the SessionKey, so it is emitted later). For 24000 use the normal prefix.

### 1.2 `ResponsePacket` base fields that are NOT emitted for 24000

`ServerTimeTicks` and `ServerNotification` are the only `ResponsePacket` base fields present.
These four exist in `dto_schema_academy.json` `wireFields` but are **absent from the official 24000 response**:

```
MissionProgressDBs, EventMissionProgressDBDict, BattlePassMissionProgressDBDict, StaticOpenConditions
```

Across the whole 109-response corpus those four appear 4 / 0 / 0 / 0 times respectively, and never in 24000.
Observed top-level key counts for 24000 are **exactly 7** in both captures. Do not emit the 4 extra fields.

---

## 2. `SessionKey`

```json
{"AccountServerId": 10015354380, "MxToken": "Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"}
```

| sub-key | type | value |
|---|---|---|
| `AccountServerId` | int | `10015354380` |
| `MxToken` | str | `Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA` |

* Key order is `AccountServerId` then `MxToken`. Exactly 2 keys.
* `MxToken` length **64**, charset `A-Za-z0-9/+`, no `=` padding. It **is valid standard base64**
  (`64 % 4 == 0`) and decodes cleanly to **48 bytes**:
  `5638b903f0b2e97d9e9d064a79882b8f1002f0ca110ce093d936f5496d773dc653ab6727c823cf75df35a466f3601280`.
  48 bytes is suggestive of `IV(16) || Key(32)` (the layout this project's transport layer uses elsewhere),
  but that split is **not proven** here — see §14. Regardless: **echo the 64-char string verbatim**; do not re-encode.

### 2.1 Does the response echo the request `SessionKey.MxToken`? — **YES, byte-identical**

```
request  SessionKey = {"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"}
response SessionKey = {"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"}
MxToken byte-identical      : True
AccountServerId identical   : True
```

---

## 3. `ServerTimeTicks`

```
ServerTimeTicks = 639304002548158993
as naive datetime (0001-01-01 epoch) = 2026-11-16T04:30:54.815899
```

* Type **int (JSON number)**, not a string. Plain decimal, no sign, no exponent.
* Semantics: **.NET ticks** (100 ns units since `0001-01-01T00:00:00`) of the server local wall clock
  (`DateTimeKind.Unspecified`, i.e. the UTC+8 local time written as a naive value).
* Evidence: the naive value `04:30:54.815899` sits **165 ms before** the HTTP response start `04:30:54.980` (UTC+8),
  which is exactly the shape of a `DateTime.Now`-style stamp taken at response build time.
* It is **not** UTC (UTC of that instant was `2026-11-15T20:30:54`).

---

## 4. `ServerNotification`

```
ServerNotification = 0        (int, enum ServerNotificationFlag)
```

Both captures: `0`. Must be an int, not a string, not an object.

---

## 5. `RequestId`

```
RequestId = "3770c1bc-a631-46fb-a9b6-0421ae2601fe"      (capture 01_)
RequestId = "90705189-49fe-422f-abef-55bd6a64a28b"      (capture 96_)
```

* **Is it a UUID?** Yes — canonical **UUID v4**, lowercase, 8-4-4-4-12, 36 chars.
  All **109** distinct `RequestId` values in the corpus are `uuid.UUID(...).version == 4`,
  variant nibbles `{8,9,a,b}`, all lowercase, all length 36.
* **Derived from anything?** No. It is not derivable from `Hash`, the request counter, `AccountId`,
  or the request content. The request payload contains **no** RequestId at all, and the value differs
  between the two captures of the same protocol for the same account. It is a server-side random v4 per response.
* **It is load-bearing.** The transport wrapper mirrors it (`plain.requestid == packet.RequestId`), and the
  client sends it back as the **`REQUEST-ID` HTTP header of the next request** — see §9.

---

## 6. `AcademyDB`

Exactly **4 keys, in this order**:

```
AcademyDB {
  "AccountId"                : int      = 10015354380
  "LastUpdate"               : str      = "2026-11-16T04:00:06.479"
  "ZoneVisitCharacterDBs"    : object   { "<ZoneId>": [ {UniqueId, ServerId, LastInteractTime}, ... ] }   # 71 keys
  "ZoneScheduleGroupRecords" : object   {}                                                      # 0 keys, always empty
}
```

### 6.1 `AcademyDB.AccountId`

```
AcademyDB.AccountId = 10015354380
SessionKey.AccountServerId = 10015354380
authenticated AccountServerId (from the 1002 auth response SessionKey) = 10015354380
```

**Equal to the authenticated `AccountServerId`** (10015354380), and equal to `SessionKey.AccountServerId`,
and equal to every `AcademyLocationDBs[].AccountId`. It is **not** an internal DB row id.

### 6.2 `AcademyDB.LastUpdate` — format confirmed exactly

```
"2026-11-16T04:00:06.479"
```

| property | finding |
|---|---|
| pattern | `yyyy-MM-ddTHH:mm:ss.FFFFFFF` (.NET `Json.NET` default `yyyy'-MM-ddTHH':mm:ss.FFFFFFFK`) |
| fraction digit count here | **3** (`.479`) |
| timezone suffix | **NONE** — no `Z`, no `+08:00`. Verified: **0 occurrences** of `Z` or `±hh:mm` anywhere in all 109 decoded responses |
| fraction trimming | trailing zeros **trimmed**; `.03` (2 digits) and `.6` (1 digit) both occur elsewhere in the corpus; when the sub-second part is 0 the fraction is **omitted entirely** (`0001-01-01T00:00:00`) |
| meaning | `04:00:06.479` = the BA daily **04:00 local** reset + 6.479 s → academy DB last refreshed at the daily reset |
| offset vs `ServerTimeTicks` | 1848.337 s earlier |
| capture 96_ | **identical** `2026-11-16T04:00:06.479` |

### 6.3 `AcademyDB.ZoneVisitCharacterDBs` — **it is a JSON OBJECT (map), not an array**

Confirmed on both captures: **`object` with 71 keys**, keys are **decimal strings** of the numeric `ZoneId`,
values are **arrays** of exactly 3-field objects `{UniqueId:int, ServerId:int, LastInteractTime:str}`.

```
"ZoneVisitCharacterDBs":{
  "1":[],                                    <-- EMPTY ARRAY is emitted, key present
  "10":[{"UniqueId":10043,"ServerId":3043301,"LastInteractTime":"0001-01-01T00:00:00"},
        {"UniqueId":20018,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"},
        {"UniqueId":13009,"ServerId":3100950,"LastInteractTime":"0001-01-01T00:00:00"}],
  ...
}
```

**Key order is ORDINAL STRING sort (lexicographic), not numeric.**
`sorted(keys) == keys` is `True`; numeric order would put `"12"` before `"110"`. Observed: `"1","10","11","110","111",...,"117","12","13",...`.
Replicate with `sorted(keys)` over the decimal strings.

Totals: **71 keys / 138 entries / 1 empty key (`"1"`)**. Per-array length range 0..3.
Both captures: identical key set, identical order, identical 138 entries (payload byte-identical).

Numeric zone set (71): `1`, `10–16`, `20–26`, `30–37`, `40–47`, `50–57`, `70–77`, `80–87`, `90–97`, `110–117`.
Note there are **no 60s and no 100s** groups.

#### All 71 keys with cardinality and the first 2 elements verbatim

| key | n | first 2 elements (verbatim) |
|---|---|---|
| `1` | **0** | `[]` (empty array, key present) |
| `10` | 3 | `{"UniqueId":10043,"ServerId":3043301,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20018,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `11` | 3 | `{"UniqueId":20028,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10068,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `110` | 2 | `{"UniqueId":10077,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20022,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `111` | 1 | `{"UniqueId":13000,"ServerId":3043294,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `112` | 3 | `{"UniqueId":10022,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":23006,"ServerId":3104827,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `113` | 3 | `{"UniqueId":20010,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10048,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `114` | 1 | `{"UniqueId":10033,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `115` | 2 | `{"UniqueId":20006,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10078,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `116` | 2 | `{"UniqueId":16003,"ServerId":3002867,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":23005,"ServerId":3043327,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `117` | 2 | `{"UniqueId":10071,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10104,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `12` | 1 | `{"UniqueId":20026,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `13` | 3 | `{"UniqueId":10062,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20009,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `14` | 2 | `{"UniqueId":10118,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":13000,"ServerId":3043294,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `15` | 2 | `{"UniqueId":10114,"ServerId":3104588,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10029,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `16` | 2 | `{"UniqueId":16009,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":26010,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `20` | 2 | `{"UniqueId":13008,"ServerId":3100995,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20030,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `21` | 3 | `{"UniqueId":10062,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10006,"ServerId":3002894,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `22` | 3 | `{"UniqueId":16012,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20017,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `23` | 1 | `{"UniqueId":10011,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `24` | 2 | `{"UniqueId":10052,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10003,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `25` | 3 | `{"UniqueId":10037,"ServerId":3108028,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20000,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `26` | 3 | `{"UniqueId":10096,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10008,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `30` | 3 | `{"UniqueId":20047,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10029,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `31` | 2 | `{"UniqueId":20048,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20000,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `32` | 2 | `{"UniqueId":20040,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":26008,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `33` | 3 | `{"UniqueId":10114,"ServerId":3104588,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":13006,"ServerId":3043306,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `34` | 2 | `{"UniqueId":26010,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10012,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `35` | 1 | `{"UniqueId":10078,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `36` | 1 | `{"UniqueId":20002,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `37` | 1 | `{"UniqueId":10125,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `40` | 3 | `{"UniqueId":16001,"ServerId":3043304,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20014,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `41` | 1 | `{"UniqueId":16005,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `42` | 3 | `{"UniqueId":10047,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10045,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `43` | 2 | `{"UniqueId":10096,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10119,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `44` | 1 | `{"UniqueId":13005,"ServerId":3043299,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `45` | 2 | `{"UniqueId":23005,"ServerId":3043327,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20018,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `46` | 2 | `{"UniqueId":10009,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":23006,"ServerId":3104827,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `47` | 1 | `{"UniqueId":10027,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `50` | 2 | `{"UniqueId":13005,"ServerId":3043299,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10123,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `51` | 1 | `{"UniqueId":10098,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `52` | 2 | `{"UniqueId":20020,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20043,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `53` | 2 | `{"UniqueId":13003,"ServerId":3002868,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10118,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `54` | 1 | `{"UniqueId":13007,"ServerId":3043298,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `55` | 2 | `{"UniqueId":20010,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10018,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `56` | 3 | `{"UniqueId":10016,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10038,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `57` | 2 | `{"UniqueId":20021,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10105,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `70` | 2 | `{"UniqueId":10066,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20013,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `71` | 3 | `{"UniqueId":10108,"ServerId":3135835,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10060,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `72` | 2 | `{"UniqueId":16000,"ServerId":3043296,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10019,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `73` | 2 | `{"UniqueId":13000,"ServerId":3043294,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":20017,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `74` | 1 | `{"UniqueId":10027,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `75` | 2 | `{"UniqueId":20023,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10107,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `76` | 1 | `{"UniqueId":16008,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `77` | 2 | `{"UniqueId":10089,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10068,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `80` | 2 | `{"UniqueId":10061,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10015,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `81` | 2 | `{"UniqueId":20025,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10082,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `82` | 1 | `{"UniqueId":10060,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `83` | 3 | `{"UniqueId":10056,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10002,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `84` | 2 | `{"UniqueId":10008,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10030,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `85` | 1 | `{"UniqueId":10093,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `86` | 3 | `{"UniqueId":10046,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":16009,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `87` | 3 | `{"UniqueId":13012,"ServerId":3105040,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10076,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>…(+1 more) |
| `90` | 2 | `{"UniqueId":10092,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":26012,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `91` | 2 | `{"UniqueId":16008,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10044,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `92` | 1 | `{"UniqueId":10028,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `93` | 2 | `{"UniqueId":20035,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10025,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `94` | 1 | `{"UniqueId":10014,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `95` | 2 | `{"UniqueId":26006,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}`<br>`{"UniqueId":10013,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `96` | 1 | `{"UniqueId":13003,"ServerId":3002868,"LastInteractTime":"0001-01-01T00:00:00"}` |
| `97` | 1 | `{"UniqueId":20023,"ServerId":0,"LastInteractTime":"0001-01-01T00:00:00"}` |

Element field notes:

| field | type | observed |
|---|---|---|
| `UniqueId` | int | character UniqueId (e.g. `10043`, `20018`, `3043301`-style ids appear in `ServerId`) |
| `ServerId` | int | per-account character ServerId; **`0` means "not owned on this account"**; non-zero values like `3043301` are owned characters |
| `LastInteractTime` | str | **always the sentinel `0001-01-01T00:00:00`** (DateTime.MinValue) in all 138 entries of both captures |

### 6.3.1 Derived facts for seeding (computed from the 138 entries)

* **107 distinct `UniqueId`s** across the 138 entries — the same character appears in several zones
  (e.g. `UniqueId 13000` in zones `14`, `73`, `111`; `UniqueId 10062` in zones `13`, `21`).
* `ServerId` is a **deterministic function of `UniqueId`**: 0 of 107 `UniqueId`s had conflicting `ServerId`s.
  So a seed table keyed by `UniqueId` is sufficient.
* **19** `UniqueId`s carry a non-zero `ServerId` (i.e. are "owned"); the other **88** are always `ServerId: 0`:

```
UniqueId 10006  -> ServerId 3002894
UniqueId 10037  -> ServerId 3108028
UniqueId 10043  -> ServerId 3043301
UniqueId 10108  -> ServerId 3135835
UniqueId 10114  -> ServerId 3104588
UniqueId 13000  -> ServerId 3043294
UniqueId 13003  -> ServerId 3002868
UniqueId 13005  -> ServerId 3043299
UniqueId 13006  -> ServerId 3043306
UniqueId 13007  -> ServerId 3043298
UniqueId 13008  -> ServerId 3100995
UniqueId 13009  -> ServerId 3100950
UniqueId 13012  -> ServerId 3105040
UniqueId 16000  -> ServerId 3043296
UniqueId 16001  -> ServerId 3043304
UniqueId 16003  -> ServerId 3002867
UniqueId 23005  -> ServerId 3043327
UniqueId 23006  -> ServerId 3104827
UniqueId 26001  -> ServerId 3043295
```

* `UniqueId` range `10002 … 26012`, bucketed by ten-thousands:
  `10000s: 58`, `13000s: 8`, `16000s: 8`, `20000s: 26`, `23000s: 2`, `26000s: 5`.

### 6.4 `AcademyDB.ZoneScheduleGroupRecords` — an EMPTY OBJECT

```json
"ZoneScheduleGroupRecords":{}
```

* Type **object with 0 keys** — emitted as `{}`, **not** `[]`, **not** `null`, **not** omitted.
* Both captures: `{}`. `observed_empty_only = true`.
* **Inner shape: 未找到 (unverified).** No capture exists with a non-empty value, so the true key/value type
  cannot be confirmed from traffic. `dto_schema_academy.json` claims `Dictionary<long, List<long>>`;
  that is *consistent* with `{}` but is **not proven** by this evidence.
* For byte-matching, emitting `{}` is safe; emitting a list is **not**.

---

## 7. `AcademyLocationDBs` — an ARRAY (not a map)

**`array` of 9 objects**, each with exactly 4 keys in order `AccountId, LocationId, Rank, Exp`.

```json
[{"AccountId": 10015354380, "LocationId": 1, "Rank": 2, "Exp": 0}, {"AccountId": 10015354380, "LocationId": 7, "Rank": 1, "Exp": 0}]
...
```

Full 9-element list, verbatim:

```json
[0] {"AccountId":10015354380,"LocationId":1,"Rank":2,"Exp":0},
[1] {"AccountId":10015354380,"LocationId":7,"Rank":1,"Exp":0},
[2] {"AccountId":10015354380,"LocationId":11,"Rank":1,"Exp":0},
[3] {"AccountId":10015354380,"LocationId":12,"Rank":2,"Exp":0},
[4] {"AccountId":10015354380,"LocationId":13,"Rank":1,"Exp":0},
[5] {"AccountId":10015354380,"LocationId":15,"Rank":1,"Exp":0},
[6] {"AccountId":10015354380,"LocationId":16,"Rank":2,"Exp":0},
[7] {"AccountId":10015354380,"LocationId":17,"Rank":2,"Exp":0},
[8] {"AccountId":10015354380,"LocationId":19,"Rank":2,"Exp":200}
```

| field | type | observed values |
|---|---|---|
| `AccountId` | int | always `10015354380` |
| `LocationId` | int | `1, 7, 11, 12, 13, 15, 16, 17, 19` (9 distinct, ascending, order preserved) |
| `Rank` | int | `{1, 2}` |
| `Exp` | int | `{0, 200}` — only `LocationId 19` has `Exp=200` |

Capture 96_ is identical (same 9 `LocationId`s, same order, same values).

---

## 8. Empty-collection vs missing-key policy (official encoder behaviour)

| location | official emits | note |
|---|---|---|
| `AcademyDB.ZoneScheduleGroupRecords` (empty object) | **`{}` — EMITTED** | empty objects are emitted, not omitted |
| `AcademyDB.ZoneVisitCharacterDBs["1"]` (empty array) | **`[]` — EMITTED** | empty arrays are emitted |
| `MissionProgressDBs` / `EventMissionProgressDBDict` / `BattlePassMissionProgressDBDict` / `StaticOpenConditions` | **OMITTED** | never appear in 24000 (0 occurrences at 24000 top level) |

**Precise list of every empty collection inside the official 24000 response:**

```
1. AcademyDB.ZoneScheduleGroupRecords                     = {}   (empty object, 0 keys)
2. AcademyDB.ZoneVisitCharacterDBs["1"]                  = []   (empty array)
```

That is the **complete** set — `AcademyLocationDBs` has 9 elements and no zone array other than `"1"` is empty.

Conclusion for the encoder: emit `{}` and `[]` where they occur, and **do not** invent the four `ResponsePacket`
fields. The 24000 key count must be exactly **7**.

---

## 9. `RequestId` ↔ HTTP header `REQUEST-ID` chaining rule (critical)

**The rule:**

```
response_N.RequestId   ==   request_{N+1}.HTTP header REQUEST-ID
```

i.e. the client **stores the last API response's `RequestId` and sends it as the `REQUEST-ID` header on its
next API request**. It is **not** the current request's id (requests carry no id) and **not** the value of the
request's own response.

Proof: **108 MATCH / 0 MISMATCH** over every API request whose preceding API response was decoded.
`hdr == own response RequestId` is **0 occurrences**.

Literal evidence for the four requested endpoints (HAR order, UTC+8):

| # | bj time | path | request `REQUEST-ID` header | that response's payload `RequestId` | verdict |
|---|---|---|---|---|---|
| 50 | 04:30:54.662 | `/api/account/auth` | **(ABSENT)** | `f24daa29-45e0-4ecb-99bc-6d0ed3bd7c4e` | first request of session, nothing to chain |
| 51 | 04:30:54.980 | `/api/academy/getinfo` (24000) | `f24daa29-45e0-4ecb-99bc-6d0ed3bd7c4e` | `3770c1bc-a631-46fb-a9b6-0421ae2601fe` | **MATCH** (= auth response) |
| 53 | 04:30:55.110 | `/api/account/loginsync` (1017) | `3770c1bc-a631-46fb-a9b6-0421ae2601fe` | `bef95b60-6b60-419a-8844-d81f61ca0e05` | **MATCH** (= 24000 response) |
| 56 | 04:30:55.460 | `/api/item/list` (4000) | `bef95b60-6b60-419a-8844-d81f61ca0e05` | `60a4ba54-2169-4eca-bbed-fe40c95034ac` | **MATCH** (= 1017 response) |
| 182 | 04:34:11.018 | `/api/academy/getinfo` (24000, 2nd) | `3f79cd64-900b-4743-abd8-bab7f94a7e4f` | `90705189-49fe-422f-abef-55bd6a64a28b` | **MATCH** (= 2nd-session `/api/management/data` response) |

Reading it as a chain (literal UUIDs):

```
1002 auth            REQ hdr: (none)                                RES RequestId: f24daa29-45e0-4ecb-99bc-6d0ed3bd7c4e
24000 getinfo        REQ hdr: f24daa29-45e0-4ecb-99bc-6d0ed3bd7c4e   RES RequestId: 3770c1bc-a631-46fb-a9b6-0421ae2601fe
1017 loginsync       REQ hdr: 3770c1bc-a631-46fb-a9b6-0421ae2601fe   RES RequestId: bef95b60-6b60-419a-8844-d81f61ca0e05
4000 item/list       REQ hdr: bef95b60-6b60-419a-8844-d81f61ca0e05   RES RequestId: 60a4ba54-2169-4eca-bbed-fe40c95034ac
3    networktime     REQ hdr: 60a4ba54-2169-4eca-bbed-fe40c95034ac   RES RequestId: d1d5579c-9c2b-44e6-a496-c66d4ccca10c
```

Corollaries:

1. The **first** Shittim API request of a session (`1002`) has **no** `REQUEST-ID` header.
2. Non-Shittim traffic interleaved between API calls (`/daq/track/v2`, `/event`, `/logstores/...`) carries **no**
   `REQUEST-ID` header — the chain is defined over Shittim API responses only, and the client skips over those.
3. `/api/health`, `/api/state`, `/api/open/red_point` are not part of this chain (no header).
4. `EO-LOG-UUID` in the response headers is unrelated (an 18–20 digit decimal logging id, different per entry).
5. Our server **must** emit a fresh UUIDv4 `RequestId` in **every** API response, otherwise the client has
   nothing to put in the next `REQUEST-ID` header and the follow-up request never fires.

Machine-readable per-entry evidence: `B_har_requestid_chain.json`.

---

## 10. Byte-level encoding notes

| # | property | finding (verified) |
|---|---|---|
| 1 | separators | `,` and `:` with **no whitespace** — `", "` absent, `": "` absent, no newline / tab / CR |
| 2 | size | 11685 chars == 11685 UTF-8 bytes == pure ASCII (`raw.isascii() == True`) |
| 3 | key order | insertion order exactly as documented above; `json.dumps(obj, separators=(",",":"))` with the captured order reproduces the packet **byte-for-byte** (`== raw` is `True`) |
| 4 | `sort_keys=True` | **breaks** byte-exactness (`== raw` is `False`) — do not sort |
| 5 | integers | plain decimal, no `+`, no exponent, no thousands separator; **all 595 numeric literals are non-negative**; no float literals (the single `.` in a number-looking match is inside the `LastUpdate` date string) |
| 6 | dates | `yyyy-MM-ddTHH:mm:ss[.FFFFFFF]`, no timezone suffix, fraction trailing-zero-trimmed and omitted when 0 |
| 7 | `null` | **no `null` anywhere** in the 24000 payload; no key is null |
| 8 | escaping | no `\uXXXX` escapes; the payload contains no characters needing escaping |
| 9 | map keys | always quoted decimal strings (`"1"`, `"110"`), never bare numbers |
| 10 | booleans | none present in 24000 |
| 11 | wire vs inner | `meta.resp_bytes = 17560` (post-encryption/compression on the wire) vs 11685 B of inner JSON; 0 terminators; first byte `{`, last two `]}` |

Minimal reference builder that reproduces the byte stream:

```python
import json, uuid, datetime
inner = {
    "Protocol": 24000,
    "SessionKey": {"AccountServerId": ACCOUNT, "MxToken": MX_TOKEN},          # echo request verbatim
    "ServerTimeTicks": int((datetime.datetime.now() - datetime.datetime(1,1,1)).total_seconds() * 10**7),
    "ServerNotification": 0,
    "RequestId": str(uuid.uuid4()),                                          # lowercase uuid4
    "AcademyDB": {
        "AccountId": ACCOUNT,
        "LastUpdate": "2026-11-16T04:00:06.479",       # yyyy-MM-ddTHH:mm:ss.FFF, no tz, .FFF trimmed
        "ZoneVisitCharacterDBs": ZONES,                # dict: str(zoneId) -> [ {UniqueId,ServerId,LastInteractTime} ]
        "ZoneScheduleGroupRecords": {},                # always an empty OBJECT
    },
    "AcademyLocationDBs": LOCS,                        # list of {AccountId,LocationId,Rank,Exp}
}
payload = json.dumps(inner, separators=(",", ":"), ensure_ascii=False)   # do NOT sort_keys
```

Zone dict ordering must be `dict(sorted(ZONES.items()))` on the **string** keys.

---

## 11. Comparison against the repo spec sources

Legend: ✅ covers · ⚠️ partial / wrong type · ❌ absent

### 11.1 `work\ba\proto\dto_schema_academy.json`

```
AcademyGetInfoResponse  tdIndex=10683  protocol=24000  base=ResponsePacket
  AcademyDB            : AcademyDB                        (object)
  AcademyLocationDBs   : List<AcademyLocationDB>          (list)
AcademyDB               tdIndex=11892  fieldCount=3
  LastUpdate           : DateTime
  ZoneVisitCharacterDBs: unknown      kind=list     ti=10463  conf=guess  src=none
  ZoneScheduleGroupRecords : Dictionary<long, List<long>>  kind=dict  ti=10425  conf=vote
AcademyLocationDB       tdIndex=11893  fieldCount=3
  LocationId, Rank, Exp : long
```

| official field | covered? | detail |
|---|---|---|
| `Protocol` | ✅ | envelope |
| `SessionKey` (+2 sub) | ❌ | injected by transport, not in this schema — fine, but must be added by the packet writer |
| `ServerTimeTicks`, `ServerNotification` | ✅ | via `ResponsePacket` base |
| `RequestId` | ❌ | not modelled (transport-level) |
| `AcademyDB` | ⚠️ | present but **fieldCount=3, missing `AccountId`** |
| `AcademyDB.AccountId` | ❌ | **MISSING — key must be added** |
| `AcademyDB.LastUpdate` | ✅ | `DateTime`, correct |
| `AcademyDB.ZoneVisitCharacterDBs` | ❌ | **TYPE MISMATCH: `kind=list`, type `unknown` — official is an OBJECT/map** |
| `AcademyDB.ZoneScheduleGroupRecords` | ⚠️ | `kind=dict` consistent with `{}`, inner type unproven |
| `AcademyLocationDBs` | ✅ | `list`, correct |
| `AcademyLocationDBs[].AccountId` | ❌ | **MISSING — fieldCount=3** |
| `…[].LocationId/Rank/Exp` | ✅ | `long`, correct |
| `MissionProgressDBs` etc. (4 fields in `wireFields`) | ⚠️ | present in `wireFields` but **must not be emitted** for 24000 |

The `unknown`/`ti=10463` on `ZoneVisitCharacterDBs` is the root of the list-vs-map error: `type_index_map.json`
has **no entry for `10463`** (`ti 10463 -> null`), so the type could not be resolved and `kind` defaulted to `list`.

> Same two omissions exist in `dto_schema_full.json` and `dto_schema_lobby.json` (`AcademyDB` and
> `AcademyLocationDB` there are also missing `AccountId`). Since it is missing from *all three* generated
> schemas, the likely cause is unresolved **base-class field inheritance** in metadata extraction
> (an `AccountId` inherited from a base DB type), not a per-type transcription slip. *(inference)*

### 11.2 `work\ba\proto\academy_24000_official.json`

This template is **structurally correct and complete** — it already contains `AccountId`, the dict-shaped
`ZoneVisitCharacterDBs` with all 71 zones, `ZoneScheduleGroupRecords: {}`, and the 9 `AcademyLocationDBs` elements.
Deep-diff vs the official packet:

```
top-level key order identical           : True
AcademyDB key order identical           : True
ZoneVisit 71 keys, same order           : True    payload json-equal : True
ZoneScheduleGroupRecords                : {} == {}
AcademyLocationDBs 9 elements           : same LocationIds/order; only AccountId differs (placeholder)
```

| official field | covered? | detail |
|---|---|---|
| `SessionKey` | ❌ **TYPE MISMATCH** | value is the **string** `"__SESSION_KEY__"`; official is an **object** `{AccountServerId, MxToken}` |
| `ServerTimeTicks` | ❌ **TYPE MISMATCH** | value is the **string** `"__TICKS__"`; official is an **int** |
| `RequestId` | ❌ **TYPE MISMATCH** | value is the **string** `"__REQUEST_ID__"` — correct JSON type (str) but not a UUID; must be replaced by a real lowercase v4 |
| `AcademyDB.AccountId` / `AcademyLocationDBs[].AccountId` | ⚠️ | placeholder `"__ACCOUNT_ID__"` is a **string**; must become an **int** (`10015354380` in the capture) |
| every other official field | ✅ | exact |

**So the template is safe only if the placeholders are substituted with the right JSON *types*.**
Naive string substitution would emit `"SessionKey":"..."`, `"ServerTimeTicks":"..."` and `"AccountId":"..."`,
which will not deserialize into the client's `SessionKey` object / `long` / `long` fields.

### 11.3 `work\ba\proto\official_spec.json` → `protocols["24000"]`

**Best source in the repo — full and correct.** Generated `2026-11-16T04:54:28+08:00` from the same HAR,
`observations: 2`, `confidence: medium`, and it agrees with this analysis on every point:

```
top_key_order        = [Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, AcademyDB, AcademyLocationDBs]
top_key_order_stable = true
SessionKey           = object, 2 keys  (AccountServerId:int, MxToken:str)
AcademyDB            = object, 4 keys  (AccountId, LastUpdate, ZoneVisitCharacterDBs, ZoneScheduleGroupRecords)
ZoneVisitCharacterDBs= type "map", key_kind "int_str", 71 keys, entries_observed 142,
                        value = array(len 0..3) of object{UniqueId,ServerId,LastInteractTime}
ZoneScheduleGroupRecords = object, key_count 0..0, observed_empty_only true,
                        note "always empty {} , inner shape unknown"
AcademyLocationDBs   = array, len 9, items object 4 keys {AccountId,LocationId,Rank,Exp}
```

Only caveat: it is a *schema* (`values_included: false`), so it carries types/cardinalities but not the literal
sample values; and its `confidence` is `medium` because only 2 observations exist.
**Recommendation: treat `official_spec.json` as the type authority and `academy_24000_official.json` as the value template.**

### 11.4 `work\ba\proto\shittim_types.json`

```
AcademyGetInfoResponse : [["AcademyDB","AcademyDB?"], ["AcademyLocationDBs","List<AcademyLocationDB>?"]]
AcademyDB              : NOT PRESENT
AcademyLocationDB      : NOT PRESENT
ResponsePacket         : NOT PRESENT
```

| official field | covered? | detail |
|---|---|---|
| `AcademyGetInfoResponse` 2 own fields + `?` nullability | ✅ | matches (both emitted non-null) |
| `AcademyDB` internals | ❌ | `AcademyDB` type is not defined at all → **no coverage** of `ZoneVisitCharacterDBs` / `ZoneScheduleGroupRecords` / `AccountId` |
| `AcademyLocationDB` internals | ❌ | not defined → no coverage of `AccountId` |

This is a *C# field list* source only; it cannot settle list-vs-map questions for these nested DB types.

### 11.5 `work\ba\proto\type_index_map.json`

A `ti → type name` resolver (35105 entries). Relevant lookups:

```
ti 34953 -> {"name":"AcademyDB", "full":"MX.GameLogic.DBModel.AcademyDB", "td":11892}   RESOLVES
ti 10463 -> null   <-- ZoneVisitCharacterDBs field type: UNRESOLVED  (root cause of the list/map error)
ti 10425 -> null   <-- ZoneScheduleGroupRecords field type: UNRESOLVED
ti 21273 -> null   <-- AcademyLocationDBs field type: UNRESOLVED
ti 10683 -> null   <-- AcademyGetInfoResponse: UNRESOLVED
```

So `type_index_map.json` **cannot** validate any of the three contested field shapes; the `List<...>`/`Dictionary<...>`
bindings in `dto_schema_academy.json` rest on the `shittim-vote` corpus, not on this resolver. No official 24000
field is covered by it beyond the `AcademyDB` class name.

### 11.6 `work\ba\proto\protocol_map.json`

```
"Academy_GetInfo": {"dto_match":"exact/exact", "id":24000, "req":"AcademyGetInfoRequest",
                   "resp":"AcademyGetInfoResponse", "segment":"Academy",
                   "token":"KKVAEXLS5QIIB36RQW27XRTJGI", "encoding":"u16+block0"}
```

| item | finding |
|---|---|
| protocol number 24000 | ✅ matches the official `Hash >> 32` (`103079215104002 >> 32 == 24000`) |
| request/response DTO names | ✅ match the official envelope (`plain.protocol == "Academy_GetInfo"`) |
| `token` | ✅ `KKVAEXLS5QIIB36RQW27XRTJGI` — identical to the `protocol` form field captured in the official HAR for `/api/academy/getinfo` |
| field-level coverage | ❌ none (it is a routing table, not a schema) |

> Note: `protocol_map.json` also records `Account_LoginSync → id 1017` and `Account_RequestBirthdayMail → id 1019`,
> which matches the official capture (`loginsync` request `Hash = 4367981740035`, `>> 32 == 1017`).
> This **contradicts** the `corrections` entry inside `work\ba\proto\observed_sequence.json`, which asserts
> *"Account_LoginSync = 1019; 1017 = Account_DismissRepurchasablePopup"*. The official traffic says **1017**.
> See §13.

### 11.7 `work\ba\server\prototype\_scratch\_1017_schema.txt`

This is the aggregate schema of the **1017 `Account_LoginSync`** response (a wrapper whose children are nested
`*Response` objects). Grep results:

```
"Academy"            : 1 occurrence  (incidental, not a field)
"AcademyDB"          : 0 occurrences
"ZoneVisit"          : 0 occurrences
"24000"              : 0 occurrences
"MissionProgressDBs" : 0 occurrences
```

| official 24000 field | covered? | detail |
|---|---|---|
| all of them | ❌ | **zero coverage** of any 24000 / Academy field |
| *(useful indirect evidence)* | ✅ | each nested `*Response` in it carries the same 5-key envelope `Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId` |
| *(useful indirect evidence)* | ✅ | confirms the official encoder **does emit empty collections** elsewhere (`TSSCharacterDBs: []`, `WeaponDBs: []`, `ExpiredCurrency: {}`, `SweepPointByRaidUniqueId: {}`) — consistent with §8 |

---

## 12. Consolidated list of type / coverage problems found

| # | file | problem | severity |
|---|---|---|---|
| 1 | `dto_schema_academy.json` | `AcademyDB` missing `AccountId` (fieldCount 3, official 4) | **high** |
| 2 | `dto_schema_academy.json` | `AcademyDB.ZoneVisitCharacterDBs` `kind=list`, `type=unknown` — official is an **object/map** | **critical** |
| 3 | `dto_schema_academy.json` | `AcademyLocationDB` missing `AccountId` (fieldCount 3, official 4) | **high** |
| 4 | `dto_schema_academy.json` | `AcademyGetInfoResponse.wireFields` lists 4 `ResponsePacket` fields not emitted by 24000 | medium |
| 5 | `academy_24000_official.json` | `SessionKey` is a **string** placeholder, must be an **object** | **critical** |
| 6 | `academy_24000_official.json` | `ServerTimeTicks` is a **string** placeholder, must be an **int** | **critical** |
| 7 | `academy_24000_official.json` | `AccountId` placeholders are strings, must be **ints** | **critical** |
| 8 | `shittim_types.json` | `AcademyDB` / `AcademyLocationDB` types absent → no nested-shape coverage | medium |
| 9 | `type_index_map.json` | `ti 10463 / 10425 / 21273 / 10683` all resolve to `null` → cannot validate the contested shapes | medium |
| 10 | `_1017_schema.txt` | zero coverage of 24000 / Academy | low (out of scope by design) |
| 11 | `observed_sequence.json` `corrections` | claims `Account_LoginSync = 1019`; official traffic and `protocol_map.json` both say **1017** (`1019 = Account_RequestBirthdayMail`) | **high** (mis-routes the post-24000 hop) |
| 12 | `gen_academy.py` `--check` | self-test **enforces the wrong shapes**: asserts `ZoneVisitCharacterDBs` **is a list**, `AcademyDB` key set is exactly the 3 old keys, top-level key count `>= 9`, and that the 4 non-emitted `ResponsePacket` fields are present — all four assertions contradict the official capture, so a correct fix would make `--check` FAIL | **critical** |

Entries 1–3 also hold for `dto_schema_full.json` and (for `AcademyLocationDB`) `dto_schema_lobby.json`.

---

## 13. What this means for the 24000 gate (actionable)

Our 24000 reply at the time of the failure was the minimal generic envelope
`{"Protocol":24000}` — **1 key**, vs the official **7 keys** (source:
`work\ba\proto\observed_sequence.json`, `last_request_before_sync_error.our_reply`:
`{"inner_keys": 1, "inner_json": "{\"Protocol\":24000}", "gen_kind": "min"}`).

Concretely missing / wrong:

1. `SessionKey` — absent. Must be an **object** echoing the request's `AccountServerId` + `MxToken` byte-identically.
2. `ServerTimeTicks` — absent. Must be an **int** (.NET ticks of local wall clock).
3. `ServerNotification` — absent. Must be `0`.
4. `RequestId` — absent. Must be a fresh lowercase **UUID v4**; it is then required as the `REQUEST-ID`
   header of the next request (§9), so without it the client cannot legally issue the follow-up `1017`.
5. `AcademyDB` — absent, and our state has **no `academy` key at all** (`account_state.seeded.json`), so there is
   no source for `AccountId` / `LastUpdate` / `ZoneVisitCharacterDBs` / `ZoneScheduleGroupRecords`.
6. `AcademyLocationDBs` — absent; needs 9 `{AccountId, LocationId, Rank, Exp}` elements.

Two independent owner-side items to fix before a byte-match is even possible:

* the **schema** says `ZoneVisitCharacterDBs` is a list and omits both `AccountId` fields (problems 1–3 above);
* the **template** `academy_24000_official.json` is value-correct but its `SessionKey` / `ServerTimeTicks` /
  `AccountId` placeholders are strings and will serialize with the wrong JSON type.

---

## 14. Explicitly NOT verified (未找到)

| claim | status |
|---|---|
| internal shape of a **non-empty** `ZoneScheduleGroupRecords` | **未找到** — always `{}` in both captures; `Dictionary<long,List<long>>` is unproven |
| why exactly our client stopped after 24000 (client-side NRE vs guard) | **unverified** — no client-side log/stack in this workspace proves the failing read; the error text `通知 / 同步账户信息时发生错误` at ~8 s is only consistent with a failure inside the sync path |
| whether the client would accept a *different* `LastUpdate` value | **unverified** — only one value observed (`2026-11-16T04:00:06.479`) in both captures |
| whether the 71-zone key set is account-independent (i.e. a fixed zone table) | **unverified** — only one account captured |
| whether `ServerTimeTicks` must be the *local* (UTC+8) wall clock vs any monotonic clock | **inference**, not proven — it matches local wall clock to within 165 ms, but a single sample cannot exclude other clocks |
| `MxToken` underlying encoding | **partially verified** — it is valid base64 (64 chars → **48 bytes**, hex `5638b903…f3601280`), but whether those 48 bytes are `IV(16)\|\|Key(32)` (or something else) is **未找到**; no capture proves the internal split. Treat the 64-char string as opaque and echo it verbatim |

---

## 15. Reproduction

All numbers in this document were produced by read-only scripts in this directory:

```
_dump_24000.py     unwrap meta -> plain -> packet
_struct_24000.py   full path/type/cardinality table          -> _struct_out.txt
_card_24000.py     per-collection cardinality + samples       -> _card_out.txt
_compare_24000.py  request vs response, MxToken echo, Hash decode -> _cmp_out.txt
_deepdiff.py       template vs official deep diff             -> _deepdiff_out.txt
_dtfmt.py          DateTime format census + ticks math        -> _dtfmt_out.txt
_bytes.py          byte-level encoding facts                  -> _bytes_out.txt
_envelope.py       envelope census + 2-capture compare        -> _envelope_out.txt
_har_chain4.py     provenance chain, UUID version, request scan -> _har_chain4_out.txt
_gen_matrix.py     emits B_24000_field_matrix.json
_gen_chain.py      emits B_har_requestid_chain.json
(this document was assembled by a one-shot generator; the 11 scripts above are the
re-runnable evidence base, and every number quoted here is reproducible from them)
```

Sibling machine-readable deliverables: `B_24000_field_matrix.json`, `B_har_requestid_chain.json`.

*Generated 2026-11-16T05:06:26+08:00. Official packet reproduced byte-exactly with `json.dumps(..., separators=(",",":"))` and insertion order.*
