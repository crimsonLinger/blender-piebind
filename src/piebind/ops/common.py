"""ops 公共常量、WindowManager 属性与状态栏/重绘小工具。"""

import json
import os
import time

import bpy

from ..core import config, keymap as ke, keyspec, pies as pie
from ..core.keyspec import (
    COMMON_KEYMAPS,
    keymap_rows,
    make_keymap_identifier,
    parse_key_text,
    split_keymap_identifier,
)


MODIFIER_EVENTS = {
    "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL",
    "LEFT_ALT", "RIGHT_ALT", "OSKEY", "LEFT_OSKEY", "RIGHT_OSKEY",
    "HYPER", "LEFT_HYPER", "RIGHT_HYPER",
}


CANCEL_EVENTS = {"ESC", "NONE"}


SLOT_POS_ITEMS = [(pos, pie.SLOT_LABELS[pos], "") for pos in pie.SLOT_ORDER]


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


WM_PROPS = {
    "piebind_capture_label": lambda: bpy.props.StringProperty(
        name="捕获结果", default="", options={"SKIP_SAVE"}
    ),
    "piebind_key_json": lambda: bpy.props.StringProperty(default="", options={"SKIP_SAVE"}),
    "piebind_keymap": lambda: bpy.props.StringProperty(
        name="Keymap", default="", options={"SKIP_SAVE"},
    ),
    "piebind_keymap_query": lambda: bpy.props.StringProperty(
        name="Keymap 搜索", default="", options={"SKIP_SAVE"},
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
    # ---- 面板状态（页签与折叠）----
    "piebind_tab": lambda: bpy.props.EnumProperty(
        name="页签",
        items=[
            ("bindings", "绑定", "管理与新建键位绑定"),
            ("pies", "饼菜单", "编辑饼菜单的 8 个槽位"),
            ("settings", "设置", "默认值、导入导出与配置位置"),
            ("health", "体检", "扫描本机插件键位"),
        ],
        default="bindings",
        options={"SKIP_SAVE"},
    ),
    "piebind_show_new": lambda: bpy.props.BoolProperty(
        name="新建绑定", default=False, options={"SKIP_SAVE"}
    ),
    "piebind_form_ready": lambda: bpy.props.BoolProperty(
        name="表单已初始化", default=False, options={"SKIP_SAVE"}
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


def _refresh_keymap_items(self, context):
    """兼容旧调用：返回下拉项（面板已改为菜单）。"""
    return [(r["id"], r["label"], r["name"]) for r in keymap_rows()]


def _refresh_pie_items(self, context):
    try:
        data = config.load()
    except Exception:
        data = {"pies": []}
    items = [(p["id"], p.get("label") or p["id"], "") for p in data.get("pies", [])]
    return items or [("none", "(还没有饼)", "")]


def _refresh_slot_pos(self, context):
    return [(pos, pie.SLOT_LABELS[pos], "") for pos in pie.SLOT_ORDER]


def _on_query_update(self, context):
    """输入时把当前选择指向第一条命中，避免选到失效值。"""
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


def _dispatch_debug(message):
    path = os.environ.get("PIEBIND_DEBUG_DISPATCH")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(str(message) + "\n")
    except Exception:
        pass

