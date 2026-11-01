"""操作符：键位捕获、应用/复原、调用饼、以及面板用到的增删改。"""

import json
import os
import time

import bpy
from bpy_extras.io_utils import ExportHelper

from . import config, diagnostics, pie, keymap_engine as ke

MODIFIER_EVENTS = {
    "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL",
    "LEFT_ALT", "RIGHT_ALT", "OSKEY", "LEFT_OSKEY", "RIGHT_OSKEY",
    "HYPER", "LEFT_HYPER", "RIGHT_HYPER",
}
CANCEL_EVENTS = {"ESC", "NONE"}


def split_keymap_identifier(value):
    try:
        name, space, region = json.loads(value)
        return {"name": name, "space": space, "region": region}
    except Exception:
        return None


def make_keymap_identifier(name, space, region):
    return json.dumps([name, space, region], ensure_ascii=False)


def _refresh_keymap_items(self, context):
    """动态枚举：keymap 列表（按名字 + 空间去重）。"""
    try:
        wm = context.window_manager
        kc = wm.keyconfigs.active or wm.keyconfigs.user
    except Exception:
        kc = None
    items = []
    seen = set()
    if kc is not None:
        rows = []
        for km in kc.keymaps:
            if getattr(km, "is_modal", False):
                continue
            ident = (km.name, km.space_type, km.region_type)
            if ident in seen:
                continue
            seen.add(ident)
            rows.append((km.space_type, km.name, km.region_type))
        rows.sort()
        for space, name, region in rows:
            label = f"{name}  [{space}]" if space and space != "EMPTY" else name
            items.append((make_keymap_identifier(name, space, region), label, name))
    if not items:
        items = [("null", "(无可用 keymap)", "")]
    return items


def _refresh_pie_items(self, context):
    try:
        data = config.load()
    except Exception:
        data = {"pies": []}
    items = [(p["id"], p.get("label") or p["id"], "") for p in data.get("pies", [])]
    return items or [("none", "(还没有饼)", "")]


def _refresh_slot_pos(self, context):
    return [(pos, pie.SLOT_LABELS[pos], "") for pos in pie.SLOT_ORDER]


SLOT_POS_ITEMS = [(pos, pie.SLOT_LABELS[pos], "") for pos in pie.SLOT_ORDER]

_DIGIT_TYPES = {
    "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR", "5": "FIVE",
    "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE", "0": "ZERO",
}
_KEY_ALIASES = {
    "tab": "TAB", "space": "SPACE", "spacebar": "SPACE",
    "enter": "RET", "return": "RET", "numpadenter": "NUMPAD_ENTER",
    "esc": "ESC", "escape": "ESC", "backspace": "BACKSPACE", "del": "DEL",
    "delete": "DEL", "home": "HOME", "end": "END",
    "pageup": "PAGEUP", "pagedown": "PAGEDOWN", "insert": "INSERT",
    "up": "UP_ARROW", "down": "DOWN_ARROW", "left": "LEFT_ARROW", "right": "RIGHT_ARROW",
    "lmb": "LEFTMOUSE", "rmb": "RIGHTMOUSE", "mmb": "MIDDLEMOUSE",
    "wheelup": "WHEELUPMOUSE", "wheeldown": "WHEELDOWNMOUSE",
    "menu": "APP", "quote": "QUOTE", "grave": "ACCENT_GRAVE",
}
_MOD_ALIASES = {
    "ctrl": "ctrl", "control": "ctrl",
    "shift": "shift",
    "alt": "alt", "option": "alt",
    "os": "oskey", "cmd": "oskey", "win": "oskey", "super": "oskey",
}


