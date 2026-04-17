import sys
import json
from pathlib import Path
from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                               QPushButton, QWidget, QLabel, QDialog)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage


class ExtensionLoader(QMainWindow):
    def __init__(self, profile, path):
        super().__init__()
        self.setWindowTitle("Extension Loader V3 (Locale Support)")
        self.resize(600, 450)
        
        # Setup Profile
        self.profile = profile
        self.ext_manager = self.profile.extensionManager()
        self.ext_path = path

        # UI
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-weight: bold; color: #333;")
        layout.addWidget(self.lbl_status)

        self.btn_load = QPushButton("1. Load Extension")
        self.btn_load.clicked.connect(self.load_extension)
        layout.addWidget(self.btn_load)

        self.btn_open = QPushButton("2. Open Popup")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_popup_window)
        layout.addWidget(self.btn_open)

        self.active_id = None
        self.popup_file = None
        self.target_name = None

    def load_extension(self):
        target = Path(self.ext_path).resolve()
        if not target.exists():
            self.lbl_status.setText(f"❌ Path not found: {target}")
            return

        manifest_path = target / "manifest.json"
        if not manifest_path.exists():
            self.lbl_status.setText("❌ manifest.json missing")
            return

        # --- PARSE MANIFEST & RESOLVE NAME ---
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                
            raw_name = manifest.get("name", "Unknown")
            
            # RESOLVER LOGIC: Check for __MSG_
            if raw_name.startswith("__MSG_") and raw_name.endswith("__"):
                self.target_name = self.resolve_locale_name(target, manifest, raw_name)
                print(f"DEBUG: Resolved '{raw_name}' -> '{self.target_name}'")
            else:
                self.target_name = raw_name

            # Find popup file
            popup = manifest.get("action", {}).get("default_popup") or \
                    manifest.get("browser_action", {}).get("default_popup")
            self.popup_file = popup or "index.html"
            
        except Exception as e:
            self.lbl_status.setText(f"❌ Parse Error: {e}")
            return

        self.lbl_status.setText(f"⏳ Loading: {self.target_name}...")
        
        # LOAD
        self.ext_manager.loadExtension(str(target))
        
        # WAIT & MATCH
        QTimer.singleShot(800, self.find_and_activate)

    def resolve_locale_name(self, ext_path, manifest, raw_name):
        """
        Reads _locales/en/messages.json to convert __MSG_extName__ -> uBlock Origin Lite
        """
        key = raw_name.replace("__MSG_", "").replace("__", "")
        default_locale = manifest.get("default_locale", "en")
        
        # Try specific locale first, then fallback to just 'en'
        candidates = [default_locale, "en", "en_US"]
        
        for loc in candidates:
            msg_path = ext_path / "_locales" / loc / "messages.json"
            if msg_path.exists():
                try:
                    with open(msg_path, "r", encoding="utf-8") as f:
                        msgs = json.load(f)
                    # Extract the actual string
                    if key in msgs:
                        return msgs[key]["message"]
                except:
                    continue
        
        return raw_name # Fallback to raw if lookup fails

    def find_and_activate(self):
        found_ext = None
        all_extensions = self.ext_manager.extensions()
        
        print(f"DEBUG: Scanning {len(all_extensions)} extensions for '{self.target_name}'")

        for ext in all_extensions:
            # Compare Name against Resolved Name
            if ext.name() == self.target_name:
                found_ext = ext
                break
        
        if found_ext:
            self.active_id = found_ext.id()
            
            # === FIX IS HERE ===
            # Pass the 'found_ext' OBJECT, not the String ID
            try:
                self.ext_manager.setExtensionEnabled(found_ext, True)
                print(f"DEBUG: Extension object passed to setExtensionEnabled.")
            except Exception as e:
                print(f"CRITICAL ERROR enabling extension: {e}")
            
            self.lbl_status.setText(f"✅ SUCCESS!\nName: {self.target_name}\nID: {self.active_id}")
            self.btn_open.setEnabled(True)
        else:
            self.lbl_status.setText(f"❌ Failed to match '{self.target_name}'")


    def open_popup_window(self):
        if not self.active_id: return
        url = f"chrome-extension://{self.active_id}/{self.popup_file}"
        print(f"Opening: {url}")

        self.popup = QDialog(self)
        self.popup.resize(500, 600)
        view = QWebEngineView(self.popup)
        view.setPage(QWebEnginePage(self.profile, view))
        view.load(QUrl(url))
        
        layout = QVBoxLayout(self.popup)
        layout.addWidget(view)
        layout.setContentsMargins(0,0,0,0)
        self.popup.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ExtensionLoader()
    window.show()
    sys.exit(app.exec())
