from __future__ import annotations

import math
from pathlib import Path

import hou

from . import scripts as script_lib
from .qt import (
    QColor,
    QComboBox,
    QDesktopServices,
    QEasingCurve,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QLabel,
    QLineEdit,
    QListWidget,
    QPainter,
    QPainterPath,
    QPixmap,
    QPointF,
    QPushButton,
    QRadialGradient,
    QRectF,
    QSize,
    Qt,
    QUrl,
    QVariantAnimation,
    QVBoxLayout,
    QWidget,
)

PACKAGE_DIR = Path(__file__).resolve().parents[1]
ICONS_DIR = PACKAGE_DIR / "icons"
# Static ExtraBold cut: a variable font may render with its thinnest weight in Houdini's Qt
FONT_FILE = PACKAGE_DIR / "fonts" / "Nunito-ExtraBold.ttf"
FONT_FAMILY = "Nunito"
FONT_SIZE = 14  # points
CLOSE_KEYS = (int(Qt.Key_Escape), int(Qt.Key_QuoteLeft))  # Esc and `
WHITE = QColor("#ffffff")

_font_loaded = False


def loadFont() -> None:
    """Register the bundled Nunito ExtraBold (SIL OFL, fonts/OFL.txt) once per Houdini session"""
    global _font_loaded
    if _font_loaded:
        return
    _font_loaded = True
    if QFontDatabase.addApplicationFont(FONT_FILE.as_posix()) < 0:
        print(f"HotBox: can't load {FONT_FILE.as_posix()}, using the system font")


def buttonFont(size: float = FONT_SIZE) -> QFont:
    loadFont()
    font = QFont(FONT_FAMILY)
    font.setPointSizeF(size)
    font.setWeight(QFont.ExtraBold)
    return font


def fitText(text: str, width: int, max_lines: int = 2) -> tuple[list[str], QFont]:
    """Word wrap measured in pixels; when it takes more than max_lines the font gets smaller"""
    for size in (FONT_SIZE, FONT_SIZE - 2, FONT_SIZE - 3):
        font = buttonFont(size)
        metrics = QFontMetrics(font)
        lines: list[str] = []
        for word in text.split():
            if lines and metrics.horizontalAdvance(f"{lines[-1]} {word}") <= width:
                lines[-1] += f" {word}"
            else:
                lines.append(word)
        if len(lines) <= max_lines:
            break
    return lines or [text], font


def keyCode(hotkey: str | None) -> int | None:
    """Qt key code of a hotkey string ('g', '1', 'F5'); None when empty or invalid.

    Qt6 returns QKeyCombination from QKeySequence[0], Qt5 an int with modifiers.
    """
    if not hotkey:
        return None
    sequence = QKeySequence(hotkey)
    if sequence.count() == 0:
        return None
    combination = sequence[0]
    if hasattr(combination, "key"):
        return int(combination.key())
    return int(combination) & ~int(Qt.KeyboardModifierMask)


def eventKeyCodes(event) -> list[int]:
    """Key codes to match a key press against: the key itself and, for another keyboard layout
    (Russian), the Latin key on the same physical key"""
    codes = [int(event.key())]
    latin = keyCode(script_lib.latinKey(event.text()))
    if latin is not None and latin not in codes:
        codes.append(latin)
    return codes


def mixColor(color: QColor, other: QColor, amount: float) -> QColor:
    """color moved towards other by amount (0..1)"""
    return QColor(
        round(color.red() + (other.red() - color.red()) * amount),
        round(color.green() + (other.green() - color.green()) * amount),
        round(color.blue() + (other.blue() - color.blue()) * amount),
    )


def _eventPos(event) -> QPointF:
    return QPointF(event.position()) if hasattr(event, "position") else QPointF(event.pos())


