"""覆盖探针：真实按键验证「静音内置项 + 我们的条目接管」。

绑定：3D View / Shift+Tab，force_override=True，目标切 use_snap_rotate。
判据：
  use_snap_rotate=True  -> 覆盖成功（我们的目标执行了）
  use_snap=True         -> 覆盖失败（原功能仍被触发）
  都为 False            -> 按键未到达
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
RESULT = os.path.join(OUT, "result_override.json")
LOG = os.path.join(OUT, "override.log")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_override")
os.environ["PIEBIND_DEBUG_DISPATCH"] = os.path.join(OUT, "override_dispatch.log")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

for stale in (RESULT, os.environ["PIEBIND_DEBUG_DISPATCH"]):
    try:
        os.remove(stale)
    except FileNotFoundError:
        pass

import piebind  # noqa: E402
from piebind import config, keymap_engine as ke  # noqa: E402

RESULTS = []
STATE = {"started": time.time()}
TIMEOUT = 240


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    line = f"[OVERRIDE] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
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
    data["bindings"].append({
        "id": "bd_override",
        "enabled": True,
        "force_override": True,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": {"type": "TAB", "value": "PRESS", "shift": True},
        "target": {"kind": "operator", "id": "wm.context_toggle",
                   "props": {"data_path": "scene.tool_settings.use_snap_rotate"}},
    })
    config.save(data)
    report = ke.apply(data)
    record("应用覆盖绑定", len(report["created"]) == 1, report)

    scene.tool_settings.use_snap = False
    scene.tool_settings.use_snap_rotate = False

    try:
        bpy.context.workspace.status_text_set("PieBind：请在 3D 视口按 Shift+Tab")
    except Exception:
        pass
    print("=" * 70, flush=True)
    print("请按 Shift+Tab（覆盖原吸附开关）", flush=True)
    print("=" * 70, flush=True)
    bpy.app.timers.register(poll, first_interval=0.12)


def poll():
    scene = STATE.get("scene")
    if scene is None:
        return 0.12
    rotate = bool(scene.tool_settings.use_snap_rotate)
    snap = bool(scene.tool_settings.use_snap)
    if rotate:
        record("覆盖生效：我们的目标被执行", snap is False, f"use_snap_rotate={rotate} use_snap={snap}")
        finish()
        return None
    if snap:
        record("覆盖生效：我们的目标被执行", False, "use_snap=True：原功能赢了")
        finish()
        return None
    if time.time() - STATE["started"] > TIMEOUT:
        record("覆盖生效", False, f"{TIMEOUT}s 内未检测到任何变化")
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