def parse_key_text(text):
    """把 'ctrl+shift+e' / 'tab' / 'F8' 解析成 key 字典。"""
    tokens = [t for t in str(text or "").replace("+", " ").split() if t]
    if not tokens:
        return None
    key = {"value": "PRESS", "ctrl": False, "shift": False, "alt": False,
           "oskey": False, "any": False, "key_modifier": "NONE"}
    key_type = None
    for token in tokens:
        low = token.lower()
        if low in _MOD_ALIASES:
            key[_MOD_ALIASES[low]] = True
            continue
        if low in _DIGIT_TYPES:
            key_type = _DIGIT_TYPES[low]
        elif low in _KEY_ALIASES:
            key_type = _KEY_ALIASES[low]
        elif low.startswith("numpad") and low[6:].isdigit():
            key_type = "NUMPAD_" + _DIGIT_TYPES.get(low[6:], low[6:].upper())
        elif len(token) == 1 and token.isalpha():
            key_type = token.upper()
        else:
            key_type = token.upper().replace("-", "_").replace(" ", "_")
    if not key_type:
        return None
    key["type"] = key_type
    return key

MODE_ITEMS = [
    ("AUTO", "不设置", ""),
    ("OBJECT", "物体模式", ""),
    ("EDIT", "编辑模式", ""),
    ("SCULPT", "雕刻模式", ""),
    ("VERTEX_PAINT", "顶点绘制", ""),
    ("WEIGHT_PAINT", "权重绘制", ""),
    ("TEXTURE_PAINT", "纹理绘制", ""),
    ("POSE", "姿态模式", ""),
]


class PIEBIND_OT_select_pie(bpy.types.Operator):
    bl_idname = "piebind.select_pie"
    bl_label = "选择饼"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def execute(self, context):
        context.window_manager.piebind_pie = self.pie_id
        return {"FINISHED"}


ICON_ITEMS = [
    ("NONE", "无", ""),
    ("MESH_CUBE", "立方体", ""),
    ("MESH_DATA", "网格", ""),
    ("OBJECT_DATA", "物体", ""),
    ("ARMATURE_DATA", "骨架", ""),
    ("BONE_DATA", "骨骼", ""),
    ("MOD_BEVEL", "倒角", ""),
    ("MOD_BOOLEAN", "布尔", ""),
    ("MOD_MIRROR", "镜像", ""),
    ("MOD_SUBSURF", "细分", ""),
    ("MODIFIER", "修改器", ""),
    ("SNAP_ON", "吸附开", ""),
    ("SNAP_OFF", "吸附关", ""),
    ("UV", "UV", ""),
    ("MATERIAL", "材质", ""),
    ("NODE", "节点", ""),
    ("LIGHT", "灯光", ""),
    ("CAMERA_DATA", "相机", ""),
    ("EMPTY_DATA", "空物体", ""),
    ("VIEW3D", "视图", ""),
    ("ADD", "添加", ""),
    ("REMOVE", "移除", ""),
    ("DUPLICATE", "复制", ""),
    ("X", "删除", ""),
    ("CHECKMARK", "确认", ""),
    ("PLAY", "播放", ""),
    ("REC", "录制", ""),
    ("EDIT", "编辑", ""),
    ("COPYDOWN", "复制值", ""),
    ("PASTEDOWN", "粘贴值", ""),
]


def _on_query_update(self, context):
    hits = ke.search_operators(getattr(self, "piebind_op_query", ""), limit=40)
    if not hits:
        return
    try:
        self.piebind_op_choice = hits[0]
    except Exception:
        pass


def _on_op_choice(self, context):
    choice = getattr(self, "piebind_op_choice", "")
    if not choice or choice == "NONE":
        return
    if not getattr(self, "piebind_slot_text", ""):
        try:
            self.piebind_slot_text = ke.operator_label(choice)
        except Exception:
            pass


def _operator_choices(self, context):
    query = getattr(self, "piebind_op_query", "")
    hits = ke.search_operators(query, limit=40)
    if not hits:
        return [("NONE", "(no match)", "")]
    return [(idn, f"{ke.operator_label(idn)} - {idn}", "") for idn in hits]


