# HotBox

A popup under the mouse with buttons for your own Python scripts in Houdini 21+.
Inspired by [W_hotbox](https://github.com/melMass/W_hotbox) for Nuke (the idea of the hotbox and the Script Manager),
written from scratch for Houdini.
HotBox is an orchestrator: it doesn't do anything by itself, it finds the scripts in `lib/`, shows the ones that fit
what you are doing and runs them.

<p align="center">
  <img src="docs/menu.png" width="49%" alt="HotBox with one camera selected">
  <img src="docs/hover.gif" width="49%" alt="Hover wave and zoom">
</p>

## What it shows

| Selection | Folder | Columns |
|---|---|---|
| nothing | `lib/all/` | scripts of the current network type (`Sop/`, `Lop/`, `Object/`, `Driver/`…) + root scripts |
| several nodes | `lib/multiple/` | scripts of the network type + root scripts |
| one node | `lib/single/` | scripts of the node type (`cam/`, `null/`…) + root scripts |

Deeper folders (`lib/all/Lop/Instances/`) are not shown.

Buttons go top to bottom in columns (context scripts, then root scripts), at most 6 per column, and all
columns share one grid, so rows are on the same level. Single buttons and `#group` blocks are sorted by group name /
label (not by file names). A group is a framed block with a caption; it is never split between columns; a group with
one button is a plain button.

Bottom row: open the HotBox folder · current context (click to close) · Script Manager.
`Esc` or `` ` `` closes the hotbox, so does a click anywhere that is not a button (outside or between buttons). Clicking a button or pressing its hotkey closes the hotbox and runs the script.
Hotkeys work in the Russian keyboard layout too (the same physical key: `f` = `а`).
Everything a script does is one undo step.

**Shift**: buttons with a `#shiftlabel` show what they do on Shift+click (Object Merge Relative → Absolute).
**Tab** starts search: type a part of a label (in any keyboard layout), the other buttons fade out, `Enter` runs the
first match, `Esc` or `Tab` ends the search.
**Recent**: a row with the last 4 scripts you ran that fit the current selection/network.

Animations: on opening the buttons grow in from their centers with a small spring, starting at the cursor and
spreading outwards (farther buttons come a bit later). On hover a white wave spreads from the cursor, the button gets lighter and a bit bigger (with the text).
On click or hotkey the button grows and fades out while the whole menu fades out, then the script runs.

## Adding a script

Drop a `.py` file into the right folder. Its button is described by the first comment lines:

```python
#label:Create Null
#textcolor:#ff8b48
#buttoncolor:#22253b
#icon:app_dino_dance.svg
#hotkey:n
#group:Nodes

import hou
...
```

Write scripts for any number of selected nodes (`for node in hou.selectedNodes()`): then one script serves
`lib/single/` and `lib/multiple/`.

### The same tool in another mode: `#ref`

A file with only a header runs another script from `lib/`:

```python
#ref:single/create_null.py
#hotkey:n
```

It takes the label, colors, icon and group of the target (its own header overrides them); the hotkey is not
inherited, choose it per context. A broken reference (file renamed, loop) shows a red button with the reason
in the tooltip; the tests check every `#ref` in `lib/`.

![Script Manager](docs/manager.png)

Or edit them in the **Script Manager** (bottom right button, the DinoWrite look, with a live animated preview of
the button): it writes the header back into the script and warns
about hotkeys already used by scripts shown together with it and about missing icons. For a `#ref` it edits only
the reference's own header (inherited values are shown greyed out); the **Ref** field sets or changes the target.
Ref and Package complete existing values inline (Tab accepts), the arrow next to them lists them.
**Code ›** slides out a code editor (Python highlighting): the script's code, or the target's code for a `#ref`;
Save writes the header and the code.

All keys are optional (the label defaults to the file name). `#icon` is a file in `icons/` (`save.svg`) or a
Houdini icon name, the one `node.type().icon()` returns (`SOP_attribwrangle`, `SOP_null`, `OBJ_camera`, `LOP_fetch`...).
The script runs as `__main__`, `sys.exit()` just stops it. When it fails, a window shows the error and the traceback;
**Open in Script Manager** opens the script with the failing line highlighted in the code panel.

### Shift+click: a second variant of a script

```python
#label:Object Merge Relative
#shiftlabel:Object Merge Absolute

import hotbox
relative = "shift" not in hotbox.modifiers()
```

`hotbox.modifiers()` is the set of keys held on the click or hotkey (`shift`, `ctrl`, `alt`; `ctrl` is Cmd on macOS).
`#shiftlabel` is the button text while Shift is held. One button instead of two: Object Merge, Fetch and
Copy Path (Shift: the file path) work like this.

### Your own scripts: `HOTBOX_PATH`

Keep personal and studio scripts outside the tool folder, so `git pull` never touches them:

```
HOTBOX_PATH = "$HOME/houdini_scripts/hotbox_lib;//server/pipeline/hotbox_lib"
```

Each folder has the same layout as `lib/` (`all/`, `multiple/`, `single/`). Folders are searched in order, the
built-in `lib/` last: a script hides the one with the same path in later folders (your `single/create_null.py`
replaces the built-in one), and `#ref` targets are looked up the same way. The Script Manager marks scripts from
these folders with the folder name; "Open HotBox folder" opens the first one. Separator: `;` (`:` works too on
Linux/macOS).

Recent scripts and the package switches are saved per user in `$HOUDINI_USER_PREF_DIR/hotbox/settings.json`;
`"recent_count": 0` there hides the Recent row.

### Packages: studio specific scripts

Scripts that only make sense at one studio go into a package:

```python
#label:Camera Import
#package:studio-name
```

The gear in the Script Manager title bar lists all packages with a switch each. A turned off package hides its
buttons (and its `#ref`s) from the hotbox; scripts without `#package` are always shown. Several packages:
`#package:studio-name, other-studio` (shown when any of them is on).

<img src="docs/packages_window.png" width="380" alt="Packages">

New packages are **off** by default, so a copied HotBox doesn't show someone else's studio buttons. The choice is
saved per user in `$HOUDINI_USER_PREF_DIR/hotbox/settings.json` (not in the tool folder). A studio can turn
packages on for everyone in `houdini.env`; the user's own switch still wins:

```
HOTBOX_PACKAGES = "studio-name"
```

The studio specific scripts in `lib/` (Camera Import/Export/Setup, Last Alembic Track, Convert to $FILM, Save HIP)
are in packages: turn them on in the gear menu if you need them.

### Shipped scripts

| Where | Scripts |
|---|---|
| everywhere, nothing selected | Flipbook, **Scene**: Missing Files (pick to jump to the nodes), Reload Caches |
| Object, nothing selected | Camera from View (new camera at the viewport view, looks through it) |
| Sop, nothing selected | Object Merge Relative, Shift: Absolute (from node paths in the clipboard) |
| Lop, nothing selected | Fetch Relative (Shift: Absolute), SOP Import (prims at `/geo/<name>`), Material Library + Assign |
| any node(s) selected | Create Vop / Wrangle, Create Null, Convert Paths, Copy Node Path (Shift: File Path), **Network**: Network Box, Color by Type |
| several nodes | Explode Nodes, Object Merge Paste, Frame Range (all of them together) |
| null | Render Node (`RENDER_` geo object under the current one, never on top of other nodes) |
| cam / hlight | Look Through (again: back to perspective), Camera Bake, Frame Range |
| alembic, alembicarchive, filecache, file | Frame Range: scene and playback range from the Alembic animation or the sequence on disk |

### Shared helpers: `common/`

Small pieces several scripts need, split by topic (whole tools stay scripts in `lib/`):

| Module | |
|---|---|
| `common/panes.py` | Network Editor / Scene Viewer under the cursor, status bar warnings |
| `common/nodes.py` | node paths from the clipboard, Object Merge / Fetch / SOP Import at the cursor, attrib VOP/wrangle under the selection, a free spot for a new node |
| `common/paths.py` | file parameters of a node and of the scene, `$JOB`/`$FILM` path conversion, missing files, reload of file nodes |
| `common/frames.py` | frame range of a node: Alembic animation, file sequence on disk, keyframes |

```python
from hotbox.common import paths

paths.convertPaths("$JOB")
```

Headers are read from the files every time the hotbox opens: nothing is cached, nothing is written into the tool folder.
The folder can be copied from user to user as is.

> Older versions kept a `lib/<mode>/schema.json` cache with absolute paths of the machine it was created on, and it
> had to be deleted after copying the tool to another user. It isn't used any more: delete leftover `schema.json`
> files, they are ignored by git.

## Install

**As a Houdini package** (recommended): clone the repo anywhere, then copy `hotbox.json` into
`$HOUDINI_USER_PREF_DIR/packages/` (e.g. `~/houdini21.0/packages/`, create the folder if needed) and set the path:

```json
{"HOTBOX_DIR": "D:/tools/hotbox"}
```

After a Houdini restart there is a **HotBox** shelf with two tools: *HotBox* (give it a hotkey in the Hotkey
Manager, search "HotBox") and *HotBox Scripts* (the Script Manager). Updating is `git pull`; the tool folder has no
personal files.

**By hand**: put the `hotbox` folder into `python3.11libs` of your Houdini preferences
(e.g. `~/houdini21.0/python3.11libs/hotbox`) and make a hotkey or shelf tool:

```python
import hotbox
hotbox.show()
```

Updated code is reloaded automatically on the next `show()` (no Houdini restart). The old
`from hotbox import main; main.start()` still works.

Camera Import / Camera Export use the studio `cam_tools` library: set its folder in `houdini.env`:

```
CAM_TOOLS_PATH = "//<server>/tools/py_libs/camera_exchanger"
```

The Flipbook button runs [DinoWrite](https://github.com/matzubr/DinoWrite), installed next to `hotbox`.

## Development

Houdini imports the folder directly; [uv](https://docs.astral.sh/uv/) is only for dev tooling (Python 3.11 like Houdini 21,
PySide6 for offscreen GUI tests, `hou` is stubbed). The repo folder must be named `hotbox`.

```bash
uv sync
uv run pytest
uv run ruff check __init__.py main.py common utils tests
uv run python docs/make_images.py   # README images (needs ffmpeg)
```

## Credits

Buttons use [Nunito](https://github.com/googlefonts/nunito) ExtraBold (`fonts/`, a static cut of the variable font),
SIL Open Font License 1.1, see `fonts/OFL.txt`.
