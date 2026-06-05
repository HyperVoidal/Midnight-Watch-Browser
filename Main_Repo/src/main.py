import sys
import warnings
import PySide6
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import *
from PySide6.QtWebEngineCore import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtNetwork import *
from PySide6.QtWebEngineCore import *
from PySide6.QtWebChannel import *
from urllib.parse import urlparse
from pathlib import Path
import requests
import urllib.request
import os
from PIL import Image, ImageOps
import json
import re
import uuid
import base64
import io
import hashlib
import shutil
import plyer
from plyer import notification
import random
from shiboken6 import isValid
from network_controller import *
from ui_core import *
from cookieManager import CookieManager
from backgroundProcessHandler import SecureDnsMonitor, GPULogMonitor


print("PyQt6 Version: " + PySide6.__version__)
print("Internal Chromium Version: " + qWebEngineChromiumVersion())
#Icon cache 
icon_cache_dir = Path(__file__).parent / "ui/icon_cache"
icon_cache_dir.mkdir(exist_ok=True)

#Main src source
srcSourceDir = Path(__file__).parent


#Internal urlscheme registry
def registerScheme():
    scheme = QWebEngineUrlScheme(b"midnightwatch")
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme |
        QWebEngineUrlScheme.Flag.FetchApiAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)

#Icon attachment filepath system
def get_normIcon(name):
    icon_path = icon_cache_dir / f"{name}"

    return QIcon(str(icon_path))

#Variable initialisation
global eColsButton, eColsStyle
eColsButton = []
eColsStyle = []

doh_providers = {
        "Default": {
            "url": ""
        }, #No DoH
        "Cloudflare": {
            "url": "https://cloudflare-dns.com/dns-query"
        }, #Secure but no additional systems
        "Cloudflare Secure": {
            "url": "https://security.cloudflare-dns.com/dns-query"
        }, #Cloudflare system but with additional malware/phishing blocking
        "Google Public DNS": {
            "url": "https://dns.google/dns-query"
        }, #Fastest and most accessible but less secure
        "AdGuard": {
            "url": "https://dns.adguard-dns.com/dns-query"
        }, #Slower but adds an additional ad/tracker blocker
        "AdGuard Family": {
            "url": "https://family.adguard-dns.com/dns-query"
        }, #Adguard system but with additional adult content filters
        #Various other dns points sourced from IronFox's list of trusted DoH providers!
        "Mullvad Default": {
            "url": "https://dns.mullvad.net/dns-query"
        },
        "Mullvad Unfiltered": {
            "url": "https://dns.mullvad.net/dns-query"
        },
        "DNS4EU (AdBlock)": {
            "url": "https://noads.joindns4.eu/dns-query"
        },
        "DNS4EU (Protective)": {
            "url": "https://protective.joindns4.eu/dns-query"
        },
        "DNS4EU (Unfiltered)": {
            "url": "https://unfiltered.joindns4.eu/dns-query"
        }
    }


# ---- MAIN FUNCTIONS ----

def saveData(profileID, profileConfig):
    with open(f"{srcSourceDir}/data/profileData.json", "r") as f:
        profileData = dict(json.load(f))
    
    if profileID in profileData:
        profileData[profileID] = profileConfig
        profileData[profileID].pop("id", None)
        with open(f"{srcSourceDir}/data/profileData.json", "w") as f:
            json.dump(profileData, f, indent=4)
        print(f"Settings applied and saved to profile ID: {profileID}")
    else:
        print(f"Warning: Profile ID {profileID} not found in profileData.json")


def updateDoHSettings(provider, dataStorage):
    if provider not in doh_providers:
        print(f"Error: Unknown provider '{provider}'")
        return False

    config = doh_providers[provider]
    dns_settings = QWebEngineGlobalSettings.DnsMode()
    if provider == "Default":
        dns_settings.secureMode = QWebEngineGlobalSettings.SecureDnsMode.SystemOnly
    else:
        if dataStorage["Dns-Fallback"] == True:
            dns_settings.secureMode = QWebEngineGlobalSettings.SecureDnsMode.SecureWithFallback
        else:
            dns_settings.secureMode = QWebEngineGlobalSettings.SecureDnsMode.SecureOnly

    if config["url"]:
        dns_settings.serverTemplates = [config["url"]]
    else:
        dns_settings.serverTemplates = []
    
    success = QWebEngineGlobalSettings.setDnsMode(dns_settings)
    if success:
        print(f"Successfully switched browser DNS mode to: {provider}")
        # Clear cache so subsequent lookups hit the new DNS endpoints instantly
        QWebEngineProfile.defaultProfile().clearHttpCache()
    else:
        print(f"Chromium failed to update settings for provider: {provider}")
        
    return success




def settingsActivate(toggles):

    chromiumFlags = [
        #allows DNS over HTTPS system
        "--enable-features=DnsOverHttps ", 
        "--force-fieldtrials=AsyncDns/Enabled",
        #enables logging to be output
        #"--enable-logging=stderr",
        #"--v=1"
        "--log-level=3"
        ]

    if "Cookie-Prediction-Sensitivity" in toggles.keys():
        global sensitivity
        sensitivity = toggles["Cookie-Prediction-Sensitivity"] #0 for limited blocking, 1 for middle ground, 2 for extensive, 3 for block everything with no limits. Anything past 1 may break persistent data
    
    if "Cookie-Auto-Handler" in toggles.keys():
        global cookieAutoHandler
        cookieAutoHandler = toggles["Cookie-Auto-Handler"]

    if "Cookie-Accept/Deny-On-Leave" in toggles.keys():
        global siteLeaveCookies
        siteLeaveCookies = toggles["Cookie-Accept/Deny-On-Leave"] #0 for remove all, 1 for accept all

    if "Save-Tabs-On-Restart" in toggles.keys():
        global saveTabsOnRestart
        saveTabsOnRestart = toggles["Save-Tabs-On-Restart"]

    if toggles["Utilise-QUIC-Browsing"]:
        chromiumFlags.extend([
            "--enable-quic",
            "--origin-to-force-quic-on=cloudflare-quic.com:443"
        ])
    if toggles["GPU-Safe-System"]:
        chromiumFlags.extend([
            "--disable-accelerated-video-decode"
        ])

    if toggles["DeGoogler"] == True:
        #Disable all screened google flags that allow for a degoogled experience without compromising security too much. This is intneded to be a power-user feature that removes google alongside their inbuilt user protections under the assumption that the user knows what they're doing
        chromiumFlags.extend([
            "--disable-domain-reliability", #Disables reporting network errors to google
            "--disable-features=MediaRouter,Translate", #Disable chromecast / LAN device discovery
            "--disable-component-update", #Stops attempting to update the internal registry of extensions
            "--disable-component-extensions-with-background-pages", #More extensions disabling
            "--disable-default-apps", #Stops installation of default apps on startup
            "--disable-stack-profiler", #Disables extra internal telemetry gathering and improves speed slightly
            "--disable-background-networking" #Stops all background chromium processes, including most metrics systems but also a variety of helpful systems like Chromium's inbuilt phishing detection systems. For advanced users only.
        ])


    if chromiumFlags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(chromiumFlags)


#value clamper
def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))

#Filter update system
def update_filters():
    filter_path = srcSourceDir / "data" / "urlblockerlist.txt"
    urllist = [
        "https://easylist.to/easylist/easylist.txt", 
        "https://easylist.to/easylist/easyprivacy.txt", 
        "https://secure.fanboy.co.nz/fanboy-annoyance.txt", 
        "https://secure.fanboy.co.nz/fanboy-cookiemonster.txt"
    ]
    
    if not filter_path.exists():
        filter_path.parent.mkdir(parents=True, exist_ok=True)
        print("Midnight Shield: Updating filters...")

        with open(filter_path, "w") as f:
            pass #clear text file
        with open(filter_path, "a", encoding="utf-8") as f:
            for url in urllist:
                try:
                    response = requests.get(url, timeout=15)
                    if response.status_code == 200:
                        # Write the text content plus a newline for safety
                        f.write(response.text + "\n")
                        print(f"Grabbed: {url.split('/')[-1]}")
                    else:
                        print(f"Server error {response.status_code} on {url}")
                except Exception as e:
                    print(f"Failed to download {url}: {e}")
        
        print("Midnight Shield: All filter data compiled.")
        return True
    return False


#Converts image to an alpha channel and a colour channel. Turns all colours to white, removes alpha, then triggers a mask recolour to the desired appearance bsaed on json file
def buttoncolourer(k, v, name=None):
    if name == None:
        name = (str(k).split("_btn"))[0]
    else:
        pass
    filepath = (f"{icon_cache_dir}/{name}.png")
    img = Image.open(filepath).convert('RGBA')
    r, g, b, a = img.split() #only need 'a' value
    #convert to white for better handling
    white_img = Image.new("RGBA", img.size, (255, 255, 255, 255))
    mask_white = white_img.copy()
    mask_white.putalpha(a)
    #convert colour data into usable rgb tuple SAFELY - consider paramaterising this to avoid injection
    vstrip = v.strip('()').split(',')
    newv = tuple(int(i) for i in vstrip)
    coloured = Image.new("RGBA", img.size, newv+(255,))
    coloured.putalpha(a)
    colouredpath = (f"{icon_cache_dir}/{name}.png")
    coloured.save(colouredpath, format='PNG')
    return colouredpath

def ensure_webchannel_js(target_dir):
    js_path = os.path.join(target_dir, "qwebchannel.js")
    # Only write it if it doesn't exist, or overwrite every time to stay updated
    if not os.path.exists(js_path):
        # This path is internal to the PySide6 binary
        resource_file = QFile(":/qtwebchannel/qwebchannel.js")
        if resource_file.open(QIODevice.OpenModeFlag.ReadOnly):
            content = resource_file.readAll().data()
            with open(js_path, "wb") as f:
                f.write(content)
            resource_file.close()

# Management for chromium flag observations to protect users in case of encoded video playback failure
FatalGPUPatterns = {
    "CONTEXT_LOST_WEBGL": 5,
    "SharedImageManager::ProduceSkia": 8,
    "Trying to make lost context current": 3,
    "MailboxVideoFrameConverter": 4,
    "NativeSkiaOutputDevice": 3,
}
PATTERN_STRING = "|".join(re.escape(key) for key in FatalGPUPatterns.keys())
GPU_ERROR_REGEX = re.compile(PATTERN_STRING)
GPUErrorMonitor = GPULogMonitor(time_window=5.0, severity_threshold=10, error_regex=GPU_ERROR_REGEX, fatalPatterns=FatalGPUPatterns)

def qt_message_router(msg_type, context, message):
    #Remove connection refused error because the notification system is now in place
    if "error -101" in message or "SSL" in message or "net::ERR_CONNECTION_REFUSED" in message:
        return
    #turn off the qt logging for webenginecontext because it's unimportant noise for the devtools window as a result of pyqt6 stripping parts of chromium
    #also because fixing it is near impossible and it's driving me nuts
    if "Autofill.enable" in message or "Autofill.setAddresses" in message:
        return

    if msg_type in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg):
        GPUErrorMonitor.process_line(message)
    
    try:
        if msg_type == QtMsgType.QtDebugMsg:
            print(f"Debug: {context}, {message}")
        elif msg_type == QtMsgType.QtWarningMsg:
            print(f"Warning: {context}, {message}")
        elif msg_type == QtMsgType.QtCriticalMsg:
            print(f"Critical: {context}, {message}")
        elif msg_type == QtMsgType.QtFatalMsg:
            print(f"Fatal: {context}, {message}")
            sys.exit(-1)
    except:
        if msg_type == QtMsgType.QtDebugMsg:
            print(f"Debug: {context.toString()}, {message}")
        elif msg_type == QtMsgType.QtWarningMsg:
            print(f"Warning: {context.toString()}, {message}")
        elif msg_type == QtMsgType.QtCriticalMsg:
            print(f"Critical: {context.toString()}, {message}")
        elif msg_type == QtMsgType.QtFatalMsg:
            print(f"Fatal: {context.toString()}, {message}")
            sys.exit(-1)




