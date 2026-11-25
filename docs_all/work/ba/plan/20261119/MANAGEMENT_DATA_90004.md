# 协议 90004 `Management_Data` 官方抓包 vs 我方 stub —— 只读比对

- 生成时间：2026-11-19 02:0x（Asia/Shanghai）
- 作业性质：**只读比对**。不联网、不碰服务器、未修改任何已有文件；本文件是唯一新增文件。
- 比对对象：`report\_tmp\official_decoded_201\` 里 10 条官方 90004 明文 + `report\_tmp\最全的一个.har` + 我方 bridge 源码
- 被核对的嫌疑点：`account_auth_probe.py` 里 `if num == 90004:` 的硬编码 16 键平铺 stub

---

## 结论先行（TL;DR）

**官方抓包里 90004 是有的，10 次调用都在，全明文可读。**

| 字段 | 官方值（10/10 一致） | 我方 stub 值 | 一致？ |
|---|---|---|---|
| `GachaProbabilityDisplay` | **数组，12 条**（每条 `GachaProbabilityDisplayId` / `Url` / `LinkedLobbyBannerId` / `GachaDisplayTag`） | `false`（布尔） | ❌ **类型错 + 内容全空** |
| `GachaPeriodDisplay` | **`null`** | `false` | ❌ |
| `RaidPeriodDisplay` | **`null`** | `false` | ❌ |
| `Banners` | **7 条**（首条 `BannerId=103869`） | `[]` | ❌ |
| `Notices` | **6 条**（首条 `NoticeId=103865`「家具互动更新」） | `[]` | ❌ |
| `Events` | **14 条**（首条 `NoticeId=103866`「掉落量2倍活动！」） | `[]` | ❌ |
| `Issues` | `[]` | `[]` | ✅ |
| `ContentLock` | **官方根本不发这个键** | `false` | ❌ 多发 |
| `GuidePopup` | `[]` | `{}`（对象） | ❌ 类型错 |

一句话：**我们不是"把值写小了"，是"把结构写错了 + 把内容写空了"。** 官方 `Data` 里 `GachaProbabilityDisplay` 是**公示页清单**（12 个 `notice.bluearchive-cn.com/static/gacha/*.html`），我方回 `false`；`Banners/Notices/Events` 官方分别 7/6/14 条，我方全空数组。这与用户实测「注意事项点开是空白」完全对应。

**并且**：仓库里其实**已经有正确实现** `dto90004.py`（2026-11-16 05:21，8891 B，注释逐条记录了官方 9 键形状和这 4 处类型错），也已有 `patch_90004.py` 把它内联进 bridge，`deploy_all.py` 也把它登记进了补丁链（L142-147）。**但当前所有在跑的 bridge 快照里这个补丁都不见了** —— 见 §4。

---

## 1. 回答 Q1：官方抓包里有没有 90004 / `Management_Data`？

### 有。10 次调用，10 份完整明文。

**证据 A —— 解码目录里的文件**（`report\_tmp\official_decoded_201\`）：

```
06_90004_api_management_data.request.json    863 B
06_90004_api_management_data.response.json  25979 B
21_90004_api_management_data.response.json  25980 B
22_90004_api_management_data.response.json  25966 B
32_90004_api_management_data.response.json  25980 B
40_90004_api_management_data.response.json  25980 B
57_90004_api_management_data.response.json  25980 B
66_90004_api_management_data.response.json  25980 B
85_90004_api_management_data.response.json  25980 B
95_90004_api_management_data.response.json  25980 B
105_90004_api_management_data.response.json 25980 B
```

`meta` 里写明：

```
"meta": { "id": 90, "bj": "04:30:55.940", "status": 200, "resp_bytes": 14124, "protocol": 90004 }
"request": { "method": "POST", "host": "gsqc-api.bluearchive-cn.com", "path": "/api/management/data",
             "status": 200, "protocol": 90004, "protocol_name": "Management_Data", "req_bytes": 926 }
```

**证据 B —— `00_README.md` L35 的抓包时间线原文**：

```
- `04:30:55.940` POST/api/management/data proto=90004(Management_Data) resp=14124B
```

**证据 C —— `report\_tmp\最全的一个.har` 里也搜过**（HAR，Reqable 3.0.39，201 entries）：

| 搜索关键词 | 命中 |
|---|---|
| `management/data`（URL） | **10 条 entry**：`POST https://gsqc-api.bluearchive-cn.com/api/management/data` status=200，9 条 14124 B + 1 条 14104 B |
| `Management_Data`（字面量） | 0 —— 线上 body 是加密/压缩态，明文里没有这个字符串 |
| `90004`（字面量） | 0 —— 同上（HAR 只留了密文 body） |
| `GachaProbabilityDisplay`（字面量） | 0 —— 同上 |

所以 HAR 只能证明"打了 10 次、每次 200、约 14 KB"，**明文要从解码目录拿**（解码目录的源 HAR 是 `official201.har`，sha256 `e4cabb58…b65fd`，见 `00_README.md` L3-4、L6 生成脚本 `work/ba/server/har_decode_official.py`）。两者是同一批流量（201 entries 对得上、14124/14104 两种体积对得上）。

> ⚠️ 一处小差异：`00_README.md` 说源 HAR 是 `official201.har`，而本次给的是 `最全的一个.har`。二者 entries 都是 201、90004 都是 10 次、体积分布一致（9×14124 + 1×14104），判定为同一份抓包的两次导出。

**证据 D —— 10 份响应的差异只有一个字段**：

把 10 份 `.inner.Data` 规范化后逐字符比较，`21/22/32/40/57/66/85/95/105` 与 `06` 的差别**只出现在 `Banners[*].CreateTime`**（服务端每次现算的时间戳）：

```
06: CreateTime":"2026-11-16T04:30:55.774218085"
21: CreateTime":"2026-11-16T04:30:58.993994323"
22: CreateTime":"2026-11-16T04:30:59.14735832"     ← 结尾 0 被 JSON 规整掉，所以 14104 B（少 10 B）
32: CreateTime":"2026-11-16T04:31:06.177095993"
40: CreateTime":"2026-11-16T04:31:13.910930204"
57: CreateTime":"2026-11-16T04:32:57.267520801"
66: CreateTime":"2026-11-16T04:33:07.200501568"
85: CreateTime":"2026-11-16T04:33:51.645267885"
95: CreateTime":"2026-11-16T04:34:10.669599712"
105: CreateTime":"2026-11-16T04:34:15.025422763"
```

**⇒ 结构 10/10 完全稳定。** 这就把官方形状钉死了：不是"某次恰好有 banner"，而是恒定 6/14/0/7/12/0 + 3 个 null。

### 官方响应完整明文（`06_90004_api_management_data.response.json` 的 `plain.packet`，9289 B，原样逐字节）

```json
{"Protocol":90004,"SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"},"ServerTimeTicks":639304002557748658,"ServerNotification":0,"RequestId":"68e8de36-ba0b-48a0-aa7d-8f686d50f407","Data":{"Notices":[{"NoticeId":103865,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T13:59:59","Url":"https://notice.bluearchive-cn.com/static/notice/68e6bb1904b3560f1af0f491ee9fc88e.html","Title":"家具互动更新","DisplayOrder":4708},{"NoticeId":103855,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T13:59:59","Url":"https://notice.bluearchive-cn.com/static/notice/0277de9700141014aab781bea1bbde95.html","Title":"主线故事更新","DisplayOrder":4726},{"NoticeId":103825,"StartDate":"2026-10-22T18:15:00","EndDate":"2026-12-15T17:59:59","Url":"https://notice.bluearchive-cn.com/static/notice/233f1f1a018a011e5c20d42a05fd6c2a.html","Title":"阿洛娜的日程笔记（第32期）","DisplayOrder":9999},{"NoticeId":103674,"StartDate":"2026-08-24T14:10:00","EndDate":"2026-12-01T13:54:24","Url":"https://notice.bluearchive-cn.com/static/notice/546675127bbd182d36b90ad367cf798c.html","Title":"组合月卡内容焕新说明","DisplayOrder":4673},{"NoticeId":100028,"StartDate":"2023-07-25T18:00:00","EndDate":"2030-12-31T23:59:59","Url":"https://notice.bluearchive-cn.com/static/notice/b21177dbcd980921286c0bb33b447cab.html","Title":"《蔚蓝档案》公平运营说明","DisplayOrder":1},{"NoticeId":100027,"StartDate":"2023-07-25T18:00:00","EndDate":"2030-12-31T23:59:59","Url":"https://notice.bluearchive-cn.com/static/notice/75ecbb40fa85c1c090c83dc7cd7474cb.html","Title":"《蔚蓝档案》信息文明说明","DisplayOrder":4}],"Events":[{"NoticeId":103866,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T03:59:59","Url":"https://notice.bluearchive-cn.com/static/event/27ac686fcb578db6eb87ff1dee16a290.html","Title":"掉落量2倍活动！","DisplayOrder":4706},{"NoticeId":103864,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T03:59:59","Url":"https://notice.bluearchive-cn.com/static/event/8892e720c719b5363867af7db16b7bbd.html","Title":"综合战术测试：突破 • 重装甲","DisplayOrder":4710},{"NoticeId":103862,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-19T03:59:59","Url":"https://notice.bluearchive-cn.com/static/event/5db200ffdd7bd2b0281040bcc7606737.html","Title":"总力战：格里高利 • 室内战","DisplayOrder":4712},{"NoticeId":103861,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-12-17T13:59:59","Url":"https://notice.bluearchive-cn.com/static/event/cd6d5e7c289a3c7a58ab0a714e02732f.html","Title":"指引任务：阿里乌斯自管区特别授课","DisplayOrder":4714},{"NoticeId":103860,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T13:59:59","Url":"https://notice.bluearchive-cn.com/static/event/b7615d87cf75d3d63559b179ce633ca9.html","Title":"限时招募：纱织（泳装）","DisplayOrder":4722},{"NoticeId":103859,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T13:59:59","Url":"https://notice.bluearchive-cn.com/static/event/c40fd853827fbd6ba0daab45972a9c04.html","Title":"限时招募：野宫（泳装）","DisplayOrder":4716},{"NoticeId":103858,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T13:59:59","Url":"https://notice.bluearchive-cn.com/static/event/abe79d746c062a36ee7148853a63b096.html","Title":"限时招募：白子（泳装）","DisplayOrder":4718},{"NoticeId":103857,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T13:59:59","Url":"https://notice.bluearchive-cn.com/static/event/f2195e0265ab636da966fd96dce47fa0.html","Title":"限时招募：日和（泳装）","DisplayOrder":4720},{"NoticeId":103856,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T13:59:59","Url":"https://notice.bluearchive-cn.com/static/event/d4241e6238f89341d1c253151ba771a5.html","Title":"限时招募：美咲（泳装）","DisplayOrder":4724},{"NoticeId":103854,"StartDate":"2026-11-11T12:00:00","EndDate":"2026-11-26T13:59:59","Url":"https://notice.bluearchive-cn.com/static/event/694ad7600be7531d7fde26291629fad2.html","Title":"限时活动：Sheside Outside","DisplayOrder":4728},{"NoticeId":103835,"StartDate":"2026-10-27T11:40:00","EndDate":"2026-11-26T13:59:59","Url":"https://notice.bluearchive-cn.com/static/event/672b3af6e96962d480f78d509df6d3d9.html","Title":"全新礼包上架","DisplayOrder":4697},{"NoticeId":103834,"StartDate":"2026-10-27T11:40:00","EndDate":"2026-11-26T03:59:59","Url":"https://notice.bluearchive-cn.com/static/event/5ede8407f1f8ce8505962cfe2fa332f8.html","Title":"无限制决战：获刻玛 • 特殊装甲","DisplayOrder":4694},{"NoticeId":103739,"StartDate":"2026-09-17T19:00:00","EndDate":"2027-06-10T13:59:59","Url":"https://notice.bluearchive-cn.com/static/event/520b518a6109dff1976548f83c6ae733.html","Title":"3★自选招募开启","DisplayOrder":4616},{"NoticeId":100011,"StartDate":"2023-07-25T18:00:00","EndDate":"2030-12-31T23:59:59","Url":"https://notice.bluearchive-cn.com/static/event/7849ab06ecdcea91756c536df5dc51c6.html","Title":"新任老师欢迎礼物","DisplayOrder":1}],"Issues":[],"Banners":[{"BannerId":103869,"StartDate":"2026-11-12T14:00:00","EndDate":"2026-11-26T13:59:59","CdnUrl":"https://webcnstatic.yostar.net/pubplat/gm/prod_backend/notice/ac9a23f8e108df439cd3aef85c045ea8.png","LinkedLobbyBannerId":5004670,"BannerType":1,"LinkUrl":"0","SurveyId":0,"BannerDisplayType":910101,"CreateTime":"2026-11-16T04:30:55.774218085"},{"BannerId":103870,"StartDate":"2026-11-12T14:00:00","EndDate":"2026-11-26T13:59:59","CdnUrl":"https://webcnstatic.yostar.net/pubplat/gm/prod_backend/notice/4ed745596e636fb6f9f99b14e0a1aec6.png","LinkedLobbyBannerId":5004680,"BannerType":1,"LinkUrl":"0","SurveyId":0,"BannerDisplayType":910102,"CreateTime":"2026-11-16T04:30:55.774218085"},{"BannerId":103871,"StartDate":"2026-11-12T14:00:00","EndDate":"2026-11-26T13:59:59","CdnUrl":"https://webcnstatic.yostar.net/pubplat/gm/prod_backend/notice/97b20b2954851bb52e11f7ae35912878.png","LinkedLobbyBannerId":5004690,"BannerType":1,"LinkUrl":"0","SurveyId":0,"BannerDisplayType":910103,"CreateTime":"2026-11-16T04:30:55.774218085"},{"BannerId":103872,"StartDate":"2026-11-12T14:00:00","EndDate":"2026-11-26T13:59:59","CdnUrl":"https://webcnstatic.yostar.net/pubplat/gm/prod_backend/notice/3ca2da8d19b369d38572f45def2f105d.png","LinkedLobbyBannerId":5004700,"BannerType":1,"LinkUrl":"0","SurveyId":0,"BannerDisplayType":910104,"CreateTime":"2026-11-16T04:30:55.774218085"},{"BannerId":103873,"StartDate":"2026-11-12T14:00:00","EndDate":"2026-11-26T13:59:59","CdnUrl":"https://webcnstatic.yostar.net/pubplat/gm/prod_backend/notice/2cd5d6b35a4fbacb3697804ebae01bc3.png","LinkedLobbyBannerId":5004710,"BannerType":1,"LinkUrl":"0","SurveyId":0,"BannerDisplayType":910105,"CreateTime":"2026-11-16T04:30:55.774218085"},{"BannerId":103874,"StartDate":"2026-11-12T14:00:00","EndDate":"2026-11-26T13:59:59","CdnUrl":"https://webcnstatic.yostar.net/pubplat/gm/prod_backend/notice/9375bf532a07456b4e239677f1cd67f6.png","LinkedLobbyBannerId":10838,"LinkUrl":"0","SurveyId":0,"BannerDisplayType":910106,"CreateTime":"2026-11-16T04:30:55.774218085"},{"BannerId":103875,"StartDate":"2026-11-12T14:00:00","EndDate":"2026-11-19T03:59:59","CdnUrl":"https://webcnstatic.yostar.net/pubplat/gm/prod_backend/userFile/025915b8e7b378500bff07b1fe9796e1.png","BannerType":4,"LinkUrl":"0","SurveyId":0,"BannerDisplayType":910107,"CreateTime":"2026-11-16T04:30:55.774218085"}],"GachaProbabilityDisplay":[{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/350d8005a62a710920e8183888096bb8.html","LinkedLobbyBannerId":5004660,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/468ed3b3fcabedbf3d678fcb323d8eff.html","LinkedLobbyBannerId":99999999,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/44da080ca4bd29f018fca61793f585df.html","LinkedLobbyBannerId":5004710,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/cc3b91b7184e3d614b607db5c3b2f112.html","LinkedLobbyBannerId":5004700,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/0b48cacdff4e88819d14d8085c9e579e.html","LinkedLobbyBannerId":5004690,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/8b2b62161a33247fd55b16268c74fde4.html","LinkedLobbyBannerId":5004680,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/813f9342ebccf1dfb41d8f8ae7eab6aa.html","LinkedLobbyBannerId":5004670,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/fe4c4930c67f73d65c44087e43fd44dc.html","LinkedLobbyBannerId":10000000,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/7a9fcd0f820811a583da825558642ed8.html","LinkedLobbyBannerId":8000004,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/3edaff0ba08d01555d46ff796c9289a7.html","LinkedLobbyBannerId":90000000,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/3a6e591a711ff848ab3b8c3895fc7061.html","LinkedLobbyBannerId":7000001,"GachaDisplayTag":-1},{"GachaProbabilityDisplayId":2,"Url":"https://notice.bluearchive-cn.com/static/gacha/342b27a4ffc444e1e89aa36cb662e717.html","LinkedLobbyBannerId":7000000,"GachaDisplayTag":-1}],"GuidePopup":[],"GachaPeriodDisplay":null,"RaidPeriodDisplay":null,"Survey":null}}
```

> 上面是**线上真正传输的 90004 响应体明文**（`plain` 字段里 `packet` 的未转义形态，单行 9289 B）。
> `plain` 外层壳为 `{"protocol":"Management_Data","packet":"<上面这段>","requestid":"68e8de36-…"}`。
> 同一份内容的缩进美化版见 `06_90004_api_management_data.response.json` 的 `inner`（第 10-347 行），二者同源。

**请求侧明文**（`06_90004_api_management_data.request.json`）：

```json
{"Protocol":90004,"Resendable":true,"Hash":386564236509191,"IsTest":false,"SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"},"AccountId":10015354380,"OSType":2}
```

**注意请求侧没有任何运营参数** —— 90004 是无参拉取，服务端必须自己给出全部运营内容。这也解释了为什么"回空数组"能过协议校验但界面全空。

---

## 2. 回答 Q2：逐字段对照 + 全字段差集

### 2.1 官方信封：6 个顶层键（顺序固定）

```
1. Protocol       = 90004
2. SessionKey     = {"AccountServerId":10015354380, "MxToken":"Vji5A/…"}
3. ServerTimeTicks= 639304002557748658
4. ServerNotification = 0
5. RequestId      = "68e8de36-ba0b-48a0-aa7d-8f686d50f407"
6. Data           = { …9 键… }
```

`Data` 内部 9 个键（顺序固定）：

```
1. Notices                  array[6]
2. Events                   array[14]
3. Issues                   array[0]
4. Banners                  array[7]
5. GachaProbabilityDisplay  array[12]
6. GuidePopup               array[0]
7. GachaPeriodDisplay       null
8. RaidPeriodDisplay        null
9. Survey                   null
```

### 2.2 对照表：官方 vs 我方 stub

我方 stub 原文（`work\ba\srv_live\20261118_022226\bapatch\tools\account_auth_probe.py` L1880-1902；`_build_banreply2` 等所有在跑的副本同文）：

```python
        if num == 90004:
            from datetime import datetime as _d9
            _n9 = _d9.now()
            _t9 = int((_n9 - _d9(1, 1, 1)).total_seconds()) * 10_000_000 + _n9.microsecond * 10
            obj = {"Protocol": 90004,
                   "ServerTimeTicks": _t9,
                   "ServerNotification": 0,
                   "MissionProgressDBs": [],
                   "EventMissionProgressDBDict": {},
                   "BattlePassMissionProgressDBDict": {},
                   "StaticOpenConditions": dict(cn_inner.STATIC_OPEN_CONDITIONS),
                   "Notices": [],
                   "Events": [],
                   "Issues": [],
                   "Banners": [],
                   "GachaProbabilityDisplay": False,
                   "ContentLock": False,
                   "GachaPeriodDisplay": False,
                   "RaidPeriodDisplay": False,
                   "GuidePopup": {}}
            rec['gen_kind'] = 'management-90004'
            rec['fallback'] = 'generic-envelope'
            return self._cn_send_envelope(name or 'Management_Data', obj, rec)
```

| # | 字段 | 官方值 | 我方值 | 是否一致 |
|---|---|---|---|---|
| 1 | `Protocol` | `90004` | `90004` | ✅ |
| 2 | `SessionKey` | `{"AccountServerId":10015354380,"MxToken":"Vji5A/…"}` | **无此键** | ❌ **漏发** |
| 3 | `ServerTimeTicks` | `639304002557748658`（.NET ticks，现算） | 现算 ✅ | ✅ |
| 4 | `ServerNotification` | `0` | `0` | ✅ |
| 5 | `RequestId` | `"68e8de36-…"`（UUID，与 HTTP 头 `requestid` 同值） | **无此键**（靠 `_cn_send_envelope` 另补外层） | ⚠️ 内层无 |
| 6 | **`Data` 外壳** | **有**（9 键 dict） | **无此键**；9 个 Data 内层键被**抬到信封层平铺** | ❌ **结构性错** |
| 7 | `Notices` | **6 条** | `[]` | ❌ |
| 8 | `Events` | **14 条** | `[]` | ❌ |
| 9 | `Issues` | `[]` | `[]` | ✅ |
| 10 | `Banners` | **7 条** | `[]` | ❌ |
| 11 | **`GachaProbabilityDisplay`** | **`array[12]`**（对象数组） | **`false`**（布尔） | ❌ **类型错 + 空** |
| 12 | **`GachaPeriodDisplay`** | **`null`** | **`false`** | ❌ 类型错 |
| 13 | **`RaidPeriodDisplay`** | **`null`** | **`false`** | ❌ 类型错 |
| 14 | `GuidePopup` | `[]`（数组） | **`{}`**（对象） | ❌ 类型错 |
| 15 | `Survey` | `null` | **无此键** | ❌ 漏发 |
| 16 | `ContentLock` | **官方不发** | `false` | ❌ 多发 |
| 17 | `StaticOpenConditions` | **官方不发** | `dict(cn_inner.STATIC_OPEN_CONDITIONS)` | ❌ 多发 |
| 18 | `MissionProgressDBs` | **官方不发** | `[]` | ❌ 多发 |
| 19 | `EventMissionProgressDBDict` | **官方不发** | `{}` | ❌ 多发 |
| 20 | `BattlePassMissionProgressDBDict` | **官方不发** | `{}` | ❌ 多发 |

**用户点名要的 5 项，逐条给死答案**：

| 问题 | 答案 |
|---|---|
| `GachaProbabilityDisplay` 官方是 true 还是 false？ | **既不是 true 也不是 false —— 是数组，12 条对象。** 我方回 `false` 属于类型级错误。 |
| `GachaPeriodDisplay` | **`null`**（不是 `false`，不是省略）。 |
| `RaidPeriodDisplay` | **`null`**（同上）。 |
| `ContentLock` | **官方响应里根本不存在这个键**（10/10 全文 `grep "ContentLock"` = 0 命中）。我方发 `false` 是无害的多余键，但**它不可能是本问题原因**。 |
| `Banners` / `Notices` / `Events` / `Issues` 条数与首条 | Banners **7 条**，首条 `BannerId=103869`；Notices **6 条**，首条 `NoticeId=103865`「家具互动更新」；Events **14 条**，首条 `NoticeId=103866`「掉落量2倍活动！」；Issues **0 条**（`[]`）。 |

### 2.3 全字段清单差集

**官方有、我方没有（3 个，全是结构性的）**：

| 字段 | 说明 | 后果 |
|---|---|---|
| `Data` | 整个 `ManagementData` 外壳 dict（9 键） | 客户端 `ManagementDataResponse.Data = null` → 招募/大厅读运营数据时 NRE 或全空。**这是最重的一条。** |
| `SessionKey` | 回声，`{AccountServerId, MxToken}` | 客户端少一份会话回声 |
| `RequestId` | 内层请求 id | 官方内层与外层 `requestid` 同值；我方内层无、只靠 `_cn_send_envelope` 补外层 |
| `Survey` | `null` | 少一个键（客户端多半容忍缺省） |

**我方有、官方没有（5 个，全是多余的）**：

| 字段 | 我方值 | 备注 |
|---|---|---|
| `ContentLock` | `false` | 官方 10/10 不发 |
| `StaticOpenConditions` | `dict(cn_inner.STATIC_OPEN_CONDITIONS)` | **官方 10/10 不发**。这个键是我方自己发明的概念，官方 90004 里没有"静态开放条件"这回事。 |
| `MissionProgressDBs` | `[]` | 官方不发（任务进度在 8000/8006 里） |
| `EventMissionProgressDBDict` | `{}` | 官方不发 |
| `BattlePassMissionProgressDBDict` | `{}` | 官方不发 |

**⇒ 我方 16 键 = 3 信封键 + 2 个 ResponsePacket 继承字段 + 9 个 Data 内层键（被抬到信封层）+ 2 个自造键。**
正确形态应为 **6 键**：`Protocol` / `SessionKey` / `ServerTimeTicks` / `ServerNotification` / `RequestId` / `Data{9}`。

### 2.4 逐条内容（官方 06，其余 9 次仅 `CreateTime` 不同）

**`Notices`（6 条）**

| # | NoticeId | Title | StartDate | EndDate | DisplayOrder |
|---|---|---|---|---|---|
| 0 | 103865 | 家具互动更新 | 2026-11-11T12:00:00 | 2026-11-26T13:59:59 | 4708 |
| 1 | 103855 | 主线故事更新 | 2026-11-11T12:00:00 | 2026-11-26T13:59:59 | 4726 |
| 2 | 103825 | 阿洛娜的日程笔记（第32期） | 2026-10-22T18:15:00 | 2026-12-15T17:59:59 | 9999 |
| 3 | 103674 | 组合月卡内容焕新说明 | 2026-08-24T14:10:00 | 2026-12-01T13:54:24 | 4673 |
| 4 | 100028 | 《蔚蓝档案》公平运营说明 | 2023-07-25T18:00:00 | 2030-12-31T23:59:59 | 1 |
| 5 | 100027 | 《蔚蓝档案》信息文明说明 | 2023-07-25T18:00:00 | 2030-12-31T23:59:59 | 4 |

元素形状（6 键，全必发）：`NoticeId:int` `StartDate:str` `EndDate:str` `Url:str` `Title:str` `DisplayOrder:int`

**`Events`（14 条）** —— 元素形状与 Notices **完全相同**（6 键）

| # | NoticeId | Title | EndDate | DisplayOrder |
|---|---|---|---|---|
| 0 | 103866 | 掉落量2倍活动！ | 2026-11-26T03:59:59 | 4706 |
| 1 | 103864 | 综合战术测试：突破 • 重装甲 | 2026-11-26T03:59:59 | 4710 |
| 2 | 103862 | 总力战：格里高利 • 室内战 | 2026-11-19T03:59:59 | 4712 |
| 3 | 103861 | 指引任务：阿里乌斯自管区特别授课 | 2026-12-17T13:59:59 | 4714 |
| 4 | 103860 | **限时招募：纱织（泳装）** | 2026-11-26T13:59:59 | 4722 |
| 5 | 103859 | **限时招募：野宫（泳装）** | 2026-11-26T13:59:59 | 4716 |
| 6 | 103858 | **限时招募：白子（泳装）** | 2026-11-26T13:59:59 | 4718 |
| 7 | 103857 | **限时招募：日和（泳装）** | 2026-11-26T13:59:59 | 4720 |
| 8 | 103856 | **限时招募：美咲（泳装）** | 2026-11-26T13:59:59 | 4724 |
| 9 | 103854 | 限时活动：Sheside Outside | 2026-11-26T13:59:59 | 4728 |
| 10 | 103835 | 全新礼包上架 | 2026-11-26T13:59:59 | 4697 |
| 11 | 103834 | 无限制决战：获刻玛 • 特殊装甲 | 2026-11-26T03:59:59 | 4694 |
| 12 | 103739 | 3★自选招募开启 | 2027-06-10T13:59:59 | 4616 |
| 13 | 100011 | 新任老师欢迎礼物 | 2030-12-31T23:59:59 | 1 |

> **招募直接相关**：`Events` 里有 **5 条「限时招募」**（纱织/野宫/白子/日和/美咲 泳装）。我方 `Events: []` ⇒ 招募页顶部的活动条与公告全空。

**`Banners`（7 条）** —— 5 条 10 键、2 条 9 键（缺的正是两个可选键，proto3 presence 语义）

| # | BannerId | LinkedLobbyBannerId | BannerType | BannerDisplayType | StartDate | EndDate | CdnUrl 尾 |
|---|---|---|---|---|---|---|---|
| 0 | 103869 | 5004670 | 1 | 910101 | 2026-11-12T14:00:00 | 2026-11-26T13:59:59 | `ac9a23f8e108df439cd3aef85c045ea8.png` |
| 1 | 103870 | 5004680 | 1 | 910102 | 同上 | 同上 | `4ed745596e636fb6f9f99b14e0a1aec6.png` |
| 2 | 103871 | 5004690 | 1 | 910103 | 同上 | 同上 | `97b20b2954851bb52e11f7ae35912878.png` |
| 3 | 103872 | 5004700 | 1 | 910104 | 同上 | 同上 | `3ca2da8d19b369d38572f45def2f105d.png` |
| 4 | 103873 | 5004710 | 1 | 910105 | 同上 | 同上 | `2cd5d6b35a4fbacb3697804ebae01bc3.png` |
| 5 | 103874 | 10838 | **（缺 BannerType）** | 910106 | 同上 | 同上 | `9375bf532a07456b4e239677f1cd67f6.png` |
| 6 | 103875 | **（缺 LinkedLobbyBannerId）** | 4 | 910107 | 2026-11-12T14:00:00 | 2026-11-19T03:59:59 | `…/userFile/025915b8e7b378500bff07b1fe9796e1.png` |

全键：`BannerId:int` `StartDate:str` `EndDate:str` `CdnUrl:str` `LinkedLobbyBannerId?:int` `BannerType?:int` `LinkUrl:str` `SurveyId:int` `BannerDisplayType:int` `CreateTime:str`
`LinkUrl` 全为 `"0"`，`SurveyId` 全为 `0`，`CreateTime` 每次请求现算。

**`GachaProbabilityDisplay`（12 条）** —— **这就是"概率公示 / 注意事项"的数据源**

| # | GachaProbabilityDisplayId | LinkedLobbyBannerId | GachaDisplayTag | Url |
|---|---|---|---|---|
| 0 | 2 | 5004660 | -1 | `…/static/gacha/350d8005a62a710920e8183888096bb8.html` |
| 1 | 2 | **99999999** | -1 | `…/static/gacha/468ed3b3fcabedbf3d678fcb323d8eff.html` |
| 2 | 2 | 5004710 | -1 | `…/static/gacha/44da080ca4bd29f018fca61793f585df.html` |
| 3 | 2 | 5004700 | -1 | `…/static/gacha/cc3b91b7184e3d614b607db5c3b2f112.html` |
| 4 | 2 | 5004690 | -1 | `…/static/gacha/0b48cacdff4e88819d14d8085c9e579e.html` |
| 5 | 2 | 5004680 | -1 | `…/static/gacha/8b2b62161a33247fd55b16268c74fde4.html` |
| 6 | 2 | 5004670 | -1 | `…/static/gacha/813f9342ebccf1dfb41d8f8ae7eab6aa.html` |
| 7 | 2 | **10000000** | -1 | `…/static/gacha/fe4c4930c67f73d65c44087e43fd44dc.html` |
| 8 | 2 | **8000004** | -1 | `…/static/gacha/7a9fcd0f820811a583da825558642ed8.html` |
| 9 | 2 | **90000000** | -1 | `…/static/gacha/3edaff0ba08d01555d46ff796c9289a7.html` |
| 10 | 2 | **7000001** | -1 | `…/static/gacha/3a6e591a711ff848ab3b8c3895fc7061.html` |
| 11 | 2 | **7000000** | -1 | `…/static/gacha/342b27a4ffc444e1e89aa36cb662e717.html` |

全键：`GachaProbabilityDisplayId:int` `Url:str` `LinkedLobbyBannerId:int` `GachaDisplayTag:int`（`GachaDisplayTag` 全 `-1`）

**⭐ 关键结构发现：`Banners.LinkedLobbyBannerId` 与 `GachaProbabilityDisplay.LinkedLobbyBannerId` 是同一个 join 键。**

```
Banners 的 LinkedLobbyBannerId 集合         = {5004670, 5004680, 5004690, 5004700, 5004710, 10838}
GachaProbabilityDisplay 的 集合            = {5004660, 5004670, 5004680, 5004690, 5004700, 5004710,
                                             7000000, 7000001, 8000004, 10000000, 90000000, 99999999}
交集（即"有 banner 且有公示"的卡池）        = {5004670, 5004680, 5004690, 5004700, 5004710}  ← 5/5 全覆盖
```

也就是说：**每个招募 banner 都恰好在 `GachaProbabilityDisplay` 里有一条对应记录**，客户端靠 `LinkedLobbyBannerId` 去查"这个卡池的概率公示链接/注意事项页"。我方两条都回空 ⇒ 招募页"注意事项"必然空白。这是目前**最强的机制解释**（结构性事实，10/10 稳定；客户端侧具体取用点未在本任务中验证，见 §6 说明）。

**`Issues`** = `[]`（官方 10/10 空）
**`GuidePopup`** = `[]`（官方 10/10 空，**是数组不是对象**）
**`GachaPeriodDisplay` / `RaidPeriodDisplay` / `Survey`** = `null`（官方 10/10 显式发 `null`，不是省略、不是 `false`、不是 `{}`）

---

## 3. 回答 Q3

### 3.1 前提不成立：官方抓包里**有** 90004

Q3 是"如果官方抓包里没有 90004"才会问的。见 §1，**有 10 次，明文完整**。所以"stub 来源无从考证"这个问题不存在 —— 我们**有**官方形状可以直接照抄，而且确实已经有人照抄过了（§3.2）。

### 3.2 上游 Shittim-Server：**根本没有 90004 的实现**

搜索路径：`C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\Shittim-Server\`（全部 `*.cs`，递归）

| 关键词 | 命中 |
|---|---|
| `Management_Data` | **0** |
| `ManagementData` | **0** |
| `\b90004\b` | **0** |
| `GachaProbabilityDisplay` | **0** |
| `GachaPeriodDisplay` | **0** |

`ProtocolHandler` 里跟 Management 有关的只有两个：

```
Core\NetworkProtocol\Handlers\ManagementHandler.cs:23:  [ProtocolHandler(Protocol.Management_BannerList)]
Core\NetworkProtocol\Handlers\ManagementHandler.cs:60:  [ProtocolHandler(Protocol.Management_ProtocolLockList)]
```

而 `Management_BannerList` 的实现（`.cs` L33-55）是：**`KoyukiIncident` 关着就直接 `response.BannerDBs = []`**，开着只回一条 `koyuki.png` 的调试 banner。

**⇒ 结论：不是"上游有一份正常实现、被我们用桩替换掉了"。上游 Shittim 压根没写 90004。** 我方那个 16 键 stub 是**从零手写的**，不是降级自上游。

### 3.3 stub 的来源：`scripts\patch_90004.py`（2026-11-14）+ 后续 `dto90004.py`（2026-11-16）

**第一代（错的）** —— `scripts\patch_90004.py`（1496 B，2026-11-14 14:44），生成的就是现在这段 16 键平铺：

```python
if 'management-90004' in s: ...
new = '''        if num == 90004:
            ...
            obj = {"Protocol": 90004,
                   ...
                   "GachaProbabilityDisplay": False,
```

同目录 `scripts\account_auth_probe.py`(2633 B) 与 `work\ba\proto\_gen_priority.py` L93-99 也记录了它是**手写桩**：

> `existing="桩/空包", existing_ref="account_auth_probe.py:_generic_protocol_response (num==90004, 空数组版)"`

**第二代（对的，但没上线）** —— `work\ba\server\deploy\dto90004.py`（8891 B，2026-11-16 05:21:08）。它的 docstring 就已经把现在的结论全部写清楚了：

> `dto_schema_full_v2.json 里 ManagementData 是 20 个字段的 DTO，ManagementDataResponse.Data 的类型就是它。官方 201 抓包（06_90004）的 Data 只发出 9 个键：`
> `Notices / Events / Issues / Banners / GachaProbabilityDisplay / GuidePopup / GachaPeriodDisplay(null) / RaidPeriodDisplay(null) / Survey(null)`
> `另外 11 个（Maintenance / ServerStatus / LatestClientVersion / … / ContentLock / DownloadLimitTime / EnableSQLite）在官方包里 一次都没出现 —— 它们是 null / 0 / 默认值，被序列化层丢掉`
> `我们 bridge 现在的 16 键平铺 = 3 个信封键 + 4 个 ResponsePacket 继承字段 + 上面那 9 个 Data 内层键被抬到了信封层，而且 4 个键类型还写错了`
> `（GachaProbabilityDisplay:false 该是 list、GuidePopup:{} 该是 list、GachaPeriodDisplay/RaidPeriodDisplay:false 该是 null）。`
> `⇒ 客户端 ManagementDataResponse.Data = null → NRE。`

**⇒ 我方的 90004 形状结论早就有人做对了、写进代码了、还配了 patch 脚本。**

---

## 4. ⭐ 本次最关键的发现：正确的补丁**存在且被验证过**，但**没有一个在跑的 bridge 有它**

`work\ba\server\deploy\patch_90004.py`（30946 B）+ `dto90004.py` 的组合会把 90004 分支整段换成官方形状，并且 `deploy_all.py` **确实把它登记进补丁链**：

```
deploy_all.py:142:  key='90004', script='patch_90004.py', arg_key='bridge',
deploy_all.py:144:  markers=[('# ==== BEGIN 90004-PATCH v1', 1), …
deploy_all.py:147:  why='90004 Management_Data 官方 6 键外壳 + 内联 dto90004 + _cn_send_envelope 的 outer rid',
deploy_all.py:192:  dict(num=90004, name='Management_Data', via='branch', gen=None),
```

**但实际状态是：**

| bridge 副本 | 大小 | mtime | `BEGIN 90004-PATCH` | `build_90004_management_data(` | `"GachaProbabilityDisplay": False` | 其它补丁（P3-HOOK-G / 1017 / 24000-v3） |
|---|---|---|---|---|---|---|
| `deploy\_verify_rig\` | 115,740 | 11-16 05:39 | ✅ | ✅ | ❌ 已消失 | HOOK-G ✗ / 1017 ✅ / 24000 ✅ |
| `deploy\_compat_check\full\` | 115,738 | 11-16 06:12 | ✅ | ✅ | ❌ | — |
| `deploy\_sandbox\90004\` | 52,804 | 11-16 05:24 | ✅ | ✅ | ❌ | — |
| `srv_live\20261118_0059\bapatch\tools\` | 157,724 | 11-17 20:30 | ❌ | ❌ | ✅ **旧 stub 还在** | HOOK-G ✅ / 1017 ✅ / 24000 ✅ |
| `srv_live\20261118_022226\bapatch\tools\` | 161,194 | 11-18 02:22 | ❌ | ❌ | ✅ | HOOK-G ✅ / 1017 ✅ / 24000 ✅ |
| `deploy\_build_cardid\` | 164,808 | 11-18 03:34 | ❌ | ❌ | ✅ | — |
| `deploy\_build_multiacct\` | 177,059 | 11-18 03:51 | ❌ | ❌ | ✅ | — |
| `deploy\_build_sidwb\` | 180,227 | 11-18 04:09 | ❌ | ❌ | ✅ | — |
| `deploy\_build_ttl\` | 183,660 | 11-18 04:45 | ❌ | ❌ | ✅ | HOOK-G ✅ / 1017 ✅ / 24000 ✅ |
| `deploy\_build_banexp\` | 191,670 | 11-18 18:46 | ❌ | ❌ | ✅ | — |
| `deploy\_build_banreply\` | 207,148 | 11-18 20:01 | ❌ | ❌ | ✅ | — |
| **`deploy\_build_banreply2\`（最新）** | **222,486** | **11-18 21:28** | ❌ | ❌ | ✅ | **HOOK-G ✅ / 1017 ✅ / 24000 ✅** |

**读法**：
1. 90004 补丁只在 **11-16 05:24–06:12** 的沙盒/验收副本里存在过。
2. **从 11-17 20:30 起的每一个副本（含 11-18 全部 7 个 `_build_*`、含最新的 `_build_banreply2`）都是旧 16 键 stub。**
3. 同一批副本里 **P3-HOOK-G / 1017 / 24000-v3 三个补丁都在**，唯独 90004 不在 ⇒ 不是"整个 deploy 链没跑"，而是**90004 这一环在链上丢了**（或被回滚覆盖）。
4. `srv_live\20261118_022226\_patched\`、`srv_live\20261118_0059\_patched\` 也都没有。

**⇒ 这就是"客户端表是干净的、catalog 是新的、问题只可能在服务端下发的数据里"的最后一块拼图：服务端下发的 90004 就是错的，而且修复代码早就写好了、只是从来没活到线上。**

---

## 5. 回答 Q4：在 `report\_tmp\official_decoded_201\` 里 grep 的结果

搜索范围：该目录下全部 `*.json`（109 个 RPC 文件 + 6 个旁路文件）。
命中**只出现在 10 个 `90004` 响应文件**里，其余 99 个文件 0 命中。

### 5.1 `GachaProbabilityDisplay`

| 文件 | 行号 | 命中行内容 |
|---|---|---|
| `06_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |
| `21_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |
| `22_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |
| `32_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |
| `40_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |
| `57_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |
| `66_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |
| `85_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |
| `95_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |
| `105_90004_api_management_data.response.json` | **L269** | `"GachaProbabilityDisplay": [` |

（外加每个文件 L9 的 `plain` 巨行里同一键各出现 1 次 —— `plain` 是整包的转义副本，故每文件 `GachaProbabilityDisplay` 总命中 14 次 = 缩进版 1 键 + 12 条…的展开 + plain 1 次。**注意：这 10 个文件里没有任何一个是 `false`。**）

### 5.2 `GachaPeriodDisplay`

| 文件 | 行号 | 命中行内容 |
|---|---|---|
| `06_…` / `21_…` / `22_…` / `32_…` / `40_…` / `57_…` / `66_…` / `85_…` / `95_…` / `105_…`（10/10） | **L344** | **`"GachaPeriodDisplay": null,`** |

### 5.3 `Banners`

| 文件 | 行号 | 命中行内容 |
|---|---|---|
| `06_…` / `21_…` / `22_…` / `32_…` / `40_…` / `57_…` / `66_…` / `85_…` / `95_…` / `105_…`（10/10） | **L185** | `"Banners": [` |

### 5.4 附带：`RaidPeriodDisplay` / `ContentLock` / `StaticOpenConditions`

| 关键词 | 结果 |
|---|---|
| `RaidPeriodDisplay` | 10/10 命中，均在 **L345：`"RaidPeriodDisplay": null,`** |
| `ContentLock` | **0 命中**（全部 109 个 JSON 文件） |
| `StaticOpenConditions` | **0 命中**（全部 109 个 JSON 文件） |
| `MissionProgressDBs` / `EventMissionProgressDBDict` | **0 命中** |

**⇒ 我方 stub 里的 `ContentLock` / `StaticOpenConditions` / `MissionProgressDBs` 三族键，在官方 109 个明文响应里一次都没出现过。**

---

## 6. 结论与建议（只写不执行；本次作业只读）

### 6.1 已确证的事实

1. 官方 90004 存在、10/10、明文完整、结构恒定（仅 `Banners[*].CreateTime` 每次变）。
2. 官方 `GachaProbabilityDisplay` 是 **12 条对象的数组**，`GachaPeriodDisplay`/`RaidPeriodDisplay` 是 **`null`**，`Banners/Notices/Events` 是 **7/6/14 条**，`Issues`/`GuidePopup` 是 **空数组**。
3. 我方 stub 把 9 个 `Data` 内层键**抬到信封层平铺**，**没有 `Data` 外壳**，把 4 个字段**类型写错**（`false`/`false`/`false`/`{}`），把 4 个列表**写空**，并**多发 5 个官方不发的键**、**漏发 `SessionKey`/`RequestId`/`Survey`**。
4. 上游 Shittim-Server **没有 90004 实现**（0 命中）——不是"替换"，是从零手写。
5. 正确实现 `dto90004.py` + `patch_90004.py` **已于 2026-11-16 写好并通过沙盒验证**，`deploy_all.py` 也已登记，但**从 11-17 起所有在跑的 bridge（含最新 `_build_banreply2`）都没有这个补丁**；同批 bridge 里 HOOK-G/1017/24000 三个补丁都在。

### 6.2 与本症状的对应关系（分层，明确区分"已证实"与"强推断"）

| 层 | 内容 | 性质 |
|---|---|---|
| **A. 结构层（已证实是错的）** | 缺 `Data` 外壳 ⇒ 客户端 `ManagementDataResponse.Data` 拿不到官方形状的 dict；4 个字段类型与官方不符 | **已证实**（对照 10/10 官方明文） |
| **B. 内容层（已证实是空的）** | `Banners/Notices/Events` 全空、`GachaProbabilityDisplay` 0 条 | **已证实** |
| **C. 招募"注意事项"空白（强推断）** | `Banners.LinkedLobbyBannerId` 与 `GachaProbabilityDisplay.LinkedLobbyBannerId` 是同一套 join 键，官方 5/5 卡池全覆盖；我方两组都空 ⇒ 招募页查不到公示/注意事项页 | **强推断**（join 键结构事实已证实；客户端具体取用点未在本任务验证） |
| **D. `No LocalizeKey`（未在本任务中单独证实）** | 拉齐 90004 后是否连带解决，需实测。官方 90004 里 **`Title` 全部是中文原文、没有任何 LocalizeKey 字段**，所以 90004 本身不直接提供 `LocalizeKey` | **待验证** |

> D 行是要特别提醒的：**官方 90004 的所有 `Title` 都是中文字面量**（`"家具互动更新"`、`"掉落量2倍活动！"`…），**没有任何 LocalizeKey 字段**。因此 90004 修好能解决"注意事项空白/公告为空/活动条为空"，但**招募界面整片 `No LocalizeKey` 是否随之消失，不能从这份材料直接推出** —— 那属于 `ShopRecruitDB` 一侧，见同目录的 `CLIENT_SHOPRECRUIT_DTO_VS_OURS.md` / `OFFICIAL_SHOPLIST_SHOPRECRUITS_CHECK.md`。

### 6.3 最小修复路径（供决策，未执行）

1. **接线**：把 `patch_90004.py` 重新纳入当前 build 链（`_build_banreply2` 基线），使 `BEGIN 90004-PATCH v1` 与 `build_90004_management_data(` 出现在 bridge 里、旧 16 键 stub 消失。**这一步单独就能把 A 层结构全部修正**（`Data` 外壳、9 键、`null`×3、空数组 `[]`、去掉 5 个多余键）。
2. **补运营数据**：`dto90004.py` 在无 ops 文件时会给 6 个列表全 `[]` —— **结构对、内容仍空**，注意事项照样空白。要让界面有内容，需要往
   `/www/wwwroot/bapatch/_ba_state/90004_ops.json`（或 `/www/wwwroot/bapatch/90004_ops.json`）放一份运营配置，最少包含：
   - `GachaProbabilityDisplay`（12 条，`GachaProbabilityDisplayId/Url/LinkedLobbyBannerId/GachaDisplayTag`）
   - `Banners`（7 条，注意 103874 缺 `BannerType`、103875 缺 `LinkedLobbyBannerId` 的可选键语义）
   - `Notices`（6 条）/ `Events`（14 条）
   逐条原始值见本报告 §2.4，可直接从 `06_90004_api_management_data.response.json` 的 `inner.Data` 抽。
3. **验证**：`python gen90004.py --verify-official` 做逐字节/shape 验收；再在客户端看招募页"注意事项"是否出内容。

---

## 附录 A：本次用到的全部路径与命令（可复现）

**材料路径**
```
C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\official_decoded_201\
C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\最全的一个.har
C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\official_decoded_201\00_README.md
C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\Shittim-Server\
C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_live\20261118_022226\bapatch\tools\account_auth_probe.py   (L1880-1902)
C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_build_banreply2\account_auth_probe.py
C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\dto90004.py
C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\patch_90004.py
C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\gen90004.py
C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\deploy_all.py  (L142-147)
C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\Shittim-Server\Core\NetworkProtocol\Handlers\ManagementHandler.cs
```

**取官方明文的一行命令**
```powershell
$o = Get-Content "report\_tmp\official_decoded_201\06_90004_api_management_data.response.json" -Raw -Encoding UTF8 | ConvertFrom-Json
($o.plain | ConvertFrom-Json).packet      # ← 9289 B 的 90004 响应体明文
$o.inner.Data                             # ← 同一份内容的解析态
```

**核对我方是否已打补丁**
```powershell
Get-ChildItem -Recurse -Filter account_auth_probe.py |
  Select-String -Pattern 'BEGIN 90004-PATCH','build_90004_management_data\(' -List
```

## 附录 B：官方 90004 的 20 键 DTO 里，哪 9 个上桌、哪 11 个不上桌

`dto90004.py` docstring 记录（与本报告 §2 的抓包事实一致）：

- **上桌 9 个**：`Notices` `Events` `Issues` `Banners` `GachaProbabilityDisplay` `GuidePopup` `GachaPeriodDisplay(null)` `RaidPeriodDisplay(null)` `Survey(null)`
- **不上桌 11 个**：`Maintenance` `ServerStatus` `LatestClientVersion` `LatestAndroidClientVersion` `LatestIosClientVersion` `LatestPCClientVersion` `MarketAppleId` `NotificationBeforeMaintenance` `ContentLock` `DownloadLimitTime` `EnableSQLite`

本报告在官方明文里对这 11 个键逐个 `grep`，**全部 0 命中**，与 docstring 一致。

---

## 附录 C：本次搜索过、但没命中的关键词/路径（避免后人重复劳动）

| 搜索关键词 | 搜索路径 | 命中 |
|---|---|---|
| `Management_Data` | `work\ba\srv_src\Shittim-Server\**\*.cs` | 0 |
| `ManagementData` | 同上 | 0 |
| `\b90004\b` | 同上 | 0 |
| `GachaProbabilityDisplay` | 同上 | 0 |
| `GachaPeriodDisplay` | 同上 | 0 |
| `Management_Data` | `report\_tmp\最全的一个.har`（字面量，非 URL） | 0（body 加密） |
| `90004` | 同上 | 0（body 加密，且 postData 也是密文） |
| `GachaProbabilityDisplay` | 同上 | 0（body 加密） |
| `management/data` | 同上（URL 维度） | **10 条 entry** |
| `ContentLock` | `report\_tmp\official_decoded_201\**\*.json` | 0 |
| `StaticOpenConditions` | 同上 | 0 |
| `MissionProgressDBs` | 同上 | 0 |
| `GachaProbabilityDisplay` / `GachaPeriodDisplay` / `Banners` | 同上 109 个 JSON | 仅 10 个 `90004_*.response.json` 命中（行号见 §5） |
