"""饼菜单与槽位的增删改、预览。"""

import json

import bpy

from ..core import config, keymap as ke, pies as pie
from .common import ICON_ITEMS, WM_PROPS, flush_pending_save, load_slot_into_form


def operator_property_names(idname):
    """该操作符可写属性的名字集合；取不到时返回空集合（= 不做校验）。"""
    if not idname or "." not in idname:
        return set()
    mod_name, op_name = idname.split(".", 1)
    try:
        rna = getattr(getattr(bpy.ops, mod_name), op_name).get_rna_type()
    except Exception:
        return set()
    names = set()
    for prop in rna.properties:
        if prop.identifier == "rna_type" or getattr(prop, "is_readonly", False):
            continue
        names.add(prop.identifier)
    return names


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
        load_slot_into_form(wm, pie_id=created["id"])
        wm.piebind_status = f"已创建饼：{created['label']}"
        return {"FINISHED"}


class PIEBIND_OT_rename_pie(bpy.types.Operator):
    bl_idname = "piebind.rename_pie"
    bl_label = "重命名饼"
    bl_description = "给选中的饼菜单改名"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()
    label: bpy.props.StringProperty(name="名称")

    def invoke(self, context, event):
        wm = context.window_manager
        pie_id = self.pie_id or getattr(wm, "piebind_pie", "")
        found = config.find_pie(config.load(), pie_id)
        if found is None:
            self.report({"ERROR"}, "请先选择一个饼")
            return {"CANCELLED"}
        self.pie_id = pie_id
        self.label = found.get("label") or ""
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        self.layout.prop(self, "label", text="名称")
        self.layout.label(text="留空则保持原名；改名后立即写入配置。", icon="INFO")

    def execute(self, context):
        wm = context.window_manager
        data = config.load()
        found = config.rename_pie(data, self.pie_id, self.label)
        if found is None:
            self.report({"ERROR"}, "饼不存在（可能已被删除）")
            return {"CANCELLED"}
        config.save(data)
        wm.piebind_status = f"已改名为：{found['label']}"
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

        if not ke.has_operator(idname):
            self.report({"ERROR"}, f"操作符不存在：{idname or '（未选择）'}")
            return {"CANCELLED"}

        # 丢掉不属于该操作符的参数（旧预设串台会让调用直接报 TypeError）
        allowed = operator_property_names(idname)
        if allowed:
            dropped = sorted(k for k in props if k not in allowed)
            for key in dropped:
                props.pop(key, None)
            if dropped:
                self.report({"WARNING"}, f"已忽略不适用于 {idname} 的参数：{'、'.join(dropped)}")

        slot = {
            "kind": "operator",
            "idname": idname,
            "text": wm.piebind_slot_text or ke.operator_label_zh(idname),
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
        load_slot_into_form(context.window_manager, pie_id=self.pie_id, pos=self.pos)
        return {"FINISHED"}


class PIEBIND_OT_select_slot(bpy.types.Operator):
    bl_idname = "piebind.select_slot"
    bl_label = "选择槽位"
    bl_options = {"REGISTER", "INTERNAL"}

    pos: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        flush_pending_save(wm)
        wm.piebind_edit_mode = ""
        wm.piebind_slot_pos = self.pos
        # 值没变时枚举的 update 回调不会触发，这里再显式读一次
        load_slot_into_form(wm, pos=self.pos)
        return {"FINISHED"}


class PIEBIND_OT_select_edit_mode(bpy.types.Operator):
    bl_idname = "piebind.select_edit_mode"
    bl_label = "切换模式变体"
    bl_description = "切到该模式的变体进行编辑（没有则新建一份）"
    bl_options = {"REGISTER", "INTERNAL"}

    mode: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        flush_pending_save(wm)
        wm.piebind_edit_mode = self.mode
        load_slot_into_form(wm)
        return {"FINISHED"}


class PIEBIND_OT_remove_edit_variant(bpy.types.Operator):
    bl_idname = "piebind.remove_edit_variant"
    bl_label = "删除该模式变体"
    bl_description = "删除当前模式的变体，回落到「所有模式」的基础绑定"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        mode = pie.normalize_mode(getattr(wm, "piebind_edit_mode", ""))
        if not mode:
            return {"CANCELLED"}
        data = config.load()
        pie_id = getattr(wm, "piebind_pie", "")
        pos = getattr(wm, "piebind_slot_pos", "N")
        pie_data = config.find_pie(data, pie_id)
        slot = ((pie_data or {}).get("slots") or {}).get(pos)
        if not slot:
            return {"CANCELLED"}
        variants = [
            variant for variant in (slot.get("variants") or [])
            if pie.normalize_mode(variant.get("mode")) != mode
        ]
        if variants:
            slot["variants"] = variants
        else:
            slot.pop("variants", None)
        config.set_slot(data, pie_id, pos, slot)
        config.save(data)
        wm.piebind_edit_mode = ""
        load_slot_into_form(wm)
        wm.piebind_status = f"已删除 {pie.mode_label(mode)} 变体"
        return {"FINISHED"}


class PIEBIND_OT_load_slot(bpy.types.Operator):
    bl_idname = "piebind.load_slot"
    bl_label = "载入槽位内容"
    bl_description = "把当前槽位已有的功能与参数读回编辑区"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        has_content = load_slot_into_form(context.window_manager)
        if not has_content:
            self.report({"INFO"}, "该槽位是空的")
        return {"FINISHED"}


class PIEBIND_OT_test_pie(bpy.types.Operator):
    bl_idname = "piebind.test_pie"
    bl_label = "预览饼"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def invoke(self, context, event):
        if bpy.app.background:
            self.report({"ERROR"}, "后台模式下无法预览饼菜单")
            return {"CANCELLED"}
        pie.PIE_STATE["pie_id"] = self.pie_id
        return bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie.PIE_MENU_ID)


