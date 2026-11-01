"""最终端到端探针：一次会话测两个键。

A: F8            -> 切 scene.tool_settings.use_snap_rotate
B: Ctrl+Alt+Shift+F9 -> 切 scene.tool_settings.use_proportional_edit

两个绑定都走「配置 -> 引擎 -> active/Window + piebind.dispatch -> 目标」全链路。
命中任意一个即可证明运行时按键链路可用。
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
RESULT = os.path.join(OUT, "result_final.json")
LOG = os.path.join(OUT, "final.log")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_final")
os.environ["PIEBIND_DEBUG_DISPATCH"] = os.path.join(OUT, "final_dispatch.log")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

for stale in (RESULT, os.environ["PIEBIND_DEBUG_DISPATCH"]):
    try:
        os.remove(stale)
    except FileNotFoundError:
        pass

import piebind  # noqa: E402
from piebind import config, keymap_engine as ke  # noqa: E402

RESULTS = []
STATE = {"started": time.time(), "hit": set()}
KEY_A = {"type": "F8", "value": "PRESS"}
KEY_B = {"type": "F9", "value": "PRESS", "ctrl": True, "shift": True, "alt": True}
TIMEOUT = 300


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    line = f"[FINAL] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def quit_later():
    bpy.ops.wm.quit_blender()


def setup():
    piebind.register()
    scene = bpy.context.scene
    STATE["scene"] = scene

    data = config.default_data()
    data["bindings"] = [
        {
            "id": "bd_a",
            "enabled": True,
            "force_override": False,
            "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
            "key": KEY_A,
            "target": {"kind": "operator", "id": "wm.context_toggle",
                       "props": {"data_path": "scene.tool_settings.use_snap_rotate"}},
        },
        {
            "id": "bd_b",
            "enabled": True,
            "force_override": False,
            "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
            "key": KEY_B,
            "target": {"kind": "operator", "id": "wm.context_toggle",
                       "props": {"data_path": "scene.tool_settings.use_proportional_edit"}},
        },
    ]
    config.save(data)
    report = ke.apply(data)
    record("应用两条绑定", len(report["created"]) == 2 and not report["skipped"], report)

    wm = bpy.context.window_manager
    ours = []
    for kc in (wm.keyconfigs.active, wm.keyconfigs.user):
        for km in kc.keymaps:
            if km.name == "Window":
                for item in km.keymap_items:
                    if item.idname == ke.DISPATCH_IDNAME:
                        ours.append({"kc": kc.name, "type": item.type,
                                     "mods": (item.ctrl, item.shift, item.alt),
                                     "binding_id": getattr(item.properties, "binding_id", "")})
    record("Window 层条目", len(ours) == 2, ours)

    scene.tool_settings.use_snap_rotate = False
    scene.tool_settings.use_proportional_edit = False

    try:
        bpy.context.workspace.status_text_set("PieBind：按 F8，再按 Ctrl+Shift+Alt+F9")
    except Exception:
        pass
    print("=" * 70, flush=True)
    print("请按顺序：F8  →  Ctrl+Shift+Alt+F9（鼠标留在 3D 视口内）", flush=True)
    print("=" * 70, flush=True)

    bpy.app.timers.register(poll, first_interval=0.12)


def poll():
    scene = STATE.get("scene")
    if scene is None:
        return 0.12
    if scene.tool_settings.use_snap_rotate:
        STATE["hit"].add("A")
    if scene.tool_settings.use_proportional_edit:
        STATE["hit"].add("B")

    if STATE["hit"]:
        record("运行时按键链路可用", True, f"hit={sorted(STATE['hit'])}")
        finish()
        return None
    if time.time() - STATE["started"] > TIMEOUT:
        record("运行时按键链路可用", False, f"{TIMEOUT}s 内两个键都没有命中")
        finish()
        return None
    return 0.12


def finish():
    try:
        ke.unapply()
        record("复原完成", True, "")
    except Exception:
        record("复原失败", False, traceback.format_exc()[:300])
    try:
        bpy.context.workspace.status_text_clear()
    except Exception:
        pass
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(RESULTS, fh, ensure_ascii=False, indent=1)
    bpy.app.timers.register(quit_later, first_interval=0.3)


try:
    setup()
except Exception:
    record("探针启动", False, traceback.format_exc()[:600])
    finish()