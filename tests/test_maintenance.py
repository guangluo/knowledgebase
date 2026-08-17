"""WikiMaintainer 自动维护测试（包自带，纯逻辑）。"""
import tempfile

import knowledgebase as kb


def _tmp_wiki():
    return kb.WikiStore(base_dir=tempfile.mkdtemp())


class _StubCompiler:
    def __init__(self, result=None):
        self.res = result or {"compiled": 1}
        self.calls = []

    def compile_item(self, title, source, body, *, related=None, tags=None, on_done=None):
        self.calls.append((title, source, body))
        if on_done:
            on_done(self.res)


def _items():
    return [
        {"ts": 1, "title": "老资料", "source": "s", "content": {"pro": "正文一"}, "raw": "r1"},
        {"ts": 2, "title": "中资料", "source": "s", "content": {"pro": "正文二"}, "raw": "r2"},
        {"ts": 3, "title": "新资料", "source": "s", "content": {"pro": "正文三"}, "raw": "r3"},
    ]


def test_health_no_issues():
    w = _tmp_wiki()
    w.write_page("concepts", "A", "[[B]]")
    w.write_page("concepts", "B", "[[A]]")
    rep = w.health()
    assert rep["counts"]["empty_links"] == 0
    assert rep["counts"]["orphans"] == 0
    assert rep["counts"]["conflicts"] == 0
    assert rep["empty_links"] == []
    assert rep["orphans"] == []
    assert rep["conflicts"] == []


def test_health_reports_orphan():
    w = _tmp_wiki()
    w.write_page("concepts", "孤儿页", "无反链")
    rep = w.health()
    assert "孤儿页" in rep["orphans"]
    assert rep["counts"]["orphans"] == 1


def test_health_reports_conflict():
    w = _tmp_wiki()
    w.write_page("concepts", "冲突页", "两种说法", conflict=True)
    rep = w.health()
    assert "冲突页" in rep["conflicts"]
    assert rep["counts"]["conflicts"] == 1


def test_health_reports_empty_links():
    w = _tmp_wiki()
    w.write_page("concepts", "C", "[[不存在的页]]")
    rep = w.health()
    assert rep["counts"]["empty_links"] == 1
    assert rep["empty_links"][0]["target"] == "不存在的页"


def test_auto_compile_oldest_first():
    w = _tmp_wiki()
    stub = _StubCompiler()
    m = kb.WikiMaintainer(w, stub)
    items = _items()
    # 逐条追上：应依次编译 ts=1,2,3（最旧优先）；推进 now 绕过节流
    now = 1000.0
    for _ in range(3):
        m.auto_compile_next(items, now=now)
        now += 100
    titles = [c[0] for c in stub.calls]
    assert titles == ["老资料", "中资料", "新资料"]


def test_auto_compile_marks_compiled_on_success():
    w = _tmp_wiki()
    stub = _StubCompiler({"compiled": 1})
    m = kb.WikiMaintainer(w, stub)
    m.auto_compile_next(_items())
    assert w.is_compiled(1)


def test_auto_compile_backoff_on_error():
    w = _tmp_wiki()
    stub = _StubCompiler({"compiled": 0, "error": "boom"})
    m = kb.WikiMaintainer(w, stub)
    r1 = m.auto_compile_next(_items())
    assert r1.get("started") is True
    assert not w.is_compiled(1)            # 出错不标记
    # 同一时刻再调：应处于 error 退避，不再编译
    r2 = m.auto_compile_next(_items())
    assert r2.get("reason") == "cooldown"
    assert len(stub.calls) == 1


def test_auto_compile_respects_cooldown():
    w = _tmp_wiki()
    stub = _StubCompiler({"compiled": 1})
    m = kb.WikiMaintainer(w, stub)
    m.auto_compile_next(_items())
    r2 = m.auto_compile_next(_items())   # 同步调用，未过 90s
    assert r2.get("reason") == "cooldown"


def test_auto_compile_skips_empty_body():
    w = _tmp_wiki()
    stub = _StubCompiler({"compiled": 1})
    m = kb.WikiMaintainer(w, stub, body_of=lambda it: "")
    items = [{"ts": 9, "title": "无正文", "source": "s", "content": {}}]
    r = m.auto_compile_next(items)
    assert r.get("skipped") is True
    assert w.is_compiled(9)               # 无正文直接标记已处理，不空转
    assert stub.calls == []


def test_maintainer_caught_up():
    w = _tmp_wiki()
    for it in _items():
        w.mark_compiled(it["ts"])
    stub = _StubCompiler()
    m = kb.WikiMaintainer(w, stub)
    r = m.auto_compile_next(_items())
    assert r.get("reason") == "caught_up"
    assert stub.calls == []
