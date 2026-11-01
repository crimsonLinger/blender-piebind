"""最小输入链路探针：验证 SendKeys 能否真的驱动 Blender 键位。

在 **Window** keymap（全窗口生效）绑一个组合键切换 `scene.tool_settings.use_snap`，
不涉及覆盖、不涉及 3D View 区域，用来区分「输入没进来」和「覆盖没生效」。
"""

import json
import os
import sys
import tempfile
import time
import traceback

import bpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
READY = os.path.join(OUT, "ready.json")
STOP = os.path.join(OUT, "stop.txt")
RESULT = os.path.join(OUT, "result.json")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_window")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

for stale in (READY, STOP, RESULT):
    try:
        os.remove(stale)
    except FileNotFoundError:
        pass

import piebind  # noqa: E402
from piebind import config, keymap_engine as ke  # noqa: E402

RESULTS = []
STATE = {"started": time.time(), "scene": bpy.context.scene}

COMBO = {"type": "F11", "value": "PRESS", "ctrl": True, "alt": True, "shift": True,
         "oskey": False, "any": False, "key_modifier": "NONE"}


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"[PROBE] {'OK  ' if ok else 'FAIL'} {name}  {detail}")


def save_results():
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, ensure_ascii=False, indent=1)


def quit_later():
    bpy.ops.wm.quit_blender()


def setup():
    piebind.register()
    scene = STATE["scene"]
    data = config.default_data()
    data["bindings"].append({
        "id": "bd_window",
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "Window", "space": "EMPTY", "region": "WINDOW"},
        "key": COMBO,
        "target": {
            "kind": "operator",
            "id": "wm.context_toggle",
            "props": {"data_path": "scene.tool_settings.use_snap"},
        },
    })
    config.save(data)
    report = ke.apply(data)
    record("创建窗口级绑定", len(report["created"]) == 1, report)

    scene.tool_settings.use_snap = False
    payload = {
        "pid": os.getpid(),
        "key": COMBO,
        "label": ke.key_label(COMBO),
        "sendkeys": "^%+{F11}",
        "expect": "use_snap == True",
    }
    with open(READY, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    bpy.app.timers.register(wait_for_key, first_interval=0.2)


def wait_for_key():
    scene = STATE["scene"]
    if os.path.exists(STOP):
        value = bool(scene.tool_settings.use_snap)
        record("SendKeys 能驱动 Blender 键位", value is True, f"use_snap={value}")
        ke.unapply()
        save_results()
        try:
            piebind.unregister()
        except Exception:
            pass
        bpy.app.timers.register(quit_later, first_interval=0.2)
        return None
    if time.time() - STATE["started"] > 90:
        record("SendKeys 探针", False, "90s 超时")
        save_results()
        bpy.app.timers.register(quit_later, first_interval=0.3)
        return None
    return 0.2


try:
    setup()
except Exception:
    record("探针启动", False, traceback.format_exc()[:600])
    save_results()
    bpy.app.timers.register(quit_later, first_interval=0.3)