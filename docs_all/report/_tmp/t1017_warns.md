### 账号 A（全新号（rules 骨架））的 WARN 全量清单：83 条

| # | 类别 | spec 路径 | 官方观测 | 为什么可以接受（逐条） |
|---:|---|---|---|---|
| 1 | 长度越界 | `CafeGetInfoResponse.CafeDBs[0].CafeVisitCharacterDBs` | map 键数 0 不在观测范围 [3,4] | 新号咖啡厅没有访客角色；官方号有 3~4 个（未找到访客调度规则，按空 map 发） |
| 2 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[0].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 3 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[1].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 4 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[2].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 5 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[3].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 6 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[5].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 7 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[6].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 8 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[7].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 9 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[8].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 10 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[9].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 11 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[10].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 12 | 长度越界 | `CafeGetInfoResponse.CafeDBs[0].ProductionDB.ProductionParcelInfos` | 数组长度 0 不在观测范围 [1,2] | 新号没有进行中的家具生产；官方号有 1~2 个在生产 |
| 13 | 空数组首见 | `CafeGetInfoResponse.CafeDBs[0].ProductionDB.ProductionParcelInfos` | 官方样本中未出现空数组 | 新号没有进行中的家具生产；官方号有 1~2 个在生产 |
| 14 | 长度越界 | `CafeGetInfoResponse.CafeDBs[1].CafeVisitCharacterDBs` | map 键数 0 不在观测范围 [3,4] | 新号咖啡厅没有访客角色；官方号有 3~4 个（未找到访客调度规则，按空 map 发） |
| 15 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[0].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 16 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[1].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 17 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[2].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 18 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[3].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 19 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[5].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 20 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[6].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 21 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[7].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 22 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[8].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 23 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[9].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 24 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[10].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 25 | 长度越界 | `CafeGetInfoResponse.CafeDBs[1].ProductionDB.ProductionParcelInfos` | 数组长度 0 不在观测范围 [1,2] | 新号没有进行中的家具生产；官方号有 1~2 个在生产 |
| 26 | 空数组首见 | `CafeGetInfoResponse.CafeDBs[1].ProductionDB.ProductionParcelInfos` | 官方样本中未出现空数组 | 新号没有进行中的家具生产；官方号有 1~2 个在生产 |
| 27 | 长度越界 | `CafeGetInfoResponse.FurnitureDBs` | 数组长度 22 不在观测范围 [27,27] | 新号家具 = 2 厅 × 11 件默认家具 = 22；官方 27 = cafe1 的 14 + cafe2 的 11 + 2 件未摆放 |
| 28 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[0].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 29 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[1].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 30 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[2].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 31 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[3].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 32 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[5].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 33 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[6].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 34 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[7].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 35 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[8].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 36 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[9].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 37 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[10].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 38 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[11].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 39 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[12].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 40 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[13].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 41 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[14].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 42 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[16].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 43 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[17].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 44 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[18].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 45 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[19].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 46 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[20].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 47 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[21].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 48 | 长度越界 | `CharacterListResponse.CharacterDBs` | 数组长度 4 不在观测范围 [46,46] | 新号 4 个初始角色（q1）；官方那个号 46 个（抽了 42 个） |
| 49 | 长度越界 | `CharacterListResponse.CharacterDBs[0].EquipmentServerIds` | 数组长度 0 不在观测范围 [3,3] | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 50 | 空数组首见 | `CharacterListResponse.CharacterDBs[0].EquipmentServerIds` | 官方样本中未出现空数组 | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 51 | 长度越界 | `CharacterListResponse.CharacterDBs[1].EquipmentServerIds` | 数组长度 0 不在观测范围 [3,3] | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 52 | 空数组首见 | `CharacterListResponse.CharacterDBs[1].EquipmentServerIds` | 官方样本中未出现空数组 | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 53 | 长度越界 | `CharacterListResponse.CharacterDBs[2].EquipmentServerIds` | 数组长度 0 不在观测范围 [3,3] | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 54 | 空数组首见 | `CharacterListResponse.CharacterDBs[2].EquipmentServerIds` | 官方样本中未出现空数组 | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 55 | 长度越界 | `CharacterListResponse.CharacterDBs[3].EquipmentServerIds` | 数组长度 0 不在观测范围 [3,3] | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 56 | 空数组首见 | `CharacterListResponse.CharacterDBs[3].EquipmentServerIds` | 官方样本中未出现空数组 | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 57 | 长度越界 | `EquipmentItemListResponse.EquipmentDBs` | 数组长度 0 不在观测范围 [84,84] | 新号没有装备（q3）；官方 84 件。官方该字段 items 里 Level/Tier 都是可选键，新号空数组不涉及 |
| 58 | 空数组首见 | `EquipmentItemListResponse.EquipmentDBs` | 官方样本中未出现空数组 | 新号没有装备（q3）；官方 84 件。官方该字段 items 里 Level/Tier 都是可选键，新号空数组不涉及 |
| 59 | 长度越界 | `EchelonListResponse.EchelonDBs` | 数组长度 1 不在观测范围 [8,8] | 新号只有 DefaultEchelonExcel 给的 1 条编队（q5）；官方 8 条 = 多内容解锁后累积（type 1/2/3/4/6/11） |
| 60 | 长度越界 | `CampaignListResponse.CampaignChapterClearRewardHistoryDBs` | 数组长度 0 不在观测范围 [12,12] | 新号一关没打 → 0 章奖励记录；官方 12 章 |
| 61 | 空数组首见 | `CampaignListResponse.CampaignChapterClearRewardHistoryDBs` | 官方样本中未出现空数组 | 新号一关没打 → 0 章奖励记录；官方 12 章 |
| 62 | 长度越界 | `CampaignListResponse.StageHistoryDBs` | 数组长度 0 不在观测范围 [90,90] | 新号一关没打 → 0 条关卡历史；官方 90 条 |
| 63 | 空数组首见 | `CampaignListResponse.StageHistoryDBs` | 官方样本中未出现空数组 | 新号一关没打 → 0 条关卡历史；官方 90 条 |
| 64 | 长度越界 | `MomoTalkOutLineResponse.MomoTalkOutLineDBs` | 数组长度 0 不在观测范围 [1,1] | 未找到初始 MomoTalk 规则 → 新号 0 条；官方 1 条（首次进入时由客户端触发） |
| 65 | 空数组首见 | `MomoTalkOutLineResponse.MomoTalkOutLineDBs` | 官方样本中未出现空数组 | 未找到初始 MomoTalk 规则 → 新号 0 条；官方 1 条（首次进入时由客户端触发） |
| 66 | 长度越界 | `MomoTalkOutLineResponse.FavorScheduleRecords` | map 键数 0 不在观测范围 [1,1] | 未找到初始好感日程规则 → 空 map；官方 1 个键 |
| 67 | 长度越界 | `ScenarioListResponse.ScenarioHistoryDBs` | 数组长度 0 不在观测范围 [191,191] | 新号剧情进度 0（q6：连序章 11000/11002 都不落库）；官方 191 条 |
| 68 | 空数组首见 | `ScenarioListResponse.ScenarioHistoryDBs` | 官方样本中未出现空数组 | 新号剧情进度 0（q6：连序章 11000/11002 都不落库）；官方 191 条 |
| 69 | 长度越界 | `ScenarioListResponse.ScenarioGroupHistoryDBs` | 数组长度 0 不在观测范围 [21,21] | 新号剧情组进度 0（q6）；官方 21 条 |
| 70 | 空数组首见 | `ScenarioListResponse.ScenarioGroupHistoryDBs` | 官方样本中未出现空数组 | 新号剧情组进度 0（q6）；官方 21 条 |
| 71 | 长度越界 | `BillingPurchaseListByYostarResponse.CountList` | 数组长度 0 不在观测范围 [4,4] | CountList 是 shop cash 的购买计数（含重置日期），运营/购买数据，ExcelDB 推不出 → 新号 0 条；官方 4 条 |
| 72 | 空数组首见 | `BillingPurchaseListByYostarResponse.CountList` | 官方样本中未出现空数组 | CountList 是 shop cash 的购买计数（含重置日期），运营/购买数据，ExcelDB 推不出 → 新号 0 条；官方 4 条 |
| 73 | 长度越界 | `EventContentPermanentListResponse.PermanentDBs` | 数组长度 0 不在观测范围 [22,22] | 新号没有任何永久活动进度 → 0 条；官方 22 个活动 |
| 74 | 空数组首见 | `EventContentPermanentListResponse.PermanentDBs` | 官方样本中未出现空数组 | 新号没有任何永久活动进度 → 0 条；官方 22 个活动 |
| 75 | 长度越界 | `AttachmentEmblemListResponse.EmblemDBs` | 数组长度 5 不在观测范围 [14,14] | 新号 5 个初始徽章（q3: DefaultParcelExcel ParcelType=20 五行）；官方 14 个 |
| 76 | 长度越界 | `ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[0].StageIds` | 数组长度 0 不在观测范围 [10,10] | 扫荡预设有 1 个（条数与官方一致），但 StageIds 是玩家已通关的关卡 → 新号空；官方 10 个 |
| 77 | 空数组首见 | `ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[0].StageIds` | 官方样本中未出现空数组 | 扫荡预设有 1 个（条数与官方一致），但 StageIds 是玩家已通关的关卡 → 新号空；官方 10 个 |
| 78 | 长度越界 | `StickerListResponse.StickerBookDB.UnusedStickerDBs` | 数组长度 0 不在观测范围 [20,20] | 未找到默认贴纸集合（StickerPageContent 23 行 ≠ 官方 20 条）→ 空；官方 20 个 |
| 79 | 空数组首见 | `StickerListResponse.StickerBookDB.UnusedStickerDBs` | 官方样本中未出现空数组 | 未找到默认贴纸集合（StickerPageContent 23 行 ≠ 官方 20 条）→ 空；官方 20 个 |
| 80 | 长度越界 | `PickupFirstGetHistoryDBs` | 数组长度 0 不在观测范围 [1,1] | 新号没抽过卡 → 空；官方 1 条（{ShopRecruitId, LogDate} 抽卡历史） |
| 81 | 空数组首见 | `PickupFirstGetHistoryDBs` | 官方样本中未出现空数组 | 新号没抽过卡 → 空；官方 1 条（{ShopRecruitId, LogDate} 抽卡历史） |
| 82 | 长度越界 | `AccountLevelRewardIds` | 数组长度 0 不在观测范围 [1,1] | AccountLevelRewardDBSchema 只有 Level 30/40/45/50/55/60 六个里程碑，新号 1 级 → 空；官方那条给了 [1] 与"已达阈值"不自洽（1<30），语义**未找到**，按表里唯一可推的规则实现 |
| 83 | 空数组首见 | `AccountLevelRewardIds` | 官方样本中未出现空数组 | AccountLevelRewardDBSchema 只有 Level 30/40/45/50/55/60 六个里程碑，新号 1 级 → 空；官方那条给了 [1] 与"已达阈值"不自洽（1<30），语义**未找到**，按表里唯一可推的规则实现 |

