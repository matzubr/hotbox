from __future__ import annotations

import math
from pathlib import Path

import hou

from . import scripts as script_lib
from .qt import (
    QColor,
    QEasingCurve,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPixmap,
    QPoint,
    QPointF,
    QPushButton,
    QRadialGradient,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
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


def fitText(text: str, width: int, max_lines: int = 2, size: float = FONT_SIZE) -> tuple[list[str], QFont]:
    """Word wrap measured in pixels. When the text takes more than max_lines or a word is wider than the
    button (long node type names: 'karmarendersettings') the font gets smaller; if it still doesn't fit,
    the lines are cut with '…' (the button tooltip has the full text)."""
    for font_size in (size, size - 2, size - 3, size - 4):
        font = buttonFont(font_size)
        metrics = QFontMetrics(font)
        lines: list[str] = []
        for word in text.split():
            if lines and metrics.horizontalAdvance(f"{lines[-1]} {word}") <= width:
                lines[-1] += f" {word}"
            else:
                lines.append(word)
        if len(lines) <= max_lines and all(metrics.horizontalAdvance(line) <= width for line in lines):
            return lines or [text], font
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [" ".join(lines[max_lines - 1:])]
    return [metrics.elidedText(line, Qt.ElideRight, width) for line in lines] or [text], font


def isElided(lines: list[str]) -> bool:
    return any(line.endswith("…") for line in lines)


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


def resolveIcon(icon) -> QIcon | None:
    """QIcon from a QIcon/QPixmap, a file in icons/ ('dino.svg') or a Houdini icon name ('SOP_null',
    the names node.type().icon() returns). None when there is no such icon."""
    if isinstance(icon, QIcon):
        return None if icon.isNull() else icon
    if isinstance(icon, QPixmap):
        return QIcon(icon)
    if not icon:
        return None
    filepath = ICONS_DIR / icon
    if filepath.is_file():
        return QIcon(filepath.as_posix())
    try:
        qicon = hou.qt.Icon(icon)
    except Exception:  # noqa: BLE001  hou.OperationFailed and friends for unknown names
        qicon = None
    if isinstance(qicon, QIcon) and not qicon.isNull():
        return qicon
    return None


class Button(QPushButton):
    """Rounded button painted by hand so it can animate:

    - hover: a white wave spreads from the cursor, the button gets lighter and bigger (text too)
    - press (playPress): grows and fades out
    - appear (playAppear): grows from nothing at its center with a small spring overshoot
    - disappear (playDisappear): the reverse, a small swell and shrinks to nothing

    While it is zoomed, the window's AnimationOverlay paints it on top of everything, so the zoom is not cut
    by the widget and buttons don't need empty space around them.
    """

    WIDTH, HEIGHT, RADIUS = 200, 60, 10
    HOVER_SCALE, PRESS_SCALE = 1.07, 1.19
    HOVER_WHITE = 0.10  # background towards white on hover
    RIPPLE_ALPHA = 0.35
    HOVER_MS, RIPPLE_MS, PRESS_MS = 150, 450, 220
    APPEAR_MS = 340
    APPEAR_OVERSHOOT = 1.6  # spring: how far past full size the button grows before settling
    DISAPPEAR_MS = 200
    DISAPPEAR_OVERSHOOT = 1.2  # swell before shrinking
    ICON_SIZE = 28
    DIM_OPACITY = 0.22  # buttons that don't match the search

    def __init__(self, label: str = "ButtonText", buttonColor: str = "#222222", textColor: str = "#e8e8e8",
                 icon=None, parent=None, size: tuple[int, int] | None = None, fontSize: float = FONT_SIZE):
        super().__init__(parent)
        self.buttonWidth, self.buttonHeight = size or (self.WIDTH, self.HEIGHT)
        self.fontSize = fontSize
        self.hover = 0.0
        self.ripple = 1.0  # 1: finished
        self.press = 0.0
        self.appear = 1.0  # 0: not shown yet, 1: full size (a bit more during the spring)
        self.dimmed = False
        self.ripplePos = QPointF(self.buttonWidth / 2, self.buttonHeight / 2)
        self._hoverAnimation = self._animation(self.HOVER_MS, "hover", QEasingCurve.OutCubic)
        self._rippleAnimation = self._animation(self.RIPPLE_MS, "ripple", QEasingCurve.OutQuad)
        self._pressAnimation = self._animation(self.PRESS_MS, "press", QEasingCurve.OutCubic)
        spring = QEasingCurve(QEasingCurve.OutBack)
        spring.setOvershoot(self.APPEAR_OVERSHOOT)
        self._appearAnimation = self._animation(self.APPEAR_MS, "appear", spring)
        self._appearTimer = QTimer(self)  # child: never fires after the button is gone
        self._appearTimer.setSingleShot(True)
        self._appearTimer.timeout.connect(lambda: self._run(self._appearAnimation, 0.0, 1.0))
        anticipation = QEasingCurve(QEasingCurve.InBack)
        anticipation.setOvershoot(self.DISAPPEAR_OVERSHOOT)
        self._disappearAnimation = self._animation(self.DISAPPEAR_MS, "appear", anticipation)
        self._disappearTimer = QTimer(self)
        self._disappearTimer.setSingleShot(True)
        self._disappearTimer.timeout.connect(lambda: self._run(self._disappearAnimation, self.appear, 0.0))

        self.setButtonIcon(icon)
        self.updateColors(buttonColor, textColor)
        self.updateText(label)
        self.setFixedSize(QSize(self.buttonWidth, self.buttonHeight))
        self.setFocusPolicy(Qt.ClickFocus)
        self.setAttribute(Qt.WA_Hover)

    def _animation(self, duration: int, attribute: str, curve) -> QVariantAnimation:
        animation = QVariantAnimation(self)
        animation.setDuration(duration)
        animation.setEasingCurve(curve)

        def apply(value, attribute=attribute):
            setattr(self, attribute, float(value))
            self.repaint_()

        animation.valueChanged.connect(apply)
        return animation

    @staticmethod
    def _run(animation: QVariantAnimation, start: float, end: float):
        animation.stop()
        animation.setStartValue(float(start))
        animation.setEndValue(float(end))
        animation.start()

    def overlay(self):
        """AnimationOverlay of the window, None outside the hotbox"""
        widget = self.parentWidget()
        while widget is not None:
            overlay = getattr(widget, "animationOverlay", None)
            if overlay is not None:
                return overlay
            widget = widget.parentWidget()
        return None

    def repaint_(self):
        self.update()
        if self.appear != 1.0 and self.parentWidget() is not None:
            self.parentWidget().update()  # group frames fade in with their buttons
        overlay = self.overlay()
        if overlay is not None:
            overlay.update()

    # --- appearance ---------------------------------------------------------------------------------------------

    def setButtonIcon(self, icon):
        qicon = resolveIcon(icon)
        if icon and qicon is None and not isinstance(icon, (QIcon, QPixmap)):
            print(f"HotBox: no icon '{icon}' (not in icons/ and not a Houdini icon)")
        self.setIcon(qicon or QIcon())

    def updateText(self, text: str):
        self.label = text
        self.setText(text)
        icon_width = self.ICON_SIZE + 6 if not self.icon().isNull() else 0
        self.lines, self.labelFont = fitText(text, self.buttonWidth - 24 - icon_width, size=self.fontSize)
        if isElided(self.lines) and not self.toolTip():
            self.setToolTip(text)
        self.update()

    def updateColors(self, buttonColor="#222222", textColor="#e8e8e8"):
        self.baseColor = QColor(buttonColor)
        self.textColor = QColor(textColor)
        self.update()

    def setDimmed(self, dimmed: bool):
        """Faded out and not clickable (search: not a match)"""
        if dimmed == self.dimmed:
            return
        self.dimmed = dimmed
        self.setAttribute(Qt.WA_TransparentForMouseEvents, dimmed)
        if dimmed:
            self.endHover()
        self.update()

    def background(self) -> QColor:
        return mixColor(self.baseColor, WHITE, self.HOVER_WHITE * self.hover)

    def scale(self) -> float:
        hover_scale = 1 + (self.HOVER_SCALE - 1) * self.hover
        return (hover_scale + (self.PRESS_SCALE - hover_scale) * self.press) * max(0.0, self.appear)

    def visualRect(self) -> QRectF:
        """The button at rest, in widget coordinates"""
        return QRectF(0, 0, self.buttonWidth, self.buttonHeight)

    def isAnimated(self) -> bool:
        return abs(self.scale() - 1) > 0.0005 or self.press > 0 or self.ripple < 1.0 or self.appear < 1.0

    def paintEvent(self, event):
        if self.isAnimated() and self.overlay() is not None:
            return  # the overlay paints the zoomed button
        painter = QPainter(self)
        self.paintTo(painter, self.visualRect())
        painter.end()

    def paintTo(self, painter: QPainter, rect: QRectF):
        """Paint the button with its current animation state into rect (the button at rest)"""
        if self.scale() < 0.01:
            return  # not appeared yet
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setOpacity((1.0 - self.press) * (self.DIM_OPACITY if self.dimmed else 1.0))
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
            gradient = QRadialGradient(self.ripplePos + rect.topLeft(), radius)
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
        icon_size = self.ICON_SIZE if not icon.isNull() else 0
        gap = 6 if icon_size else 0
        x = center.x() - (icon_size + gap + text_width) / 2
        if icon_size:
            icon.paint(painter, int(x), int(center.y() - icon_size / 2), icon_size, icon_size)
        text_rect = QRectF(x + icon_size + gap, center.y() - text_height / 2, text_width, text_height)
        painter.drawText(text_rect, Qt.AlignCenter, "\n".join(self.lines))
        painter.restore()

    # --- animation ----------------------------------------------------------------------------------------------

    def playAppear(self, delay_ms: int = 0):
        """Hidden now, grows in after the delay"""
        self.appear = 0.0
        self._appearAnimation.stop()
        self._appearTimer.start(max(0, int(delay_ms)))
        self.repaint_()

    def finishAppear(self):
        self._appearTimer.stop()
        self._appearAnimation.stop()
        self.appear = 1.0
        self.repaint_()

    def playDisappear(self, delay_ms: int = 0):
        """Shrink to nothing at the center after the delay (from wherever the appear animation is)"""
        self._appearTimer.stop()
        self._appearAnimation.stop()
        self._hoverAnimation.stop()
        self._disappearTimer.start(max(0, int(delay_ms)))

    def startHover(self, pos: QPointF | None = None):
        self.ripplePos = pos if pos is not None else self.visualRect().center()
        self._run(self._rippleAnimation, 0.0, 1.0)
        self._run(self._hoverAnimation, self.hover, 1.0)

    def endHover(self):
        self._run(self._hoverAnimation, self.hover, 0.0)

    def playPress(self, finished=None):
        """Grow and fade out; finished() is called at the end"""
        self.raise_()
        if finished is not None:
            self._pressAnimation.finished.connect(finished)
        self._run(self._pressAnimation, 0.0, 1.0)

    def enterEvent(self, event):
        self.startHover(_eventPos(event))
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.endHover()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.ripplePos = _eventPos(event)
        self._run(self._rippleAnimation, 0.0, 1.0)  # a wave from the click point
        super().mousePressEvent(event)


class AnimationOverlay(QWidget):
    """Transparent layer over the whole window painting the zoomed (hovered/pressed) buttons on top.

    The owner sets `self.animationOverlay = AnimationOverlay(self)` and keeps it on top and full size.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setGeometry(parent.rect())
        self.raise_()

    def paintEvent(self, event):
        owner = self.parentWidget()
        buttons = [b for b in owner.findChildren(Button) if b.isVisible() and b.isAnimated()]
        if not buttons:
            return
        painter = QPainter(self)
        for button in sorted(buttons, key=lambda b: (b.press, b.hover)):  # the pressed one on top
            top_left = QPointF(button.mapTo(owner, QPoint(0, 0)))
            button.paintTo(painter, button.visualRect().translated(top_left))
        painter.end()


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
        if script.root is not None:
            tooltip += f"\n{script.root.as_posix()}"
        self.setToolTip(tooltip)


class ScriptGrid(QWidget):
    """Buttons on one grid, so every row is on the same level in all columns.

    Columns go top to bottom: context scripts first, then root scripts in their own column(s); a column
    takes at most MAX_ROWS buttons, then the next one starts. #group blocks are never split.
    Gaps are grid rows/columns of their own: the gap above a group makes room for its frame and caption,
    and the same gap is used in every column, so rows stay aligned.
    """

    MAX_ROWS = 6
    ROW_GAP = 12  # between buttons
    COLUMN_GAP = 14
    CAPTION_HEIGHT = 16
    FRAME_PAD = 8  # between buttons and their group frame
    FRAME_GAP = 8  # between a group frame and the buttons/frames around it

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for column_index, column in enumerate(self.columns):
            row = 0
            for _name, buttons in column:
                for button in buttons:
                    layout.addWidget(button, 2 * row + 1, 2 * column_index + 1)
                    row += 1
        for index, gap in enumerate(self.rowGaps()):
            layout.setRowMinimumHeight(2 * index, gap)
        column_gaps = self.columnGaps()
        for index, gap in enumerate(column_gaps):
            layout.setColumnMinimumWidth(2 * index, gap)
        # Extra space (if the widget is bigger than needed) goes to the end, gaps stay as computed
        layout.setRowStretch(2 * len(self.rowGaps()), 1)
        layout.setColumnStretch(2 * len(column_gaps), 1)

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

    def _columnRows(self, column) -> list[tuple[str, bool, bool]]:
        """(group, first in group, last in group) for each row of a column"""
        rows = []
        for name, buttons in column:
            for index in range(len(buttons)):
                rows.append((name, index == 0, index == len(buttons) - 1))
        return rows

    def rowGaps(self) -> list[int]:
        """Height of the gap above each button row and below the last one"""
        row_count = max((sum(len(b) for _, b in column) for column in self.columns), default=0)
        gaps = [0] + [self.ROW_GAP] * (row_count - 1) + [0] if row_count else []
        frame_top = self.CAPTION_HEIGHT + 4
        for column in self.columns:
            rows = self._columnRows(column)
            for boundary in range(len(rows) + 1):
                above = rows[boundary - 1] if boundary > 0 else None
                below = rows[boundary] if boundary < len(rows) else None
                need = 0
                if above and above[0] and above[2]:
                    need += self.FRAME_PAD  # frame bottom of the group above
                if below and below[0] and below[1]:
                    need += frame_top  # caption and frame top of the group below
                if need and above and below:
                    need += self.FRAME_GAP
                gaps[boundary] = max(gaps[boundary], need)
        return gaps

    def columnGaps(self) -> list[int]:
        """Width of the gap left of each column and right of the last one"""
        grouped = [any(name for name, _ in column) for column in self.columns]
        pad = [self.FRAME_PAD if g else 0 for g in grouped]
        gaps = [pad[0]] if grouped else []
        for index in range(1, len(grouped)):
            gaps.append(pad[index - 1] + self.COLUMN_GAP + pad[index])
        if grouped:
            gaps.append(pad[-1])
        return gaps

    def groupFrame(self, buttons) -> QRectF:
        rect = QRectF()
        for button in buttons:
            rect = rect.united(button.visualRect().translated(QPointF(button.pos())))
        pad = self.FRAME_PAD
        return rect.adjusted(-pad, -(self.CAPTION_HEIGHT + 4), pad, pad)

    def paintEvent(self, event):
        if not self.groups:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for name, buttons in self.groups:
            paintGroupFrame(painter, self.groupFrame(buttons), name, buttons)
        painter.end()

    def keybindings(self) -> dict[int, ScriptButton]:
        bindings = {}
        for button in self.buttons:
            code = keyCode(button.hotkey)
            if code is not None:
                bindings[code] = button
        return bindings


def paintGroupFrame(painter: QPainter, frame: QRectF, name: str, buttons=()) -> None:
    """Translucent rounded frame with a caption: #group blocks and the Recent row.
    While its buttons appear, the frame fades in with the first of them."""
    shown = max((min(1.0, max(0.0, b.appear)) * (1.0 - b.press) for b in buttons), default=1.0)
    if shown <= 0:
        return
    painter.save()
    painter.setOpacity(shown)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, 14))
    painter.drawRoundedRect(frame, 12, 12)
    painter.setFont(buttonFont(FONT_SIZE - 4))
    painter.setPen(QColor(232, 232, 232, 150))
    caption = QRectF(frame.left() + 10, frame.top() + 3, frame.width() - 20, ScriptGrid.CAPTION_HEIGHT)
    painter.drawText(caption, Qt.AlignLeft | Qt.AlignVCenter, name)
    painter.restore()


class RecentRow(QWidget):
    """The last run scripts of this mode in a row, framed like a group"""

    CAPTION = "Recent"

    def __init__(self, scripts: list[script_lib.Script], parent: QWidget = None):
        super().__init__(parent)
        self.buttons = [ScriptButton(script, parent=self) for script in scripts]
        layout = QHBoxLayout(self)
        pad = ScriptGrid.FRAME_PAD
        layout.setContentsMargins(pad, ScriptGrid.CAPTION_HEIGHT + 4, pad, pad)
        layout.setSpacing(ScriptGrid.COLUMN_GAP)
        for button in self.buttons:
            layout.addWidget(button)

    def paintEvent(self, event):
        if not self.buttons:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        paintGroupFrame(painter, QRectF(self.rect()), self.CAPTION, self.buttons)
        painter.end()


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
