"""配置导入导出与体检刷新。"""

import json

import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..core import config, keymap as ke


class PIEBIND_OT_export_config(bpy.types.Operator, ExportHelper):
    bl_idname = "piebind.export_config"
    bl_label = "导出配置"
    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            with open(self.filepath, "w", encoding="utf-8") as fh:
                json.dump(config.load(), fh, ensure_ascii=False, indent=1)
        except Exception as exc:
            self.report({"ERROR"}, f"导出失败：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已导出：{self.filepath}")
        return {"FINISHED"}


class PIEBIND_OT_import_config(bpy.types.Operator, ImportHelper):
    bl_idname = "piebind.import_config"
    bl_label = "导入配置"
    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            with open(self.filepath, "r", encoding="utf-8") as fh:
                data = config._coerce(json.load(fh))
            config.save(data)
            ke.apply(data)
        except Exception as exc:
            self.report({"ERROR"}, f"导入失败：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已导入：{self.filepath}")
        return {"FINISHED"}


class PIEBIND_OT_refresh_health(bpy.types.Operator):
    bl_idname = "piebind.refresh_health"
    bl_label = "重新扫描"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        ke.invalidate_cache()
        context.window_manager.piebind_status = "已重新扫描本机键位"
        return {"FINISHED"}


CLASSES = (
    PIEBIND_OT_export_config,
    PIEBIND_OT_import_config,
    PIEBIND_OT_refresh_health,
)