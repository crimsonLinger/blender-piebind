# PieBind 设计说明

> 目标：在不破坏 Blender 默认键位的前提下，把「多个功能」收进一个饼菜单，
> 并让被接管的键位可以一键复原。

## 1. 分层

```
ui/     只画界面，不直接改键位             （prefs / pickers / widgets / io_ops）
ops/    Blender 操作符：捕获、CRUD、分发    （capture / bindings / pie_ops / dispatch ...）
core/   纯数据与引擎，不依赖界面            （config / keymap / keyspec / pies）
api.py  进程内 Agent API（薄封装，调用 core + ops）
```

依赖方向单向：`ui → ops → core`。`core` 不 import `ops`/`ui`。

**兼容层**：根目录 `config.py` / `keymap_engine.py` / `pie.py` 是 PEP 562 别名模块，
0.1.x 的导入路径继续可用，计划 0.3 移除。

## 2. 数据模型（schema v2）

```json
{
  "schema_version": 2,
  "settings": {
    "default_keymap": "<JSON [name, space, region]>",
    "force_override": false,
    "restrict_view3d": true
  },
  "pies": [
    {"id": "pie_x", "label": "模式", "slots": {
      "W": {"kind": "operator", "idname": "object.mode_set",
            "text": "编辑模式", "icon": "NONE", "props": {"mode": "EDIT"}}
    }}
  ],
  "bindings": [
    {"id": "bd_x", "enabled": true, "force_override": true,
     "keymap": {"name": "Object Non-modal", "space": "EMPTY", "region": "WINDOW",
                "area": "VIEW_3D"},
     "key": {"type": "TAB", "value": "PRESS", "ctrl": false, "shift": false,
             "alt": false, "oskey": false, "any": false, "key_modifier": "NONE"},
     "target": {"kind": "pie", "id": "pie_x", "props": {}}}
  ]
}
```

- 迁移：`_migrate()` 按 `schema_version` 补齐 `settings`，未知版本保持原样。
- 写盘：临时文件 + 原子替换 + 最多 5 份备份。
- 运行期状态（应用了什么、接管了哪些条目）落在 `owned.json` / `journal.json`。

## 3. 键位接管策略

| 模式 | 做法 | 复原 |
|---|---|---|
| 普通绑定 | 在 `active/Window` 新建条目，按 `keymap.space` 与 `area` 过滤 | 删除该条目 |
| 强制覆盖 | **就地改写**命中的原条目：`idname → piebind.dispatch` + `binding_id` | 按 journal 写回 `orig_idname` 与原始属性 |

覆盖时的匹配顺序：
1. 用户所选 keymap；
2. 若一条没命中，回退到**同空间或全局（EMPTY）** keymap（例如 `Tab` 实际在 `Object Non-modal`）。

> 实测结论：区域 keymap 里被静音（`active=False`）的条目**仍会消费按键**，
> 所以覆盖只能就地改写，不能靠“静音 + 新建条目”。

## 4. 分发链路

```
按键 → 键位条目(idname=piebind.dispatch) → PIEBIND_OT_dispatch
     → 读 binding（id / target）
     → target.kind == "pie" ? wm.call_menu_pie(PIEBIND_MT_pie)
                             : bpy.ops.<operator>(INVOKE_DEFAULT)
```

饼菜单是**单一静态 Menu 类**，调用前把 `pie_id` 写进 `PIE_STATE`；
绘制用 `layout.menu_pie()` + 8 次（操作符或 `separator()`）占位，
顺序固定 `W, E, S, N, NW, NE, SW, SE`。

## 5. 冲突检测

- 两层：`keymap`（区域 keymap 内同键）与**全局扫描**（`scan_key_owners`，跨所有 keymap）。
- 归属判定：操作符 `__module__` → `preferences.addons` 反查插件名，识别“Blender 内置 / 某插件”。
- 自检（绑定行 `?`）输出：键位、keymap、接管条目数、冲突数、饼槽位数，以及
  “实际绑在哪个 keymap”的提示。

已知局限：尚未校验**对象模式**（Object/Edit/Sculpt），`Mesh`、`Sculpt` 类 keymap 会偏宽松。

## 6. 界面结构

```
[状态条]  已应用 N · 绑定 N · 饼 N        [应用] [复原]
[页签]    绑定 | 饼菜单 | 设置 | 体检

绑定：列表（勾选 / 键位 / keymap / 目标 / 冲突 / 自检 / 改键 / 删除）
      + 折叠「新建绑定」（键位 → keymap → 目标 → 覆盖选项 → 冲突预览 → 保存）
饼菜单：饼下拉 + 新建/删除 → 罗盘 3x3 → 已填槽位 → 槽位编辑器 → 预览
设置：默认值（keymap / 强制覆盖 / 仅 3D 视口）、导入导出、配置目录、关于
体检：本机插件键位扫描 + 重新扫描
```

设计原则：
- 页签切换用静态 `EnumProperty`（`piebind_tab`），避免动态枚举在下拉里不刷新；
- 所有“下拉选择”都是 `Menu` 类，不用动态 `EnumProperty` 承载可变列表；
- 面板只读配置，写操作一律走操作符（可撤销、可报告错误）。

## 7. 已知问题与下一步

1. 模式级限制（`mode` 字段）未实现 → v0.2；
2. 槽位只支持 operator 与 mode 快捷，未支持子菜单 / 宏 → v0.2；
3. 兼容别名层待移除；
4. 饼菜单目前无法在自动化截图中验证排布，需要人工确认。