# Development

PieBind is a pure-`bpy` Blender extension: no third-party packages and no build step for the
add-on itself. Everything below runs with the Blender binary you already have.

## Requirements

- Blender 4.2 or newer (developed and tested against 5.2 LTS).
- Python 3.11+ (bundled with Blender).
- PowerShell for the helper scripts is optional — the plain `blender` commands work anywhere.

## Run the tests

```bash
# end-to-end checks (149 assertions): config schema, keymap engine, dispatch, presets, UI callbacks
blender -b --factory-startup --python-exit-code 1 --python tests/run_headless.py

# operator/menu smoke harness: every operator, every menu, all four preference tabs
blender -b --factory-startup --python-exit-code 1 --python tests/run_smoke_ops.py
```

Both run without a display and exit non-zero on the first failed assertion.

## Build the extension package

```bash
pwsh -File scripts/build.ps1
# or point at a specific binary / set BLENDER:
pwsh -File scripts/build.ps1 -Blender /path/to/blender
```

Output: `dist/piebind-<version>.zip`, validated with `blender --command extension validate`.

If you invoke Blender directly instead of the script, create the output folder first
(`mkdir -p dist`): the build writes `dist/.<name>.zip` before renaming it, and fails if `dist/`
does not exist.

## Install a development copy

Copy `src/piebind` into `extensions/user_default/piebind` inside your Blender config directory,
or add `src` to `sys.path` when running tests and probes.

## GUI probes

`tests/gui_probe_*.py` are one-off scripts that open Blender, drive the preferences panel and
save screenshots under `.probe/`. Run them with:

```bash
blender --python tests/gui_probe_slot_info.py
```

They need a display and are not part of CI.

## Project layout

```
src/piebind/   add-on source (extension root)
  core/        pure data + engines (config, keymap, keyspec, pies, presets)
  ops/         operators (capture, bindings, pie_ops, dispatch, sidekeys, …)
  ui/          preferences panel, pickers, widgets
  api.py       in-process agent API
tests/         headless tests, smoke harness, GUI probes
scripts/       packaging (build.ps1)
docs/          design notes and the development log
```

## CI

`.github/workflows/ci.yml` runs the headless suite and the smoke harness against Blender
4.2 / 4.5 / 5.2 on Ubuntu, then builds and validates the extension package.

## Notes

- Key configurations differ between Blender versions; the headless suite starts with
  `--factory-startup`, so anything depending on a user keymap must be tested through the GUI
  probes.
- The extension writes its JSON config to Blender's user config folder; tests override it with
  the `PIEBIND_CONFIG_DIR` environment variable.