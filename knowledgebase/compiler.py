"""LLM Wiki 编译引擎：KBCompiler。

把一份入库资料（标题 / 来源 / 正文）增量编译成若干结构化互链 wiki 页。
LLM 调用通过 duck-typed provider 注入，包本身不绑定任何具体模型服务：

    provider(prompt, on_done, on_error, max_tokens=None)

- on_done(reply: str)：LLM 成功返回文本时回调
- on_error(err)：调用失败时回调

包仅依赖标准库，绝不引用 GUI / 网络框架 / 调用方代码。
"""
import json

from .store import WikiStore, _parse_wiki_pages

# 通用编译提示词（不绑定任何具体产品品牌）
_WIKI_COMPILE_PROMPT = (
    "你是知识库的编译引擎。下面是一份刚入库的资料（标题、来源、正文摘要）。\n"
    "请把它编译成若干结构化 wiki 页面，规则：\n"
    "1. 先判断是否需要复用已有页面（下面给出当前 wiki 已存在的相关页面标题，若相关就更新它们而不是新建）；\n"
    "2. 页面分类只用 sources / concepts / entities / topics 之一；\n"
    "3. 每个页面用 Markdown 写，概念/实体/主题之间用 [[页面标题]] 双链互联；\n"
    "4. 事实必须标注来源；无法确认写「待核实」；\n"
    "5. 若资料与已有说法冲突，写进同一页并明确标注「冲突：A说…（来源/时间）；B说…（来源/时间）」，不要覆盖；\n"
    "6. 只输出一个 JSON 数组，每个元素："
    "{{\"category\":\"\",\"title\":\"\",\"content\":\"markdown正文\",\"conflict\":false,"
    "\"sources\":[\"\"],\"tags\":[\"\"]}}，不要输出任何额外文字。\n\n"
    "【已存在的 wiki 相关页面】\n{existing}\n\n"
    "【新入库资料】\n标题：{title}\n来源：{source}\n正文：\n{body}"
)


def plan_compile(title, wiki):
    """编译前的纯本地决策（可离线测试）：检索现有 wiki 相关页面标题，供 LLM 复用。"""
    if not isinstance(wiki, WikiStore):
        return []
    related = wiki.search_index(title or "")
    return [t for _, t, _ in related[:10]]


class KBCompiler:
    def __init__(self, wiki, provider, max_tokens=3000):
        """
        wiki:        WikiStore 实例（落库目标）
        provider:    callable(prompt, on_done, on_error, max_tokens=None)
        max_tokens:  编译时传给 provider 的默认上限
        """
        self.wiki = wiki
        self.provider = provider
        self.max_tokens = max_tokens

    def compile_item(self, title, source, body, *, related=None, tags=None, on_done=None):
        """把一份资料增量编译进 wiki/。无正文时优雅跳过（仅记日志），绝不抛异常。

        返回（同步路径下也返回）一个结果 dict：
            {"compiled": N}                      成功写 N 页
            {"compiled": 0, "skipped": True}     无正文/未配置provider，跳过
            {"compiled": 0, "parse_fail": True}  LLM 返回无法解析
            {"compiled": 0, "error": "..."}      调用失败
        """
        wiki = self.wiki
        if wiki is None:
            if on_done:
                on_done({"compiled": 0, "skipped": True})
            return {"compiled": 0, "skipped": True}

        title = title or "未命名"
        source = source or "未知"
        if not (body or "").strip():
            if on_done:
                on_done({"compiled": 0, "skipped": True})
            return {"compiled": 0, "skipped": True}

        if not callable(self.provider):
            wiki.append_log({"source": source, "action": "skip_compile",
                             "note": "未配置 LLM provider，跳过 Wiki 编译"})
            if on_done:
                on_done({"compiled": 0, "skipped": True})
            return {"compiled": 0, "skipped": True}

        if related is None:
            related = plan_compile(title, wiki)
        existing = "\n".join(f"- {t}" for t in related) or "（暂无相关页面）"
        prompt = _WIKI_COMPILE_PROMPT.format(
            existing=existing, title=title, source=source, body=body[:4000])

        def _done(reply):
            try:
                pages = _parse_wiki_pages(reply)
                written = 0
                for p in pages:
                    if not p.get("title"):
                        continue
                    wiki.write_page(
                        p.get("category", "topics"), p["title"], p.get("content", ""),
                        sources=p.get("sources") or [source],
                        tags=p.get("tags") or (tags or []),
                        conflict=bool(p.get("conflict")))
                    written += 1
                wiki.append_log({"source": source, "action": "compile",
                                 "note": f"编译 {written} 个页面", "related": related})
                if on_done:
                    on_done({"compiled": written})
            except Exception:
                wiki.append_log({"source": source, "action": "compile_parse_fail",
                                 "note": "LLM 返回无法解析为页面 JSON"})
                if on_done:
                    on_done({"compiled": 0, "parse_fail": True})

        def _err(e):
            wiki.append_log({"source": source, "action": "compile_error",
                             "note": str(e)[:60]})
            if on_done:
                on_done({"compiled": 0, "error": str(e)[:40]})

        try:
            self.provider(prompt, _done, _err, self.max_tokens)
        except Exception as e:
            wiki.append_log({"source": source, "action": "compile_error",
                             "note": str(e)[:60]})
            if on_done:
                on_done({"compiled": 0, "error": str(e)[:40]})
        return {"compiled": 0, "started": True}
