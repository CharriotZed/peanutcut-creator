#!/usr/bin/env python3
"""通过 qianfan web search 网关做联网搜索。

本技能（及其生成的产物 skill）做联网研究时，统一走这个自建网关，而不是直接用
Claude Code / Codex 各自内置的 WebSearch。好处是搜索源可控、结果结构统一、
不同 agent 环境行为一致。

用法:
    python3 web_search.py "英伟达最新财报"
    python3 web_search.py "抖音职场号爆款打法" --top 15 --json
    python3 web_search.py "小红书美食探店" --source baidu_search_v2

API key 读取顺序:
    1. 环境变量 QIANFAN_WEBSEARCH_API_KEY
    2. skill 目录下 .env 里的 QIANFAN_WEBSEARCH_API_KEY=xxx
    未配置则报错退出——不静默降级、不返回空结果。

网关地址同理可覆盖:
    环境变量 QIANFAN_WEBSEARCH_API_BASE 或 .env 里的同名项，默认指向预发网关。

铁律：搜不到就报错，绝不返回缓存/编造的结果。联网研究的价值全在"实时"二字，
拿旧数据或空结果冒充搜索结果，比明说搜不到更有害。
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

DEFAULT_API_BASE = "http://pre-qianfan.bilibili.co/v2/ai_search/web_search"
DEFAULT_SEARCH_SOURCE = "baidu_search_v2"
DEFAULT_TOP_K = 10
DEFAULT_TIMEOUT = 20


def _load_env_value(name):
    """按优先级读取配置：环境变量 > skill 目录 .env。找不到返回 None。"""
    val = os.environ.get(name)
    if val:
        return val.strip()
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() == name:
                    return value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


def _load_api_key():
    return _load_env_value("QIANFAN_WEBSEARCH_API_KEY")


def _load_api_base():
    base = _load_env_value("QIANFAN_WEBSEARCH_API_BASE")
    return (base or DEFAULT_API_BASE).rstrip("/")


def search(query, top=DEFAULT_TOP_K, source=DEFAULT_SEARCH_SOURCE,
           timeout=DEFAULT_TIMEOUT, api_key=None, api_base=None):
    """调用网关做一次搜索，返回精简后的结果列表。

    每条结果字段：title / url / snippet / content / date / website。
    失败抛异常，绝不吞掉、绝不返回空列表冒充"无结果"。
    """
    api_key = api_key or _load_api_key()
    if not api_key:
        raise RuntimeError(
            "未配置 QIANFAN_WEBSEARCH_API_KEY。请把网关密钥写进环境变量，"
            "或 skill 目录下被 .gitignore 排除的 .env 文件："
            "QIANFAN_WEBSEARCH_API_KEY=your-key-here")
    api_base = api_base or _load_api_base()

    body = json.dumps({
        "search_source": source,
        "resource_type_filter": [{"type": "web", "top_k": top}],
        "messages": [{"content": query, "role": "user"}],
    }).encode("utf-8")
    req = urllib.request.Request(
        api_base, data=body, method="POST",
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json; charset=utf-8",
        })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    refs = payload.get("references")
    if not isinstance(refs, list):
        raise RuntimeError("搜索网关返回异常：无 references 数组（%r）"
                           % payload.get("request_id"))
    results = []
    for r in refs:
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("snippet", "") or r.get("web_anchor", ""),
            "content": r.get("content", ""),
            "date": r.get("date", ""),
            "website": r.get("website", ""),
        })
    return results


def _print_human(query, results):
    print("【搜索】%s（%d 条）" % (query, len(results)))
    for i, r in enumerate(results, 1):
        date_s = " · %s" % r["date"] if r["date"] else ""
        site_s = "[%s] " % r["website"] if r["website"] else ""
        print("\n%2d. %s%s%s" % (i, site_s, r["title"], date_s))
        print("    %s" % r["url"])
        snippet = (r["snippet"] or r["content"] or "").strip().replace("\n", " ")
        if snippet:
            print("    %s" % (snippet[:200] + ("…" if len(snippet) > 200 else "")))


def main(argv):
    p = argparse.ArgumentParser(
        description="通过 qianfan web search 网关做联网搜索")
    p.add_argument("query", help="搜索关键词/问题")
    p.add_argument("--top", type=int, default=DEFAULT_TOP_K, help="返回前 N 条")
    p.add_argument("--source", default=DEFAULT_SEARCH_SOURCE, help="搜索源")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    p.add_argument("--json", action="store_true", help="输出原始 JSON 而非人类可读格式")
    args = p.parse_args(argv)

    try:
        results = search(args.query, top=args.top, source=args.source,
                         timeout=args.timeout)
    except (urllib.error.URLError, OSError) as e:
        print("联网搜索失败（网络/网关不可达）：%s\n"
              "本工具不返回缓存数据——请修好网关或网络再重试，"
              "不要拿旧数据/空结果冒充搜索结果。" % e, file=sys.stderr)
        return 1
    except (ValueError, RuntimeError) as e:
        print("联网搜索失败：%s" % e, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        _print_human(args.query, results)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
