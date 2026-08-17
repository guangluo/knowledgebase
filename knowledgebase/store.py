"""LLM Wiki 存储层：WikiStore。

本地 wiki/ 目录为唯一真相源（每页一个 .md，含 [[双链]] + index.json 元数据）。
仅依赖标准库，可被任意项目复用。用户知识内容由构造参数 base_dir 指定，不随包分发。
"""
import os
import json
import time

# 页面分类（对应 LLM Wiki 的 concepts / entities / topics / sources）
_WIKI_CATEGORIES = ("sources", "concepts", "entities", "topics")


def _wiki_slug(title):
    """把页面标题转成安全的文件名 slug（保留中英文与下划线，其余折叠为 _）。"""
    s = (title or "").strip().replace(" ", "_")
    out = []
    for ch in s:
        if ch.isalnum() or ch in "_-." or "\u4e00" <= ch <= "\u9fff":
            out.append(ch)
        else:
            out.append("_")
    slug = "".join(out).strip("_") or "untitled"
    return slug[:80]


def _now_iso():
    return time.strftime("%Y-%m-%d %H:%M", time.localtime())


def _yaml_scalar(v):
    """把标量安全格式化为 YAML 单行字符串，必要时加双引号转义（不引入第三方依赖）。"""
    s = "" if v is None else str(v)
    if (not s) or s != s.strip() or any(ch in s for ch in (":", "#", "'", '"', "[", "]", "{", "}")):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _parse_yaml_scalar(s):
    """解析 YAML 标量：处理双引号 / 单引号包裹，其余按原文返回。"""
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s


def _format_frontmatter(meta):
    """生成 Obsidian 原生 YAML frontmatter（title/type/aliases/tags/sources/created/updated）。"""
    L = ["---"]
    L.append("title: " + _yaml_scalar(meta.get("title", "")))
    L.append("type: " + _yaml_scalar(meta.get("type", "")))
    L.append("aliases:")
    for a in (meta.get("aliases") or []):
        L.append("  - " + _yaml_scalar(a))
    L.append("tags:")
    for t in (meta.get("tags") or []):
        L.append("  - " + _yaml_scalar(t))
    L.append("sources:")
    for s in (meta.get("sources") or []):
        L.append("  - " + _yaml_scalar(s))
    L.append("created: " + _yaml_scalar(meta.get("created", "")))
    L.append("updated: " + _yaml_scalar(meta.get("updated", "")))
    L.append("---")
    return "\n".join(L) + "\n"


def _parse_frontmatter(text):
    """若 text 以 --- 开头，解析简单 YAML frontmatter，返回 (dict, body)；否则 (None, text)。

    仅支持本包写入的字段子集（标量 + 简单列表），对未知字段忽略；
    足以支撑 Obsidian 原生元数据的写入与回读，且不引入第三方依赖。
    """
    if not text.startswith("---"):
        return None, text
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return None, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, text
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])
    if body.startswith("\n"):
        body = body[1:]
    meta = {}
    i, n = 0, len(fm_lines)
    while i < n:
        line = fm_lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            items = []
            j = i + 1
            while j < n and (fm_lines[j].startswith("  - ") or fm_lines[j].strip().startswith("- ")):
                item = fm_lines[j].strip()[2:].strip()
                items.append(_parse_yaml_scalar(item))
                j += 1
            meta[key] = items
            i = j
        else:
            meta[key] = _parse_yaml_scalar(val)
            i += 1
    return meta, body


def _parse_wikilinks(md):
    """从 markdown 提取 [[目标]] 双链，返回去重目标列表（纯字符串解析，不依赖 re）。
    支持 [[标题|显示名]] 形式，取标题部分。"""
    links, seen = [], set()
    i, n = 0, len(md)
    while True:
        j = md.find("[[", i)
        if j < 0:
            break
        k = md.find("]]", j + 2)
        if k < 0:
            break
        target = md[j + 2:k].strip()
        if "|" in target:
            target = target.split("|", 1)[0].strip()
        if target and target not in seen:
            seen.add(target)
            links.append(target)
        i = k + 2
    return links


def _parse_wiki_pages(reply):
    """从 LLM 回复里尽量抠出页面 JSON 数组；支持外层 ```json 代码块或多余文字包裹。"""
    if not reply:
        return []
    text = reply.strip()
    low = text.lower()
    start = low.find("```json")
    if start >= 0:
        end = text.find("```", start + 7)
        if end > start:
            text = text[start + 7:end].strip()
    else:
        s, e = text.find("["), text.rfind("]")
        if s >= 0 and e > s:
            text = text[s:e + 1]
    try:
        data = json.loads(text)
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("pages", [data])
    if not isinstance(data, list):
        return []
    return [p for p in data if isinstance(p, dict) and p.get("title")]


