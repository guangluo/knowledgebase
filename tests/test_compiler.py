"""KBCompiler 编译引擎测试（包自带）。"""
import tempfile

import knowledgebase as kb


def _tmp_wiki():
    return kb.WikiStore(base_dir=tempfile.mkdtemp())


def _provider(reply):
    def _p(prompt, on_done, on_error, max_tokens=None):
        on_done(reply)
    return _p


def test_plan_finds_existing_related():
    w = _tmp_wiki()
    w.write_page("concepts", "RAG 实践", "关于 RAG。")
    related = kb.plan_compile("RAG 实践", w)
    assert "RAG 实践" in related


def test_plan_no_wiki_returns_empty():
    assert kb.plan_compile("x", None) == []


def test_parse_wiki_pages_json_block():
    reply = "```json\n[{\"title\":\"A\",\"content\":\"c\"}]\n```"
    pages = kb._parse_wiki_pages(reply)
    assert len(pages) == 1 and pages[0]["title"] == "A"


def test_parse_wiki_pages_bare_json():
    pages = kb._parse_wiki_pages("[{\"title\":\"B\",\"content\":\"c\"}]")
    assert pages[0]["title"] == "B"


def test_parse_wiki_pages_fail():
    assert kb._parse_wiki_pages("完全不是 json 的胡说") == []


def test_compile_skips_without_provider():
    w = _tmp_wiki()
    res = kb.KBCompiler(w, None).compile_item("t", "s", "body")
    assert res.get("skipped") is True
    assert w.stats()["pages"] == 0


def test_compile_skips_empty_body():
    w = _tmp_wiki()
    res = kb.KBCompiler(w, _provider("[]")).compile_item("t", "s", "")
    assert res.get("skipped") is True


def test_compile_writes_pages_on_success():
    w = _tmp_wiki()
    reply = ('[{"category":"concepts","title":"X","content":"c [[Y]]",'
             '"sources":["s"],"tags":["t"]}]')
    captured = {}
    kb.KBCompiler(w, _provider(reply)).compile_item(
        "new", "src", "正文…", on_done=captured.update)
    assert captured["compiled"] == 1
    assert "concepts/X" in w.index["pages"]
    assert w.index["pages"]["concepts/X"]["links"] == ["Y"]


def test_compile_no_network_when_key_like_guard():
    # 无 provider 即无网络调用，应直接 skip，不抛异常
    w = _tmp_wiki()
    kb.KBCompiler(w, None).compile_item("t", "s", "body 内容")
    assert w.stats()["pages"] == 0
