# Flet 0.80.0+ Development Rules

**This document exists to prevent common deprecation issues and syntax pitfalls when developing Flet applications.**

Always refer to these guidelines when making UI modifications in Flet. 

## 1. Do NOT use `ft.colors` property access for String Colors
Flet 0.80.0 deprecated `ft.colors.XXX` properties. 
**Incorrect:** `bgcolor=ft.colors.BLUE_50`
**Incorrect:** `bgcolor=ft.colors.PRIMARY`
**Correct (String):** `bgcolor="blue_50"`
**Correct (String):** `bgcolor="primary"`
**Correct (Hex):** `bgcolor="#EFF6FF"`
If you need colors with opacity, avoid `ft.colors.with_opacity`, and instead use standard Hex Strings containing the alpha channel: `shadow.color="#66BFDBFE"` (approximately 40% opacity on `#BFDBFE`).

## 2. Do NOT use `ft.MaterialState`
Flet 0.80.0 removed the `MaterialState` class entirely. It is superseded by `ControlState`.
**Incorrect:** `bgcolor={ft.MaterialState.HOVERED: "blue_700", "": "primary"}`
**Correct:** `bgcolor={ft.ControlState.HOVERED: "blue_700", "": "primary"}`

## 3. Do NOT use `ft.ElevatedButton`, `ft.TextButton`, etc. when styling advanced properties
Use the generic `ft.Button` class as the newer, more unified paradigm. Though old classes partially work, they are slated for deprecation and removal.

## 4. Alignment Attributes
`ft.alignment.center` and similar alignment class variables throw `AttributeError`. They should be constructed manually.
**Incorrect:** `alignment=ft.alignment.center`
**Correct:** `alignment=ft.Alignment(0, 0)` (Center)
**Correct:** `alignment=ft.Alignment(-1, 0)` (Center-Left)
**Correct:** `alignment=ft.Alignment(1, 0)` (Center-Right)

## 5. Main Loop Initialization
Avoid using `ft.app(target=main)`, as it triggers a `DeprecationWarning`. 
Use `ft.run(main)` to boot the GUI instead.

## 6. Global State Dictionaries Initialization
When defining global state dictionaries (e.g., `task_stats`) that are updated selectively or incrementally throughout the app's lifecycle, **always initialize them with all expected keys preemptively**.
**Incorrect:** `task_stats = {"total": 0}` (and assuming `steps` will be added via `.update()` later, which fails under `+=` operations)
**Correct:** `task_stats = {"total": 0, "done": 0, "success": 0, "fail": 0, "steps": 0}` 
This avoids random `KeyError` exceptions when certain application paths perform mathematical accumulations (`+=`) directly on fields like `steps` before they were dynamically injected.

## General Coding Standards
- Flet components with explicit dimensions should utilize `dense=True` and `content_padding` tightly.
- Use explicit UI threads / Locks `_ui.flush_now()` and `_ui.request()` when dealing with background modifications for `TaskRow`s instead of pure inline `page.update()` to avoid overlapping component state modifications.
