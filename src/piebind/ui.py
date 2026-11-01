"""偏好设置面板：状态、绑定列表、新建/改键、饼编辑（罗盘点选）、体检页。"""

import json
from collections import Counter

import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import config, keymap_engine as ke
from . import ops, pie

SEVERITY_ICON = {"blocker": "ERROR", "warning": "INFO"}


# ------------------------------------------------------------------ helpers
def _target_label(data, binding):
    target = binding.get("target") or {}
    if target.get("kind") == "pie":
        found = config.find_pie(data, target.get("id"))
        return f"饼：{found['label'] if found else '(已删除)'}"
    return ke.operator_label(target.get("id") or "")


def _conflict_of(binding):
    if not binding.get("enabled", True):
        return []
    try:
        return ke.scan_conflict(binding.get("keymap") or {}, binding.get("key") or {})
    except Exception:
        return []


def _worst(occupants):
    for level in ("blocker", "warning"):
        if any(o["severity"] == level for o in occupants):
            return level
    return ""


def _draw_operator_picker(layout, wm):
    """搜索 + 结果按钮 + 手填字段；支持中文（用 Blender 的 UI 翻译）。"""
    layout.prop(wm, "piebind_op_query", text="搜索")
    hits = ke.search_operators(wm.piebind_op_query, limit=6)
    if hits:
        col = layout.column(align=True)
        for idn in hits:
            op = col.operator(
                "piebind.pick_operator",
                text=f"{ke.operator_label_zh(idn)} - {idn}",
            )
            op.idname = idn
    chosen = getattr(wm, "piebind_op_choice", "")
    if chosen and ke.has_operator(chosen):
        layout.label(text=f"已选：{ke.operator_label_zh(chosen)}", icon="CHECKMARK")
    layout.prop(wm, "piebind_op_choice", text="操作符 ID")


def _slot_summary(slot):
    if not slot:
        return "—"
    return (slot.get("text") or ke.operator_label(slot.get("idname", "")) or "?")[:10]


def _draw_compass(layout, wm, pie_data):
    """3x3 罗盘：点击方位即选中该槽。"""
    slots = (pie_data or {}).get("slots") or {}
    selected = wm.piebind_slot_pos
    grid = layout.grid_flow(row_major=True, columns=3, even_columns=True, even_rows=True, align=True)
    order = ("NW", "N", "NE", "W", None, "E", "SW", "S", "SE")
    for pos in order:
        if pos is None:
            box = grid.box()
            box.label(text=(pie_data or {}).get("label", "（饼）")[:12], icon="MESH_CIRCLE")
            box.label(text="← 点击方位选择槽 →")
            continue
        cell = grid.column(align=True)
        cell.scale_y = 0.9
        op = cell.operator(
            "piebind.select_slot",
            text=f"{pos}  {_slot_summary(slots.get(pos))}",
            depress=(pos == selected),
        )
        op.pos = pos


def _draw_health(layout, data):
    rows = ke.scan_all_plugin_bindings()
    own = data.get("bindings", [])
    own_keys = set()
    for b in own:
        if not b.get("enabled", True):
            continue
        spec = b.get("keymap") or {}
        own_keys.add((spec.get("name"), spec.get("space"), ke.key_label(b.get("key") or {})))

    box = layout.box()
    header = box.row(align=True)
    header.label(text=f"本机插件键位（{len(rows)} 条）", icon="PRESET")
    header.operator("piebind.refresh_health", text="", icon="FILE_REFRESH")

    if not rows:
        box.label(text="未检测到插件注册的键位")
        return

    owners = Counter(r["owner"] for r in rows)
    box.label(text="来源：" + "、".join(f"{k}×{v}" for k, v in owners.most_common(6)))

    overlap = 0
    for row in rows[:24]:
        hit = (row["keymap"], row["space"], row["key"]) in own_keys
        if hit:
            overlap += 1
        line = box.row(align=True)
        if hit:
            line.label(text="⚠", icon="ERROR")
        line.label(text=row["key"])
        line.label(text=row["keymap"])
        line.label(text=row["owner"])
    if overlap:
        box.label(text=f"其中 {overlap} 条与你的绑定同键（如不需要请改键）", icon="ERROR")