def _on_query_update(self, context):
    """输入时把当前选择指向第一条命中，避免选到失效值。"""
    hits = ke.search_operators(getattr(self, "piebind_op_query", ""), limit=40)
    if not hits:
        return
    try:
        self.piebind_op_choice = hits[0]
    except Exception:
        pass


class PIEBIND_OT_pick_operator(bpy.types.Operator):
    bl_idname = "piebind.pick_operator"
    bl_label = "选择操作符"
    bl_options = {"REGISTER", "INTERNAL"}

    idname: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        if not ke.has_operator(self.idname):
            self.report({"ERROR"}, f"操作符不存在：{self.idname}")
            return {"CANCELLED"}
        wm.piebind_op_choice = self.idname
        if not wm.piebind_slot_text:
            wm.piebind_slot_text = ke.operator_label_zh(self.idname)
        return {"FINISHED"}


WM_PROPS = {
    "piebind_capture_label": lambda: bpy.props.StringProperty(
        name="捕获结果", default="", options={"SKIP_SAVE"}
    ),
    "piebind_key_json": lambda: bpy.props.StringProperty(default="", options={"SKIP_SAVE"}),
    "piebind_keymap": lambda: bpy.props.EnumProperty(
        name="Keymap", items=_refresh_keymap_items, options={"SKIP_SAVE"},
    ),
    "piebind_target_kind": lambda: bpy.props.EnumProperty(
        name="目标类型",
        items=[("operator", "操作符", ""), ("pie", "饼菜单", "")],
        default="operator",
    ),
    "piebind_op_query": lambda: bpy.props.StringProperty(
        name="搜索", default="", options={"SKIP_SAVE"}, update=_on_query_update,
    ),
    # 动态枚举在 WindowManager 上不可靠（下拉不刷新 items），改用字符串 + 按钮列表
    "piebind_op_choice": lambda: bpy.props.StringProperty(
        name="操作符", default="", options={"SKIP_SAVE"},
    ),
    "piebind_pie": lambda: bpy.props.StringProperty(
        name="饼菜单", default="", options={"SKIP_SAVE"},
    ),
    "piebind_force_override": lambda: bpy.props.BoolProperty(
        name="强制覆盖", default=False,
    ),
    "piebind_restrict_view3d": lambda: bpy.props.BoolProperty(
        name="仅 3D 视口", default=False,
    ),
    "piebind_slot_pos": lambda: bpy.props.EnumProperty(
        name="方位", items=SLOT_POS_ITEMS, options={"SKIP_SAVE"},
    ),
    "piebind_slot_mode": lambda: bpy.props.EnumProperty(
        name="模式", items=MODE_ITEMS, default="AUTO", options={"SKIP_SAVE"},
    ),
    "piebind_slot_props": lambda: bpy.props.StringProperty(
        name="属性 JSON", default="", options={"SKIP_SAVE"},
    ),
    "piebind_slot_text": lambda: bpy.props.StringProperty(
        name="文字", default="", options={"SKIP_SAVE"}
    ),
    "piebind_slot_icon": lambda: bpy.props.EnumProperty(
        name="图标", items=ICON_ITEMS, options={"SKIP_SAVE"},
    ),
    "piebind_new_pie_label": lambda: bpy.props.StringProperty(
        name="饼名称", default="新建饼", options={"SKIP_SAVE"}
    ),
    "piebind_status": lambda: bpy.props.StringProperty(
        name="状态", default="", options={"SKIP_SAVE"}
    ),
}


def register_wm_props():
    for name, factory in WM_PROPS.items():
        setattr(bpy.types.WindowManager, name, factory())


def unregister_wm_props():
    for name in WM_PROPS:
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)


