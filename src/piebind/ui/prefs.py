"""偏好设置面板：页签式布局（绑定 / 饼菜单 / 设置 / 体检）。

设计：面板本身只负责“分区 + 页签”，具体控件在 widgets / pickers 里复用。
"""

import json

from ..core import config, keymap as ke, keyspec, pies as pie, presets
from ..ops.settings import apply_form_defaults
from . import pickers, widgets


def draw_preferences(panel, context):
    layout = panel.layout
    wm = context.window_manager
    data = config.load()
    apply_form_defaults(wm)
    try:
        from ..ops import sidekeys
        sidekeys.ensure_armed()
    except Exception:
        pass

    _draw_header(layout, wm, data)
    _draw_tabs(layout, wm)

    tab = getattr(wm, "piebind_tab", "bindings")
    if tab == "pies":
        _draw_pies(layout, wm, data)
    elif tab == "settings":
        _draw_settings(layout, wm, data)
    elif tab == "health":
        widgets.draw_health(layout, data)
    else:
        _draw_bindings(layout, wm, data)


# ---------------------------------------------------------------- header
def _draw_header(layout, wm, data):
    bindings = data.get("bindings", [])
    pies = data.get("pies", [])
    box = layout.box()
    row = box.row(align=True)
    row.label(
        text=f"已应用 {len(ke.APPLIED['items'])} · 绑定 {len(bindings)} · 饼 {len(pies)}",
        icon="KEYINGSET",
    )
    row.operator("piebind.apply", text="应用", icon="PLAY")
    row.operator("piebind.unapply", text="复原", icon="LOOP_BACK")

    dups = ke.duplicate_bindings(data)
    if dups:
        box.label(text=f"⚠ 有 {len(dups)} 组绑定互相撞键：{dups[0]['key']}", icon="ERROR")
    if wm.piebind_status:
        box.label(text=wm.piebind_status, icon="INFO")


def _draw_tabs(layout, wm):
    row = layout.row(align=True)
    row.prop(wm, "piebind_tab", expand=True)


# ---------------------------------------------------------------- 绑定
def _draw_bindings(layout, wm, data):
    bindings = data.get("bindings", [])
    box = layout.box()
    box.label(text=f"绑定（{len(bindings)}）", icon="HAND")
    if not bindings:
        box.label(text="还没有绑定：展开下面的「新建绑定」", icon="INFO")
    else:
        box.label(text="每行依次为：键位 · Keymap · 目标", icon="INFO")
    ordered = sorted(
        bindings,
        key=lambda b: ((b.get("keymap") or {}).get("name", ""), ke.key_label(b.get("key") or {})),
    )
    for binding in ordered:
        _draw_binding_row(box, wm, data, binding)

    _draw_new_binding(layout, wm, data)


def _draw_binding_row(box, wm, data, binding):
    conflicts = widgets.conflict_of(binding)
    enabled = binding.get("enabled", True)
    km = binding.get("keymap") or {}
    row = box.row(align=True)

    op = row.operator(
        "piebind.toggle_binding", text="",
        icon="CHECKBOX_HLT" if enabled else "CHECKBOX_DEHLT",
    )
    op.binding_id = binding["id"]
    row.label(text=ke.key_label(binding.get("key") or {}))
    row.label(text=km.get("name", "?"))
    row.label(text=widgets.target_label(data, binding))

    if conflicts:
        level = widgets.worst(conflicts)
        row.label(text=f"⚠{len(conflicts)}", icon=widgets.SEVERITY_ICON.get(level, "INFO"))
    if binding.get("force_override"):
        row.label(text="", icon="LOCKED")

    op = row.operator("piebind.check_binding", text="", icon="QUESTION")
    op.binding_id = binding["id"]
    op = row.operator("piebind.capture_key", text="", icon="REC")
    op.binding_id = binding["id"]
    op = row.operator("piebind.delete_binding", text="", icon="X")
    op.binding_id = binding["id"]

    if conflicts:
        owners = "、".join(sorted({c["owner"] for c in conflicts}))[:40]
        box.label(text=f"    └ 被 {owners} 占用", icon=widgets.SEVERITY_ICON.get(
            widgets.worst(conflicts), "INFO"))


def _draw_new_binding(layout, wm, data):
    col = layout.column(align=True)
    head = col.row(align=True)
    head.prop(
        wm, "piebind_show_new", text="新建绑定", emboss=False,
        icon="TRIA_DOWN" if wm.piebind_show_new else "TRIA_RIGHT",
    )
    if not wm.piebind_show_new:
        return

    box = col.box()
    row = box.row(align=True)
    row.label(text="键位：")
    row.label(text=wm.piebind_capture_label or "（未捕获）")
    row.operator("piebind.capture_key", text="捕获", icon="REC")

    pickers.keymap_picker(box, wm)

    box.prop(wm, "piebind_target_kind", expand=True)
    if wm.piebind_target_kind == "pie":
        current_pie = pickers.pie_picker(box, wm, data, "目标饼：")
        if not data.get("pies"):
            box.label(text="还没有饼：切到「饼菜单」页签新建", icon="INFO")
        elif current_pie is None:
            box.label(text="点上面的下拉选中一个饼", icon="INFO")
    else:
        pickers.operator_picker(box, wm)

    row = box.row(align=True)
    row.prop(wm, "piebind_force_override")
    row.prop(wm, "piebind_restrict_view3d")

    key = None
    if wm.piebind_key_json:
        try:
            key = json.loads(wm.piebind_key_json)
        except Exception:
            key = None
    pickers.conflict_preview(box, wm, key)

    box.operator("piebind.create_binding", text="保存绑定", icon="ADD")