分类合计：可选键缺失 40, 空数组首见 18, 长度越界 25；**FAIL = 0**。

### 账号 B（中期号（手工状态））的 WARN 全量清单：89 条

| # | 类别 | spec 路径 | 官方观测 | 为什么可以接受（逐条） |
|---:|---|---|---|---|
| 1 | 长度越界 | `CafeGetInfoResponse.CafeDBs[0].CafeVisitCharacterDBs` | map 键数 0 不在观测范围 [3,4] | 新号咖啡厅没有访客角色；官方号有 3~4 个（未找到访客调度规则，按空 map 发） |
| 2 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[0].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 3 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[1].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 4 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[2].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 5 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[3].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 6 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[5].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 7 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[6].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 8 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[7].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 9 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[8].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 10 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[9].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 11 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[10].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 12 | 长度越界 | `CafeGetInfoResponse.CafeDBs[0].ProductionDB.ProductionParcelInfos` | 数组长度 0 不在观测范围 [1,2] | 新号没有进行中的家具生产；官方号有 1~2 个在生产 |
| 13 | 空数组首见 | `CafeGetInfoResponse.CafeDBs[0].ProductionDB.ProductionParcelInfos` | 官方样本中未出现空数组 | 新号没有进行中的家具生产；官方号有 1~2 个在生产 |
| 14 | 长度越界 | `CafeGetInfoResponse.CafeDBs[1].CafeVisitCharacterDBs` | map 键数 0 不在观测范围 [3,4] | 新号咖啡厅没有访客角色；官方号有 3~4 个（未找到访客调度规则，按空 map 发） |
| 15 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[0].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 16 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[1].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 17 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[2].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 18 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[3].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 19 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[5].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 20 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[6].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 21 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[7].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 22 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[8].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 23 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[9].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 24 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[10].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 25 | 长度越界 | `CafeGetInfoResponse.CafeDBs[1].ProductionDB.ProductionParcelInfos` | 数组长度 0 不在观测范围 [1,2] | 新号没有进行中的家具生产；官方号有 1~2 个在生产 |
| 26 | 空数组首见 | `CafeGetInfoResponse.CafeDBs[1].ProductionDB.ProductionParcelInfos` | 官方样本中未出现空数组 | 新号没有进行中的家具生产；官方号有 1~2 个在生产 |
| 27 | 长度越界 | `CafeGetInfoResponse.FurnitureDBs` | 数组长度 22 不在观测范围 [27,27] | 新号家具 = 2 厅 × 11 件默认家具 = 22；官方 27 = cafe1 的 14 + cafe2 的 11 + 2 件未摆放 |
| 28 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[0].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 29 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[1].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 30 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[2].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 31 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[3].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 32 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[5].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 33 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[6].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 34 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[7].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 35 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[8].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 36 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[9].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 37 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[10].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 38 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[11].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 39 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[12].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 40 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[13].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 41 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[14].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 42 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[16].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 43 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[17].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 44 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[18].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 45 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[19].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 46 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[20].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 47 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[21].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 48 | 长度越界 | `CharacterListResponse.CharacterDBs` | 数组长度 6 不在观测范围 [46,46] | 新号 4 个初始角色（q1）；官方那个号 46 个（抽了 42 个） |
| 49 | 长度越界 | `CharacterListResponse.CharacterDBs[0].PotentialStats` | map 键数 0 不在观测范围 [3,3] | 官方观测长度比新号长（新号数据少），结构没错 |
| 50 | 长度越界 | `CharacterListResponse.CharacterDBs[1].PotentialStats` | map 键数 0 不在观测范围 [3,3] | 官方观测长度比新号长（新号数据少），结构没错 |
| 51 | 长度越界 | `CharacterListResponse.CharacterDBs[2].PotentialStats` | map 键数 0 不在观测范围 [3,3] | 官方观测长度比新号长（新号数据少），结构没错 |
| 52 | 长度越界 | `CharacterListResponse.CharacterDBs[3].PotentialStats` | map 键数 0 不在观测范围 [3,3] | 官方观测长度比新号长（新号数据少），结构没错 |
| 53 | 长度越界 | `CharacterListResponse.CharacterDBs[4].EquipmentServerIds` | 数组长度 0 不在观测范围 [3,3] | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 54 | 空数组首见 | `CharacterListResponse.CharacterDBs[4].EquipmentServerIds` | 官方样本中未出现空数组 | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 55 | 长度越界 | `CharacterListResponse.CharacterDBs[4].PotentialStats` | map 键数 0 不在观测范围 [3,3] | 官方观测长度比新号长（新号数据少），结构没错 |
| 56 | 长度越界 | `CharacterListResponse.CharacterDBs[5].EquipmentServerIds` | 数组长度 0 不在观测范围 [3,3] | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 57 | 空数组首见 | `CharacterListResponse.CharacterDBs[5].EquipmentServerIds` | 官方样本中未出现空数组 | 新号没有任何装备（q3: EquipmentDBs=[]），所以每个角色的 3 个装备槽都是 0 |
| 58 | 长度越界 | `CharacterListResponse.CharacterDBs[5].PotentialStats` | map 键数 0 不在观测范围 [3,3] | 官方观测长度比新号长（新号数据少），结构没错 |
| 59 | 长度越界 | `EquipmentItemListResponse.EquipmentDBs` | 数组长度 0 不在观测范围 [84,84] | 新号没有装备（q3）；官方 84 件。官方该字段 items 里 Level/Tier 都是可选键，新号空数组不涉及 |
| 60 | 空数组首见 | `EquipmentItemListResponse.EquipmentDBs` | 官方样本中未出现空数组 | 新号没有装备（q3）；官方 84 件。官方该字段 items 里 Level/Tier 都是可选键，新号空数组不涉及 |
| 61 | 长度越界 | `EchelonListResponse.EchelonDBs` | 数组长度 2 不在观测范围 [8,8] | 新号只有 DefaultEchelonExcel 给的 1 条编队（q5）；官方 8 条 = 多内容解锁后累积（type 1/2/3/4/6/11） |
| 62 | 长度越界 | `EchelonListResponse.EchelonDBs[1].SupportSlotServerIds` | 数组长度 0 不在观测范围 [2,2] | 官方观测长度比新号长（新号数据少），结构没错 |
| 63 | 空数组首见 | `EchelonListResponse.EchelonDBs[1].SupportSlotServerIds` | 官方样本中未出现空数组 | 官方样本里这个数组从没空过（因为官方号有进度），新号没有 → 空 |
| 64 | 长度越界 | `CampaignListResponse.CampaignChapterClearRewardHistoryDBs` | 数组长度 0 不在观测范围 [12,12] | 新号一关没打 → 0 章奖励记录；官方 12 章 |
| 65 | 空数组首见 | `CampaignListResponse.CampaignChapterClearRewardHistoryDBs` | 官方样本中未出现空数组 | 新号一关没打 → 0 章奖励记录；官方 12 章 |
| 66 | 长度越界 | `CampaignListResponse.StageHistoryDBs` | 数组长度 3 不在观测范围 [90,90] | 新号一关没打 → 0 条关卡历史；官方 90 条 |
| 67 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[0].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 68 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[0].Star1Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 69 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[0].Star2Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 70 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[0].Star3Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 71 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[1].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 72 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[1].Star1Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 73 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[1].Star2Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 74 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[1].Star3Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 75 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[2].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 76 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[2].Star1Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 77 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[2].Star2Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 78 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[2].Star3Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 79 | 长度越界 | `MomoTalkOutLineResponse.FavorScheduleRecords` | map 键数 0 不在观测范围 [1,1] | 未找到初始好感日程规则 → 空 map；官方 1 个键 |
| 80 | 长度越界 | `ScenarioListResponse.ScenarioHistoryDBs` | 数组长度 12 不在观测范围 [191,191] | 新号剧情进度 0（q6：连序章 11000/11002 都不落库）；官方 191 条 |
| 81 | 长度越界 | `ScenarioListResponse.ScenarioGroupHistoryDBs` | 数组长度 3 不在观测范围 [21,21] | 新号剧情组进度 0（q6）；官方 21 条 |
| 82 | 长度越界 | `BillingPurchaseListByYostarResponse.CountList` | 数组长度 1 不在观测范围 [4,4] | CountList 是 shop cash 的购买计数（含重置日期），运营/购买数据，ExcelDB 推不出 → 新号 0 条；官方 4 条 |
| 83 | 长度越界 | `EventContentPermanentListResponse.PermanentDBs` | 数组长度 3 不在观测范围 [22,22] | 新号没有任何永久活动进度 → 0 条；官方 22 个活动 |
| 84 | 长度越界 | `AttachmentEmblemListResponse.EmblemDBs` | 数组长度 8 不在观测范围 [14,14] | 新号 5 个初始徽章（q3: DefaultParcelExcel ParcelType=20 五行）；官方 14 个 |
| 85 | 长度越界 | `ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[0].StageIds` | 数组长度 0 不在观测范围 [10,10] | 扫荡预设有 1 个（条数与官方一致），但 StageIds 是玩家已通关的关卡 → 新号空；官方 10 个 |
| 86 | 空数组首见 | `ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[0].StageIds` | 官方样本中未出现空数组 | 扫荡预设有 1 个（条数与官方一致），但 StageIds 是玩家已通关的关卡 → 新号空；官方 10 个 |
| 87 | 长度越界 | `StickerListResponse.StickerBookDB.UnusedStickerDBs` | 数组长度 5 不在观测范围 [20,20] | 未找到默认贴纸集合（StickerPageContent 23 行 ≠ 官方 20 条）→ 空；官方 20 个 |
| 88 | 长度越界 | `PickupFirstGetHistoryDBs` | 数组长度 0 不在观测范围 [1,1] | 新号没抽过卡 → 空；官方 1 条（{ShopRecruitId, LogDate} 抽卡历史） |
| 89 | 空数组首见 | `PickupFirstGetHistoryDBs` | 官方样本中未出现空数组 | 新号没抽过卡 → 空；官方 1 条（{ShopRecruitId, LogDate} 抽卡历史） |

