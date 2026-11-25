| 类型 | 命名空间 | tdIndex | 字段数 | 已提取 | 说明 |
| --- | --- | ---: | ---: | :--: | --- |
| `AcademyGetInfoRequest` | MX.NetworkProtocol | 10682 | 0 | ✓ | 24000 请求，空体（客户端只发 Protocol） |
| `AcademyGetInfoResponse` | MX.NetworkProtocol | 10683 | 2 | ✓ | **24000 响应主体** |
| `AcademyAttendScheduleRequest` | MX.NetworkProtocol | 10684 | 1 | ✓ | 24001 请求 |
| `AcademyAttendScheduleResponse` | MX.NetworkProtocol | 10685 | 3 | ✓ | 24001 响应 |
| `AcademyDB` | MX.GameLogic.DBModel | 11892 | 3 | ✓ | 课程表存档根，被 24000/24001 引用 |
| `AcademyLocationDB` | MX.GameLogic.DBModel | 11893 | 3 | ✓ | 地点（Rank/Exp） |
| `AcademyMessageOutLineDB` | MX.GameLogic.DBModel | 11894 | 4 | ✓ | MomoTalk 式消息会话摘要 |
| `AcademyMessageDB` | MX.GameLogic.DBModel | 11895 | 7 | ✓ | 单条消息 |
| `AcademyScheduleDB` | MX.GameLogic.DBModel | 11896 | 5 | ✓ | 单次日程记录 |
| `AcademyService` | MX.GameLogic.Service | 11645 | 0 | — | 服务实现类，非 DTO（0 字段，不出包） |
| `CharacterAcademyTagResult` | MX.GameLogic.Service | 11843 | 2 | — | 角色标签校验结果（服务层返回值） |