class objectMasterBridge(QObject):
    # Signal to push updates to JS (like a ticking clock or settings change)
    dataUpdated = Signal(str, str) # (key, value)

    # Signal to request a search from the html page
    searchRequested = Signal(str)

    #Placeholder signal to send back adjustments to the actionToggles.json file
    dataReturned = Signal(str, str)


    def __init__(self, browser, page=None):
        super().__init__()
        with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            self.colourData = dict(json.load(f))
        self.browser = browser
        self.page=page

    def trusted_origin(self):
        if not self.page:
            return False
        url=self.page.url()
        print(url.toString())
        return (url.scheme().lower()=="midnightwatch" and url.host().lower()=="local")

    @Slot(str)
    def receiveSearchQuery(self, query):
        cQuery = query.strip()
        if cQuery:
            print("HTML Bridge received: " + cQuery)
            self.searchRequested.emit(cQuery)

    @Slot(list)
    def receiveData(self, data):
        if not self.trusted_origin():
            print("MIDNIGHT SHIELD: Blocked bridge call from untrusted source.")
            return
        
        if data:
            #data is returned as a list giving [0, 1] for [header, value] for insertion into json files
            dataHeader = data[0]
            dataValue = data[1]
            print(f"Received data: {dataHeader}: {dataValue}")

            settingsData = self.browser.settingsData
            
            if dataHeader == "blur-slider":
                settingsData["Blur"] = round(int(dataValue) / 25)
            
            if dataHeader == "cookieFilterSens":
                new_level = int(dataValue)
                settingsData["Cookie-Prediction-Sensitivity"] = new_level
                self.browser.cookieManager.updateSensitivity(new_level)

            if dataHeader == "cookieAutoHandler":
                settingsData["Cookie-Auto-Handler"] = (str(dataValue).lower() == "true")
                self.browser.cookieManager.updateHandler(int(dataValue))

            if dataHeader == "cookieMassDelete":
                self.browser.cookieMassDelete()

            if dataHeader == "DNSoverHTTPS": 
                settingsData["DNS-over-HTTPS"] = str(dataValue)

                #Trigger informational changes
                updateDoHSettings(str(dataValue), settingsData)

            if dataHeader == "TabCloseAction": 
                settingsData["Cookie-Accept/Deny-On-Leave"] = (str(dataValue).lower() == "true")
            
            if dataHeader == "SaveTabsOnReload":
                settingsData["Save-Tabs-On-Restart"] = (str(dataValue).lower() == "true")

            if dataHeader == "DisplayGreeting":
                settingsData["Greeting"] = (str(dataValue).lower() == "true")

            if dataHeader == "nameInput":
                settingsData["Name"] = (str(dataValue))

            if dataHeader == "timeInput":
                settingsData["Time-Display"] = (str(dataValue))

            if dataHeader == "Tab Bar Pos": 
                keymap = {
                    "Top": "North",
                    "Bottom": "South",
                    "Vertical Left": "West",
                    "Vertical Right": "East" 
                }
                settingsData["Tab-Position"] = (keymap[str(dataValue)])
            
            if dataHeader == "Stacks":
                try:
                    data_dict = json.loads(dataValue)

                    top_stack = data_dict.get("Top-Stack", [])
                    bottom_stack = data_dict.get("Bottom-Stack", [])
                    hidden_stack = data_dict.get("Hidden-Stack", [])

                    settingsData["Top-Stack"] = top_stack
                    settingsData["Bottom-Stack"] = bottom_stack
                    settingsData["Hidden-Stack"] = hidden_stack
                    
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON: {e}")

            if dataHeader == "Date Display":
                format_map = {
                    "Global": "dd/MM",
                    "US": "M/d",
                    "ISO": "MM-dd",  
                    "Long-Form": "dddd, d MMMM",
                    "Minimalist": "dd MMM"
                }
                (settingsData["Date-Display"])[0] = (format_map[str(dataValue)])

            if dataHeader == "yearInDate":
                (settingsData["Date-Display"])[1] = (str(dataValue).lower() == "true")
            
            if dataHeader == "advDate":
                settingsData["Date-Display"][0] = (str(dataValue))

            if dataHeader == "QUICBrowse":
                settingsData["Utilise-QUIC-Browsing"] = (str(dataValue).lower() == "true")
            
            if dataHeader == "DeGoogler":
                settingsData["DeGoogler"] = (str(dataValue).lower() == "true")

            if dataHeader == "DnsFallback":
                settingsData["Dns-Fallback"] = (str(dataValue).lower() == "true")
                updateDoHSettings(settingsData["DNS-over-HTTPS"], settingsData)

            if dataHeader == "GPUSafeSystem":
                settingsData["GPU-Safe-System"] = (str(dataValue).lower() == "true")
            
            if dataHeader == "imageUpload":
                fileInfo = dataValue
                fileName = fileInfo["name"]
                header, encoded = fileInfo["data"].split(",", 1)
                file_bytes = base64.b64decode(encoded)

                #Image upload sanitiser - make sure it's not a hidden attack
                try:
                    img = Image.open(io.BytesIO(file_bytes))
                    
                    # For GIFs and other formats, just check the format is valid
                    # Don't call verify() on GIFs as it can fail with animations
                    if img.format and img.format.upper() in ['PNG', 'JPEG', 'GIF', 'BMP', 'WEBP']:
                        # Format is valid, proceed with upload
                        pass
                    else:
                        raise ValueError(f"Unsupported image format: {img.format}")

                    new_file_hash = hashlib.md5(file_bytes).hexdigest()
                    save_path = os.path.join(f"{srcSourceDir}/ui/images/", fileName)

                    if os.path.exists(save_path):
                        with open(save_path, "rb") as existing_file:
                            existing_hash = hashlib.md5(existing_file.read()).hexdigest()
                        
                        if new_file_hash == existing_hash:
                            print("Attempted upload image present in files already! Defaulting to using current name")
                        else:
                            random_suffix = uuid.uuid4().hex[:8]
                            name_part, extension = os.path.splitext(fileName)
                            fileName = f"{name_part}_{random_suffix}{extension}"
                            save_path = os.path.join(f"{srcSourceDir}/ui/images/", fileName)

                    with open(save_path, "wb") as f:
                        f.write(file_bytes)
                    
                    settingsData["Image-Url"] = fileName
                    print(f"Successfully uploaded image: {fileName}")
                
                except Exception as e:
                    print(f"Image upload failed: {e}")

            if dataHeader == "themeUpdate":
                with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
                    ColourData = json.load(f)
                
                dictName = next(iter(dataValue))
                ColourData[dictName] = dataValue[dictName]
                print(ColourData[dictName])
                
                with open(f"{srcSourceDir}/data/colourProfiles.json", "w") as f:
                    json.dump(ColourData, f, indent=4)

                self.browser.colourMenu.clear()
                self.browser.colourpalette_btn, self.browser.colourMenu = (self.browser.barManager.setup_colourPalette_button(ColourData))
                
                #select applied colour theme
                self.browser.SelectColourTheme(dictName, ColourData)

            
            #Return edited data to the json file
            with open (f"{srcSourceDir}/data/actionToggles.json", "w") as file_return:
                json.dump(settingsData, file_return, indent=4)

            #Trigger a re-update of remaining systems
            self.browser.settingsData = settingsData.copy()
            settingsActivate(settingsData)

    @Slot(str, result=str)
    def getData(self, key):
        with open (f"{srcSourceDir}/data/actionToggles.json", "r") as file_grab:
                settingsData = dict(json.load(file_grab))

        #Generalised getter for JS to pull data
        if key == "time":
            timeFormat = (settingsData["Time-Display"])
            timeCall = QDateTime.currentDateTime()
            #Syntax: time display goes "hh:mm:ss AP". AP is whether to display AM/PM, lowercase hh means 12-hr, uppercase means 24-hr. 
            # Note current restrictions in settings menu allow any combination of these characters up to a max of 32 chars
            return timeCall.toString(f"{timeFormat}")

        elif key == "date":
            #Syntax: formatting [0] is one of 5 options - Global, US, ISO, Long-Form, Minimalist. Formatting is below but super complicated. Formatting [1] is true/false for year.
            """
            d: Day number with no leading zero (e.g 1)
            dd: Day number with leading zero (e.g. 01)
            ddd: Abbreviated localized day name (e.g. “Mon”)
            dddd: Long localized day name (e.g. “Monday”)
            M: Month number with no leading zero (e.g. 1)
            MM:Month number with leading zero (e.g. 01)
            MMM:Abbreviated localized month name (e.g. “Jan”)
            MMMM:Long localized month name (e.g. “January”)
            yy:Year as two digit number (e.g. 99)
            yyyy: Year as four digit number (e.g. 1999). Can be a negative number for BCE years.
            """

            date_format, provide_year = settingsData["Date-Display"][0], settingsData["Date-Display"][1]
            dateCall = QDateTime.currentDateTime()

            # Define base formats without year info
            format_map = {
                    "dd/MM": "Global",
                    "M/d": "US",
                    "MM-dd": "ISO",  
                    "dddd, d MMMM": "Long-Form",
                    "dd MMM": "Minimalist"
                }
            
            if date_format in format_map.keys():
                base = format_map[date_format]

                # Specific year-attachment logic per format
                if provide_year:
                    if base == "ISO":
                        date_format = f"yyyy-{date_format}"
                    elif base in ["Global", "US"]:
                        date_format += "/yyyy"
                    else: # Long-Form and Minimalist
                        date_format += " yyyy"

            else:
                if provide_year:  
                    date_format += " yyyy"
                else:
                    pass


            return dateCall.toString(date_format)
        
        elif key == "greeting":
            if settingsData["Greeting"] == True:
                hourCall = int(QDateTime.currentDateTime().toString("HH")) #returns time in 24hr
                
                match hourCall:
                    case hC if 4 <= hC < 12:
                        return (f"Good Morning, " + settingsData["Name"]) if settingsData["Name"] != "" else (f"Good Morning")
                    case hC if 12 <= hC < 17:
                        return (f"Good Afternoon, " + settingsData["Name"]) if settingsData["Name"] != "" else (f"Good Afternoon")
                    case hC if 17 <= hC < 21:
                        return (f"Good Evening, " + settingsData["Name"]) if settingsData["Name"] != "" else (f"Good Evening")
                    case hC if (21 <= hC <= 23) or (0 <= hC < 4):
                        return (f"Sleep Well, " + settingsData["Name"]) if settingsData["Name"] != "" else (f"Sleep Well")
                    case _:
                        return (f"Hello, " + settingsData["Name"]) if settingsData["Name"] != "" else (f"Hello")
            else:
                return ""
        
        elif key == "BGimage":
            return str(f"images/{settingsData["Image-Url"]}")
        
        elif key == "settingsLink":
            return "midnightwatch://local/icon_cache/settings.png"
        
        # Settings html bridge section
        
        elif key == "blur":
            return str(settingsData["Blur"])
        
        elif key == "cookieSens":
            return str(settingsData["Cookie-Prediction-Sensitivity"])
        
        elif key == "cookieAutoHandler":
            return str(settingsData["Cookie-Auto-Handler"])
        
        elif key == "DNSoHTTPS":
            return str(settingsData["DNS-over-HTTPS"])
        
        elif key == "CookieActOnClose":
            return str(settingsData["Cookie-Accept/Deny-On-Leave"])
        
        elif key == "SaveTabsOnRestart":
            return str(settingsData["Save-Tabs-On-Restart"])
        
        elif key == 'GreetDisp':
            return str(settingsData["Greeting"])

        elif key == "Username":
            return str(settingsData["Name"])
        
        elif key == "timeInputDisplay":
            return str(settingsData["Time-Display"])
        
        elif key == "tabBarPos":
            keymap = {
                "North": "Top",
                "South": "Bottom",
                "West": "Vertical Left",
                "East": "Vertical Right"
            }
            return str(keymap[settingsData["Tab-Position"]])

        elif key == "StackEditor":
            StackEditorDict = {
                "Top-Stack": settingsData["Top-Stack"],
                "Bottom-Stack": settingsData["Bottom-Stack"],
                "Hidden-Stack": settingsData["Hidden-Stack"]
            }
            return json.dumps(StackEditorDict)

        elif key == "DateDisplay":
            format_map = {
                    "dd/MM": "Global",
                    "M/d": "US",
                    "MM-dd": "ISO",  
                    "dddd, d MMMM": "Long-Form",
                    "dd MMM": "Minimalist"
                }
            if settingsData["Date-Display"][0] in format_map.keys():
                return str(format_map[settingsData["Date-Display"][0]]) 
            else:
                return "Custom Date Value"
        
        elif key == "dateYear":
            return str(settingsData["Date-Display"][1])

        elif key == "AdvancedDateFormatting":
            return str(settingsData["Date-Display"][0])
        
        elif key == "ColourThemeNames":
            with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
                datalist = json.load(f)
            return json.dumps(datalist)
        
        elif key == "CurrentTheme":
            return str(settingsData["Colour-Theme"])    

        elif key == "QUICBrowsing":
            return str(settingsData["Utilise-QUIC-Browsing"])    

        elif key == "DeGoogler": 
            return str(settingsData["DeGoogler"])  

        elif key == "DnsFallback":
            return str(settingsData["Dns-Fallback"])

        elif key == "GPUSafeSystem":
            return str(settingsData["GPU-Safe-System"])
            
        else:
            return f"Error: Key: {str(key)} not found"

    
    @Slot(result='QVariant')
    def openFileDialog(self):

        path, _ = QFileDialog.getOpenFileName(
            None,
            "Select image",
            f"{srcSourceDir}/ui/images",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )

        if not path:
            return {}

        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()

        suffix = Path(path).suffix.lower()

        mime = {
            ".png":"image/png",
            ".jpg":"image/jpeg",
            ".jpeg":"image/jpeg",
            ".gif":"image/gif",
            ".bmp":"image/bmp",
            ".webp":"image/webp"
        }.get(suffix, "application/octet-stream")

        return {
            "name": Path(path).name,
            "mime": mime,
            "data": f"data:{mime};base64,{encoded}"
        }
        

    #Button deferred update system, call only on apply press to avoid overloading or potentially corrupting the main data storage file.
    @Slot(bool)
    def applySettings(self, shouldReload=False):

        settingsData = self.browser.settingsData

        # update live profile config
        self.browser.profile_config["stored_data"] = settingsData

        # persist to profileData.json
        saveData(self.browser.currentProfileID, self.browser.profile_config)

        if shouldReload:
            self.browser.fullRestart(triggerCloseEvent = False, profile_config=self.browser.profile_config.copy())
            

    


