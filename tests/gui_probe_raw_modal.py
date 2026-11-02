"""原样记录模态收到的鼠标事件，用于确认侧键能否到达 Blender。"""

import os
import tempfile

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
LOG = os.path.join(OUT, "raw_modal.log")


class TMP_OT_raw(bpy.types.Operator):
    bl_idname = "tmp.raw"
    bl_label = "raw modal"

    def invoke(self, context, event):
        with open(LOG, "w", encoding="utf-8") as fh:
            fh.write("START\n")
        context.window_manager.modal_handler_add(self)
        bpy.app.timers.register(self.stop, first_interval=8.0)
        return {"RUNNING_MODAL"}

    def stop(self):
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("STOP\n")
        bpy.ops.wm.quit_blender()
        return None

    def modal(self, context, event):
        if "MOUSE" in event.type or "WHEEL" in event.type or event.type.startswith("BUTTON"):
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write(f"{event.type}/{event.value}\n")
        return {"RUNNING_MODAL"}


def setup():
    bpy.utils.register_class(TMP_OT_raw)
    bpy.ops.tmp.raw("INVOKE_DEFAULT")
    print("RAW_STARTED", flush=True)
    return None


bpy.app.timers.register(setup, first_interval=2.0)