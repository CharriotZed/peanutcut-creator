#!/usr/bin/env python3
"""
抓取抖音用户主页账号数据、全部视频指标与评论，生成分析报告。

用法:
    python3 scrape_douyin.py --url https://www.douyin.com/user/MS4w...
    python3 scrape_douyin.py --url https://www.douyin.com/user/MS4w... --session session.json

依赖:
    pip install playwright && playwright install chromium
"""

import argparse
import datetime
import json
import os
import re
import sys
import time


def parse_args():
    parser = argparse.ArgumentParser(description="抓取抖音用户主页数据并生成分析报告")
    parser.add_argument("--url", required=True, help="抖音用户主页 URL")
    parser.add_argument("--session", default="", help="session storage 文件路径（默认自动生成）")
    parser.add_argument("--data-dir", default="", help="输出目录（默认脚本同级 data/）")
    parser.add_argument("--max-comments", type=int, default=20, help="每个视频抓取评论数上限")
    parser.add_argument("--timeout", type=int, default=120, help="扫码登录超时秒数")
    return parser.parse_args()


def resolve_data_dir(script_dir, cli_override):
    if cli_override:
        return cli_override
    d = os.path.join(script_dir, "data")
    os.makedirs(d, exist_ok=True)
    return d


def launch_browser(session_path=""):
    """启动非 headless Chromium，返回 (p, browser, context, page)。"""
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )
    if session_path and os.path.isfile(session_path):
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            storage_state=session_path,
        )
        print("已加载 session:", session_path)
    else:
        context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    return p, browser, context, page


def login_if_needed(page, timeout, session_path):
    """导航到抖音首页，如果需要登录则等待用户扫码。"""
    page.goto("https://www.douyin.com", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    logged_in_selectors = [
        'text=发布视频',
        '[data-e2e="user-avatar"]',
        'img[alt*="头像"]',
    ]
    for sel in logged_in_selectors:
        try:
            if page.locator(sel).first.is_visible(timeout=3000):
                print("[已登录] 检测到登录状态")
                return
        except Exception:
            continue

    print("=" * 50)
    print("请在浏览器中扫码登录抖音")
    print("（%d秒超时，登录后请等待页面跳转到抖音首页）" % timeout)
    print("=" * 50)

    try:
        page.locator('text=登录').first.click(timeout=5000)
    except Exception:
        pass
    time.sleep(2)

    try:
        page.locator('text=扫码登录').first.click(timeout=3000)
    except Exception:
        pass

    start = time.time()
    while time.time() - start < timeout:
        for sel in logged_in_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=2000):
                    print("[登录成功]")
                    time.sleep(2)
                    return
            except Exception:
                continue
        time.sleep(3)

    raise TimeoutError("扫码登录超时（%d秒），请重新运行" % timeout)


def save_session(context, session_path):
    """保存浏览器 session 到文件。"""
    context.storage_state(path=session_path)
    print("session 已保存:", session_path)


def _parse_count(text):
    """将 '1.2万' / '1234' 解析为整数。"""
    if not text:
        return 0
    text = text.strip().replace(",", "").replace(" ", "")
    if "亿" in text:
        return int(float(text.replace("亿", "")) * 100000000)
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    try:
        return int(text)
    except ValueError:
        return 0


def _wait_for_text(page, selectors, timeout=10000):
    """尝试一组选择器，返回第一个有可见文本的元素文本。"""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=timeout)
            text = el.inner_text().strip()
            if text:
                return text
        except Exception:
            continue
    return ""