class Button(QPushButton):
    """Rounded button painted by hand so it can animate:

    - hover: a white wave spreads from the cursor, the button gets lighter and a bit bigger (text too)
    - press (playPress): grows and fades out

    The widget is larger than the visible button by MARGIN so the zoom is never cut off.
    """

    WIDTH, HEIGHT, RADIUS = 200, 60, 10
    HOVER_SCALE, PRESS_SCALE = 1.05, 1.12
    HOVER_WHITE = 0.10  # background towards white on hover
    RIPPLE_ALPHA = 0.35
    HOVER_MS, RIPPLE_MS, PRESS_MS = 150, 450, 220
    MARGIN_X = math.ceil(WIDTH * (PRESS_SCALE - 1) / 2)
    MARGIN_Y = math.ceil(HEIGHT * (PRESS_SCALE - 1) / 2)

    def __init__(self, label: str = "ButtonText", buttonColor: str = "#222222", textColor: str = "#e8e8e8",
                 icon=None, parent=None):
        super().__init__(parent)
        self.hover = 0.0
        self.ripple = 1.0  # 1: finished
        self.press = 0.0
        self.ripplePos = QPointF(self.WIDTH / 2, self.HEIGHT / 2)
        self.iconPixmap = None
        self._hoverAnimation = self._animation(self.HOVER_MS, "hover", QEasingCurve.OutCubic)
        self._rippleAnimation = self._animation(self.RIPPLE_MS, "ripple", QEasingCurve.OutQuad)
        self._pressAnimation = self._animation(self.PRESS_MS, "press", QEasingCurve.OutCubic)

        if isinstance(icon, (QIcon, QPixmap)):
            self.setIcon(QIcon(icon) if isinstance(icon, QPixmap) else icon)
        elif icon:
            filepath = ICONS_DIR / icon
            if filepath.exists():
                self.setIcon(QIcon(filepath.as_posix()))
            else:
                print(f"HotBox: no icon {filepath.as_posix()}")

        self.updateColors(buttonColor, textColor)
        self.updateText(label)
        self.setFixedSize(QSize(self.WIDTH + 2 * self.MARGIN_X, self.HEIGHT + 2 * self.MARGIN_Y))
        self.setFocusPolicy(Qt.ClickFocus)
        self.setAttribute(Qt.WA_Hover)

    def _animation(self, duration: int, attribute: str, curve) -> QVariantAnimation:
        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setEasingCurve(curve)

        def apply(value, attribute=attribute):
            setattr(self, attribute, float(value))
            self.update()

        animation.valueChanged.connect(apply)
        return animation

    @staticmethod
    def _run(animation: QVariantAnimation, start: float, end: float):
        animation.stop()
        animation.setStartValue(float(start))
        animation.setEndValue(float(end))
        animation.start()

    # --- appearance ---------------------------------------------------------------------------------------------

    def updateText(self, text: str):
        self.label = text
        self.setText(text)
        icon_width = 32 if not self.icon().isNull() else 0
        self.lines, self.labelFont = fitText(text, self.WIDTH - 24 - icon_width)

    def updateColors(self, buttonColor="#222222", textColor="#e8e8e8"):
        self.baseColor = QColor(buttonColor)
        self.textColor = QColor(textColor)
        self.update()

    def background(self) -> QColor:
        return mixColor(self.baseColor, WHITE, self.HOVER_WHITE * self.hover)

    def scale(self) -> float:
        hover_scale = 1 + (self.HOVER_SCALE - 1) * self.hover
        return hover_scale + (self.PRESS_SCALE - hover_scale) * self.press

    def visualRect(self) -> QRectF:
        """The button at rest, in widget coordinates"""
        return QRectF(self.MARGIN_X, self.MARGIN_Y, self.WIDTH, self.HEIGHT)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setOpacity(1.0 - self.press)

        rect = self.visualRect()
        center = rect.center()
        painter.translate(center)
        painter.scale(self.scale(), self.scale())
        painter.translate(-center)

        path = QPainterPath()
        path.addRoundedRect(rect, self.RADIUS, self.RADIUS)
        painter.fillPath(path, self.background())

        if self.ripple < 1.0:  # white wave from the cursor
            radius = max(1.0, math.hypot(rect.width(), rect.height()) * self.ripple)
            alpha = self.RIPPLE_ALPHA * (1.0 - self.ripple)
            gradient = QRadialGradient(self.ripplePos, radius)
            gradient.setColorAt(0.0, QColor(255, 255, 255, int(255 * alpha * 0.35)))
            gradient.setColorAt(0.8, QColor(255, 255, 255, int(255 * alpha)))
            gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(rect, gradient)
            painter.restore()

        painter.setFont(self.labelFont)
        painter.setPen(self.textColor)
        metrics = QFontMetrics(self.labelFont)
        text_width = max(metrics.horizontalAdvance(line) for line in self.lines)
        text_height = metrics.height() * len(self.lines)
        icon = self.icon()
        icon_size = 28 if not icon.isNull() else 0
        gap = 6 if icon_size else 0
        x = rect.center().x() - (icon_size + gap + text_width) / 2
        if icon_size:
            icon.paint(painter, int(x), int(rect.center().y() - icon_size / 2), icon_size, icon_size)
        text_rect = QRectF(x + icon_size + gap, rect.center().y() - text_height / 2, text_width, text_height)
        painter.drawText(text_rect, Qt.AlignCenter, "\n".join(self.lines))
        painter.end()

    # --- animation ----------------------------------------------------------------------------------------------

    def startHover(self, pos: QPointF | None = None):
        self.ripplePos = pos if pos is not None else self.visualRect().center()
        self._run(self._rippleAnimation, 0.0, 1.0)
        self._run(self._hoverAnimation, self.hover, 1.0)

    def endHover(self):
        self._run(self._hoverAnimation, self.hover, 0.0)

    def playPress(self, finished=None):
        """Grow and fade out; finished() is called at the end"""
        if finished is not None:
            self._pressAnimation.finished.connect(finished)
        self._run(self._pressAnimation, 0.0, 1.0)

    def enterEvent(self, event):
        self.startHover(_eventPos(event))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.endHover()
        super().leaveEvent(event)


