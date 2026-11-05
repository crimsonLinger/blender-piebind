"""操作符参数预设：把常用「属性 JSON」做成下拉选项。

不改变存储格式——预设只是把 JSON 填进 `piebind_slot_props`，用户仍可手改。
覆盖不到的冷门操作符，会按 RNA 枚举属性自动生成条目（最多 2 个属性 × 16 项）。
"""

import bpy

# idname -> [(值标识, 中文标签, props)]；命中这里就不走自动枚举
STATIC = {
    "view3d.view_axis": [
        ("TOP", "顶视图", {"type": "TOP"}),
        ("BOTTOM", "底视图", {"type": "BOTTOM"}),
        ("FRONT", "正视图", {"type": "FRONT"}),
        ("BACK", "后视图", {"type": "BACK"}),
        ("LEFT", "左视图", {"type": "LEFT"}),
        ("RIGHT", "右视图", {"type": "RIGHT"}),
    ],
    "object.mode_set": [
        ("OBJECT", "物体模式", {"mode": "OBJECT"}),
        ("EDIT", "编辑模式", {"mode": "EDIT"}),
        ("POSE", "姿态模式", {"mode": "POSE"}),
        ("SCULPT", "雕刻模式", {"mode": "SCULPT"}),
        ("VERTEX_PAINT", "顶点绘制", {"mode": "VERTEX_PAINT"}),
        ("WEIGHT_PAINT", "权重绘制", {"mode": "WEIGHT_PAINT"}),
        ("TEXTURE_PAINT", "纹理绘制", {"mode": "TEXTURE_PAINT"}),
    ],
    "object.hide_view_set": [
        ("SELECTED", "隐藏所选（H）", {"unselected": False}),
        ("UNSELECTED", "隐藏未选中（Shift+H）", {"unselected": True}),
    ],
    "object.hide_view_clear": [
        ("ALL", "显示全部（Alt+H）", {}),
        ("ALL_SELECT", "显示全部并选中", {"select": True}),
    ],
}


def static_presets(idname):
    rows = []
    for value, label, props in STATIC.get(idname or "", ()):
        rows.append({
            "key": value,
            "label": label,
            "text": label,
            "props": dict(props),
        })
    return rows


def rna_presets(idname, max_items=16, max_props=2):
    """从操作符的 RNA 属性反推可选参数（枚举 + 布尔），作为冷门操作符的兜底。"""
    if not idname or "." not in idname:
        return []
    mod_name, op_name = idname.split(".", 1)
    try:
        rna = getattr(getattr(bpy.ops, mod_name), op_name).get_rna_type()
    except Exception:
        return []

    rows = []
    used_props = 0
    for prop in rna.properties:
        if prop.identifier == "rna_type" or used_props >= max_props:
            continue
        if prop.type == "BOOLEAN":
            used_props += 1
            for value, suffix in ((False, "否"), (True, "是")):
                rows.append({
                    "key": f"{prop.identifier}:{str(value).lower()}",
                    "label": f"{prop.name}：{suffix}",
                    "text": "",
                    "props": {prop.identifier: value},
                })
            continue
        if prop.type != "ENUM":
            continue
        try:
            items = list(prop.enum_items)
        except Exception:
            continue
        if not items or len(items) > max_items:
            continue
        used_props += 1
        for item in items:
            rows.append({
                "key": f"{prop.identifier}:{item.identifier}",
                "label": f"{prop.name}：{item.name}",
                "text": item.name,
                "props": {prop.identifier: item.identifier},
            })
    return rows


def presets_for(idname):
    """返回某项操作符可用的参数预设；没有则返回空列表。"""
    rows = static_presets(idname)
    return rows if rows else rna_presets(idname)


def label_for(idname, props):
    """按 props 反查预设标签（面板按钮回显用）。"""
    if not props:
        return ""
    for row in presets_for(idname):
        if row.get("props") == props:
            return row["label"]
    return ""