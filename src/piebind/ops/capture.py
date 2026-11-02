"""快捷键捕获（模态 + 强制重绘）。"""

import json
import os
import time

import bpy

from ..core import config, keymap as ke
from .common import (
    CANCEL_EVENTS,
    MODIFIER_EVENTS,
    _clear_status,
    _schedule_redraw,
    _set_status,
)


class PIEBIND_OT_capture_key(bpy.types.Operator):
    bl_idname = "piebind.capture_key"
    bl_label = "捕获快捷键"
    bl_options = {"REGISTER", "INTERNAL"}

    binding_id: bpy.props.StringProperty()

    def invoke(self, context, event):
        wm = context.window_manager
        wm.piebind_capture_label = "请按下组合键…（Esc 取消）"
        wm.piebind_capturing = True
        _set_status(context, "PieBind：请按下组合键…")
        context.window_manager.modal_handler_add(self)
        _schedule_redraw()
        return {"RUNNING_MODAL"}

    def _finish(self, context, label, key):
        wm = context.window_manager
        wm.piebind_capturing = False
        wm.piebind_key_json = json.dumps(key)
        if self.binding_id:
            data = config.load()
            for binding in data["bindings"]:
                if binding.get("id") == self.binding_id:
                    binding["key"] = key
                    config.save(data)
                    ke.apply(data)
                    break
            wm.piebind_capture_label = f"已改键：{label}"
        else:
            wm.piebind_capture_label = label
        log_path = os.environ.get("PIEBIND_DEBUG_CAPTURE")
        if log_path:
            try:
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write(f"CAPTURED {key.get('type')} {label}\n")
            except Exception:
                pass
        _clear_status(context)
        _schedule_redraw()
        return {"FINISHED"}

    def modal(self, context, event):
        # 调试开关：记录收到的每一个事件，便于定位“某些键抓不到”
        log_path = os.environ.get("PIEBIND_DEBUG_CAPTURE")
        if log_path:
            try:
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write(f"{event.type}/{event.value} c={event.ctrl} s={event.shift} "
                             f"a={event.alt}\n")
            except Exception:
                pass
        if event.value not in ("PRESS", "CLICK", "DOUBLE_CLICK"):
            return {"RUNNING_MODAL"}
        if event.type in ("MOUSEMOVE", "INBETWEEN_MOUSEMOVE", "TIMER", "TIMER_REPORT",
                          "WINDOW_DEACTIVATE", "WINDOW_ACTIVATE"):
            return {"RUNNING_MODAL"}
        if event.type in CANCEL_EVENTS:
            context.window_manager.piebind_capturing = False
            context.window_manager.piebind_capture_label = "已取消"
            _clear_status(context)
            _schedule_redraw()
            return {"CANCELLED"}
        if event.type in MODIFIER_EVENTS:
            return {"RUNNING_MODAL"}

        key = {
            "type": event.type,
            "value": "PRESS" if event.value != "CLICK" else "PRESS",
            "ctrl": event.ctrl,
            "shift": event.shift,
            "alt": event.alt,
            "oskey": event.oskey,
            "any": event.alt and event.ctrl and event.shift,
            "key_modifier": "NONE",
        }
        return self._finish(context, ke.key_label(key), key)
