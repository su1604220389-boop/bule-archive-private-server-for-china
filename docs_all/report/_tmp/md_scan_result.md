# global-metadata.dat 单字节 XOR 全量扫描报告

- 文件: `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`
- 大小: 38426024 (0x24a55a8)
- SHA256: `2352CB570A4652CC76574B9EB87A2941CF906237FF1F1A80454AB1B5634B47E6`  (与预期一致)
- 扫描: 256 个 key x 64 个关键词, 耗时 157.4s
- numpy: 可用

## 0. header 破解

```
前 256 字节:
00000000  94 43 72 12 18 4b 9e ec 66 67 66 66 a6 62 65 66  .Cr..K..fgff.bef
00000010  a6 63 65 66 6e a2 6d 66 ae af 68 66 ee 1a 0a 66  .cefn.mf..hf...f
00000020  36 20 1d 66 de 5e 66 66 6e 19 1d 66 6a cb 69 66  6 .f.^ffn..fj.if
00000030  72 4a ed 66 da e3 f6 66 b6 d7 7d 67 46 99 67 66  rJ.f...f..}gF.gf
00000040  96 d6 7b 67 82 66 69 66 be d7 4a 67 ee 7a 35 66  ..{g.fif..Jg.z5f
00000050  06 a8 19 67 da 96 67 66 7a d9 e7 67 12 d0 49 66  ...g..gfz..g..If
00000060  f6 13 d7 67 ee 41 45 66 7e fb b2 67 96 a0 67 66  ...g.AEf~..g..gf
00000070  6e 02 b0 67 ee 7d 66 66 f6 19 b0 67 76 86 66 66  n..g.}ff...gv.ff
00000080  c6 39 b1 67 62 bb 66 66 c2 5a be 67 3e bf 66 66  .9.gb.ff.Z.g>.ff
00000090  9a 73 bf 67 ba e0 75 66 be fa 8a 67 16 e2 65 66  .s.g..uf...g..ef
000000a0  2e 47 96 67 3e 45 49 66 c6 22 79 64 7e 76 66 66  .G.g>EIf."yd~vff
000000b0  de 32 79 64 a6 7f 66 66 1e 08 79 64 5e 0b 66 66  .2yd..ff..yd^.ff
000000c0  d6 bd 79 64 7e 6f 66 66 ae 82 79 64 36 cf 7e 66  ..yd~off..yd6.~f
000000d0  7e e8 5e 64 be ee 6b 66 96 70 20 64 fa 24 64 66  ~.^d..kf.p d.$df
000000e0  ea 3f 2e 64 be ba 67 66 02 50 2c 64 66 66 66 66  .?.d..gf.P,dffff
000000f0  02 50 2c 64 66 66 66 66 02 50 2c 64 22 79 66 66  .P,dffff.P,d"yff
```

对 `uint32` 序列做 256 个单字节 key 试验, 唯一通过"跳过前 2 word 后 offset 单调不减 + 范围合法" 的 key 是 **0x66**;
`magic ^0x66 = 0x741425f2`(不是 0xFAB11BAF), `version ^0x66 = 0x8af82d7e`(垃圾),
说明 **前 8 字节 (sanity/version) 另行处理**, 从 0x08 起整个 header 是 `^0x66`。

| # | 起始 | 大小 | 结束 | 说明 |
|---|---|---|---|---|
| header | 0x00000000 | 0x100 | 0x00000100 | 64 word, ^0x66 |
| sec00 | 0x00000100 | 0x0304c0 | 0x000305c0 | OK |
| sec01 | 0x000305c0 | 0x0bc408 | 0x000ec9c8 | OK |
| sec02 | 0x000ec9c8 | 0x6c7c88 | 0x007b4650 | OK |
| sec03 | 0x007b4650 | 0x0038b8 | 0x007b7f08 | OK |
| sec04 | 0x007b7f08 | 0x0fad0c | 0x008b2c14 | OK |
| sec05 | 0x008b2c14 | 0x9085bc | 0x011bb1d0 | OK |
| sec06 | 0x011bb1d0 | 0x01ff20 | 0x011db0f0 | OK |
| sec07 | 0x011db0f0 | 0x0f00e4 | 0x012cb1d4 | OK |
| sec08 | 0x012cb1d8 | 0x531c88 | 0x017fce60 | OK |
| sec09 | 0x017fce60 | 0x01f0bc | 0x0181bf1c | OK |
| sec10 | 0x0181bf1c | 0x2fb674 | 0x01b17590 | OK |
| sec11 | 0x01b17590 | 0x232788 | 0x01d49d18 | OK |
| sec12 | 0x01d49d18 | 0x01c6f0 | 0x01d66408 | OK |
| sec13 | 0x01d66408 | 0x001b88 | 0x01d67f90 | OK |
| sec14 | 0x01d67f90 | 0x00e010 | 0x01d75fa0 | OK |
| sec15 | 0x01d75fa0 | 0x00dd04 | 0x01d83ca4 | OK |
| sec16 | 0x01d83ca4 | 0x00d958 | 0x01d915fc | OK |
| sec17 | 0x01d915fc | 0x1386dc | 0x01ec9cd8 | OK |
| sec18 | 0x01ec9cd8 | 0x038470 | 0x01f02148 | OK |
| sec19 | 0x01f02148 | 0x2f2358 | 0x021f44a0 | OK |
| sec20 | 0x021f44a0 | 0x001018 | 0x021f54b8 | OK |
| sec21 | 0x021f54b8 | 0x0019c0 | 0x021f6e78 | OK |
| sec22 | 0x021f6e78 | 0x006d38 | 0x021fdbb0 | OK |
| sec23 | 0x021fdbb0 | 0x000918 | 0x021fe4c8 | OK |
| sec24 | 0x021fe4c8 | 0x18a950 | 0x02388e18 | OK |
| sec25 | 0x02388e18 | 0x0d88d8 | 0x024616f0 | OK |
| sec26 | 0x024616f0 | 0x02429c | 0x0248598c | OK |
| sec27 | 0x0248598c | 0x01dcd8 | 0x024a3664 | OK |
| sec28 | 0x024a3664 | 0x000000 | 0x024a3664 | OK |
| sec29 | 0x024a3664 | 0x000000 | 0x024a3664 | OK |
| sec30 | 0x024a3664 | 0x001f44 | 0x024a55a8 | OK |

全部 31 段首尾相接、末段正好等于文件长度 (0x24a55a8) —— 这是 header 被正确解开的硬证据。

### 自检
```
PASS RSA PEM @0x0178CC60 明文  b'-----BEGIN PUBLIC KEY-----\n'
PASS URL @0x0c172b ^0xB5  b'http://test-ba.yostar.net:5210/api/state'
PASS header ^0x66 段表依次相接  gaps=[0, 4]
PASS header ^0x66 末段==EOF  last_end=0x24a55a8 filesize=0x24a55a8
PASS sec00 大小 == 24728*8  0x304c0
PASS BlueArchive @0xec9c8 明文  b'BlueArchive\x00\x00\x00\x00\x00Blue'
```

## 1. key -> 命中关键词