# ------------------------------------------------------------------ io ops
class PIEBIND_OT_export_config(bpy.types.Operator, ExportHelper):
    bl_idname = "piebind.export_config"
    bl_label = "导出配置"
    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            with open(self.filepath, "w", encoding="utf-8") as fh:
                json.dump(config.load(), fh, ensure_ascii=False, indent=1)
        except Exception as exc:
            self.report({"ERROR"}, f"导出失败：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已导出：{self.filepath}")
        return {"FINISHED"}


class PIEBIND_OT_import_config(bpy.types.Operator, ImportHelper):
    bl_idname = "piebind.import_config"
    bl_label = "导入配置"
    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            with open(self.filepath, "r", encoding="utf-8") as fh:
                data = config._coerce(json.load(fh))
            config.save(data)
            ke.apply(data)
        except Exception as exc:
            self.report({"ERROR"}, f"导入失败：{exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"已导入：{self.filepath}")
        return {"FINISHED"}


class PIEBIND_OT_refresh_health(bpy.types.Operator):
    bl_idname = "piebind.refresh_health"
    bl_label = "重新扫描"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context):
        ke.invalidate_cache()
        context.window_manager.piebind_status = "已重新扫描本机键位"
        return {"FINISHED"}


# ------------------------------------------------------------------ panel
class PIEBIND_AP_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        data = config.load()
        bindings = data.get("bindings", [])
        pies = data.get("pies", [])
        dups = ke.duplicate_bindings(data)

        # ---------- 状态 ----------
        box = layout.box()
        row = box.row(align=True)
        row.label(
            text=f"已应用 {len(ke.APPLIED['items'])} · 静音 {len(ke.APPLIED['muted'])} · 绑定 {len(bindings)}",
            icon="KEYINGSET",
        )
        row.operator("piebind.apply", text="应用", icon="PLAY")
        row.operator("piebind.unapply", text="全部复原", icon="LOOP_BACK")
        row = box.row(align=True)
        row.operator("piebind.export_config", text="导出", icon="EXPORT")
        row.operator("piebind.import_config", text="导入", icon="IMPORT")
        row.operator("piebind.copy_diagnostics", text="诊断", icon="COPYDOWN")
        if dups:
            box.label(text=f"⚠ 有 {len(dups)} 组绑定互相撞键：{dups[0]['key']}", icon="ERROR")
        if wm.piebind_status:
            box.label(text=wm.piebind_status, icon="INFO")

        # ---------- 绑定列表 ----------
        box = layout.box()
        box.label(text=f"绑定（{len(bindings)}）", icon="HAND")
        if not bindings:
            box.label(text="还没有绑定。先在下方捕获一个键位。")
        ordered = sorted(
            bindings,
            key=lambda b: ((b.get("keymap") or {}).get("name", ""), ke.key_label(b.get("key") or {})),
        )
        for binding in ordered:
            conflicts = _conflict_of(binding)
            enabled = binding.get("enabled", True)
            row = box.row(align=True)
            op = row.operator(
                "piebind.toggle_binding", text="",
                icon="CHECKBOX_HLT" if enabled else "CHECKBOX_DEHLT",
            )
            op.binding_id = binding["id"]
            row.label(text=ke.key_label(binding.get("key") or {}))
            km = binding.get("keymap") or {}
            row.label(text=f"[{km.get('name', '?')}]")
            row.label(text=_target_label(data, binding))
            if conflicts:
                level = _worst(conflicts)
                row.label(text=f"⚠{len(conflicts)}", icon=SEVERITY_ICON.get(level, "INFO"))
            if binding.get("force_override"):
                row.label(text="", icon="LOCKED")
            op = row.operator("piebind.capture_key", text="", icon="REC")
            op.binding_id = binding["id"]
            op = row.operator("piebind.delete_binding", text="", icon="X")
            op.binding_id = binding["id"]
            if conflicts:
                owners = "、".join(sorted({c["owner"] for c in conflicts}))[:40]
                box.label(text=f"    └ 被 {owners} 占用", icon=SEVERITY_ICON.get(_worst(conflicts), "INFO"))

        # ---------- 新建绑定 ----------
        box = layout.box()
        box.label(text="新建绑定", icon="ADD")
        row = box.row(align=True)
        row.label(text="键位：")
        row.label(text=wm.piebind_capture_label or "（未捕获）")
        row.operator("piebind.capture_key", text="捕获", icon="REC")
        row = box.row(align=True)
        row.prop(wm, "piebind_key_manual", text="手动键位")
        row.operator("piebind.apply_manual_key", text="应用", icon="CHECKMARK")
        row = box.row(align=True)
        row.prop(wm, "piebind_keymap", text="Keymap")
        row = box.row(align=True)
        row.prop(wm, "piebind_target_kind", expand=True)
        if wm.piebind_target_kind == "pie":
            box.label(text="目标饼（点一下选中）：")
            col = box.column(align=True)
            for item in pies:
                op = col.operator(
                    "piebind.select_pie",
                    text=item.get("label") or item["id"],
                    depress=(item["id"] == wm.piebind_pie),
                )
                op.pie_id = item["id"]
            if not pies:
                box.label(text="还没有饼，先在下方新建", icon="INFO")
            elif not wm.piebind_pie:
                box.label(text="请点上面的饼名选中它", icon="INFO")
        else:
            _draw_operator_picker(box, wm)
        box.prop(wm, "piebind_force_override")
        box.prop(wm, "piebind_restrict_view3d")

        if wm.piebind_key_json:
            try:
                key = json.loads(wm.piebind_key_json)
            except Exception:
                key = None
            if key:
                spec = ops.split_keymap_identifier(wm.piebind_keymap)
                occupants = ke.scan_conflict(spec, key) if spec else []
                if occupants:
                    warn = box.box()
                    warn.label(text=f"⚠ 该键位已被 {len(occupants)} 条占用：", icon="ERROR")
                    for occ in occupants[:4]:
                        warn.label(text=f"· {occ['owner']} — {occ['label']}（{occ['layer']}）")
                    if not wm.piebind_force_override:
                        warn.label(text="未勾选强制覆盖 → 这条绑定很可能不会生效", icon="INFO")
                else:
                    box.label(text="该键位当前无冲突", icon="CHECKMARK")
        box.operator("piebind.create_binding", text="保存绑定", icon="ADD")

        # ---------- 饼菜单 ----------
        box = layout.box()
        box.label(text=f"饼菜单（{len(pies)}）", icon="MESH_CIRCLE")
        row = box.row(align=True)
        row.prop(wm, "piebind_new_pie_label", text="名称")
        row.operator("piebind.create_pie", text="新建饼", icon="ADD")

        if pies:
            box.label(text="选择要编辑的饼：")
            col = box.column(align=True)
            for item in pies:
                op = col.operator(
                    "piebind.select_pie",
                    text=item.get("label") or item["id"],
                    depress=(item["id"] == wm.piebind_pie),
                )
                op.pie_id = item["id"]
            row = box.row(align=True)
            op = row.operator("piebind.test_pie", text="预览当前饼", icon="PLAY")
            op.pie_id = wm.piebind_pie
            current = config.find_pie(data, wm.piebind_pie)
            if current:
                _draw_compass(box, wm, current)

                editor = box.box()
                editor.label(text=f"编辑槽位 · {pie.SLOT_LABELS[wm.piebind_slot_pos]}", icon="EDIT")
                editor.prop(wm, "piebind_slot_pos", text="方位")
                editor.prop(wm, "piebind_slot_mode", text="模式")
                if getattr(wm, "piebind_slot_mode", "AUTO") != "AUTO":
                    editor.label(text="已选模式：将写入 object.mode_set（忽略下面的操作符）", icon="INFO")
                _draw_operator_picker(editor, wm)
                editor.prop(wm, "piebind_slot_props", text="属性 JSON")
                row = editor.row(align=True)
                row.prop(wm, "piebind_slot_text", text="文字")
                row.prop(wm, "piebind_slot_icon", text="图标")
                row2 = editor.row(align=True)
                row2.operator("piebind.add_slot", text="写入槽位", icon="ADD")
                op = row2.operator("piebind.remove_slot", text="清空", icon="X")
                op.pie_id = current["id"]
                op.pos = wm.piebind_slot_pos

        # ---------- 体检 ----------
        _draw_health(layout, data)


CLASSES = (
    PIEBIND_OT_export_config,
    PIEBIND_OT_import_config,
    PIEBIND_OT_refresh_health,
    PIEBIND_AP_Preferences,
)