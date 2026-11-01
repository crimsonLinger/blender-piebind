# PieBind

**Keymap inspection, reversible overrides and lightweight pie menus for Blender 4.2+.**

PieBind answers a question Blender's own Keymap editor never answers: *"which add-on is
holding this shortcut?"* — then lets you take the key, and put everything back exactly as it
was, in one click.

[中文说明](README_zh.md)

## Why

- Blender add-on keymaps have the **lowest priority**. A new shortcut silently loses to the
  built-in one, and you have to hunt down the conflicting entry by hand.
- Nothing in Blender tells you **who** registered a shortcut. When five add-ons fight over
  `Alt+E`, you find out by pressing it.
- Manual overrides are **one-way**: once you disable a built-in entry you must remember what
  you disabled, for every add-on, forever.

PieBind makes all three visible, and reversible.

## Features

- **Conflict inspector** — scan all keymap layers (`Blender`, `Blender user`, `Blender addon`),
  attribute each entry to the add-on that owns it, and flag what your bindings will shadow.
- **Reversible override** — muting a conflicting entry is journaled. Disable the add-on,
  crash Blender, or press *Restore all*: the original shortcut comes back.
- **Lightweight pies** — up to 8 slots on one key, compass editing, icons, text, and
  automatic greying when the operator isn't available in the current context.
- **Rebind anything** — point any key at any operator, in any keymap (3D View, Mesh, Sculpt,
  Dopesheet, …), with per-binding "force override".
- **Portable config** — export/import a JSON profile; per-binding enable/disable.
- **Agent-ready API** — a single `api.call(action, **kwargs)` entry point with `dry_run`
  support, structured errors and a self-describing catalogue.

## Install

Blender 4.2 or newer (developed and tested against 5.2 LTS).

1. Download `piebind-<version>.zip` from [Releases](../../releases).
2. `Edit > Preferences > Add-ons > Install from Disk…` (Blender 4.2+) and pick the zip.
3. Enable **PieBind**, then open its preferences: `Preferences > Add-ons > PieBind`.

For development you can also copy `src/piebind` into
`<user>/extensions/user_default/piebind` (or add `src` to `sys.path` for tests).

## Quick start

1. In PieBind preferences, press **Capture** and press the key you want (e.g. `Alt+E`).
2. Pick a **Keymap** (e.g. `3D View`), then pick a target: an operator, or a pie menu.
3. If the key is already taken, PieBind lists the owner and what it does.
   Tick **Force override** to take the key anyway.
4. Press **Save binding** — it is applied immediately and journaled.

Build a pie: **New pie** → click a compass cell → search an operator → **Write slot**.
Preview it with **Preview**, then bind it like any other target.

## Honest limitations

- Overriding mutates Blender's keymap state. PieBind journals every change, but a *hard*
  crash while an override is active is recovered on the next start from the journal file.
- Conflict detection is *static*: Blender resolves shortcuts at runtime through `poll()`, so a
  same-key entry may be context-specific. PieBind marks those as **warning** instead of
  **blocker**.
- Add-ons that register shortcuts lazily (only after a user action) are not visible until
  they do. Press **Rescan** in the inspector after enabling such an add-on.
- PieBind is **not** a Pie Menu Editor replacement: no macros, no nested menus, no Python
  actions. It aims to be small, inspectable and reversible.

## Agent API

Inside Blender (no network, no MCP required):

```python
import piebind.api as api

api.call("describe")                                  # self-describing catalogue
api.call("search_operators", query="bevel", limit=5)
api.call("create_pie", label="Modeling", slots=[
    {"pos": "W", "idname": "mesh.bevel", "text": "Bevel"},
    {"pos": "N", "idname": "mesh.fill_holes", "text": "Fill"},
])
api.call("check_conflict", keymap="3D View", key={"type": "E", "alt": True})
api.call("bind", keymap="3D View", key={"type": "E", "alt": True},
         target={"kind": "pie", "id": "pie_xxx"}, force_override=True, dry_run=True)
api.call("apply")
api.call("unapply")                                   # full restore
```

Every call returns `{"ok": bool, "data": ...}` or
`{"ok": false, "error": {"code", "message", "hint"}}`.

## Diagnostics

`Preferences > Add-ons > PieBind > Diagnostics` copies an environment snapshot (Blender
version, keymap layer sizes, attributed add-on bindings, your bindings, duplicates) with
local paths redacted. Please attach it to bug reports.

## Development

```bash
# headless end-to-end tests (40 checks)
blender -b --factory-startup --python-exit-code 1 --python tests/run_headless.py

# build + validate the extension package into dist/
blender --command extension build --source-dir src/piebind --output-dir dist
blender --command extension validate dist/piebind-*.zip
```

CI runs the same tests against Blender 4.2 / 4.5 / 5.2 (see `.github/workflows/ci.yml`).

Layout:

```
src/piebind/          add-on source (extension root)
  __init__.py         registration, deferred apply, journal reconciliation
  config.py           JSON storage, atomic writes, backups
  keymap_engine.py    apply / mute / restore / conflict scan / attribution
  pie.py              single static pie menu class
  ops.py              capture, apply, restore, CRUD operators
  ui.py               preferences panel, compass editor, inspector
  api.py              in-process agent API
  diagnostics.py      issue-ready environment snapshot
tests/                headless tests + GUI override probe
```

## Roadmap

- v0.1 — inspection, reversible overrides, 8-slot pies, agent API *(current)*
- v0.2 — macros, nested menus, operator property forms
- v0.3 — optional MCP bridge (separate package; the add-on itself stays network-free)

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).