# PieBind

**Blender 4.2+ 的键位体检、可逆覆盖与轻量饼菜单。**

PieBind 回答的是 Blender 自带键位编辑器永远不回答的问题：**"这个快捷键被哪个插件占了？"**
——然后让你把键拿过来，并且能一键把一切恢复原样。

[English](README.md) · [更新日志](CHANGELOG_zh.md) · [开发文档](DEVELOPMENT.md)

## 为什么

- 插件键位优先级**最低**：新加的快捷键会静默输给内置条目，只能自己一条条翻。
- Blender 不告诉你键位**是谁注册的**。五个插件抢 `Alt+E` 时，你只能靠按下去猜。
- 手动覆盖是**单向**的：禁用了内置条目，就得永远记住自己禁用了什么。

PieBind 把这三件事都变成可见、可回滚的。

## 功能

- **冲突体检**：扫描 `Blender` / `Blender user` / `Blender addon` 三层键位，把每条归属到具体插件，并标出会被你的绑定遮住的条目。
- **可逆覆盖**：静音冲突项时写 journal。禁用插件、Blender 崩溃、点"全部复原"都能拿回原快捷键。
- **轻量饼菜单**：一个键 8 个槽，罗盘点选、图标、文字；当前上下文不可用的槽位自动置灰。
- **任意重绑**：任意 keymap（3D View / Mesh / Sculpt / Dopesheet…）里把任意键指给任意操作符，逐条勾选"强制覆盖"。
- **配置可移植**：JSON 导入导出，逐条启用/停用。
- **给 agent 的 API**：单入口 `api.call(action, **kwargs)`，支持 `dry_run`、结构化错误、自描述动作目录。

## 安装

需要 Blender 4.2 或更高（开发与验证基于 5.2 LTS）。

1. 从 [Releases](../../releases) 下载 `piebind-<version>.zip`。
2. `编辑 > 偏好设置 > 插件 > 从磁盘安装…`（4.2+）选择该 zip。
3. 启用 **PieBind**，然后打开它的偏好设置：`偏好设置 > 插件 > PieBind`。

开发时也可以把 `src/piebind` 复制到 `<user>/extensions/user_default/piebind`，或把 `src` 加进 `sys.path`。

## 快速开始

1. 在 PieBind 面板点 **捕获**，按下你想用的键（例如 `Alt+E`）。
2. 选 **Keymap**（如 `3D View`），再选目标：某个操作符，或某个饼菜单。
3. 若该键已被占用，面板会列出占用者及其功能；勾选 **强制覆盖** 即可强行接管。
4. 点 **保存绑定**，立即生效并写入 journal。

做饼：**新建饼** → 点罗盘某一格 → 搜索操作符 →（可选）**参数** 下拉选预设，改完自动保存；**预览** 确认后，像普通目标一样绑定到键。

## 已知限制（诚实版）

- 覆盖会改动 Blender 的键位状态。PieBind 会 journal 每处改动；若覆盖生效期间发生**硬崩溃**，下次启动会按 journal 自愈。
- 冲突检测是**静态**的：Blender 在运行时用 `poll()` 决定响应哪条，所以同键条目可能只是上下文不同。这类会被标成 **warning** 而非 **blocker**。
- 懒注册的插件（只有用户执行某操作后才注册键位）在注册前不可见；启用这类插件后请点体检页的 **重新扫描**。
- PieBind **不是** Pie Menu Editor 的替代品：没有宏、没有嵌套菜单、没有 Python 动作。它的目标是**小而可查、可回滚**。

## Agent API

在 Blender 内即可使用（不需要网络，也不需要 MCP）：

```python
import piebind.api as api

api.call("describe")                                  # 自描述能力目录
api.call("search_operators", query="bevel", limit=5)
api.call("create_pie", label="建模速取", slots=[
    {"pos": "W", "idname": "mesh.bevel", "text": "倒角"},
    {"pos": "N", "idname": "mesh.fill_holes", "text": "封口"},
])
api.call("check_conflict", keymap="3D View", key={"type": "E", "alt": True})
api.call("bind", keymap="3D View", key={"type": "E", "alt": True},
         target={"kind": "pie", "id": "pie_xxx"}, force_override=True, dry_run=True)
api.call("apply")
api.call("unapply")                                   # 全部复原
```

每次调用返回 `{"ok": bool, "data": ...}` 或
`{"ok": false, "error": {"code", "message", "hint"}}`。

## 诊断导出

`偏好设置 > 插件 > PieBind > 诊断`：复制一份环境快照（Blender 版本、各层键位规模、插件键位归属、你的绑定、重复键），本地路径已脱敏。提 issue 时请附上。

## 开发

完整的贡献者文档（测试、打包、目录结构、CI）见 [DEVELOPMENT.md](DEVELOPMENT.md)。常用命令：

```bash
# headless 端到端测试（见 tests/run_headless.py）
blender -b --factory-startup --python-exit-code 1 --python tests/run_headless.py

# 构建 + 校验扩展包到 dist/
blender --command extension build --source-dir src/piebind --output-dir dist
blender --command extension validate dist/piebind-*.zip
```

CI 会在 Blender 4.2 / 4.5 / 5.2 上跑同一套测试（见 `.github/workflows/ci.yml`）。

## 路线图

- v0.1 — 体检、可逆覆盖、8 槽饼、agent API（当前）
- v0.2 — 宏、嵌套菜单、操作符参数表单
- v0.3 — 可选 MCP 桥接（独立包；插件本体保持零网络）

## 许可

GPL-3.0-or-later，见 [LICENSE](LICENSE)。