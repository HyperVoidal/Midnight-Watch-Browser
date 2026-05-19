import sys
import warnings
import PySide6
from PySide6.QtCore import QUrl, QObject, Slot, QDateTime
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlScheme, QWebEngineUrlSchemeHandler, qWebEngineChromiumVersion
from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtNetwork import QNetworkCookie, QNetworkCookieJar, QNetworkAccessManager
from PySide6.QtWebEngineCore import QWebEngineCookieStore, QWebEngineGlobalSettings
from PySide6.QtWebChannel import QWebChannel
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
from network_controller import *
from ui_core import *
from cookieManager import CookieManager


print("PyQt6 Version: " + PySide6.__version__)
print("Internal Chromium Version: " + qWebEngineChromiumVersion())
#Icon cache 
icon_cache_dir = Path(__file__).parent / "ui/icon_cache"
icon_cache_dir.mkdir(exist_ok=True)

#Main src source
srcSourceDir = Path(__file__).parent

#Icon attachment filepath system
def get_normIcon(name):
    icon_path = icon_cache_dir / f"{name}"

    return QIcon(str(icon_path))


with open (f"{srcSourceDir}/data/engineData.json", "r") as f:
    engineData = dict(json.load(f))

#Secondary dictionary to continue compat with current functions
engines = {}
engine = ""
for key, value in engineData.items():
    engines[key] = value["URL"]
    if value["active"] == True:
        engine = key

#print("ENGINES LIST FROM JSON: ", engines)
print("Startup Selected Engine: ", engine)

#setText names
global eColsButton, eColsStyle
eColsButton = []
eColsStyle = []

#Apply starting settings from settings json file
with open (f"{srcSourceDir}/data/actionToggles.json", "r") as f:
    global toggles
    toggles = dict(json.load(f))


# ---- MAIN FUNCTIONS ----
def updateDoHSettings(provider):
    doh_providers = {
        "Default": {
            "mode": QWebEngineGlobalSettings.SecureDnsMode.SystemOnly, 
            "url": ""
        }, #No DoH
        "Cloudflare": {
            "mode": QWebEngineGlobalSettings.SecureDnsMode.SecureOnly, 
            "url": "https://cloudflare-dns.com/dns-query"
        }, #Secure but no additional systems
        "Google Public DNS": {
            "mode": QWebEngineGlobalSettings.SecureDnsMode.SecureOnly, 
            "url": "https://dns.google/dns-query/dns-query"
        }, #Fastest and most accessible but less secure
        "AdGuard": {
            "mode": QWebEngineGlobalSettings.SecureDnsMode.SecureOnly, 
            "url": "https://dns.adguard-dns.com/dns-query"
        }, #Slower but adds an additional ad/tracker blocker
        "AdGuard Family": {
            "mode": QWebEngineGlobalSettings.SecureDnsMode.SecureOnly, 
            "url": "https://family.adguard-dns.com/dns-query"
        } #Adguard system but with additional adult content filters
    }

    if provider not in doh_providers:
        print(f"Error: Unknown provider '{provider}'")
        return False

    config = doh_providers[provider]
    dns_settings = QWebEngineGlobalSettings.DnsMode()
    dns_settings.secureMode = config["mode"]

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
        ]

    if "Cookie-Prediction-Sensitivity" in toggles.keys():
        global sensitivity
        sensitivity = toggles["Cookie-Prediction-Sensitivity"] #0 for limited blocking, 1 for middle ground, 2 for extensive, 3 for block everything with no limits. Anything past 1 may break persistent data

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

