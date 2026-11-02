"""饼菜单排布测试：4 个不同操作符。"""

import os
import tempfile

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
SHOT = os.path.join(OUT, "pie_distinct.png")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_piedistinct")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)


def shot():
    try:
        bpy.ops.screen.screenshot(filepath=SHOT)
        print("SHOT OK", SHOT, flush=True)
    except Exception as exc:
        print("SHOT FAIL", exc, flush=True)
    bpy.ops.wm.quit_blender()
    return None


def open_pie():
    import importlib
    pkg = importlib.import_module("bl_ext.user_default.piebind")
    data = pkg.config.load()
    pie = data["pies"][0]
    print("SLOTS", sorted(pie["slots"]), flush=True)
    bpy.ops.piebind.call_pie("INVOKE_DEFAULT", pie_id=pie["id"])
    bpy.app.timers.register(shot, first_interval=1.5)
    return None


def setup():
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.piebind")
    import importlib
    pkg = importlib.import_module("bl_ext.user_default.piebind")
    data = pkg.config.default_data()
    pie = pkg.config.create_pie(data, "四向饼")
    for pos, idn, text in (
        ("W", "object.shade_smooth", "平滑"),
        ("E", "object.duplicate", "复制"),
        ("N", "object.origin_set", "原点"),
        ("S", "object.delete", "删除"),
    ):
        pkg.config.set_slot(data, pie["id"], pos, {
            "kind": "operator", "idname": idn, "text": text, "icon": "NONE", "props": {},
        })
    pkg.config.save(data)
    bpy.context.window_manager.piebind_pie = pie["id"]
    bpy.app.timers.register(open_pie, first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)