"""面板通用小部件：冲突徽标、目标名、罗盘、体检页。"""

from collections import Counter

import bpy

from ..core import config, keymap as ke, pies as pie

SEVERITY_ICON = {"blocker": "ERROR", "warning": "INFO"}


def target_label(data, binding):
    target = binding.get("target") or {}
    if target.get("kind") == "pie":
        found = config.find_pie(data, target.get("id"))
        return f"饼：{found['label'] if found else '(已删除)'}"
    return ke.operator_label(target.get("id") or "")


def conflict_of(binding):
    if not binding.get("enabled", True):
        return []
    try:
        return ke.scan_conflict(binding.get("keymap") or {}, binding.get("key") or {})
    except Exception:
        return []


def worst(occupants):
    for level in ("blocker", "warning"):
        if any(o["severity"] == level for o in occupants):
            return level
    return ""


def slot_summary(slot):
    if not slot:
        return "—"
    return (slot.get("text") or ke.operator_label(slot.get("idname", "")) or "?")[:8]


def draw_compass(layout, wm, pie_data):
    """3x3 罗盘：点击方位即选中该槽。"""
    slots = (pie_data or {}).get("slots") or {}
    selected = wm.piebind_slot_pos
    grid = layout.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True, align=True)
    order = ("NW", "N", "NE", "W", None, "E", "SW", "S", "SE")
    for pos in order:
        if pos is None:
            center = grid.box()
            center.label(text=(pie_data or {}).get("label", "（饼）")[:10], icon="MESH_CIRCLE")
            center.label(text="点击方位选槽")
            continue
        cell = grid.column(align=True)
        cell.scale_y = 0.9
        op = cell.operator(
            "piebind.select_slot",
            text=f"{pos} {slot_summary(slots.get(pos))}",
            depress=(pos == selected),
        )
        op.pos = pos


def draw_health(layout, data):
    rows = ke.scan_all_plugin_bindings()
    own = data.get("bindings", [])
    own_keys = set()
    for binding in own:
        if not binding.get("enabled", True):
            continue
        spec = binding.get("keymap") or {}
        own_keys.add((spec.get("name"), spec.get("space"), ke.key_label(binding.get("key") or {})))

    box = layout.box()
    header = box.row(align=True)
    header.label(text=f"本机插件键位（{len(rows)} 条）", icon="PRESET")
    header.operator("piebind.refresh_health", text="", icon="FILE_REFRESH")

    if not rows:
        box.label(text="未检测到插件注册的键位")
        return

    owners = Counter(r["owner"] for r in rows)
    box.label(text="来源：" + "、".join(f"{k}×{v}" for k, v in owners.most_common(6)))

    overlap = 0
    for row in rows[:24]:
        hit = (row["keymap"], row["space"], row["key"]) in own_keys
        if hit:
            overlap += 1
        line = box.row(align=True)
        if hit:
            line.label(text="⚠", icon="ERROR")
        line.label(text=row["key"])
        line.label(text=row["keymap"])
        line.label(text=row["owner"])
    if overlap:
        box.label(text=f"其中 {overlap} 条与你的绑定同键", icon="ERROR")