| key | 命中数 | 命中的关键词 |
|---|---|---|
| 0x00 | 589 | LoginState, WaitForRequest, IsFinished, OnLoginFinish, HandleAccountAuthResponseMessage, Nickname, RelayPackets, LoginTask, Account_Auth, Account_CheckYostar, ResultState, ErrorCode, Protocol, ServerInfoConnectionGroupData ... |
| 0x01 | 1 | Protocol |
| 0x07 | 1 | ErrorCode |
| 0x0a | 2 | Protocol |
| 0x13 | 2 | Protocol |
| 0x19 | 1 | ErrorCode |
| 0x1a | 1 | Reason |
| 0x20 | 1 | Protocol |
| 0x2c | 1 | ErrorCode |
| 0x30 | 1 | Protocol |
| 0x36 | 1 | Protocol |
| 0x44 | 1 | Protocol |
| 0x51 | 1 | Protocol |
| 0x55 | 1 | 通知 |
| 0x5f | 1 | Protocol |
| 0x66 | 121 | IsFinished, Nickname, ErrorCode, Protocol, ServerInfoConnectionGroupData, CallbackUrl, Bypass, Reason, JOSYdf8ys97uhFYS |
| 0x77 | 1 | Protocol |
| 0x92 | 1 | Reason |
| 0x94 | 1 | Reason |
| 0x96 | 1 | Protocol |
| 0x9a | 1 | Protocol |
| 0x9f | 1 | Protocol |
| 0xa0 | 1 | Protocol |
| 0xa7 | 1 | Protocol |
| 0xaf | 2 | Protocol |
| 0xb2 | 1 | Protocol |
| 0xb5 | 3 | yostar.net |
| 0xc4 | 1 | Protocol |
| 0xc6 | 1 | Reason |
| 0xc7 | 2 | Protocol, 请确认网络连接状态后重试 |
| 0xc8 | 1 | Bypass |
| 0xc9 | 1 | Nickname |
| 0xcb | 1 | Protocol |
| 0xcc | 1 | ErrorCode |
| 0xd0 | 2 | Protocol |
| 0xd2 | 1 | Nickname |
| 0xd7 | 1 | Protocol |
| 0xdb | 1 | Protocol |
| 0xdd | 1 | Bypass |
| 0xe3 | 1 | Nickname |
| 0xe9 | 1 | JOSYdf8ys97uhFYS |
| 0xef | 1 | Protocol |
| 0xf1 | 1 | Protocol |
| 0xf9 | 1 | Protocol |
| 0xfc | 2 | Reason |
| 0xfe | 1 | 网络连接失败 |

> 说明: 命中数 = 该 key 下所有关键词的原始匹配次数(含重复)。

## 2. 每个关键词的命中明细

### 登录/协议(客户端方法名)

**`LoginState`** — 2 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0013fdd3` | `ingTicket>k__BackingField.WaitingTicket.LoginState.Finished.Failed.<CheckContinueCampaign>` |
| 0x00 | `0x006a87fb` | `sCode.ReceiveState.Resp.ValidThrough.FtpLoginState.NotLoggedIn.LoggedIn.LoggedInButNeedsRe` |

**`WaitForRequest`** — 4 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0021a6d6` | `rError.BuildErrorMessage.timeOut.Resend.WaitForRequest.httpMessage.<ResponseHandler>k__Backing` |
| 0x00 | `0x0021a803` | `ror>b__44_0.<HandleServerError>b__44_1.<WaitForRequest>d__59.HttpMethodType.GET.POST.HttpMessa` |
| 0x00 | `0x003d91d0` | `Program-Scripts-Network-HttpGameSession-WaitForRequest0.Assets-_MX-Program-Scripts-Network-Htt` |
| 0x00 | `0x0078775f` | `s.SetMaxConcurrentRequests.QueueRequest.WaitForRequestToBeActive.OnWebAsyncOpComplete.s_MaxReq` |

**`IsFinished`** — 6 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0021a587` | `sionStateChangedMessage.get_Session.get_IsFinished.<Session>k__BackingField.Session.IsFini` |
| 0x00 | `0x0021a5b3` | `nished.<Session>k__BackingField.Session.IsFinished.HttpGameSession.get_ResponseHandler.set` |
| 0x00 | `0x00226fb4` | `get_IsLevelLoaded.set_IsLevelLoaded.set_IsFinished.previousSceneGroupId.finishedAction.Han` |
| 0x00 | `0x002271a4` | `ngField.<IsLevelLoaded>k__BackingField.<IsFinished>k__BackingField.PreviousSceneGroupId.Ar` |
| 0x00 | `0x00495e43` | `-Network-SessionStateChangedMessage-get_IsFinished0.Assets-_MX-Program-Scripts-Network-Ses` |
| 0x66 | `0x007b376a` | `...."......"....../.......f$....."....../. .......f$.....#......%...../.......f$.....#....` |

**`OnLoginFinish`** — 10 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0013faf0` | `ungeon.HandleAccountAuthResponseMessage.OnLoginFinish.devId.StartLoginWithAccountPassCheck.on` |
| 0x00 | `0x0013fcd3` | `>b__40_0.<ShowTTSDownLoadPopup>b__40_1.<OnLoginFinish>g__CloseTitle\|52_6.<SkipAccountCallname` |
| 0x00 | `0x00140296` | `et>b__0.<ErrorQueuingGetTicket>b__14_1.<OnLoginFinish>b__52_0.<OnLoginFinish>b__52_1.<OnLogin` |
| 0x00 | `0x001402ad` | `tTicket>b__14_1.<OnLoginFinish>b__52_0.<OnLoginFinish>b__52_1.<OnLoginFinish>b__52_3.<>9__52_` |
| 0x00 | `0x001402c4` | `nFinish>b__52_0.<OnLoginFinish>b__52_1.<OnLoginFinish>b__52_3.<>9__52_1.<>9__52_3.<co_SyncTut` |
| 0x00 | `0x001404dd` | `>b__3.<CheckContinueSchoolDungeon>b__2.<OnLoginFinish>b__2.<OnLoginFinish>g__CompletePatch\|4.` |
| 0x00 | `0x001404f1` | `SchoolDungeon>b__2.<OnLoginFinish>b__2.<OnLoginFinish>g__CompletePatch\|4.<OnLoginFinish>g__Co` |
| 0x00 | `0x00140513` | `b__2.<OnLoginFinish>g__CompletePatch\|4.<OnLoginFinish>g__ContinuedContentProcess\|5.<OnLoginFi` |
| 0x00 | `0x0014053f` | `ginFinish>g__ContinuedContentProcess\|5.<OnLoginFinish>b__7.mxAccount.<StartLoginWithAccountPa` |
| 0x00 | `0x0040be7c` | `k-CheckContinueSchoolDungeon0.LoginTask-OnLoginFinish0.LoginTask-co_RelayPacketsProcess0.Logi` |

**`HandleAccountAuthResponseMessage`** — 2 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0013facf` | `eWeekDungeon.CheckContinueSchoolDungeon.HandleAccountAuthResponseMessage.OnLoginFinish.devId.StartLoginWithAccou` |
| 0x00 | `0x0040bedb` | `ask-StartRequestRelayPackets0.LoginTask-HandleAccountAuthResponseMessage0.LoginTask-HandleAccountCreateResponseM` |

