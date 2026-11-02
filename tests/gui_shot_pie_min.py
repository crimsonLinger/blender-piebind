"""最小饼菜单对照实验：4 个条目直接写在 self.layout。"""

import os
import tempfile

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
SHOT = os.path.join(OUT, "pie_min.png")


class TMP_MT_pie(bpy.types.Menu):
    bl_idname = "TMP_MT_pie"
    bl_label = "最小测试饼"

    def draw(self, context):
        layout = self.layout
        for index in range(4):
            op = layout.operator("wm.context_toggle", text=f"项 {index + 1}")
            op.data_path = "scene.tool_settings.use_snap"


def shot():
    try:
        bpy.ops.screen.screenshot(filepath=SHOT)
        print("SHOT OK", SHOT, flush=True)
    except Exception as exc:
        print("SHOT FAIL", exc, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def open_menu():
    bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name="TMP_MT_pie")
    bpy.app.timers.register(shot, first_interval=1.5)
    return None


def setup():
    bpy.utils.register_class(TMP_MT_pie)
    bpy.app.timers.register(open_menu, first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)