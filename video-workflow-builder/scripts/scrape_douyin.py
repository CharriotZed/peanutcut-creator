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

    finally:
        context.close()
        browser.close()
        p.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