# ---------------------------------------------------------------- operators
class PIEBIND_OT_delete_pie(bpy.types.Operator):
    bl_idname = "piebind.delete_pie"
    bl_label = "删除饼"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def execute(self, context):
        wm = context.window_manager
        pie_id = self.pie_id or getattr(wm, "piebind_pie", "")
        data = config.load()
        pie_data = config.find_pie(data, pie_id)
        if pie_data is None:
            self.report({"ERROR"}, "请先选择一个饼")
            return {"CANCELLED"}
        config.delete_pie(data, pie_id)
        config.save(data)
        wm.piebind_pie = ""
        ke.apply(config.load())
        self.report({"INFO"}, f"已删除饼：{pie_data.get('label', pie_id)}")
        return {"FINISHED"}


class PIEBIND_MT_pies(bpy.types.Menu):
    bl_label = "选择饼"
    bl_idname = "PIEBIND_MT_pies"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        data = config.load()
        pies = data.get("pies", [])
        if not pies:
            layout.label(text="还没有饼")
            return
        for item in pies:
            op = layout.operator(
                "piebind.select_pie",
                text=item.get("label") or item["id"],
                icon="CHECKMARK" if item["id"] == wm.piebind_pie else "DOT",
            )
            op.pie_id = item["id"]
        layout.separator()
        layout.operator("piebind.delete_pie", text="删除当前饼", icon="X")


class PIEBIND_MT_operators(bpy.types.Menu):
    bl_label = "选择操作符"
    bl_idname = "PIEBIND_MT_operators"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        query = getattr(wm, "piebind_op_query", "")
        hits = ke.search_operators(query, limit=20)
        if not hits:
            layout.label(text=f"没有匹配：{query}" if query else "输入搜索词后打开")
            return
        for idn in hits:
            op = layout.operator(
                "piebind.pick_operator",
                text=f"{ke.operator_label_zh(idn)} ({idn})",
            )
            op.idname = idn


class PIEBIND_OT_call_pie(bpy.types.Operator):
    bl_idname = "piebind.call_pie"
    bl_label = "调用饼菜单"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def invoke(self, context, event):
        pie.PIE_STATE["pie_id"] = self.pie_id
        try:
            return bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie.PIE_MENU_ID)
        except Exception as exc:
            self.report({"ERROR"}, f"调用饼菜单失败：{exc}")
            return {"CANCELLED"}

    def execute(self, context):
        return self.invoke(context, None)


def _set_status(context, text):
    """兼容不同版本的 status_text API。"""
    ws = getattr(context, "workspace", None)
    if ws is None:
        return
    try:
        ws.status_text_set(text)
    except Exception:
        try:
            ws.status_text_set(text, None)
        except Exception:
            pass


def _clear_status(context):
    ws = getattr(context, "workspace", None)
    if ws is None:
        return
    for attempt in (
        lambda: ws.status_text_clear(),
        lambda: ws.status_text_set(None),
        lambda: ws.status_text_set(""),
    ):
        try:
            attempt()
            return
        except Exception:
            continue


def _schedule_redraw():
    """给所有窗口的所有区域打重绘标记（偏好设置窗口不会因属性变化自动重绘）。"""

    def _redraw():
        wm = bpy.context.window_manager
        tagged = 0
        for win in wm.windows:
            screen = win.screen
            if screen is None:
                continue
            for area in screen.areas:
                try:
                    area.tag_redraw()
                    tagged += 1
                except Exception:
                    pass
                for region in area.regions:
                    try:
                        region.tag_redraw()
                    except Exception:
                        pass
        if tagged == 0:
            # 兜底：没有可标记区域时直接触发一次绘制
            try:
                win = getattr(bpy.context, "window", None) or (wm.windows[0] if len(wm.windows) else None)
                if win is not None:
                    with bpy.context.temp_override(window=win):
                        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
            except Exception:
                pass
        return None

    try:
        bpy.app.timers.register(_redraw, first_interval=0.01)
    except Exception:
        pass


