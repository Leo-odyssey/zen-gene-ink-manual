import time
import win32gui
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication


class ClipboardMonitor(QObject):
    """Watches QClipboard for text changes and emits text_copied(text, hwnd).

    Call suppress_for(seconds) before any clipboard operation your code does
    (hotkey reads, pastes) so those changes don't trigger the companion panel.
    """

    text_copied = pyqtSignal(str, int)   # text, source window handle

    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = False
        self._suppress_until = 0.0

    def start(self):
        QApplication.clipboard().dataChanged.connect(self._on_changed)

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def suppress_for(self, seconds: float = 3.0):
        """Temporarily ignore clipboard changes (call before own clipboard ops)."""
        self._suppress_until = max(self._suppress_until, time.time() + seconds)

    def _on_changed(self):
        if not self._enabled:
            return
        if time.time() < self._suppress_until:
            return
        text = QApplication.clipboard().text().strip()
        if not text:
            return
        hwnd = win32gui.GetForegroundWindow()
        self.text_copied.emit(text, hwnd)
