import json
from pathlib import Path
import requests
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from functools import partial
from cookieManager import CookieManager




icon_cache_dir = Path(__file__).parent / "ui/icon_cache"
icon_cache_dir.mkdir(exist_ok=True)

srcSourceDir =  Path(__file__).parent

def loadActionToggles():
    with open (srcSourceDir / "data/actionToggles.json", "r") as f:
                actionToggles = json.load(f)
    return actionToggles

def get_normIcon(name):
    icon_path = icon_cache_dir / f"{name}"

    return QIcon(str(icon_path))



class additionalUIElements:
    def __init__(self, parent):
        self.parent = parent
        

    def WindowConfirmation(self, title, message, num=2):
        parent=None
        if isinstance(self.parent,QWidget):
            parent=self.parent
        elif hasattr(self.parent,"view"):
            parent=self.parent.view()

        msg_box=QMessageBox(parent)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Question)

        if num==1:
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes)
            yes_button=msg_box.button(QMessageBox.StandardButton.Yes)
            yes_button.setText("Okay")
            msg_box.exec()
            return (msg_box.clickedButton() == yes_button)

        elif num==2:
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.exec()
            return (msg_box.clickedButton() == msg_box.button(QMessageBox.StandardButton.Yes))
        

    def WindowInput(self, title, message, default_text=""):
        text, ok = QInputDialog.getText(
            self.parent,
            title,
            message,
            QLineEdit.EchoMode.Normal,
            default_text
        )
        if ok and text.strip():
            return text.strip()
        return None
    

