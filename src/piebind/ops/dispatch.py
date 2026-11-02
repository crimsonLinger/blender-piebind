"""按键分发器：执行绑定目标（饼菜单或操作符），并支持侧键按事件反查。"""

import bpy

from ..core import config, keymap as ke, pies as pie
from .common import _dispatch_debug

SIDE_BUTTON_TYPES = ("BUTTON4MOUSE", "BUTTON5MOUSE", "BUTTON6MOUSE", "BUTTON7MOUSE")


def event_key(event):
    """把 Blender 事件转成配置里的 key 结构（只取按压 + 修饰键）。"""
    return {
        "type": event.type,
        "value": "PRESS",
        "ctrl": event.ctrl,
        "shift": event.shift,
        "alt": event.alt,
        "oskey": event.oskey,
        "any": event.alt and event.ctrl and event.shift,
        "key_modifier": "NONE",
    }


def find_binding_for_key(data, key):
    """按组合键查找启用中的绑定（侧键分发用）。"""
    for binding in data.get("bindings", []):
        if not binding.get("enabled", True):
            continue
        if ke.same_combo(binding.get("key") or {}, key):
            return binding
    return None


def _area_allows(context, binding):
    spec = binding.get("keymap") or {}
    space = spec.get("space") or "EMPTY"
    area = context.area
    area_type = area.type if area else None
    if space not in ("EMPTY", ""):
        if area is not None and area.type != space:
            _dispatch_debug(f"area gate rejected: {area_type} != {space}")
            return False
    wanted_area = spec.get("area")
    if wanted_area and area is not None and area.type != wanted_area:
        _dispatch_debug(f"restricted area rejected: {area_type} != {wanted_area}")
        return False
    return True


def run_binding(context, binding, operator=None):
    """执行一个绑定；返回 Blender 操作符结果集合。"""
    if not _area_allows(context, binding):
        return {"CANCELLED"}

    target = binding.get("target") or {}
    if target.get("kind") == "pie":
        pie.PIE_STATE["pie_id"] = target.get("id")
        try:
            return bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie.PIE_MENU_ID)
        except Exception as exc:
            _dispatch_debug(f"pie failed: {exc}")
            if operator is not None:
                operator.report({"ERROR"}, f"饼菜单调用失败：{exc}")
            return {"CANCELLED"}

    idname = target.get("id") or ""
    if not ke.has_operator(idname):
        _dispatch_debug(f"operator missing: {idname}")
        if operator is not None:
            operator.report({"ERROR"}, f"操作符不存在：{idname}")
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
        if operator is not None:
            operator.report({"ERROR"}, f"{idname} 调用失败：{exc}")
        return {"CANCELLED"}
    _dispatch_debug(f"called {idname} -> {result}")
    return {"FINISHED"} if "FINISHED" in result else {"CANCELLED"}


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
        try:
            from . import sidekeys
            sidekeys.ensure_armed()
        except Exception:
            pass
        area_type = context.area.type if context.area else None
        _dispatch_debug(f"enter binding={self.binding_id} area={area_type}")
        data = config.load()
        binding = config.find_binding(data, self.binding_id)
        if not binding or not binding.get("enabled", True):
            _dispatch_debug("missing/disabled binding")
            return {"CANCELLED"}
        return run_binding(context, binding, self)


