"""参数预设：菜单类 + 把预设写入「属性 JSON」的操作符。"""

import json

import bpy

from ..core import keymap as ke, presets


class PIEBIND_OT_apply_slot_preset(bpy.types.Operator):
    bl_idname = "piebind.apply_slot_preset"
    bl_label = "应用参数预设"
    bl_description = "把选中的参数预设写入槽位的「属性 JSON」"
    bl_options = {"REGISTER", "INTERNAL"}

    # 注意：属性不能叫 idname / text —— 会和 OperatorProperties 自带字段撞名
    op_id: bpy.props.StringProperty()
    props_json: bpy.props.StringProperty()
    slot_text: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        idname = self.op_id or getattr(wm, "piebind_op_choice", "")
        if not idname or not ke.has_operator(idname):
            self.report({"ERROR"}, f"操作符不存在：{idname}")
            return {"CANCELLED"}
        try:
            payload = json.loads(self.props_json or "{}")
            if not isinstance(payload, dict):
                raise ValueError("需要 JSON 对象")
        except Exception as exc:
            self.report({"ERROR"}, f"预设数据无效：{exc}")
            return {"CANCELLED"}

        wm.piebind_op_choice = idname
        wm.piebind_slot_props = json.dumps(payload, ensure_ascii=False) if payload else ""

        current = (getattr(wm, "piebind_slot_text", "") or "").strip()
        autofilled = {idname}
        try:
            autofilled.add(ke.operator_label_zh(idname))
            autofilled.add(ke.operator_label(idname))
        except Exception:
            pass
        if not current or current in autofilled:
            wm.piebind_slot_text = self.slot_text

        wm.piebind_status = f"参数预设已填入：{self.slot_text or idname}"
        return {"FINISHED"}


class PIEBIND_MT_slot_presets(bpy.types.Menu):
    bl_idname = "PIEBIND_MT_slot_presets"
    bl_label = "参数预设"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        idname = getattr(wm, "piebind_op_choice", "")
        if not idname:
            layout.label(text="先在上面选一个操作符", icon="INFO")
            return
        rows = presets.presets_for(idname)
        if not rows:
            layout.label(text=f"{idname} 没有可选参数", icon="INFO")
            layout.label(text="可以直接在下方手填 JSON")
            return

        current = (getattr(wm, "piebind_slot_props", "") or "").replace(" ", "")
        for row in rows[:40]:
            payload = json.dumps(row["props"], ensure_ascii=False)
            selected = bool(current) and current == payload.replace(" ", "")
            op = layout.operator(
                "piebind.apply_slot_preset",
                text=row["label"],
                icon="CHECKMARK" if selected else "DOT",
            )
            op.op_id = idname
            op.props_json = payload
            op.slot_text = row["text"]
        if len(rows) > 40:
            layout.separator()
            layout.label(text=f"还有 {len(rows) - 40} 项，可用下方 JSON 手填")


CLASSES = (
    PIEBIND_MT_slot_presets,
    PIEBIND_OT_apply_slot_preset,
)