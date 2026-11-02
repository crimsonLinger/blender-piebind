"""按键分发器：按 binding_id 执行饼菜单或操作符。"""

import os

import bpy

from ..core import config, keymap as ke, pies as pie
from .common import _dispatch_debug


class PIEBIND_OT_slot_missing(bpy.types.Operator):
    bl_idname = "piebind.slot_missing"
    bl_label = "槽位不可用"
    bl_options = {"REGISTER", "INTERNAL"}

    slot_text: bpy.props.StringProperty()

    def execute(self, context):
        self.report({"WARNING"}, f"该槽位的操作符已不存在：{self.slot_text}")
        return {"CANCELLED"}


class PIEBIND_OT_dispatch(bpy.types.Operator):
    bl_idname = "piebind.dispatch"
    bl_label = "PieBind Dispatch"
    bl_description = "按绑定的目标执行，并按区域做上下文判断"
    bl_options = {"REGISTER", "INTERNAL"}

    binding_id: bpy.props.StringProperty()

    def execute(self, context):
        area_type = context.area.type if context.area else None
        _dispatch_debug(f"enter binding={self.binding_id} area={area_type}")
        data = config.load()
        binding = config.find_binding(data, self.binding_id)
        if not binding or not binding.get("enabled", True):
            _dispatch_debug("missing/disabled binding")
            return {"CANCELLED"}

        spec = binding.get("keymap") or {}
        space = spec.get("space") or "EMPTY"
        if space not in ("EMPTY", ""):
            area = context.area
            # 窗口级 keymap 被调用时 context.area 可能是 None；此时不做否决，
            # 交由目标操作符自己的 poll 判断（否则绑定会“按了没反应”）。
            if area is not None and area.type != space:
                _dispatch_debug(f"area gate rejected: {area_type} != {space}")
                return {"CANCELLED"}
        wanted_area = spec.get("area")
        if wanted_area and context.area is not None and context.area.type != wanted_area:
            _dispatch_debug(f"restricted area rejected: {area_type} != {wanted_area}")
            return {"CANCELLED"}

        target = binding.get("target") or {}
        if target.get("kind") == "pie":
            pie.PIE_STATE["pie_id"] = target.get("id")
            try:
                return bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie.PIE_MENU_ID)
            except Exception as exc:
                _dispatch_debug(f"pie failed: {exc}")
                self.report({"ERROR"}, f"饼菜单调用失败：{exc}")
                return {"CANCELLED"}

        idname = target.get("id") or ""
        if not ke.has_operator(idname):
            _dispatch_debug(f"operator missing: {idname}")
            self.report({"ERROR"}, f"操作符不存在：{idname}")
            return {"CANCELLED"}
        mod_name, op_name = idname.split(".", 1)
        kwargs = dict(target.get("props") or {})
        op = getattr(getattr(bpy.ops, mod_name), op_name)
        try:
            result = op("INVOKE_DEFAULT", **kwargs)
        except TypeError:
            result = op(**kwargs)
        except Exception as exc:
            _dispatch_debug(f"call failed: {exc}")
            self.report({"ERROR"}, f"{idname} 调用失败：{exc}")
            return {"CANCELLED"}
        _dispatch_debug(f"called {idname} -> {result}")
        return {"FINISHED"} if "FINISHED" in result else {"CANCELLED"}
