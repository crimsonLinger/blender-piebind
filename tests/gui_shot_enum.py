"""用弹出菜单渲染枚举控件并截图，核对标签显示。"""

import os
import tempfile

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
SHOT = os.path.join(OUT, "enum_menu.png")


class TMP_MT_enum(bpy.types.Menu):
    bl_label = "Enum Render Test"
    bl_idname = "TMP_MT_enum"

    def draw(self, context):
        col = self.layout.column()
        col.label(text="operator enum:")
        col.prop(context.window_manager, "piebind_op_choice", text="")
        col.label(text="keymap enum:")
        col.prop(context.window_manager, "piebind_keymap", text="")
        col.label(text="dummy operator list:")
        col.label(text="Bake Keyframes  ·  action.bake_keys")
        col.label(text="Bake Keyframes - action.bake_keys")
        col.label(text="中文对照：倒角 / 烘焙 / 顶点")


def shot():
    try:
        bpy.ops.screen.screenshot(filepath=SHOT)
        print("SHOT OK", SHOT, flush=True)
    except Exception as exc:
        print("SHOT FAIL", exc, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def setup():
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default.piebind")
    except Exception as exc:
        print("ENABLE FAIL", exc, flush=True)
    bpy.utils.register_class(TMP_MT_enum)
    try:
        bpy.context.window_manager.piebind_op_choice = "action.bake_keys"
    except Exception as exc:
        print("SET FAIL", exc, flush=True)
    bpy.app.timers.register(open_menu, first_interval=1.5)
    return None


def open_menu():
    try:
        bpy.ops.wm.call_menu("INVOKE_DEFAULT", name="TMP_MT_enum")
    except Exception as exc:
        print("MENU FAIL", exc, flush=True)
    bpy.app.timers.register(shot, first_interval=2.0)
    return None


bpy.app.timers.register(setup, first_interval=1.2)