class PIEBIND_OT_capture_key(bpy.types.Operator):
    bl_idname = "piebind.capture_key"
    bl_label = "捕获快捷键"
    bl_options = {"REGISTER", "INTERNAL"}

    binding_id: bpy.props.StringProperty()

    def invoke(self, context, event):
        wm = context.window_manager
        wm.piebind_capture_label = "请按下组合键…（Esc 取消）"
        _set_status(context, "PieBind：请按下组合键…")
        context.window_manager.modal_handler_add(self)
        _schedule_redraw()
        return {"RUNNING_MODAL"}

    def _finish(self, context, label, key):
        wm = context.window_manager
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


class PIEBIND_OT_apply(bpy.types.Operator):
    bl_idname = "piebind.apply"
    bl_label = "应用键位"
    bl_description = "把配置写入键位并静音冲突项（会写 journal 以便复原）"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        data = config.load()
        report = ke.apply(data)
        msg = f"已创建 {len(report['created'])} 条绑定，静音 {len(report['muted'])} 条冲突项"
        context.window_manager.piebind_status = msg
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class PIEBIND_OT_unapply(bpy.types.Operator):
    bl_idname = "piebind.unapply"
    bl_label = "全部复原"
    bl_description = "移除本插件键位并恢复被静音的条目"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        result = ke.unapply()
        msg = f"移除 {result['removed']} 条，恢复 {result['restored']} 条"
        context.window_manager.piebind_status = msg
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class PIEBIND_OT_create_pie(bpy.types.Operator):
    bl_idname = "piebind.create_pie"
    bl_label = "新建饼"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        data = config.load()
        created = config.create_pie(data, wm.piebind_new_pie_label or "新建饼")
        config.save(data)
        wm.piebind_pie = created["id"]
        wm.piebind_status = f"已创建饼：{created['label']}"
        return {"FINISHED"}


class PIEBIND_OT_add_slot(bpy.types.Operator):
    bl_idname = "piebind.add_slot"
    bl_label = "写入槽位"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        pie_id = wm.piebind_pie
        idname = wm.piebind_op_choice
        data = config.load()
        if not config.find_pie(data, pie_id):
            self.report({"ERROR"}, "请先选择饼")
            return {"CANCELLED"}

        props = {}
        raw = (wm.piebind_slot_props or "").strip()
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    props.update(parsed)
                else:
                    raise ValueError("需要 JSON 对象")
            except Exception as exc:
                self.report({"ERROR"}, f"属性 JSON 无效：{exc}")
                return {"CANCELLED"}

        mode = getattr(wm, "piebind_slot_mode", "AUTO")
        default_text = ke.operator_label_zh(idname)
        if mode and mode != "AUTO":
            idname = "object.mode_set"
            props["mode"] = mode
            default_text = {key: label for key, label, _desc in MODE_ITEMS}.get(mode, mode)

        if not ke.has_operator(idname):
            self.report({"ERROR"}, f"操作符不存在：{idname}")
            return {"CANCELLED"}
        slot = {
            "kind": "operator",
            "idname": idname,
            "text": wm.piebind_slot_text or default_text,
            "icon": wm.piebind_slot_icon or "NONE",
            "props": props,
        }
        config.set_slot(data, pie_id, wm.piebind_slot_pos, slot)
        config.save(data)
        wm.piebind_status = f"已写入槽位 {wm.piebind_slot_pos}：{idname}"
        return {"FINISHED"}


class PIEBIND_OT_remove_slot(bpy.types.Operator):
    bl_idname = "piebind.remove_slot"
    bl_label = "清空槽位"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()
    pos: bpy.props.StringProperty()

    def execute(self, context):
        data = config.load()
        config.set_slot(data, self.pie_id, self.pos, None)
        config.save(data)
        return {"FINISHED"}


