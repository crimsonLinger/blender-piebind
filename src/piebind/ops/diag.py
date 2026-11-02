"""诊断导出与复制。"""

import json
import os

import bpy
from bpy_extras.io_utils import ExportHelper

from .. import diagnostics
from ..core import config, keymap as ke


class PIEBIND_OT_export_diagnostics(bpy.types.Operator, ExportHelper):
    bl_idname = "piebind.export_diagnostics"
    bl_label = "导出诊断 JSON"
    bl_description = "导出环境与键位快照，便于在 issue 里排查（本地路径已脱敏）"
    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            with open(self.filepath, "w", encoding="utf-8") as fh:
                fh.write(diagnostics.dumps())
        except Exception as exc:
            self.report({"ERROR"}, f"导出失败：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"诊断已导出：{self.filepath}")
        return {"FINISHED"}


class PIEBIND_OT_copy_diagnostics(bpy.types.Operator):
    bl_idname = "piebind.copy_diagnostics"
    bl_label = "复制诊断到剪贴板"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        try:
            text = diagnostics.dumps()
            context.window_manager.clipboard = text
        except Exception as exc:
            self.report({"ERROR"}, f"复制失败：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已复制 {len(text)} 字符的诊断信息")
        return {"FINISHED"}
