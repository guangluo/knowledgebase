"""LLM Wiki 的可配置规则层（对应 LLM Wiki 的 AGENTS.md / Schema 层）。

默认内置 10 条核心维护规则；conflict_policy 控制新旧说法冲突时的处理策略：
- dual：双说并存，不直接覆盖
- overwrite：以新覆盖旧
"""
import json


def get_default_schema():
    """返回一份全新的默认规则 dict（每次调用独立对象，避免调用方误改共享状态）。"""
    return {
        "version": 1,
        "conflict_policy": "dual",   # dual=双说并存; overwrite=覆盖
        "rules": [
            "处理新资料前，先检索 wiki/ 现有页面，判断补旧页还是开新页（增量，不重建全库）",
            "raw/ 是事实来源，禁止改写、删除或移动其中的文件",
            "每份 Raw 在 wiki/sources/ 建对应来源摘要页，保留原始文件链接",
            "概念、实体、主题使用独立页面，通过 [[双链]] 建立关系，不堆在一篇",
            "所有事实性内容都要标注来源；无法确认的内容明确写为「待核实」",
            "新旧资料出现分歧时，同时保留不同说法及其来源、时间和适用范围，不直接覆盖旧结论",
            "每次只更新受影响的页面，并同步维护相关双链、index.json 与 log.json",
            "log.json 采用只追加方式，记录日期、资料来源、新建/更新页面和待人工确认事项",
            "不擅自删除现有页面；同名文件已存在时，先读取并合并必要内容，保留原内容",
            "信息不足或判断可能影响整体结构时，暂停执行并向主人提问",
        ],
    }


# 包级常量，便于直接 import
DEFAULT_SCHEMA = get_default_schema()


def load_kb_schema(path=None):
    """从 path 读取规则；path 缺省/文件缺失/格式异常时回退到默认规则。"""
    if not path:
        return get_default_schema()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data.get("rules"):
            raise ValueError("schema 格式异常")
        return data
    except Exception:
        return get_default_schema()


def save_kb_schema(data, path):
    """把规则写到 path（调用方决定文件位置）。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
