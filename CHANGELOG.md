# Changelog

All notable changes to PieBind. This project follows [Semantic Versioning](https://semver.org/).

[中文更新日志](CHANGELOG_zh.md)

## [Unreleased]

### Added

- Operator search results now show the operator's existing Blender shortcut (read-only), e.g.
  `Hide Objects (object.hide_view_set) — H / SHIFT+H`; the selected-operator button shows it
  too. This makes editor-specific operators (`outliner.*`, `node.*`, …) easier to tell apart.
- Parameter presets now include boolean flags, and curated entries for hide/show
  (`隐藏所选（H）`, `隐藏未选中（Shift+H）`, `显示全部（Alt+H）`).
- Search by built-in shortcut: typing `H`, `Shift+H` or `F8` lists the operators bound to that
  key; text search also ranks prefix matches first.
- Operator names are now translated with Blender's `Operator` context, so names that do have a
  Chinese translation (e.g. `隐藏物体`, `框显全部`, `设置物体模式`) are found by Chinese search.

## [0.1.0] — 2026-11-05

First public release.

### Added

- **Keymap inspector** — scans the `Blender`, `Blender user` and `Blender addon` layers,
  attributes every entry to the add-on that owns it, and flags what your bindings will shadow.
- **Reversible force-override** — taking a key rewrites the original entry and journals the
  change; disabling the add-on, pressing *Restore all*, or recovering from a crash puts it back.
- **Lightweight pie menus** — up to 8 slots on one key, compass editing, icons, slot text and
  automatic greying when the operator is unavailable in the current context.
- **Parameter presets** — a dropdown of ready-made operator parameters (view axes, object
  modes) with an RNA enum fallback for other operators.
- **Tabbed preferences panel** — Bindings / Pies / Settings / Health.
- **In-process agent API** — a single `api.call(action, **kwargs)` entry point with `dry_run`,
  structured errors and a self-describing action catalogue.
- **Diagnostics snapshot** for bug reports, with local paths redacted.
- **Packaging and CI** — extension manifest, GPL-3.0-or-later license, GitHub Actions matrix
  for Blender 4.2 / 4.5 / 5.2.

### Changed

- Slot edits are saved automatically (debounced by 0.6 s); the separate *Write slot* button is
  gone.
- Pie menus can be renamed from the preferences panel.
- Choosing a slot loads its current operator, text and parameters into the editor.

### Fixed

- `NameError` when saving a binding, and when opening the keymap dropdown.
- Invalid icon names (`EDIT`, `SAVE`) that broke panel drawing on Blender 5.2.
- A native crash when a pie menu was invoked without a UI (background mode); it is now rejected
  with a message.
- Stale operator parameters leaking between slots; unknown parameters are dropped on save.

### Known issues

- Mouse side buttons (M4/M5) can be captured and displayed, but executing them is best-effort.
- Blender 4.2 compatibility is covered by CI but not exercised by the maintainer.