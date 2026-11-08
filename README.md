# HotBox

A popup under the mouse with buttons for your own Python scripts in Houdini 21+.
HotBox is an orchestrator: it doesn't do anything by itself, it finds the scripts in `lib/`, shows the ones that fit
what you are doing and runs them.

![dino](icons/dino.jpg)

## What it shows

| Selection | Folder | Columns |
|---|---|---|
| nothing | `lib/all/` | scripts of the current network type (`Sop/`, `Lop/`, `Object/`, `Driver/`…) + root scripts |
| several nodes | `lib/multiple/` | scripts of the network type + root scripts |
| one node | `lib/single/` | scripts of the node type (`cam/`, `null/`…) + root scripts |

Deeper folders (`lib/all/Lop/Instances/`) are not shown.

Bottom row: open the HotBox folder · current context (click to close) · Script Manager.
`Esc` or `` ` `` closes the hotbox. Clicking a button or pressing its hotkey closes the hotbox and runs the script.
Everything a script does is one undo step.

## Adding a script

Drop a `.py` file into the right folder. Its button is described by the first comment lines:

```python
#label:Create Null
#textcolor:#ff8b48
#buttoncolor:#22253b
#icon:app_dino_dance.svg
#hotkey:n

import hou
...
```

All keys are optional (the label defaults to the file name, icons are looked up in `icons/`).
The script runs as `__main__`, `sys.exit()` just stops it, errors are printed to the console and shown in the status bar.

Headers are read from the files every time the hotbox opens: nothing is cached, nothing is written into the tool folder.
The folder can be copied from user to user as is.

> Older versions kept a `lib/<mode>/schema.json` cache with absolute paths of the machine it was created on, and it
> had to be deleted after copying the tool to another user. It isn't used any more: delete leftover `schema.json`
> files, they are ignored by git.

## Install

Put the `hotbox` folder into `python3.11libs` of your Houdini preferences or package
(e.g. `~/houdini21.0/python3.11libs/hotbox`). Hotkey or shelf tool:

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
uv run ruff check __init__.py main.py utils tests
```