class PIEBIND_OT_create_binding(bpy.types.Operator):
    bl_idname = "piebind.create_binding"
    bl_label = "保存绑定"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        wm = context.window_manager
        spec = split_keymap_identifier(wm.piebind_keymap)
        if spec is None:
            self.report({"ERROR"}, "请选择 Keymap")
            return {"CANCELLED"}
        raw = wm.piebind_key_json
        if not raw:
            self.report({"ERROR"}, "请先捕获快捷键")
            return {"CANCELLED"}
        key = json.loads(raw)
        kind = wm.piebind_target_kind
        if kind == "pie":
            target = {"kind": "pie", "id": wm.piebind_pie, "props": {}}
            if not config.find_pie(config.load(), target["id"]):
                self.report({"ERROR"}, "请选择饼菜单")
                return {"CANCELLED"}
        else:
            idname = wm.piebind_op_choice
            if not ke.has_operator(idname):
                self.report({"ERROR"}, f"操作符不存在：{idname}")
                return {"CANCELLED"}
            target = {"kind": "operator", "id": idname, "props": {}}

        data = config.load()
        binding = {
            "id": config.new_id("bd"),
            "enabled": True,
            "force_override": bool(wm.piebind_force_override),
            "keymap": dict(spec),
            "key": key,
            "target": target,
        }
        if wm.piebind_restrict_view3d:
            binding["keymap"]["area"] = "VIEW_3D"
        data["bindings"].append(binding)
        config.save(data)
        ke.apply(data)
        wm.piebind_status = f"已保存绑定：{ke.key_label(key)} → {target['id']}"
        return {"FINISHED"}


class PIEBIND_OT_delete_binding(bpy.types.Operator):
    bl_idname = "piebind.delete_binding"
    bl_label = "删除绑定"
    bl_options = {"REGISTER", "INTERNAL"}

    binding_id: bpy.props.StringProperty()

    def execute(self, context):
        data = config.load()
        data["bindings"] = [b for b in data["bindings"] if b.get("id") != self.binding_id]
        config.save(data)
        ke.apply(data)
        return {"FINISHED"}


class PIEBIND_OT_toggle_binding(bpy.types.Operator):
    bl_idname = "piebind.toggle_binding"
    bl_label = "启用/停用绑定"
    bl_options = {"REGISTER", "INTERNAL"}

    binding_id: bpy.props.StringProperty()

    def execute(self, context):
        data = config.load()
        for binding in data["bindings"]:
            if binding.get("id") == self.binding_id:
                binding["enabled"] = not binding.get("enabled", True)
                break
        config.save(data)
        ke.apply(data)
        return {"FINISHED"}


class PIEBIND_OT_test_pie(bpy.types.Operator):
    bl_idname = "piebind.test_pie"
    bl_label = "预览饼"
    bl_options = {"REGISTER", "INTERNAL"}

    pie_id: bpy.props.StringProperty()

    def invoke(self, context, event):
        pie.PIE_STATE["pie_id"] = self.pie_id
        return bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie.PIE_MENU_ID)


class PIEBIND_OT_select_slot(bpy.types.Operator):
    bl_idname = "piebind.select_slot"
    bl_label = "选择槽位"
    bl_options = {"REGISTER", "INTERNAL"}

    pos: bpy.props.StringProperty()

    def execute(self, context):
        context.window_manager.piebind_slot_pos = self.pos
        return {"FINISHED"}


