"""分发探针：验证「写进 active keyconfig 的运行时绑定会不会被事件系统捡到」。

不依赖区域：直接用 Window keymap（全窗口生效）+ 自定义标记操作符。
用户按 Ctrl+Alt+Shift+F12，若操作符被调用则 STATE.hit=True。
"""

import json
import os
import tempfile
import time
import traceback

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
RESULT = os.path.join(OUT, "result_dispatch.json")
LOG = os.path.join(OUT, "dispatch.log")

TIMEOUT = 900
STATE = {"started": time.time(), "hit": False}
RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    line = f"[DISPATCH] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def quit_later():
    bpy.ops.wm.quit_blender()


class PROBE_OT_mark(bpy.types.Operator):
    bl_idname = "probe.mark"
    bl_label = "Probe Mark"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        STATE["hit"] = True
        return {"FINISHED"}


COMBO = {"type": "F12", "value": "PRESS", "ctrl": True, "shift": True, "alt": True}


def setup():
    bpy.utils.register_class(PROBE_OT_mark)
    wm = bpy.context.window_manager
    active = wm.keyconfigs.active
    window_km = None
    for candidate in active.keymaps:
        if candidate.name == "Window" and not candidate.is_modal:
            window_km = candidate
            break
    if window_km is None:
        record("找到 Window keymap", False, "missing")
        finish()
        return
    item = window_km.keymap_items.new("probe.mark", "F12", "PRESS", ctrl=True, shift=True, alt=True)
    STATE["item"] = item
    record("绑定写入 active/Window", item.active is True,
           f"{item.type} {item.ctrl} {item.shift} {item.alt}")

    try:
        bpy.context.workspace.status_text_set("PieBind 探针：请按 Ctrl+Alt+Shift+F12")
    except Exception:
        pass
    print("=" * 70, flush=True)
    print("请直接按 Ctrl+Alt+Shift+F12（不需要点任何区域）", flush=True)
    print("=" * 70, flush=True)
    bpy.app.timers.register(poll, first_interval=0.12)


def poll():
    if STATE.get("hit"):
        record("active 层运行时绑定被分发", True, "probe.mark 被调用")
        finish()
        return None
    if time.time() - STATE["started"] > TIMEOUT:
        record("active 层运行时绑定被分发", False, f"{TIMEOUT}s 内没有调用")
        finish()
        return None
    return 0.12


def finish():
    try:
        item = STATE.get("item")
        wm = bpy.context.window_manager
        active = wm.keyconfigs.active
        window_km = next((k for k in active.keymaps if k.name == "Window"), None)
        if item is not None and window_km is not None:
            window_km.keymap_items.remove(item)
        record("清理完成", True, "")
    except Exception:
        record("清理", False, traceback.format_exc()[:300])
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