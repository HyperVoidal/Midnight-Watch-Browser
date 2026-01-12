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


def get_normIcon(name):
    icon_path = icon_cache_dir / f"{name}"

    return QIcon(str(icon_path))

engines = {
    "ecosia": "https://www.ecosia.org/search?q=",
    "google": "https://www.google.com/search?udm=14&q=",
    "brave": "https://search.brave.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/search?q="
}

#starter engine
engine = 'brave'

#setText names
global eColsButton, eColsStyle
eColsButton = []
eColsStyle = []

def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))
 
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
        global eColsButtons
        self.url_bar = QLineEdit()
        eColsStyle.append("url_bar")
        self.user = "mainUser" #make a system for this at some point!!!

        self.main_path = Path(__file__).parent
        self.home_path = self.main_path / "homepage.html"
        self.tabs  = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.switch_tab)
        eColsStyle.append("tabs")
        self.setCentralWidget(self.tabs)
        self.add_new_tab(QUrl.fromLocalFile(str(self.home_path)), "Home")

        self.nav_bar = QToolBar("Navigation")
        self.addToolBar(self.nav_bar)
        self.nav_bar.setMovable(False)
        self.nav_bar.setStyleSheet("background:rgb(1, 1, 100)")
        eColsStyle.append("nav_bar")

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
            Ctext_label.setStyleSheet("text-align:center")#fix this????
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
            
            # Add text
            text_label = QLabel(key.capitalize())   
            text_label.setObjectName(f"browser_menu_text_label_{key}")
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

        #final reset to styling to skip default selection
        self.SelectColourTheme(self.selectedprofile, Colourdata)

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
            fullurl = engines[engine] + texturlcomp
            print(fullurl)
        
        self.current_browser.setUrl(QUrl(fullurl))

    def on_load_finished(self):
        pass
    
    def set_engine(self, key):
        global engine
        engine = key
        self.engine = key
        self.engine_btn.setText(key.capitalize())
        self.engine_btn.setToolTip(key)
        self.engine_btn.setIcon(QIcon(str(icon_cache_dir / f"{key}")))
    
    def SelectColourTheme(self, profile, themes):
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
                    obj.setStyleSheet(f"background:rgb{v}")
                #adjust stylesheet to v colour by setting the stylesheet of self.{k} to the rgb value of {v}
                pass
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
    

    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec())
