import os
import sys
from pathlib import Path

def pathingDefine():
    MSIX_REDIRECT = True
    return MSIX_REDIRECT


def resolve_source_dir(module_file=None):
    """Resolve the writable source root for the current runtime.

    In VS Code / local development we want the source tree under the project
    folder. For packaged/frozen builds on Windows we keep using the AppData
    location so the browser can write its runtime data in the MSIX-safe area.
    """

    MSIX_REDIRECT = pathingDefine()

    module_path = Path(module_file or __file__).resolve()

    if sys.platform == "win32" and MSIX_REDIRECT:
        if getattr(sys, "frozen", False) or MSIX_REDIRECT:
            local_appdata = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
            app_data_folder = os.environ.get("MIDNIGHT_APPDATA_FOLDER", "MidnightWatch")
            app_data_path = Path(local_appdata) / app_data_folder
            app_data_path.mkdir(parents=True, exist_ok=True)
            return app_data_path

    return Path(module_path.parent)