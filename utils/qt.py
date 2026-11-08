"""Qt compatibility: Houdini 21+ ships PySide6 (Qt6), older versions PySide2 (Qt5).

Import Qt names from here instead of PySide directly:
    from .qt import *
"""
try:
    from PySide6.QtCore import *
    from PySide6.QtGui import *
    from PySide6.QtWidgets import *

    QT_VERSION = 6
except ImportError:
    from PySide2.QtCore import *
    from PySide2.QtGui import *
    from PySide2.QtWidgets import *

    QT_VERSION = 5
