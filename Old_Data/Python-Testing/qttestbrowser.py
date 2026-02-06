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

#CSS INJECTION AHAHAHAHA FUCK YOU DISCORD NITRO
'''
css_override = """
* {
    background-color: rgb(0, 0, 255) !important;
    background-image: none !important;
    color: white !important;
}
"""
'''

css_override = ""

inject_js = f"""
var style = document.createElement('style');
style.innerHTML = `{css_override}`;
document.head.appendChild(style);
"""



engines = {
    "ecosia": ("https://www.ecosia.org/search?q=", "https://www.ecosia.org/favicon.ico"),
    "google": ("https://www.google.com/search?q=", "https://www.google.com/favicon.ico"),
    "brave": ("https://search.brave.com/search?q=", "https://brave.com/favicon.ico"),
    "duckduckgo": ("https://duckduckgo.com/search?q=", "https://duckduckgo.com/favicon.ico")
}




#Icon cache 
icon_cache_dir = Path(__file__).parent / "icon_cache"
icon_cache_dir.mkdir(exist_ok=True)

#allow swappable colourtheme by updating an individual HSV value for each icon and storing them inside the colourProfiles.json file
#right click menu on icon -> HSV colourwheel?
#thus allow hotswappable pallets that can be custom designed and stored
#dynamically update each icon to the adjusted HSV value by using PIL image colour conversion and storing the new icons in an adjusted ico
#make sure swapping colour themes replaces the adjusted ico files - building up a cache for this is theoretically too storage intensive

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

