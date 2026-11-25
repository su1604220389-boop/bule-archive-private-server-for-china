# official_decoded/ 说明

- 源 HAR：`C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\official201.har`
- sha256：`e4cabb5840b30341d0470765433f90e47bd383eba49e3e2c5a701919a92b65fd`
- 条目数：201
- 生成脚本：`work/ba/server/har_official_decode.py`

## 结论先行

**本 HAR 内 `POST /api/*`（游戏协议）条数 = 109。** 因此没有任何可解密的
`Account_Auth(1002)` / `Account_GetInfo` / `Academy_GetInfo(24000)` 信封。
这里存放的是**真实抓到的其余官方明文**，用于对齐我们的私服实现。

## 文件

| 文件 | 来源 | 条数 |
|---|---|---|
| `10_state-api_state.json` | `state-api.bluearchive-cn.com/api/state` | 1 |
| `11_gsqc-api_state.json` | `gsqc-api.bluearchive-cn.com/api/state` | 1 |
| `12_gs-api_health.json` | `gs-api.bluearchive-cn.com/api/health` | 4 |
| `21_sdk_user_detail.json` | `sdk-api.yostar.cn/user/detail` | 1 |
| `30_adjust_role_events.json` | `app.adjust.cn/event` | 1 |
| `40_bluearchive_hosts.json` | 全部 `*.bluearchive-cn.com` 条目 | 125 |
| `_timeline.txt` | 全部 88 条按时间排序 | 201 |
| `_summary.json` | 桶统计/_id 缺口/连接连续性 | - |

## 游戏 RPC 解密结果

