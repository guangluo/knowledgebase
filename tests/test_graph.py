"""关系图谱纯函数测试（包自带）。"""
import tempfile

import knowledgebase as kb


def _tmp_wiki():
    return kb.WikiStore(base_dir=tempfile.mkdtemp())


def _index():
    w = _tmp_wiki()
    w.write_page("sources", "S", "来源页，指向 [[A]]。")
    w.write_page("concepts", "A", "A 指向 [[B]]。")
    w.write_page("concepts", "B", "B 被 A 指向。")
    w.write_page("concepts", "C", "C 指向 [[不存在的页]]。")
    return w.index


def test_build_wiki_graph_links_and_dangling():
    nodes, edges, danglers = kb.build_wiki_graph(_index())
    assert ("sources/S", "concepts/A", False) in edges
    assert ("concepts/A", "concepts/B", False) in edges
    assert ("concepts/C", "不存在的页", True) in edges
    assert "concepts/C" in danglers


def test_node_color_priority():
    meta_conf = {"category": "concepts", "conflict": True}
    meta_src = {"category": "sources", "conflict": False}
    meta_orph = {"category": "concepts", "conflict": False}
    meta_norm = {"category": "concepts", "conflict": False}
    assert kb.wiki_node_color("k1", meta_conf, set(), set()) == kb.CONFLICT_COLOR
    assert kb.wiki_node_color("k2", meta_src, set(), set()) == kb.SOURCE_COLOR
    assert kb.wiki_node_color("k3", meta_orph, {"k3"}, set()) == kb.ORPHAN_COLOR
    assert kb.wiki_node_color("k4", meta_norm, set(), set()) == kb.NORMAL_COLOR


def test_layout_bounded_and_finite():
    W, H = 560, 540
    nodes = {
        "a": {"x": 100, "y": 100, "vx": 0, "vy": 0},
        "b": {"x": 120, "y": 110, "vx": 0, "vy": 0},
    }
    edges = [("a", "b", False)]
    for _ in range(200):
        kb._graph_layout_step(nodes, edges, W, H)
    for nd in nodes.values():
        assert abs(nd["x"]) < 1e6 and abs(nd["y"]) < 1e6   # 有限
        assert 0 <= nd["x"] <= W and 0 <= nd["y"] <= H       # 有界


def test_layout_repulsion():
    nodes = {
        "a": {"x": 100.0, "y": 100.0, "vx": 0.0, "vy": 0.0},
        "b": {"x": 102.0, "y": 100.0, "vx": 0.0, "vy": 0.0},
    }
    edges = []
    d0 = abs(nodes["a"]["x"] - nodes["b"]["x"])
    kb._graph_layout_step(nodes, edges, 560, 540)
    d1 = abs(nodes["a"]["x"] - nodes["b"]["x"])
    assert d1 > d0   # 斥力使间距变大


def test_short_label_truncates():
    assert kb._short_label("abcdefghij", 6) == "abcdef…"
    assert kb._short_label("短", 6) == "短"
