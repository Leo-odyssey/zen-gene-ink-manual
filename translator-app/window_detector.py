import win32gui


def get_active_window_title() -> str:
    hwnd = win32gui.GetForegroundWindow()
    return win32gui.GetWindowText(hwnd).lower()


def infer_scene(window_title: str, window_scene_map: dict, default: str = "spoken") -> str:
    title = window_title.lower()
    for keyword in sorted(window_scene_map, key=len, reverse=True):
        if keyword.lower() in title:
            return window_scene_map[keyword]
    return default