**`Nickname`** — 94 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0012b004` | `sion>b__2_0.<ProcessSession>d__2.AccountNicknameResponseMessage.AccountNicknameNetworkTa` |
| 0x00 | `0x0012b023` | `2.AccountNicknameResponseMessage.AccountNicknameNetworkTask.AccountPassCheckResponseMess` |
| 0x00 | `0x00136247` | `getLayer.AccountService.nickname.IsValidNickname.callname.IsValidCallname.AttachmentFilt` |
| 0x00 | `0x0013f826` | `ccountCreateResponseMessage.ErrorAccountNickname.HandleAccountNicknameResponseMessage.Er` |
| 0x00 | `0x0013f83c` | `ssage.ErrorAccountNickname.HandleAccountNicknameResponseMessage.ErrorAccountCallname.Han` |
| 0x00 | `0x0013f9bb` | `ackets.co_SyncTutorialCompletionIds.ShowNicknamePopup.ShowCallnamePopup.ShowTTSDownLoadP` |
| 0x00 | `0x0013fa7f` | `ryLoginWithAccountCheckYostar.SetAccountNickname.SetAccountCallname.CheckContinueWeekDun` |
| 0x00 | `0x0013fc23` | `BeforehandGachaProceeding.RequestAccountNickname.hash.<AccountAuthStart>b__20_0.<Account` |
| 0x00 | `0x0015ea53` | `e.RefreshFavorite.RefreshComment.RefreshNickname.RefreshCallname.RefreshLevelExp.Refresh` |
| 0x00 | `0x0015eafe` | `t.RefreshNewbieObject.OnClickUUID.OnEditNickname.OnEditComment.OnEditCallname.co_PlayCal` |
| 0x00 | `0x0015ee13` | `.newbieIcon.newbieTagInfoComment.<OnEditNickname>b__57_0.<OnEditNickname>b__57_1.<OnEdit` |
| 0x00 | `0x0015ee2b` | `oComment.<OnEditNickname>b__57_0.<OnEditNickname>b__57_1.<OnEditComment>b__58_0.<OnEditC` |
| 0x00 | `0x001b5f25` | `_Input_CommentMode.IdCard.UIPopup_Input_Nickname.UIPopup_Input_ReturnResult.limitLength.` |
| 0x00 | `0x001ce668` | `odLabel.LoginChangeButtonClicked.UITitleNicknamePopup.nicknameInput.uIPopup_Option_Toggl` |

**`RelayPackets`** — 7 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0013f98d` | `eate.RequestAccountCallname.StartRequestRelayPackets.co_SyncTutorialCompletionIds.ShowNickna` |
| 0x00 | `0x0013fbb9` | `ponseMessage.RequestAccountPassCheck.co_RelayPacketsProcess.OnLoginFail.co_SyncShopListTutor` |
| 0x00 | `0x00140585` | `StartLoginWithAccountPassCheck>b__0.<co_RelayPacketsProcess>b__0.errorExist.<co_RelayPackets` |
| 0x00 | `0x001405ad` | `RelayPacketsProcess>b__0.errorExist.<co_RelayPacketsProcess>b__1.queueState.<co_RelayPackets` |
| 0x00 | `0x001405d5` | `RelayPacketsProcess>b__1.queueState.<co_RelayPacketsProcess>d__60.<taskQueue>5__2.<co_SyncSh` |
| 0x00 | `0x0040be98` | `0.LoginTask-OnLoginFinish0.LoginTask-co_RelayPacketsProcess0.LoginTask-StartRequestRelayPack` |
| 0x00 | `0x0040bec3` | `ayPacketsProcess0.LoginTask-StartRequestRelayPackets0.LoginTask-HandleAccountAuthResponseMes` |

**`LoginTask`** — 60 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0013f654` | `lResponseMessage>g__CoPortalUsed\|25_0>d.LoginTask.CheckContinueCampaign.CheckContinueEven` |
| 0x00 | `0x003dd675` | `omotalkInfoComponent-GetOutlineMessage0.LoginTask-Close0.LoginTask-HandleContentSaveDisca` |
| 0x00 | `0x003dd686` | `ent-GetOutlineMessage0.LoginTask-Close0.LoginTask-HandleContentSaveDiscardResponseMessage` |
| 0x00 | `0x003dd6b9` | `andleContentSaveDiscardResponseMessage0.LoginTask-ErrorContentSaveDiscard0.LoginTask-Requ` |
| 0x00 | `0x003dd6dc` | `age0.LoginTask-ErrorContentSaveDiscard0.LoginTask-RequestContentSaveDiscard0.MXContentBri` |
| 0x00 | `0x0040b482` | `.EventContentTask-RequestEnterSubStage0.LoginTask-CheckContinueCampaign0.LoginTask-CheckC` |
| 0x00 | `0x0040b4a3` | `Stage0.LoginTask-CheckContinueCampaign0.LoginTask-CheckContinueEventContent0.ScenarioMode` |
| 0x00 | `0x0040b505` | `tScenarioModeFromStoryStrategyContinue0.LoginTask-CheckContinueStoryStrategy0.LoginTask-C` |
| 0x00 | `0x0040b52b` | `0.LoginTask-CheckContinueStoryStrategy0.LoginTask-CheckContinueConquestBattle0.BA-Cri-Cri` |
| 0x00 | `0x0040b64c` | `deTask-StartScenarioModeByContinueData0.LoginTask-CheckContinueStoryMode0.LoginTask-Reset` |
| 0x00 | `0x0040b66e` | `Data0.LoginTask-CheckContinueStoryMode0.LoginTask-ResetContinueStorySaveData0.UITitle-Hid` |
| 0x00 | `0x0040b6dd` | `onPopup0.XIGNCODE3Interface-GetCookie20.LoginTask-ErrorAccountCheckYostar0.LoginTask-Requ` |
| 0x00 | `0x0040b700` | `ie20.LoginTask-ErrorAccountCheckYostar0.LoginTask-RequestAccountCheckYostar0.UIAssetDataC` |
| 0x00 | `0x0040b81f` | `Title-ShowServerWaitingConnectionPopup0.LoginTask-HandleQueuingGetTicketResponseMessage0.` |

**`Account_Auth`** — 2 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0022d988` | `tistics.Account_Create.Account_Nickname.Account_Auth.Account_CurrencySync.Account_SetReprese` |
| 0x00 | `0x0022da5a` | `ostar.Account_CallName.Account_BirthDay.Account_Auth2.Account_LinkReward.Account_ReportXignC` |

**`Account_CheckYostar`** — 1 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0022da24` | `count_PassCheck.Account_VerifyForYostar.Account_CheckYostar.Account_CallName.Account_BirthDay.Accou` |

**`Queuing_GetAuthTicket`** — 0 命中

**`ResultState`** — 4 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0022cbad` | `eratedIV.AccountCheckYostarResponse.get_ResultState.set_ResultState.get_ResultMessag.set_Re` |
| 0x00 | `0x0022cbbd` | `CheckYostarResponse.get_ResultState.set_ResultState.get_ResultMessag.set_ResultMessag.<Resu` |
| 0x00 | `0x0022cbec` | `tate.get_ResultMessag.set_ResultMessag.<ResultState>k__BackingField.<ResultMessag>k__Backin` |
| 0x00 | `0x0022cc26` | `kingField.<ResultMessag>k__BackingField.ResultState.ResultMessag.AccountResetRequest.Accoun` |

**`ErrorCode`** — 41 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0011a18e` | `rmitSync.RefreshClanLobby.errorCode.ShowErrorCodePopupCheck.ClanChattingChannelJoin.<MyCl` |
| 0x00 | `0x0011a464` | `nc>b__2.<SyncUiClanMemberList>b__0.<ShowErrorCodePopupCheck>b__68_0.<ShowErrorCodePopupCh` |
| 0x00 | `0x0011a485` | `0.<ShowErrorCodePopupCheck>b__68_0.<ShowErrorCodePopupCheck>b__68_1.<>9__68_1.ClanMemberO` |
| 0x00 | `0x001285a9` | `.get_IsTicketAvailable.get_LastEndBattleErrorCode.set_LastEndBattleErrorCode.get_LastEndB` |
| 0x00 | `0x001285c4` | `LastEndBattleErrorCode.set_LastEndBattleErrorCode.get_LastEndBattleResponse.set_LastEndBa` |
| 0x00 | `0x001288c3` | `<SyncTime>k__BackingField.<LastEndBattleErrorCode>k__BackingField.<LastEndBattleResponse>` |
| 0x00 | `0x0012899c` | `omOpened.IsTicketAvailable.LastEndBattleErrorCode.LastEndBattleResponse.AnyPlayableRoom.A` |
| 0x00 | `0x0012b0cb` | `untReportXignCodeCheaterNetworkTask.get_ErrorCode.set_ErrorCode.<ErrorCode>k__BackingFiel` |
| 0x00 | `0x0012b0d9` | `odeCheaterNetworkTask.get_ErrorCode.set_ErrorCode.<ErrorCode>k__BackingField.ErrorCode.Ac` |
| 0x00 | `0x0012b0e4` | `etworkTask.get_ErrorCode.set_ErrorCode.<ErrorCode>k__BackingField.ErrorCode.AccountReques` |
| 0x00 | `0x0012b0fe` | `et_ErrorCode.<ErrorCode>k__BackingField.ErrorCode.AccountRequestBirthdayMailNetworkTask.g` |
| 0x00 | `0x0016b111` | `.inviteAnimation.characterThumb.receivedErrorCode.<StudentInvited>k__BackingField.<isTick` |
| 0x00 | `0x0023ef7d` | `ingField.IsFileReady.TTSFileS3Uri.WebAPIErrorCode.InvalidPacket.InvalidProtocol.InvalidSe` |
| 0x00 | `0x0062ca70` | `Microsoft.Win32.hr.GetMessage.MakeHRFromErrorCode.SafeHandleCache`1.Microsoft.Win32.SafeH` |