class ScriptButton(Button):
    """Button that runs a library script"""

    BROKEN_TEXT = "#ff6b6b"

    def __init__(self, script: script_lib.Script, parent=None):
        label = f"{script.label} ({script.hotkey})" if script.hotkey else script.label
        text_color = self.BROKEN_TEXT if script.error else script.textcolor
        super().__init__(label, script.buttoncolor, text_color, script.icon, parent)
        self.script = script
        self.hotkey = script.hotkey
        tooltip = script.relpath
        if script.ref:
            tooltip += f"\n→ {script.ref}"
        if script.error:
            tooltip += f"\n{script.error}"
        self.setToolTip(tooltip)


class ScriptGrid(QWidget):
    """Buttons on one grid, so every row is on the same level in all columns.

    Columns go top to bottom: context scripts first, then root scripts in their own column(s); a column
    takes at most MAX_ROWS buttons, then the next one starts. #group blocks are never split, their frame and
    caption are painted behind the buttons in the gap above them.
    """

    MAX_ROWS = 6
    ROW_GAP = 18  # between button widgets (the visible gap adds 2 * Button.MARGIN_Y)
    COLUMN_GAP = 4  # (+ 2 * Button.MARGIN_X)
    CAPTION_HEIGHT = 16
    FRAME_PAD = 5

    def __init__(self, scripts: list[script_lib.Script], context: str = "", parent: QWidget = None):
        super().__init__(parent)
        in_context, root = script_lib.scriptsForContext(scripts, context)

        self.buttons: list[ScriptButton] = []
        self.columns: list[list[tuple[str, list[ScriptButton]]]] = []
        self.groups: list[tuple[str, list[ScriptButton]]] = []
        for column_scripts in (in_context, root):
            for column in self.splitColumns(script_lib.groupBlocks(column_scripts)):
                blocks = []
                for name, block_scripts in column:
                    buttons = [ScriptButton(script, parent=self) for script in block_scripts]
                    self.buttons += buttons
                    blocks.append((name, buttons))
                    if name:
                        self.groups.append((name, buttons))
                self.columns.append(blocks)

        layout = QGridLayout(self)
        layout.setContentsMargins(self.FRAME_PAD, self.CAPTION_HEIGHT + 4, self.FRAME_PAD, 4)
        layout.setHorizontalSpacing(self.COLUMN_GAP)
        layout.setVerticalSpacing(self.ROW_GAP)
        for column_index, column in enumerate(self.columns):
            row = 0
            for _name, buttons in column:
                for button in buttons:
                    layout.addWidget(button, row, column_index, Qt.AlignTop)
                    row += 1

        for key, paths in script_lib.duplicateHotkeys(in_context + root).items():
            print(f"HotBox: hotkey '{key}' is used by several scripts, the last one wins: {', '.join(paths)}")

    @classmethod
    def splitColumns(cls, blocks):
        columns = []
        for block in blocks:
            if not columns or sum(len(b[1]) for b in columns[-1]) + len(block[1]) > cls.MAX_ROWS:
                columns.append([])
            columns[-1].append(block)
        return [column for column in columns if column]

    def buttonRow(self, button) -> int:
        layout = self.layout()
        return layout.getItemPosition(layout.indexOf(button))[0]

    def groupFrame(self, buttons) -> QRectF:
        rect = QRectF()
        for button in buttons:
            rect = rect.united(button.visualRect().translated(QPointF(button.pos())))
        pad = self.FRAME_PAD
        return rect.adjusted(-pad, -(self.CAPTION_HEIGHT + 2), pad, pad)

    def paintEvent(self, event):
        if not self.groups:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        caption_font = buttonFont(FONT_SIZE - 4)
        for name, buttons in self.groups:
            frame = self.groupFrame(buttons)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 14))
            painter.drawRoundedRect(frame, 12, 12)
            painter.setFont(caption_font)
            painter.setPen(QColor(232, 232, 232, 150))
            caption = QRectF(frame.left() + 10, frame.top() + 1, frame.width() - 20, self.CAPTION_HEIGHT)
            painter.drawText(caption, Qt.AlignLeft | Qt.AlignVCenter, name)
        painter.end()

    def keybindings(self) -> dict[int, ScriptButton]:
        bindings = {}
        for button in self.buttons:
            code = keyCode(button.hotkey)
            if code is not None:
                bindings[code] = button
        return bindings


