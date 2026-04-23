import threading
import keyboard
from PyQt5.QtCore import QObject, pyqtSignal


class HotkeyListener(QObject):
    triggered = pyqtSignal()

    def __init__(self, hotkey: str, parent=None):
        super().__init__(parent)
        self._hotkey = hotkey
        self._active = threading.Event()
        self._active.set()  # active by default
        self._registered = False

    def start(self):
        try:
            keyboard.add_hotkey(self._hotkey, self._fire)
            self._registered = True
        except Exception as e:
            raise RuntimeError(f"Failed to register hotkey '{self._hotkey}': {e}") from e

    def _fire(self):
        # Called from keyboard library's background thread.
        # triggered signal uses Qt.AutoConnection which queues across thread boundaries.
        if self._active.is_set():
            self.triggered.emit()

    def set_hotkey(self, new_hotkey: str):
        if self._registered:
            try:
                keyboard.remove_hotkey(self._hotkey)
            except KeyError:
                pass
        self._hotkey = new_hotkey
        try:
            keyboard.add_hotkey(self._hotkey, self._fire)
            self._registered = True
        except Exception as e:
            raise RuntimeError(f"Failed to register hotkey '{new_hotkey}': {e}") from e

    def pause(self):
        self._active.clear()

    def resume(self):
        self._active.set()
