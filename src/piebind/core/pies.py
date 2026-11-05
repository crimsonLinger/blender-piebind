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

# ------------------------------------------------------------ 按模式切换的变体
MODE_ITEMS = (
    ("", "所有模式"),
    ("OBJECT", "物体模式"),
    ("EDIT", "编辑模式"),
    ("SCULPT", "雕刻模式"),
    ("VERTEX_PAINT", "顶点绘制"),
    ("WEIGHT_PAINT", "权重绘制"),
    ("TEXTURE_PAINT", "纹理绘制"),
    ("POSE", "姿态模式"),
)

_MODE_KEYS = [key for key, _label in MODE_ITEMS]


def normalize_mode(mode):
    """把 context.mode（EDIT_MESH / EDIT_ARMATURE …）归一成 EDIT 这类大类。"""
    text = str(mode or "").upper()
    if text.startswith("EDIT"):
        return "EDIT"
    return text


def mode_label(mode):
    mode = normalize_mode(mode)
    for key, label in MODE_ITEMS:
        if key == mode:
            return label
    return mode or "所有模式"


def slot_for_mode(slot, mode):
    """取当前模式应使用的槽位内容：模式变体优先，否则退回基础槽位。"""
    if not slot:
        return None
    mode = normalize_mode(mode)
    base = {key: value for key, value in slot.items() if key != "variants"}
    if mode:
        for variant in slot.get("variants") or []:
            if normalize_mode(variant.get("mode")) == mode:
                merged = dict(base)
                merged.update({k: v for k, v in variant.items() if k != "mode"})
                # 变体存在但还没填操作符时，同样回落到基础绑定
                if not merged.get("idname"):
                    return base
                return merged
    return base


def variant_for(slot, mode):
    """返回该模式的变体字典（不存在返回 None）。"""
    mode = normalize_mode(mode)
    if not mode:
        return None
    for variant in (slot or {}).get("variants") or []:
        if normalize_mode(variant.get("mode")) == mode:
            return variant
    return None

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
    # 同一槽位可以按模式存多个变体，这里取当前模式对应的那一份
    slot = slot_for_mode(slot, getattr(context, "mode", "")) if slot else None
    if not slot:
        layout.separator()
        return

    kind = slot.get("kind", "operator")
    if kind != "operator":
        layout.label(text=str(slot.get("text") or kind))
        return

    idname = slot.get("idname") or ""
    if not idname:
        layout.separator()
        return
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