class PIEBIND_OT_call_pie(bpy.types.Operator):
    bl_idname = "piebind.call_pie"
    bl_label = "调用饼菜单"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def invoke(self, context, event):
        if bpy.app.background:
            self.report({"ERROR"}, "后台模式下无法打开饼菜单")
            return {"CANCELLED"}
        pie.PIE_STATE["pie_id"] = self.pie_id
        try:
            return bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie.PIE_MENU_ID)
        except Exception as exc:
            self.report({"ERROR"}, f"调用饼菜单失败：{exc}")
            return {"CANCELLED"}

    def execute(self, context):
        return self.invoke(context, None)


class PIEBIND_OT_add_sub_item(bpy.types.Operator):
    bl_idname = "piebind.add_sub_item"
    bl_label = "加入子项"
    bl_description = "把编辑区当前的操作符（含参数）加入该槽位的子菜单"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        flush_pending_save(wm)
        idname = getattr(wm, "piebind_op_choice", "")
        if not idname or not ke.has_operator(idname):
            self.report({"INFO"}, "先在编辑区选一个操作符")
            return {"CANCELLED"}
        pie_id = getattr(wm, "piebind_pie", "")
        pos = getattr(wm, "piebind_slot_pos", "N")
        data = config.load()
        pie_data = config.find_pie(data, pie_id)
        if pie_data is None:
            return {"CANCELLED"}
        slot = dict((pie_data.get("slots") or {}).get(pos) or {})
        props = {}
        raw = (getattr(wm, "piebind_slot_props", "") or "").strip()
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                props = parsed
        child = {
            "idname": idname,
            "text": (getattr(wm, "piebind_slot_text", "") or "").strip()
            or ke.operator_label_zh(idname),
            "props": props,
        }
        children = list(slot.get("children") or [])
        children.append(child)
        slot["kind"] = "menu"
        slot["children"] = children
        if not slot.get("idname"):
            slot["idname"] = idname
        config.set_slot(data, pie_id, pos, slot)
        config.save(data)
        wm.piebind_status = f"子项已加入（{len(children)}）"
        return {"FINISHED"}


class PIEBIND_OT_remove_sub_item(bpy.types.Operator):
    bl_idname = "piebind.remove_sub_item"
    bl_label = "移除子项"
    bl_options = {"REGISTER", "INTERNAL"}

    index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        wm = context.window_manager
        flush_pending_save(wm)
        pie_id = getattr(wm, "piebind_pie", "")
        pos = getattr(wm, "piebind_slot_pos", "N")
        data = config.load()
        pie_data = config.find_pie(data, pie_id)
        if pie_data is None:
            return {"CANCELLED"}
        slot = dict((pie_data.get("slots") or {}).get(pos) or {})
        children = list(slot.get("children") or [])
        if not (0 <= self.index < len(children)):
            return {"CANCELLED"}
        children.pop(self.index)
        if children:
            slot["children"] = children
        else:
            slot.pop("children", None)
            slot["kind"] = "operator"
        config.set_slot(data, pie_id, pos, slot)
        config.save(data)
        wm.piebind_status = f"已移除子项（剩 {len(children)}）"
        return {"FINISHED"}
