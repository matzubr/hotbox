"""README images, rendered offscreen with the real widgets.

    uv run --with pillow python docs/make_images.py

hou is stubbed like in the tests, so Houdini icons (SOP_null, OBJ_camera...) are not drawn.
The images use a copy of lib/ where every package is called 'studio-name': no real studio names in public images.
"""
import builtins
import os
import re
import shutil
import sys
import tempfile
import types
from pathlib import Path

from PIL import Image

# Package settings in a temp file: the user's own choice doesn't change the images
os.environ["HOTBOX_SETTINGS"] = Path(tempfile.mkdtemp(), "hotbox", "settings.json").as_posix()
os.environ.pop("HOTBOX_PACKAGES", None)

DOCS = Path(__file__).resolve().parent
ROOT = DOCS.parent
sys.path.insert(0, (ROOT / "tests").as_posix())
import conftest  # noqa: F401  (hou stub, offscreen Qt, hotbox on sys.path)
from PySide6 import QtWidgets
from PySide6.QtCore import QPointF, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtTest import QTest

BACKGROUND = QColor("#262626")
FRAME_MS = 33
PACKAGE = "studio-name"


def anonymousLibrary() -> Path:
    """Copy of lib/ with every #package renamed to PACKAGE; returns the folder that contains 'lib'"""
    work = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "lib", work / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    for script in (work / "lib").rglob("*.py"):
        text = script.read_text(encoding="utf-8")
        script.write_text(re.sub(r"(?m)^#package:.*$", f"#package:{PACKAGE}", text), encoding="utf-8")
    return work


class Swatch(QtWidgets.QPushButton):
    """Looks like Houdini's color swatch"""

    def setColor(self, color):
        self._color = QColor(color)
        self.setStyleSheet(f"background:{self._color.name()}; border:1px solid #555; border-radius:3px;")

    def color(self):
        return self._color


def onBackground(widget, pad: int = 16) -> QPixmap:
    image = widget.grab()
    result = QPixmap(image.size() + QSize(2 * pad, 2 * pad))
    result.fill(BACKGROUND)
    painter = QPainter(result)
    painter.drawPixmap(pad, pad, image)
    painter.end()
    return result


def main():
    app = QtWidgets.QApplication([])
    main_window = QtWidgets.QWidget()
    hou = sys.modules["hou"]
    hou.qt = types.SimpleNamespace(mainWindow=lambda: main_window, Icon=lambda name: QIcon(),
                                   ColorSwatchButton=Swatch)
    print_ = builtins.print  # Houdini icons are missing here: don't spam about them
    builtins.print = lambda *a, **k: None if a and str(a[0]).startswith("HotBox: no icon") else print_(*a, **k)

    from hotbox import main as hotbox_main
    from hotbox.utils import manager, settings, utility

    work = anonymousLibrary()
    os.chdir(work)  # relative lib path: no personal absolute paths in the File field of a public image
    settings.setPackageEnabled(PACKAGE, True)  # the full camera menu in the images

    utility.detectContext = lambda: utility.Context("single", "cam", "cam", None)
    box = hotbox_main.HotBox(lib_dir=Path("lib"))
    box._fadeAnimation.stop()
    box.setWindowOpacity(1)
    app.processEvents()
    onBackground(box).save((DOCS / "hotbox.png").as_posix())

    # Animation: hover one button, then move to another
    frames = []

    def record(count: int, wait: bool = True):
        for _ in range(count):
            if wait:
                QTest.qWait(FRAME_MS)
            app.processEvents()
            frames.append(onBackground(box).toImage())

    buttons = box.scripts_buttons.buttons
    first, target = buttons[0], buttons[4]
    record(4, wait=False)
    first.startHover(QPointF(30, 40))
    record(14)
    first.endHover()
    target.startHover(QPointF(150, 20))
    record(16)
    record(6, wait=False)
    box.close()
    saveGif(frames, DOCS / "hotbox_animation.gif")

    script_manager = manager.ScriptManager(lib_folder=Path("lib"))
    script_manager._fadeAnimation.stop()
    script_manager.setWindowOpacity(1)
    folders = [script_manager.folders_list.item(i).text() for i in range(script_manager.folders_list.count())]
    script_manager.folders_list.setCurrentRow(folders.index("Object"))
    files = [script_manager.files_list.item(i).text() for i in range(script_manager.files_list.count())]
    script_manager.files_list.setCurrentRow(files.index("save_project.py"))
    QTest.qWait(500)
    app.processEvents()
    onBackground(script_manager, pad=0).save((DOCS / "script_manager.png").as_posix())

    packages = script_manager.openPackages()
    packages._fadeAnimation.stop()
    packages.setWindowOpacity(1)
    QTest.qWait(300)
    app.processEvents()
    onBackground(packages, pad=0).save((DOCS / "packages.png").as_posix())
    os.chdir(ROOT)
    shutil.rmtree(work, ignore_errors=True)
    print("docs images updated")


def saveGif(frames, path: Path):
    """One palette for all frames: per frame palettes made Pillow's frame optimization drop buttons"""
    with tempfile.TemporaryDirectory() as folder:
        images = []
        for index, frame in enumerate(frames):
            png = Path(folder, f"{index:03d}.png")
            frame.save(png.as_posix())
            image = Image.open(png).convert("RGB")
            images.append(image.resize((image.width * 3 // 4, image.height * 3 // 4), Image.LANCZOS))
    # The palette from all frames side by side, so hover colors are in it too
    sheet = Image.new("RGB", (images[0].width, images[0].height * len(images)))
    for index, image in enumerate(images):
        sheet.paste(image, (0, image.height * index))
    palette = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    paletted = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in images]
    durations = [FRAME_MS] * len(paletted)
    durations[-1] = 900
    paletted[0].save(path, save_all=True, append_images=paletted[1:], duration=durations, loop=0, optimize=False,
                     disposal=1)


if __name__ == "__main__":
    main()
