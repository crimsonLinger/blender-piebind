"""默认值与配置文件相关操作。"""

import bpy

from ..core import config


def apply_form_defaults(wm):
    """把 config.settings 里的默认值应用到「新建绑定」表单（仅首次）。"""
    if getattr(wm, "piebind_form_ready", False):
        return
    data = config.load()
    block = config.settings(data)
    try:
        wm.piebind_keymap = block.get("default_keymap") or ""
        wm.piebind_force_override = bool(block.get("force_override", False))
        wm.piebind_restrict_view3d = bool(block.get("restrict_view3d", True))
        wm.piebind_form_ready = True
    except Exception:
        pass


class PIEBIND_OT_save_defaults(bpy.types.Operator):
    bl_idname = "piebind.save_defaults"
    bl_label = "保存当前表单为默认值"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        data = config.load()
        block = config.settings(data)
        block["default_keymap"] = getattr(wm, "piebind_keymap", "")
        block["force_override"] = bool(getattr(wm, "piebind_force_override", False))
        block["restrict_view3d"] = bool(getattr(wm, "piebind_restrict_view3d", False))
        config.save(data)
        wm.piebind_status = "默认值已保存到配置"
        return {"FINISHED"}


class PIEBIND_OT_load_defaults(bpy.types.Operator):
    bl_idname = "piebind.load_defaults"
    bl_label = "载入默认值到表单"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        block = config.settings(config.load())
        wm.piebind_keymap = block.get("default_keymap") or ""
        wm.piebind_force_override = bool(block.get("force_override", False))
        wm.piebind_restrict_view3d = bool(block.get("restrict_view3d", True))
        wm.piebind_status = "已载入默认值"
        return {"FINISHED"}


class PIEBIND_OT_open_config_dir(bpy.types.Operator):
    bl_idname = "piebind.open_config_dir"
    bl_label = "打开配置目录"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        try:
            bpy.ops.wm.path_open(filepath=config.config_dir())
        except Exception as exc:
            self.report({"ERROR"}, f"打不开目录：{exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


CLASSES = (
    PIEBIND_OT_save_defaults,
    PIEBIND_OT_load_defaults,
    PIEBIND_OT_open_config_dir,
)