**`Protocol`** — 300 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0012af9d` | `countLoginSyncNoPartNetworkTask.get_SyncProtocols.SyncProtocols.AccountLoginSyncNetworkT` |
| 0x00 | `0x0012afab` | `NoPartNetworkTask.get_SyncProtocols.SyncProtocols.AccountLoginSyncNetworkTask.<ProcessSe` |
| 0x00 | `0x001cdb36` | `er.OnClickPersonalPrivacy.OnClickPrivacyProtocol.OnClickUserAndPrivacy.OnOpen.<OnClickNo` |
| 0x00 | `0x001cdc65` | `nterButton.personalPrivacyButton.privacyProtocolButton.userAndPrivacyButton.<OnClickCach` |
| 0x00 | `0x001d7558` | `taNetworkTask.ManagementDataRequest.get_Protocol.ManagementDataResponse.ShopBuyTutorialG` |
| 0x00 | `0x001fd24a` | `pRootMotionFlatBuffer.RootMotionsLength.ProtocolSettingExcelTable.GetRootAsProtocolSetti` |
| 0x00 | `0x001fd26d` | `ngth.ProtocolSettingExcelTable.GetRootAsProtocolSettingExcelTable.CreateProtocolSettingE` |
| 0x00 | `0x001fd28d` | `etRootAsProtocolSettingExcelTable.CreateProtocolSettingExcelTable.StartProtocolSettingEx` |
| 0x00 | `0x001fd2ac` | `le.CreateProtocolSettingExcelTable.StartProtocolSettingExcelTable.EndProtocolSettingExce` |
| 0x00 | `0x001fd2c9` | `Table.StartProtocolSettingExcelTable.EndProtocolSettingExcelTable.FinishProtocolSettingE` |
| 0x00 | `0x001fd2e9` | `able.EndProtocolSettingExcelTable.FinishProtocolSettingExcelTableBuffer.FinishSizePrefix` |
| 0x00 | `0x001fd31b` | `ttingExcelTableBuffer.FinishSizePrefixedProtocolSettingExcelTableBuffer.ProtocolSettingE` |
| 0x00 | `0x001fd33b` | `PrefixedProtocolSettingExcelTableBuffer.ProtocolSettingExcel.GetRootAsProtocolSettingExc` |
| 0x00 | `0x001fd359` | `bleBuffer.ProtocolSettingExcel.GetRootAsProtocolSettingExcel.get_protocol.GetProtocolByt` |

**`ServerInfoConnectionGroupData`** — 17 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x00129d13` | `tData>b__0.<RequestManagementData>d__19.ServerInfoConnectionGroupData.get_AddressablesCatalogUrlRoot.set_Addr` |
| 0x00 | `0x003d8df9` | `twork-GameSessionManager-CreateSession0.ServerInfoConnectionGroupData-get_ApiUrl0.Assets-_MX-Program-Scripts-` |
| 0x66 | `0x003e2022` | `..."...4.........K3.....+........."...Vf5...../...%.........!...."...K...9+....+....... ...(...Vf5...../...%.` |
| 0x66 | `0x003e205b` | `...!...."...K...9+....+....... ...(...Vf5...../...%.........!...."...K...9+....+........... ...(...Vf5...../.` |
| 0x66 | `0x003e2098` | `...."...K...9+....+........... ...(...Vf5...../...%.........!...."...K...92....+....... ...(...Vf5...../...%.` |
| 0x66 | `0x003e20d1` | `...!...."...K...92....+....... ...(...Vf5...../...%.........!...."...K...92....+........... ...(...Vf3.... ..` |
| 0x66 | `0x003e2150` | `. .........K*...Wf3.... .........K5...Vf5...../...%.........!...."...K!..4......6.......Vf5...../...%........` |
| 0x66 | `0x003e2182` | `%.........!...."...K!..4......6.......Vf5...../...%.........!...."...K/...4..6....Vf5...../...%.........!....` |
| 0x66 | `0x003e21ae` | `../...%.........!...."...K/...4..6....Vf5...../...%.........!...."...K/...Vf5...../...%.........!...."...K4..` |
| 0x66 | `0x003e21d2` | `..Vf5...../...%.........!...."...K/...Vf5...../...%.........!...."...K4....'..3..Vf5...../...%.........!...."` |
| 0x66 | `0x003e21fd` | `.../...%.........!...."...K4....'..3..Vf5...../...%.........!...."...K!..'....$......3..4...Vf5...../...%....` |
| 0x66 | `0x003e2233` | `......!...."...K!..'....$......3..4...Vf5...../...%.........!...."...K!..2....3..4...Vf5...../...%.........!.` |
| 0x66 | `0x003e2262` | `...%.........!...."...K!..2....3..4...Vf5...../...%.........!...."...K!..+....+.......3..4...Vf5...../...%...` |
| 0x66 | `0x003e2299` | `.....!...."...K!..+....+.......3..4...Vf5...../...%.........!...."...K!..+....+...........3..4...Vf5...../...` |

**`CallbackUrl`** — 9 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x00129dd6` | `.get_ApiUrls.set_ApiUrls.get_ApiUrl.get_CallbackUrl.set_CallbackUrl.get_Msg.set_Msg.get_Res` |
| 0x00 | `0x00129de6` | `_ApiUrls.get_ApiUrl.get_CallbackUrl.set_CallbackUrl.get_Msg.set_Msg.get_ResourceVersion.set` |
| 0x00 | `0x0012a2fc` | `_BackingField.<ApiUrls>k__BackingField.<CallbackUrl>k__BackingField.<Msg>k__BackingField.<R` |
| 0x00 | `0x001d7172` | `ResultCode>b__3.<CheckResultCode>b__6_2.CallbackUrlData.get_order_notify.set_order_notify.g` |
| 0x00 | `0x00230e31` | `set_PurchaseServerTag.get_PurchaseServerCallbackUrl.set_PurchaseServerCallbackUrl.<Purchase` |
| 0x00 | `0x00230e4f` | `haseServerCallbackUrl.set_PurchaseServerCallbackUrl.<PurchaseResetDate>k__BackingField.<MXS` |
| 0x00 | `0x00230ecb` | `erverTag>k__BackingField.<PurchaseServerCallbackUrl>k__BackingField.PurchaseResetDate.MXSee` |
| 0x00 | `0x00230f11` | `rchaseResetDate.MXSeedKey.PurchaseServerCallbackUrl.BillingTransactionEndByYostarRequest.ge` |
| 0x66 | `0x00114c2a` | `.."...f'......5...../"f5..3/"f%....../"f%.......3..fZ!..+.....*....*...$.%......../.X.99PS9` |

**`AddressablesCatalogUrlRoots`** — 4 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x00129d73` | `Root.set_AddressablesCatalogUrlRoot.get_AddressablesCatalogUrlRoots.set_AddressablesCatalogUrlRoots.get_Api` |
| 0x00 | `0x00129d93` | `oot.get_AddressablesCatalogUrlRoots.set_AddressablesCatalogUrlRoots.get_ApiUrls.set_ApiUrls.get_ApiUrl.get_` |
| 0x00 | `0x0012a2b6` | `essablesCatalogUrlRoot>k__BackingField.<AddressablesCatalogUrlRoots>k__BackingField.<ApiUrls>k__BackingFiel` |
| 0x00 | `0x0012a5f4` | `ata.apiIndex.AddressablesCatalogUrlRoot.AddressablesCatalogUrlRoots.ApiUrls.ApiUrl.Msg.ResourceVersion.Tabl` |

