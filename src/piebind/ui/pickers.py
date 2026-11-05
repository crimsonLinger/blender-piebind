"""面板选择器：操作符 / Keymap / 饼，以及键位冲突预览。"""

from ..core import config, keymap as ke, keyspec, pies as pie


def operator_picker(layout, wm):
    """搜索框 + 范围（模块前缀）+ 下拉菜单选择操作符（中文优先）。"""
    row = layout.row(align=True)
    row.prop(wm, "piebind_op_query", text="搜索")
    prefix = getattr(wm, "piebind_op_prefix", "")
    row.menu("PIEBIND_MT_op_prefixes", text=f"范围：{ke.prefix_label(prefix)}")
    chosen = getattr(wm, "piebind_op_choice", "")
    if chosen and ke.has_operator(chosen):
        label = f"{ke.operator_label_zh(chosen)}"
        shortcut = ke.shortcut_for(chosen)
        if shortcut:
            label += f"  [{shortcut}]"
    else:
        label = "选择操作符…"
    layout.menu("PIEBIND_MT_operators", text=label, icon="COLLAPSEMENU")


def keymap_picker(layout, wm):
    """Keymap 搜索 + 下拉菜单。"""
    row = layout.row(align=True)
    row.prop(wm, "piebind_keymap_query", text="Keymap 搜索")
    spec = keyspec.split_keymap_identifier(getattr(wm, "piebind_keymap", ""))
    if spec:
        suffix = f" [{spec['space']}]" if spec.get("space") not in ("", "EMPTY") else ""
        label = f"{spec['name']}{suffix}"
    else:
        label = "未选择（默认 3D View）"
    layout.menu("PIEBIND_MT_keymaps", text=label, icon="KEYINGSET")


def pie_picker(layout, wm, data, text=""):
    """饼下拉菜单，返回当前饼数据。"""
    current = config.find_pie(data, getattr(wm, "piebind_pie", ""))
    row = layout.row(align=True)
    row.menu(
        "PIEBIND_MT_pies",
        text=(text + (current["label"] if current else "未选择")),
        icon="MESH_CIRCLE",
    )
    op = row.operator("piebind.delete_pie", text="", icon="X")
    op.pie_id = current["id"] if current else ""
    return current


def conflict_preview(layout, wm, key):
    """新建绑定表单里的键位冲突提示。"""
    if not key:
        return
    spec = keyspec.split_keymap_identifier(getattr(wm, "piebind_keymap", ""))
    occupants = ke.scan_conflict(spec, key) if spec else []
    if not occupants:
        layout.label(text="该键位当前无冲突", icon="CHECKMARK")
        return
    warn = layout.box()
    warn.label(text=f"⚠ 已占用 {len(occupants)} 条：", icon="ERROR")
    for occ in occupants[:4]:
        warn.label(text=f"· {occ['owner']} — {occ['label']}（{occ['layer']}）")
    if not getattr(wm, "piebind_force_override", False):
        warn.label(text="未勾强制覆盖 → 很可能不生效", icon="INFO")