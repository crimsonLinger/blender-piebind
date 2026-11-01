"""引擎路径探针：用不依赖 Shift 的 F8，验证「配置 -> 引擎 -> 分发器 -> 目标」整链。

同时把 Window keymap 的条目状态写入日志，便于定位条目到底落在哪个 keymap。
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
RESULT = os.path.join(OUT, "result_engine.json")
LOG = os.path.join(OUT, "engine.log")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_engine")
os.environ.setdefault("PIEBIND_DEBUG_DISPATCH", os.path.join(OUT, "engine_dispatch.log"))
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
KEY = {"type": "F8", "value": "PRESS", "ctrl": False, "shift": False, "alt": False,
       "oskey": False, "any": False, "key_modifier": "NONE"}


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:600]})
    line = f"[ENGINE] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def quit_later():
    bpy.ops.wm.quit_blender()


def dump_state():
    wm = bpy.context.window_manager
    rows = []
    for kc in (wm.keyconfigs.active, wm.keyconfigs.user, wm.keyconfigs.addon):
        if kc is None:
            continue
        for km in kc.keymaps:
            if km.name == "Window":
                rows.append({
                    "kc": kc.name,
                    "space": km.space_type,
                    "region": km.region_type,
                    "items": len(km.keymap_items),
                    "ours": [i.idname for i in km.keymap_items if (i.idname or "").startswith("piebind.")],
                })
    record("Window keymap 状态", any(r["ours"] for r in rows), rows)


def setup():
    piebind.register()
    scene = bpy.context.scene
    STATE["scene"] = scene

    data = config.default_data()
    data["bindings"].append({
        "id": "bd_engine",
        "enabled": True,
        "force_override": False,
        "keymap": {"name": "3D View", "space": "VIEW_3D", "region": "WINDOW"},
        "key": KEY,
        "target": {
            "kind": "operator",
            "id": "wm.context_toggle",
            "props": {"data_path": "scene.tool_settings.use_snap_rotate"},
        },
    })
    config.save(data)
    report = ke.apply(data)
    record("应用绑定", len(report["created"]) == 1 and not report["skipped"], report)
    dump_state()

    def later():
        dump_state()
        return None

    bpy.app.timers.register(later, first_interval=3.0)

    scene.tool_settings.use_snap_rotate = False
    try:
        bpy.context.workspace.status_text_set("PieBind 探针：请按 F8")
    except Exception:
        pass
    print("=" * 70, flush=True)
    print("请在 3D 视口里按 F8（不需要 Shift）", flush=True)
    print("=" * 70, flush=True)
    bpy.app.timers.register(poll, first_interval=0.12)


def poll():
    scene = STATE.get("scene")
    if scene is None:
        return 0.12
    if scene.tool_settings.use_snap_rotate:
        record("引擎整链生效（F8 → 分发器 → context_toggle）", True, "use_snap_rotate=True")
        finish()
        return None
    if time.time() - STATE["started"] > 420:
        record("引擎整链生效", False, "420s 内没有检测到 use_snap_rotate 变化")
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