class NewProfileDialog(QDialog):
    def __init__(self, parent=None, title="Create New Profile", placeholder="Enter profile name...", image=None, image_text="Profile Image:"):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(400, 220)

        self.image_path = ""

        layout = QVBoxLayout(self)

        # ----- Name -----
        layout.addWidget(QLabel("Profile Name:"))

        self.nameInput = QLineEdit()
        self.nameInput.setPlaceholderText(placeholder)
        layout.addWidget(self.nameInput)

        # ----- Image Selection -----
        layout.addWidget(QLabel(image_text))

        imgLayout = QHBoxLayout()

        self.imagePreview = QLabel()
        self.imagePreview.setFixedSize(64,64)
        self.imagePreview.setStyleSheet("""
            border: 1px solid gray;
            background: transparent;
        """)
        self.imagePreview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if image:
            self.image_path = image

            pixmap = QPixmap(image)
            pixmap = pixmap.scaled(
                64,64,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            self.imagePreview.setPixmap(pixmap)

        self.browseButton = QPushButton("Browse...")
        self.browseButton.clicked.connect(self.selectImage)

        imgLayout.addWidget(self.imagePreview)
        imgLayout.addWidget(self.browseButton)

        layout.addLayout(imgLayout)

        # ----- OK / Cancel -----
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def selectImage(self):

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Profile Image",
            f"{srcSourceDir}/ui/images",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if filepath:
            self.image_path = filepath

            pixmap = QPixmap(filepath)
            pixmap = pixmap.scaled(64,64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            self.imagePreview.setPixmap(pixmap)

    def getData(self):
        return {
            "name": self.nameInput.text().strip(),
            "photoURL": self.image_path
        }
    

class EmergencyOverlay(QWidget):
    # Signal emitted when the action button is clicked
    reboot_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #0d0d0d;
                color: #f0f0f0;
            }
            QLabel#OverlayTitle {
                font-size: 24px;
                font-weight: bold;
                color: #ff4d4d;
                margin-bottom: 10px;
                background: transparent;
            }
            QLabel#OverlayText {
                font-size: 14px;
                color: #cccccc;
                background: transparent;
            }
            QPushButton#RebootButton {
                background-color: #ff4d4d;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#RebootButton:hover {
                background-color: #e63939;
            }
            QPushButton#RebootButton:pressed {
                background-color: #cc2929;
            }
        """)

        # Set up the layout
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Create UI elements with specific object names for the CSS
        self.title_label = QLabel()
        self.title_label.setObjectName("OverlayTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #self.title_label.setWordWrap(True)

        self.text_label = QLabel()
        self.text_label.setObjectName("OverlayText")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #self.text_label.setWordWrap(True)

        self.reboot_btn = QPushButton("Reboot Browser")
        self.reboot_btn.setObjectName("RebootButton")
        self.reboot_btn.setFixedSize(220, 45)
        self.reboot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        

        # Connect the button click to out-of-file backend emitters
        self.reboot_btn.clicked.connect(self.reboot_requested.emit)

        self.title_label.setAlignment(Qt.AlignHCenter)
        self.text_label.setAlignment(Qt.AlignHCenter)
        self.text_label.adjustSize()


        # Assemble UI tree
        layout.addWidget(self.title_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.reboot_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_content(self, title, text):
        """Updates the labels dynamically when an error matches."""
        self.title_label.setText(title)
        self.text_label.setText(text)

class BarManager:

    def __init__(self, parent, eColsStyle, eColsButton):
        self.parent = parent
        self.eColsStyle = eColsStyle
        self.eColsButton = eColsButton

        
        

    def setup_url_bar(self):
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.parent.load_url)
        self.url_bar.focusInEvent = self.parent._url_bar_focus_in
        self.parent.nav_bar.addWidget(self.url_bar)
        self.eColsStyle.append("url_bar")

        self.url_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.url_bar.customContextMenuRequested.connect(self.parent.displayUrlBarContextMenu)
        return self.url_bar


    def setup_tabs(self):
        actionToggles = self.parent.settingsData
        if actionToggles["Tab-Position"] in ["North", "South"]:
            self.tabs = QTabWidget()
            self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
            self.tabs.tabBar().setExpanding(True)

        elif actionToggles["Tab-Position"] in ["East", "West"]:
            self.tabs = QTabWidget()
            self.tabs.setTabBar(VerticalTabBar())
            self.tabs.tabBar().setExpanding(False)
            self.tabs.tabBar().setElideMode(Qt.ElideNone)
            self.eColsButton.append("pintabs_btn")


        else:
            print("tab position loading error, defaulting to north")
            self.tabs = QTabWidget()
            self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
            self.tabs.tabBar().setExpanding(True)

        self.eColsStyle.append("tabs")
        self.eColsStyle.append("tab_backer")
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setStyleSheet("""QTabBar::tab {
                                                height: 35px;
                                                width: 200px;
                                            }
                                            """)
                                         
        self.tabs.tabBar().setUsesScrollButtons(True)
        return self.tabs
    

    def setup_navbar(self):
        self.nav_bar = QToolBar("Navigation")
        self.nav_bar.setMovable(False)
        self.nav_bar.setStyleSheet("background:rgb(1, 1, 100)")
        self.eColsStyle.append("nav_bar")


        #main button constructors
        self.ButtonConstructor("back_btn", "Back", "back", "go_back")
        self.ButtonConstructor("reload_btn", "Reload", "reload", "reload_tab")
        self.ButtonConstructor("forward_btn", "Forward", "forward", "go_forward")
        self.ButtonConstructor("home_btn", "Home", "home", "go_home")
        self.ButtonConstructor("newtab_btn", "New Tab", "newtab", "new_tab")
        self.ButtonConstructor("settings_btn", "Settings", "settings", "open_settings_menu")

        #reload animation components
        self.rotation_angle = 0
        self.parent.rotation_timer = QTimer()
        self.parent.rotation_timer.timeout.connect(self.rotate_reload_icon)
        self.parent.current_browser.loadStarted.connect(self.start_reload_animation)
        self.parent.current_browser.loadFinished.connect(self.stop_reload_animation)


        return self.nav_bar

    def setup_statusbar(self, profile_icon=None, name=None):
        self.status_bar = QToolBar("Status")
        self.status_bar.setMovable(False)

        self.status_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.status_bar.customContextMenuRequested.connect(lambda pos: self.parent.displayStatusBarContextMenu(pos, self.status_bar, "Status Bar"))

        self.eColsStyle.append("status_bar")

        #spacer widget
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        #controls the date display
        self.dateBox = QLineEdit()
        self.dateBox.setReadOnly(True)
        self.dateBox.setPlaceholderText("...")
        self.dateBox.setMaximumWidth(300)
        
        #controls the time display
        self.timeBox = QLineEdit()
        self.timeBox.setReadOnly(True)
        self.timeBox.setPlaceholderText("...")
        self.timeBox.setMaximumWidth(150)

        #controls the zoom display and slider
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(0)
        self.zoom_slider.setMaximum(300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(self.status_bar.width() // 3)
        self.zoom_slider.sliderMoved.connect(self.on_zoom_slider_moved)

        #dispay based on current zoom value, press to return to 100% exactly
        self.zoomDisplay = QPushButton("100%")
        self.zoomDisplay.clicked.connect(lambda: self.zoom_slider.setValue(100))
        self.zoom_slider.valueChanged.connect(lambda value: (self.zoomDisplay.setText(f"{value}%"), self.on_zoom_slider_moved(value)))

        self.zoomDisplay.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.zoomDisplay.customContextMenuRequested.connect(lambda pos: self.parent.displayStatusBarContextMenu(pos, self.zoomDisplay, "zoomDisplay"))

        self.profileDisplay = QPushButton(name if name else "Ephemeral")
        if profile_icon:
            try:
                print(f"Loading profile icon from: {profile_icon}")
                image = QImage()
                if image.load(str(profile_icon)):
                    pixmap = QPixmap.fromImage(image)
                    self.profileDisplay.setIcon(QIcon(pixmap))
                    self.profileDisplay.setIconSize(QSize(16, 16))
                else:
                    print(f"Failed to load image from: {profile_icon}")
            except Exception as e:
                print(f"Error loading profile icon: {e}")
        #is there a way to make this reopen the profile selection menu?
        self.profileDisplay.clicked.connect(self.parent.open_profile_menu)

        self.profileDisplay.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.profileDisplay.customContextMenuRequested.connect(lambda pos: self.parent.displayStatusBarContextMenu(pos, self.profileDisplay, "profileDisplay"))



        #sets the displays to the bar
        self.status_bar.addWidget(self.profileDisplay)
        self.status_bar.addWidget(self.zoom_slider)
        self.status_bar.addWidget(self.zoomDisplay)
        self.status_bar.addWidget(spacer)
        self.status_bar.addWidget(self.timeBox)
        self.status_bar.addWidget(self.dateBox)


        #runs the update timer
        self.barUpdateTimer = QTimer(self.parent)
        self.barUpdateTimer.timeout.connect(self.updateStatusBar)
        self.barUpdateTimer.start(1000)

        return self.status_bar
    
    def on_zoom_slider_moved(self, value):
        self.parent.tab_zoom_values[self.parent.current_browser] = value
        self.parent.zoomValue = value
        self.parent.current_browser.setZoomFactor(value / 100)
        self.zoomDisplay.setText(f"{value}%")

    def updateStatusBar(self):
        settingsDataPull = self.parent.settingsData
        
        #time return - pulls from same system as new tab window display
        timeFormat = (settingsDataPull["Time-Display"])
        timeCall = QDateTime.currentDateTime()
        time_text = timeCall.toString(f"{timeFormat}")
        self.timeBox.setText(time_text)
        time_metrics = QFontMetrics(self.timeBox.font())
        time_width = time_metrics.horizontalAdvance(time_text) + 16
        self.timeBox.setFixedWidth(time_width)



        #date return - pulls from same system as new tab window display
        date_format, provide_year = settingsDataPull["Date-Display"][0], settingsDataPull["Date-Display"][1]
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
        date_text = dateCall.toString(date_format)
        self.dateBox.setText(date_text)
        date_metrics = QFontMetrics(self.dateBox.font())
        date_width = date_metrics.horizontalAdvance(date_text) + 16
        self.dateBox.setFixedWidth(date_width)
    
    def setup_bookmarksbar(self, bookmarksData):
        self.bookmarks_bar = QToolBar("Bookmarks")
        self.bookmarks_bar.setMovable(False)
        self.bookmarks_bar.setStyleSheet("background:rgb(1, 1, 100)")
        self.eColsStyle.append("bookmarks_bar")
        self.eColsButton.append("bookmarks_btn")

        try:
            bookmarkData = bookmarksData
            
            for bid, data in bookmarkData.items():
                name = data["name"]
                url = data["url"]
                Bbutton = QPushButton(name.capitalize())

                FAVurl = f"https://www.google.com/s2/favicons?domain={QUrl(url).host()}&sz=32"
                response = requests.get(FAVurl)
                if response.status_code == 200: 
                    image = QImage()
                    image.loadFromData(response.content)
                    pixmap = QPixmap.fromImage(image)
                else:
                    #use image for tabIcon.png
                    pixmap = QPixmap(str(icon_cache_dir / "tabIcon.png"))

                Bbutton.setIcon(QIcon(pixmap))
                Bbutton.setIconSize(QSize(16, 16))
                Bbutton.clicked.connect(partial(self.parent.load_url, qurl=url, label=name))
                Bbutton_action = QWidgetAction(self.parent)
                Bbutton_action.setDefaultWidget(Bbutton)

                #Right click context menu 
                Bbutton.setContextMenuPolicy(Qt.CustomContextMenu)
                Bbutton.customContextMenuRequested.connect(partial(self.parent.displayBookmarksContextMenu, Bbutton, bid, bookmarkData))

                self.bookmarks_bar.addAction(Bbutton_action)

        except json.decoder.JSONDecodeError:
            print("No bookmarks saved, skipping.")

        return self.bookmarks_bar
    

    def refresh_bookmarksbar(self, bookmarksData):
        self.bookmarks_bar.clear()
        try:
            bookmarkData = bookmarksData
            for bid, data in bookmarkData.items():
                name = data["name"]
                url = data["url"]
                btn = QPushButton(name.capitalize())

                try:
                    domain = QUrl(url).host()
                    icon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
                    response = requests.get(icon_url, timeout=5)

                    if response.status_code == 200:
                        image = QImage()
                        image.loadFromData(response.content)
                        pixmap = QPixmap.fromImage(image)
                    else:
                        pixmap = QPixmap(str(icon_cache_dir / "tabIcon.png"))

                except:
                    pixmap = QPixmap(str(icon_cache_dir / "tabIcon.png"))

                btn.setIcon(QIcon(pixmap))
                btn.setIconSize(QSize(16, 16))

                btn.clicked.connect(
                    lambda checked, t=url, l=name: self.parent.add_new_tab(qurl=t, label=l)
                )

                action = QWidgetAction(self.parent)
                action.setDefaultWidget(btn)
                self.bookmarks_bar.addAction(action)

            #link to right click context menu after refreshing
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(partial(self.show_bookmark_menu, btn, bid, bookmarkData))
        except (json.decoder.JSONDecodeError, UnboundLocalError):
            print("Can't refresh bookmarks as none exist in the json file!")
            pass
    
    
    def setupContextMenu(self):
        # Parent it to the main window/browser class
        RContextMenu = QMenu(self.parent)

        # Default button actions
        backClick = QAction("Go Back", self.parent)
        backClick.triggered.connect(self.parent.go_back)
        RContextMenu.addAction(backClick)

        forwardClick = QAction("Go Forward", self.parent)
        forwardClick.triggered.connect(self.parent.go_forward)
        RContextMenu.addAction(forwardClick)

        reloadClick = QAction("Reload Page", self.parent)
        reloadClick.triggered.connect(self.parent.reload_tab)
        RContextMenu.addAction(reloadClick)

        return RContextMenu


    def ButtonConstructor(self, name, tooltip, icon, handler_name):
        """Creates all buttons for navbar"""
        btn = QToolButton(self.parent)
        btn.setToolTip(tooltip)
        btn.setText(name)
        btn.setIcon(get_normIcon(icon))
        self.nav_bar.addWidget(btn)

        #Dynamically attach button to object data
        setattr(self.parent, name, btn)

        #Connect to class method
        if hasattr(self.parent, handler_name):
            btn.clicked.connect(getattr(self.parent, handler_name))
        else:
            print(f"WARNING! Handler name {handler_name} not found")
        
        self.eColsButton.append(name)

        btn.setContextMenuPolicy(Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, b=btn: self.parent.displayContextMenu(pos, b))

        
        return btn
    
    #reload icon animations
    def rotate_reload_icon(self):
        """Rotate the reload icon continuously"""
        self.rotation_angle = (self.rotation_angle + 10) % 720
        base_icon = get_normIcon("reload")
        pixmap = base_icon.pixmap(24, 24)
        
        transform = QTransform().rotate(self.rotation_angle)
        rotated_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        self.parent.reload_btn.setIcon(QIcon(rotated_pixmap))
    
    def start_reload_animation(self):
        if not self.parent.rotation_timer.isActive():
            self.parent.rotation_timer.start(0.01)  # adjust speed here (ms per frame)
    
    def stop_reload_animation(self):
        if self.parent.rotation_timer.isActive():
            self.parent.rotation_timer.stop()
        # reset icon to upright
        self.rotation_angle = 0
        self.parent.reload_btn.setIcon(get_normIcon("reload"))

    def setup_colourPalette_button(self, Colourdata):
        self.colourpalette_btn = QToolButton(self.parent)
        self.colourpalette_btn.setToolTip("Colour Palettes")
        self.ColourMenu = QMenu(self.parent)
        
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
            Cwidget_action = QWidgetAction(self.parent)
            Cwidget_action.setDefaultWidget(Cwidget)
            Cwidget_action.setData(key)
            Cwidget_action.triggered.connect(lambda checked, p=key, d=Colourdata: self.parent.SelectColourTheme(p, d))
            self.ColourMenu.addAction(Cwidget_action)

        
        self.colourpalette_btn.setMenu(self.ColourMenu)
        self.colourpalette_btn.setIcon(get_normIcon("colourpalette"))

        # When the main button is clicked, read the current selectedprofile at click time
        self.colourpalette_btn.clicked.connect(lambda checked=False, d=Colourdata: self.parent.ToggleColourTheme(self.parent.selectedprofile, d))

        self.colourpalette_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.parent.nav_bar.addWidget(self.colourpalette_btn)
        self.eColsButton.append("colourpalette_btn")

        self.colourpalette_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.colourpalette_btn.customContextMenuRequested.connect(lambda pos, b=self.colourpalette_btn: self.parent.displayContextMenu(pos, b))

        return self.colourpalette_btn, self.ColourMenu

    def setup_engine_button(self, engines):
        self.engine_btn = QToolButton(self.parent)
        self.engine_btn.setText("Search With...")
        self.browserMenu = QMenu(self.parent)
        self.engine_btn.setToolTip("Select/Switch Search Engines")

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
            widget_action = QWidgetAction(self.parent)
            widget_action.setDefaultWidget(widget)
            widget_action.setData((key, search_url))
            widget_action.triggered.connect(lambda checked, k=key: self.parent.set_engine(k))
            self.browserMenu.addAction(widget_action)
            
        self.engine_btn.setMenu(self.browserMenu)
        self.engine_btn.setIcon(QIcon(str(icon_cache_dir / f"{self.parent.engine}")))

        self.engine_btn.clicked.connect(lambda: self.parent.current_browser.setUrl(QUrl(engines[self.parent.engine].split('/search?q=')[0])))

        self.engine_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.parent.nav_bar.addWidget(self.engine_btn)

        self.engine_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.engine_btn.customContextMenuRequested.connect(lambda pos, b=self.engine_btn: self.parent.displayContextMenu(pos, b))

        self.parent.set_engine(self.parent.engine)

        return self.engine_btn, self.browserMenu


    def setup_cookie_button(self):
        self.eColsButton.append("cookie_btn")
        self.cookie_btn = QToolButton(self.parent)
        self.cookie_btn.setText("cookie_btn")
        self.cookie_btn.setToolTip("Accept/Deny Cookies")
        self.cookieMenu = QMenu(self.parent)
        setattr(self, "cookie_btn", self.cookie_btn)

        self.cookie_btn.setMenu(self.cookieMenu)
        self.cookie_btn.setIcon(get_normIcon("cookie"))
        self.cookie_btn.setPopupMode(QToolButton.InstantPopup)
        self.nav_bar.addWidget(self.cookie_btn)

        self.cookie_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.cookie_btn.customContextMenuRequested.connect(lambda pos, b=self.cookie_btn: self.parent.displayContextMenu(pos, b))

        return self.cookie_btn, self.cookieMenu
    
    def update_cookie_menu(self, row_colour):
        #Scroll bar system
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {self.parent.hexval};
                border: none;
            }}
            /* Target the internal container specifically */
            QScrollArea > QWidget > QWidget {{ 
                background-color: {self.parent.hexval};
            }}
            /* Custom Scrollbar styling to make it look modern */
            QScrollBar:vertical {{
                border: none;
                background: {self.parent.hexval};
                width: 8px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 0.3); /* Semi-transparent white */
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        # Set max height to prevent the menu from growing off-screen
        scroll_area.setMaximumHeight(400)
        scroll_area.setFixedWidth(500)

        #Row Containers
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(8)

        #Add rows to scroll bar
        for cookieID, value in self.parent.cookiedict.items():
            cookie_row = QWidget()
            cookie_row.setObjectName("CookieRow")
            row_layout = QHBoxLayout(cookie_row)
            
            name = (value["name"][:15] + "..") if len(value["name"]) > 15 else value["name"]
            name_label = QLabel(name)
            predict_label = QLabel(f"({value['prediction']})")
            predict_label.setStyleSheet(f"color: {self.parent.hexval}; font-size: 10px;")
            
            btn_accept = QPushButton("✓")
            btn_deny = QPushButton("✕")

            btn_accept.setStyleSheet(f"background-color: {self.parent.hexval}; color: {row_colour};")
            btn_deny.setStyleSheet(f"background-color: {self.parent.hexval}; color: {row_colour};")
            
            # Connect buttons (using the handle_cookie_action from previous step)
            btn_accept.clicked.connect(lambda _, Cid=cookieID: self.parent.handle_cookie_action(Cid, "accept"))
            btn_deny.clicked.connect(lambda _, Cid=cookieID: self.parent.handle_cookie_action(Cid, "deny"))

            row_layout.addWidget(name_label)
            row_layout.addWidget(predict_label)
            row_layout.addStretch()
            row_layout.addWidget(btn_accept)
            row_layout.addWidget(btn_deny)

            # Styling
            cookie_row.setStyleSheet(f"#CookieRow {{ background-color: {row_colour}; border-radius: 6px; }}")
            
            container_layout.addWidget(cookie_row)

        # Add a stretch at the end to keep rows at the top if there are few
        container_layout.addStretch()
        
        #Apply widget to scroll area
        scroll_area.setWidget(container_widget)
        
        # Host the entire ScrollArea inside one QWidgetAction
        menu_scroll_action = QWidgetAction(self.cookieMenu)
        menu_scroll_action.setDefaultWidget(scroll_area)
        self.cookieMenu.addAction(menu_scroll_action)

        return self.cookieMenu
    

    def get_muted_icon(self, original_icon):
        # Convert your existing icon into a pixel map (standard 16x16 size for tabs)
        pixmap = original_icon.pixmap(16, 16)
        
        # Initialize a painter to draw directly onto the image
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Define a thick, clean red line for the slash
        pen = QPen(QColor("red"), 2) 
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Draw a diagonal line from top-right to bottom-left
        painter.drawLine(14, 2, 2, 14)
        painter.end()
        
        # Return it as a brand new QIcon
        return QIcon(pixmap)
    


class VerticalTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.hovered_index = -1
        self.update_close_buttons()
        self.update_hover_from_cursor()
        self.currentChanged.connect(lambda _: self.update_hover_from_cursor())
        self.tabMoved.connect(lambda *_: self.update_hover_from_cursor())
        QTimer.singleShot(0, self.hideStarterTabClose)
        self.hover_timer = QTimer(self)
        self.hover_timer.timeout.connect(self.update_hover_from_cursor)
        self.hover_timer.start(16)

        #Compact mode systems
        self.autoCompact = True
        self.compact_mode = True
        self.expanded_width = 200
        self.collapsed_width = 48

        self.width_anim = QPropertyAnimation(self, b"minimumWidth")
        self.width_anim.setDuration(300)
        self.width_anim.setEasingCurve(QEasingCurve.OutQuint)
        self.setMinimumWidth(self.collapsed_width)
        self.setMaximumWidth(self.expanded_width)

        self.compact_timer = QTimer(self)
        self.compact_timer.setSingleShot(True)
        self.compact_timer.timeout.connect(lambda: (self.set_compact_mode(True), self.update_close_buttons()))

        self.width_anim.valueChanged.connect(lambda v: self.setMaximumWidth(v) if self.compact_mode else None)

        #Toggle Mode Pin Button
        self.pin_btn = QPushButton(self)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setToolTip("Pin Tab Bar")
        self.pin_btn.clicked.connect(self.toggle_pin)
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                outline: none;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 5px; 
            }
        """)

        self.default_pin_path = f"{srcSourceDir}/ui/icon_cache/pintabs.png"
        self.pin_btn.setIconSize(QSize(24, 24))

    def toggle_pin(self, checked):
        self.autoCompact = not checked
        if checked:
            self.compact_timer.stop()
            self.set_compact_mode(False)
        else:
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self.compact_timer.start(500)
                
        self.update_pin_icon() # This handles the rotation logic

    def update_pin_icon(self):
        size = self.pin_btn.iconSize()
        if size.width() <= 0: size = QSize(24, 24)
        pixmap = QPixmap(self.default_pin_path).scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        
        if pixmap.isNull():
            print(f"Error: Could not load icon at {self.default_pin_path}")
            return
        
        if not self.autoCompact:
            rotated = QPixmap(pixmap.size())
            rotated.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rotated)
            if painter.isActive() or painter.begin(rotated):
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.translate(rotated.width() / 2, rotated.height() / 2)
                painter.rotate(-45)
                painter.drawPixmap(-pixmap.width() / 2, -pixmap.height() / 2, pixmap)
                painter.end()
                pixmap = rotated

        self.pin_btn.setIcon(QIcon(pixmap))
        self.pin_btn.setIconSize(QSize(20, 20)) # Slightly smaller than the 30px button

    def update_pin_button_pos(self):
        btn_size = 30
        x = (self.width() - btn_size) // 2
        y = self.height() - btn_size - 5  # 5px padding from bottom
        self.pin_btn.setGeometry(x, y, btn_size, btn_size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_pin_button_pos()

    def enterEvent(self, event):
        if self.autoCompact:
            self.compact_timer.stop()
            self.set_compact_mode(False)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.autoCompact:
            self.compact_timer.start(500)
        super().leaveEvent(event)



    def tabSizeHint(self, index):
        # This makes the tabs follow the animation frame-by-frame
        return QSize(self.width(), 35) 

    def set_compact_mode(self, enabled: bool):
        if self.compact_mode == enabled:
            return
        self.compact_mode = enabled
        
        target = self.collapsed_width if enabled else self.expanded_width
        
        self.width_anim.stop()
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(target)
        
        # Force the maximum width to expand so the minimum animation isn't blocked
        if not enabled: 
            self.setMaximumWidth(self.expanded_width)
        
        self.width_anim.start()

    def update_hover_from_cursor(self):
        pos = self.mapFromGlobal(QCursor.pos())

        if not self.rect().contains(pos):
            new_hover = -1
        else:
            new_hover = self.tabAt(pos)

        if new_hover != self.hovered_index:
            self.hovered_index = new_hover
            self.update_close_buttons()
            self.update()

    def update_close_buttons(self):
        for i in range(self.count()):
            btn = self.tabButton(i, QTabBar.RightSide)

            if btn:
                btn.move(
                    self.tabRect(i).right() - btn.width() - 5,
                    self.tabRect(i).center().y() - btn.height() // 2
                )

                is_hovered = (i == self.hovered_index)
                btn.setVisible(is_hovered)

    def hideStarterTabClose(self):
        for i in range(self.count()):
            btn = self.tabButton(i, QTabBar.RightSide)
            if btn:
                btn.hide()

    def paintEvent(self, event):
        painter = QStylePainter(self)

        for i in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, i)

            text = option.text
            icon = self.tabIcon(i)

            # Remove both so Qt doesn't draw them
            option.text = ""
            option.icon = QIcon()

            # Draw tab background + state
            painter.drawControl(QStyle.CE_TabBarTab, option)

            rect = self.tabRect(i)

            # --- ICON ---
            icon_size = QSize(16, 16)
            if self.compact_mode:
                icon_x = rect.center().x() - icon_size.width() // 2
            else:
                icon_x = rect.left() + 8
            icon_y = rect.center().y() - icon_size.height() // 2

            if not icon.isNull():
                painter.drawPixmap(
                    icon_x,
                    icon_y,
                    icon.pixmap(icon_size)
                )

            # --- TEXT ---
            if self.width() > self.collapsed_width + 20:

                text_color = self.tabTextColor(i)

                painter.setPen(text_color)

                text_rect = QRect(
                    icon_x + icon_size.width() + 6,
                    rect.top(),
                    rect.width() - (icon_size.width() + 10),
                    rect.height()
                )

                painter.drawText(
                    text_rect,
                    Qt.AlignVCenter | Qt.AlignLeft,
                    text
                )


