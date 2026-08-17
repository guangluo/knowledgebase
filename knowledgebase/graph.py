"""Wiki 关系图谱（纯数据 + 布局计算，不依赖任何 GUI）。

调用方（如桌面宠物）自行用 Tkinter / web 渲染 nodes/edges。
"""

# 节点配色（供 UI 复用）
CONFLICT_COLOR = "#e74c3c"   # 红：冲突页
SOURCE_COLOR   = "#3498db"   # 蓝：来源页
ORPHAN_COLOR   = "#f1c40f"   # 黄：孤儿页（无反向链接）
NORMAL_COLOR   = "#2ecc71"   # 绿：普通页
EMPTY_OUTLINE  = "#e67e22"   # 橙：虚线，指向不存在页的空链


def build_wiki_graph(index):
    """从 wiki index 构建图谱数据：
    返回 (nodes, edges, empty_link_sources)。
      nodes:            {key: meta}
      edges:            [(from_key, to_key_or_target, dangling)]
      empty_link_sources: 指向不存在页面的源 key 集合（用于高亮）"""
    pages = index.get("pages", {})
    nodes = dict(pages)
    edges = []
    empty_link_sources = set()
    by_slug = {m.get("slug"): k for k, m in pages.items()}
    by_title = {m.get("title"): k for k, m in pages.items()}
    for key, meta in pages.items():
        for ln in meta.get("links", []):
            tgt = by_slug.get(ln) or by_title.get(ln)
            if tgt:
                edges.append((key, tgt, False))
            else:
                edges.append((key, ln, True))
                empty_link_sources.add(key)
    return nodes, edges, empty_link_sources


def wiki_node_color(key, meta, orphan_keys, conflict_keys):
    """节点配色：冲突 > 来源 > 孤儿 > 普通。"""
    if key in conflict_keys or meta.get("conflict"):
        return CONFLICT_COLOR
    if meta.get("category") == "sources":
        return SOURCE_COLOR
    if key in orphan_keys:
        return ORPHAN_COLOR
    return NORMAL_COLOR


def _short_label(text, n=6):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n] + "…"


def _graph_layout_step(nodes, edges, w, h, repulse=1400.0, spring=0.03, damp=0.82):
    """一步力导向：节点间库仑斥力 + 真实边的弹簧引力；就地更新 x/y/vx/vy，
    并约束在画布 [20, w-20]×[20, h-20] 内。nodes 值为含 x/y/vx/vy 的 dict。"""
    keys = list(nodes.keys())
    n = len(keys)
    for i in range(n):
        a = nodes[keys[i]]
        fx = fy = 0.0
        for j in range(n):
            if i == j:
                continue
            b = nodes[keys[j]]
            dx = a["x"] - b["x"]
            dy = a["y"] - b["y"]
            d2 = dx * dx + dy * dy
            if d2 < 0.01:
                d2 = 0.01
            f = repulse / d2
            d = d2 ** 0.5
            fx += f * dx / d
            fy += f * dy / d
        a["vx"] = (a["vx"] + fx) * damp
        a["vy"] = (a["vy"] + fy) * damp
    for (a_key, b_key, dangling) in edges:
        if dangling:
            continue
        a = nodes.get(a_key)
        b = nodes.get(b_key)
        if not a or not b:
            continue
        dx = b["x"] - a["x"]
        dy = b["y"] - a["y"]
        a["vx"] += dx * spring
        a["vy"] += dy * spring
        b["vx"] -= dx * spring
        b["vy"] -= dy * spring
    # 约束在画布内
    for k in keys:
        nd = nodes[k]
        nd["x"] = max(20.0, min(w - 20.0, nd["x"] + nd["vx"]))
        nd["y"] = max(20.0, min(h - 20.0, nd["y"] + nd["vy"]))