class objectMasterBridge(QObject):
    # Signal to push updates to JS (like a ticking clock or settings change)
    dataUpdated = Signal(str, str) # (key, value)

    # Signal to request a search from the html page
    searchRequested = Signal(str)

    #Placeholder signal to send back adjustments to the actionToggles.json file
    dataReturned = Signal(str, str)


    def __init__(self, browser):
        super().__init__()
        with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            self.colourData = dict(json.load(f))
        self.browser = browser

    @Slot(str)
    def receiveSearchQuery(self, query):
        cQuery = query.strip()
        if cQuery:
            print("HTML Bridge received: " + cQuery)
            self.searchRequested.emit(cQuery)

    @Slot(list)
    def receiveData(self, data):
        if data:
            #data is returned as a list giving [0, 1] for [header, value] for insertion into json files
            dataHeader = data[0]
            dataValue = data[1]
            print(f"Received data: {dataHeader}: {dataValue}")

            with open (f"{srcSourceDir}/data/actionToggles.json", "r") as file_grab:
                settingsData = dict(json.load(file_grab))
            
            if dataHeader == "blur-slider":
                settingsData["Blur"] = round(int(dataValue) / 25)
            
            if dataHeader == "cookieFilterSens":
                settingsData["Cookie-Prediction-Sensitivity"] = int(dataValue)
                #update filter sentivity
                new_level = int(dataValue)
                settingsData["Cookie-Prediction-Sensitivity"] = new_level
                self.browser.cookieManager.updateSensitivity(new_level)

            if dataHeader == "DNSoverHTTPS": 
                settingsData["DNS-over-HTTPS"] = str(dataValue)

                #Trigger informational changes
                updateDoHSettings(str(dataValue))

            if dataHeader == "TabCloseCookieAction": 
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
            
            if dataHeader == "imageUpload":
                fileInfo = dataValue
                fileName = fileInfo["name"]
                header, encoded = fileInfo["data"].split(",", 1)
                file_bytes = base64.b64decode(encoded)

                #Image upload sanitiser - make sure it's not a hidden attack (e.g. image.exe.png or some other non-image item)
                try:
                    img = Image.open(io.BytesIO(file_bytes))
                    img.verify()

                    new_file_hash = hashlib.md5(file_bytes).hexdigest()

                    save_path = os.path.join(f"{srcSourceDir}/ui/images/", fileName)

                    if os.path.exists(save_path):
                        with open(save_path, "rb") as existing_file:
                            existing_hash = hashlib.md5(existing_file.read()).hexdigest()
                        
                        if new_file_hash == existing_hash:
                            print("Attempted upload image present in files already! Defaulting to using current name")
                        else:
                            random_suffix = uuid.uuid4().hex[:8] #generate random file addition to avoid overwrites if the users' pasted image is different
                            name_part, extension = os.path.splitext(fileName)
                            fileName = f"{name_part}_{random_suffix}{extension}"
                            save_path = os.path.join(f"{srcSourceDir}/ui/images/", fileName)

                    with open (save_path, "wb") as f:
                        f.write(file_bytes)
                    settingsData["Image-Url"] = fileName
                
                except Exception as e:
                    print(f"Possible Security Alert, invalid image type? Error: {e}")

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
            abs_path = os.path.abspath(f"{srcSourceDir}/ui/icon_cache/settings.png")
            return f"file:///{abs_path.replace(os.sep, '/')}" 
        
        # Settings html bridge section
        
        elif key == "blur":
            return str(settingsData["Blur"])
        
        elif key == "cookieSens":
            return str(settingsData["Cookie-Prediction-Sensitivity"])
        
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
            
        else:
            return f"Error: Key: {str(key)} not found"
        

    #potential system to use later for the settings menu
    """ @Slot(str, str)
    def updateData(self, key, value):
        #Generalised setter for JS to save settings
        print(f"Updating {key} to {value}")
        self.settings_data[key] = value
        self.dataUpdated.emit(key, value) """
    


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Midnight Watch Browser")
        self.resize(1200, 800)
        self.setWindowIcon(get_normIcon("tightlyCroppedIcon.png"))
        global eColsStyle
        global eColsButton
        global sensitivity

        

        self.user = "mainUser"

        
        self.profile = QWebEngineProfile("PersistentUser", self)
        self.current_browser = QWebEngineView(self)

        #Url Manager
        self.UrlManager = UrlManager()
        #Assign URL Scheme to page loaders
        self.handler = UrlCustomSchemeManager()
        self.profile.installUrlSchemeHandler(b"MidnightWatch", self.handler)
        
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

        #Would be good to disable for efficiency and maximum security but I need javascript actually working - could be a toggleable system?
        settings.setAttribute(settings.WebAttribute.JavascriptEnabled, True)
        


        #Data storage management - future plans to use this for history saving and long term cookie storage/removal choices for users
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
        self.cookieManager = CookieManager(self.profile, sensitivity)
        self.cookie_store = self.profile.cookieStore()
        self.cookie_store.deleteAllCookies()
        self.cookie_store.loadAllCookies() 
        self.cookie_store.cookieAdded.connect(self.on_cookie_received)
        self.cookiedict = {} #Set up for later to store cookies for display in the accept/deny GUI


        #instantiate objectMasterBridge
        self.objectBridge = objectMasterBridge(self)
        self.objectBridge.searchRequested.connect(self.htmlSearch)
        self.channel = QWebChannel(self.current_browser.page())
        self.channel.registerObject("pyBridge", self.objectBridge)


        #Bar Management System
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.barManager = BarManager(self, eColsStyle, eColsButton)

        self.tabs = self.barManager.setup_tabs()

        if actionToggles["Tab-Position"] in ["East", "West"]:
             self.tabs.tabCloseRequested.connect(lambda i: QTimer.singleShot(0, self.tabs.tabBar().update_hover_from_cursor))
        self.tabs.tabCloseRequested.connect(lambda i: (self.close_tab(i)))
        self.tabs.currentChanged.connect(self.switch_tab)

        self.nav_bar = self.barManager.setup_navbar()

        self.bookmarks_bar = self.barManager.setup_bookmarksbar()

        self.status_bar = self.barManager.setup_statusbar()


        with open (f"{srcSourceDir}/data/actionToggles.json", "r") as f:
            BootData = dict(json.load(f))

        #set components on top and bottom based on json settings
        for element in BootData["Top-Stack"]:
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
        self.tabs.setTabPosition(mapping[BootData["Tab-Position"]])
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.tabs, 1)

        for element in BootData["Bottom-Stack"]:
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
        self.selectedprofile = toggles["Colour-Theme"]
        print(self.selectedprofile)

        with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            Colourdata = dict(json.load(f))
        self.colourpalette_btn, self.colourMenu = self.barManager.setup_colourPalette_button(Colourdata)
        


        #engine system
        self.engine = engine
        self.engine_btn = None
        self.engine_btn, self.browserMenu = self.barManager.setup_engine_button(engines)
        self.current_browser.urlChanged.connect((lambda qurl, browser=self.current_browser: self.on_url_changed(qurl, browser)))



        #Cookie Menu GUI
        self.cookie_btn, self.cookieMenu = self.barManager.setup_cookie_button()
        self.cookieMenu.aboutToShow.connect(self.cookieGUI)

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
        """ tabmute_action = QAction("&Mute &Tab", self)
        self.addAction(tabmute_action)
        tabmute_action.setShortcut(QKeySequence("Ctrl+M"))
        tabmute_action.triggered.connect(self.mute_tab) """



        #Miscellaneous additions

        #Zoom
        self.zoomValue = 100
        self.tab_zoom_values = {} #Dictionary to store zoom values for each tab
        self.is_panning = False
        self.pan_start_pos = None
        self.pan_offset_x = 0
        self.pan_offset_y = 0




        #Run all browser startup triggers such as loading tabs from previous sessions, deploying js code, etc.
        self.onStartup()








    '''Startup and Shutdown functions'''

    def onStartup(self):
        #Load all tabs from most recent shutdown if possible
        if saveTabsOnRestart:
            try:
                with open(f"{srcSourceDir}/data/bootupTabs.json", "r") as f:
                    savetabs = json.load(f)
                    
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

    def shutdown_Systems(self):
        if saveTabsOnRestart:
            #save all urls to a json file for attempted re-opening on browser start
            savetabs = {}
            for tab in range (self.tabs.count()):
                if "midnightwatch://" in self.tabs.widget(tab).url().toString():
                    pass #Skip custom url scheme pages
                else:
                    savetabs[self.tabs.widget(tab).url().toString()] = str(self.tabs.tabText(tab))
                    print(f"Saving: {str(self.tabs.tabText(tab))}")

            with open(f"{srcSourceDir}/data/bootupTabs.json", "w") as f:
                json.dump(savetabs, f, indent=4)

        # Clean up all remaining pages before closing to prevent profile release errors
        for tab_index in range(self.tabs.count()):
            browser = self.tabs.widget(tab_index)
            if browser and hasattr(browser, 'page') and browser.page():
                browser.page().deleteLater()

        #Clear HTTP cache to avoid potential clientside injection attacks
        self.profile.clearHttpCacheCompleted.connect(self.exit_app)
        self.profile.clearHttpCache()


    def exit_app(self):
        QApplication.quit()





    '''Main Events Handling'''

    def closeEvent(self, event):
        if self.WindowConfirmation("Exit", "Close Midnight Watch?"):
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
        
        if toggles["Tab-Position"] in ["East", "West"]:
            self.tabs.tabBar().update_hover_from_cursor()

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_tabs_sized'):
            self.update_tab_sizes()
            self._tabs_sized = True

    def wheelEvent(self, event):
        """Handle mouse wheel zoom (including two-finger trackpad gestures)"""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Ctrl + Scroll = Zoom
            if event.angleDelta().y() > 0:
                self.setContentZoom(True)
            else:
                self.setContentZoom(False)
            event.accept()
        else:
            super().wheelEvent(event)
                





    '''Window System'''

    def WindowConfirmation(self, title, message, num=2):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        if num == 1:
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes)
            yes_button = msg_box.button(QMessageBox.StandardButton.Yes)
            yes_button.setText("Okay")
        elif num == 2:
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        else: 
            print("Too high a number of buttons passed to window confirmation!")
            return
            
        msg_box.exec()
        return msg_box.clickedButton() == yes_button

        

    def WindowInput(self, title, message, default_text=""):
        text, ok = QInputDialog.getText(
            self,
            title,
            message,
            QLineEdit.EchoMode.Normal,
            default_text
        )
        if ok and text.strip():
            return text.strip()
        return None







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




    '''Tab Management'''

    def add_new_tab(self, qurl=None, label="New Tab"):
        if qurl is None or isinstance(qurl, bool):
            qurl = QUrl("MidnightWatch://local/homepage.html")
            
        if isinstance(qurl, tuple):
            qurl = qurl[0]
        
        browser = QWebEngineView()
        new_page = QWebEnginePage(self.profile, browser)
        new_page.setWebChannel(self.channel)
        browser.setPage(new_page)
        browser.setUrl(qurl)

        self.tab_zoom_values[browser] = 100
        browser.setZoomFactor(1.0)
        

        i = self.tabs.addTab(browser, label)

        self.tabs.setCurrentIndex(i)

        if hasattr(self, 'contrast_qcolor'):
            self.tabs.tabBar().setTabTextColor(i, self.contrast_qcolor)

        # Connect signals
        new_page.iconChanged.connect(lambda: self.update_tab_icon(browser))
        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_tab_title(browser))
        browser.loadStarted.connect(lambda: self.barManager.start_reload_animation())
        browser.loadFinished.connect(lambda ok, b=browser: (self.barManager.stop_reload_animation(), self.on_load_finished(browser)))
        browser.titleChanged.connect(lambda title, browser=browser, i=i: (self.update_tab_title(browser, title), self.tabs.setTabToolTip(i, f"{title}\n{self.UrlManager.normalise_url(browser.url().toString())}")))


        self.update_tab_sizes()
        self.update_tab_icon(self.current_browser)
        #Update tab apperances for vertical-specific adjustments
        if toggles["Tab-Position"] in ["East", "West"]:
            VerticalTabBar.update_close_buttons(self.tabs.tabBar())
            QTimer.singleShot(0, self.tabs.tabBar().update_close_buttons)
        else:
            pass
        return browser
    
    def on_url_changed(self, qurl, browser):
        if browser != self.current_browser:
            return

        clean = self.UrlManager.normalise_url(qurl.toString())
        self.url_bar.setText(clean)
    
    def update_tab_icon(self, browser):
        tab_index = self.tabs.indexOf(browser)
        if tab_index != -1:
            icon = browser.page().icon()
            if not icon.isNull():  # Only set if icon actually loaded
                self.tabs.setTabIcon(tab_index, icon)
            else:
                self.tabs.setTabIcon(tab_index, get_normIcon("tabIcon.png"))  # Set default icon if none
                
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
                        if data["domain"] in target_url:
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
        if toggles["Tab-Position"] in ["East", "West"]:
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
            if toggles["Tab-Position"] in ["East", "West"]:
                QTimer.singleShot(0, self.tabs.tabBar().update_close_buttons)
            

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
        if toggles["Tab-Position"] in ["East", "West"]:
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
            search_url = engines[engine] + input_text.replace(" ", "+")
            self.current_browser.setUrl(QUrl(search_url))

        #update url bar to proper cleaned url text
        raw_url = self.current_browser.url().toString()
        clean_url = self.UrlManager.normalise_url(raw_url)
        self.url_bar.setText(clean_url)

    def htmlSearch(self, cQuery):
        #convert to search link
        search_url = engines[engine] + cQuery.replace(" ", "+")
        #update and process system
        self.current_browser.setUrl(QUrl(UrlManager.normalise_url(True, search_url)))
        #update url bar to proper cleaned url text
        raw_url = self.current_browser.url().toString()
        clean_url = self.UrlManager.normalise_url(raw_url)
        self.url_bar.setText(clean_url)
        



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
            with open(f"{srcSourceDir}/data/bookmarks.json", "r") as f:
                bookmarkData = json.load(f)

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
        super(QLineEdit, self.url_bar).mousePressEvent(event)
    
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
            with open(f"{srcSourceDir}/data/engineData.json", "r") as f:
                engineData = dict(json.load(f))
            for key, value in engineData.items():
                if engineData[key]["active"] == True:
                    engineData[key]["active"] = False
            engineData[self.engine]["active"] = True
            with open(f"{srcSourceDir}/data/engineData.json", "w") as f:
                json.dump(engineData, f, indent=4)


    '''Bookmarks System'''

    #needs to create a menu popup that can accept a name input. Use Qsanitiser system to clean user input to keep everything safe
    def add_bookmark(self, url):
        name = self.WindowInput(
            "Add Bookmark",
            "Enter bookmark name:",
            self.tabs.tabText(self.tabs.currentIndex())
        )

        if not name:
            return
        
        try:
            with open(f"{srcSourceDir}/data/bookmarks.json", "r") as f:
                data = json.load(f)
        except:
            data = {}

        new_id = str(uuid.uuid4())

        data[new_id] = {
            "name": name,
            "url": url
        }

        with open(f"{srcSourceDir}/data/bookmarks.json", "w") as f:
            json.dump(data, f, indent=4)

        #reload bookmarks bar to show new bookmark
        self.barManager.refresh_bookmarksbar()
        self.update_url_bar_buttons(self.current_browser.url().toString(), self.current_browser)

    def remove_bookmark(self, id):
        with open(f"{srcSourceDir}/data/bookmarks.json", "r") as f:
            data = json.load(f)

        del data[id]

        with open(f"{srcSourceDir}/data/bookmarks.json", "w") as f:
            json.dump(data, f, indent=4)
        
        self.barManager.refresh_bookmarksbar()
        self.update_url_bar_buttons(self.current_browser.url().toString(), self.current_browser)

    


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
        
        #need to set colourmenu attibutes individually for each QMenu dropdown segment
        self.colourMenu.setAttribute(Qt.WA_TranslucentBackground)
        self.browserMenu.setAttribute(Qt.WA_TranslucentBackground)
        self.cookieMenu.setAttribute(Qt.WA_TranslucentBackground)

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

            #needs to happen again for engine menu, maybe this needs reworking??
            #can't seem to find the engine labels?
            # Apply styling to the browsermenu (Engine Selector)
            for action in self.browserMenu.actions():
                widget = action.defaultWidget()
                if widget:
                    # Get the engine name from the action data (e.g., 'google')
                    engine_key = action.data()[0] 

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

        

    #system for when I implement the main colourtheme editor
    def ColourThemeEditor(self):
        print("ColourThemeEditor still WIP")
        pass

    




    '''Cookie Management'''

    def on_cookie_received(self, cookie):
        #these three aren't technically doing anything but they're good references for later
        name = cookie.name().data().decode(errors='ignore')
        domain = cookie.domain()
        value = cookie.value().data().decode()
        #actual logic - refresh cookie dictionary each time a new one is added
        self.cookiedict = self.cookieManager.on_cookie_added(cookie)


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




'''Main execution loop'''
    
if __name__ == "__main__":
    scheme = QWebEngineUrlScheme(b"MidnightWatch")
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme |
        QWebEngineUrlScheme.Flag.LocalScheme |
        QWebEngineUrlScheme.Flag.LocalAccessAllowed |
        QWebEngineUrlScheme.Flag.CorsEnabled |
        QWebEngineUrlScheme.Flag.FetchApiAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)

    settingsActivate(toggles)
    app = QApplication(sys.argv)

    #Trigger DNS over HTTPS System
    if "DNS-over-HTTPS" in toggles.keys():
        updateDoHSettings(toggles["DNS-over-HTTPS"])

    window = Browser()
    window.show()
    sys.exit(app.exec())