# ---------------------------------------------------------------- 饼菜单
def _draw_pies(layout, wm, data):
    pies = data.get("pies", [])
    box = layout.box()
    header = box.row(align=True)
    header.label(text=f"饼菜单（{len(pies)}）", icon="MESH_CIRCLE")

    naming = box.row(align=True)
    naming.prop(wm, "piebind_new_pie_label", text="新饼名称")
    naming.operator("piebind.create_pie", text="新建", icon="ADD")

    if not pies:
        box.label(text="在上面填名称 → 点「新建」；建好后也能随时改名", icon="INFO")
        return

    current = pickers.pie_picker(box, wm, data, "编辑：")
    if current is None:
        box.label(text="点上面的下拉选择一个饼", icon="INFO")
        return

    renaming = box.row(align=True)
    renaming.label(text=f"当前名称：{current['label']}", icon="MESH_CIRCLE")
    op = renaming.operator("piebind.rename_pie", text="改 名")
    op.pie_id = current["id"]

    widgets.draw_compass(box, wm, current)

    slots = current.get("slots") or {}
    filled = [pos for pos in pie.SLOT_ORDER if slots.get(pos)]
    row = box.row(align=True)
    row.label(text=f"已填槽位 {len(filled)}/8：{'、'.join(filled) if filled else '无'}", icon="INFO")
    op = row.operator("piebind.test_pie", text="预览", icon="PLAY")
    op.pie_id = current["id"]

    editor = box.box()
    head = editor.row(align=True)
    head.label(
        text=f"编辑槽位 · {pie.SLOT_LABELS[wm.piebind_slot_pos]}", icon="TOOL_SETTINGS"
    )
    head.operator("piebind.load_slot", text="载入", icon="FILE_REFRESH")
    op = head.operator("piebind.remove_slot", text="清空", icon="X")
    op.pie_id = current["id"]
    op.pos = wm.piebind_slot_pos

    pickers.operator_picker(editor, wm)

    row = editor.row(align=True)
    row.prop(wm, "piebind_slot_text", text="文字")
    row.prop(wm, "piebind_slot_icon", text="图标")

    row = editor.row(align=True)
    row.label(text="参数")
    current_props = (wm.piebind_slot_props or "").strip()
    preset_label = ""
    if current_props:
        try:
            parsed = json.loads(current_props)
            if isinstance(parsed, dict):
                preset_label = presets.label_for(wm.piebind_op_choice, parsed)
        except Exception:
            preset_label = ""
    if preset_label:
        menu_text = f"{preset_label} ▾"
    else:
        menu_text = current_props[:32] if current_props else "点这里选预设（或下方手填 JSON）"
    row.menu("PIEBIND_MT_slot_presets", text=menu_text, icon="PRESET")
    editor.prop(wm, "piebind_slot_props", text="属性 JSON")


# ---------------------------------------------------------------- 设置
def _draw_settings(layout, wm, data):
    block = config.settings(data)
    spec = keyspec.split_keymap_identifier(block.get("default_keymap") or "")
    km_name = f"{spec['name']} [{spec['space']}]" if spec else "3D View（默认）"

    box = layout.box()
    box.label(text="新建绑定的默认值", icon="PREFERENCES")
    box.label(text=f"Keymap：{km_name}")
    box.label(text=f"强制覆盖：{'开' if block.get('force_override') else '关'}")
    box.label(text=f"仅 3D 视口：{'开' if block.get('restrict_view3d') else '关'}")
    row = box.row(align=True)
    row.operator("piebind.save_defaults", text="用当前表单存为默认", icon="FILE_TICK")
    row.operator("piebind.load_defaults", text="载入默认到表单", icon="IMPORT")

    box = layout.box()
    box.label(text="侧键（鼠标 4 / 5 / 6 / 7 键）", icon="MOUSE_LMB")
    try:
        from ..ops import sidekeys
        _armed = sidekeys.is_armed()
    except Exception:
        _armed = False
    box.label(
        text="监听：已挂载" if _armed else "监听：未挂载（点下面按钮重新挂载）",
        icon="CHECKMARK" if _armed else "ERROR",
    )
    box.operator("piebind.arm_side_listener", text="重新挂载侧键监听", icon="PLAY")

    box = layout.box()
    box.label(text="数据与诊断", icon="FILEBROWSER")
    row = box.row(align=True)
    row.operator("piebind.export_config", text="导出配置", icon="EXPORT")
    row.operator("piebind.import_config", text="导入配置", icon="IMPORT")
    row.operator("piebind.copy_diagnostics", text="复制诊断", icon="COPYDOWN")
    box.label(text=f"配置目录：{config.config_dir()}")
    row = box.row(align=True)
    row.operator("piebind.open_config_dir", text="打开配置目录", icon="FILE_FOLDER")

    box = layout.box()
    box.label(text="关于", icon="INFO")
    box.label(text=f"PieBind 0.1.0 · 配置格式 v{config.SCHEMA_VERSION}")
    box.label(text="Agent API：piebind.api.call(action, payload)")
    box.label(text="测试绑定是否生效：绑定列表每行最左侧的 ? 按钮")