分类合计：可选键缺失 52, 空数组首见 9, 长度越界 28；**FAIL = 0**。

### 账号 C（官方样本回放）的 WARN 全量清单：309 条

| # | 类别 | spec 路径 | 官方观测 | 为什么可以接受（逐条） |
|---:|---|---|---|---|
| 1 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[0].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 2 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[1].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 3 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[2].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 4 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[3].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 5 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[4].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 6 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[6].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 7 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[7].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 8 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[8].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 9 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[9].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 10 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[10].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 11 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[11].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 12 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[12].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 13 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[0].FurnitureDBs[13].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 14 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[0].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 15 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[1].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 16 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[2].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 17 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[3].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 18 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[5].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 19 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[6].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 20 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[7].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 21 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[8].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 22 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[9].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 23 | 可选键缺失 | `CafeGetInfoResponse.CafeDBs[1].FurnitureDBs[10].Rotation` | always=false 未出现 (官方观测 2/25 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 24 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[0].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 25 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[1].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 26 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[2].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 27 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[3].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 28 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[4].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 29 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[6].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 30 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[7].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 31 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[8].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 32 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[9].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 33 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[10].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 34 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[11].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 35 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[12].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 36 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[13].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 37 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[14].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 38 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[15].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 39 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[16].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 40 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[17].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 41 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[18].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 42 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[19].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 43 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[21].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 44 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[22].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 45 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[23].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 46 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[24].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 47 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[25].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 48 | 可选键缺失 | `CafeGetInfoResponse.FurnitureDBs[26].Rotation` | always=false 未出现 (官方观测 2/27 次有) | Rotation 是 spec 里的 always=false 可选键：官方 22~27 件家具里只有 2 件带值（FurnitureId=5 那份 270°），其余省略 —— proto3 可选标量 presence 语义，不是缺字段 |
| 49 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[0].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 50 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[0].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 51 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[0].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 52 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[1].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 53 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[1].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 54 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[1].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 55 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[2].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 56 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[2].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 57 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[2].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 58 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[3].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 59 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[3].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 60 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[3].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 61 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[4].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 62 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[4].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 63 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[4].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 64 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[5].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 65 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[5].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 66 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[5].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 67 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[6].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 68 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[6].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 69 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[6].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 70 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[7].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 71 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[7].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 72 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[7].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 73 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[8].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 74 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[8].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 75 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[8].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 76 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[9].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 77 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[9].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 78 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[9].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 79 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[10].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 80 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[10].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 81 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[10].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 82 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[11].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 83 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[11].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 84 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[11].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 85 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[12].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 86 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[12].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 87 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[12].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 88 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[13].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 89 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[13].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 90 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[13].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 91 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[14].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 92 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[14].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 93 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[14].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 94 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[15].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 95 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[15].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 96 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[15].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 97 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[16].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 98 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[16].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 99 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[16].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 100 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[38].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 101 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[38].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 102 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[38].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 103 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[39].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 104 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[39].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 105 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[39].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 106 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[40].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 107 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[40].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 108 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[40].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 109 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[41].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 110 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[41].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 111 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[41].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 112 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[42].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 113 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[42].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 114 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[42].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 115 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[43].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 116 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[43].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 117 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[43].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 118 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[44].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 119 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[44].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 120 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[44].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 121 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[45].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 122 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[45].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 123 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[45].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 124 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[46].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 125 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[46].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 126 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[46].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 127 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[47].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 128 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[47].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 129 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[47].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 130 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[48].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 131 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[48].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 132 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[48].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 133 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[49].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 134 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[49].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 135 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[49].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 136 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[50].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 137 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[50].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 138 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[50].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 139 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[51].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 140 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[51].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 141 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[51].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 142 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[52].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 143 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[52].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 144 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[52].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 145 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[53].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 146 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[53].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 147 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[53].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 148 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[54].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 149 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[54].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 150 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[54].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 151 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[64].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 152 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[64].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 153 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[64].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 154 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[65].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 155 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[65].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 156 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[65].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 157 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[66].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 158 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[66].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 159 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[66].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 160 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[67].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 161 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[67].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 162 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[67].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 163 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[68].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 164 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[68].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 165 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[68].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 166 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[69].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 167 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[69].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 168 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[69].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 169 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[70].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 170 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[70].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 171 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[70].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 172 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[71].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 173 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[71].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 174 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[71].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 175 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[72].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 176 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[72].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 177 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[72].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 178 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[73].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 179 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[73].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 180 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[73].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 181 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[74].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 182 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[74].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 183 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[74].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 184 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[75].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 185 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[75].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 186 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[75].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 187 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[76].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 188 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[76].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 189 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[76].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 190 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[77].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 191 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[77].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 192 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[77].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 193 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[78].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 194 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[78].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 195 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[78].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 196 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[79].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 197 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[79].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 198 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[79].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 199 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[80].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 200 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[80].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 201 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[80].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 202 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[81].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 203 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[81].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 204 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[81].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 205 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[82].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 206 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[82].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 207 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[82].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 208 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[83].Level` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 209 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[83].Tier` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 210 | 可选键缺失 | `EquipmentItemListResponse.EquipmentDBs[83].BoundCharacterServerId` | always=false 未出现 (官方观测 30/84 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 211 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[5].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 212 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[5].Star1Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 213 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[5].Star2Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 214 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[5].Star3Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 215 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[6].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 216 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[6].Star1Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 217 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[6].Star2Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 218 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[6].Star3Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 219 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[7].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 220 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[7].Star1Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 221 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[7].Star2Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 222 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[7].Star3Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 223 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[11].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 224 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[12].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 225 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[13].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 226 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[14].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 227 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[14].Star1Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 228 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[14].Star2Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 229 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[14].Star3Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 230 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[15].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 231 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[16].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 232 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[17].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 233 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[18].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 234 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[19].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 235 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[20].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 236 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[20].Star1Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 237 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[20].Star2Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 238 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[20].Star3Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 239 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[21].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 240 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[21].Star1Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 241 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[21].Star2Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 242 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[21].Star3Flag` | always=false 未出现 (官方观测 84/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 243 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[22].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 244 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[23].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 245 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[24].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 246 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[25].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 247 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[26].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 248 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[27].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 249 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[29].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 250 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[30].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 251 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[31].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 252 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[32].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 253 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[33].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 254 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[34].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 255 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[35].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 256 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[36].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 257 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[37].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 258 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[38].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 259 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[39].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 260 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[40].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 261 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[41].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 262 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[42].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 263 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[43].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 264 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[44].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 265 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[45].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 266 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[46].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 267 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[47].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 268 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[48].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 269 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[49].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 270 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[50].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 271 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[51].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 272 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[52].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 273 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[53].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 274 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[54].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 275 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[55].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 276 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[56].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 277 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[57].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 278 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[58].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 279 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[59].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 280 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[60].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 281 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[61].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 282 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[62].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 283 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[63].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 284 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[64].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 285 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[65].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 286 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[66].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 287 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[67].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 288 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[68].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 289 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[69].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 290 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[70].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 291 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[71].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 292 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[72].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 293 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[73].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 294 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[74].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 295 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[75].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 296 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[76].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 297 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[77].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 298 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[78].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 299 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[79].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 300 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[80].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 301 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[81].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 302 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[82].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 303 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[83].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 304 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[84].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 305 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[85].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 306 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[86].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 307 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[87].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 308 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[88].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |
| 309 | 可选键缺失 | `CampaignListResponse.StageHistoryDBs[89].TacticClearCountWithRankSRecord` | always=false 未出现 (官方观测 9/90 次有) | spec 标记 always=false 的可选键，官方只在部分实例上出现 |

分类合计：可选键缺失 309；**FAIL = 0**。
