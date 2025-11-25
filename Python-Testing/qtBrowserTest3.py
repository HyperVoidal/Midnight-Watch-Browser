import sys
from PySide6.QtCore import QUrl 
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtCore import *
from PySide6.QtGui import *
from urllib.parse import urlparse
from pathlib import Path
import urllib.request
import os
from PIL import Image, ImageOps
import json


#Icon cache 
icon_cache_dir = Path(__file__).parent / "icon_cache"
icon_cache_dir.mkdir(exist_ok=True)

inv = True

#pull icons and insert into cache
def get_favicon(name, favicon_url):
    """Download and cache favicon, return QIcon"""
    icon_path = icon_cache_dir / f"{name}.ico"
    
    # Download icon if not cached
    if not icon_path.exists():
        try:
            urllib.request.urlretrieve(favicon_url, icon_path)
        except:
            return QIcon()  # Return empty icon if download fails
            
    return QIcon(str(icon_path))

def get_normIcon(name, inv):
    if inv == True:
        icon_path = icon_cache_dir / f"inv_{name}.ico"
    else:
        icon_path = icon_cache_dir / f"{name}.ico"

    return QIcon(str(icon_path))

engines = {
    "ecosia": ("https://www.ecosia.org/search?q=", "https://www.ecosia.org/favicon.ico"),
    "google": ("https://www.google.com/search?udm=14&q=", "https://www.google.com/favicon.ico"),
    "brave": ("https://search.brave.com/search?q=", "https://brave.com/favicon.ico"),
    "duckduckgo": ("https://duckduckgo.com/search?q=", "https://duckduckgo.com/favicon.ico")
}