class WikiStore:
    def __init__(self, base_dir=None):
        """base_dir：wiki 落盘根目录（由调用方指定）。默认 "./wiki"。"""
        self.base_dir = os.path.abspath(base_dir or "wiki")
        self.index_file = os.path.join(self.base_dir, "index.json")
        self.log_file = os.path.join(self.base_dir, "log.json")
        self.compiled_file = os.path.join(self.base_dir, "_compiled.json")
        self.index = {"pages": {}}
        self.log = []
        self._compiled = None
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            for cat in _WIKI_CATEGORIES:
                os.makedirs(os.path.join(self.base_dir, cat), exist_ok=True)
        except Exception:
            pass
        self._load_index()
        self._load_log()
        self._load_compiled()

    # ---- 持久化 ----
    def _load_index(self):
        try:
            with open(self.index_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "pages" in data:
                self.index = data
        except Exception:
            self.index = {"pages": {}}

    def _save_index(self):
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_log(self):
        try:
            with open(self.log_file, encoding="utf-8") as f:
                self.log = json.load(f)
            if not isinstance(self.log, list):
                self.log = []
        except Exception:
            self.log = []

    def _save_log(self):
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(self.log, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---- 已编译标记（哪些 KB 条目已编入 wiki）----
    def _load_compiled(self):
        try:
            with open(self.compiled_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._compiled = set(data)
                return
        except Exception:
            pass
        self._compiled = set()

    def _save_compiled(self):
        try:
            with open(self.compiled_file, "w", encoding="utf-8") as f:
                json.dump(sorted(self._compiled), f, ensure_ascii=False)
        except Exception:
            pass

    def is_compiled(self, ts):
        return ts in self._compiled

    def mark_compiled(self, ts):
        if ts is None:
            return
        self._compiled.add(ts)
        self._save_compiled()

    def compiled_set(self):
        return set(self._compiled)

    # ---- 基础读写 ----
    def _key(self, category, slug):
        return f"{category}/{slug}"

    def page_path(self, category, slug):
        return os.path.join(self.base_dir, category, f"{slug}.md")

    def write_page(self, category, title, content_md, *, links=None, sources=None,
                   tags=None, aliases=None, conflict=False, raw_ts=None):
        """新建或覆盖一个 wiki 页：写 .md 文件（含 Obsidian frontmatter）+ 更新 index 元数据。返回 slug。"""
        if category not in _WIKI_CATEGORIES:
            category = "topics"
        slug = _wiki_slug(title)
        key = self._key(category, slug)
        existing = self.index["pages"].get(key, {})
        now = _now_iso()
        meta = {
            "category": category,
            "slug": slug,
            "title": title,
            "type": category.rstrip("s"),
            "aliases": aliases if aliases is not None else existing.get("aliases", []),
            "tags": tags or existing.get("tags", []),
            "sources": sources or existing.get("sources", []),
            "links": links if links is not None else _parse_wikilinks(content_md),
            "created": existing.get("created", now),
            "updated": now,
            "conflict": bool(conflict) or existing.get("conflict", False),
            "raw_ts": raw_ts if raw_ts is not None else existing.get("raw_ts"),
        }
        try:
            # 防御：剥离传入正文可能自带的 frontmatter，避免双重 --- 块；
            # 再以 index 元数据为准生成标准 frontmatter，紧随正文写入。
            _, body = _parse_frontmatter(content_md or "")
            full = _format_frontmatter(meta) + "\n" + body
            with open(self.page_path(category, slug), "w", encoding="utf-8") as f:
                f.write(full)
        except Exception:
            pass
        self.index["pages"][key] = meta
        self._save_index()
        return slug

    def read_page(self, category, slug):
        key = self._key(category, slug)
        base_meta = self.index["pages"].get(key)
        if base_meta is None:
            return None
        try:
            with open(self.page_path(category, slug), encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            raw = ""
        fm, body = _parse_frontmatter(raw)
        meta = dict(base_meta)
        if fm:
            # frontmatter 存在的字段覆盖 index 元数据（Obsidian 手改可被回读）
            for k in ("title", "type", "aliases", "tags", "sources", "created", "updated"):
                if k in fm and fm[k] not in (None, "", [], {}):
                    meta[k] = fm[k]
        return {"meta": meta, "body": body}

    def search_index(self, query):
        """按标题/别名/标签做不区分大小写子串匹配，返回 [(key,title,score)] 降序。"""
        q = (query or "").lower().strip()
        if not q:
            return []
        scored = []
        for key, meta in self.index["pages"].items():
            title = (meta.get("title") or "").lower()
            aliases = " ".join(meta.get("aliases", [])).lower()
            tags = " ".join(meta.get("tags", [])).lower()
            score = 0
            if q in title:
                score += 3
            if q in aliases:
                score += 2
            if q in tags:
                score += 1
            if score > 0:
                scored.append((key, meta.get("title", ""), score))
        scored.sort(key=lambda x: x[2], reverse=True)
        return scored

    # ---- 图谱 / 体检 ----
    def backlinks(self, slug):
        """哪些页面通过 [[双链]] 指向了 slug（按 slug 或标题匹配）。"""
        result = set()
        for key, meta in self.index["pages"].items():
            for ln in meta.get("links", []):
                if ln == slug or ln == meta.get("title"):
                    result.add(key)
        return result

    def empty_links(self):
        """指向不存在页面的 [[双链]]：返回 [(来源key, 目标)]。"""
        known = {meta.get("slug") for meta in self.index["pages"].values()}
        known |= {meta.get("title") for meta in self.index["pages"].values()}
        return [(key, ln) for key, meta in self.index["pages"].items()
                for ln in meta.get("links", []) if ln not in known]

    def orphans(self):
        """无反向链接、且非来源页的页面（孤儿知识）。"""
        out = []
        for key, meta in self.index["pages"].items():
            if meta.get("category") == "sources":
                continue
            if not self.backlinks(meta.get("slug")) and not self.backlinks(meta.get("title", "")):
                out.append(key)
        return out

    def conflict_pages(self):
        return [key for key, meta in self.index["pages"].items() if meta.get("conflict")]

    def resolve_conflict(self, category, slug, new_body=None):
        """人工裁决冲突页：清除 index 中的 conflict 标记。

        - new_body 为 None：仅翻转标记，正文不动（用户已在别处修订）。
        - new_body 给定：先就地清空标记，再调用 write_page 重写正文，确保
          conflict 不会被旧的 True 值继承；frontmatter / 双链解析照常保留。
        返回 True 表示成功消解，False 表示页面不存在。
        """
        key = self._key(category, slug)
        meta = self.index["pages"].get(key)
        if meta is None:
            return False
        if new_body is not None:
            # 先就地清空标记，write_page 读取 existing 时才不会继承旧 True
            self.index["pages"][key]["conflict"] = False
            self.write_page(
                category, meta.get("title", slug), new_body,
                sources=meta.get("sources"), tags=meta.get("tags"),
                aliases=meta.get("aliases"), conflict=False,
            )
        else:
            self.index["pages"][key]["conflict"] = False
            self._save_index()
        return True

    # ---- 日志 ----
    def append_log(self, entry):
        try:
            entry = dict(entry)
            entry.setdefault("date", _now_iso())
            self.log.append(entry)
            if len(self.log) > 500:
                self.log = self.log[-500:]
            self._save_log()
        except Exception:
            pass

    def stats(self):
        pages = list(self.index["pages"].values())
        return {
            "pages": len(pages),
            "conflicts": sum(1 for p in pages if p.get("conflict")),
            "empty_links": len(self.empty_links()),
            "orphans": len(self.orphans()),
        }

    def health(self):
        """体检报告：空链/孤儿/冲突的明细列表（含页面标题），供后台任务播报与面板展示。"""
        pages = list(self.index["pages"].values())
        empties = self.empty_links()      # [(key, target)]
        orph = self.orphans()             # [key]
        conf = self.conflict_pages()      # [key]

        def _title(k):
            m = self.index["pages"].get(k, {})
            return m.get("title", k)

        return {
            "pages": len(pages),
            "empty_links": [{"from": _title(k), "from_key": k, "target": t}
                            for k, t in empties],
            "orphans": [_title(k) for k in orph],
            "conflicts": [_title(k) for k in conf],
            "counts": {
                "pages": len(pages),
                "empty_links": len(empties),
                "orphans": len(orph),
                "conflicts": len(conf),
            },
        }
