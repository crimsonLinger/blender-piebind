"""模拟真实绑定：强制覆盖 Tab → 饼菜单，并截图看饼的排布。"""

import os
import sys
import tempfile

sys.path.insert(0, r"<旧目录>\src")
os.environ["PIEBIND_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pb-bind-")

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
SHOT = os.path.join(OUT, "pie_binding.png")

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


def run():
    data = cfg.load()
    pie = cfg.create_pie(data, "模式饼")
    for pos, mode, text in (("W", "EDIT", "编辑模式"), ("E", "OBJECT", "物体模式"),
                            ("N", "SCULPT", "雕刻模式"), ("S", "POSE", "姿态模式")):
        cfg.set_slot(data, pie["id"], pos, {
            "kind": "operator", "idname": "object.mode_set", "text": text,
            "icon": "NONE", "props": {"mode": mode},
        })
    binding = {
        "id": cfg.new_id("bd"),
        "enabled": True,
        "force_override": True,
        "keymap": {"name": "Object Non-modal", "space": "EMPTY", "region": "WINDOW"},
        "key": {"type": "TAB", "value": "PRESS", "ctrl": False, "shift": False, "alt": False,
                "oskey": False, "any": False, "key_modifier": "NONE"},
        "target": {"kind": "pie", "id": pie["id"], "props": {}},
    }
    data["bindings"].append(binding)
    cfg.save(data)
    print("APPLY", ke.apply(data), flush=True)
    kc = bpy.context.window_manager.keyconfigs.active
    for km in kc.keymaps:
        for kmi in km.keymap_items:
            if kmi.type == "TAB" and kmi.idname.startswith("piebind."):
                try:
                    bid = kmi.properties.binding_id
                except Exception as exc:
                    bid = f"<{exc}>"
                print("PATCHED", km.name, kmi.idname, "binding=", bid, flush=True)
    try:
        result = bpy.ops.piebind.dispatch("INVOKE_DEFAULT", binding_id=binding["id"])
        print("DISPATCH", result, flush=True)
    except Exception as exc:
        print("DISPATCH FAIL", type(exc).__name__, exc, flush=True)
    bpy.app.timers.register(shot, first_interval=2.0)
    return None


def setup():
    try:
        piebind.register()
    except Exception as exc:
        print("REGISTER FAIL", exc, flush=True)
    bpy.app.timers.register(run, first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)