- `04:30:54.662` POST/api/account/auth proto=1002(Account_Auth) resp=5056B 
- `04:30:54.980` POST/api/academy/getinfo proto=24000(Academy_GetInfo) resp=17560B 
- `04:30:55.110` POST/api/account/loginsync proto=1017(Account_LoginSync) resp=246808B 
- `04:30:55.460` POST/api/item/list proto=4000(Item_List) resp=16088B 
- `04:30:55.625` POST/api/networktime/sync proto=3(NetworkTime_Sync) resp=620B 
- `04:30:55.773` POST/api/contentsave/get proto=26000(ContentSave_Get) resp=640B 
- `04:30:55.940` POST/api/management/data proto=90004(Management_Data) resp=14124B 
- `04:30:56.071` POST/api/account/gettutorial proto=1005(Account_GetTutorial) resp=640B 
- `04:30:56.292` POST/api/mission/list proto=8000(Mission_List) resp=268396B 
- `04:30:56.632` POST/api/mission/guidemissionseasonlist proto=8006(Mission_GuideMissionSeasonList) resp=160216B 
- `04:30:56.839` POST/api/mission/list proto=8000(Mission_List) resp=8768B 
- `04:30:57.167` POST/api/mission/list proto=8000(Mission_List) resp=8216B 
- `04:30:57.315` POST/api/minigame/missionlist proto=35003(MiniGame_MissionList) resp=4480B 
- `04:30:57.515` POST/api/toast/list proto=16000(Toast_List) resp=556B 
- `04:30:57.747` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:30:57.913` POST/api/opencondition/eventlist proto=15002(OpenCondition_EventList) resp=600B 
- `04:30:58.104` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:30:58.577` POST/api/mail/check proto=7001(Mail_Check) resp=556B 
- `04:30:58.711` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:30:58.860` POST/api/clan/check proto=28019(Clan_Check) resp=536B 
- `04:30:59.008` POST/api/friend/check proto=43010(Friend_Check) resp=536B 
- `04:30:59.161` POST/api/management/data proto=90004(Management_Data) resp=14124B 
- `04:30:59.309` POST/api/management/data proto=90004(Management_Data) resp=14104B 
- `04:31:01.246` POST/api/billing/purchaselistbyyostar proto=29002(Billing_PurchaseListByYostar) resp=1280B 
- `04:31:02.981` POST/api/mail/listsemipermanent proto=7003(Mail_ListSemiPermanent) resp=556B 
- `04:31:03.093` POST/api/mail/list proto=7000(Mail_List) resp=1600B 
- `04:31:05.134` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:31:05.316` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:31:05.777` POST/api/mail/check proto=7001(Mail_Check) resp=556B 
- `04:31:05.891` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:31:06.042` POST/api/clan/check proto=28019(Clan_Check) resp=536B 
- `04:31:06.190` POST/api/friend/check proto=43010(Friend_Check) resp=536B 
- `04:31:06.340` POST/api/management/data proto=90004(Management_Data) resp=14124B 
- `04:31:08.629` POST/api/billing/purchaselistbyyostar proto=29002(Billing_PurchaseListByYostar) resp=1280B 
- `04:31:12.824` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:31:12.986` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:31:13.454` POST/api/mail/check proto=7001(Mail_Check) resp=556B 
- `04:31:13.571` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:31:13.723` POST/api/clan/check proto=28019(Clan_Check) resp=536B 
- `04:31:13.873` POST/api/friend/check proto=43010(Friend_Check) resp=536B 
- `04:31:14.069` POST/api/management/data proto=90004(Management_Data) resp=14124B 
- `04:31:14.785` POST/api/billing/purchaselistbyyostar proto=29002(Billing_PurchaseListByYostar) resp=1280B 
- `04:31:23.190` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:31:23.350` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:31:26.630` POST/api/campaign/list proto=6000(Campaign_List) resp=44672B 
- `04:31:26.794` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:31:36.586` POST/api/mail/check proto=7001(Mail_Check) resp=556B 
- `04:31:37.247` POST/api/echelon/list proto=5000(Echelon_List) resp=4120B 
- `04:31:37.905` POST/api/echelon/save proto=5001(Echelon_Save) resp=984B 
- `04:31:38.827` POST/api/campaign/entermainstagestrategyskip proto=6020(Campaign_EnterMainStageStrategySkip) resp=2072B 
- `04:32:49.197` POST/api/campaign/mainstagestrategyskipresult proto=6021(Campaign_MainStageStrategySkipResult) resp=10284B 
- `04:32:56.190` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:32:56.362` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:32:56.842` POST/api/mail/check proto=7001(Mail_Check) resp=556B 
- `04:32:56.967` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:32:57.117` POST/api/clan/check proto=28019(Clan_Check) resp=536B 
- `04:32:57.266` POST/api/friend/check proto=43010(Friend_Check) resp=536B 
- `04:32:57.432` POST/api/management/data proto=90004(Management_Data) resp=14124B 
- `04:32:59.340` POST/api/eventcontent/permanentlist proto=30041(EventContent_PermanentList) resp=2156B 
- `04:33:03.675` POST/api/mission/multiplereward proto=8002(Mission_MultipleReward) resp=8320B 
- `04:33:06.123` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:33:06.299` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:33:06.769` POST/api/mail/check proto=7001(Mail_Check) resp=556B 
- `04:33:06.898` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:33:07.049` POST/api/clan/check proto=28019(Clan_Check) resp=536B 
- `04:33:07.214` POST/api/friend/check proto=43010(Friend_Check) resp=536B 
- `04:33:07.363` POST/api/management/data proto=90004(Management_Data) resp=14124B 
- `04:33:10.041` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:33:10.166` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:33:12.442` POST/api/arena/enterlobby proto=22000(Arena_EnterLobby) resp=9068B 
- `04:33:15.394` POST/api/arena/cumulativetimereward proto=22008(Arena_CumulativeTimeReward) resp=3072B 
- `04:33:17.101` POST/api/arena/dailyreward proto=22009(Arena_DailyReward) resp=3224B 
- `04:33:18.562` POST/api/echelon/list proto=5000(Echelon_List) resp=4120B 
- `04:33:20.377` POST/api/echelon/list proto=5000(Echelon_List) resp=4120B 
- `04:33:21.382` POST/api/arena/syncechelonsettingtime proto=22016(Arena_SyncEchelonSettingTime) resp=640B 
- `04:33:22.070` POST/api/echelon/list proto=5000(Echelon_List) resp=4120B 
- `04:33:22.785` POST/api/echelon/save proto=5001(Echelon_Save) resp=1004B 
- `04:33:23.501` POST/api/arena/enterbattle proto=22004(Arena_EnterBattle) resp=67180B 
- `04:33:46.722` POST/api/arena/enterlobby proto=22000(Arena_EnterLobby) resp=9068B 
- `04:33:50.283` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:33:50.453` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:33:50.924` POST/api/mail/check proto=7001(Mail_Check) resp=556B 
- `04:33:51.024` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:33:51.222` POST/api/clan/check proto=28019(Clan_Check) resp=536B 
- `04:33:51.655` POST/api/friend/check proto=43010(Friend_Check) resp=536B 
- `04:33:51.803` POST/api/management/data proto=90004(Management_Data) resp=14124B 
- `04:33:59.137` POST/api/shop/list proto=10002(Shop_List) resp=1304B 
- `04:34:01.533` POST/api/cafe/ack proto=20001(Cafe_Ack) resp=5016B 
- `04:34:03.336` POST/api/cafe/receivecurrency proto=20013(Cafe_ReceiveCurrency) resp=11136B 
- `04:34:09.740` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:34:09.859` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:34:10.335` POST/api/mail/check proto=7001(Mail_Check) resp=556B 
- `04:34:10.452` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:34:10.584` POST/api/clan/check proto=28019(Clan_Check) resp=536B 
- `04:34:10.717` POST/api/friend/check proto=43010(Friend_Check) resp=536B 
- `04:34:10.849` POST/api/management/data proto=90004(Management_Data) resp=14124B 
- `04:34:11.018` POST/api/academy/getinfo proto=24000(Academy_GetInfo) resp=17560B 
- `04:34:11.245` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:34:11.911` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:34:14.031` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:34:14.172` POST/api/notification/eventcontentreddotcheck proto=36001(Notification_EventContentReddotCheck) resp=1088B 
- `04:34:14.644` POST/api/mail/check proto=7001(Mail_Check) resp=556B 
- `04:34:14.810` POST/api/event/rewardincrease proto=25003(Event_RewardIncrease) resp=792B 
- `04:34:14.945` POST/api/clan/check proto=28019(Clan_Check) resp=536B 
- `04:34:15.074` POST/api/friend/check proto=43010(Friend_Check) resp=536B 
- `04:34:15.207` POST/api/management/data proto=90004(Management_Data) resp=14124B 
- `04:34:16.937` POST/api/clan/lobby proto=28000(Clan_Lobby) resp=35864B 
- `04:34:18.043` POST/api/clan/chat/records proto=90009(Clan_Chat_Records) resp=30316B 
- `04:34:22.916` POST/api/clan/chat/records proto=90009(Clan_Chat_Records) resp=556B 
