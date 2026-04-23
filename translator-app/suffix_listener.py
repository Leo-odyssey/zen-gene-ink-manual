import threading
import keyboard
from PyQt5.QtCore import QObject, pyqtSignal


class SuffixListener(QObject):
    """Watches for a configurable two-char suffix typed in any app and emits triggered().

    The suffix is expected to be two identical characters (e.g. ·· ;; zz).
    Only the first character is used as the trigger key.
    """

    triggered = pyqtSignal()

    # Some keys have non-obvious names in the keyboard library on Windows.
    _KEY_ALIASES: dict[str, set[str]] = {
        ";": {"semicolon", ";"},
    }

    def __init__(self, suffix: str = "··", parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._last_match = False
        self._enabled = threading.Event()
        self._char, self._names = self._parse(suffix)

    @classmethod
    def _parse(cls, suffix: str) -> tuple[str, set[str]]:
        char = suffix[0] if suffix else "·"
        names = cls._KEY_ALIASES.get(char, {char})
        return char, names

    def set_suffix(self, suffix: str):
        with self._lock:
            self._char, self._names = self._parse(suffix)
            self._last_match = False

    def start(self):
        keyboard.on_press(self._on_key, suppress=False)

    def set_enabled(self, enabled: bool):
        with self._lock:
            if enabled:
                self._enabled.set()
            else:
                self._enabled.clear()
                self._last_match = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled.is_set()

    def _on_key(self, event):
        with self._lock:
            if not self._enabled.is_set():
                self._last_match = False
                return
            if event.name in self._names:
                if self._last_match:
                    self._last_match = False
                    self.triggered.emit()
                else:
                    self._last_match = True
            else:
                self._last_match = False