def scrape_account(page, url):
    """导航到用户主页，提取账号级数据。"""
    print("正在抓取主页数据:", url)
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(5)  # 等 JS 渲染完成

    account = {
        "nickname": "",
        "douyin_id": "",
        "avatar_url": "",
        "signature": "",
        "follower_count": 0,
        "following_count": 0,
        "total_likes": 0,
        "video_count": 0,
        "verified_badge": None,
        "url": url,
        "fetched_at": datetime.datetime.now().isoformat(),
    }

    # 昵称
    account["nickname"] = _wait_for_text(page, [
        '[data-e2e="user-info-name"]',
        'h1[class*="name"]',
        '[class*="profile"] h1',
        'span[class*="nickname"]',
    ], timeout=5000)

    # 抖音号
    account["douyin_id"] = _wait_for_text(page, [
        '[data-e2e="user-info-id"]',
        'span[class*="short-id"]',
        'text=/抖音号:.*/',
    ], timeout=3000)
    if account["douyin_id"]:
        account["douyin_id"] = account["douyin_id"].replace("抖音号:", "").replace("抖音号：", "").strip()

    # 简介
    account["signature"] = _wait_for_text(page, [
        '[data-e2e="user-info-desc"]',
        'span[class*="signature"]',
        'p[class*="desc"]',
    ], timeout=3000)

    # 粉丝数、关注数、获赞数 —— 使用通用的统计项选择器
    stat_items = page.locator('[data-e2e="user-info-stats"] span, [class*="stats"] span, [class*="count"]').all()
    stat_texts = []
    for item in stat_items:
        try:
            text = item.inner_text().strip()
            if text:
                stat_texts.append(text)
        except Exception:
            continue

    # 查找"获赞"、"关注"、"粉丝"附近的数字
    # 抖音主页的统计数据通常在一行中显示
    all_text = page.locator('[data-e2e="user-info-stats"], [class*="stats"], [class*="user-info"]').first.inner_text() if page.locator('[data-e2e="user-info-stats"], [class*="stats"], [class*="user-info"]').count() > 0 else ""

    # 用模式匹配提取数字
    follower_match = re.search(r"(\d[\d,.]*[亿万]?)\s*(?:粉丝|获赞)", all_text)
    if not follower_match:
        follower_match = re.search(r"(?:粉丝|获赞)\s*:?\s*(\d[\d,.]*[亿万]?)", all_text)

    # 遍历 stat_texts 按位置推断
    # 典型结构: "获赞 X  关注 Y  粉丝 Z" 或 "X 获赞  Y 关注  Z 粉丝"
    for i, t in enumerate(stat_texts):
        if "获赞" in t or "赞" in t:
            # 数字可能在前面或后面
            num = re.search(r"(\d[\d,.]*[亿万]?)", t)
            if num:
                account["total_likes"] = _parse_count(num.group(1))
        elif "关注" in t:
            num = re.search(r"(\d[\d,.]*[亿万]?)", t)
            if num:
                account["following_count"] = _parse_count(num.group(1))
        elif "粉丝" in t:
            num = re.search(r"(\d[\d,.]*[亿万]?)", t)
            if num:
                account["follower_count"] = _parse_count(num.group(1))

    # 作品数
    video_count_text = _wait_for_text(page, [
        '[data-e2e="user-tab-video"] span',
        'text=/作品.*\d/',
    ], timeout=3000)
    count_match = re.search(r"(\d[\d,.]*[亿万]?)", video_count_text or "")
    if count_match:
        account["video_count"] = _parse_count(count_match.group(1))

    # 认证标识
    try:
        badge = page.locator('[data-e2e="verified-badge"], [class*="verified"], [class*="certify"]').first
        if badge.is_visible(timeout=2000):
            account["verified_badge"] = badge.inner_text().strip()
    except Exception:
        pass

    print("账号: %s (粉丝: %s, 获赞: %s, 作品: %s)" % (
        account["nickname"],
        account["follower_count"],
        account["total_likes"],
        account["video_count"],
    ))
    return account


def main():
    args = parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = resolve_data_dir(script_dir, args.data_dir)
    session_path = args.session or os.path.join(data_dir, "douyin_session.json")

    p, browser, context, page = launch_browser(session_path)
    try:
        login_if_needed(page, args.timeout, session_path)
        save_session(context, session_path)

        # 等待用户查看浏览器，确认登录成功
        print("登录完成，浏览器将保持打开。请在终端继续操作。")
        input("按 Enter 开始抓取数据...")

        account = scrape_account(page, args.url)
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        json_path = os.path.join(data_dir, "%s-douyin-account.json" % timestamp)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"account": account, "videos": []}, f, ensure_ascii=False, indent=2)
        print("账号数据已保存:", json_path)

    finally:
        context.close()
        browser.close()
        p.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
