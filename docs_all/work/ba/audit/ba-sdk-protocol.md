# 国服 SDK 登录协议（实测抓包，2026-11-13）

## 一、端点来源（明文，可直接改）

`assets/SDKConfigSettings.json`
```json
{ "sdk_url": "https://sdk-api.yostar.cn", "sdk_pid": "CN-BA", "channel": "official" }
```
**改 `sdk_url` 即可把整个 SDK 登录指向我们自己的服务器**，无需改代码。
⚠️ 注意：改成 HTTP（`http://127.0.0.1:8080`）可行，因为 `res/Dk.xml`（network-security-config）里是
`cleartextTrafficPermitted=true`，全域名允许明文 —— **不需要证书、不需要装 CA、不需要证书绕过**。

## 二、登录链（已验证顺序）

| 顺序 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 1 | POST | `/common/config` | 拉应用配置（7.5 KB），失败 → 游戏提示「初始化资源失败」 |
| 2 | POST | `/user/quick-login` | **登录主接口**，返回用户信息 + `Data.User.Token` |
| 3 | POST | `/user/detail` | 用户详情 |
| 4 | POST | `/common/geo-ip` | 返回 `{"Data":{"Prov":"浙江省"}}` |
| 5 | POST | `/health-game/duration` | 游戏时长 |
| 6 | POST | `/heartbeat/pulse` | 心跳，返回 `{"Data":{"Delay":3600}}` |

统一请求头：
```
Authorization: {"Head":{"PID":"CN-BA","Channel":"official","Platform":"android","Lang":"zh",
  "DeviceID":"<16位hex>","Version":"1.16.1","GVersionNo":"73","GBuildNo":"",
  "DeviceModel":"PLR110","RID":"<uuid>","Time":<unix>},"Sign":"<base64 RSA>"}
gray-tag: ""
User-Agent: okhttp/4.9.2
```

## 三、quick-login 真实响应结构（节选）

```json
{"Code":200,"Msg":"OK","Data":{
  "Identity":{"Type":0,"RealName":"**仙","Underage":false,"State":1},
  "Keys":[{"Type":"mobile","NickName":"177****1532","NickNameEnc":"..."}],
  "Pass":{"ID":22420602,"NickName":"YS1013178778","State":1},
  "User":{"ID":1013178778,"PID":"CN-BA","Token":"e026a35f...","State":1,"RegChannel":"android_official"}
}}
```
`Data.User.Token` 就是后续游戏网关用的凭据。

## 四、卡密设计（据此实现）

不在游戏内做 UI（那要改 dex/il2cpp），而是：

```
我们自己的启动器 App（原生界面，输入卡密）
        ↓ 卡密 + 设备 DeviceID 上报
我们的服务器（卡密库：一卡一设备、可封禁）
        ↓
游戏的 /user/quick-login 到达我们服务器 → 校验该 DeviceID 有没有有效卡密
        ├─ 无 → 返回 Code != 200（游戏停在我们指定的提示）
        └─ 有 → 返回我们伪造的 User/Token（卡密即身份）
```
这样：**游戏内不出现任何“私服”痕迹**，没卡密的人连服务器信息都拿不到（服务器地址在 APK 里是 127.0.0.1/本地入口，无卡密时服务器只回错误码，不下发任何业务数据）。

## 五、已验证 vs 待验证

| 项 | 状态 |
|---|---|
| sdk_url 改为本地 HTTP 后 SDK 真的连过来 | ✅ 抓到 6 个真实请求 |
| 官方响应可直接中继 | ✅ `sdk_resp/*.json` 全量落盘 |
| 卡密 gate 插在 quick-login | ⏳ 待实现 |
| 游戏网关（state-api）地址 | ⏳ 仍混淆在 libil2cpp，未定位；下一步方案：在 libunity 内 code cave 改 getaddrinfo，或让 SDK 响应里带服务端地址（待验证客户端是否采用）|