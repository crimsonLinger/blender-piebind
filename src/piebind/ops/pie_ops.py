"""饼菜单与槽位的增删改、预览。"""

import json

import bpy

from ..core import config, keymap as ke, pies as pie
from .common import ICON_ITEMS, MODE_ITEMS, WM_PROPS


class PIEBIND_OT_create_pie(bpy.types.Operator):
    bl_idname = "piebind.create_pie"
    bl_label = "新建饼"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        data = config.load()
        created = config.create_pie(data, wm.piebind_new_pie_label or "新建饼")
        config.save(data)
        wm.piebind_pie = created["id"]
        wm.piebind_status = f"已创建饼：{created['label']}"
        return {"FINISHED"}


class PIEBIND_OT_delete_pie(bpy.types.Operator):
    bl_idname = "piebind.delete_pie"
    bl_label = "删除饼"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        pie_id = self.pie_id or getattr(wm, "piebind_pie", "")
        data = config.load()
        pie_data = config.find_pie(data, pie_id)
        if pie_data is None:
            self.report({"ERROR"}, "请先选择一个饼")
            return {"CANCELLED"}
        config.delete_pie(data, pie_id)
        config.save(data)
        wm.piebind_pie = ""
        ke.apply(config.load())
        self.report({"INFO"}, f"已删除饼：{pie_data.get('label', pie_id)}")
        return {"FINISHED"}


class PIEBIND_OT_add_slot(bpy.types.Operator):
    bl_idname = "piebind.add_slot"
    bl_label = "写入槽位"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        pie_id = wm.piebind_pie
        idname = wm.piebind_op_choice
        data = config.load()
        if not config.find_pie(data, pie_id):
            self.report({"ERROR"}, "请先选择饼")
            return {"CANCELLED"}

        props = {}
        raw = (wm.piebind_slot_props or "").strip()
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    props.update(parsed)
                else:
                    raise ValueError("需要 JSON 对象")
            except Exception as exc:
                self.report({"ERROR"}, f"属性 JSON 无效：{exc}")
                return {"CANCELLED"}

        mode = getattr(wm, "piebind_slot_mode", "AUTO")
        default_text = ke.operator_label_zh(idname)
        if mode and mode != "AUTO":
            idname = "object.mode_set"
            props["mode"] = mode
            default_text = {key: label for key, label, _desc in MODE_ITEMS}.get(mode, mode)

        if not ke.has_operator(idname):
            self.report({"ERROR"}, f"操作符不存在：{idname}")
            return {"CANCELLED"}
        slot = {
            "kind": "operator",
            "idname": idname,
            "text": wm.piebind_slot_text or default_text,
            "icon": wm.piebind_slot_icon or "NONE",
            "props": props,
        }
        config.set_slot(data, pie_id, wm.piebind_slot_pos, slot)
        config.save(data)
        wm.piebind_status = f"已写入槽位 {wm.piebind_slot_pos}：{idname}"
        return {"FINISHED"}


class PIEBIND_OT_remove_slot(bpy.types.Operator):
    bl_idname = "piebind.remove_slot"
    bl_label = "清空槽位"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()
    pos: bpy.props.StringProperty()

    def execute(self, context):
        data = config.load()
        config.set_slot(data, self.pie_id, self.pos, None)
        config.save(data)
        return {"FINISHED"}


class PIEBIND_OT_select_slot(bpy.types.Operator):
    bl_idname = "piebind.select_slot"
    bl_label = "选择槽位"
    bl_options = {"REGISTER", "INTERNAL"}

    pos: bpy.props.StringProperty()

    def execute(self, context):
        context.window_manager.piebind_slot_pos = self.pos
        return {"FINISHED"}


class PIEBIND_OT_test_pie(bpy.types.Operator):
    bl_idname = "piebind.test_pie"
    bl_label = "预览饼"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def invoke(self, context, event):
        pie.PIE_STATE["pie_id"] = self.pie_id
        return bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie.PIE_MENU_ID)


class PIEBIND_OT_call_pie(bpy.types.Operator):
    bl_idname = "piebind.call_pie"
    bl_label = "调用饼菜单"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def invoke(self, context, event):
        pie.PIE_STATE["pie_id"] = self.pie_id
        try:
            return bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie.PIE_MENU_ID)
        except Exception as exc:
            self.report({"ERROR"}, f"调用饼菜单失败：{exc}")
            return {"CANCELLED"}

    def execute(self, context):
        return self.invoke(context, None)
