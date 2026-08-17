"""knowledgebase —— LLM Wiki 知识库框架。

Raw / Wiki / Schema 三层架构：存储、编译、体检、关系图谱。
零运行时依赖，可被任意项目 import 复用。
"""
from .store import WikiStore, _wiki_slug, _now_iso, _parse_wikilinks, _parse_wiki_pages, _WIKI_CATEGORIES
from .schema import get_default_schema, load_kb_schema, save_kb_schema, DEFAULT_SCHEMA
from .compiler import KBCompiler, plan_compile, _WIKI_COMPILE_PROMPT
from .maintenance import WikiMaintainer, _default_body_of
from .graph import (
    build_wiki_graph, wiki_node_color, _short_label, _graph_layout_step,
    CONFLICT_COLOR, SOURCE_COLOR, ORPHAN_COLOR, NORMAL_COLOR, EMPTY_OUTLINE,
)

__version__ = "0.1.0"

__all__ = [
    "WikiStore",
    "KBCompiler",
    "WikiMaintainer",
    "get_default_schema",
    "load_kb_schema",
    "save_kb_schema",
    "DEFAULT_SCHEMA",
    "plan_compile",
    "build_wiki_graph",
    "wiki_node_color",
    "_short_label",
    "_graph_layout_step",
    "_WIKI_CATEGORIES",
    "CONFLICT_COLOR", "SOURCE_COLOR", "ORPHAN_COLOR", "NORMAL_COLOR", "EMPTY_OUTLINE",
    "_wiki_slug", "_now_iso", "_parse_wikilinks", "_parse_wiki_pages", "_default_body_of",
    "_WIKI_COMPILE_PROMPT",
]
