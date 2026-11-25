# `LocalizeConfig.txt` 推送操作手册（给执行 agent / 给 lead 复核）

> 本手册只写「把本地已生成的文件放到手机上 + 校验 + 回滚」。
> **不包含任何 adb/ssh 到手机的动作**——由负责推文件的 agent 按自己的授权去做。
> 语义与证据见 `report\54-客户端补丁方案-本地配置绕过.md`。

---

## 0. 一句话

**只有在你确认「远端 CDN 能真的供出客户端要的每一个文件」之后，才推「接管版」；
否则只推「官方基线版」做一次基线复位。**

---

## 1. 目标路径

```
/sdcard/Android/data/com.RoamingStar.BlueArchive/files/LocalizeConfig.txt
```

同目录应能看到这些邻居（用来确认没走错目录）：`Hosts`、`LocalConfig.json`、`GlobalConfig.json`、`DeviceOption`、`TableBundles/`、`AssetBundles/`。

---

## 2. 本地已生成的两个文件

| 文件 | 字节数 | 用途 |
|---|---|---|
| `work\ba\cfg\LocalizeConfig.official.txt` | **164** | **官方基线 / 回滚用**。内容与设备当前文件逐字节一致（sha256 前 16 位 `faac329d83776577`） |
| `work\ba\cfg\LocalizeConfig.cdn-ours.txt` | **131** | **CDN 接管版**（方案 B）：三条都指 `https://example.com/prodm39` |

两份都是 **UTF-8 无 BOM + LF + 末尾不带换行**。**不要用编辑器「另存为」，不要让它自动加换行**。

---

## 3. 推送前必做的三件事

1. **备份现场**
   ```sh
   cp -a .../files/LocalizeConfig.txt .../files/LocalizeConfig.txt.bak-$(date +%s)
   ```
   备份完 `wc -c` 应该也是 **164**。如果备不出来（目录不可写/权限不对），**停手**，先解决权限。

2. **确认远端 CDN 可用**（只有推"接管版"才需要）
   ```sh
   curl -sI https://example.com/prodm39/          # 至少不能 404/5xx
   curl -sI https://example.com/prodm39/catalog_Remote.json
   ```
   证书必须是 **`example.com` 的真证书**（report/09 D04）。**不要自签**。
   如果 TLS 没准备好，就把两条 URL 都改成 `http://` 明文本（社区样例就是这么用的，说明 CDN 侧不强制 TLS）。

3. **确认没有别的 agent 正在改同一批文件**（`Hosts` / `LocalConfig.json` 会被客户端自己写，别和它抢）。

---

## 4. 推送

把选定文件的内容写到目标路径。**写完立刻校验**：

```sh
wc -c .../files/LocalizeConfig.txt        # 必须是 164 或 131
grep -c . .../files/LocalizeConfig.txt    # 必须是 3
od -c .../files/LocalizeConfig.txt | tail -3   # 末尾不应出现 \n
cat .../files/LocalizeConfig.txt          # 肉眼确认三行
```

**权限/属主**：保持和邻居一致（`u0_aXXX` + `ext_data_rw` 组，`rw-rw----`）。
可以用 `ls -ln .../files/Hosts` 看邻居的 uid/gid，再 `chown` 对齐。

---

## 5. 生效验证（冷启动）

1. **完全杀掉客户端**（不要只按 home），再冷启动。
2. 正常冷启动到标题页 **45–58 s**（这是已知基线）。
3. 观察三件事：

| 观察点 | 期望（接管版生效） | 期望（接管版未生效） |
|---|---|---|
| `https://example.com/prodm39/` 的 nginx access_log | **出现 `GET /prodm39/...`** | 一条都没有 |
| 客户端行为 | 提示"下载资源"/重新加载，约 **130 MB** 量级 | 完全照旧，秒进 |
| 我们的抓包/反代日志 | 有 static 类请求打到我们 | 请求还是去官方 static |

4. **不要**期待登录流程有任何变化 —— `ResUrls` 与登录正交（见报告 §8）。
   **登录仍然会卡在 `HttpGameSession.WaitForRequest` 的 `IsFinished`**，这是另一条线。

---

## 6. 失败画像与处置

| 现象 | 含义 | 处置 |
|---|---|---|
| 卡在"资源初始化 / 下载中"不动，或提示网络错误后**进不去游戏** | 远端缺文件 / 证书不对 / 目录 404 | **立刻回滚**（§7） |
| 冷启动变慢但最终进得去 | 远端部分命中（可能只服务了 catalog） | 查 access_log 缺哪些路径，补齐或回滚 |
| 完全没变化 | 文件没被读到，或 `/api/state` 的 `AddressablesCatalogUrlRoots` 把它覆盖了 | 见报告 §11.2 的判定实验；先别继续折腾 |
| 反复弹公告/网络提示 | 可能是 `static` 侧 404（report D-48 已知坑） | 检查远端路径是否齐全 |

---

## 7. 回滚（30 秒）

```sh
cp -a .../files/LocalizeConfig.txt.bak-<ts> .../files/LocalizeConfig.txt
# 或
cp -a work/ba/cfg/LocalizeConfig.official.txt .../files/LocalizeConfig.txt
wc -c .../files/LocalizeConfig.txt    # 回到 164
```

回滚后**冷启动一次**确认能进游戏。回滚不需要清 Cache/不需要重装。

---

## 8. 红线（写在这里防止越界）

- **不要**改 `Env`（保持 `dev`）——无收益，且可能有未知副作用。
- **不要**改 `IsLocalize`（保持 `false`）——语义未证实，改了没有任何被验证过的正面效果。
- **不要**只写 1 条 `ResUrls` —— `CDNLineCount = 3`，必须 3 条（同一 URL 重复 3 次是已知能工作的写法）。
- **不要**给 `https` 自签证书 —— 社区能用的样例用的是 `http`。
- **不要**同时改 `Hosts` / `LocalConfig.json` —— 单变量原则，否则出了事分不清是谁的责任。
- **不要**在没有备份的情况下覆盖原文件。
