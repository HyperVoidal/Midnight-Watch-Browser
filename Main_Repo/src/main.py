import sys
import warnings
from PySide6.QtCore import QUrl 
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineExtensionManager
from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtNetwork import QNetworkCookie, QNetworkCookieJar, QNetworkAccessManager
from PySide6.QtWebEngineCore import QWebEngineCookieStore
from urllib.parse import urlparse
from pathlib import Path
import urllib.request
import os
from PIL import Image, ImageOps
import json
from network_controller import AdInterceptor, EVAdInterceptor, CosmeticBlocker, ScriptletBlocker
from extensionmanager import *
from ui_core import *
from cookieManager import CookieManager

# Suppress PySide6 SbkConverter warnings for extension enumeration
warnings.filterwarnings("ignore", message=".*SbkConverter::copyToPython.*")

#Tweaking extension support with schemes, environment variables, and profile settings
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-features=ExtensionManifestV2Unsupported,ExtensionManifestV2Disabled"

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

print("ENGINES LIST FROM JSON: ", engines)
print("SELECTED ENGINE: ", engine)


#setText names
global eColsButton, eColsStyle
eColsButton = []
eColsStyle = []

#Encryption Systems enable/disable
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
    sensitivity = toggles["Cookie-Prediction-Sensitivity"]

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
def buttoncolourer(k, v):
    name = (str(k).split("_btn"))[0]
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
        global eColsStyle
        global eColsButton
        global sensitivity
        self.url_bar = QLineEdit()
        eColsStyle.append("url_bar")
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


        #Update adblocker filters from easylist
        update_filters()
        #Adblock interceptor
        self.interceptor = AdInterceptor()
        self.profile.setUrlRequestInterceptor(self.interceptor)
        

        #Extension manager
        self.ext_manager = self.profile.extensionManager()
        self.extman_instance = ExtensionManager(self.ext_manager)
        

        #Initialise cookie jar (Cookie management)
        self.cookieManager = CookieManager(self.profile, sensitivity)
        self.cookie_store = self.profile.cookieStore()
        self.cookie_store.deleteAllCookies()
        self.cookie_store.loadAllCookies() 
        self.cookie_store.cookieAdded.connect(self.on_cookie_received)
        self.cookiedict = {} #Set up for later to store cookies for display in the accept/deny GUI


        self.main_path = Path(__file__).parent
        self.home_path = self.main_path / "ui/homepage.html"
        self.tabs  = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.switch_tab)
        eColsStyle.append("tabs")
        eColsStyle.append("tab_backer") #for background of tab bar!
        # default tab sizing (set once) to avoid repeated overrides
        # Apply sizing directly to the QTabBar so later per-widget stylesheets don't clobber it
        self.tabs.tabBar().setStyleSheet("QTabBar::tab { height: 30px; width: 150px; }")
        self.setCentralWidget(self.tabs)
        self.add_new_tab(QUrl.fromLocalFile(str(self.home_path)), "Home")

        self.nav_bar = QToolBar("Navigation")
        self.addToolBar(self.nav_bar)
        self.nav_bar.setMovable(False)
        self.nav_bar.setStyleSheet("background:rgb(1, 1, 100)")
        eColsStyle.append("nav_bar")

        #buttons

        #url bar buttons - add one for enabling/disabling inbuilt adblock
        

        #main button constructors
        self.ButtonConstructor("back_btn", "Back", "back", "go_back")
        self.ButtonConstructor("reload_btn", "Reload", "reload", "reload_page")
        self.ButtonConstructor("forward_btn", "Forward", "forward", "go_forward")
        self.ButtonConstructor("home_btn", "Home", "home", "go_home")
        self.ButtonConstructor("newtab_btn", "New Tab", "newtab", "new_tab")

        #reload animation components
        self.rotation_angle = 0
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_reload_icon)
        self.current_browser.loadStarted.connect(self.start_reload_animation)
        self.current_browser.loadFinished.connect(self.stop_reload_animation)

        #Colour palette systems
        '''
        Current plan is to steal the dropdown system from my engine selector ui and use it to select themes from a list
        The list is extracted from colourProfiles.json and can be either cycled through by pressing the colourtheme button
        OR clicking the dropdown to select a colour specifically. In the dropdown menu is also a final selector for customising 
        colour palettes that opens the customiser UI and greys out and disables the buttons, allowing users to left click buttons
        to select a colour for them.
        '''
        self.colourPalette_btn = QToolButton(self)
        self.colourPalette_btn.setToolTip("Colour Palettes")
        self.ColourMenu = QMenu(self)

        #define starter profile. Need to do this more elegantly at some point since the profile selection doesn't even start at this it's just a placeholder
        with open (f'{self.main_path}/data/userData.json', "r") as f:
            Udata = dict(json.load(f))
        self.selectedprofile = (dict(Udata[self.user]))["ColourProfile"]
        print(self.selectedprofile)

        with open (f"{self.main_path}/data/colourProfiles.json", "r") as f:
            Colourdata = dict(json.load(f))
        
        for key in Colourdata.keys():
            # Widgets for Menu Items
            Cwidget = QWidget()
            Clayout = QHBoxLayout(Cwidget)
            Clayout.setContentsMargins(5, 2, 5, 2)
            Clayout.setSpacing(5)

            #Add text
            Ctext_label = QLabel(key.capitalize())
            Ctext_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            Clayout.addWidget(Ctext_label)

            #Create Widget Action
            Cwidget_action = QWidgetAction(self)
            Cwidget_action.setDefaultWidget(Cwidget)
            Cwidget_action.setData(key)
            Cwidget_action.triggered.connect(lambda checked, p=key, d=Colourdata: self.SelectColourTheme(p, d))
            self.ColourMenu.addAction(Cwidget_action)

        #add more themes button append
        Awidget = QWidget()
        Alayout = QHBoxLayout(Awidget)
        Alayout.setContentsMargins(5, 2, 5, 2)
        Alayout.setSpacing(5)

        Atext_label = QLabel("Add New Themes")
        Alayout.addWidget(Atext_label)

        Awidget_action = QWidgetAction(self)
        Awidget_action.setDefaultWidget(Awidget)
        Awidget_action.setData("Add New Themes")
        Awidget_action.triggered.connect(self.ColourThemeEditor)
        self.ColourMenu.addAction(Awidget_action)

        
        self.colourPalette_btn.setMenu(self.ColourMenu)
        self.colourPalette_btn.setIcon(get_normIcon("colourPalette"))

        # When the main button is clicked, read the current selectedprofile at click time
        self.colourPalette_btn.clicked.connect(lambda checked=False, d=Colourdata: self.ToggleColourTheme(self.selectedprofile, d))

        self.colourPalette_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.nav_bar.addWidget(self.colourPalette_btn)
        eColsButton.append("colourPalette_btn")
        


        #engine system
        self.engine = engine
        self.engine_btn = QToolButton(self)
        self.engine_btn.setText("Search With...")
        self.browsermenu = QMenu(self)

        for key, search_url in engines.items():
            # Create widget for menu item
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(5, 2, 5, 2)
            layout.setSpacing(5)
            
            # Add icon
            icon_label = QLabel()
            icon = QIcon(str(icon_cache_dir / f"{key}"))
            icon_label.setPixmap(icon.pixmap(16, 16))
            layout.addWidget(icon_label)
            icon_label.setFixedWidth(30) 
            
            # Add text
            text_label = QLabel(key.capitalize())   
            text_label.setObjectName(f"browser_menu_text_label_{key}")
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(text_label)

            # Create QWidgetAction and set the custom widget
            widget_action = QWidgetAction(self)
            widget_action.setDefaultWidget(widget)
            widget_action.setData((key, search_url))
            widget_action.triggered.connect(lambda checked, k=key: self.set_engine(k))
            self.browsermenu.addAction(widget_action)
            
        self.engine_btn.setMenu(self.browsermenu)
        self.engine_btn.setIcon(QIcon(str(icon_cache_dir / f"{self.engine}")))

        self.engine_btn.clicked.connect(lambda: self.current_browser.setUrl(QUrl(engines[self.engine].split('/search?q=')[0])))

        self.engine_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.nav_bar.addWidget(self.engine_btn)


        self.set_engine(self.engine)
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.load_url)
        self.nav_bar.addWidget(self.url_bar)

        self.current_browser.urlChanged.connect((lambda q: self.url_bar.setText(q.toString())))

        #Extensions Buttons
        #create button
        #on click button to open:         self.extman_instance.manager(), pull class from extensionmanager, list extensions, button to navigate to chrome web store, maybe one to open install location + autoloading??
        eColsButton.append("ext_btn")
        self.ext_btn = QToolButton(self)
        self.ext_btn.setText("ext_btn")
        self.ext_btn.setToolTip("See all extensions")
        self.ext_menu = QMenu(self)
        setattr(self, "ext_btn", self.ext_btn)

        self.ext_btn.setMenu(self.ext_menu)
        self.ext_btn.setIcon(get_normIcon("ext"))
        self.ext_menu.aboutToShow.connect(self.extensionmanagement)
        self.ext_btn.setPopupMode(QToolButton.InstantPopup)
        self.nav_bar.addWidget(self.ext_btn)


        #Cookie Menu GUI
        eColsButton.append("cookie_btn")
        self.cookie_btn = QToolButton(self)
        self.cookie_btn.setText("cookie_btn")
        self.cookie_btn.setToolTip("Accept/Deny Cookies")
        self.cookieMenu = QMenu(self)
        setattr(self, "cookie_btn", self.cookie_btn)

        self.cookie_btn.setMenu(self.cookieMenu)
        self.cookie_btn.setIcon(get_normIcon("cookie"))
        self.cookieMenu.aboutToShow.connect(self.cookieGUI)
        self.cookie_btn.setPopupMode(QToolButton.InstantPopup)
        self.nav_bar.addWidget(self.cookie_btn)










        #final reset to styling to skip default selection
        self.SelectColourTheme(self.selectedprofile, Colourdata)

        #Deploy js code when webpage starts
        EVAdInterceptor.deployPayload(browser=self.current_browser) #TODO: Script executes but doesn't actually work, research into that??? storage access permission denied
        #alternatively, just work on rudimentary adblock and suggest ublock; integrate chrome extensions store



    def ButtonConstructor(self, name, tooltip, icon, handler_name):
        """Creates all buttons for navbar"""
        btn = QToolButton(self)
        btn.setToolTip(tooltip)
        btn.setText(name)
        btn.setIcon(get_normIcon(icon))
        self.nav_bar.addWidget(btn)

        #Dynamically attach button to object data
        setattr(self, name, btn)

        #Connect to class method
        if hasattr(self, handler_name):
            btn.clicked.connect(getattr(self, handler_name))
        else:
            print(f"WARNING! Handler name {handler_name} not found")
        
        global eColsButton
        eColsButton.append(name)
        
        return btn

    #button assignment functions
    def go_back(self): self.current_browser.back()
    def reload_page(self): self.current_browser.reload()
    def go_forward(self): self.current_browser.forward()
    def go_home(self): self.current_browser.setUrl(QUrl.fromLocalFile(str(self.home_path)))
    def new_tab(self): self.add_new_tab(QUrl.fromLocalFile(str(self.home_path)), "Home")

    #reload icon animations
    def rotate_reload_icon(self):
        """Rotate the reload icon continuously"""
        self.rotation_angle = (self.rotation_angle + 10) % 360
        base_icon = get_normIcon("reload")
        pixmap = base_icon.pixmap(24, 24)
        
        transform = QTransform().rotate(self.rotation_angle)
        rotated_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        self.reload_btn.setIcon(QIcon(rotated_pixmap))
    
    def start_reload_animation(self):
        if not self.rotation_timer.isActive():
            self.rotation_timer.start(0.01)  # adjust speed here (ms per frame)
    
    def stop_reload_animation(self):
        if self.rotation_timer.isActive():
            self.rotation_timer.stop()
        # reset icon to upright
        self.rotation_angle = 0
        self.reload_btn.setIcon(get_normIcon("reload"))

    def current_browser(self):
        return self.tabs.currentWidget()

    def add_new_tab(self, qurl=engine, label="New Tab"):
        if qurl is None:
            qurl = QUrl("https://www.google.com")
        
        browser = QWebEngineView()
        new_page = QWebEnginePage(self.profile, browser)
        browser.setPage(new_page)
        browser.setUrl(qurl)
        self.current_browser = browser
        

        i = self.tabs.addTab(browser, label)

        self.tabs.setCurrentIndex(i)

        if hasattr(self, 'contrast_qcolor'):
            self.tabs.tabBar().setTabTextColor(i, self.contrast_qcolor)

        # Connect signals
        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_tab_title(browser))
        browser.loadStarted.connect(self.start_reload_animation)
        browser.loadFinished.connect(lambda ok, b=browser: (self.stop_reload_animation(), self.on_load_finished(browser)))
        browser.titleChanged.connect(lambda title, browser=browser: self.update_tab_title(browser, title))

        
        if qurl.toString().endswith("homepage.html"):
            self.url_bar.setText("Homepage")
        return browser
    
    def close_tab(self, index):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
        else:
            self.close()  # Exit if last tab closed

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

            if "https://chromewebstore.google.com/detail/" in title:
                print("THEYRE ON THE WEB STORE ENTRY GETTEM RAHHHHHHHHH")
                self.triggerExtensionsPopup(browser, browser.url().toString())
                

            self.tabs.setTabText(i, title)
            self.update_url_bar_buttons(browser.url().toString(), browser)
            
        pass

    def load_url(self):
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
    
    def set_engine(self, key):
        global engine
        engine = key
        self.engine = key
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
    
    def SelectColourTheme(self, profile, themes):
        self.tabs.setStyleSheet("")
        self.tabs.tabBar().setStyleSheet("")
        global eColsButton, eColsStyle
        self.selectedprofile = profile

        self.colourPalette_btn.setToolTip(f"Colour Palettes (currently {profile})")

        print(f"Colour Profile Switched to {profile}")

        datalist = list((themes[profile]).items())
        print(datalist)

        #adjust user profile colour selection
        with open (f"{self.main_path}/data/userData.json", "r") as f:
            dataedit = json.load(f)
        (dict(dataedit["mainUser"]))["ColourProfile"] = profile
        dataedit["mainUser"]["ColourProfile"] = profile
        with open (f"{self.main_path}/data/userData.json", "w") as f:
            json.dump(dataedit, f)
            

        #recolour icons
        tabcolour = "(255, 255, 255)" #white is default
        for k, v in datalist:
            if k in eColsButton:
                print(f"eColsButton: {k}")
                print(f"colourAdjust: {v}")
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
                        print(f"Adjusting colourPalette dropdown {self.hexval}, {self.rgb_tuple}, {self.light_rgb_tuple}")
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
                print(f"eColsStyle: {k}")
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

                    print(r, g, b)
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
        self.ColourMenu.setAttribute(Qt.WA_TranslucentBackground)
        self.browsermenu.setAttribute(Qt.WA_TranslucentBackground)

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
        
        for action in self.ColourMenu.actions():
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
            for action in self.browsermenu.actions():
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


        #run through key value pair and map to button name then swap rgb or hsv values
        print(f"button stuff: {eColsButton}")
        print(f"style stuff: {eColsStyle}")
        




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





    def PopupSystem(self, browser, title, message, buttons):
        overlay = Overlay(browser)
        overlay.show()

        dialogue = Dialog(browser)
        # Configure the buttons BEFORE calling exec()
        dialogue.outputPrompt(title, message, buttons)
        
        # exec() blocks here and returns the integer passed to done()
        result = dialogue.exec()

        overlay.deleteLater()
        return result
    

    def triggerExtensionsPopup(self, browser, url):
        # Define buttons and their unique return codes
        ext_selections = [("Download Now", QDialog.Accepted), ("No thanks", QDialog.Rejected)]
        
        res = self.PopupSystem(browser, "Extension Manager", "Download this extension to Midnight Watch?", ext_selections)
        
        if res == QDialog.Accepted:
            print("GET THE DOWNLOAD READY GOGOGOGO")
            self.extman_instance.installer(url, srcSourceDir)
        else:
            print("Download ignored by user.")
            pass

    def update_url_bar_buttons(self, url, browser):
        is_webstore = "https://chromewebstore.google.com/detail/" in url

        # Remove existing action
        if hasattr(self, 'reopen_button') and self.reopen_button is not None:
            self.url_bar.removeAction(self.reopen_button)
            self.reopen_button = None

        # Add only if on webstore
        if is_webstore:
            with open(f"{self.main_path}/data/colourProfiles.json", "r") as f:
                Colourdata = json.load(f)
                colour = Colourdata[self.selectedprofile]["ext_btn"]
            buttoncolourer("extdown_btn", colour)

            icon = get_normIcon("extdown")
            self.reopen_button = self.url_bar.addAction(icon, QLineEdit.TrailingPosition)
            self.reopen_button.setToolTip("Reopen Extension Prompt")
            self.reopen_button.triggered.connect(lambda: self.triggerExtensionsPopup(browser, url))
            self.url_bar.update()  


    def extensionmanagement(self):
        self.ext_menu.clear()
        json_path = Path(srcSourceDir) / "data/extensionList.json"

        if not json_path.exists():
            return

        with open(json_path, "r") as f:
            extensions_data = json.load(f)

        for ext_id, info in extensions_data.items():
            ext_path = Path(info["path"])
            if not ext_path.exists(): continue

            with open(ext_path / "manifest.json", "r") as m:
                manifest = json.load(m)

            ext_widget = QWidget()
            layout = QHBoxLayout(ext_widget)
            layout.setContentsMargins(5, 2, 5, 2)

            # Icon
            icon_label = QLabel()
            icons = manifest.get("icons", {})
            icon_file = icons.get("128") or icons.get("48") or icons.get("16")
            if icon_file:
                icon_label.setPixmap(QIcon(str(ext_path / icon_file)).pixmap(18, 18))
            layout.addWidget(icon_label)

            # Name
            name_label = QLabel(info.get("name", ext_id))
            name_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(name_label)
            layout.addStretch() # Pushes the checkbox to the right

            # Checkbox (The new toggle)
            check = QCheckBox()
            live_extensions = self.ext_manager.extensions()
            # Generator to find the match (handles the NoneType bug by checking 'ext is not None')
            live_ext = next((ext for ext in live_extensions if ext is not None and ext.extensionId() == ext_id), None)

            is_enabled = live_ext.isEnabled() if live_ext else info.get("enabled", True)
            check.setChecked(is_enabled)

            
            # Connect the toggle to both the engine and JSON persistence
            check.toggled.connect(lambda checked, eid=ext_id: self.toggle_extension(eid, checked, json_path))
            
            layout.addWidget(check)

            action = QWidgetAction(self.ext_menu)
            action.setDefaultWidget(ext_widget)
            self.ext_menu.addAction(action)


        pass
    

    def open_extension_options(self, ext_id):
        # Extension internal pages follow this URI scheme:
        options_url = f"chrome-extension://{ext_id}/manifest.json" 
        # Note: For uBlock, you might want to point to their actual dashboard:
        # f"chrome-extension://{ext_id}/dashboard.html"
        self.add_new_tab(QUrl(options_url), "Extension Settings")


    def toggle_extension(self, ext_id, checked, json_path):
        #using any reference to self.ext_manager.extensions() to track the list of active extensions triggers a bug in qt's C++ -> python wrapper
        #As a result, I'm making my own list in the active/inactive readings on extensionList.json()
        #SBKconverter issue for C++ to Python conversion is likely to be unpatched until the next release, which could be months, so I need to build this myself
        #update JSON Registry
        with open(json_path, "r") as f:
            data = json.load(f)
        
        if ext_id not in data: return
        data[ext_id]["enabled"] = checked
        
        with open(json_path, "w") as f:
            json.dump(data, f, indent=4)
        name = data[ext_id]["name"]
        
        #send engine commands
        if checked:
            # Re-loading the path "wakes up" the extension if it was soft-disabled
            self.ext_manager.loadExtension(data[ext_id]["path"])
            name = data[ext_id]["name"]
            QTimer.singleShot(500, lambda: self.finalise_permissions(ext_id, name))
            print(f"Sent LOAD command for: {ext_id}")
            
            try:
                ext_list = [ext for ext in self.ext_manager.extensions() if ext is not None]
                for ext in ext_list:
                    try:
                        ext_id_str = ext.extensionId()
                        print(f"Extension loaded: {ext_id_str}, enabled: {ext.isEnabled()}")
                        ext.setAllowedOnAnySite(True)
                    except Exception as e:
                        print(f"Warning: Could not process extension: {e}")
            except Exception as e:
                print(f"Warning: Could not enumerate extensions: {e}")
            
            print(f"Broad permissions granted for {name}")
        else:
            #set enabled to false in json then unload extension
            print(f"Extension {ext_id} marked as DISABLED in JSON.")
            try:
                ext_list = [ext for ext in self.ext_manager.extensions() if ext is not None]
                for ext in ext_list:
                    try:
                        if ext.extensionId() == ext_id:
                            self.ext_manager.unloadExtension(ext)
                            print(f"Successfully unloaded extension: {ext_id}")
                            break
                    except Exception as e:
                        print(f"Warning: Could not check extension ID: {e}")
            except Exception as e:
                print(f"Warning: Could not unload extension: {e}")

        #always need to reload the current page for uBlock to attach/detach scripts
        self.current_browser.reload() 

    def finalise_permissions(self, ext_id, name):
        selections = [("Accept", QDialog.Accepted), ("Deny", QDialog.Rejected)]
        selectaccess = self.PopupSystem(self.current_browser, "Extension Manager", f"Grant Javascript permissions to {name}?", selections)
        
        if selectaccess == QDialog.Accepted:
            try:
                ext_list = [ext for ext in self.ext_manager.extensions() if ext is not None]
                for ext in ext_list:
                    try:
                        ext_id_str = ext.extensionId()
                        print(f"Checking extension: {ext_id_str}")
                        if ext_id_str == ext_id:
                            ext.setAllowedOnAnySite(True)
                            print(f"Permissions granted for extension: {ext_id}")
                            return
                    except Exception as e:
                        print(f"Warning: Could not check extension: {e}")
                print(f"Extension {ext_id} not found in manager.")
            except Exception as e:
                print(f"Warning: Could not finalize permissions: {e}")
            return
        else:
            print(f"js access disabled for extension: {name}.")
            return

    def on_cookie_received(self, cookie):
        #these three aren't technically doing anything but they're good references for later
        name = cookie.name().data().decode(errors='ignore')
        domain = cookie.domain()
        value = cookie.value().data().decode()
        #actual logic - refresh cookie dictionary each time a new one is added
        cookiedict = self.cookieManager.on_cookie_added(cookie)
        self.cookiedict = cookiedict
    
    def cookieGUI(self):
        self.cookieMenu.clear()

        #Check if cookiedict exists to avoid crashes
        if not hasattr(self, 'cookiedict') or not self.cookiedict:
            self.cookieMenu.addAction("No cookies detected yet.")
            print("no cookies detected or error in loading")
            return
        
        for action in self.cookieMenu.actions():
            self.cookieMenu.removeAction(action)
            action.deleteLater()

        for cookieID, value in self.cookiedict.items():
            #Container widget for the row
            cookie_row = QWidget()
            layout = QHBoxLayout(cookie_row)
            layout.setContentsMargins(10, 2, 10, 2)
            layout.setSpacing(10)

            #Labels
            name_label = QLabel(value["name"])
            name_label.setMinimumWidth(100)
            predict_label = QLabel(f"({value['prediction']})")
            predict_label.setStyleSheet("color: gray; font-size: 10px;")
            
            layout.addWidget(name_label)
            layout.addWidget(predict_label)
            layout.addStretch() # Pushes buttons to the right

            #Action Buttons (Standard QPushButtons work better inside the row)
            btn_accept = QPushButton("✓")
            btn_accept.setFixedSize(24, 24)
            btn_accept.clicked.connect(lambda chk=False, id=cookieID: self.cookieManager.acceptCookie(id))

            btn_deny = QPushButton("✕")
            btn_deny.setFixedSize(24, 24)
            btn_deny.clicked.connect(lambda chk=False, id=cookieID: self.cookieManager.cookieEVAPORATOR(id))

            layout.addWidget(btn_accept)
            layout.addWidget(btn_deny)

            #QWidgetAction to host the row in the menu
            container_action = QWidgetAction(self.cookieMenu)
            container_action.setDefaultWidget(cookie_row)
            
            self.cookieMenu.addAction(container_action)
            self.cookieMenu.update()
            self.cookieMenu.repaint()




    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec())