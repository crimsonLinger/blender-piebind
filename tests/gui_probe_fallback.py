"""验证：keymap 选错时（3D View + Tab）能否自动回退到 Object Non-modal。"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
os.environ["PIEBIND_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pb-fb-")

import bpy

import piebind
import piebind.config as cfg
import piebind.keymap_engine as ke


def run():
    data = cfg.load()
    pie = cfg.create_pie(data, "模式饼")
    cfg.set_slot(data, pie["id"], "W", {
        "kind": "operator", "idname": "object.mode_set", "text": "编辑模式",
        "icon": "NONE", "props": {"mode": "EDIT"},
    })
    binding = {
        "id": cfg.new_id("bd"),
        "enabled": True,
        "force_override": True,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "TAB", "value": "PRESS", "ctrl": False, "shift": False, "alt": False,
                "oskey": False, "any": False, "key_modifier": "NONE"},
        "target": {"kind": "pie", "id": pie["id"], "props": {}},
    }
    data["bindings"].append(binding)
    cfg.save(data)
    report = ke.apply(data)
    print("REPORT", report, flush=True)
    kc = bpy.context.window_manager.keyconfigs.active
    for km in kc.keymaps:
        for kmi in km.keymap_items:
            if kmi.idname == ke.DISPATCH_IDNAME:
                try:
                    bid = kmi.properties.binding_id
                except Exception:
                    bid = None
                print("ITEM", km.name, km.space_type, "binding=", bid, flush=True)
    print("OWNERS", [(r["keymap"], r["idname"]) for r in ke.scan_key_owners(binding["key"])][:6], flush=True)
    ke.unapply()
    print("RESTORED", [(km.name, kmi.idname) for km in kc.keymaps
                       for kmi in km.keymap_items
                       if kmi.type == "TAB" and not kmi.idname.startswith("piebind.")], flush=True)
    bpy.ops.wm.quit_blender()
    return None


def setup():
    piebind.register()
    bpy.app.timers.register(run, first_interval=1.5)
    return None


bpy.app.timers.register(setup, first_interval=1.2)