import time
import win32clipboard
import win32con
import keyboard


def _get_clipboard_text() -> str:
    opened = False
    try:
        win32clipboard.OpenClipboard()
        opened = True
        try:
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        except TypeError:
            return ""
    except Exception:
        return ""
    finally:
        if opened:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass


def _set_clipboard_text(text: str) -> None:
    opened = False
    try:
        win32clipboard.OpenClipboard()
        opened = True
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        if opened:
            win32clipboard.CloseClipboard()


def save_clipboard() -> str | None:
    try:
        return _get_clipboard_text()
    except Exception:
        return None


def restore_clipboard(saved: str | None) -> None:
    if saved is not None:
        try:
            _set_clipboard_text(saved)
        except Exception:
            pass


def read_input_box() -> tuple[str, str | None, bool]:
    """
    Returns (text, saved_clipboard, had_selection).
    Tries to read selected text first; falls back to Ctrl+A select-all.
    """
    saved = save_clipboard()

    # Release any modifier keys still held from the hotkey press so that
    # subsequent ctrl+c / ctrl+a sends are not contaminated by ctrl+shift.
    for _mod in ("ctrl", "shift", "alt"):
        try:
            keyboard.release(_mod)
        except Exception:
            pass

    # Try reading existing selection first
    _set_clipboard_text("")
    time.sleep(0.05)
    keyboard.send("ctrl+c")
    time.sleep(0.15)
    selected = _get_clipboard_text()

    if selected.strip():
        return selected, saved, True

    # No selection — select all and copy
    keyboard.send("ctrl+a")
    time.sleep(0.05)
    keyboard.send("ctrl+c")
    time.sleep(0.15)
    text = _get_clipboard_text()

    return text, saved, False


def write_input_box(text: str, saved_clipboard: str | None, had_selection: bool) -> None:
    """
    Replace input box content with text, then restore the original clipboard.
    If had_selection is True, only the selected region is replaced (Ctrl+V).
    If had_selection is False, Ctrl+A is sent first to select all before pasting.
    """
    # Source apps (e.g. Outlook) can keep the clipboard locked for a short time
    # after a Ctrl+C read. Retry until we can actually set the new content.
    for _attempt in range(8):
        try:
            _set_clipboard_text(text)
            break
        except Exception:
            time.sleep(0.1)

    # Give Windows time to commit the clipboard data before we paste.
    time.sleep(0.15)

    if not had_selection:
        keyboard.send("ctrl+a")
        time.sleep(0.05)
    keyboard.send("ctrl+v")
    time.sleep(0.2)
    restore_clipboard(saved_clipboard)