class DynamicRatioButton(QPushButton):
    def __init__(self, name, ratio, parent=None):
        super().__init__(name, parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ratio = ratio


    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_height = int(self.width() / self.ratio)
        self.setFixedHeight(new_height)


class SystemHelperUI(QDialog):
    def __init__(self, parent, displayData, buttonClicked, selectedFromSettings):
        super().__init__(parent)
        self.setWindowTitle("Midnight Watch Help")
        self.resize(900, 600)
        self.setWindowIcon(get_normIcon("tightlyCroppedIcon.png"))
        self.parent = parent
        self.displayData = displayData
        self.ratio_buttons = []
        self.buttonClicked = buttonClicked
        self.sidebar_buttons = {}
        self.selectedFromSettings = selectedFromSettings

        self.NormalStyle = """
            QPushButton {
                background-color: rgb(60,60,75);
                color:white;
                border:2px solid rgb(63,129,255);
                border-radius:5px;
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
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(45, 45, 60);
            }
        """)

        # Main horizontal layout for the dialog window
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # LEFT SIDEBAR: Outer Scroll Area
        sidebarFrame = QWidget()
        sidebarFrame.setObjectName("sidebarFrame")
        sidebarFrame.setStyleSheet("""
            QWidget#sidebarFrame{
                background-color: rgb(45,45,60);
                border-radius:15px;
                border:5px solid #3f81ff;
            }
        """)
        sidebarLayout = QVBoxLayout(sidebarFrame)
        sidebarLayout.setContentsMargins(15,15,15,15)



        self.dataSelectArea = QScrollArea()
        self.dataSelectArea.setObjectName("dataSelectArea")
        self.dataSelectArea.setWidgetResizable(True)
        self.dataSelectArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dataSelectArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dataSelectArea.setStyleSheet("""
            QScrollArea#dataSelectArea{
                background-color: rgb(45, 45, 60);
                border: none;
                border-radius:15px;
            }
            QScrollBar:vertical {
                background: rgb(45, 45, 60);
                width: 12px;
                border-radius:15px;
            }
            QScrollBar::handle:vertical {
                background: rgb(85, 85, 105);
            }
            QScrollBar::handle:vertical:hover {
                background: rgb(110, 110, 135);
            }
        """)
        self.dataSelectArea.viewport().setStyleSheet("""
            background-color: rgb(45,45,60);
            border-radius:15px;
        """)

        # LEFT SIDEBAR: Inner Container Widget
        self.dataSelectContainer = QWidget()

        # Layout inside the left sidebar container
        self.buttonBox = QVBoxLayout(self.dataSelectContainer)
        self.buttonBox.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.buttonBox.setSpacing(15)
        self.buttonBox.setContentsMargins(15, 15, 15, 15)

        for key, value in self.displayData.items():
            self.buttonBox.addStretch()
            
            name = value[1]

            icon = QIcon()
            iconPixmap = (QPixmap(f"{srcSourceDir}/ui/icon_cache/{value[2]}"))
            icon.addPixmap(iconPixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))            


            btn = DynamicRatioButton(name=name, ratio=3)
            btn.setIcon(icon)
            btn.setStyleSheet(self.NormalStyle)
            self.ratio_buttons.append(btn)
            

            internal_id = value[1]
            self.sidebar_buttons[internal_id] = btn



            self.buttonBox.addWidget(btn)

            btn.clicked.connect(lambda checked=False, iid=internal_id: self.selectButton(iid))



        # Attach inner container to the left scroll area
        self.dataSelectArea.setWidget(self.dataSelectContainer)

        # RIGHT CONTENT: Main Area
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_area.setStyleSheet("""
            QScrollArea {
                background-color: rgb(45, 45, 60); 
                border-radius: 15px; 
                border: 5px solid #3f81ff;
            }
        """)

        sidebarLayout.addWidget(self.dataSelectArea)
        main_layout.addWidget(sidebarFrame, stretch=3)
        main_layout.addWidget(self.content_area, stretch=10)

        if not self.selectedFromSettings:
            QTimer.singleShot(0, lambda: self.selectButton(self.buttonClicked))
        else:
            self.renderMainUI("Starting")

    def selectButton(self, selected_id):
        self.buttonClicked = selected_id
        for internal_id, btn in self.sidebar_buttons.items():
            if internal_id == selected_id:
                btn.setStyleSheet(self.SelectedStyle)
                self.renderMainUI(self.buttonClicked)
            else:
                btn.setStyleSheet(self.NormalStyle)
    
    def renderMainUI(self, SelectedUI):
        print(SelectedUI)
        
        self.contentWidget = QWidget()

        self.contentLayout = QVBoxLayout()
        self.contentLayout.setContentsMargins(20, 20, 20, 20)
        self.contentLayout.setSpacing(20)
        self.contentWidget.setStyleSheet("background: transparent;")


        title = QLabel(SelectedUI + " Help")
        title.setStyleSheet("""
            color: #3f81ff;
            font-size: 25px;
            font-weight: 800;
        """)
        self.contentLayout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        self.contentLayout.addSpacing(35)


        data = self.returnMainDisplay(SelectedUI)
        for key, value in data.items():
            if "text" in key:
                text = QLabel(value)
                text.setStyleSheet("""
                    color: white;
                    font-size: 15px;
                    line-height: 1.6;
                    margin-bottom: 20px;
                """)            
                self.contentLayout.addWidget(text, alignment=Qt.AlignmentFlag.AlignLeft)
            
            if "image" in key:
                image = QPixmap(value)
                if not image.isNull():
                    imageScaled = image.scaled(self.contentWidget.width()/1.2, self.contentWidget.height()/1.2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    label = QLabel()
                    label.setStyleSheet("border-radius: 15px; border: 4px solid #3f81ff;")
                    label.setPixmap(imageScaled)
                    label.setToolTip(value)
                    self.contentLayout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)
            
            if "subtitle" in key:
                subtitle = QLabel(value)
                subtitle.setStyleSheet("""
                    color: #ffeb78;
                    font-size: 20px;
                    font-weight: 700;
                    line-height: 2;
                    margin-bottom: 25px;
                    text-decoration: underline;
                """) 
                self.contentLayout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignLeft)


        self.contentLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.contentWidget.setLayout(self.contentLayout)
        self.content_area.setWidget(self.contentWidget)


    def returnMainDisplay(self, SelectedUI):
        DisplayUIText = {
            "Back" : {
                "subtitle1": "The back button",
                "text1": "This is the back button!",
                "image1": f"{srcSourceDir}/ui/images/MainImageBackground.png",
                "text2": "This is the image",
                "text3": "If I provide enough text here \n\n this should \n\n begin to \n\n overflow \n\n off the screen"
            },
            "Forward": {
                "text1": "The forward button",
                "image1": ""
            },
            "Home": {
                "text1": "The home button",
                "image1": ""
            },
            "Reload": {
                "text1": "The reload button",
                "image1": ""
            },
            "Settings": {
                "text1": "The settings button",
                "image1": ""
            },
            "New Tab": {
                "text1": "The new tab button",
                "image1": ""
            },
            "Colour Palettes": {
                "text1": "The colour palettes button",
                "image1": ""
            },
            "Engines": {
                "text1": "The engine button",
                "image1": ""
            },
            "Cookies": {
                "text1": "The cookies button",
                "image1": ""
            },
            "Tabs": {
                "text1": "The tabs display",
                "image1": ""
            },
            "Bookmarks": {
                "text1": "The bookmarks display",
                "image1": ""
            },
            "Url Bar": {
                "text1": "The url bar",
                "image1": ""
            },
            "Zooming": {
                "text1": "Zooming is",
                "image1": ""
            },
            "Profiles": {
                "text1": "Profiles are",
                "image1": ""
            },
            "Status Bar": {
                "text1": "The status bar is",
                "image1": ""
            }
        }

        return DisplayUIText[SelectedUI]

        