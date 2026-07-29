import json
import urllib.error

import web_search as ws


class _FakeResp:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok_payload(titles):
    return {"request_id": "req-1", "references": [
        {"title": t, "url": "https://example.com/%s" % t,
         "snippet": "snip-%s" % t, "content": "body-%s" % t,
         "date": "2026-07-29", "website": "示例站"}
        for t in titles]}


def test_search_success(monkeypatch):
    monkeypatch.setenv("QIANFAN_WEBSEARCH_API_KEY", "bsk-test")
    monkeypatch.setattr(ws.urllib.request, "urlopen",
                        lambda req, timeout=20: _FakeResp(_ok_payload(["A", "B", "C"])))
    results = ws.search("q", top=2)
    assert [r["title"] for r in results] == ["A", "B", "C"]
    assert results[0]["url"] == "https://example.com/A"
    assert results[0]["snippet"] == "snip-A"


def test_missing_key_raises(monkeypatch):
    # 铁律：没配密钥必须报错，不能静默降级
    monkeypatch.delenv("QIANFAN_WEBSEARCH_API_KEY", raising=False)
    monkeypatch.setattr(ws, "_load_api_key", lambda: None)
    try:
        ws.search("q")
        assert False, "缺密钥时应抛错"
    except RuntimeError as e:
        assert "QIANFAN_WEBSEARCH_API_KEY" in str(e)


def test_network_failure_propagates_not_stale(monkeypatch):
    # 铁律：搜不到就抛错，绝不返回空结果/旧数据
    monkeypatch.setenv("QIANFAN_WEBSEARCH_API_KEY", "bsk-test")

    def _boom(req, timeout=20):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(ws.urllib.request, "urlopen", _boom)
    try:
        ws.search("q")
        assert False, "网络失败时应抛错，不得返回空结果"
    except urllib.error.URLError:
        pass


def test_bad_payload_raises(monkeypatch):
    monkeypatch.setenv("QIANFAN_WEBSEARCH_API_KEY", "bsk-test")
    monkeypatch.setattr(ws.urllib.request, "urlopen",
                        lambda req, timeout=20: _FakeResp({"request_id": "x"}))
    try:
        ws.search("q")
        assert False, "网关无 references 时应抛错"
    except RuntimeError:
        pass


def test_main_network_failure_returns_1(monkeypatch, capsys):
    monkeypatch.setenv("QIANFAN_WEBSEARCH_API_KEY", "bsk-test")

    def _boom(req, timeout=20):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(ws.urllib.request, "urlopen", _boom)
    rc = ws.main(["q"])
    assert rc == 1
    assert "不返回缓存" in capsys.readouterr().err
