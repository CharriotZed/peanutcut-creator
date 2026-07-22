#!/usr/bin/env python3
"""
用 gpt-image-2 生成视频封面（走 B站 LLM 网关）。

用法:
    python3 generate_cover.py --platform bilibili --prompt "封面画面描述" --output cover_bilibili.png
    python3 generate_cover.py --platform douyin   --prompt "..."        --output cover_douyin.png

API key 读取顺序:
    1. 环境变量 LLM_GATEWAY_API_KEY（优先，方便临时覆盖）
    2. skill 目录下的 .env 文件里的 LLM_GATEWAY_API_KEY=xxx（兜底，免去每次 export）
    .env 已在 .gitignore 中，不会被提交。

依赖:
    pip install openai
"""

import argparse
import base64
import os
import sys

BASE_URL = "http://llmapi.bilibili.co/v1"
MODEL = "gpt-image-2"

# 平台 -> 画幅尺寸。取最接近目标比例的档位：
#   bilibili / baijiahao 4:3 横版  -> 1024x768
#   douyin / xiaohongshu / shipinhao 3:4 竖版 -> 768x1024
PLATFORM_SIZES = {
    "douyin": "768x1024",
    "bilibili": "1024x768",
    "xiaohongshu": "768x1024",
    "shipinhao": "768x1024",
    "baijiahao": "1024x768",
}


def _load_api_key():
    """按优先级读取 API key：环境变量 > skill 目录下的 .env。"""
    key = os.environ.get("LLM_GATEWAY_API_KEY")
    if key:
        return key.strip()
    # 兜底：读取 skill 根目录（本脚本上一级）下的 .env
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == "LLM_GATEWAY_API_KEY":
                    return value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


def resolve_size(platform, override):
    """手动指定 --size 时优先使用，否则按平台取默认画幅。"""
    if override:
        return override
    return PLATFORM_SIZES[platform]


def main():
    parser = argparse.ArgumentParser(description="生成视频封面 (gpt-image-2)")
    parser.add_argument(
        "--platform",
        required=True,
        choices=list(PLATFORM_SIZES.keys()),
        help="目标平台，决定画幅比例",
    )
    parser.add_argument("--prompt", required=True, help="封面画面描述提示词")
    parser.add_argument("--output", required=True, help="输出文件路径 (.png)")
    parser.add_argument(
        "--size",
        default=None,
        help="可选，手动指定尺寸如 1024x768，覆盖平台默认值",
    )
    args = parser.parse_args()

    api_key = _load_api_key()
    if not api_key:
        print(
            "错误：未找到 LLM_GATEWAY_API_KEY。\n"
            "请二选一：export LLM_GATEWAY_API_KEY=你的key，"
            "或在 skill 目录下的 .env 里写入 LLM_GATEWAY_API_KEY=你的key。",
            file=sys.stderr,
        )
        return 1

    try:
        import openai
    except ImportError:
        print("错误：未安装 openai 库。请运行:  pip install openai", file=sys.stderr)
        return 1

    size = resolve_size(args.platform, args.size)
    client = openai.OpenAI(base_url=BASE_URL, api_key=api_key)

    print("正在生成 " + args.platform + " 封面 (" + size + ") ...", file=sys.stderr)
    try:
        result = client.images.generate(
            model=MODEL,
            prompt=args.prompt,
            size=size,
            n=1,
        )
    except Exception as e:
        print("生成失败：" + str(e), file=sys.stderr)
        return 1

    data = result.data[0]
    image_bytes = None

    # 网关可能返回 base64 或 url，两种都兼容
    b64 = getattr(data, "b64_json", None)
    if b64:
        image_bytes = base64.b64decode(b64)
    else:
        url = getattr(data, "url", None)
        if not url:
            print("生成失败：返回结果中既无 b64_json 也无 url。", file=sys.stderr)
            return 1
        import urllib.request

        with urllib.request.urlopen(url) as resp:
            image_bytes = resp.read()

    with open(args.output, "wb") as f:
        f.write(image_bytes)

    print("已保存封面：" + args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
