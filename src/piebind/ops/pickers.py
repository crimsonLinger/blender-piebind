"""选择器：keymap / 操作符 / 饼 的下拉菜单与对应操作符。"""

import bpy

from ..core import config, keymap as ke, keyspec, pies as pie
from .common import WM_PROPS, _on_query_update, _refresh_pie_items


class PIEBIND_OT_pick_operator(bpy.types.Operator):
    bl_idname = "piebind.pick_operator"
    bl_label = "选择操作符"
    bl_options = {"REGISTER", "INTERNAL"}

    idname: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        if not ke.has_operator(self.idname):
            self.report({"ERROR"}, f"操作符不存在：{self.idname}")
            return {"CANCELLED"}
        wm.piebind_op_choice = self.idname
        if not wm.piebind_slot_text:
            wm.piebind_slot_text = ke.operator_label_zh(self.idname)
        return {"FINISHED"}


class PIEBIND_OT_select_keymap(bpy.types.Operator):
    bl_idname = "piebind.select_keymap"
    bl_label = "选择 Keymap"
    bl_options = {"REGISTER", "INTERNAL"}

    identifier: bpy.props.StringProperty()

    def execute(self, context):
        if not self.identifier:
            return {"CANCELLED"}
        context.window_manager.piebind_keymap = self.identifier
        return {"FINISHED"}


class PIEBIND_OT_select_pie(bpy.types.Operator):
    bl_idname = "piebind.select_pie"
    bl_label = "选择饼"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def execute(self, context):
        context.window_manager.piebind_pie = self.pie_id
        return {"FINISHED"}


class PIEBIND_MT_keymaps(bpy.types.Menu):
    bl_label = "选择 Keymap"
    bl_idname = "PIEBIND_MT_keymaps"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        rows = keymap_rows(getattr(wm, "piebind_keymap_query", ""))
        if not rows:
            layout.label(text="没有匹配的 keymap")
            return
        limit = 30
        current = getattr(wm, "piebind_keymap", "")
        for row in rows[:limit]:
            op = layout.operator(
                "piebind.select_keymap",
                text=row["label"],
                icon="CHECKMARK" if row["id"] == current else "DOT",
            )
            op.identifier = row["id"]
        if len(rows) > limit:
            layout.separator()
            layout.label(text=f"还有 {len(rows) - limit} 条，请用上方搜索框缩小范围")


class PIEBIND_MT_pies(bpy.types.Menu):
    bl_label = "选择饼"
    bl_idname = "PIEBIND_MT_pies"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        data = config.load()
        pies = data.get("pies", [])
        if not pies:
            layout.label(text="还没有饼")
            return
        for item in pies:
            op = layout.operator(
                "piebind.select_pie",
                text=item.get("label") or item["id"],
                icon="CHECKMARK" if item["id"] == wm.piebind_pie else "DOT",
            )
            op.pie_id = item["id"]
        layout.separator()
        layout.operator("piebind.delete_pie", text="删除当前饼", icon="X")


class PIEBIND_MT_operators(bpy.types.Menu):
    bl_label = "选择操作符"
    bl_idname = "PIEBIND_MT_operators"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        query = getattr(wm, "piebind_op_query", "")
        hits = ke.search_operators(query, limit=20)
        if not hits:
            layout.label(text=f"没有匹配：{query}" if query else "输入搜索词后打开")
            return
        for idn in hits:
            op = layout.operator(
                "piebind.pick_operator",
                text=f"{ke.operator_label_zh(idn)} ({idn})",
            )
            op.idname = idn
