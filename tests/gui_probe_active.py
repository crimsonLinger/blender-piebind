"""主动层探针：把键位直接写进「当前活动 keyconfig」，验证运行时是否立即生效。

背景：写进 `keyconfigs.addon` 的条目在当前进程里似乎不会立刻参与分发
（`keyconfigs.update()` 也没有把它合并进 active/user 的 keymap_items）。
本探针改用 active 层，若按键后 use_snap_rotate 翻转，说明这是正确的落点。
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
RESULT = os.path.join(OUT, "result_active.json")
LOG = os.path.join(OUT, "active.log")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_active")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

TIMEOUT = 900
STATE = {"started": time.time()}
RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    line = f"[ACTIVE] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def quit_later():
    bpy.ops.wm.quit_blender()


def setup():
    wm = bpy.context.window_manager
    active = wm.keyconfigs.active
    user = wm.keyconfigs.user
    scene = bpy.context.scene

    km = None
    for candidate in active.keymaps:
        if candidate.name == "3D View" and candidate.space_type == "VIEW_3D" and not candidate.is_modal:
            km = candidate
            break
    if km is None:
        record("找到 3D View keymap", False, "missing")
        finish(False)
        return

    orig = None
    for kmi in km.keymap_items:
        if kmi.idname != "wm.context_toggle":
            continue
        if (getattr(kmi.properties, "data_path", "") or "") != "tool_settings.use_snap":
            continue
        if kmi.ctrl or kmi.alt:
            continue
        orig = kmi
        break
    if orig is None:
        record("找到内置键位", False, "no use_snap toggle")
        finish(False)
        return

    STATE["orig"] = orig
    STATE["km"] = km
    STATE["scene"] = scene
    record("找到内置键位", True, f"{orig.type}+shift → {orig.idname}")
    orig.active = False
    record("内置项被静音", orig.active is False)

    ours = km.keymap_items.new("wm.context_toggle", "TAB", "PRESS", shift=True)
    ours.properties.data_path = "scene.tool_settings.use_snap_rotate"
    STATE["ours"] = ours
    record("活动层写入我们的条目", ours.active is True, f"active={ours.active}")

    # user 层里若有同键条目也一起静音
    muted_user = 0
    for kmu in user.keymaps:
        if kmu.name != "3D View" or kmu.space_type != "VIEW_3D":
            continue
        for kmi in kmu.keymap_items:
            if kmi.idname != "wm.context_toggle":
                continue
            if (getattr(kmi.properties, "data_path", "") or "") != "tool_settings.use_snap":
                continue
            if kmi.active:
                kmi.active = False
                muted_user += 1
    record("user 层同键静音数", True, muted_user)

    scene.tool_settings.use_snap = False
    scene.tool_settings.use_snap_rotate = False

    try:
        bpy.context.workspace.status_text_set(
            "PieBind 探针：先点一下 3D 视口，再按 Shift+Tab"
        )
    except Exception:
        pass
    print("=" * 70, flush=True)
    print("PieBind 主动层探针：请先点击 3D 视口获得焦点，然后按 Shift+Tab", flush=True)
    print("=" * 70, flush=True)

    bpy.app.timers.register(poll, first_interval=0.15)


def poll():
    scene = STATE.get("scene")
    if scene is None:
        return 0.15
    rotate = bool(scene.tool_settings.use_snap_rotate)
    snap = bool(scene.tool_settings.use_snap)
    if rotate:
        record("实按后我们的操作生效（active 层）", snap is False,
               f"use_snap_rotate={rotate} use_snap={snap}")
        finish(True)
        return None
    if snap:
        record("实按后我们的操作生效（active 层）", False,
               "use_snap=True：原功能先被触发，覆盖没赢")
        finish(True)
        return None
    if time.time() - STATE["started"] > TIMEOUT:
        record("等待手动按键", False, f"{TIMEOUT}s 内没有检测到按键")
        finish(True)
        return None
    return 0.15


def finish(cleanup=True):
    if cleanup:
        try:
            ours = STATE.get("ours")
            km = STATE.get("km")
            if ours is not None and km is not None:
                km.keymap_items.remove(ours)
            orig = STATE.get("orig")
            if orig is not None:
                orig.active = True
            record("复原后内置项激活", bool(getattr(orig, "active", False)))
        except Exception:
            record("复原流程", False, traceback.format_exc()[:300])
    try:
        if bpy.context.workspace:
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
    finish(False)