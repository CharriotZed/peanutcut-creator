import os
import content_db as cdb


def test_resolve_data_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    assert cdb.resolve_data_root() == str(tmp_path)


def test_dump_and_parse_frontmatter_roundtrip():
    meta = {
        "id": "2026-07-27-maotai",
        "created": "2026-07-27",
        "platform": ["抖音", "B站"],
        "tags": ["白酒", "财报"],
        "title": "茅台跌停:压垮它的不是股价",
        "series": "",
        "status": "pending",
        "metrics": {"views": None, "likes": None},
    }
    text = cdb.dump_frontmatter(meta) + "\n正文台词第一句\n"
    parsed, body = cdb.parse_frontmatter(text)
    assert parsed["platform"] == ["抖音", "B站"]
    assert parsed["tags"] == ["白酒", "财报"]
    assert parsed["metrics"] == {"views": None, "likes": None}
    assert parsed["title"] == "茅台跌停:压垮它的不是股价"
    assert parsed["series"] == ""
    assert "正文台词第一句" in body


def test_slugify_handles_chinese_and_punct():
    # 所有非词字符(标点、空格)各自压成单个 dash,首尾 dash 去掉
    assert cdb.slugify("茅台跌停!复盘 2026") == "茅台跌停-复盘-2026"
