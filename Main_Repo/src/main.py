import sys
import warnings
from PySide6.QtCore import QUrl, QObject, Slot, QDateTime
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlScheme, QWebEngineUrlSchemeHandler
from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtNetwork import QNetworkCookie, QNetworkCookieJar, QNetworkAccessManager
from PySide6.QtWebEngineCore import QWebEngineCookieStore
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
from network_controller import *
from ui_core import *
from cookieManager import CookieManager

# Suppress PySide6 SbkConverter warnings for extension enumeration
#warnings.filterwarnings("ignore", message=".*SbkConverter::copyToPython.*")


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

if toggles["DNS-over-HTTPS"]:
    #Forces the browser to resolve domains via HTTPS, hiding lookups from the firewall
    sys.argv.append("--built-in-dns-lookup-enabled")
    sys.argv.append("--dns-over-https-templates=https://cloudflare-dns.com")
    print("DNS-over-HTTPS enabled")
else:
    print("DNS-over-HTTPS disabled")

if toggles["Encrypted-Client Hello"]:
    #Hides the SNI (the website name) during the SSL handshake
    sys.argv.append("--enable-features=EncryptedClientHello")
    print("Encrypted-Client Hello enabled")
else:
    print("Encrypted-Client Hello disabled")

if "Cookie-Prediction-Sensitivity" in toggles.keys():
    global sensitivity
    sensitivity = toggles["Cookie-Prediction-Sensitivity"] #0 for limited blocking, 1 for middle ground, 2 for extensive

if "Cookie-Accept/Deny On Leave" in toggles.keys():
    global siteLeaveCookies
    siteLeaveCookies = toggles["Cookie-Accept/Deny On Leave"] #0 for remove all, 1 for accept all

if "Save-Tabs-On-Restart" in toggles.keys():
    saveTabsOnRestart = toggles["Save-Tabs-On-Restart"]

