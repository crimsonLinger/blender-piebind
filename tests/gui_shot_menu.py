"""渲染饼菜单下拉，用于核对显示。"""

import os
import tempfile

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
SHOT = os.path.join(OUT, "menu_pies.png")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_menushot")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)


def shot():
    try:
        bpy.ops.screen.screenshot(filepath=SHOT)
        print("SHOT OK", SHOT, flush=True)
    except Exception as exc:
        print("SHOT FAIL", exc, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def open_menu():
    try:
        bpy.ops.wm.call_menu("INVOKE_DEFAULT", name="PIEBIND_MT_pies")
    except Exception as exc:
        print("MENU FAIL", exc, flush=True)
    bpy.app.timers.register(shot, first_interval=1.8)
    return None


def setup():
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default.piebind")
    except Exception as exc:
        print("ENABLE FAIL", exc, flush=True)
    import importlib
    pkg = importlib.import_module("bl_ext.user_default.piebind")
    data = pkg.config.default_data()
    for name in ("模式", "建模速取", "材质", "对齐"):
        pkg.config.create_pie(data, name)
    pkg.config.save(data)
    wm = bpy.context.window_manager
    wm.piebind_pie = data["pies"][0]["id"]
    bpy.app.timers.register(open_menu, first_interval=1.6)
    return None


bpy.app.timers.register(setup, first_interval=1.2)