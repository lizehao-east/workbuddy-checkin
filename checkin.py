#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy 云端每日签到脚本（GitHub Actions / 任何 CI）
- 凭证全部来自环境变量 / Secret：WB_ACCESS_TOKEN、WB_UID、WB_DOMAIN(可选)
- 调用官方接口领取每日积分；"已签到"(code 10001) 视为成功
- 结果通过 WxPusher SPT 推送到微信（WB_WXPUSHER_SPT）
  可选 fallback：Server酱(WB_SERVERCHAN_SENDKEY) / PushPlus(WB_PUSHPLUS_TOKEN)
纯 Python 标准库，零第三方依赖。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

API_DOMAIN = (os.environ.get("WB_DOMAIN") or "www.workbuddy.cn").strip() or "www.workbuddy.cn"
CHECKIN_STATUS_URL = f"https://{API_DOMAIN}/v2/billing/meter/checkin-status"
DAILY_CHECKIN_URL = f"https://{API_DOMAIN}/v2/billing/meter/daily-checkin"
REQUEST_TIMEOUT = 20


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode("utf-8", errors="replace").decode("utf-8", errors="replace"), flush=True)


def build_headers(creds: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {creds['access_token']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "WorkBuddy-Cloud-Checkin/1.0",
    }
    if creds.get("uid"):
        headers["X-User-Id"] = creds["uid"]
    if creds.get("domain"):
        headers["X-Domain"] = creds["domain"]
    return headers


def request_json(url: str, creds: dict) -> dict | None:
    req = urllib.request.Request(url, data=b"{}", method="POST", headers=build_headers(creds))
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        log(f"   HTTP {e.code}: {e.reason} {err_body[:300]}")
        try:
            return json.loads(err_body) if err_body else None
        except Exception:
            return None
    except Exception as e:
        log(f"   请求失败: {e}")
        return None


def msg_of(payload) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("message") or payload.get("msg") or "")


def already_checked_in(payload) -> bool:
    if not isinstance(payload, dict):
        return False
    code = payload.get("code")
    m = msg_of(payload)
    if code == 10001 or "已签到" in m or "已经签到" in m:
        return True
    return bool(payload.get("today_checked_in") or payload.get("checked_in"))


def unwrap_data(payload):
    if not isinstance(payload, dict):
        return None
    code = payload.get("code")
    if code is not None and code not in (0, 200):
        return None
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def load_creds() -> dict | None:
    token = os.environ.get("WB_ACCESS_TOKEN", "").strip()
    if not token:
        log("[x] 缺少 WB_ACCESS_TOKEN")
        return None
    return {
        "access_token": token,
        "account_name": os.environ.get("WB_ACCOUNT_NAME", "cloud").strip() or "cloud",
        "uid": os.environ.get("WB_UID", "").strip() or None,
        "domain": API_DOMAIN,
    }


def do_checkin() -> dict:
    creds = load_creds()
    if not creds:
        return {"ok": False, "title": "WorkBuddy 签到失败 ❌",
                "content": "云端缺少 WB_ACCESS_TOKEN，请在仓库 Settings→Secrets 中配置。"}

    log(f"账号: {creds['account_name']}  domain: {creds['domain']}")

    status_raw = request_json(CHECKIN_STATUS_URL, creds)
    if already_checked_in(status_raw):
        log("[ok] 今日已签到，无需重复领取。")
        return {"ok": True, "title": "今日已签到 ✅",
                "content": f"账号「{creds['account_name']}」今日已领取过积分，无需重复签到。"}

    result_raw = request_json(DAILY_CHECKIN_URL, creds)
    if already_checked_in(result_raw):
        log("[ok] 今日已签到。")
        return {"ok": True, "title": "今日已签到 ✅",
                "content": f"账号「{creds['account_name']}」今日已领取过积分。"}

    result = unwrap_data(result_raw)
    if result is None:
        err = msg_of(result_raw) or f"接口异常(HTTP/网络)。域名={API_DOMAIN}"
        return {"ok": False, "title": "WorkBuddy 签到失败 ❌",
                "content": f"账号「{creds['account_name']}」签到失败：{err}。可能原因：WB_ACCESS_TOKEN 过期，需重新从 WorkBuddy 本地登录态更新。"}

    if result.get("success") is False:
        return {"ok": False, "title": "WorkBuddy 签到失败 ❌",
                "content": f"账号「{creds['account_name']}」领取未成功：{result.get('message') or result}"}

    credit = result.get("credit", result.get("today_credit", result.get("points")))
    streak = result.get("streak_days")
    extra = []
    if credit is not None:
        extra.append(f"本次获得 {credit} 积分")
    if streak is not None:
        extra.append(f"连续签到 {streak} 天")
    detail = "，".join(extra) or "领取成功"
    log(f"[ok] 签到成功! {detail}")
    return {"ok": True, "title": "WorkBuddy 签到成功 🎉",
            "content": f"账号「{creds['account_name']}」云端每日积分领取成功！\n{detail}"}


def push_wechat(title: str, content: str) -> bool:
    text = f"{title}\n{content}"
    try:
        if os.environ.get("WB_WXPUSHER_SPT"):
            spt = os.environ["WB_WXPUSHER_SPT"].strip()
            payload = json.dumps({
                "spt": spt,
                "content": f"### {title}\n\n{content}",
                "summary": title[:100],
                "contentType": 3,
            }).encode()
            req = urllib.request.Request(
                "https://wxpusher.zjiecode.com/api/send/message/simple-push",
                data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                r = json.loads(resp.read().decode())
            ok = r.get("code") == 1000
            log(f"[{'ok' if ok else 'x'}] WxPusher SPT推送: {r}")
            return ok
        if os.environ.get("WB_SERVERCHAN_SENDKEY"):
            key = os.environ["WB_SERVERCHAN_SENDKEY"].strip()
            body = urllib.parse.urlencode({"title": title[:32], "desp": content}).encode()
            req = urllib.request.Request(f"https://sctapi.ftqq.com/{key}.send", data=body, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                r = json.loads(resp.read().decode())
            ok = r.get("code") == 0
            log(f"[{'ok' if ok else 'x'}] Server酱推送: {r}")
            return ok
        if os.environ.get("WB_PUSHPLUS_TOKEN"):
            token = os.environ["WB_PUSHPLUS_TOKEN"].strip()
            payload = json.dumps({"token": token, "title": title[:100], "content": content, "template": "txt"}).encode()
            req = urllib.request.Request("https://www.pushplus.plus/send", data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                r = json.loads(resp.read().decode())
            ok = r.get("code") == 200
            log(f"[{'ok' if ok else 'x'}] PushPlus推送: {r}")
            return ok
    except Exception as e:
        log(f"[x] 微信推送异常: {e}")
        return False
    log("[i] 未配置任何推送渠道，跳过微信推送")
    return False


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    log("=" * 52)
    log("WorkBuddy 云端每日签到")
    log("=" * 52)
    result = do_checkin()
    pushed = push_wechat(result["title"], result["content"])
    log(f"结束 ok={result['ok']} wechat_pushed={pushed}")
    # 无论成败均以非零区分，便于 CI 日志观察（推送失败不视为签到失败）
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    import urllib.parse
    sys.exit(main())
