import sys
from pathlib import Path

# Add translator-app to sys.path so that 'config' can be imported
translator_app_dir = Path(__file__).parent / "translator-app"
if str(translator_app_dir) not in sys.path:
    sys.path.insert(0, str(translator_app_dir))