class profileSelectUI(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Profile Select")
        self.resize(1200, 800)
        self.setWindowIcon(get_normIcon("tightlyCroppedIcon.png"))

        with open(f"{srcSourceDir}/data/profileData.json", "r") as f:
            self.profileData = dict(json.load(f))

        self.chosenProfile = None
        self.lastSelectedProfile = None

        self.profile_buttons = {}

        self.NormalStyle = """
            QPushButton {
                background-color: rgb(60,60,75);
                color:white;
                border:2px solid rgb(63,129,255);
                border-radius:25px;
                font-size:14px;
                font-weight:bold;
            }

            QPushButton:hover {
                background-color: rgb(70,70,85);
                border:2px solid rgb(96,151,253);
            }

            QPushButton QLabel {
                background: transparent;
                border: none;
                color: white;
            }
            """

        self.SelectedStyle = """
            QPushButton {
                background-color: rgb(85,105,160);
                color:white;
                border:4px solid #3f81ff;
                border-radius:25px;
                font-size:14px;
                font-weight:bold;
            }

            QPushButton:hover {
                background-color: rgb(100,120,180);
            }

            QPushButton QLabel {
                background: transparent;
                border: none;
                color: white;
            }
            """

        self.init_ui()

    def init_ui(self):
        # Set background color to match settings menu (darker grey)
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(45, 45, 60);
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Title label
        title = QLabel("Select Profile")
        title.setStyleSheet("""
            color: white;
            font-size: 20px;
            font-weight: bold;
        """)
        main_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Centered scroll area for buttons
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: rgb(45, 45, 60);
                border: none;
            }
            QScrollBar:vertical {
                background: rgb(45, 45, 60);
                width: 12px;
                border-radius: 10px;
            }
            QScrollBar::handle:vertical {
                background: rgb(85, 85, 105);
                border-radius: 10px;
                border: 2px solid rgb(45, 45, 60);
            }
            QScrollBar::handle:vertical:hover {
                background: rgb(110, 110, 135);
            }
        """)
        scroll_area.setWidgetResizable(True)

        # Container widget with centered layout
        container = QWidget()
        container.setStyleSheet("background-color: rgb(45, 45, 60);")
        self.buttonBox = QHBoxLayout(container)
        self.buttonBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.buttonBox.setSpacing(15)
        self.buttonBox.setContentsMargins(40, 40, 40, 40)

        self.populate_profile_buttons()

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area, 1)




        self.selectionContainer = QWidget()
        self.selectionContainer.setStyleSheet("""
            border: 2px solid #3f81ff;
            border-radius: 30px;
            """)
        self.selectionContainer.setFixedHeight(125)
        self.selectBox = QVBoxLayout(self.selectionContainer)
        self.selectBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selectBox.setSpacing(10)
        self.selectBox.setContentsMargins(200, 10, 200, 10)

        # Create a horizontal layout for the three buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)  # Adjust space between buttons

        # Create three buttons
        btn1 = QPushButton("Select Profile")
        btn1.clicked.connect(lambda checked=False: self.select_profile())
        btn2 = QPushButton("Edit Profile")
        btn2.clicked.connect(lambda checked=False: self.edit_profile())
        btn3 = QPushButton("Delete Profile")
        btn3.clicked.connect(lambda checked=False: self.delete_profile())

        # Set common size
        for btn in (btn1, btn2, btn3):
            btn.setFixedSize(200, 75)
            btn.setStyleSheet("""
                              QPushButton {
                                background-color: rgb(60, 60, 75); 
                                color: white; font-weight: bold; font-size:15px; border-radius:15px;
                                }
                              QPushButton:hover {
                                background-color: rgb(70,70,85);
                                border: 2px solid rgb(96,151,253);
                                }""")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        btn1.setStyleSheet("""
                           QPushButton{
                            background-color: #3f81ff; 
                            color: white; 
                            font-weight: bold; 
                            font-size:15px; 
                            border-radius:15px;
                            }
                           QPushButton:hover {
                           background-color: #7ba9fd;
                           border: 2px solid rgb(96,151,253);
                           }""")

        # Add buttons to the horizontal layout        
        button_layout.addWidget(btn3)
        button_layout.addWidget(btn2)
        button_layout.addWidget(btn1)

        # Add the horizontal layout to the main vertical layout
        self.selectBox.addLayout(button_layout)   


        self.selectorHolder = QWidget()
        self.selectorHolder.setMaximumHeight(0)

        holder_layout = QVBoxLayout(self.selectorHolder)
        holder_layout.setContentsMargins(0,0,0,0)

        holder_layout.addWidget(self.selectionContainer)

        main_layout.addWidget(self.selectorHolder)

        self.animation = QPropertyAnimation(
            self.selectorHolder,
            b"maximumHeight"
        )

        self.animation.setDuration(300)

    def summonSelector(self, profile_key):

        if profile_key == self.lastSelectedProfile:
            self.animation.setStartValue(145)
            self.animation.setEndValue(0)

            self.chosenProfile = None
            self.lastSelectedProfile = None

        else:
            self.animation.setStartValue(0)
            self.animation.setEndValue(145)   # slightly bigger than container

            self.chosenProfile = profile_key
            self.lastSelectedProfile = profile_key

        self.updateSelectedButton()
        self.animation.start()

    def select_profile(self):
        """Handle profile selection"""
        self.selected_profile = self.chosenProfile
        self.accept()

    def edit_profile(self):
        dialog = NewProfileDialog(self, 
                                  title=f"Edit Profile {self.profileData[self.chosenProfile]["Name"]}", 
                                  placeholder=f"Previously: '{self.profileData[self.chosenProfile]["Name"]}'", 
                                  image = srcSourceDir/self.profileData[self.chosenProfile]["photoURL"],
                                  image_text = "Current Profile Image:")
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            returned_data = dialog.getData()
            self.profileData[self.chosenProfile]["Name"] = returned_data["name"]
            image_path = returned_data["photoURL"]

            if image_path:
                if os.path.exists(image_path):
                    fileName = os.path.basename(image_path)
                    save_path = os.path.join(srcSourceDir, "ui/profile_icons", fileName)
                    
                    try:
                        if image_path != save_path:
                            shutil.copy(image_path, save_path)
                    except shutil.SameFileError: #Avoid errors in file duplication/overwrite
                        pass

                    self.profileData[self.chosenProfile]["photoURL"] = f"ui/profile_icons/{fileName}"
                else:
                    QMessageBox.warning(self, "Invalid Input", "No image path could be found! Remaining with current image.")
            
            for key, profile in list(self.profileData.items()):
                if profile.get("Name") == "Add New Profile":
                    print(self.profileData[key])
                    del self.profileData[key]

            with open(f"{srcSourceDir}/data/profileData.json", "w") as f:
                    json.dump(self.profileData, f, indent=4)
            
            self.refresh_ui()

    def delete_profile(self):
        if self.WindowConfirmation("Confirm Deletion", f"Are you sure you'd like to delete the profile: '{self.profileData[self.chosenProfile]['Name']}' permanently?"):
            
            if self.chosenProfile in self.profileData:
                del self.profileData[self.chosenProfile]

            reindexed_profiles = {}
            new_index = 0
            
            for key, profile_content in self.profileData.items():
                # Skip the temporary "Add New Profile" if it's currently saved in data
                if profile_content.get("Name") == "Add New Profile":
                    continue
                    
                # Assign the clean, sequential ID to the profile data structure
                new_key = f"id{new_index}"
                reindexed_profiles[new_key] = profile_content
                new_index += 1
                
            self.profileData = reindexed_profiles

            with open(f"{srcSourceDir}/data/profileData.json", "w") as f:
                json.dump(self.profileData, f, indent=4)
                
            self.refresh_ui()


    def create_new_profile(self, profile_key):
        dialog = NewProfileDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            profile_data = dialog.getData()

            if profile_data and profile_data["name"]:

                self.profileData[profile_key]["Name"] = profile_data["name"]

                image_path = profile_data["photoURL"]

                # fallback if none selected
                if not image_path:
                    image_path = f"{srcSourceDir}/ui/profile_icons/add_profile.png"

                # copy image into app folder
                if os.path.exists(image_path):
                    fileName = os.path.basename(image_path)
                    save_path = os.path.join(srcSourceDir, "ui/profile_icons", fileName)

                    try:
                        if image_path != save_path:
                            shutil.copy(image_path, save_path)
                    except shutil.SameFileError: #Avoid errors in file duplication/overwrite
                        pass

                    self.profileData[profile_key]["photoURL"] = f"ui/profile_icons/{fileName}"
                else:
                    self.profileData[profile_key]["photoURL"] = "ui/profile_icons/add_profile.png"
                
                self.profileData[profile_key]["saved_tabs"] = {}
                self.profileData[profile_key]["saved_bookmarks"] = {}

                with open(f"{srcSourceDir}/data/profileData.json", "w") as f:
                    json.dump(self.profileData, f, indent=4)

            else:
                QMessageBox.warning(self, "Invalid Input", "Please enter a valid name.")
        
        self.refresh_ui()

    def populate_profile_buttons(self):
        self.buttonBox.addStretch()

        #first button - create new icon button
        #source ID as next value
        id = int((next(reversed(self.profileData.keys())))[2:]) + 1 if self.profileData else 0
        #source data for new profile from the default profile - grab from default or otherwise just add default values
        stored_data = self.profileData["id0"]["stored_data"] if "id0" in self.profileData else {"DNS-over-HTTPS": "AdGuard","Cookie-Prediction-Sensitivity": 0,"Cookie-Accept/Deny-On-Leave": 0,"Save-Tabs-On-Restart": 0,"Tab-Position": "North","Top-Stack": ["nav_bar","bookmarks_bar"],"Bottom-Stack": ["status_bar"],"Hidden-Stack": [],"Date-Display": ["dddd, d MMMM",1],"Time-Display": "hh:mm AP","Name": "Default","Greeting": 1,"Blur": 10,"Image-Url": "MainImageBackground.png","Colour-Theme": "Secured Blue","Utilise-QUIC-Browsing": 1,"DeGoogler": 0, "Dns-Fallback": 1, "GPU-Safe-System": 0, "Cookie-Auto-Handler": 1}
           
        self.profileData[f"id{id}"] = {
            "Name": "Add New Profile",
            "photoURL": "ui/profile_icons/add_profile.png",
            "stored_data": stored_data
        }

        # Create buttons for each profile
        for i in range(len(self.profileData.keys())):

            profile_key = "id" + str(i)
            profile_name = self.profileData[profile_key]["Name"]
            profile_photo = f'{srcSourceDir}/{self.profileData[profile_key]["photoURL"]}'

            btn = QPushButton()
            btn.setFixedSize(250,270)

            btn.setStyleSheet(self.NormalStyle)

            btn.setToolTip(profile_name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            layout = QVBoxLayout(btn)
            layout.setContentsMargins(8,8,8,8)
            layout.setSpacing(0)

            text = QLabel(profile_name)
            text.setStyleSheet("""
                color:white;
                font-size:14px;
                font-weight:bold;
            """)
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)

            icon = QLabel()
            if os.path.exists(profile_photo):
                pixmap = QPixmap(profile_photo)
                if not pixmap.isNull():
                    icon.setPixmap(pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            
            icon.setContentsMargins(15, 15, 15, 15)

            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            layout.addWidget(icon)
            layout.addWidget(text)
            
            if profile_name == "Add New Profile":
                btn.clicked.connect(lambda checked=False, profile=profile_key: (self.create_new_profile(profile), self.summonSelector(None)))
            else:
                btn.clicked.connect(lambda checked=False, profile=profile_key: self.summonSelector(profile))
            self.buttonBox.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

            self.profile_buttons[profile_key] = btn

        self.buttonBox.addStretch()

    def refresh_ui(self):
        #Clear profile buttons
        while self.buttonBox.count() > 0:
            item = self.buttonBox.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()  # Safely delete old QPushButton

        #Re-read the updated data from JSON file
        with open(f"{srcSourceDir}/data/profileData.json", "r") as f:
            self.profileData = dict(json.load(f))
        
        self.summonSelector(None)

        # Re-run the UI loops
        self.populate_profile_buttons()
    
    def updateSelectedButton(self):

        for key, btn in self.profile_buttons.items():

            if key == self.chosenProfile:
                btn.setStyleSheet(self.SelectedStyle)
            else:
                btn.setStyleSheet(self.NormalStyle)

    
    def WindowConfirmation(self, title, message):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.exec()
        return msg_box.clickedButton() == msg_box.button(QMessageBox.StandardButton.Yes)

    def getSelectedConfig(self):
        if hasattr(self, 'selected_profile'):
            data = self.profileData[self.selected_profile].copy()
            data["id"] = self.selected_profile
            return data
        return None






class Browser(QMainWindow):
    def __init__(self, profile_config: dict):
        super().__init__()
        self.setWindowTitle("Midnight Watch Browser")
        self.resize(1200, 800)
        self.setWindowIcon(get_normIcon("tightlyCroppedIcon.png"))
        global eColsStyle
        global eColsButton
        global sensitivity
        global cookieAutoHandler

        #update main loader json file with the info selected from the profile
        profileData = profile_config["stored_data"]
        self.profile_config = profile_config

        if profile_config["Name"] == "Ephemeral":
            self.profile = QWebEngineProfile("Ephemeral", self)
        else:
            self.profile = QWebEngineProfile("PersistentUser", self)

        #Assign URL Scheme to page loaders
        self.handler = UrlCustomSchemeManager()
        self.profile.installUrlSchemeHandler(b"midnightwatch", self.handler)

        #Create browser widgets
        self.current_browser = QWebEngineView(self)
        
        #Link webview to context menu to override main caller class
        self.current_browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.current_browser.customContextMenuRequested.connect(lambda pos: self.displayWebContextMenu(pos))

        #Create devtools window link #1
        self.devtools_view = QWebEngineView()
        self.devtools_page = QWebEnginePage(self.current_browser.page().profile(), self.devtools_view)
        self.devtools_view.setPage(self.devtools_page)
        self.current_browser.page().setDevToolsPage(self.devtools_page)
        self.devtools_view.closeEvent = self.devtoolsCloseEvent


        self.is_restarting = False
        self.pending_restart = False

        with open(f"{srcSourceDir}/data/actionToggles.json","w") as f:
            json.dump(profileData, f, indent=4)

        self.settingsData = json.loads(json.dumps(profileData))
        self.currentProfileID = profile_config.get("id", None)

        settingsActivate(self.settingsData)

        #Url Manager
        self.UrlManager = UrlManager()
        
        #load webchannel data from internal system to ui folder
        ensure_webchannel_js(os.path.join(srcSourceDir, "ui"))

        #settings system
        settings = self.profile.settings()
        #Set to false to enable sandboxing and security
        #Stops local content from fetching outside content, would block execution scripts that install remote tools. Ties into QFlagged UrlScheme that my files all hook into that instead of directly running it
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        #Naturally avoid, baseline security
        settings.setAttribute(settings.WebAttribute.AllowRunningInsecureContent, False)
        #Avoids silent clipboard access, helps in privacy
        settings.setAttribute(settings.WebAttribute.JavascriptCanAccessClipboard, False)
        #Blocks local running html that isn't authorised via the QFlagged UrlScheme
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, False)

        #Security enable settings
        settings.setAttribute(settings.WebAttribute.XSSAuditingEnabled, True)

        #Would be good to disable for efficiency and maximum security but I need javascript actually working.
        settings.setAttribute(settings.WebAttribute.JavascriptEnabled, True)
        


        #Data storage management - future plans to use this for history saving
        if profile_config["Name"] != "Ephemeral":
            base_path = os.path.abspath("./Main_Repo/src/data/Browser_Data")
            profile_path = os.path.join(base_path, "User_Profile")
            cache_path = os.path.join(base_path, "User_Cache")

            os.makedirs(profile_path, exist_ok=True)
            os.makedirs(cache_path, exist_ok=True)

            self.profile.setCachePath(cache_path)
            self.profile.setPersistentStoragePath(profile_path)
            self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
            self.profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)



        #Update adblocker filters from easylist
        update_filters()
        #Adblock interceptor
        self.interceptor = AdInterceptor()
        self.profile.setUrlRequestInterceptor(self.interceptor)

        

        #Initialise cookie jar (Cookie management)
        self.cookieManager = CookieManager(self.profile, sensitivity, cookieAutoHandler)
        self.cookie_store = self.profile.cookieStore()
        self.cookie_store.loadAllCookies() 
        self.cookie_store.cookieAdded.connect(self.on_cookie_received)
        self.cookiedict = {} #Set up for later to store cookies for display in the accept/deny GUI


        #Bar Management System
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.barManager = BarManager(self, eColsStyle, eColsButton)
        self.additionalUIElements = additionalUIElements(self)

        self.tabs = self.barManager.setup_tabs()

        if self.settingsData["Tab-Position"] in ["East", "West"]:
             self.tabs.tabCloseRequested.connect(lambda i: QTimer.singleShot(0, self.tabs.tabBar().update_hover_from_cursor))
        self.tabs.tabCloseRequested.connect(lambda i: (self.close_tab(i)))
        self.tabs.currentChanged.connect(self.switch_tab)

        #Attach tab bar to right click menu
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.displayTabsContextMenu)

        self.nav_bar = self.barManager.setup_navbar()

        self.bookmarks_bar = self.barManager.setup_bookmarksbar(self.profile_config["saved_bookmarks"] if not None else {})

        self.status_bar = self.barManager.setup_statusbar(profile_icon=f"{srcSourceDir}/{profile_config['photoURL']}", name=profile_config["Name"])


        #set components on top and bottom based on json settings
        for element in self.settingsData["Top-Stack"]:
            widget = getattr(self, element, None)
            if widget:
                self.layout.addWidget(widget)
            else:
                print("Couldn't find mapping assignment for top bar element: ", element)

        mapping = {
            "North": QTabWidget.TabPosition.North,
            "South": QTabWidget.TabPosition.South,
            "West": QTabWidget.TabPosition.West,
            "East": QTabWidget.TabPosition.East
        }
        #set tab alignment based on JSON setting
        self.tabs.setTabPosition(mapping[self.settingsData["Tab-Position"]])
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.tabs, 1)

        for element in self.settingsData["Bottom-Stack"]:
            widget = getattr(self, element, None)
            if widget:
                self.layout.addWidget(widget)
            else:
                print("Couldn't find mapping assignment for bottom bar element: ", element)

        self.url_bar = self.barManager.setup_url_bar()
        #link mouse presses on the url bar to automatically highlight text
        self.url_bar.mousePressEvent = self._url_bar_mouse_press

        self.setCentralWidget(self.container)

    

        #Colour palette systems
        self.selectedprofile = self.settingsData["Colour-Theme"]
        print(self.selectedprofile)

        with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            Colourdata = dict(json.load(f))
        self.colourpalette_btn, self.colourMenu = self.barManager.setup_colourPalette_button(Colourdata)
        


        #engine system
        with open (f"{srcSourceDir}/data/engineData.json", "r") as f:
            engineData = dict(json.load(f))

        self.engines = {}
        engine = ""
        for key, value in engineData.items():
            self.engines[key] = value
            if value["active"] == 1:
                engine = key

        #print("ENGINES LIST FROM JSON: ", engines)
        print("Startup Selected Engine: ", engine)

        self.engine = engine
        self.engine_btn = None
        self.engine_btn, self.browserMenu = self.barManager.setup_engine_button(self.engines)
        self.current_browser.urlChanged.connect((lambda qurl, browser=self.current_browser: self.on_url_changed(qurl, browser)))



        #Cookie Menu GUI
        self.cookie_btn, self.cookieMenu = self.barManager.setup_cookie_button()
        self.cookieMenu.aboutToShow.connect(self.cookieGUI)

        #Right Click Context Menu
        self.RContextMenu = self.barManager.setupContextMenu()
        self.Bookmark_menu = QMenu()

        #final reset to styling to skip default selection
        self.SelectColourTheme(self.selectedprofile, Colourdata)

        #Deploy js code when webpage starts
        EVAdInterceptor.deployPayload(browser=self.current_browser, profile=self.profile)


        #Actions list using commands

        #Quit command
        exit_action = QAction("&Exit", self)
        self.addAction(exit_action)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.shutdown_Systems)

        #Close tab command
        tabclose_action = QAction("&Close &Tab", self)
        self.addAction(tabclose_action)
        tabclose_action.setShortcut(QKeySequence("Ctrl+W"))
        tabclose_action.triggered.connect(lambda ok: self.close_tab())

        #Add tab command
        tabopen_action = QAction("&New &Tab", self)
        self.addAction(tabopen_action)
        tabopen_action.setShortcut(QKeySequence("Ctrl+T"))
        tabopen_action.triggered.connect(self.add_new_tab)

        #Reload tab command
        tabreload_action = QAction("&Reload &Tab", self)
        self.addAction(tabreload_action)
        tabreload_action.setShortcut(QKeySequence("Ctrl+R"))
        tabreload_action.triggered.connect(self.reload_tab)

        #Tab Forward command
        tabForward_action = QAction("&Go Forward", self)
        self.addAction(tabForward_action)
        tabForward_action.setShortcut(QKeySequence("Alt+Right"))
        tabForward_action.triggered.connect(lambda ok: self.go_forward())

        #Tab backward command
        tabBack_action = QAction("&Go Back", self)
        self.addAction(tabBack_action)
        tabBack_action.setShortcut(QKeySequence("Alt+Left"))
        tabBack_action.triggered.connect(lambda ok: self.go_back())
        
        #Swap to index tabs command
        available_indexes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
        for idx in available_indexes:
            action = QAction(self)
            action.setShortcut(QKeySequence(f"Ctrl+{idx}"))
            action.triggered.connect(lambda checked=False, idx=idx: self.tabs.setCurrentIndex(9 if idx == 0 else idx - 1))
            self.addAction(action) 

        tabScrollRight_action = QAction(self)
        self.addAction(tabScrollRight_action)
        tabScrollRight_action.setShortcut(QKeySequence(f"Ctrl+Right"))
        tabScrollRight_action.triggered.connect(lambda ok: self.tabs.setCurrentIndex(int(self.tabs.currentIndex()) + 1))

        tabScrollLeft_action = QAction(self)
        self.addAction(tabScrollLeft_action)
        tabScrollLeft_action.setShortcut(QKeySequence(f"Ctrl+Left"))
        tabScrollLeft_action.triggered.connect(lambda ok: self.tabs.setCurrentIndex(int(self.tabs.currentIndex()) - 1))

        zoomIn_action = QAction(self)
        self.addAction(zoomIn_action)
        zoomIn_action.setShortcut(QKeySequence(f"Ctrl+="))
        zoomIn_action.triggered.connect(lambda ok: self.setContentZoom(True))

        zoomOut_action = QAction(self)
        self.addAction(zoomOut_action)
        zoomOut_action.setShortcut(QKeySequence(f"Ctrl+-"))
        zoomOut_action.triggered.connect(lambda ok: self.setContentZoom(False))

        #Mute tab command - need to actually build
        tabmute_action = QAction("&Mute &Tab", self)
        self.addAction(tabmute_action)
        tabmute_action.setShortcut(QKeySequence("Ctrl+M"))
        tabmute_action.triggered.connect(lambda ok: self.mute_tab(self.tabs.currentIndex()))



        #Miscellaneous additions

        #Zoom
        self.zoomValue = 100
        self.tab_zoom_values = {} #Dictionary to store zoom values for each tab
        self.is_panning = False
        self.pan_start_pos = None
        self.pan_offset_x = 0
        self.pan_offset_y = 0

        #close Event helper
        self.bypassCloseEvent = False



        # Register background processes

        # Dns fallback monitor
        if profileData["DNS-over-HTTPS"] != "Default":
            self.monitor = SecureDnsMonitor(profileData["Dns-Fallback"], doh_providers[profileData["DNS-over-HTTPS"]]["url"])

        # Instantiate error overlay
        self.overlay = EmergencyOverlay(parent=self)
        self.overlay.hide()
        self.overlay.reboot_requested.connect(lambda: self.fullRestart(triggerCloseEvent = False, profile_config=self.profile_config.copy()))


        #New Expandable Repetition Button system for help display
        self.buttonInternals = {
            #Main homescreen for pressing the help button
            "General": [None, "General", "help", 1],
            #Past this point are the internally defined clickable buttons
            "Back Help": [self.back_btn, "Back", "back", 1],
            "Forward Help": [self.forward_btn, "Forward", "forward", 1],
            "Settings Help": [self.settings_btn, "Settings", "settings", 1],
            "Home Help": [self.home_btn, "Home", "home", 1],
            "Reload Help": [self.reload_btn, "Reload", "reload", 1],
            "New Tab Help": [self.newtab_btn, "New Tab", "newtab", 1],
            "Colour Palettes Help": [self.colourpalette_btn, "Colour Palettes", "colourpalette", 1],
            "Search Engines Help": [self.engine_btn, "Engines", "tabIcon", 1],
            "Cookies Help": [self.cookie_btn, "Cookies", "cookie", 1],
            #Past this point are non internally-defined clickable areas, their controls are in ui_core
            "Tabs Help": [None, "Tabs", "tabIcon", 0],
            "Bookmarks Help": [None, "Bookmarks", "BookmarkNotAdded", 0],
            "UrlBar Help": [None, "Url Bar", "urlbar", 0],
            "Zooming Help": [None, "Zooming", "magnify", 0],
            "Profiles Help": [None, "Profiles", "profile", 0],
            "StatusBar Help": [None, "Status Bar", "statusbar", 0],
            #Past this point is non-clickable areas that appear at the bottom of the help index
            "Keybinds Help": [None, "Keybinds", "keybinds", 0]
        }

        #Run all browser startup triggers such as loading tabs from previous sessions.
        self.onStartup()








    ''' Internal Browser Management '''

    def onStartup(self):
        #Load all tabs from most recent shutdown if possible
        if saveTabsOnRestart:
            try:
                savetabs = self.profile_config["saved_tabs"]
                    
                for url, title in savetabs.items():
                    self.add_new_tab(QUrl(url), title)
                    self.update_tab_icon(self.current_browser)
                    
            except Exception as e:
                print("No tabs saved in startup OR an error has occurred.")
                print("Report: ", e)
        else:
            pass
        
        #Add a default homepage window
        self.add_new_tab()
        
        #Update all tabs to the correct appearance
        self.update_tab_icon(self.current_browser)

    def shutdown_Systems(self, restart=False):
            
        if saveTabsOnRestart:
            savetabs = {}
            for tab in range(self.tabs.count()):
                if "midnightwatch://" not in self.tabs.widget(tab).url().toString():
                    savetabs[self.tabs.widget(tab).url().toString()] = str(self.tabs.tabText(tab))
            
            self.profile_config["saved_tabs"] = savetabs
            
            #Update profileData json with new settings for current profile using ID
            saveData(self.currentProfileID, self.profile_config)

        self.restart_requested = restart
        #Clear HTTP cache to avoid potential clientside injection attacks
        self.profile.clearHttpCacheCompleted.connect(self.finish_shutdown)
        self.profile.clearHttpCache()
        #extra assurance shutdown command to avoid hanging on shutdown in case of httpcache clear failure
        QTimer.singleShot(3000, self.finish_shutdown)

    def fullRestart(self, triggerCloseEvent=True, profile_config=None):
        self.is_restarting = True
        self.pending_restart = True
        if triggerCloseEvent != True:
            self.bypassCloseEvent = True
        else:
            self.bypassCloseEvent = False
        print("FULL RESTART CALLED")
        with open(f"{srcSourceDir}/data/currentProfile.json","w") as f:
            json.dump(profile_config, f, indent=4)
        
        self.shutdown_Systems()

    def finish_shutdown(self):
        if getattr(self, "_shutdown_finished", False):
            return

        self._shutdown_finished = True

        if getattr(self, "pending_restart", False):
            QProcess.startDetached(sys.executable, sys.argv)

        QApplication.quit()

    def handleNewWindow(self, request):
        print("NEW WINDOW REQUEST")
        print(request.requestedUrl())

        new_tab = self.browser.add_new_tab()
        request.openIn(new_tab.page())

    #profile menu reloader system
    def open_profile_menu(self):
        if self.additionalUIElements.WindowConfirmation("Restart Required", "Browser will restart to allow profile changes. Continue?"):
            
            # Save current open tabs before restart
            if saveTabsOnRestart:
                savetabs = {}
                for tab in range(self.tabs.count()):
                    if "midnightwatch://" not in self.tabs.widget(tab).url().toString():
                        savetabs[self.tabs.widget(tab).url().toString()] = str(self.tabs.tabText(tab))
                
                self.profile_config["saved_tabs"] = savetabs
            
            # Close current browser window
            launcher = profileSelectUI()

            if launcher.exec() == QDialog.Accepted:

                profile = launcher.getSelectedConfig()

                self.fullRestart(profile_config=profile)

    def executeEmergency(self, danger):
        if danger == "accelVidDecodeErr":
            #trigger UI display
            self.current_browser.hide()
            title="Critical Rendering Error Detected"
            text="""Midnight Watch has detected unstable GPU rendering on your device
        Expected error: Accelerated Video Decoding error

        To ensure continual functionality, accelerated video decoding has been disabled
        (GPU Safe System should be enabled in settings)
        Please reboot the browser to resume operation"""
            self.overlay.set_content(title, text)
            self.overlay.setGeometry(0, 0, self.width(), self.height())
            self.overlay.show()
            self.overlay.raise_()
            self.current_browser.page().setAudioMuted(True)

            #set all profiles to GPU Safe System
            with open(f"{srcSourceDir}/data/profileData.json","r") as f:
                fullList = dict(json.load(f))

            for id, profileData in fullList.items():
                profileData["stored_data"]["GPU-Safe-System"] = True
                fullList[id] = profileData
            
            with open(f"{srcSourceDir}/data/profileData.json","w") as f:
                json.dump(fullList, f, indent=4)

            #Update current profile to allow the reboot to not use stale data
            self.profile_config["stored_data"]["GPU-Safe-System"] = True

    
    def displayContextMenu(self, pos, clicked_button):
        # Guard clause for potential errors
        if not clicked_button:
            return
        
        # Loop backwards through actions to safely remove elements without breaking index positions
        for action in reversed(self.RContextMenu.actions()):
            if action.objectName() in ["dynamic_help_action", 
                                        "dynamic_bookmark_action", 
                                        "dynamic_tab_action", 
                                        "dynamic_url_action", 
                                        "dynamic_status_action",
                                        "dynamic_web_action"]:
                self.RContextMenu.removeAction(action)
                action.deleteLater() # Clean up the memory instantly
        
        #Add in separator strip
        sep = self.RContextMenu.addSeparator()
        sep.setObjectName("dynamic_help_action")

        for action_text, components in self.buttonInternals.items():
            if components[3] == 1:
                target_button = components[0]
                helper_id = components[1]
                
                # Check if this configuration matches the right-clicked widget
                if clicked_button == target_button:
                    # Create the action dynamically
                    new_action = QAction(action_text, self)

                    new_action.setObjectName("dynamic_help_action")
                    
                    new_action.triggered.connect(lambda checked=False, id_str=helper_id: self.UIHelper(id_str))
                    
                    self.RContextMenu.addAction(new_action)
                    break  # Exit loop early since a match was discovered
            
            else:
                #pass for when the component isn't actually a part of the list. This is for elements to be added to the internal help display
                pass
                    
        
        #Set background of context menu transparent
        self.RContextMenu.setWindowFlags(self.RContextMenu.windowFlags() | Qt.FramelessWindowHint)
        self.RContextMenu.setAttribute(Qt.WA_TranslucentBackground)


        self.RContextMenu.exec(clicked_button.mapToGlobal(pos))

    def displayUrlBarContextMenu(self, pos):
        # Guard clause 
        if not hasattr(self, 'url_bar') or not self.url_bar:
            return

        for action in reversed(self.RContextMenu.actions()):
            if action.objectName() in ["dynamic_help_action", 
                                        "dynamic_bookmark_action", 
                                        "dynamic_tab_action", 
                                        "dynamic_url_action", 
                                        "dynamic_status_action",
                                        "dynamic_web_action"]:
                self.RContextMenu.removeAction(action)
                action.deleteLater()

        sep = self.RContextMenu.addSeparator()
        sep.setObjectName("dynamic_help_action")

        # Generate the native menu from the URL bar widget
        native_menu = self.url_bar.createStandardContextMenu()

        # Migrate the native actions
        if native_menu:
            for action in native_menu.actions():
                action.setObjectName("dynamic_url_action")
                self.RContextMenu.addAction(action)
            
            # Clean up the unrendered native menu shell from memory
            native_menu.deleteLater()
        
        sep = self.RContextMenu.addSeparator()
        sep.setObjectName("dynamic_url_action")

        # Extra components
        clear_url_action = QAction("Clear URL Bar", self)
        clear_url_action.setObjectName("dynamic_url_action")
        clear_url_action.triggered.connect(lambda: self.url_bar.clear())
        self.RContextMenu.addAction(clear_url_action)

        urlHelp_action = QAction("Url Bar Help", self)
        urlHelp_action.setObjectName("dynamic_url_action")
        urlHelp_action.triggered.connect(lambda: self.UIHelper("Url Bar"))
        self.RContextMenu.addAction(urlHelp_action)

        self.RContextMenu.setWindowFlags(self.RContextMenu.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.RContextMenu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.RContextMenu.exec(self.url_bar.mapToGlobal(pos))
    

    def displayStatusBarContextMenu(self, pos, widget, buttonName):
    
        for action in reversed(self.RContextMenu.actions()):
            if action.objectName() in ["dynamic_help_action", 
                                        "dynamic_bookmark_action", 
                                        "dynamic_tab_action", 
                                        "dynamic_url_action", 
                                        "dynamic_status_action",
                                        "dynamic_web_action"]:
                self.RContextMenu.removeAction(action)
                action.deleteLater()

        sep = self.RContextMenu.addSeparator()
        sep.setObjectName("dynamic_help_action")

        if buttonName == "zoomDisplay":
            zoomHelp_action = QAction("Zooming Help")
            zoomHelp_action.setObjectName("dynamic_status_action")
            zoomHelp_action.triggered.connect(lambda: self.UIHelper("Zooming"))
            self.RContextMenu.addAction(zoomHelp_action)
        if buttonName == "profileDisplay":
            profileHelp_action = QAction("Profile Help")
            profileHelp_action.setObjectName("dynamic_status_action")
            profileHelp_action.triggered.connect(lambda: self.UIHelper("Profiles"))
            self.RContextMenu.addAction(profileHelp_action)

        statusHelp_action = QAction("Status Bar Help", self)
        statusHelp_action.setObjectName("dynamic_status_action")
        statusHelp_action.triggered.connect(lambda: self.UIHelper("Status Bar"))
        self.RContextMenu.addAction(statusHelp_action)
        
        self.RContextMenu.setWindowFlags(self.RContextMenu.windowFlags() | Qt.FramelessWindowHint)
        self.RContextMenu.setAttribute(Qt.WA_TranslucentBackground)

        self.RContextMenu.exec(widget.mapToGlobal(pos))



    def displayTabsContextMenu(self, pos):
        # Determine the integer index of the specific tab that was right-clicked
        tab_index = self.tabs.tabBar().tabAt(pos)
        if tab_index == -1: 
            return # User right-clicked the empty blank space next to tabs
            
        # Clear out previous dynamic actions safely
        for action in reversed(self.RContextMenu.actions()):
            if action.objectName() in ["dynamic_help_action", 
                                        "dynamic_bookmark_action", 
                                        "dynamic_tab_action", 
                                        "dynamic_url_action", 
                                        "dynamic_status_action",
                                        "dynamic_web_action"]:
                self.RContextMenu.removeAction(action)
                action.deleteLater()

        sep = self.RContextMenu.addSeparator()
        sep.setObjectName("dynamic_help_action")
                
        # Add tab-specific actions dynamically
        close_action = QAction(f"Close Tab", self)
        close_action.setObjectName("dynamic_tab_action")
        close_action.triggered.connect(lambda: self.close_tab(tab_index))
        self.RContextMenu.addAction(close_action)

        if self.tabs.widget(tab_index).page().isAudioMuted() == False:
            mute_action = QAction(f"Mute Tab", self)
        else:
            mute_action = QAction(f"Unmute Tab", self)
        mute_action.setObjectName("dynamic_tab_action")
        mute_action.triggered.connect(lambda: self.mute_tab(tab_index))
        self.RContextMenu.addAction(mute_action)

        sep = self.RContextMenu.addSeparator()
        sep.setObjectName("dynamic_help_action")

        tabHelp_action = QAction("Tabs Help", self)
        tabHelp_action.setObjectName("dynamic_tab_action")
        tabHelp_action.triggered.connect(lambda: self.UIHelper("Tabs"))
        self.RContextMenu.addAction(tabHelp_action)
        
        # Apply rendering transformations and trigger
        self.RContextMenu.setWindowFlags(self.RContextMenu.windowFlags() | Qt.FramelessWindowHint)
        self.RContextMenu.setAttribute(Qt.WA_TranslucentBackground)



        self.RContextMenu.exec(self.tabs.tabBar().mapToGlobal(pos))
    
    def displayBookmarksContextMenu(self, button, bid, bookmarksData, pos):
        #Clear out old help actions or previous bookmark actions from the main menu first
        for action in reversed(self.RContextMenu.actions()):
            if action.objectName() in ["dynamic_help_action", 
                                        "dynamic_bookmark_action", 
                                        "dynamic_tab_action", 
                                        "dynamic_url_action", 
                                        "dynamic_status_action",
                                        "dynamic_web_action"]:
                self.RContextMenu.removeAction(action)
                action.deleteLater()

        # Extract the bookmark details
        data = bookmarksData
        bookmark = data[bid]
        name = bookmark["name"]
        url = bookmark["url"]

        # Add a visual separator line before the bookmark options
        sep = self.RContextMenu.addSeparator()
        sep.setObjectName("dynamic_bookmark_action")

        # Create actions and attach them to the main context menu
        rename = QAction("Rename", self)
        rename.setObjectName("dynamic_bookmark_action")
        # Use lambda to capture variables securely for the triggered events
        rename.triggered.connect(lambda: self.handle_bookmark_rename(bid, name, data))
        self.RContextMenu.addAction(rename)

        delete = QAction("Delete", self)
        delete.setObjectName("dynamic_bookmark_action")
        delete.triggered.connect(lambda: self.remove_bookmark(bid))
        self.RContextMenu.addAction(delete)

        open_tab = QAction("Open in New Tab", self)
        open_tab.setObjectName("dynamic_bookmark_action")
        open_tab.triggered.connect(lambda: self.add_new_tab(qurl=url, label=name))
        self.RContextMenu.addAction(open_tab)

        sep = self.RContextMenu.addSeparator()
        sep.setObjectName("dynamic_help_action")

        bookmarksHelp = QAction("Bookmarks Help", self)
        bookmarksHelp.setObjectName("dynamic_bookmark_action")
        bookmarksHelp.triggered.connect(lambda: self.UIHelper("Bookmarks"))
        self.RContextMenu.addAction(bookmarksHelp)

        # Apply the window transparency flags to the main menu
        self.RContextMenu.setWindowFlags(self.RContextMenu.windowFlags() | Qt.FramelessWindowHint)
        self.RContextMenu.setAttribute(Qt.WA_TranslucentBackground)

        # Summon the main context menu at the button's location
        self.RContextMenu.exec(button.mapToGlobal(pos))

    def handle_bookmark_rename(self, bid, name, data):
        new_name = self.additionalUIElements.WindowInput(
            "Rename Bookmark", "Enter new name:", default_text=name
        )
        if new_name:
            data[bid]["name"] = new_name
            self.refresh_bookmarksbar(data)


    def displayWebContextMenu(self, pos):
        # cleanup existing dynamic actions
        for action in reversed(self.RContextMenu.actions()):
            if action.objectName() in ["dynamic_help_action", 
                                        "dynamic_bookmark_action", 
                                        "dynamic_tab_action", 
                                        "dynamic_url_action", 
                                        "dynamic_status_action",
                                        "dynamic_web_action"]:
                self.RContextMenu.removeAction(action)
                action.deleteLater()

        request = self.current_browser.lastContextMenuRequest()

        if request:

            if request.linkUrl().isValid() and not request.linkUrl().isEmpty():
                self.RContextMenu.addSeparator()

                open_link = QAction("Open Link", self)
                open_link.setObjectName("dynamic_web_action")
                open_link.triggered.connect(lambda checked=False, req=request: self.load_url(QUrl(self.UrlManager.normalise_url(req.linkUrl().toString()))))
                self.RContextMenu.addAction(open_link)

                open_link_newtab = QAction("Open in New Tab", self)
                open_link_newtab.setObjectName("dynamic_web_action")
                open_link_newtab.triggered.connect(lambda checked=False, req=request: self.add_new_tab(qurl = QUrl(self.UrlManager.normalise_url(req.linkUrl().toString()))))
                self.RContextMenu.addAction(open_link_newtab)

                #I might need to make this more secure!
                copy_link = QAction("Copy Link", self)
                copy_link.setObjectName("dynamic_web_action")
                copy_link.triggered.connect(lambda checked=False, req=request: QGuiApplication.clipboard().setText(req.linkUrl().toString()))
                self.RContextMenu.addAction(copy_link)

                copy_clean_link = QAction("Copy Cleaned Link", self)
                copy_clean_link.setObjectName("dynamic_web_action")
                copy_clean_link.triggered.connect(lambda  checked=False, req=request: QGuiApplication.clipboard().setText(self.UrlManager.normalise_url(req.linkUrl().toString())))
                self.RContextMenu.addAction(copy_clean_link)


            
            if request.mediaUrl().isValid() and not request.mediaUrl().isEmpty():
                self.RContextMenu.addSeparator()

                open_img_newtab = QAction("Open Image in New Tab", self)
                open_img_newtab.setObjectName("dynamic_web_action")
                open_img_newtab.triggered.connect(lambda checked=False, req=request: self.add_new_tab(qurl = QUrl(self.UrlManager.normalise_url(req.mediaUrl().toString()))))
                self.RContextMenu.addAction(open_img_newtab)

                save_img = QAction("Save Image")
                save_img.setObjectName("dynamic_web_action")
                save_img.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.DownloadImageToDisk))
                self.RContextMenu.addAction(save_img)

                copy_img = QAction("Copy Image")
                copy_img.setObjectName("dynamic_web_action")
                copy_img.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.CopyImageToClipboard))
                self.RContextMenu.addAction(copy_img)

                copy_img_url = QAction("Copy Image Url")
                copy_img_url.setObjectName("dynamic_web_action")
                copy_img_url.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.CopyImageUrlToClipboard))
                self.RContextMenu.addAction(copy_img_url)



            if request.selectedText() and not request.isContentEditable():
                self.RContextMenu.addSeparator()

                copy_select = QAction("Copy", self)
                copy_select.setObjectName("dynamic_web_action")
                copy_select.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.Copy))
                self.RContextMenu.addAction(copy_select)

                cut_select = QAction("Cut", self)
                cut_select.setObjectName("dynamic_web_action")
                cut_select.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.Cut))
                self.RContextMenu.addAction(cut_select)

                paste_select = QAction("Paste", self)
                paste_select.setObjectName("dynamic_web_action")
                paste_select.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.Paste))
                self.RContextMenu.addAction(paste_select)

                

            if request.isContentEditable():
                self.RContextMenu.addSeparator()

                copy_select = QAction("Copy", self)
                copy_select.setObjectName("dynamic_web_action")
                copy_select.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.Copy))
                self.RContextMenu.addAction(copy_select)

                cut_select = QAction("Cut", self)
                cut_select.setObjectName("dynamic_web_action")
                cut_select.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.Cut))
                self.RContextMenu.addAction(cut_select)

                paste_select = QAction("Paste", self)
                paste_select.setObjectName("dynamic_web_action")
                paste_select.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.Paste))
                self.RContextMenu.addAction(paste_select)

                self.RContextMenu.addSeparator()

                undo_text = QAction("Undo", self)
                undo_text.setObjectName("dynamic_web_action")
                undo_text.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.Undo))
                self.RContextMenu.addAction(undo_text)

                redo_text = QAction("Redo", self)
                redo_text.setObjectName("dynamic_web_action")
                redo_text.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.Redo))
                self.RContextMenu.addAction(redo_text)

            else:
                pass



        self.RContextMenu.addSeparator()

        # add extras
        inspect = QAction("DevTools", self)
        inspect.setObjectName("dynamic_web_action")
        inspect.triggered.connect(self.openDevTools)
        self.RContextMenu.addAction(inspect)

        select_all = QAction("Select All")
        select_all.setObjectName("dynamic_web_action")
        select_all.triggered.connect(lambda: self.current_browser.page().triggerAction(QWebEnginePage.WebAction.SelectAll))
        self.RContextMenu.addAction(select_all)

        self.RContextMenu.addSeparator()

        # Apply the window transparency flags to the main menu
        self.RContextMenu.setWindowFlags(self.RContextMenu.windowFlags() | Qt.FramelessWindowHint)
        self.RContextMenu.setAttribute(Qt.WA_TranslucentBackground)

        self.RContextMenu.exec(self.current_browser.mapToGlobal(pos))

    def displayEngineContextMenu(self, pos, trigger_widget, key):
        for action in reversed(self.RContextMenu.actions()):
            if action.objectName() in ["dynamic_help_action", 
                                        "dynamic_bookmark_action", 
                                        "dynamic_tab_action", 
                                        "dynamic_url_action", 
                                        "dynamic_status_action",
                                        "dynamic_web_action"]:
                self.RContextMenu.removeAction(action)
                action.deleteLater()

        deleteEngine = QAction("Delete Engine", self)
        deleteEngine.setObjectName("dynamic_help_action")
        deleteEngine.triggered.connect(lambda checked=False, k=key: self.deleteEngineEntry(k))
        self.RContextMenu.addAction(deleteEngine)
        
        self.RContextMenu.addSeparator()

        self.RContextMenu.setWindowFlags(self.RContextMenu.windowFlags() | Qt.FramelessWindowHint)
        self.RContextMenu.setAttribute(Qt.WA_TranslucentBackground)

        # Temporarily force the active dropdown menu to be the structural parent of the context menu, fix for wayland mechanics on Linux
        if hasattr(self.barManager, 'browserMenu') and self.barManager.browserMenu:
            self.RContextMenu.setParent(self.barManager.browserMenu, self.RContextMenu.windowFlags())

        self.RContextMenu.exec(trigger_widget.mapToGlobal(pos))


    def openDevTools(self):
        current_page = self.current_browser.page()
        current_page.setDevToolsPage(self.devtools_page)
        self.devtools_view.show()


    def UIHelper(self, buttonClicked):
        launcher = SystemHelperUI(self, self.buttonInternals, buttonClicked, False)
        launcher.exec()







    '''Main Events Handling'''

    def closeEvent(self, event):
        if not self.bypassCloseEvent and not self.pending_restart:
            if self.additionalUIElements.WindowConfirmation("Exit", "Close Midnight Watch?"):
                self.shutdown_Systems()
                event.accept()
            else:
                event.ignore()
                print("Exit cancelled by user")
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        
        new_width = event.size().width()
        old_width = event.oldSize().width()
        
        if new_width != old_width:
            # Width changed - update tab sizes
            self.update_tab_sizes()
        
        if self.settingsData["Tab-Position"] in ["East", "West"]:
            self.tabs.tabBar().update_hover_from_cursor()

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_tabs_sized'):
            self.update_tab_sizes()
            self._tabs_sized = True

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel zoom (including two-finger trackpad gestures)"""

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            
            delta = event.pixelDelta()
            if delta.isNull():
                delta = event.angleDelta()
            
            if not delta.isNull():
                if delta.y() > 0:
                    self.apply_zoom(self.zoomValue + 10)
                else:
                    self.apply_zoom(self.zoomValue - 10)
                
                event.accept()
                return
            
        super().wheelEvent(event)   

    def devtoolsCloseEvent(self, event):
        try:
            page = self.current_browser.page()
            # detach inspector backend
            page.setDevToolsPage(None)

        except Exception as e:
            print(e)

        event.accept()




    '''Buttons, Controls, and Icons'''

    

    #button assignment functions
    def go_back(self): self.current_browser.back()
    def reload_tab(self): self.current_browser.reload()
    def go_forward(self): self.current_browser.forward()
    def go_home(self): self.current_browser.setUrl(QUrl("MidnightWatch://local/homepage.html"))
    def new_tab(self): self.add_new_tab()
    def open_settings_menu(self): self.open_settings()



    '''Zooming'''


    def apply_zoom(self, value):
        factor = value / 100.0
        cursor_style = 'grab' if factor > 1 else 'auto'
        js_code = f"""
        document.body.style.transform = 'scale({factor}) translate({self.pan_offset_x}px, {self.pan_offset_y}px)';
        document.body.style.transformOrigin = '0 0';
        document.body.style.cursor = '{cursor_style}';
        """
        self.current_browser.page().runJavaScript(js_code)


    def setContentZoom(self, direction):
        if direction:
            self.zoomValue += 10
        else:
            self.zoomValue -= 10
        
        if self.zoomValue < 50:
            self.zoomValue = 50
        if self.zoomValue > 500:
            self.zoomValue = 500

        # Store zoom value using browser widget as key (survives tab reordering)
        self.tab_zoom_values[self.current_browser] = self.zoomValue
        
        self.current_browser.setZoomFactor(self.zoomValue/100)

        # Update slider without triggering its signal
        if hasattr(self, 'barManager') and hasattr(self.barManager, 'zoom_slider'):
            self.barManager.zoom_slider.blockSignals(True)
            self.barManager.zoom_slider.setValue(self.zoomValue)
            self.barManager.zoom_slider.blockSignals(False)
            self.barManager.zoomDisplay.setText(f"{self.zoomValue}%")




    '''Tab Management'''
    def add_new_tab(self, qurl=None, label="New Tab"):
        if qurl is None or isinstance(qurl, bool):
            qurl = QUrl("MidnightWatch://local/homepage.html")
            
        if isinstance(qurl, tuple):
            qurl = qurl[0]
        
        browser = QWebEngineView()
        browser.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        browser.customContextMenuRequested.connect(lambda pos: self.displayWebContextMenu(pos))

        new_page = InternalPage(self.profile, browser, self)

        browser.setPage(new_page)

        self.configure_bridge(qurl, browser)

        browser.setUrl(qurl)

        self.tab_zoom_values[browser] = 100
        browser.setZoomFactor(1.0)
        

        i = self.tabs.addTab(browser, label)

        self.tabs.setCurrentIndex(i)

        if hasattr(self, 'contrast_qcolor'):
            self.tabs.tabBar().setTabTextColor(i, self.contrast_qcolor)

        # Connect signals
        new_page.iconChanged.connect(lambda: self.update_tab_icon(browser))
        browser.urlChanged.connect(lambda qurl, browser=browser: (self.update_tab_title(browser), self.on_url_changed(qurl, browser)))
        browser.loadStarted.connect(lambda: self.barManager.start_reload_animation())
        browser.loadFinished.connect(lambda ok, b=browser: (self.barManager.stop_reload_animation(), self.on_load_finished(browser)))
        browser.titleChanged.connect(lambda title, browser=browser, i=i: (self.update_tab_title(browser, title), self.tabs.setTabToolTip(i, f"{title}\n{self.UrlManager.normalise_url(browser.url().toString())}")))


        self.update_tab_sizes()
        self.update_tab_icon(self.current_browser)
        #Update tab apperances for vertical-specific adjustments
        if self.settingsData["Tab-Position"] in ["East", "West"]:
            VerticalTabBar.update_close_buttons(self.tabs.tabBar())
            QTimer.singleShot(0, self.tabs.tabBar().update_close_buttons)
        else:
            pass
        return browser
    
    def on_url_changed(self, qurl, browser):
        
        self.configure_bridge(qurl, browser)

        clean = self.UrlManager.normalise_url(qurl.toString())
        self.url_bar.setText(clean)
    
    def update_tab_icon(self, browser):
        tab_index = self.tabs.indexOf(browser)
        if tab_index != -1:
            icon = browser.page().icon()
            if icon.isNull():
                icon = get_normIcon("tabIcon.png")
                
            if browser.page().isAudioMuted():
                icon = self.barManager.get_muted_icon(icon)

            self.tabs.setTabIcon(tab_index, icon)
                
    def close_tab(self, index=None):

        if index is None:
            index = self.tabs.currentIndex()

        if self.tabs.count() > 1:
            #manage all remaining cookies based on settings preferences
            target_tab = self.tabs.widget(index)
            if target_tab:
                target_url = target_tab.url().toString()
                if self.cookiedict is not None:
                    for key, data in list(self.cookiedict.items()):
                        cookie_domain = data["domain"].lstrip(".")
                        tab_host = QUrl(target_url).host()
                        if tab_host.endswith(cookie_domain):
                            if siteLeaveCookies:
                                self.cookieManager.acceptCookie(key)
                            else:
                                self.cookieManager.cookieEVAPORATOR(key)
                else:
                    pass

                # Clean up the page before removing the tab to prevent profile release errors
                if hasattr(target_tab, 'page') and target_tab.page():
                    target_tab.page().deleteLater()

            self.tabs.removeTab(index)
        else:
            self.close()

        self.update_tab_sizes()
        #Vertical tab specific updates
        if self.settingsData["Tab-Position"] in ["East", "West"]:
            QTimer.singleShot(0, self.tabs.tabBar().update_close_buttons)

    def switch_tab(self, index):
        current_browser = self.tabs.widget(index)
        if current_browser:
            self.current_browser = current_browser
            raw_url = current_browser.url().toString()
            clean_url = self.UrlManager.normalise_url(raw_url)
            self.url_bar.setText(clean_url)

            # Restore zoom value for this tab using browser widget as key
            self.zoomValue = self.tab_zoom_values.get(current_browser, 100)
            self.current_browser.setZoomFactor(self.zoomValue / 100)
            
            # Update slider to reflect tab's zoom
            if hasattr(self, 'barManager') and hasattr(self.barManager, 'zoom_slider'):
                self.barManager.zoom_slider.blockSignals(True)
                self.barManager.zoom_slider.setValue(self.zoomValue)
                self.barManager.zoom_slider.blockSignals(False)
                self.barManager.zoomDisplay.setText(f"{self.zoomValue}%")
            
            #update url bar buttons, especially bookmarks
            self.update_url_bar_buttons(self.current_browser.url().toString(), self.current_browser)
            #Vertical tab specific updates
            if self.settingsData["Tab-Position"] in ["East", "West"]:
                QTimer.singleShot(0, self.tabs.tabBar().update_close_buttons)

    def mute_tab(self, index):
        target_tab = self.tabs.widget(index)
        if target_tab:
            target_tab.page().setAudioMuted(not target_tab.page().isAudioMuted())
            self.update_tab_icon(target_tab)
            

    def update_tab_title(self, browser, title=None):
        i = self.tabs.indexOf(browser)
        if i != -1:

            #update url bar buttons
            self.update_url_bar_buttons(browser.url().toString(), browser)


            # Use provided title or fallback to using default with guard clause
            if not title:
                return

            # Clean it up a bit for display
            if len(title) > 60:
                title = title[:57] + "..."
            
            if title == "midnightwatch://local/homepage.html":
                title = 'Homepage'

            self.tabs.setTabText(i, title)
            
        pass

    def calculate_tab_width(self):
        # Get total available width
        tab_bar_width = self.tabs.tabBar().width() #change this if I need more padding, though note that it will override once the tabs reach the smallest possible size
        tab_bar_width = tab_bar_width - (tab_bar_width/12) #padding for scroll buttons and general breathing room, adjust as needed
        tab_count = max(1, self.tabs.count())
        
        # Calculate width per tab
        width_per_tab = tab_bar_width / tab_count
        
        # Apply min/max constraints (e.g., 100px minimum, 300px maximum)
        min_width = 100
        max_width = 200
        final_width = clamp(width_per_tab, min_width, max_width)
        
        return final_width

    def update_tab_sizes(self):
        #Guard clause to only run these updates if the user is on a horizontal tab system
        if ["Tab-Position"] in ["East", "West"]:
            return
        tab_width = self.calculate_tab_width()
        tabbar = self.tabs.tabBar()
        current_style = tabbar.styleSheet()
        
        # Remove any existing QTabBar::tab rules
        cleaned_style = re.sub(
            r'QTabBar::tab\s*\{[^}]*\}',
            '',
            current_style
        )
        
        # Append fresh rule with new width
        new_rule = f"QTabBar::tab {{ height: 30px; width: {int(tab_width)}px; }}"
        final_style = cleaned_style + "\n" + new_rule
        
        tabbar.setStyleSheet(final_style)

    '''URL + URL Bar Handling'''

    def load_url(self, qurl=None, label=None):
        if qurl is not None:
            self.configure_bridge(qurl, self.current_browser)
            self.current_browser.setUrl(qurl)
            if label is not None:
                self.update_tab_title(self.current_browser, title=label)
            return


        input_text = self.url_bar.text().strip()
        if not input_text:
            return

        # QUrl.fromUserInput automatically handles missing schemes (adds http://)
        # and checks if the string looks like a valid web address
        url = QUrl.fromUserInput(UrlManager.normalise_url(True, input_text))

        if url.isValid() and "." in input_text and " " not in input_text:
            # It's a valid URL (e.g., "google.com")
            self.current_browser.setUrl(url)
        else:
            # It's a search query
            search_url = self.engines[engine]["URL"] + input_text.replace(" ", "+")
            self.current_browser.setUrl(QUrl(search_url))

        #update url bar to proper cleaned url text
        raw_url = self.current_browser.url().toString()
        clean_url = self.UrlManager.normalise_url(raw_url)
        self.url_bar.setText(clean_url)

    def htmlSearch(self, cQuery):
        #convert to search link
        search_url = self.engines[engine]["URL"] + cQuery.replace(" ", "+")
        #update and process system
        self.current_browser.setUrl(QUrl(UrlManager.normalise_url(True, search_url)))
        #update url bar to proper cleaned url text
        raw_url = self.current_browser.url().toString()
        clean_url = self.UrlManager.normalise_url(raw_url)
        self.url_bar.setText(clean_url)

    def configure_bridge(self, target_url, browser=None):
        if browser is None:
            browser = self.current_browser

        page = browser.page()
        is_internal = (target_url.scheme().lower() == "midnightwatch" and target_url.host().lower() == "local")

        if is_internal:
            if getattr(page, "bridge", None) is None:
                bridge = objectMasterBridge(self, page)
                bridge.searchRequested.connect(self.htmlSearch)
                channel = QWebChannel(page)
                channel.registerObject("pyBridge", bridge)
                page.setWebChannel(channel)
                page.bridge = bridge
                page.channel = channel
                print("Bridge attached.")

        else:

            if getattr(page, "channel", None):
                page.setWebChannel(None)
                if page.bridge:
                    page.bridge.deleteLater()
                if page.channel:
                    page.channel.deleteLater()
                page.bridge = None
                page.channel = None
                print("Bridge removed.")
            else:
                print("Skipped")



    def on_load_finished(self, browser):
        #attempt to close extra boxes on blocked ads
        CosmeticBlocker.inject_css(browser)
        ScriptletBlocker.inject_scriptlets(browser)
        #extra case for final updates, catchall for url changes after loading a new page, finishing loading a different page, etc
        clean_url = self.UrlManager.normalise_url(self.current_browser.url().toString())
        self.url_bar.setText(clean_url)
        pass

    def update_url_bar_buttons(self, url, browser):
        normalised_bookmarks = {}
        current = self.UrlManager.normalise_url(self.current_browser.url().toString())

        
        with open(f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            Colourdata = json.load(f)
        try:
            bookmarkData = self.profile_config["saved_bookmarks"]

            #load bookmarks and compare against normalised
            normalised_bookmarks = {bid: self.UrlManager.normalise_url(data["url"]) for bid, data in bookmarkData.items()}

        except json.decoder.JSONDecodeError:
            print("Nothing in bookmarks folder, skipping.")
        
        colour = Colourdata[self.selectedprofile]["bookmark_btn"]

        if not hasattr(self, "bookmark_button"):
            self.bookmark_button = self.url_bar.addAction(QIcon(), QLineEdit.TrailingPosition)

        #disconnect previous signals
        try:
            self.bookmark_button.triggered.disconnect()
        except:
            pass
        
        #load bookmark actions based on current tab
        matched_id = next((bid for bid, url in normalised_bookmarks.items() if url == current), None)
        if matched_id:
            iconpath = buttoncolourer("BookmarkAdded", colour, "BookmarkAdded")
            icon = QIcon(str(iconpath))
            self.bookmark_button.setIcon(icon)
            self.bookmark_button.setToolTip("Remove Bookmark")
            self.bookmark_button.triggered.connect(
                lambda: self.remove_bookmark(matched_id)
            )
        else:
            iconpath = buttoncolourer("BookmarkNotAdded", colour, "BookmarkNotAdded")
            icon = QIcon(str(iconpath))
            self.bookmark_button.setIcon(icon)
            self.bookmark_button.setToolTip("Add Bookmark")
            self.bookmark_button.triggered.connect(
                lambda: self.add_bookmark(self.UrlManager.normalise_url(self.current_browser.url().toString()))
            )
        
        self.url_bar.update()

    def _url_bar_mouse_press(self, event):
        if not self.url_bar.hasFocus():
            self.url_bar.selectAll()
        QLineEdit.mousePressEvent(self.url_bar, event)
    
    def _url_bar_focus_in(self, event):
        # Only clear if it's an internal page (your scheme)
        text = self.url_bar.text()

        if "midnightwatch://" in text:
            self.url_bar.clear()

        self.url_bar.selectAll()
        super(QLineEdit, self.url_bar).focusInEvent(event)



    '''Search Engine Management'''
    
    def set_engine(self, key):
        global engine
        engine = key
        self.engine = key
        if hasattr(self, 'engine_btn') and self.engine_btn is not None:
            self.engine_btn.setText(key.capitalize())
            self.engine_btn.setToolTip(key)
            self.engine_btn.setIcon(QIcon(str(icon_cache_dir / f"{key}")))
            
            #reformat json file to show active browser as 'true'. Swapping browsers lets the selected one persist after resets
            for key, value in self.engines.items():
                if self.engines[key]["active"] == 1:
                    self.engines[key]["active"] = 0
            self.engines[self.engine]["active"] = 1
            with open(f"{srcSourceDir}/data/engineData.json", "w") as f:
                json.dump(self.engines, f, indent=4)
    
    def add_new_engine(self):
        name, url = self.additionalUIElements.WindowDoubleInput(
            "Add New Engine",
            "Enter the display name (e.g. Brave, Google)",
            "Display Name",
            "Enter the search URL (e.g. https://www.google.com/search?q=)",
            "Search URL"
        )
        if not url:
            return
        if not name:
            name = "Unnamed Engine"

        self.engines[str(name)] = {"URL": url, "active": 0}


        #Update engines data backend
        self.barManager.update_engine_menu(self.engines)

        self.browserMenu = self.barManager.browserMenu

        #Save modified data
        with open(f"{srcSourceDir}/data/engineData.json", "w") as f:
                json.dump(self.engines, f, indent=4)

        #update colour theme
        with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            Colourdata = dict(json.load(f))
        self.SelectColourTheme(self.profile_config["stored_data"]["Colour-Theme"], Colourdata)

    def deleteEngineEntry(self, engineName):
        print(str(engineName))

        if self.engine == str(engineName):
            iterator = iter(self.engines)
            first_key = next(iterator, None)

            if first_key != str(engineName):
                # First item is not the one being deleted, use it
                self.set_engine(first_key)
            else:
                # First item is the one being deleted, try to get the second
                second_key = next(iterator, None)
                if second_key is not None:
                    self.set_engine(second_key)
                else:
                    # Handle case where no other engines are available
                    QMessageBox.warning(None, "Engine Deletion", "Cannot delete engine, only one is present in the list! \n\n Please ensure at least one engine is present in your list at all times.")
                    return


        #Remove engines entry
        target_key = next((k for k in self.engines if k.lower() == str(engineName).lower()), None)

        if target_key:
            del self.engines[target_key]
        else:
            QMessageBox.warning(
                None, 
                "Engine Deletion", 
                "Attempted to delete an engine that doesn't exist in data. Please refresh the dropdown or reload the entire browser and try again."
            )
            return
            
        #Close UI for refreshing
        if hasattr(self.barManager, 'browserMenu'):
            self.barManager.browserMenu.close()
        
        #Update menu
        self.barManager.update_engine_menu(self.engines)

        self.browserMenu = self.barManager.browserMenu


        #Save data
        with open(f"{srcSourceDir}/data/engineData.json", "w") as f:
                json.dump(self.engines, f, indent=4)
        
        #Remove icon for deleted engine
        icon_path = f"{srcSourceDir}/ui/icon_cache/{str(engineName)}.png"
        if os.path.exists(icon_path):
            try:
                os.remove(icon_path)
            except Exception as e:
                print(f"Could not remove cached image file: {e}")
        else:
            print("No image to remove")

        #update colour theme
        with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            Colourdata = dict(json.load(f))
        self.SelectColourTheme(self.profile_config["stored_data"]["Colour-Theme"], Colourdata)
        
        


        



    '''Bookmarks System'''

    #needs to create a menu popup that can accept a name input. Use Qsanitiser system to clean user input to keep everything safe
    def add_bookmark(self, url):
        name = self.additionalUIElements.WindowInput(
            "Add Bookmark",
            "Enter bookmark name:",
            self.tabs.tabText(self.tabs.currentIndex())
        )

        if not name:
            return
        
        try:
            data = self.profile_config["saved_bookmarks"]
        except:
            data = {}

        new_id = str(uuid.uuid4())

        data[new_id] = {
            "name": name,
            "url": url
        }

        self.profile_config["saved_bookmarks"] = data

        #reload bookmarks bar to show new bookmark
        self.barManager.refresh_bookmarksbar(self.profile_config["saved_bookmarks"])
        self.update_url_bar_buttons(self.current_browser.url().toString(), self.current_browser)
        saveData(self.currentProfileID, self.profile_config)

    def remove_bookmark(self, id):
        data = self.profile_config["saved_bookmarks"]

        del data[id]

        self.profile_config["saved_bookmarks"] = data
        
        self.barManager.refresh_bookmarksbar(self.profile_config["saved_bookmarks"])
        self.update_url_bar_buttons(self.current_browser.url().toString(), self.current_browser)
        saveData(self.currentProfileID, self.profile_config)

    


    '''Settings Menu System'''
    def open_settings(self):
        self.add_new_tab(QUrl("MidnightWatch://local/settings.html"))
        pass

    '''Colour Theme Management'''
    
    def SelectColourTheme(self, profile, themes=None):

        #reload themes from source to allow updates
        with open(f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            themes = json.load(f)

        self.tabs.tabBar().setStyleSheet("""
            QTabBar::tab {
                height: 35px;
                width: 200px;
            }
            """)
        global eColsButton, eColsStyle
        self.selectedprofile = profile

        self.colourpalette_btn.setToolTip(f"Colour Palettes (currently {profile})")

        print(f"Colour Profile Switched to {profile}")

        datalist = list((themes[profile]).items())
        #print(datalist)

        #adjust user profile colour selection
        with open (f"{srcSourceDir}/data/actionToggles.json", "r") as f:
            dataedit = dict(json.load(f))
        dataedit["Colour-Theme"] = str(profile)
        with open (f"{srcSourceDir}/data/actionToggles.json", "w") as f:
            json.dump(dataedit, f, indent=4)
        self.profile_config["stored_data"]["Colour-Theme"] = str(profile)
            

        #recolour icons
        tabcolour = "(255, 255, 255)" #white is default
        for k, v in datalist:
            if k in eColsButton:
                #print(f"eColsButton: {k}")
                #print(f"colourAdjust: {v}")
                obj = getattr(self, k, None)
                if obj is not None:
                    colouredpath = buttoncolourer(k, v)
                    #REFRESH ICON
                    obj.setIcon(QIcon(str(colouredpath)))

                    #adjust dropdown icon for colourpalettes
                    if k == "colourpalette_btn":
                        rgb_list = list((v[1:-1]).split(", "))
                        self.select_RGB_SL = (
                            clamp(int(rgb_list[0]), 0, 255),
                            clamp(int(rgb_list[1]), 0, 255),
                            clamp(int(rgb_list[2]), 0, 255)
                        )
                        self.light_rgb_tuple = (
                            clamp(int(rgb_list[0]) - 40, 0, 255),
                            clamp(int(rgb_list[1]) - 40, 0, 255),
                            clamp(int(rgb_list[2]) - 40, 0, 255)
                            ) 
                        self.rgb_tuple = (
                            clamp(int(rgb_list[0]) - 120, 0, 255),
                            clamp(int(rgb_list[1]) - 120, 0, 255),
                            clamp(int(rgb_list[2]) - 120, 0, 255)
                            )
                        
                        
                        self.hexval = '#%02x%02x%02x' % self.rgb_tuple
                        #print(f"Adjusting colourPalette dropdown {self.hexval}, {self.rgb_tuple}, {self.light_rgb_tuple}")
                        # Apply the styles specifically to the dropdown button (colourpalette_btn)
                        obj.setStyleSheet(f"""
                            QToolButton {{
                                background-color: {self.hexval};   /* Set background color */
                                border: 1px solid {self.hexval};   /* Optional: add border matching background */
                                padding-right: 14px;          /* Adjust padding */
                                border-radius: 5px;
                            }}
                            
                            QToolButton::menu-indicator {{
                                background-color: {self.hexval};   /* Set the menu indicator color */
                                padding: 3px;                 /* Adjust indicator size */
                            }}
                            
                            QToolButton::icon {{
                                image: url({str(colouredpath)}); /* Correct way to set the icon image */
                            }}
                        """)

                        #update any icons in the url bar by rerunning url bar update
                        self.update_url_bar_buttons(self.current_browser.url().toString(), self.current_browser)
                #select file from system and use PIL to change based on colour v, then s
                pass
                
                if k == "pintabs_btn":
                    pintabs_btn_col = buttoncolourer("pintabs", v, "pintabs")
                    self.tabs.tabBar().pin_btn.setIcon(QIcon(str(pintabs_btn_col)))
                    self.tabs.tabBar().update_pin_icon()

            #recolour other elements
            elif k in eColsStyle:
                #print(f"eColsStyle: {k}")
                obj = getattr(self, k, None)
                if obj is not None:
                    if k not in ('tabs', 'tab_backer'):
                        obj.setStyleSheet(f"background:rgb{v}")

                # parse the rgb tuple
                rgb_vals = [int(x.strip()) for x in str(v).strip('()').split(',')]
                avgnew = sum(rgb_vals) / 3
                # choose black text for light backgrounds, white for dark backgrounds
                self.contrast_qcolor = QColor(0, 0, 0) if avgnew > 150 else QColor(255, 255, 255)

                if k == 'tabs':
                    # tab text color + set URL bar to match tabs background with contrasting text
                    for i in range(self.tabs.count()):
                        self.tabs.tabBar().setTabTextColor(i, self.contrast_qcolor)

                    bg_rgb_str = f"rgb({rgb_vals[0]}, {rgb_vals[1]}, {rgb_vals[2]})"
                    text_rgb_str = f"rgb({self.contrast_qcolor.red()}, {self.contrast_qcolor.green()}, {self.contrast_qcolor.blue()})"
                    self.url_bar.setStyleSheet(f"background: {bg_rgb_str}; color: {text_rgb_str}")

                elif k == 'tab_backer':
                    # set the tab bar background color specifically using QPalette (more robust than stylesheets)
                    r, g, b = rgb_vals
                    self.tabs.setDocumentMode(True)
                    self.tabs.setAutoFillBackground(True)
                    self.tabs.tabBar().setStyleSheet(f"QTab::pane {{ color: rgb({r}, {g}, {b}); }}")
                    self.tabs.setStyleSheet(f"\nQTabBar {{ color: rgb({r}, {g}, {b}); }}")
                    tabbar = self.tabs.tabBar()

                    # Apply color to the tabBar via palette to avoid stylesheet parsing issues
                    color = QColor(r, g, b)
                    pal = tabbar.palette()
                    pal.setColor(QPalette.Window, color)
                    tabbar.setAutoFillBackground(True)
                    tabbar.setPalette(pal)
                    tabbar.setStyleSheet(f"""
                        QTabBar {{
                            background-color: rgb({r}, {g}, {b});
                        }}

                        QTabBar::tab {{
                            height: 35px;
                            width: 200px;
                        }}
                    """)

                    # Also set the QTabWidget pane background so the area behind tabs matches
                    tabs_pal = self.tabs.palette()
                    tabs_pal.setColor(QPalette.Window, color)
                    self.tabs.setAutoFillBackground(True)
                    self.tabs.setPalette(tabs_pal)
                    tabbar.setPalette(tabs_pal)

                    # Update existing tab text contrast
                    for i in range(self.tabs.count()):
                        tabbar.setTabTextColor(i, self.contrast_qcolor)
                    tabbar.repaint()

                    #print(r, g, b)
                    self.tabs.setStyleSheet(f"QTab::pane {{ color: rgb({r}, {g}, {b}); }}")

                
                elif k == 'url_bar':
                    # explicit url_bar entry overrides url bar styling
                    text_qcolor = QColor(0, 0, 0) if avgnew > 150 else QColor(255, 255, 255)
                    bg_rgb_str = f"rgb({rgb_vals[0]}, {rgb_vals[1]}, {rgb_vals[2]})"
                    text_rgb_str = f"rgb({text_qcolor.red()}, {text_qcolor.green()}, {text_qcolor.blue()})"
                    self.url_bar.setStyleSheet(f"background: {bg_rgb_str}; color: {text_rgb_str}")

                elif k == "bookmarks_bar":
                    # set the bookmarks bar background color and text contrast
                    bg_rgb_str = f"rgb({rgb_vals[0]}, {rgb_vals[1]}, {rgb_vals[2]})"
                    text_rgb_str = f"rgb({self.contrast_qcolor.red()}, {self.contrast_qcolor.green()}, {self.contrast_qcolor.blue()})"
                    self.bookmarks_bar.setStyleSheet(f"background: {bg_rgb_str}; color: {text_rgb_str}")

                elif k == "status_bar":
                    # set the status bar background color and text contrast
                    bg_rgb_str = f"rgb({rgb_vals[0]}, {rgb_vals[1]}, {rgb_vals[2]})"
                    text_rgb_str = f"rgb({self.contrast_qcolor.red()}, {self.contrast_qcolor.green()}, {self.contrast_qcolor.blue()})"
                    self.status_bar.setStyleSheet(f"background: {bg_rgb_str}; color: {text_rgb_str}")
                
            else:
                #print(f"other: {k}")
                pass
            
            self.update_tab_sizes()
        
        #recolour background for searchicon
        self.engine_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {self.hexval};   /* Set background color */
                border: 1px solid {self.hexval};   /* Optional: add border matching background */
                padding-right: 14px;          /* Adjust padding */
                border-radius: 5px;
            }}
            
            QToolButton::menu-indicator {{
                background-color: {self.hexval};   /* Set the menu indicator color */
                padding: 3px;                 /* Adjust indicator size */
            }}
            
            QToolButton::icon {{
                image: url({str(colouredpath)}); /* Correct way to set the icon image */
            }}
        """)

        #Style menu appearance
        bg_rgb_str = f"rgb({rgb_vals[0]}, {rgb_vals[1]}, {rgb_vals[2]})"
        for element in [self.RContextMenu, self.Bookmark_menu]:
            if element is None or not isValid(element):
                continue

            element.setStyleSheet(f"""
                QMenu {{
                    background-color: {bg_rgb_str};
                    border: 4px solid rgb({', '.join(str(int(c) + (55 if avgnew < 150 else -55)) for c in bg_rgb_str.replace('rgb(', '').replace(')', '').split(','))});
                    border-radius: 8px;
                    padding: 4px;
                }}
                QMenu::item {{
                    background-color: transparent;
                    padding: 6px 24px;
                    color: {"white" if avgnew < 150 else "black"};
                    border-radius: 4px;
                }}
                /* Hover state display */
                QMenu::item:selected {{
                    background-color: rgb({rgb_vals[0] + (30 if avgnew < 150 else -30)}, {rgb_vals[1] + (30 if avgnew < 150 else -30)}, {rgb_vals[2] + (30 if avgnew < 150 else -30)});
                    color: {text_rgb_str};
                }}
                /* Custom visual separator line */
                QMenu::separator {{
                    height: 1px;
                    background-color: {"white" if avgnew < 150 else "black"};
                    margin: 4px 8px;
                }}
                """)
        
        #need to set colourmenu attibutes individually for each QMenu dropdown segment
        self.colourMenu.setAttribute(Qt.WA_TranslucentBackground)
        self.browserMenu.setAttribute(Qt.WA_TranslucentBackground)
        self.cookieMenu.setAttribute(Qt.WA_TranslucentBackground)
        self.Bookmark_menu.setWindowFlags(self.RContextMenu.windowFlags() | Qt.FramelessWindowHint)
        self.Bookmark_menu.setAttribute(Qt.WA_TranslucentBackground)

        app.setStyleSheet(f"""
            /* Style the dropdown menu items */
            QMenu {{
                background-color: {self.hexval};  /* Set background color for the dropdown */
                border: 5px solid {self.hexval};      /* Optional border for the dropdown */
                border-radius: 10px;
                padding: 5px;
            }}
            QMenu::item::selected {{
                colour: {self.select_RGB_SL}; 
            }}
            """)
        
        colour_rgb_str = f"rgb({self.light_rgb_tuple[0]}, {self.light_rgb_tuple[1]}, {self.light_rgb_tuple[2]})"

        
        for action in self.colourMenu.actions():
            widget = action.defaultWidget()
            if widget:
                #find the label inside the embedded widget to style the text color
                label = widget.findChild(QLabel)
                
                #apply the background and border-radius to the embedded widget itself
                widget.setStyleSheet(f"""
                    QWidget {{
                        background-color: {colour_rgb_str};
                        border-radius: 6px;
                        margin: 2px 5px 2px 5px; /* Add margin to visually separate items */
                    }}
                """)
                
                if label:
                    label.setStyleSheet(f"color: {self.hexval}") #needs a contrastive colour


            # Apply styling to the browsermenu (Engine Selector)
            for action in self.browserMenu.actions():
                widget = action.defaultWidget()
                if widget:
                    # Get the engine name from the action data (e.g., 'google')
                    act_data = action.data()
                    engine_key = act_data[0] if (isinstance(act_data, tuple) or isinstance(act_data, list)) else "new_engine"

                    # Find the text label using its unique object name
                    # findChild(Class, name) is safer than findChild(Class)
                    text_label = widget.findChild(QLabel, f"browser_menu_text_label_{engine_key}")
                    
                    # Apply the background and border-radius to the embedded widget itself
                    widget.setStyleSheet(f"""
                        QWidget {{
                            background-color: {colour_rgb_str};
                            border-radius: 6px;
                            margin: 2px 5px 2px 5px; /* Add margin to visually separate items */
                        }}
                    """)
                    
                    if text_label:
                        text_label.setStyleSheet(f"color: {self.hexval}")




    def ToggleColourTheme(self, profile, themes):
        colourkeys = list(themes.keys())
        keyselect = colourkeys.index(profile)
        next_index = (keyselect + 1) % len(colourkeys)
        next_profile = colourkeys[next_index]
        
        self.selectedprofile = next_profile
        #all colour profile change handling is done in SelectColourTheme function to reduce total lines
        self.SelectColourTheme(next_profile, themes)

        

    




    '''Cookie Management'''

    def on_cookie_received(self, cookie):
        #these three aren't technically doing anything but they're good references for later
        name = cookie.name().data().decode(errors='ignore')
        domain = cookie.domain()
        value = cookie.value().data().decode()
        #actual logic - refresh cookie dictionary each time a new one is added
        self.cookiedict = self.cookieManager.on_cookie_added(cookie, self.current_browser.url().host())


    def cookieGUI(self):
        self.cookieMenu.clear()
        row_colour = f"rgb({self.light_rgb_tuple[0]}, {self.light_rgb_tuple[1]}, {self.light_rgb_tuple[2]})"

        if not hasattr(self, 'cookiedict') or not self.cookiedict:
            self.cookieMenu.addAction("No cookies detected yet.")
            return

        self.cookieMenu = self.barManager.update_cookie_menu(row_colour)

    def handle_cookie_action(self, cookieID, action_type):
        """Helper to process data and force a refresh while menu is open."""
        if action_type == "accept":
            self.cookieManager.acceptCookie(cookieID)
        else:
            self.cookieManager.cookieEVAPORATOR(cookieID)
        
        #Re-Run gui builder
        self.cookieManager.refresh_cookie_list()
        self.cookieMenu.adjustSize()
        self.cookieGUI() 
    
    def cookieMassDelete(self):
        self.cookie_store.deleteAllCookies()



    
if __name__ == "__main__":
    # Register scheme FIRST - before QApplication or any dialogs
    registerScheme()
    qInstallMessageHandler(qt_message_router)
    
    # NOW create the application
    app = QApplication(sys.argv)

    # Show profile selector
    selectedProfile = None
    handoff_path = f"{srcSourceDir}/data/currentProfile.json"

    if os.path.exists(handoff_path):
        
        print("loading from profile")
        with open(handoff_path) as f:
            selectedProfile = json.load(f)
        
        os.remove(handoff_path)

    else:
        launcher = profileSelectUI()

        if launcher.exec() != QDialog.Accepted:
            sys.exit(0)

        selectedProfile = launcher.getSelectedConfig()
    
    startupSettings = selectedProfile["stored_data"]

    settingsActivate(startupSettings)

    if "DNS-over-HTTPS" in startupSettings:
        updateDoHSettings(startupSettings["DNS-over-HTTPS"], startupSettings)

    # Create the browser
    window = Browser(profile_config=selectedProfile)
    GPUErrorMonitor.emergency_fired.connect(window.executeEmergency)
    window.show()

    sys.exit(app.exec())