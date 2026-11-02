"""PieBind — Blender 键位体检 / 可逆覆盖 / 轻量饼菜单。"""

bl_info = {
    "name": "PieBind",
    "author": "PieBind contributors",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "Preferences > Add-ons > PieBind",
    "description": "键位体检、可逆覆盖与轻量饼菜单 (agent-ready)",
    "category": "Interface",
}

import os
import traceback

import bpy

from . import api, core, ops, ui
from .core import config, keymap as ke, pies as pie
from .ops.settings import apply_form_defaults
from .ui.prefs import draw_preferences

LOG = "[PieBind]"


class PIEBIND_AP_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    def draw(self, context):
        draw_preferences(self, context)


CLASSES = (
    pie.PIEBIND_MT_pie,
) + ui.CLASSES + ops.CLASSES + (PIEBIND_AP_Preferences,)

_timer_registered = False


def log(message):
    print(f"{LOG} {message}")


def _deferred():
    """延迟应用：注册时 keyconfig 可能尚未加载完成。"""
    if os.environ.get("PIEBIND_NO_DEFERRED"):
        return None
    try:
        apply_form_defaults(bpy.context.window_manager)
    except Exception:
        traceback.print_exc()
    try:
        healed = ke.reconcile_journal()
        if healed.get("restored"):
            log(f"journal 自愈：恢复 {healed['restored']} 条键位")
        if ke.APPLIED.get("items") and not healed.get("restored"):
            log("绑定已应用，跳过重复应用")
            return None
        data = config.load()
        report = ke.apply(data)
        log(
            "已应用 {created} 条绑定 / 静音 {muted} 条冲突项".format(
                created=len(report.get("created", [])), muted=len(report.get("muted", []))
            )
        )
    except Exception:
        traceback.print_exc()
    return None


def _on_load_post(*_args):
    _deferred()


def register():
    global _timer_registered
    try:
        ke.refresh_owned()
    except Exception:
        traceback.print_exc()
    for cls in CLASSES:
        try:
            bpy.utils.register_class(cls)
        except Exception as exc:
            log(f"注册失败 {getattr(cls, '__name__', cls)}: {exc}")
    try:
        ops.register_wm_props()
    except Exception:
        traceback.print_exc()

    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)

    try:
        if not bpy.app.timers.is_registered(_deferred):
            bpy.app.timers.register(_deferred, first_interval=0.25)
            _timer_registered = True
    except Exception:
        traceback.print_exc()


def unregister():
    try:
        ke.unapply()
    except Exception:
        traceback.print_exc()

    try:
        if _on_load_post in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_on_load_post)
    except Exception:
        pass

    try:
        if bpy.app.timers.is_registered(_deferred):
            bpy.app.timers.unregister(_deferred)
    except Exception:
        pass

    ops.unregister_wm_props()

    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    log("已卸载，键位与静音状态已复原")