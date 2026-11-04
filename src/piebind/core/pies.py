"""饼菜单：单一静态 Menu 类 + 调用态传参。

槽位顺序由 Blender 固定为：西、东、南、北、西北、东北、西南、东南。
空槽必须用 separator() 占位，否则后续条目会前移。
"""

import os

import bpy

from . import config, keymap as ke

PIE_MENU_ID = "PIEBIND_MT_pie"

SLOT_ORDER = ("W", "E", "S", "N", "NW", "NE", "SW", "SE")

SLOT_LABELS = {
    "W": "西 (左)",
    "E": "东 (右)",
    "S": "南 (下)",
    "N": "北 (上)",
    "NW": "西北 (左上)",
    "NE": "东北 (右上)",
    "SW": "西南 (左下)",
    "SE": "东南 (右下)",
}

# 当前要绘制的饼（由 piebind.call_pie 在调用前写入）
PIE_STATE = {"pie_id": None}

_ICON_CACHE = {"set": None}


def valid_icons():
    """Blender 图标枚举（缓存）；取不到时返回空集合，表示不校验。"""
    cached = _ICON_CACHE["set"]
    if cached is None:
        try:
            items = bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items
            cached = {item.identifier for item in items}
        except Exception:
            cached = set()
        _ICON_CACHE["set"] = cached
    return cached


def safe_icon(icon):
    """老配置里可能残留已失效的图标名，绘制前兜底成 NONE。"""
    icon = icon or "NONE"
    known = valid_icons()
    if known and icon not in known:
        return "NONE"
    return icon


def _draw_slot(layout, slot, context):
    if not slot:
        layout.separator()
        return

    kind = slot.get("kind", "operator")
    if kind != "operator":
        layout.label(text=str(slot.get("text") or kind))
        return

    idname = slot.get("idname") or ""
    text = slot.get("text") or ke.operator_label_zh(idname)
    icon = safe_icon(slot.get("icon"))

    # 注意：饼菜单里 layout.label() 不占一个饼位，会把后面的条目挤到一起。
    # 所以无论可用与否都用操作符占位；poll 不通过的由 Blender 自动置灰。
    if not ke.has_operator(idname):
        op = layout.operator("piebind.slot_missing", text=f"{text}（已失效）", icon="ERROR")
        op.slot_text = text
        return

    op = layout.operator(idname, text=text, icon=icon)
    for prop, value in (slot.get("props") or {}).items():
        try:
            setattr(op, prop, value)
        except Exception:
            continue


class PIEBIND_MT_pie(bpy.types.Menu):
    bl_idname = PIE_MENU_ID
    bl_label = "PieBind"

    def draw(self, context):
        layout = self.layout
        data = config.load()
        pie_data = config.find_pie(data, PIE_STATE.get("pie_id"))
        slots = (pie_data or {}).get("slots") or {}
        debug = os.environ.get("PIEBIND_DEBUG_PIE")
        # 关键：饼菜单必须用 layout.menu_pie() 创建饼布局，
        # 直接往 self.layout 里加条目会被排成一列（所有选项挤在中心）。
        pie = layout.menu_pie()
        if not any(slots.get(pos) for pos in SLOT_ORDER):
            pie.label(text="（这个饼还没有内容）", icon="INFO")
            return
        for pos in SLOT_ORDER:
            slot = slots.get(pos)
            if debug:
                try:
                    with open(debug, "a", encoding="utf-8") as fh:
                        fh.write(f"SLOT {pos} {'empty' if not slot else slot.get('idname')}\n")
                except Exception:
                    pass
            _draw_slot(pie, slot, context)