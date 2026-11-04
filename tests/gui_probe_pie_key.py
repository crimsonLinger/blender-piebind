"""用真实按键触发饼菜单（配合外部 SendInput）。"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
os.environ["PIEBIND_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pb-key-")

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
SHOT = os.path.join(OUT, "pie_key.png")
os.makedirs(OUT, exist_ok=True)

import piebind
import piebind.config as cfg
import piebind.keymap_engine as ke


def shot():
    try:
        bpy.ops.screen.screenshot(filepath=SHOT)
        print("SHOT OK", SHOT, flush=True)
    except Exception as exc:
        print("SHOT FAIL", exc, flush=True)
    try:
        ke.unapply()
    except Exception:
        pass
    bpy.ops.wm.quit_blender()
    return None


def ready():
    print("READY_FOR_KEY", flush=True)
    bpy.app.timers.register(shot, first_interval=4.0)
    return None


def setup():
    piebind.register()
    data = cfg.load()
    pie = cfg.create_pie(data, "模式饼")
    for pos, mode, text in (("W", "EDIT", "编辑模式"), ("E", "OBJECT", "物体模式"),
                            ("N", "SCULPT", "雕刻模式"), ("S", "POSE", "姿态模式")):
        cfg.set_slot(data, pie["id"], pos, {
            "kind": "operator", "idname": "object.mode_set", "text": text,
            "icon": "NONE", "props": {"mode": mode},
        })
    data["bindings"].append({
        "id": cfg.new_id("bd"),
        "enabled": True,
        "force_override": True,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "T", "value": "PRESS", "ctrl": False, "shift": False, "alt": False,
                "oskey": False, "any": False, "key_modifier": "NONE"},
        "target": {"kind": "pie", "id": pie["id"], "props": {}},
    })
    cfg.save(data)
    print("APPLY", ke.apply(data), flush=True)
    bpy.app.timers.register(ready, first_interval=1.2)
    return None


bpy.app.timers.register(setup, first_interval=1.2)