#change this to change search browser for normal text entry. MAKE A DROPDOWN TO CHANGE THIS LATER
engine = engines['brave'][0]

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Midnight")
        self.resize(1200, 800)
        self.contextButtonSelected = None
        self.url_bar = QLineEdit()

        
        home_path = Path(__file__).parent / "homepage.html"
        self.tabs  = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.switch_tab)
        self.setCentralWidget(self.tabs)
        self.add_new_tab(QUrl.fromLocalFile(str(home_path)), "Home")


        nav_bar = QToolBar("Navigation")
        self.addToolBar(nav_bar)
        nav_bar.setMovable(False)
        nav_bar.setStyleSheet("background:rgb(1, 1, 100)")


        back_btn = QToolButton(self)
        back_btn.clicked.connect(self.current_browser.back)
        nav_bar.addWidget(back_btn)
        back_btn.setIcon(get_normIcon("back_button", inv))
        back_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        back_btn.customContextMenuRequested.connect(lambda pos, b=back_btn: self.show_icon_menu(b, pos))


        forward_btn = QToolButton(self)
        forward_btn.clicked.connect(self.current_browser.forward)
        nav_bar.addWidget(forward_btn)
        forward_btn.setIcon(get_normIcon("forward_button", inv))

        self.reload_btn = QToolButton(self)
        self.reload_btn.setIcon(get_normIcon("reload", inv))
        self.reload_btn.clicked.connect(self.current_browser.reload)
        nav_bar.addWidget(self.reload_btn)
        self.rotation_angle = 0
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_reload_icon)
        
        # Connect start/stop signals
        self.current_browser.loadStarted.connect(self.start_reload_animation)
        self.current_browser.loadFinished.connect(self.stop_reload_animation)
        

        home_btn = QAction("Home", self)
        home_btn.triggered.connect(lambda: self.current_browser.setUrl(QUrl.fromLocalFile(str(home_path))))
        nav_bar.addAction(home_btn)
        home_btn.setIcon(get_normIcon("home", inv))


        self.newtab_btn = QToolButton(self)
        self.newtab_btn.setIcon(get_normIcon("newtab", inv))
        self.newtab_btn.clicked.connect(lambda: self.add_new_tab(QUrl.fromLocalFile(str(home_path)), "Home"), "New Tab")
        nav_bar.addWidget(self.newtab_btn)


        
        self.colourTheme_btn = QToolButton(self)
        self.colourTheme_btn.setText("Colours")
        self.colourTheme_btn.setIcon(get_normIcon("colourPallete", inv))

        #this isn't working for some reason. It just shows the button, no dropdown menu. Loads json data correctly but nothing else
        Cmenu = QMenu(self)
        with open (f"{Path(__file__).parent}/colourProfiles.json", 'r') as datafile:
            colourPalletes = json.load(datafile)
        for Name, data in colourPalletes.items():
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(5, 2, 5, 2)
            layout.setSpacing(5)

            text_label = QLabel(Name.capitalize())
            layout.addWidget(text_label)

            Cwidget_action = QWidgetAction(self)
            Cwidget_action.setDefaultWidget(widget)
            Cwidget_action.setData((Name, data))
            Cwidget_action.triggered.connect(lambda checked, N = Name, d = data: self.setColourPallete(N, d))
            Cmenu.addAction(Cwidget_action)
        
        self.colourTheme_btn.setMenu(Cmenu)
        self.colourTheme_btn.setPopupMode(QToolButton.InstantPopup)
        initial_pallette = [k for k, v in colourPalletes.items() if k[0] == inv]
        nav_bar.addWidget(self.colourTheme_btn)



        
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
        nav_bar.addWidget(self.engine_btn)


        self.set_engine([k for k,v in engines.items() if v[0]==self.engine][0], self.engine)
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.load_url)
        nav_bar.addWidget(self.url_bar)

        self.current_browser.urlChanged.connect((lambda q: self.url_bar.setText(q.toString())))

    def show_icon_menu(self, button, pos):
        menu = QMenu(self)

        colour_menu = QMenu("Colour", self)
        menu.addMenu(colour_menu)

        self.contextButtonSelected = button
        
        # simple preset colours
        for name, rgb in [("Blue", (0, 0, 255)), ("Red", (255, 0, 0)), ("Green", (0, 255, 0))]:
            act = QAction(name, self)
            act.triggered.connect(lambda checked=False, btn=button, c=rgb: self.setButtonColour(btn, c))
            colour_menu.addAction(act)

        # colour wheel (QColorDialog)
        custom = QAction("Custom...", self)
        self.contextButtonSelected = button
        custom.triggered.connect(self.pick_button_colour)
        colour_menu.addAction(custom)

        menu.exec(button.mapToGlobal(pos))


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
        browser.setContextMenuPolicy(Qt.CustomContextMenu)
        browser.customContextMenuRequested.connect(self.RCContextMenu) #set connect value once main function is done

        i = self.tabs.addTab(browser, label)
        self.tabs.setStyleSheet("QTabBar::tab { height: 30px; width: 150px;}")
        self.tabs.setCurrentIndex(i)

        # Connect signals
        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_tab_title(browser))
        browser.loadStarted.connect(self.start_reload_animation)
        browser.loadFinished.connect(lambda ok, b=browser: (self.stop_reload_animation(), self.on_load_finished()))
        browser.titleChanged.connect(lambda title, browser=browser: self.update_tab_title(browser, title))

        
        if qurl.toString().endswith("homepage.html"):
            self.url_bar.setText("")
        return browser
    
    def RCContextMenu(self, pos):
        view = self.current_browser
        menu = QMenu(self)

        #default buttons
        menu.addAction(view.pageAction(QWebEnginePage.Back))
        menu.addAction(view.pageAction(QWebEnginePage.Forward))
        menu.addAction(view.pageAction(QWebEnginePage.Reload))
        menu.addAction(view.pageAction(QWebEnginePage.SavePage))
        menu.addSeparator()

        #Main colourmenu
        colourmenu = QMenu("Colours", self)
        menu.addMenu(colourmenu)

        for name, rgb in [("Blue", (0, 0, 255)), ("Red", (255, 0, 0)), ("Green", (0, 255, 0))]:
            act = QAction(name, self)
            act.triggered.connect(lambda checked=False, c=rgb: self.setPageColour(c))
            colourmenu.addAction(act)

        custom_act = QAction("Custom…", self)
        custom_act.triggered.connect(self.pick_page_colour)
        colourmenu.addAction(custom_act)

        # important: map pos to global coordinates relative to the web view
        menu.exec(view.mapToGlobal(pos))


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

    def update_tab_title(self, browser, title=None):
        i = self.tabs.indexOf(browser)
        if i != -1:
            # Use provided title or fallback
            if not title:
                title = browser.url().toString()

            # Clean it up a bit for display
            if len(title) > 60:
                title = title[:57] + "..."
            
            if title == 'homepage.html':
                title = 'Home'

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
    
    def set_engine(self, key, value):
        global engine
        self.engine = value
        engine = value
        self.engine_btn.setText(key.capitalize())
        self.engine_btn.setToolTip(value)
        self.engine_btn.setIcon(get_favicon(key, engines[key][1]))
    
    def handle_load_finished(self, browser, ok):
        self.stop_reload_animation()
        self.on_load_finished()

    def on_load_finished(self):
        self.current_browser.page().runJavaScript(inject_js)

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        colour_menu = QMenu("Colour", self)
        menu.addMenu(colour_menu)

        # Predefined palette choices
        for name, rgb in [("Blue", (0,0,255)), ("Red", (255,0,0)), ("Green", (0,255,0))]:
            action = QAction(name, self)
            action.triggered.connect(lambda checked=False, b = self.contextButtonSelected, c=rgb: self.setButtonColour(b, c))
            colour_menu.addAction(action)

        # A custom colour chooser (the “wheel”)
        custom_action = QAction("Custom…", self)
        custom_action.triggered.connect(self.pick_button_colour)
        colour_menu.addAction(custom_action)

        menu.exec(event.globalPos())

    def pick_button_colour(self):
        button = self.contextButtonSelected
        colour = QColorDialog.getColor()
        if colour.isValid():
            rgb = (colour.red(), colour.green(), colour.blue())
            self.setButtonColour(button, rgb)


    def setButtonColour(self, button, rgb):
        print(button)
        print(self.contextButtonSelected)
        #recolour logic
        print(f"Recoloring {button} with {rgb}")
        pass

    def pick_page_colour(self):
        colour = QColorDialog.getColor()
        if colour.isValid():
            self.setPageColour((colour.red(), colour.green(), colour.blue()))
        

    def setPageColour(self, rgb):
        js = f"""
            document.body.style.backgroundColor = 'rgb({rgb[0]}, {rgb[1]}, {rgb[2]})';
            document.body.style.backgroundImage = 'none';
        """
        self.current_browser.page().runJavaScript(js)

    def setColourPallete(self, Name, data):
        pass


if __name__ == "__main__":#
    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec())