### ★协议 token 字面量(parent 指定, 优先)

**`AHTQLQI65FWJGGGK4KL5AEF57A`** — 0 命中

**`PFJRUKK5IXXQR2XFFCMNXEIKXM`** — 0 命中

**`VLWZJ6JP2FMSAXBR2BDAXLLBNQ`** — 0 命中

**`ahtqlqi65fwjgggk4kl5aef57a`** — 0 命中

**`AHTQLQI65FWJGGGK4KL5AEF57a`** — 0 命中

**`ToBase32String`** — 3 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x001552e9` | `oInt.encoded.FromBase32String.padOutput.ToBase32String._digits._mask._shift.NCalcLexer.get_Gra` |
| 0x00 | `0x0040c216` | `Data-LastConnectSaveData-Update0.Base32-ToBase32String0.Base32-ToBase32String1.TTSService-TTSF` |
| 0x00 | `0x0040c22d` | `a-Update0.Base32-ToBase32String0.Base32-ToBase32String1.TTSService-TTSFileName0.TTSService-get` |

**`Base32`** — 10 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x001552b5` | `alTimeMS>b__9_1.<FinishAccumulator>b__0.Base32.CharToInt.encoded.FromBase32String.padO` |
| 0x00 | `0x001552d2` | `lator>b__0.Base32.CharToInt.encoded.FromBase32String.padOutput.ToBase32String._digits.` |
| 0x00 | `0x001552eb` | `nt.encoded.FromBase32String.padOutput.ToBase32String._digits._mask._shift.NCalcLexer.g` |
| 0x00 | `0x0040c20f` | `MX-SaveData-LastConnectSaveData-Update0.Base32-ToBase32String0.Base32-ToBase32String1.` |
| 0x00 | `0x0040c218` | `ta-LastConnectSaveData-Update0.Base32-ToBase32String0.Base32-ToBase32String1.TTSServic` |
| 0x00 | `0x0040c226` | `SaveData-Update0.Base32-ToBase32String0.Base32-ToBase32String1.TTSService-TTSFileName0` |
| 0x00 | `0x0040c22f` | `Update0.Base32-ToBase32String0.Base32-ToBase32String1.TTSService-TTSFileName0.TTSServi` |
| 0x00 | `0x0041ceee` | `mulator0.MXStopwatch-FinishAccumulator0.Base32-CharToInt0.Base32-FromBase32String0.NCa` |
| 0x00 | `0x0041cf00` | `ch-FinishAccumulator0.Base32-CharToInt0.Base32-FromBase32String0.NCalcLexer-get_Gramma` |
| 0x00 | `0x0041cf0b` | `cumulator0.Base32-CharToInt0.Base32-FromBase32String0.NCalcLexer-get_GrammarFileName0.` |

**`BASE32`** — 0 命中

**`base32`** — 0 命中

### bypass / 状态机

**`IsGatewayBypassed`** — 4 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x00219efe` | `ficateHandler.get_SessionQueueCount.get_IsGatewayBypassed.set_IsGatewayBypassed.ClearAllSession.C` |
| 0x00 | `0x00219f14` | `ionQueueCount.get_IsGatewayBypassed.set_IsGatewayBypassed.ClearAllSession.ClearAllSessionWithoutC` |
| 0x00 | `0x0021a1e8` | `ld.<CertificateHandler>k__BackingField.<IsGatewayBypassed>k__BackingField.ShowUIRepeater.ShowUIRe` |
| 0x00 | `0x0021a27a` | `ed.CertificateHandler.SessionQueueCount.IsGatewayBypassed.<RemoveSession>b__0.<PopupAndResend>b__` |

**`GatewayBypass`** — 5 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x00219f00` | `cateHandler.get_SessionQueueCount.get_IsGatewayBypassed.set_IsGatewayBypassed.ClearAllSession` |
| 0x00 | `0x00219f16` | `nQueueCount.get_IsGatewayBypassed.set_IsGatewayBypassed.ClearAllSession.ClearAllSessionWithou` |
| 0x00 | `0x0021a1ea` | `.<CertificateHandler>k__BackingField.<IsGatewayBypassed>k__BackingField.ShowUIRepeater.ShowUI` |
| 0x00 | `0x0021a27c` | `.CertificateHandler.SessionQueueCount.IsGatewayBypassed.<RemoveSession>b__0.<PopupAndResend>b` |
| 0x00 | `0x0021a67e` | `d.set_Elapsed.get_TimeOut.set_TimeOut.isGatewayBypassed.SetSessionParameters.HandleServerErro` |

**`bypass`** — 10 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0075a972` | `putChannels.outputChannels.SetBusMatrix.bypass.SetEffectBypass.SetEffectParameter.GetE` |
| 0x00 | `0x007a6ecd` | `get_reverbZoneMix.set_reverbZoneMix.get_bypassEffects.set_bypassEffects.get_bypassList` |
| 0x00 | `0x007a6edf` | `set_reverbZoneMix.get_bypassEffects.set_bypassEffects.get_bypassListenerEffects.set_by` |
| 0x00 | `0x007a6ef1` | `get_bypassEffects.set_bypassEffects.get_bypassListenerEffects.set_bypassListenerEffect` |
| 0x00 | `0x007a6f0b` | `ssEffects.get_bypassListenerEffects.set_bypassListenerEffects.get_bypassReverbZones.se` |
| 0x00 | `0x007a6f25` | `erEffects.set_bypassListenerEffects.get_bypassReverbZones.set_bypassReverbZones.get_do` |
| 0x00 | `0x007a6f3b` | `stenerEffects.get_bypassReverbZones.set_bypassReverbZones.get_dopplerLevel.set_doppler` |
| 0x00 | `0x007a7111` | `ize.spatializePostEffects.reverbZoneMix.bypassEffects.bypassListenerEffects.bypassReve` |
| 0x00 | `0x007a711f` | `PostEffects.reverbZoneMix.bypassEffects.bypassListenerEffects.bypassReverbZones.rollof` |
| 0x00 | `0x007a7135` | `Mix.bypassEffects.bypassListenerEffects.bypassReverbZones.rolloffMode.minVolume.rollof` |

**`Bypass`** — 32 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x00219f07` | `dler.get_SessionQueueCount.get_IsGatewayBypassed.set_IsGatewayBypassed.ClearAllSession` |
| 0x00 | `0x00219f1d` | `ount.get_IsGatewayBypassed.set_IsGatewayBypassed.ClearAllSession.ClearAllSessionWithou` |
| 0x00 | `0x0021a1f1` | `ficateHandler>k__BackingField.<IsGatewayBypassed>k__BackingField.ShowUIRepeater.ShowUI` |
| 0x00 | `0x0021a283` | `icateHandler.SessionQueueCount.IsGatewayBypassed.<RemoveSession>b__0.<PopupAndResend>b` |
| 0x00 | `0x0021a685` | `lapsed.get_TimeOut.set_TimeOut.isGatewayBypassed.SetSessionParameters.HandleServerErro` |
| 0x00 | `0x0031fc55` | `AudioMixerGroup.AudioClips.CustomCurves.BypassEffects.BypassListenerEffects.BypassReve` |
| 0x00 | `0x0031fc63` | `p.AudioClips.CustomCurves.BypassEffects.BypassListenerEffects.BypassReverbZones.Stereo` |
| 0x00 | `0x0031fc79` | `ves.BypassEffects.BypassListenerEffects.BypassReverbZones.StereoPan.SpatialBlend.Rever` |
| 0x00 | `0x006ab1b1` | `asyncHint.m_closed.IWebProxy.GetProxy.IsBypassed.WebProxy.BypassOnLocal.BypassList.set` |
| 0x00 | `0x006ab1c3` | `.IWebProxy.GetProxy.IsBypassed.WebProxy.BypassOnLocal.BypassList.set_UseDefaultCredent` |
| 0x00 | `0x006ab1d1` | `Proxy.IsBypassed.WebProxy.BypassOnLocal.BypassList.set_UseDefaultCredentials.UpdateReg` |
| 0x00 | `0x006ab20f` | `ultCredentials.UpdateRegExList.IsMatchInBypassList.IsLocalInProxyHash.IsBypassedManual` |
| 0x00 | `0x006ab22f` | `sMatchInBypassList.IsLocalInProxyHash.IsBypassedManual.get_ScriptEngine.CreateDefaultP` |
| 0x00 | `0x006ab2a3` | `ateFromRegistry.proxyUri.GetProxyAuto.isBypassed.IsBypassedAuto.proxies.checkFirstOnly` |

