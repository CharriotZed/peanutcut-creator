import json
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


def test_archive_creates_file_and_index(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    import archive_content as ac
    path = ac.archive(
        topic="茅台跌停复盘", title="茅台跌停!三个信号",
        script_body="开头钩子...", platform=["抖音"], tags=["白酒"],
        created="2026-07-27",
    )
    assert os.path.isfile(path)
    index = json.load(open(os.path.join(str(tmp_path), "index.json"), encoding="utf-8"))
    ids = [e["id"] for e in index["entries"]]
    assert "2026-07-27-茅台跌停复盘" in ids
    entry = index["entries"][0]
    assert entry["status"] == "pending"
    assert entry["title"] == "茅台跌停!三个信号"


def test_archive_appends_series_member(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    import archive_content as ac
    ac.archive(topic="第一期", title="T1", script_body="a",
               platform=["抖音"], tags=[], series="涨停复盘", created="2026-07-27")
    ac.archive(topic="第二期", title="T2", script_body="b",
               platform=["抖音"], tags=[], series="涨停复盘", created="2026-07-28")
    series_file = os.path.join(str(tmp_path), "series", cdb.slugify("涨停复盘") + ".md")
    meta, _ = cdb.parse_frontmatter(open(series_file, encoding="utf-8").read())
    assert len(meta["members"]) == 2


def test_archive_duplicate_id_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_DB_ROOT", str(tmp_path))
    import archive_content as ac
    ac.archive(topic="同题", title="T", script_body="a",
               platform=["抖音"], tags=[], created="2026-07-27")
    import pytest
    with pytest.raises(FileExistsError):
        ac.archive(topic="同题", title="T", script_body="a",
                   platform=["抖音"], tags=[], created="2026-07-27")
