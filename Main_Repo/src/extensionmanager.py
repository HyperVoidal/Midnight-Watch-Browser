import shutil
import sys
import os
from pathlib import Path
import urllib.request
import os
from PIL import Image, ImageOps
import json
import PySide6
from PySide6.QtWebEngineCore import QWebEngineExtensionManager
from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QIcon
import zipfile
import subprocess
import requests
import time

global ext_id, ext_name
ext_id = None
ext_name = None

class ExtensionManager():
    def __init__(self, ext_manager):
        super().__init__()
        self.data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)

        self.ext_manager = ext_manager

        self.ext_manager.installFinished.connect(self.on_install_finished)

        self.extensions = self.ext_manager.extensions()

        self.install_root = Path(self.ext_manager.installPath()) #Returns absolute path to extension install directory so I don't have to make a new one
        print(self.install_root)

        self.srcSourceDir = srcSourceDir = Path(__file__).parent
        pass

    def load_installed_extensions(self):
        json_path = Path(self.data_dir) / "data/extensionList.json" # Use your actual path
        if json_path.exists():
            with open(json_path, "r") as f:
                data = json.load(f)
                for ext_id, info in data.items():
                    print(f"Reloading extension: {info['name']}")
                    self.ext_manager.installExtension(info['path'])

    def installer(self, url, srcSourceDir):
        #System for installing extensions on request
        #grab extension ID
        global ext_name, ext_ID
        parts = url.rstrip('/').split('/')
        ext_ID = parts[-1] 
        print(f"Targeting Extension ID: {ext_ID}")

        path = Path(srcSourceDir) / f"ext_cache/{ext_ID}.crx"
        extract_to = Path(srcSourceDir) / f"ext_cache/{ext_ID}_unpacked"
        path.parent.mkdir(parents=True, exist_ok=True) 
        extract_to.mkdir(parents=True, exist_ok=True)

        #grab latest google chrome release version identifiers but the second one in the list, making sure the client download link doesn't lpose 
        version_num = (requests.get("https://versionhistory.googleapis.com/v1/chrome/platforms/win/channels/stable/versions").json())["versions"][1]["version"]

    
        #attempt install using urlpathing for the download repository
        #this specific string tells Google's servers to package the extension as a CRX3 file
        download_URL = (
            f"https://clients2.google.com/service/update2/crx?"
            f"response=redirect&prodversion={version_num}&acceptformat=crx3&x=id%3D{ext_ID}%26uc"
        )
        
        # Add headers
        headers = {
            "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version_num} Safari/537.36",
            "Accept": "*/*"
        }

        try:
            r = requests.get(download_URL, headers=headers, stream=True)
            if r.status_code == 200:
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                print("File downloaded and added to cache")
            else:
                print(r.status_code)
        except Exception as e:
            print("Download failed:", e)
        
        crx_path = Path(path)
        temp_zip = srcSourceDir / "temp_ext.zip"

        with open(crx_path, 'rb') as f:
            data = f.read()

        # Locate the ZIP start (PK\x03\x04)
        # This is universal for all CRX versions
        zip_offset = data.find(b'\x50\x4B\x03\x04')

        if zip_offset == -1:
            print("Error: Not a valid ZIP-based CRX file.")
            return

        # Write the raw ZIP data
        with open(temp_zip, 'wb') as f_out:
            f_out.write(data[zip_offset:])

        #extract data to generated extract directory
        try:
            shutil.unpack_archive(str(temp_zip), str(extract_to), 'zip')
            print(f"Successfully extracted to: {extract_to}")
        finally:
            if temp_zip.exists():
                temp_zip.unlink() # Clean up temp zip
            if path.exists():
                path.unlink() # Clean up the downloaded CRX file

        #install extension and add info to extensionList json file

        #try reading from manifest files since pyside6 has errors
        ext_name = ext_ID  # Default fallback
        try:
            manifest_path = extract_to / "manifest.json"
            with open(manifest_path, "r", encoding="utf-8") as m_file:
                manifest = json.load(m_file)
            
            #use the name from manifest, or fallback to the ID
            name = manifest.get("name", "")
            print(f"Manifest name field: {name}")
            
            if name and not name.startswith("__MSG_"):
                # Direct name in manifest
                ext_name = name
                print(f"Using direct manifest name: {ext_name}")
            elif name.startswith("__MSG_"):
                # Localized name - try to resolve
                key = name.replace("__MSG_", "").replace("__", "")
                locale_path = extract_to / "_locales/en/messages.json"
                if locale_path.exists():
                    with open(locale_path, "r", encoding="utf-8") as f:
                        messages = json.load(f)
                        localized_name = messages.get(key, {}).get("message", None)
                        if localized_name:
                            ext_name = localized_name
                            print(f"Using localized name: {ext_name}")
                        else:
                            print(f"Localization key '{key}' not found, using ID")
                            ext_name = ext_ID
                else:
                    print(f"Locale file not found, using ID")
                    ext_name = ext_ID
            else:
                print(f"No name in manifest, using ID")
                ext_name = ext_ID

        except Exception as e:
            print(f"Could not read manifest, using ID as name: {e}")
            ext_name = ext_ID

        print(f"Final extension name: {ext_name}")

        #install
        print(f"Installing from: {extract_to}")
        self.ext_manager.installExtension(str(extract_to))

    def on_install_finished(self):
        global ext_name, ext_ID
        print(ext_name, ext_ID)
        #update json association with new data
        try:
            json_file = Path(self.srcSourceDir) / "data/extensionList.json"
            if not json_file.exists():
                json_file.parent.mkdir(parents=True, exist_ok=True)
                with open(json_file, "w") as f: json.dump({}, f)

            with open(json_file, "r") as f:
                content = json.load(f)
            
            install_root = self.ext_manager.installPath()
            # Find the actual folder created by the engine
            match = [f for f in os.listdir(install_root) if f.startswith(f"{ext_ID}_unpacked")]
            actual_install_path = os.path.join(install_root, match[0]) if match else None


            content[ext_ID] = {
                "engine_id": ext_ID,
                "name": ext_name,
                "path": actual_install_path
            }
            
            with open(json_file, "w") as f:
                json.dump(content, f, indent=4)
            
            print(f"Successfully registered {ext_name} in extensionList.json")

        except Exception as e:
            print("Error saving to extensionList.json: ", e)


 
    def uninstaller(self, ext_id):
        for ext in self.ext_manager.extensions():
            if ext.extensionId() == ext_id:
                self.ext_manager.uninstallExtension(ext_id)
        pass

    def loader(self):
        #temporary extension enabling for a given session
        pass

    def display(self):
        json_path = Path(self.srcSourceDir) / "data/extensionList.json"
        if not json_path.exists():
            return {}
        
        with open(json_path, "r") as f:
            return json.load(f) # Returns the dict for your UI loop

        
        return extensionsDict