**`SkipLogin`** — 0 命中

**`SkipAccountCallname`** — 4 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0013fb54` | `Initialized.StartLogin.ErrorAccountAuth.SkipAccountCallname.onCreateStateEnd.HandleAccountCallnameR` |
| 0x00 | `0x0013fcf5` | `40_1.<OnLoginFinish>g__CloseTitle\|52_6.<SkipAccountCallname>b__56_0.<SkipAccountCallname>g__TTSSave` |
| 0x00 | `0x0013fd12` | `itle\|52_6.<SkipAccountCallname>b__56_0.<SkipAccountCallname>g__TTSSaveAndRequestAccountAuth\|56_1.<C` |
| 0x00 | `0x0040c6a5` | `0.LoginTask-onCreateStateEnd0.LoginTask-SkipAccountCallname0.LogoutTask-Release0.MissionSyncTimer-D` |

**`DevLogin`** — 8 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x001cdd01` | `_14_0.<OnClickInitGamesetting>b__15_0.UIDevLogin.OnClickDevLoginButton.UIFirstLogin.OnCl` |
| 0x00 | `0x001cdd11` | `itGamesetting>b__15_0.UIDevLogin.OnClickDevLoginButton.UIFirstLogin.OnClickTrigger.SetSc` |
| 0x00 | `0x0048b107` | `u-OnOpen0.UIAssetDataClearMenu-Awake0.UIDevLogin-Awake0.UIDevLogin-OnEnable0.UIDevLogin-` |
| 0x00 | `0x0048b119` | `ataClearMenu-Awake0.UIDevLogin-Awake0.UIDevLogin-OnEnable0.UIDevLogin-OnClickDevLoginBut` |
| 0x00 | `0x0048b12e` | `IDevLogin-Awake0.UIDevLogin-OnEnable0.UIDevLogin-OnClickDevLoginButton0.UIDevLogin-OnAnd` |
| 0x00 | `0x0048b13e` | `.UIDevLogin-OnEnable0.UIDevLogin-OnClickDevLoginButton0.UIDevLogin-OnAndroidBackButton0.` |
| 0x00 | `0x0048b150` | `le0.UIDevLogin-OnClickDevLoginButton0.UIDevLogin-OnAndroidBackButton0.UIFirstLogin-SetSc` |
| 0x00 | `0x02218c80` | `ClearMenu.........SU......*MX/UITitle/UIDevLogin.SU.......MX/UITitle/UIFirstLogin.SU....` |

**`DebugLogin`** — 0 命中

**`GuestLogin`** — 0 命中

**`OfflineMode`** — 0 命中

**`CheatMode`** — 0 命中

### 错误识别

**`IsSpecificErrorJson`** — 2 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0021a50f` | `tOrReturnOriginal.HandleDecryptionError.IsSpecificErrorJson.hostURL.<message>k__BackingField.Reques` |
| 0x00 | `0x00497673` | `Program-Scripts-Network-HttpGameMessage-IsSpecificErrorJson0.Assets-_MX-Program-Scripts-Network-Htt` |

**`Reason`** — 66 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0015e4e0` | `0.<OnClickButton>b__28_1.isLocked.lockedReason.widgetsParent.zoneLabel.scheduleLabel.t` |
| 0x00 | `0x00187fca` | `ckCoverWidget.clearWidget.dotWidget.lockReasonLabel.<myItem>k__BackingField.myItem.Gui` |
| 0x00 | `0x00190e94` | `anOpenConditionButtonController.get_LockReason.set_LockReason.get_IsButtonUnlocked.set` |
| 0x00 | `0x00190ea3` | `ButtonController.get_LockReason.set_LockReason.get_IsButtonUnlocked.set_IsButtonUnlock` |
| 0x00 | `0x00190f2e` | `15_0.LockAnimation.unlockCoroutine.<LockReason>k__BackingField.<IsButtonUnlocked>k__Ba` |
| 0x00 | `0x00190f84` | `ckingField.OpenConditionContentType.LockReason.IsButtonUnlocked.<CoPlayUnlockAnimation` |
| 0x00 | `0x00208418` | `al.System_Craft.Reward_Pack.ParcelChangeReason.Acquire_NewAccount.Acquire_PlayReward.A` |
| 0x00 | `0x0023045d` | `ProgressDBDict.StaticOpenConditions.set_Reason.<Reason>k__BackingField.InventoryFullEr` |
| 0x00 | `0x00230465` | `DBDict.StaticOpenConditions.set_Reason.<Reason>k__BackingField.InventoryFullErrorPacke` |
| 0x00 | `0x002304c9` | `rrorPacket.AccountBanErrorPacket.get_BanReason.set_BanReason.<BanReason>k__BackingFiel` |
| 0x00 | `0x002304d7` | `ountBanErrorPacket.get_BanReason.set_BanReason.<BanReason>k__BackingField.BanReason.Ac` |
| 0x00 | `0x002304e2` | `rPacket.get_BanReason.set_BanReason.<BanReason>k__BackingField.BanReason.AccountConten` |
| 0x00 | `0x002304fc` | `BanReason.<BanReason>k__BackingField.BanReason.AccountContentBanErrorPacket.get_BanSta` |
| 0x00 | `0x0024968b` | `NewbieAttendanceReward.OpenConditionLockReason.CafeRank.ScenarioModeClear.CafeOpen.Ope` |

**`HandleDecryptionError`** — 2 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0021a4f9` | `.DecodeResponse.DecryptOrReturnOriginal.HandleDecryptionError.IsSpecificErrorJson.hostURL.<message>k_` |
| 0x00 | `0x004976bb` | `Program-Scripts-Network-HttpGameMessage-HandleDecryptionError0.Assets-_MX-Program-Scripts-Network-Htt` |

**`ShowDefaultNetworkError`** — 3 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x00219d3a` | `dString.ParseProtocol.ParsePacketString.ShowDefaultNetworkError.addressFamily.ParseReceivedString.<Show` |
| 0x00 | `0x00219d75` | `rror.addressFamily.ParseReceivedString.<ShowDefaultNetworkError>b__0.buttonText.<GetIpAddress>b__0.WAIT` |
| 0x00 | `0x00496786` | `-Program-Scripts-Network-NetworkService-ShowDefaultNetworkError0.Assets-_MX-Program-Scripts-Network-Net` |

