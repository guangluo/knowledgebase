"""WikiStore 存储层测试（包自带，不依赖桌面宠物）。"""
import os
import tempfile

import knowledgebase as kb


def _tmp_wiki():
    return kb.WikiStore(base_dir=tempfile.mkdtemp())


def test_write_and_read_roundtrip():
    w = _tmp_wiki()
    slug = w.write_page("concepts", "向量数据库", "RAG 常配合 [[RAG]] 使用。",
                        sources=["src1"], tags=["检索"])
    assert slug == "向量数据库"
    page = w.read_page("concepts", slug)
    assert page is not None
    assert "RAG 常配合" in page["body"]
    assert page["meta"]["category"] == "concepts"
    assert page["meta"]["sources"] == ["src1"]
    assert page["meta"]["tags"] == ["检索"]


def test_backlinks_empty_links_orphans():
    w = _tmp_wiki()
    w.write_page("concepts", "RAG", "检索增强生成。")
    w.write_page("concepts", "向量数据库", "见 [[RAG]]。")
    # 向量数据库 指向 RAG，故 RAG 有反链；向量数据库本身是孤儿（无页指向它）
    assert "concepts/向量数据库" in w.backlinks("RAG")
    assert "concepts/RAG" not in w.backlinks("向量数据库")
    assert "concepts/向量数据库" in w.orphans()
    assert w.empty_links() == []


def test_empty_link_dangling():
    w = _tmp_wiki()
    w.write_page("concepts", "C", "指向 [[不存在的页]]。")
    empties = w.empty_links()
    assert len(empties) == 1
    assert empties[0][1] == "不存在的页"


def test_conflict_flag():
    w = _tmp_wiki()
    w.write_page("concepts", "X", "旧说法。", conflict=True)
    assert "concepts/X" in w.conflict_pages()
    # 覆盖写入，conflict 应保留
    w.write_page("concepts", "X", "新说法。")
    assert w.read_page("concepts", "X")["meta"]["conflict"] is True


def test_index_persistence():
    d = tempfile.mkdtemp()
    w = kb.WikiStore(base_dir=d)
    w.write_page("concepts", "P", "正文")
    del w
    w2 = kb.WikiStore(base_dir=d)   # 重新加载
    assert "concepts/P" in w2.index["pages"]


def test_stats_counts():
    w = _tmp_wiki()
    w.write_page("concepts", "A", "[[B]]")
    w.write_page("concepts", "B", "无反链", conflict=True)
    s = w.stats()
    assert s["pages"] == 2
    assert s["conflicts"] == 1
    assert s["orphans"] == 1       # B 无反链
    assert s["empty_links"] == 0


def test_default_schema_has_10_rules():
    schema = kb.get_default_schema()
    assert schema["conflict_policy"] == "dual"
    assert len(schema["rules"]) == 10


def test_load_kb_schema_fallback(tmp_path):
    # 不存在的文件 → 回退默认
    assert len(kb.load_kb_schema(str(tmp_path / "missing.json"))["rules"]) == 10
    # 损坏文件 → 回退默认
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert len(kb.load_kb_schema(str(bad))["rules"]) == 10


def test_parse_wikilinks_alias():
    links = kb._parse_wikilinks("见 [[向量数据库|向量DB]] 与 [[RAG]]。")
    assert links == ["向量数据库", "RAG"]