class HLayout(QHBoxLayout):
    """Layout which aligns all input widgets to the left"""

    def __init__(self, widgets=(), align=Qt.AlignLeft, parent=None):
        super().__init__(parent)
        if align:
            self.setAlignment(align)
        for widget in widgets:
            self.addWidget(widget)


class HSeparator(QFrame):
    """Horizontal line"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)


class ScriptManager(QWidget):
    """Browse library scripts and edit their header settings (written back into the script files)"""

    ROOT_ITEM = "(root)"

    def __init__(self, lib_folder: Path, parent=None):
        super().__init__(parent or hou.qt.mainWindow())
        self.lib = Path(lib_folder)
        self.scripts: list[script_lib.Script] = []

        self.setWindowTitle("Script Manager")
        self.setGeometry(300, 300, 1000, 400)
        self.setWindowFlags(Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.initUI()

    def initUI(self):
        main_layout = QHBoxLayout()
        main_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.mode_combobox = QComboBox()
        self.mode_combobox.addItems(list(script_lib.MODES))
        self.folders_list = QListWidget()
        self.files_list = QListWidget()

        fc_layout = QVBoxLayout()
        fc_layout.addWidget(self.mode_combobox)
        fc_layout.addWidget(self.folders_list)

        sc_layout = QVBoxLayout()
        sc_layout.addWidget(self.files_list)

        self.name_lineedit = QLineEdit()
        self.group_lineedit = QLineEdit()
        self.group_lineedit.setPlaceholderText("buttons of one group stand together")
        self.button_color_swatch = hou.qt.ColorSwatchButton()
        self.text_color_swatch = hou.qt.ColorSwatchButton()
        self.icon_lineedit = QLineEdit()
        self.icon_lineedit.setPlaceholderText("file name in icons/")
        self.hotkey_lineedit = QLineEdit()
        self.hotkey_lineedit.setPlaceholderText("g, 1, F5...")
        self.file_lineedit = QLineEdit()
        self.file_lineedit.setReadOnly(True)
        self.ref_label = QLabel()
        self.warning_label = QLabel()
        self.warning_label.setStyleSheet("color:#ffb04a")
        self.warning_label.setWordWrap(True)
        self.save_button = QPushButton("Save")
        self.open_button = QPushButton("Open file")

        tc_layout = QVBoxLayout()
        tc_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        tc_layout.addLayout(HLayout([QLabel("Name"), self.name_lineedit]))
        tc_layout.addLayout(HLayout([QLabel("Group"), self.group_lineedit]))
        tc_layout.addLayout(HLayout([QLabel("Button Color"), self.button_color_swatch]))
        tc_layout.addLayout(HLayout([QLabel("Text Color"), self.text_color_swatch]))
        tc_layout.addLayout(HLayout([QLabel("Icon"), self.icon_lineedit]))
        tc_layout.addLayout(HLayout([QLabel("Hotkey"), self.hotkey_lineedit]))
        tc_layout.addWidget(self.warning_label)
        tc_layout.addLayout(HLayout([self.save_button, self.open_button]))
        tc_layout.addWidget(HSeparator())
        tc_layout.addLayout(HLayout([QLabel("File"), self.file_lineedit]))
        tc_layout.addWidget(self.ref_label)

        main_layout.addLayout(fc_layout)
        main_layout.addLayout(sc_layout)
        main_layout.addLayout(tc_layout)
        self.setLayout(main_layout)

        self.mode_combobox.currentIndexChanged.connect(self.updateScripts)
        self.folders_list.currentRowChanged.connect(self.updateFilesList)
        self.files_list.currentRowChanged.connect(self.updateInfo)
        self.hotkey_lineedit.textChanged.connect(self.updateWarnings)
        self.icon_lineedit.textChanged.connect(self.updateWarnings)
        self.save_button.clicked.connect(self.save)
        self.open_button.clicked.connect(self.openFile)
        self.updateScripts()
        self.show()

    def currentFolder(self) -> str | None:
        item = self.folders_list.currentItem()
        if item is None:
            return None
        return "" if item.text() == self.ROOT_ITEM else item.text()

    def folderScripts(self) -> list[script_lib.Script]:
        folder = self.currentFolder()
        if folder is None:
            return []
        return [s for s in self.scripts if s.context == folder]

    def updateScripts(self):
        self.scripts = script_lib.scanScripts(self.lib / self.mode_combobox.currentText())
        folders = sorted({s.context for s in self.scripts})
        self.folders_list.clear()
        self.folders_list.addItems([folder or self.ROOT_ITEM for folder in folders])
        if folders:
            self.folders_list.setCurrentRow(0)
        else:
            self.updateFilesList()

    def updateFilesList(self):
        self.files_list.clear()
        files = [s.path.name for s in self.folderScripts()]
        self.files_list.addItems(files)
        if files:
            self.files_list.setCurrentRow(0)
        else:
            self.updateInfo()

    def currentScript(self) -> script_lib.Script | None:
        row = self.files_list.currentRow()
        folder_scripts = self.folderScripts()
        return folder_scripts[row] if 0 <= row < len(folder_scripts) else None

    def updateInfo(self):
        """Fields show the script's own header; inherited values (from #ref) are placeholders"""
        script = self.currentScript()
        own = script.ownSettings if script else {}
        merged = script.settings if script else {}
        for lineedit, key in ((self.name_lineedit, "label"), (self.group_lineedit, "group"),
                              (self.icon_lineedit, "icon"), (self.hotkey_lineedit, "hotkey")):
            lineedit.setText(own.get(key, ""))
        self.name_lineedit.setPlaceholderText(script.label if script else "")
        self.group_lineedit.setPlaceholderText(merged.get("group", "") or "buttons of one group stand together")
        self.icon_lineedit.setPlaceholderText(merged.get("icon", "") or "file name in icons/")
        self.file_lineedit.setText(script.path.as_posix() if script else "")
        if script and script.ref:
            self.ref_label.setText(f"#ref → {script.ref}" + (f"  ({script.error})" if script.error else ""))
        else:
            self.ref_label.setText("")
        if script:
            self.button_color_swatch.setColor(QColor(script.buttoncolor))
            self.text_color_swatch.setColor(QColor(script.textcolor))
        for widget in (self.save_button, self.open_button):
            widget.setEnabled(script is not None)
        self.updateWarnings()

    def warnings(self) -> list[str]:
        script = self.currentScript()
        if script is None:
            return []
        messages = []
        hotkey = self.hotkey_lineedit.text().strip()
        if hotkey and keyCode(hotkey) is None:
            messages.append(f"'{hotkey}' is not a key")
        conflicts = script_lib.hotkeyConflicts(self.scripts, script, hotkey)
        if conflicts:
            messages.append(f"Hotkey '{hotkey}' is also used by: {', '.join(conflicts)}")
        icon = self.icon_lineedit.text().strip()
        if icon and not (ICONS_DIR / icon).exists():
            messages.append(f"No icon icons/{icon}")
        return messages

    def updateWarnings(self):
        self.warning_label.setText("\n".join(self.warnings()))

    def editedSettings(self) -> dict:
        """The script's own header after editing. Values equal to the inherited/default ones that the
        header didn't set are not written: a #ref stub stays a stub."""
        script = self.currentScript()
        if script is None:
            return {}
        own = dict(script.ownSettings)
        inherited = {k: v for k, v in script.settings.items() if k not in own}
        edited = {
            "label": self.name_lineedit.text().strip(),
            "group": self.group_lineedit.text().strip(),
            "buttoncolor": self.button_color_swatch.color().name(),
            "textcolor": self.text_color_swatch.color().name(),
            "icon": self.icon_lineedit.text().strip(),
            "hotkey": self.hotkey_lineedit.text().strip(),
        }
        for key, value in edited.items():
            fallback = inherited.get(key) or script_lib.DEFAULTS.get(key, "")
            if key not in own and value.lower() == fallback.lower():
                continue
            own[key] = value
        return own

    def save(self):
        script = self.currentScript()
        if script is None:
            return
        script_lib.writeHeader(script.path, self.editedSettings())
        folder_row, file_row = self.folders_list.currentRow(), self.files_list.currentRow()
        self.scripts = script_lib.scanScripts(self.lib / self.mode_combobox.currentText())
        self.folders_list.setCurrentRow(folder_row)
        self.files_list.setCurrentRow(file_row)
        self.updateInfo()

    def openFile(self):
        script = self.currentScript()
        if script is not None:  # the code: the ref target for a #ref
            path = script.runPath or script.path
            QDesktopServices.openUrl(QUrl.fromLocalFile(path.as_posix()))

    def keyPressEvent(self, event):
        if int(event.key()) == int(Qt.Key_Escape):
            self.close()
            return
        super().keyPressEvent(event)
