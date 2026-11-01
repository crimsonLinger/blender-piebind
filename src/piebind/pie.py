"""饼菜单：单一静态 Menu 类 + 调用态传参。

槽位顺序由 Blender 固定为：西、东、南、北、西北、东北、西南、东南。
空槽必须用 separator() 占位，否则后续条目会前移。
"""

import bpy

from . import config, keymap_engine as ke

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


def _draw_slot(layout, slot, context):
    if not slot:
        layout.separator()
        return

    kind = slot.get("kind", "operator")
    if kind != "operator":
        layout.label(text=str(slot.get("text") or kind))
        return

    idname = slot.get("idname") or ""
    text = slot.get("text") or ke.operator_label(idname)
    icon = slot.get("icon") or "NONE"

    if not ke.has_operator(idname):
        layout.label(text=f"{text}（已失效）", icon="ERROR")
        return
    if not ke.poll_ok(idname):
        layout.label(text=f"{text}（当前上下文不可用）", icon="INFO")
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
        pie = config.find_pie(data, PIE_STATE.get("pie_id"))
        slots = (pie or {}).get("slots") or {}
        for pos in SLOT_ORDER:
            _draw_slot(layout, slots.get(pos), context)