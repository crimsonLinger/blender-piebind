"""打开偏好设置并逐个页签重绘，捕捉 draw 期间的异常。"""

import os
import tempfile

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_tabs")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

TABS = ["bindings", "pies", "settings", "health"]


def next_tab(index=0):
    if index >= len(TABS):
        print("TABS DONE", flush=True)
        bpy.ops.wm.quit_blender()
        return None
    tab = TABS[index]
    wm = bpy.context.window_manager
    try:
        wm.piebind_tab = tab
        wm.piebind_show_new = True
        print(f"TAB {tab}", flush=True)
    except Exception as exc:
        print(f"TAB FAIL {tab}: {type(exc).__name__} {exc}", flush=True)
    try:
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
    except Exception as exc:
        print(f"REDRAW FAIL {tab}: {exc}", flush=True)
    bpy.app.timers.register(lambda: next_tab(index + 1), first_interval=0.6)
    return None


def setup():
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default.piebind")
    except Exception as exc:
        print("ENABLE FAIL", exc, flush=True)
    import importlib
    pkg = importlib.import_module("bl_ext.user_default.piebind")
    data = pkg.core.config.default_data()
    pie = pkg.core.config.create_pie(data, "模式饼")
    pkg.core.config.set_slot(data, pie["id"], "W", {
        "kind": "operator", "idname": "object.mode_set", "text": "编辑模式",
        "icon": "NONE", "props": {"mode": "EDIT"},
    })
    pkg.core.config.save(data)
    bpy.context.window_manager.piebind_pie = pie["id"]
    try:
        bpy.ops.preferences.addon_show(module="bl_ext.user_default.piebind")
        print("PREFS SHOWN", flush=True)
    except Exception as exc:
        print("PREFS FAIL", exc, flush=True)
    bpy.app.timers.register(lambda: next_tab(0), first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)