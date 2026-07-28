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


def main():
    args = parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = resolve_data_dir(script_dir, args.data_dir)
    print("数据输出目录:", data_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