# ---- MAIN FUNCTIONS ----

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


    def __init__(self):
        super().__init__()
        with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            self.colourData = dict(json.load(f))

    @Slot(str)
    def receiveSearchQuery(self, query):
        cQuery = query.strip()
        if cQuery:
            print("HTML Bridge received: " + cQuery)
            self.searchRequested.emit(cQuery)

    @Slot(str, result=str)
    def getData(self, key):
        #Generalised getter for JS to pull data
        if key == "time":
            timeFormat = (toggles["Time-Display"])[0]
            timeCall = QDateTime.currentDateTime()
            #Syntax: time display goes "hh:mm:ss AP". AP is whether to display AM/PM, lowercase hh means 12-hr, uppercase means 24-hr
            return timeCall.toString(f"{timeFormat} AP") if (toggles["Time-Display"])[1] == True else timeCall.toString(f"{timeFormat}")

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

            date_format, provide_year = toggles["Date-Display"]
            dateCall = QDateTime.currentDateTime()

            # Define base formats without year info
            format_map = {
                "Global": "dd/MM",
                "US": "M/d",
                "ISO": "MM-dd",  
                "Long-Form": "dddd, d MMMM",
                "Minimalist": "dd MMM"
            }

            base = format_map.get(date_format, "dd/MM")

            # Specific year-attachment logic per format
            if provide_year:
                if date_format == "ISO":
                    base = f"yyyy-{base}"
                elif date_format in ["Global", "US"]:
                    base += "/yyyy"
                else: # Long-Form and Minimalist
                    base += " yyyy"

            return dateCall.toString(base)
        
        elif key == "greeting":
            if toggles["Greeting"] == True:
                hourCall = int(QDateTime.currentDateTime().toString("HH")) #returns time in 24hr
                
                match hourCall:
                    case hC if 4 <= hC < 12:
                        return (f"Good Morning, " + toggles["Name"])
                    case hC if 12 <= hC < 17:
                        return (f"Good Afternoon, " + toggles["Name"])
                    case hC if 17 <= hC < 21:
                        return (f"Good Evening, " + toggles["Name"])
                    case hC if (21 <= hC <= 23) or (0 <= hC < 4):
                        return (f"Sleep Well, " + toggles["Name"])
                    case _:
                        return (f"Hello, " + toggles["Name"])
            else:
                return ""
        
        elif key == "blur":
            return str(f"{toggles["Blur"]}px")
        
        elif key == "BGimage":
            return str(f"images/{toggles["Image-Url"]}")
            
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
        self.setWindowTitle("Midnight Engine")
        self.resize(1200, 800)
        self.setWindowIcon(get_normIcon("tightlyCroppedIcon.png"))
        global eColsStyle
        global eColsButton
        global sensitivity

        

        self.user = "mainUser" #make a system for this at some point!!!from PySide6.QtWebEngineCore import QWebEngineProfile

        
        self.profile = QWebEngineProfile("PersistentUser", self)
        self.current_browser = QWebEngineView(self)
        #self.profile.persistentCookiesPolicy() = True #enable this another time

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


        #Bar Management System
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.barManager = BarManager(self, eColsStyle, eColsButton, srcSourceDir)

        self.tabs = self.barManager.setup_tabs()

        self.tabs.tabCloseRequested.connect(lambda i: (self.close_tab(i), QTimer.singleShot(0, self.tabs.tabBar().update_hover_from_cursor)))
        self.tabs.currentChanged.connect(self.switch_tab)

        self.nav_bar = self.barManager.setup_navbar()

        self.bookmarks_bar = self.barManager.setup_bookmarksbar()


        with open (f"{srcSourceDir}/data/actionToggles.json", "r") as f:
            PositionOrder = dict(json.load(f))

        #set components on top and bottom based on json settings
        for element in PositionOrder["Top-Bar"]:
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
        self.tabs.setTabPosition(mapping[PositionOrder["Tab-Position"]])
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.tabs, 1)

        for element in PositionOrder["Bottom-Bar"]:
            widget = getattr(self, element, None)
            if widget:
                self.layout.addWidget(widget)
            else:
                print("Couldn't find mapping assignment for bottom bar element: ", element)

        self.url_bar = self.barManager.setup_url_bar()
        #link mouse presses on the url bar to automatically highlight text
        self.url_bar.mousePressEvent = self._url_bar_mouse_press


        self.setCentralWidget(self.container)


        #Object bridging
        self.objectBridge = objectMasterBridge()
        self.objectBridge.searchRequested.connect(self.htmlSearch)
        self.channel = QWebChannel(self.current_browser.page())
        self.channel.registerObject("pyBridge", self.objectBridge)

    

        #Colour palette systems
        self.selectedprofile = toggles["Colour-Theme"]
        print(self.selectedprofile)

        with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            Colourdata = dict(json.load(f))
        self.colourPalette_btn, self.colourMenu = self.barManager.setup_colourPalette_button(Colourdata)
        


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
        EVAdInterceptor.deployPayload(browser=self.current_browser) #TODO: Script executes but doesn't actually work, research into that??? storage access permission denied
        #alternatively, just work on rudimentary adblock and suggest ublock; integrate chrome extensions store



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
        tabclose_action.triggered.connect(self.close_tab)

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

        #Mute tab command - need to actually build
        """ tabmute_action = QAction("&Mute &Tab", self)
        self.addAction(tabmute_action)
        tabmute_action.setShortcut(QKeySequence("Ctrl+M"))
        tabmute_action.triggered.connect(self.mute_tab) """


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

        self.tabs.tabBar().update_hover_from_cursor()

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_tabs_sized'):
            self.update_tab_sizes()
            self._tabs_sized = True
            





    '''Window System'''

    def WindowConfirmation(self, title, message):
        reply = QMessageBox.question(self, title, message,
                                     QMessageBox.StandardButton.No |
                                     QMessageBox.StandardButton.Yes)
        return reply == QMessageBox.StandardButton.Yes
    

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







    '''Buttons and Icons'''

    

    #button assignment functions
    def go_back(self): self.current_browser.back()
    def reload_tab(self): self.current_browser.reload()
    def go_forward(self): self.current_browser.forward()
    def go_home(self): self.current_browser.setUrl(QUrl("MidnightWatch://local/homepage.html"))
    def new_tab(self): self.add_new_tab()
    def open_settings_menu(self): self.open_settings()






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
        #fix close button not disappearing issue for vertical tabs when a new one is created
        if toggles["Tab-Position"] in ["East", "West"]:
            VerticalTabBar.update_close_buttons(self.tabs.tabBar())
        else:
            pass
        QTimer.singleShot(0, self.tabs.tabBar().update_close_buttons)
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
                
    def close_tab(self, index):
        if self.tabs.count() > 1:
            #manage all remaining cookies based on settings preferences
            target_tab = self.tabs.widget(index)
            if target_tab:
                target_url = target_tab.url().toString()
                for key, data in list(self.cookiedict.items()):
                    if data["domain"] in target_url:
                        if siteLeaveCookies:
                            self.cookieManager.acceptCookie(key)
                        else:
                            self.cookieManager.cookieEVAPORATOR(key)

                # Clean up the page before removing the tab to prevent profile release errors
                if hasattr(target_tab, 'page') and target_tab.page():
                    target_tab.page().deleteLater()

            self.tabs.removeTab(index)
        else:
            self.close()

        self.update_tab_sizes()
        QTimer.singleShot(0, self.tabs.tabBar().update_close_buttons)

    def switch_tab(self, index):
        current_browser = self.tabs.widget(index)
        if current_browser:
            self.current_browser = current_browser
            raw_url = current_browser.url().toString()
            clean_url = self.UrlManager.normalise_url(raw_url)
            self.url_bar.setText(clean_url)
            
            #update url bar buttons, especially bookmarks
            self.update_url_bar_buttons(self.current_browser.url().toString(), self.current_browser)
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
        print('tst')
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
    
    def SelectColourTheme(self, profile, themes):
        self.tabs.setStyleSheet("")
        self.tabs.tabBar().setStyleSheet("")
        global eColsButton, eColsStyle
        self.selectedprofile = profile

        self.colourPalette_btn.setToolTip(f"Colour Palettes (currently {profile})")

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
                    if k == "colourPalette_btn":
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
                        # Apply the styles specifically to the dropdown button (colourPalette_btn)
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
                    # fallback: explicitly set stylesheet on tabBar so background is reliably visible
                    existing = tabbar.styleSheet() or ""
                    size_rule = "QTabBar::tab { height: 30px; width: 150px; }"
                    if "QTabBar::tab" not in existing:
                        existing = existing + "\n" + size_rule
                    tabbar.setStyleSheet(existing + f"\nQTabBar {{ background-color: rgb({r}, {g}, {b}); }}")

                    # Also set the QTabWidget pane background so the area behind tabs matches
                    tabs_pal = self.tabs.palette()
                    tabs_pal.setColor(QPalette.Window, color)
                    self.tabs.setAutoFillBackground(True)
                    self.tabs.setPalette(tabs_pal)
                    tabbar.setPalette(tabs_pal)

                    # Update existing tab text contrast
                    for i in range(self.tabs.count()):
                        tabbar.setTabTextColor(i, self.contrast_qcolor)

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

    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec())
