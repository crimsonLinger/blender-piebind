"""渲染饼菜单本体，核对槽位分布。"""

import os
import tempfile

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
SHOT = os.path.join(OUT, "pie_body.png")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_piebody")
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
    pie = data["pies"][0] if data.get("pies") else None
    print("PIE", pie["id"] if pie else None, "SLOTS", sorted((pie or {}).get("slots", {})), flush=True)
    try:
        bpy.ops.piebind.call_pie("INVOKE_DEFAULT", pie_id=pie["id"])
        print("PIE OPENED", flush=True)
    except Exception as exc:
        print("PIE FAIL", exc, flush=True)
    bpy.app.timers.register(shot, first_interval=2.0)
    return None


def setup():
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default.piebind")
    except Exception as exc:
        print("ENABLE FAIL", exc, flush=True)
    import importlib
    pkg = importlib.import_module("bl_ext.user_default.piebind")
    data = pkg.config.default_data()
    pie = pkg.config.create_pie(data, "测试饼")
    for pos, idn, text in (
        ("W", "object.mode_set", "编辑模式"),
        ("E", "object.shade_smooth", "平滑"),
        ("N", "object.origin_set", "原点"),
        ("S", "object.duplicate", "复制"),
    ):
        pkg.config.set_slot(data, pie["id"], pos, {
            "kind": "operator", "idname": idn, "text": text,
            "icon": "NONE", "props": {},
        })
    pkg.config.save(data)
    bpy.context.window_manager.piebind_pie = pie["id"]
    bpy.app.timers.register(open_pie, first_interval=1.6)
    return None


bpy.app.timers.register(setup, first_interval=1.2)
