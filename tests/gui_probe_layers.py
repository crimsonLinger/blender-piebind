"""分层诊断：一次按键分别验证「事件到达」与「区域 keymap 从哪一层取」。

- active/Window + Shift+Tab      → 切 use_snap（若翻转：按键确实到达 Blender）
- user/3D View + Ctrl+Shift+Tab  → 切 use_proportional_edit（若翻转：区域 keymap 读 user 层）
- 同时把 3D View 里原有的 Shift+Tab 条目静音，避免干扰
"""

import json
import os
import tempfile
import time
import traceback

import bpy

OUT = os.path.join(tempfile.gettempdir(), "piebind_gui_probe")
os.makedirs(OUT, exist_ok=True)
RESULT = os.path.join(OUT, "result_layers.json")
LOG = os.path.join(OUT, "layers.log")

TIMEOUT = 420
STATE = {"started": time.time(), "seen": set()}
RESULTS = []
CHECK_EVERY = 0.12


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    line = f"[LAYER] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def quit_later():
    bpy.ops.wm.quit_blender()


def get_km(kc, name, space):
    for candidate in kc.keymaps:
        if candidate.name == name and candidate.space_type == space and not candidate.is_modal:
            return candidate
    return None


def setup():
    wm = bpy.context.window_manager
    scene = bpy.context.scene
    STATE["scene"] = scene

    active = wm.keyconfigs.active
    user = wm.keyconfigs.user
    STATE["kcs"] = (active, user)

    # 静音原有的 3D View Shift+Tab
    muted = 0
    for kc in (active, user):
        km = get_km(kc, "3D View", "VIEW_3D")
        if km is None:
            continue
        for kmi in km.keymap_items:
            if kmi.type == "TAB" and kmi.shift and not (kmi.ctrl or kmi.alt) and kmi.active:
                kmi.active = False
                muted += 1
    record("静音原有 Shift+Tab", True, muted)

    items = []

    # A: active / Window / Shift+Tab -> use_snap
    win_km = get_km(active, "Window", "EMPTY")
    if win_km is None:
        win_km = active.keymaps.new(name="Window", space_type="EMPTY")
    item_a = win_km.keymap_items.new("wm.context_toggle", "TAB", "PRESS", shift=True)
    item_a.properties.data_path = "scene.tool_settings.use_snap"
    items.append(("active/Window", win_km, item_a))

    # B: user / 3D View / Ctrl+Shift+Tab -> use_proportional_edit
    view_km = get_km(user, "3D View", "VIEW_3D")
    if view_km is not None:
        item_b = view_km.keymap_items.new("wm.context_toggle", "TAB", "PRESS", ctrl=True, shift=True)
        item_b.properties.data_path = "scene.tool_settings.use_proportional_edit"
        items.append(("user/3DView", view_km, item_b))

    STATE["items"] = items
    record("写入分层探针条目", True, [name for name, _km, _i in items])

    scene.tool_settings.use_snap = False
    scene.tool_settings.use_proportional_edit = False

    try:
        bpy.context.workspace.status_text_set(
            "PieBind：鼠标放到 3D 视口 → 按 Shift+Tab → 再按 Ctrl+Shift+Tab"
        )
    except Exception:
        pass
    print("=" * 70, flush=True)
    print("请在 3D 视口内：先按 Shift+Tab，再按 Ctrl+Shift+Tab", flush=True)
    print("=" * 70, flush=True)

    bpy.app.timers.register(poll, first_interval=CHECK_EVERY)


def poll():
    scene = STATE.get("scene")
    if scene is None:
        return CHECK_EVERY

    if scene.tool_settings.use_snap and "A" not in STATE["seen"]:
        STATE["seen"].add("A")
        record("A 事件到达 Blender（active/Window 生效）", True, "use_snap=True")
    if scene.tool_settings.use_proportional_edit and "B" not in STATE["seen"]:
        STATE["seen"].add("B")
        record("B user 层区域 keymap 生效", True, "use_proportional_edit=True")

    if {"A", "B"} <= STATE["seen"] or time.time() - STATE["started"] > TIMEOUT:
        if "A" not in STATE["seen"]:
            record("A 事件到达 Blender（active/Window 生效）", False, "未检测到 use_snap 变化")
        if "B" not in STATE["seen"]:
            record("B user 层区域 keymap 生效", False, "未检测到 use_proportional_edit 变化")
        finish()
        return None
    return CHECK_EVERY


def finish():
    try:
        for _name, km, item in STATE.get("items", []):
            try:
                km.keymap_items.remove(item)
            except Exception:
                pass
        record("清理完成", True, "")
    except Exception:
        record("清理失败", False, traceback.format_exc()[:300])
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