#starter engine
engine = engines['brave'][0]

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Midnight Engine")
        self.resize(1200, 800)
        self.url_bar = QLineEdit()

        self.main_path = Path(__file__).parent
        self.home_path = self.main_path / "homepage.html"
        self.tabs  = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.switch_tab)
        self.setCentralWidget(self.tabs)
        self.add_new_tab(QUrl.fromLocalFile(str(self.home_path)), "Home")

        self.SelectedColourProfile = "profile1" #handle this more elegantly at some point

        self.nav_bar = QToolBar("Navigation")
        self.addToolBar(self.nav_bar)
        self.nav_bar.setMovable(False)
        self.nav_bar.setStyleSheet("background:rgb(1, 1, 100)")
        

        #buttons

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
        self.ColourPalette_btn = QToolButton(self)
        self.ColourPalette_btn.setToolTip("Colour Palettes")
        ColourMenu = QMenu(self)

        with open (f"{self.main_path}/colourProfiles.json", "r") as f:
            Colourdata = dict(json.load(f))
        
        for profile in range(len(Colourdata)):
            dictions = [[k,v] for k,v in Colourdata.items()]
            self.selectedprofile = str(dictions[profile][0])
            # Widgets for Menu Items
            Cwidget = QWidget()
            Clayout = QHBoxLayout(Cwidget)
            Clayout.setContentsMargins(5, 2, 5, 2)
            Clayout.setSpacing(5)

            #Add text
            Ctext_label = QLabel(self.selectedprofile.capitalize())
            Clayout.addWidget(Ctext_label)

            #Create Widget Action
            Cwidget_action = QWidgetAction(self)
            Cwidget_action.setDefaultWidget(Cwidget)
            Cwidget_action.setData((self.selectedprofile))
            Cwidget_action.triggered.connect(lambda checked, p=self.selectedprofile, d=Colourdata: self.SelectColourTheme(p, d))
            ColourMenu.addAction(Cwidget_action)
        
        self.ColourPalette_btn.setMenu(ColourMenu)
        self.ColourPalette_btn.setIcon(get_normIcon("colourPalette", inv))

        self.ColourPalette_btn.clicked.connect(lambda checked, p=self.selectedprofile, d=Colourdata: self.ToggleColourTheme(p, d))

        self.ColourPalette_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.nav_bar.addWidget(self.ColourPalette_btn)
        #define starter profile
        self.selectedprofile = 'profile1'


        #engine system
        self.engine = engine
        self.engine_btn = QToolButton(self)
        self.engine_btn.setText("Search With...")
        menu = QMenu(self)

        for key, (search_url, favicon_url) in engines.items():
            # Create widget for menu item
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(5, 2, 5, 2)
            layout.setSpacing(5)
            
            # Add icon
            icon_label = QLabel()
            icon = get_favicon(key, favicon_url)
            icon_label.setPixmap(icon.pixmap(16, 16))
            layout.addWidget(icon_label)
            
            # Add text
            text_label = QLabel(key.capitalize())
            layout.addWidget(text_label)
            
            # Create QWidgetAction and set the custom widget
            widget_action = QWidgetAction(self)
            widget_action.setDefaultWidget(widget)
            widget_action.setData((key, search_url))
            widget_action.triggered.connect(lambda checked, v=search_url, k=key: self.set_engine(k, v))
            menu.addAction(widget_action)
            
        self.engine_btn.setMenu(menu)

        initial_engine = [k for k,v in engines.items() if v[0]==self.engine][0]
        self.engine_btn.setIcon(get_favicon(initial_engine, engines[initial_engine][1]))

        self.engine_btn.clicked.connect(lambda: self.current_browser.setUrl(QUrl(self.engine.split('/search?q=')[0])))

        self.engine_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.nav_bar.addWidget(self.engine_btn)


        self.set_engine([k for k,v in engines.items() if v[0]==self.engine][0], self.engine)
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.load_url)
        self.nav_bar.addWidget(self.url_bar)

        self.current_browser.urlChanged.connect((lambda q: self.url_bar.setText(q.toString())))

    def ButtonConstructor(self, name, tooltip, icon, handler_name):
        """Creates all buttons for navbar"""
        btn = QToolButton(self)
        btn.setToolTip(tooltip)
        btn.setIcon(get_normIcon(icon, inv))
        self.nav_bar.addWidget(btn)

        #Dynamically attach button to object data
        setattr(self, name, btn)

        #Connect to class method
        if hasattr(self, handler_name):
            btn.clicked.connect(getattr(self, handler_name))
        else:
            print(f"WARNING! Handler name {handler_name} not found")
        
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
        base_icon = get_normIcon("reload", inv)
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
        self.reload_btn.setIcon(get_normIcon("reload", inv))

    def current_browser(self):
        return self.tabs.currentWidget()

    def add_new_tab(self, qurl=engine, label="New Tab"):
        if qurl is None:
            qurl = QUrl("https://www.google.com")
        
        browser = QWebEngineView()
        browser.setUrl(qurl)

        i = self.tabs.addTab(browser, label)
        self.tabs.setStyleSheet("QTabBar::tab { height: 30px; width: 150px;}")
        self.tabs.setCurrentIndex(i)

        # Connect signals
        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_tab_title(browser))
        browser.loadStarted.connect(self.start_reload_animation)
        browser.loadFinished.connect(lambda ok, b=browser: (self.stop_reload_animation(), self.on_load_finished()))
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

            self.tabs.setTabText(i, title)

    def load_url(self):
        url = self.url_bar.text()
        urlparsed = urlparse(url)
        if urlparsed.scheme and urlparsed.netloc:
            print(urlparsed)
            fullurl = url
            pass
        else:
            wordlist = url.split(" ")
            joiner = "+"
            texturlcomp = joiner.join(wordlist)
            fullurl = engine + texturlcomp
            print(fullurl)
        
        self.current_browser.setUrl(QUrl(fullurl))
    
    def on_load_finished(self):
        pass
    
    def set_engine(self, key, value):
        global engine
        self.engine = value
        engine = value
        self.engine_btn.setText(key.capitalize())
        self.engine_btn.setToolTip(value)
        self.engine_btn.setIcon(get_favicon(key, engines[key][1]))
    
    def SelectColourTheme(self, profile, themes):
        components = dict(themes[profile])
        print(components)

        pass

    def ToggleColourTheme(self, profile, themes):
        print(profile)
        pass

    

    #system for when I implement the main colourtheme editor
    def ColourThemeEditor(self):
        pass
    
if __name__ == "__main__":#
    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec())
