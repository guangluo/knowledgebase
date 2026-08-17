"""Wiki 自动维护：WikiMaintainer（体检 + 增量编译存量）。

纯逻辑、零 GUI 依赖。调用方负责把结果呈现到 UI（如冒泡提醒）、负责线程调度。
"""
import time

from .store import WikiStore
from .compiler import KBCompiler


def _default_body_of(item):
    """从一条 KB 条目抽取可编译正文（通用默认实现，覆盖常见 content 结构）。"""
    c = item.get("content", {}) or {}
    if isinstance(c, dict):
        return c.get("pro") or c.get("baize") or (item.get("raw", "") or "")[:300]
    return (item.get("raw", "") or "")[:300]


class WikiMaintainer:
    def __init__(self, wiki, compiler, cooldown=90, error_cooldown=1800, body_of=None):
        """
        wiki:            WikiStore 实例
        compiler:        KBCompiler 实例
        cooldown:        正常节奏下两条编译最小间隔（秒），默认 90
        error_cooldown:  上一次出错后到下次重试的退避间隔（秒），默认 1800（30 分钟）
        body_of:         callable(item) -> str，从 KB 条目抽取正文；缺省用 _default_body_of
        """
        self.wiki = wiki
        self.compiler = compiler
        self.cooldown = cooldown
        self.error_cooldown = error_cooldown
        self._body_of = body_of or _default_body_of
        self._compiling = False
        self._last_compile = 0.0
        self._last_error = False

    def auto_compile_next(self, kb_items, now=None):
        """把 KB 里尚未编入 wiki 的条目，按节奏（最旧优先）逐条增量编译，追上存量。

        返回结果 dict，例如：
            {"compiled": 0, "reason": "in_progress" | "no_items" | "cooldown" | "caught_up"}
            {"compiled": 0, "skipped": True}            无正文，标记已处理避免空转
            {"compiled": 0, "started": True}            已发起异步编译
        on_done 在编译完成/失败后回写 compiled 标记。
        """
        if now is None:
            now = time.time()
        if self._compiling:
            return {"compiled": 0, "reason": "in_progress"}
        if not isinstance(self.wiki, WikiStore):
            return {"compiled": 0, "reason": "no_wiki"}
        if not kb_items:
            return {"compiled": 0, "reason": "no_items"}
        gap = self.error_cooldown if self._last_error else self.cooldown
        if now - self._last_compile < gap:
            return {"compiled": 0, "reason": "cooldown"}

        pending = [it for it in kb_items if not self.wiki.is_compiled(it.get("ts"))]
        if not pending:
            return {"compiled": 0, "reason": "caught_up"}
        pending.sort(key=lambda x: x.get("ts", 0))   # 最旧的先编译，追上存量
        it = pending[0]
        ts = it.get("ts")
        title = it.get("title", "") or "未命名"
        source = it.get("source", "") or "未知"
        body = self._body_of(it)
        if not (body or "").strip():
            # 没有可编译正文，直接标记为已处理，避免空转
            self.wiki.mark_compiled(ts)
            return {"compiled": 0, "skipped": True}

        self._compiling = True
        self._last_compile = now

        def _on(d):
            self._compiling = False
            if d.get("compiled", 0) > 0 or d.get("skipped"):
                self.wiki.mark_compiled(ts)
                self._last_error = False
            elif d.get("parse_fail") or d.get("error"):
                self._last_error = True

        self.compiler.compile_item(title, source, body, on_done=_on)
        return {"compiled": 0, "started": True}
