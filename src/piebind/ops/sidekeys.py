"""侧键（BUTTON4~7）支持：常驻模态监听（尽力而为）。

实测结论：
- Blender 5.2 会把侧键作为 BUTTON4MOUSE~BUTTON7MOUSE 事件送给**模态处理者**，
  所以「捕获侧键」是可靠的；
- 写进 keymap 的侧键条目**不会被事件分发**（user / active keyconfig 都试过）；
- 模态必须在**真实窗口上下文**里挂载才收得到事件。从定时器 / temp_override 里挂，
  有时能收到、有时只收到一次 WINDOW_DEACTIVATE 就静默——这是目前不稳定的根因。

因此策略：只挂一次，不自作主张反复重挂；提供「重新挂载」按钮（在 3D 视口里点更可靠），
并在面板上显示“是否收到过事件”。
"""

import bpy

from ..core import config
from .common import _dispatch_debug
from .dispatch import event_key, find_binding_for_key, run_binding

SIDE_TYPES = ("BUTTON4MOUSE", "BUTTON5MOUSE", "BUTTON6MOUSE", "BUTTON7MOUSE")

ALIVE = {"value": False}
GOT_EVENT = {"value": False}
STOP = {"value": False}
WATCHDOG = {"value": False}


class PIEBIND_OT_side_listener(bpy.types.Operator):
    bl_idname = "piebind.side_listener"
    bl_label = "PieBind 侧键监听"
    bl_options = {"REGISTER", "INTERNAL"}

    def invoke(self, context, event):
        if STOP["value"] or ALIVE["value"]:
            return {"CANCELLED"}
        if context.window is None:
            return {"CANCELLED"}
        ALIVE["value"] = True
        GOT_EVENT["value"] = False
        context.window_manager.modal_handler_add(self)
        _dispatch_debug("side listener armed")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if STOP["value"]:
            ALIVE["value"] = False
            return {"CANCELLED"}
        if event.type == "WINDOW_DEACTIVATE":
            ALIVE["value"] = False
            _dispatch_debug("side listener on inactive window -> stopped")
            return {"CANCELLED"}
        GOT_EVENT["value"] = True
        if event.type in SIDE_TYPES and event.value == "PRESS":
            if getattr(context.window_manager, "piebind_capturing", False):
                _dispatch_debug("side press ignored (capturing)")
                return {"PASS_THROUGH"}
            key = event_key(event)
            data = config.load()
            binding = find_binding_for_key(data, key)
            _dispatch_debug(f"side press {key['type']} -> {'hit' if binding else 'miss'}")
            if binding is not None:
                run_binding(context, binding, self)
                return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}

    def execute(self, context):
        return {"CANCELLED"}


def is_armed():
    return bool(ALIVE["value"] and GOT_EVENT["value"])


def ensure_armed():
    """在当前窗口上挂监听；已有监听时不重复挂。"""
    if STOP["value"] or ALIVE["value"]:
        return False
    if getattr(bpy.context, "window", None) is None:
        return False
    try:
        bpy.ops.piebind.side_listener("INVOKE_DEFAULT")
        return True
    except Exception as exc:
        _dispatch_debug(f"side arm failed: {exc}")
        ALIVE["value"] = False
        return False


def _watchdog():
    """启动后补挂几次（窗口就绪前 context.window 可能为空）。"""
    if STOP["value"] or ALIVE["value"]:
        return None
    ensure_armed()
    try:
        from ..core import config as _cfg
        data = _cfg.load()
        wanted = any(str((b.get("key") or {}).get("type", "")).startswith("BUTTON")
                     for b in data.get("bindings", []))
    except Exception:
        wanted = False
    return 2.0 if not wanted else 2.0


def start_watchdog():
    if WATCHDOG["value"]:
        return
    WATCHDOG["value"] = True
    STOP["value"] = False
    try:
        bpy.app.timers.register(_watchdog, first_interval=1.5, persistent=True)
    except Exception:
        WATCHDOG["value"] = False


def stop_listener():
    STOP["value"] = True
    ALIVE["value"] = False
    GOT_EVENT["value"] = False
    WATCHDOG["value"] = False
    try:
        if bpy.app.timers.is_registered(_watchdog):
            bpy.app.timers.unregister(_watchdog)
    except Exception:
        pass


class PIEBIND_OT_arm_side_listener(bpy.types.Operator):
    bl_idname = "piebind.arm_side_listener"
    bl_label = "重新挂载侧键监听"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        ALIVE["value"] = False
        GOT_EVENT["value"] = False
        if ensure_armed():
            self.report({"INFO"}, "已尝试挂载侧键监听；请在 3D 视口按一下侧键验证")
            return {"FINISHED"}
        self.report({"ERROR"}, "挂载失败：请在 3D 视口里再点一次")
        return {"CANCELLED"}


# 兼容旧接口名（注册流程用）
def register_side_keymap():
    start_watchdog()
    return ensure_armed()


def unregister_side_keymap():
    stop_listener()


CLASSES = (PIEBIND_OT_side_listener, PIEBIND_OT_arm_side_listener)