**`NetworkErrorHandler`** — 4 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0021a5fa` | `ResponseHandler.set_ResponseHandler.get_NetworkErrorHandler.set_NetworkErrorHandler.get_RequestHand` |
| 0x00 | `0x0021a612` | `onseHandler.get_NetworkErrorHandler.set_NetworkErrorHandler.get_RequestHandler.set_RequestHandler.g` |
| 0x00 | `0x0021a713` | `ssage.<ResponseHandler>k__BackingField.<NetworkErrorHandler>k__BackingField.<RequestHandler>k__Back` |
| 0x00 | `0x0021a799` | `TimeOut>k__BackingField.ResponseHandler.NetworkErrorHandler.RequestHandler.Elapsed.TimeOut.<HandleS` |

**`SessionStateChangedMessage`** — 6 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0021a02f` | `ayer.SendRequestApi.CreateSession.HandleSessionStateChangedMessage.DisableNetworkInputLayer.session.Handle` |
| 0x00 | `0x0021a55c` | `k__BackingField.RequestState.RetryCount.SessionStateChangedMessage.get_Session.get_IsFinished.<Session>k__` |
| 0x00 | `0x0040c101` | `ate0.Assets-_MX-Program-Scripts-Network-SessionStateChangedMessage-get_SessionState0.LoginTask-HandleSessi` |
| 0x00 | `0x0048b22b` | `ble0.Assets-_MX-Program-Scripts-Network-SessionStateChangedMessage-get_SessionId0.Assets-_MX-Program-Scrip` |
| 0x00 | `0x0048b742` | `cripts-Network-GameSessionManager-HandleSessionStateChangedMessage0.Assets-_MX-Program-Scripts-Network-Gam` |
| 0x00 | `0x00495e24` | `ame0.Assets-_MX-Program-Scripts-Network-SessionStateChangedMessage-get_IsFinished0.Assets-_MX-Program-Scri` |

**`ResponseHandler`** — 6 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x00180f07` | `_37_0.<LoadBG>b__37_1.<UIRaidRoomEnd>g__ResponseHandler\|46_0.mapView.listView.FX_Root.insertRen` |
| 0x00 | `0x001b802f` | `k.set_NewRankingCheck.<UIRaidRoomEnd>g__ResponseHandler\|33_0.<OnOpened>b__35_0.SettlementObject` |
| 0x00 | `0x0021a5d2` | `.Session.IsFinished.HttpGameSession.get_ResponseHandler.set_ResponseHandler.get_NetworkErrorHan` |
| 0x00 | `0x0021a5e6` | `HttpGameSession.get_ResponseHandler.set_ResponseHandler.get_NetworkErrorHandler.set_NetworkErro` |
| 0x00 | `0x0021a6f2` | `eOut.Resend.WaitForRequest.httpMessage.<ResponseHandler>k__BackingField.<NetworkErrorHandler>k_` |
| 0x00 | `0x0021a789` | `__BackingField.<TimeOut>k__BackingField.ResponseHandler.NetworkErrorHandler.RequestHandler.Elap` |

### 中文文案(UTF-8)

**`认证失败`** — 0 命中

**`认证失败@utf16le`** — 0 命中

**`服务器处理请求失败`** — 0 命中

**`服务器处理请求失败@utf16le`** — 0 命中

**`通知`** — 1 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x55 | `0x000ebdaf` | `..........................................................R/"S..\!?...]77]%'C;9C:9I.#L` |

**`通知@utf16le`** — 0 命中