class PIEBIND_OT_export_diagnostics(bpy.types.Operator, ExportHelper):
    bl_idname = "piebind.export_diagnostics"
    bl_label = "导出诊断 JSON"
    bl_description = "导出环境与键位快照，便于在 issue 里排查（本地路径已脱敏）"
    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            with open(self.filepath, "w", encoding="utf-8") as fh:
                fh.write(diagnostics.dumps())
        except Exception as exc:
            self.report({"ERROR"}, f"导出失败：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"诊断已导出：{self.filepath}")
        return {"FINISHED"}


class PIEBIND_OT_copy_diagnostics(bpy.types.Operator):
    bl_idname = "piebind.copy_diagnostics"
    bl_label = "复制诊断到剪贴板"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        try:
            text = diagnostics.dumps()
            context.window_manager.clipboard = text
        except Exception as exc:
            self.report({"ERROR"}, f"复制失败：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已复制 {len(text)} 字符的诊断信息")
        return {"FINISHED"}


def _dispatch_debug(message):
    path = os.environ.get("PIEBIND_DEBUG_DISPATCH")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(str(message) + "\n")
    except Exception:
        pass


class PIEBIND_OT_dispatch(bpy.types.Operator):
    bl_idname = "piebind.dispatch"
    bl_label = "PieBind Dispatch"
    bl_description = "按绑定的目标执行，并按区域做上下文判断"
    bl_options = {"REGISTER", "INTERNAL"}

    binding_id: bpy.props.StringProperty()

    def execute(self, context):
        area_type = context.area.type if context.area else None
        _dispatch_debug(f"enter binding={self.binding_id} area={area_type}")
        data = config.load()
        binding = config.find_binding(data, self.binding_id)
        if not binding or not binding.get("enabled", True):
            _dispatch_debug("missing/disabled binding")
            return {"CANCELLED"}

        spec = binding.get("keymap") or {}
        space = spec.get("space") or "EMPTY"
        if space not in ("EMPTY", ""):
            area = context.area
            # 窗口级 keymap 被调用时 context.area 可能是 None；此时不做否决，
            # 交由目标操作符自己的 poll 判断（否则绑定会“按了没反应”）。
            if area is not None and area.type != space:
                _dispatch_debug(f"area gate rejected: {area_type} != {space}")
                return {"CANCELLED"}
        wanted_area = spec.get("area")
        if wanted_area and context.area is not None and context.area.type != wanted_area:
            _dispatch_debug(f"restricted area rejected: {area_type} != {wanted_area}")
            return {"CANCELLED"}

        target = binding.get("target") or {}
        if target.get("kind") == "pie":
            pie.PIE_STATE["pie_id"] = target.get("id")
            try:
                return bpy.ops.wm.call_menu_pie("INVOKE_DEFAULT", name=pie.PIE_MENU_ID)
            except Exception as exc:
                _dispatch_debug(f"pie failed: {exc}")
                self.report({"ERROR"}, f"饼菜单调用失败：{exc}")
                return {"CANCELLED"}

        idname = target.get("id") or ""
        if not ke.has_operator(idname):
            _dispatch_debug(f"operator missing: {idname}")
            self.report({"ERROR"}, f"操作符不存在：{idname}")
            return {"CANCELLED"}
        mod_name, op_name = idname.split(".", 1)
        kwargs = dict(target.get("props") or {})
        op = getattr(getattr(bpy.ops, mod_name), op_name)
        try:
            result = op("INVOKE_DEFAULT", **kwargs)
        except TypeError:
            result = op(**kwargs)
        except Exception as exc:
            _dispatch_debug(f"call failed: {exc}")
            self.report({"ERROR"}, f"{idname} 调用失败：{exc}")
            return {"CANCELLED"}
        _dispatch_debug(f"called {idname} -> {result}")
        return {"FINISHED"} if "FINISHED" in result else {"CANCELLED"}


CLASSES = (
    PIEBIND_OT_call_pie,
    PIEBIND_OT_capture_key,
    PIEBIND_OT_apply,
    PIEBIND_OT_unapply,
    PIEBIND_OT_create_pie,
    PIEBIND_OT_add_slot,
    PIEBIND_OT_remove_slot,
    PIEBIND_OT_create_binding,
    PIEBIND_OT_delete_binding,
    PIEBIND_OT_toggle_binding,
    PIEBIND_OT_test_pie,
    PIEBIND_OT_select_slot,
    PIEBIND_OT_export_diagnostics,
    PIEBIND_OT_copy_diagnostics,
    PIEBIND_OT_dispatch,
    PIEBIND_OT_pick_operator,
    PIEBIND_OT_select_pie,
    PIEBIND_OT_delete_pie,
    PIEBIND_MT_pies,
    PIEBIND_MT_operators,
)