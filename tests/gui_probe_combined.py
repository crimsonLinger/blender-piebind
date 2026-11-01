"""组合探针：同时验证「按键能不能进 Blender」和「覆盖能不能赢」。

1. 在 active 层写入 Shift+Tab → 切换 use_snap_rotate，并静音原 use_snap。
2. 轮询三个信号：
   - screen.is_animation_playing → 用户按了空格，说明输入链路正常
   - use_snap_rotate → 我们的绑定生效（覆盖成功）
   - use_snap → 原功能赢了（覆盖失败，但输入正常）
3. 任何信号出现都写日志；成功后自动复原并退出。
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
RESULT = os.path.join(OUT, "result_combined.json")
LOG = os.path.join(OUT, "combined.log")
os.environ["PIEBIND_CONFIG_DIR"] = os.path.join(OUT, "cfg_combined")
os.makedirs(os.environ["PIEBIND_CONFIG_DIR"], exist_ok=True)

TIMEOUT = 900
STATE = {"started": time.time()}
RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
    line = f"[COMBO] {'OK  ' if ok else 'FAIL'} {name}  {detail}"
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
    STATE["scene"] = scene
    STATE["screen"] = bpy.context.screen

    km = None
    for candidate in active.keymaps:
        if candidate.name == "3D View" and candidate.space_type == "VIEW_3D" and not candidate.is_modal:
            km = candidate
            break
    if km is None:
        record("找到 3D View keymap", False, "missing")
        finish()
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
        finish()
        return

    STATE["km"] = km
    STATE["orig"] = orig
    orig.active = False
    ours = km.keymap_items.new("wm.context_toggle", "TAB", "PRESS", shift=True)
    ours.properties.data_path = "scene.tool_settings.use_snap_rotate"
    STATE["ours"] = ours
    record("准备完成", True,
           f"active 层已写入 Shift+Tab，内置项 active={orig.active}，我们 active={ours.active}")

    for kmu in user.keymaps:
        if kmu.name != "3D View" or kmu.space_type != "VIEW_3D":
            continue
        for kmi in kmu.keymap_items:
            if kmi.idname == "wm.context_toggle" and kmi.active:
                if (getattr(kmi.properties, "data_path", "") or "") == "tool_settings.use_snap":
                    kmi.active = False

    scene.tool_settings.use_snap = False
    scene.tool_settings.use_snap_rotate = False

    try:
        bpy.context.workspace.status_text_set(
            "PieBind 探针：点一下 3D 视口 → 按空格 → 再按 Shift+Tab"
        )
    except Exception:
        pass
    print("=" * 70, flush=True)
    print("请点一下 3D 视口，先按空格（测试输入），再按 Shift+Tab（测试覆盖）", flush=True)
    print("=" * 70, flush=True)

    bpy.app.timers.register(poll, first_interval=0.12)


def poll():
    scene = STATE.get("scene")
    screen = STATE.get("screen")
    if scene is None:
        return 0.12
    try:
        playing = bool(getattr(screen, "is_animation_playing", False)) if screen else False
    except Exception:
        playing = False
    rotate = bool(scene.tool_settings.use_snap_rotate)
    snap = bool(scene.tool_settings.use_snap)

    if playing:
        record("输入链路正常（空格触发了播放）", True, "is_animation_playing=True")
        try:
            bpy.ops.screen.animation_cancel(restore_frame=True)
        except Exception:
            pass

    if rotate:
        record("覆盖生效：Shift+Tab 执行了我们的操作", snap is False,
               f"use_snap_rotate=True use_snap={snap}")
        finish()
        return None
    if snap:
        record("覆盖失败：原功能赢了", False, "use_snap=True use_snap_rotate=False")
        finish()
        return None
    if time.time() - STATE["started"] > TIMEOUT:
        record("等待按键", False, f"{TIMEOUT}s 内没有检测到任何信号")
        finish()
        return None
    return 0.12


def finish():
    try:
        ours = STATE.get("ours")
        km = STATE.get("km")
        if ours is not None and km is not None:
            km.keymap_items.remove(ours)
        orig = STATE.get("orig")
        if orig is not None:
            orig.active = True
        record("复原完成", True, f"内置项 active={getattr(orig, 'active', None)}")
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
    finish()