**`网络连接失败`** — 1 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0xfe | `0x000ebd04` | `.@..@.8B(6@38N3>O..H.+O..B.:O.2N *B7.D'%.Co.Eb.A`.p[.ZO.J[.Br.QI._P.PZ.Co.Eb.A`.p[.}{.xK.~\|%ML(uE/` |

**`网络连接失败@utf16le`** — 0 命中

**`认证服务器拒绝了请求`** — 0 命中

**`认证服务器拒绝了请求@utf16le`** — 0 命中

**`请确认网络连接状态后重试`** — 1 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0xc7 | `0x000ebd3d` | `[.Br.QI._P.PZ.Co.Eb.A`.p[.}{.xK.~\|%ML(uE/hp fi/ic zV \|[/xY!Ib Mq!GF"WI.@J/hR$GE.....................................` |

**`请确认网络连接状态后重试@utf16le`** — 0 命中

### 自检/已知常量

**`2021.3.56f2`** — 0 命中

**`m_UnityVersion`** — 0 命中

**`Il2CppMetadata`** — 0 命中

**`PROTOCOL_HEAD_RESERVE`** — 1 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0025e39d` | `ryptManager.requestBytes.EncryptRequest.PROTOCOL_HEAD_RESERVE._cryptor._checker.StringCipher.EncryptS` |

**`FBENCRYPT_BLOCK_SIZE`** — 1 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x00259c18` | `256Api.sEncryptedString.DecryptRJ256Api.FBENCRYPT_BLOCK_SIZE.cRandom.IVString.CryptAESOrigin.plainTe` |

**`JOSYdf8ys97uhFYS`** — 2 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x66 | `0x012d172c` | ``nfdbgfffffffffdbffffffffffdb`nfdb`nlg&F,)5?..^.._Q.. ?5>....!.../...RS-.(3P6>.+7...,/WM.SV2M.".` |
| 0xe9 | `0x0007aa13` | `..............................................................................................y`` |

**`BEGIN PUBLIC KEY`** — 1 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0x00 | `0x0178cc65` | `...................................-----BEGIN PUBLIC KEY-----.MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMI` |

**`yostar.net`** — 3 命中
| key | 文件偏移 | 前后 40B (ASCII) |
|---|---|---|
| 0xb5 | `0x000c173a` | `..........................................................................................` |
| 0xb5 | `0x000c1765` | `..........................................................................................` |
| 0xb5 | `0x000c1790` | `...................................................................l.j.J.L...J.Ll~.x{.}x.~` |

## 3. 1MB 块最佳 key / 可打印率 (区段边界探测)

| 块 | 起始 | 最佳key | 可打印率 | k=0x00 | k=0x66 | k=0xB5 | top3 |
|---|---|---|---|---|---|---|---|
| 00 | 0x00000000 | 0x33 | 0.450 | 0.434 | 0.412 | 0.339 | 0x33,0x37,0x30 |
| 01 | 0x00100000 | 0x34 | 0.939 | 0.810 | 0.525 | 0.000 | 0x34,0x3f,0x33 |
| 02 | 0x00200000 | 0x3f | 0.942 | 0.807 | 0.513 | 0.000 | 0x3f,0x34,0x2e |
| 03 | 0x00300000 | 0x39 | 0.885 | 0.835 | 0.583 | 0.000 | 0x39,0x3f,0x3d |
| 04 | 0x00400000 | 0x24 | 0.933 | 0.836 | 0.548 | 0.000 | 0x24,0x20,0x27 |
| 05 | 0x00500000 | 0x24 | 0.936 | 0.835 | 0.541 | 0.000 | 0x24,0x20,0x27 |
| 06 | 0x00600000 | 0x3f | 0.936 | 0.798 | 0.518 | 0.000 | 0x3f,0x38,0x34 |
| 07 | 0x00700000 | 0x3f | 0.893 | 0.629 | 0.546 | 0.055 | 0x3f,0x38,0x34 |
| 08 | 0x00800000 | 0x29 | 0.737 | 0.262 | 0.573 | 0.221 | 0x29,0x36,0x3a |
| 09 | 0x00900000 | 0x55 | 0.656 | 0.243 | 0.511 | 0.304 | 0x55,0x56,0x30 |
| 10 | 0x00a00000 | 0x55 | 0.640 | 0.226 | 0.489 | 0.319 | 0x55,0x56,0x51 |
| 11 | 0x00b00000 | 0x55 | 0.641 | 0.251 | 0.505 | 0.307 | 0x55,0x56,0x40 |
| 12 | 0x00c00000 | 0x36 | 0.628 | 0.245 | 0.496 | 0.316 | 0x36,0x33,0x31 |
| 13 | 0x00d00000 | 0x2f | 0.652 | 0.268 | 0.528 | 0.278 | 0x2f,0x42,0x2c |
| 14 | 0x00e00000 | 0x33 | 0.663 | 0.276 | 0.538 | 0.277 | 0x33,0x37,0x34 |
| 15 | 0x00f00000 | 0x33 | 0.665 | 0.255 | 0.511 | 0.291 | 0x33,0x34,0x37 |
| 16 | 0x01000000 | 0x33 | 0.680 | 0.265 | 0.506 | 0.278 | 0x33,0x55,0x56 |
| 17 | 0x01100000 | 0x55 | 0.660 | 0.260 | 0.513 | 0.282 | 0x55,0x37,0x33 |
| 18 | 0x01200000 | 0x37 | 0.701 | 0.386 | 0.604 | 0.180 | 0x37,0x34,0x6b |
| 19 | 0x01300000 | 0x3f | 0.697 | 0.327 | 0.572 | 0.186 | 0x3f,0x3b,0x3d |
| 20 | 0x01400000 | 0x33 | 0.709 | 0.346 | 0.581 | 0.178 | 0x33,0x3c,0x37 |
| 21 | 0x01500000 | 0x2e | 0.694 | 0.305 | 0.566 | 0.195 | 0x2e,0x29,0x2a |
| 22 | 0x01600000 | 0x0a | 0.695 | 0.319 | 0.567 | 0.186 | 0x0a,0x09,0x0d |
| 23 | 0x01700000 | 0x4b | 0.612 | 0.289 | 0.513 | 0.271 | 0x4b,0x4c,0x4f |
| 24 | 0x01800000 | 0x33 | 0.721 | 0.313 | 0.581 | 0.178 | 0x33,0x34,0x37 |
| 25 | 0x01900000 | 0x33 | 0.709 | 0.325 | 0.572 | 0.182 | 0x33,0x34,0x59 |
| 26 | 0x01a00000 | 0x33 | 0.752 | 0.343 | 0.614 | 0.152 | 0x33,0x37,0x34 |
| 27 | 0x01b00000 | 0x54 | 0.699 | 0.313 | 0.575 | 0.193 | 0x54,0x49,0x53 |
| 28 | 0x01c00000 | 0x6f | 0.649 | 0.328 | 0.557 | 0.233 | 0x6f,0x6b,0x3f |
| 29 | 0x01d00000 | 0x36 | 0.756 | 0.367 | 0.513 | 0.166 | 0x36,0x32,0x31 |
| 30 | 0x01e00000 | 0x31 | 0.766 | 0.408 | 0.466 | 0.176 | 0x31,0x36,0x32 |
| 31 | 0x01f00000 | 0x4e | 0.625 | 0.222 | 0.492 | 0.325 | 0x4e,0x4a,0x4f |
| 32 | 0x02000000 | 0x58 | 0.597 | 0.225 | 0.476 | 0.346 | 0x58,0x5f,0x5b |
| 33 | 0x02100000 | 0x55 | 0.595 | 0.220 | 0.473 | 0.349 | 0x55,0x33,0x37 |
| 34 | 0x02200000 | 0x31 | 0.813 | 0.357 | 0.596 | 0.136 | 0x31,0x32,0x26 |
| 35 | 0x02300000 | 0x29 | 0.797 | 0.484 | 0.561 | 0.110 | 0x29,0x2d,0x24 |
| 36 | 0x02400000 | 0x37 | 0.774 | 0.346 | 0.607 | 0.139 | 0x37,0x34,0x33 |

> **重要警告**: "可打印率最高的 key" 有严重退化 —— 对纯字母文本, `^0x20`(大小写翻转) 和 `^0x34`(a-z<->U-N 映射) 也能得到 90%+ 可打印率。所以该列**不能**单独用来判定真实 key, 只能看块间**相对跳变**(= 区段边界)。真实 key 以 §1 的关键词命中为准。

## 4. 结论

1. header: 0x00-0x07 未解(被单独改写), 0x08-0xFF 是 `^0x66`。
2. 段表: 31 段见 §0, 全部落在文件内且首尾相接。
3. 字符串区 key: 见 §1/§3; 字面量区(sec01) 至少局部是 `^0xB5`, 标识符区(sec02) 是明文 `^0x00`。

## 5. § token 字面量命中情况 (最重要)

| token (26 char BASE32) | 256 key 全扫命中 | 结论 |
|---|---|---|
| `AHTQLQI65FWJGGGK4KL5AEF57A` | 0 | **不在文件里** |
| `PFJRUKK5IXXQR2XFFCMNXEIKXM` | 0 | **不在文件里** |
| `VLWZJ6JP2FMSAXBR2BDAXLLBNQ` | 0 | **不在文件里** |

补充证据:
- 大小写变体 (`ahtqlqi…`, 末位 `7a`) 同样 0 命中。
- `[A-Z2-7]{26,64}` 正则扫描: 有 4731 条匹配, 但全部是二进制里连续相同字节(如 `2222…`)或 `ABCDEFGHIJKLMNOPQRSTUVWXYZ` 这类常量在某个 key 下的巧合,去掉 <12 种不同字符后, **没有任何一条等于上述三个 token**。
- 结论: 客户端**没有**预计算的协议 token 表; token 是运行时由协议名算出来的(`ToBase32String` 在 0x1552e9 / 0x40c216 有命中, `Base32` 在 0x1552b5 等)。⇒ 改 token 字面量这条路走不通, 只能改协议名/枚举。


## 6. 区段边界与每段 key

| 段 | 区间 | 大小 | 实测 key | 依据 |
|---|---|---|---|---|
| header | 0x00000000-0x000000ff | 0x100 | ^0x66 (前 8B 除外) | 段表 31 段首尾相接且末段=EOF |
| sec00 | 0x00000100-0x000305c0 | 0x304c0 | 未定 (非单字节 XOR) | 24728*8=stringLiteral 表, 内容仍乱码 |
| sec01 | 0x000305c0-0x000ec9c8 | 0xbc408 | **每条字面量各自一个 key** | URL@0xc172b=^0xB5, 中文@0xebd04=^0xFE、@0xebd3d=^0xC7、@0xebdaf=^0x55 |
| sec02 | 0x000ec9c8-0x007b4650 | 0x6c7c88 | ^0x00 (明文) | `BlueArchive\0`, 所有标识符/协议名可读 |
| sec03-sec27 | 0x007b4650-0x024a3664 | — | ^0x00 (二进制表) | uint32 偏移表, 无文本 |
| sec30 | 0x024a3664-0x024a55a8 | 0x1f44 | 未定 | 表区 |

- 因此"全区段单一 key"的假设**不成立**: sec01 内部逐条换 key; sec02 是明文; header 是 ^0x66。
- 1MB 块"可打印率最高 key"那一列会因为 0x20/0x34 这类大小写翻转 key 而退化, 只能用于看块间**跳变**, 不能单独判定 key。
