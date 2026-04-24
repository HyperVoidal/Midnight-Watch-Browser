import sys
import warnings
from PySide6.QtCore import QUrl 
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtNetwork import QNetworkCookie, QNetworkCookieJar, QNetworkAccessManager
from PySide6.QtWebEngineCore import QWebEngineCookieStore
from urllib.parse import urlparse
from pathlib import Path
import requests
import urllib.request
import os
from PIL import Image, ImageOps
import json
import re
from network_controller import AdInterceptor, EVAdInterceptor, CosmeticBlocker, ScriptletBlocker
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
        #self.profile.persistentCookiesPolicy() = True

        #settings system
        settings = self.profile.settings()
        #Leave these true so javascript injections function properly
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(settings.WebAttribute.AllowRunningInsecureContent, True)
        #Allows important sandboxing similar to Chrome. NEVER ENABLE THIS, IT LETS FILEPAGE JAVASCRIPT READ FILE HEADERS ON PC
        settings.setAttribute(settings.WebAttribute.LocalContentCanAccessFileUrls, False)
        #Would be good but I need javascript actually working
        settings.setAttribute(settings.WebAttribute.JavascriptEnabled, True)
        #Avoid giving instant clipboard access
        settings.setAttribute(settings.WebAttribute.JavascriptCanAccessClipboard, False)


        #Data storage management - future plans to use this for history saving and long term cookie storage/removal choices for users
        base_path = os.path.abspath("./Main_Repo/src/data/Browser_Data")
        profile_path = os.path.join(base_path, "User_Profile")
        cache_path = os.path.join(base_path, "User_Cache")

        os.makedirs(profile_path, exist_ok=True)
        os.makedirs(cache_path, exist_ok=True)

        self.profile.setCachePath(cache_path)
        self.profile.setPersistentStoragePath(profile_path)



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

        self.home_path = f"{srcSourceDir}/ui/homepage.html"


        #Bar Management System
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.barManager = BarManager(self, eColsStyle, eColsButton, srcSourceDir)

        self.tabs = self.barManager.setup_tabs()
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.switch_tab)

        self.nav_bar = self.barManager.setup_navbar()

        self.bookmarks_bar = self.barManager.setup_bookmarksbar()


        with open (f"{srcSourceDir}/data/actionToggles.json", "r") as f:
            PositionOrder = dict(json.load(f))

        #set components on top and bottom based on json settings
        for element in PositionOrder["top_bar"]:
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
        self.tabs.setTabPosition(mapping[PositionOrder["tab_position"]])
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.tabs, 1)

        for element in PositionOrder["bottom_bar"]:
            widget = getattr(self, element, None)
            if widget:
                self.layout.addWidget(widget)
            else:
                print("Couldn't find mapping assignment for bottom bar element: ", element)

        self.url_bar = self.barManager.setup_url_bar()


        self.setCentralWidget(self.container)



    

        #Colour palette systems
        with open (f'{srcSourceDir}/data/userData.json', "r") as f:
            Udata = dict(json.load(f))
        self.selectedprofile = (dict(Udata[self.user]))["ColourProfile"]
        print(self.selectedprofile)

        with open (f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            Colourdata = dict(json.load(f))
        self.colourPalette_btn, self.colourMenu = self.barManager.setup_colourPalette_button(Colourdata)
        


        #engine system
        self.engine = engine
        self.engine_btn = None
        self.engine_btn, self.browserMenu = self.barManager.setup_engine_button(engines)
        self.current_browser.urlChanged.connect((lambda q: self.url_bar.setText(q.toString())))



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
        exit_action.triggered.connect(self.exit_app)

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
        self.add_new_tab(QUrl.fromLocalFile(str(self.home_path)), "Home")
        
        #Update all tabs to the correct appearance
        self.update_tab_icon(self.current_browser)

    def exit_app(self):
        if saveTabsOnRestart:
            #save all urls to a json file for attempted re-opening on browser start
            savetabs = {}
            for tab in range (self.tabs.count()):
                if "homepage.html" in self.tabs.widget(tab).url().toString():
                    pass #skip new tab windows
                else:
                    savetabs[self.tabs.widget(tab).url().toString()] = str(self.tabs.tabText(tab))
                    print(f"Saving: {str(self.tabs.tabText(tab))}")

            with open(f"{srcSourceDir}/data/bootupTabs.json", "w") as f:
                json.dump(savetabs, f)

        # Clean up all remaining pages before closing to prevent profile release errors
        for tab_index in range(self.tabs.count()):
            browser = self.tabs.widget(tab_index)
            if browser and hasattr(browser, 'page') and browser.page():
                browser.page().deleteLater()

        QApplication.quit()
        







    '''Main Events Handling'''

    def closeEvent(self, event):
        if self.WindowConfirmation("Exit", "Close Midnight Watch?"):
            self.exit_app()
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







    '''Buttons and Icons'''

    

    #button assignment functions
    def go_back(self): self.current_browser.back()
    def reload_tab(self): self.current_browser.reload()
    def go_forward(self): self.current_browser.forward()
    def go_home(self): self.current_browser.setUrl(QUrl.fromLocalFile(str(self.home_path)))
    def new_tab(self): self.add_new_tab(QUrl.fromLocalFile(str(self.home_path)), "Home")






    '''Tab Management'''

    def current_browser(self):
        return self.tabs.currentWidget()
    
    def add_new_tab(self, qurl=None, label="New Tab"):
        if qurl is None or isinstance(qurl, bool):
            qurl = QUrl.fromLocalFile(f"{srcSourceDir}/ui/homepage.html")
        
        if isinstance(qurl, tuple):
            qurl = qurl[0]
        
        browser = QWebEngineView()
        new_page = QWebEnginePage(self.profile, browser)
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
        browser.titleChanged.connect(lambda title, browser=browser: self.update_tab_title(browser, title))

        
        if qurl.toString().endswith("homepage.html"):
            self.url_bar.setText("Homepage")

        self.update_tab_sizes()
        self.update_tab_icon(self.current_browser)
        #fix close button not disappearing issue for vertical tabs when a new one is created
        if toggles["tab_position"] in ["East", "West"]:
            VerticalTabBar.update_close_buttons(self.tabs.tabBar())
        else:
            pass
        return browser
    
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

    def switch_tab(self, index):
        current_browser = self.tabs.widget(index)
        if current_browser:
            self.current_browser = current_browser
            self.url_bar.setText(current_browser.url().toString())
            if current_browser.url().toString().endswith("homepage.html"):
                self.url_bar.setText("Homepage")
            

    def update_tab_title(self, browser, title=None):
        i = self.tabs.indexOf(browser)
        if i != -1:
            # Use provided title or fallback
            if not title:
                title = browser.url().toString()

            # Clean it up a bit for display
            if len(title) > 60:
                title = title[:57] + "..."
            
            if title.endswith('homepage.html'):
                title = 'Homepage'

            self.tabs.setTabText(i, title)
            self.update_url_bar_buttons(browser.url().toString(), browser)
            
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
        if toggles["tab_position"] in ["East", "West"]:
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

    '''URL Handling'''

    def load_url(self):
        #had to encase this in a try-except loop, there's an odd keyboardinterrupt error that is cased by virtually nothing and fixes by pressing enter again, this should circumvent.
        input_text = self.url_bar.text().strip()
        if not input_text:
            return

        # QUrl.fromUserInput automatically handles missing schemes (adds http://)
        # and checks if the string looks like a valid web address
        url = QUrl.fromUserInput(input_text)

        if url.isValid() and "." in input_text and " " not in input_text:
            # It's a valid URL (e.g., "google.com")
            self.current_browser.setUrl(url)
        else:
            # It's a search query
            search_url = engines[engine] + input_text.replace(" ", "+")
            self.current_browser.setUrl(QUrl(search_url))

    def on_load_finished(self, browser):
        #attempt to close extra boxes on blocked ads
        CosmeticBlocker.inject_css(browser)
        ScriptletBlocker.inject_scriptlets(browser)
        pass

    def update_url_bar_buttons(self, url, browser):
        with open(f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
            Colourdata = json.load(f)
        with open(f"{srcSourceDir}/data/bookmarks.json", "r") as f:
            bookmarkData = json.load(f)
        
        colour = Colourdata[self.selectedprofile]["bookmark_btn"]

        print(self.current_browser.url().toString())

        #check current url, if not added, grab the unadded bookmark button, otherwise grab the added bookmark button
        if self.current_browser.url().toString() in bookmarkData.values():
            buttoncolourer("bookmark_btn", colour, "BookmarkAdded")
            icon = get_normIcon("BookmarkAdded")
            self.bookmark_button = self.url_bar.addAction(icon, QLineEdit.TrailingPosition)
            self.bookmark_button.setToolTip("Remove Bookmark")
            self.bookmark_button.triggered.connect(lambda: self.remove_bookmark(self.current_browser.url().toString()))
        else:
            buttoncolourer("bookmark_btn", colour, "BookmarkNotAdded")
            icon = get_normIcon("BookmarkNotAdded")
            self.bookmark_button = self.url_bar.addAction(icon, QLineEdit.TrailingPosition)
            self.bookmark_button.setToolTip("Add Bookmark")
            self.bookmark_button.triggered.connect(lambda: self.add_bookmark(self.current_browser.url().toString()))
        
        self.url_bar.update()

        


        
        #NOTE the below code doesn't work because it was designed for the extensions system and I've commented it out for safety.
        #I'm keeping it around after the removal of the extensions system because it has some useful references for how I might 
        #implement additions to the URL bar such as bookmarking a link or something else I might think of e.g. automatic webpage colour switching (dark reader emulation)
        """ if is_webstore:
            with open(f"{srcSourceDir}/data/colourProfiles.json", "r") as f:
                Colourdata = json.load(f)
                colour = Colourdata[self.selectedprofile]["ext_btn"]
            buttoncolourer("extdown_btn", colour)

            icon = get_normIcon("extdown")
            self.reopen_button = self.url_bar.addAction(icon, QLineEdit.TrailingPosition)
            self.reopen_button.setToolTip("Reopen Extension Prompt")
            self.reopen_button.triggered.connect(lambda: self.triggerExtensionsPopup(browser, url))
            self.url_bar.update() """
    



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
                json.dump(engineData, f)


    '''Bookmarks System'''
    
    #needs to create a menu popup that can accept a name input. Use Qsanitiser system to clean user input to keep everything safe
    def add_bookmark(self):
        pass

    def remove_bookmark(self):
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
        with open (f"{srcSourceDir}/data/userData.json", "r") as f:
            dataedit = json.load(f)
        (dict(dataedit["mainUser"]))["ColourProfile"] = profile
        dataedit["mainUser"]["ColourProfile"] = profile
        with open (f"{srcSourceDir}/data/userData.json", "w") as f:
            json.dump(dataedit, f)
            

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
            else:
                print(f"other: {k}")
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
    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec())