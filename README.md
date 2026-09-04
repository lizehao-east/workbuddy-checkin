# WorkBuddy 云端每日签到（GitHub Actions）

每天自动领取 WorkBuddy 每日积分并把结果推送到微信。**与电脑开机关机无关**，GitHub 免费托管。

## 工作原理
- GitHub Actions 每天**北京时间 09:05** 运行（UTC 01:05）
- 脚本用你的 `WB_ACCESS_TOKEN` 调用 WorkBuddy 官方接口领取每日积分
- 「今天已签到」(code 10001) 视为成功，不会误报
- 结果通过 **WxPusher SPT** 推送到你微信

## 需要配置的 Secrets（Settings → Secrets and variables → Actions → New repository secret）

| Secret 名 | 是否必填 | 取值 |
|---|---|---|
| `WB_ACCESS_TOKEN` | ✅ 必填 | WorkBuddy accessToken，从本地登录态文件取 |
| `WB_UID` | 建议 | 账号 uid |
| `WB_ACCOUNT_NAME` | 否 | 昵称（仅日志显示） |
| `WB_DOMAIN` | 否 | 默认 `www.workbuddy.cn` |
| `WB_WXPUSHER_SPT` | ✅ 推荐 | WxPusher SPT 密钥（微信推送用） |
| `WB_SERVERCHAN_SENDKEY` | 否 | 备用：Server酱 SendKey |
| `WB_PUSHPLUS_TOKEN` | 否 | 备用：PushPlus token |

> 没配任何推送渠道也能签到成功，只是不会微信通知你。

## 如何拿到 accessToken（Windows）
文件：`%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info`
JSON 里 `auth.accessToken` 字段的值。
> accessToken 会过期，失效后重新打开 WorkBuddy 客户端刷新登录态，再回 GitHub 更新该 Secret 即可（无需改代码）。

## 手动触发一次测试
仓库 → Actions → 左侧 **WorkBuddy Daily Cloud Checkin** → **Run workflow**。
日志里出现 `[ok] 签到成功` 或 `[ok] 今日已签到` 即正常。
